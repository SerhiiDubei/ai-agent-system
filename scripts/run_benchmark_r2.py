"""Sprint 5.5 — Benchmark Round 2: Premium Models + Human Evaluation.

Tests expensive models: gpt-4o, claude-3-5-sonnet, claude-3-opus.
Output: concise human-readable summaries (3 proposals per agent).
NO automated scoring — you grade manually after reading.

Also includes drafter diagnostics to understand haiku/sonnet failures.

Usage:
    python scripts/run_benchmark_r2.py
"""
from __future__ import annotations

import asyncio
import sys
import time
import textwrap
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from ai_agent_system.config import settings
from ai_agent_system.benchmark.types import PageElements, PainPointList, ABHypothesis, estimate_cost
from ai_agent_system.marketing.models import MarketingContext
from ai_agent_system.marketing.drafter import DrafterDeps, SYSTEM_PROMPT, _BRIEF_PROMPT

W = 72  # output width


# ── Shared ────────────────────────────────────────────────────────────────────

def make_model(model_id: str) -> OpenAIModel:
    return OpenAIModel(
        model_name=model_id,
        provider=OpenAIProvider(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key.get_secret_value(),
        ),
    )


def wrap(text: str, indent: int = 8) -> str:
    return textwrap.fill(text, width=W, initial_indent=" " * indent,
                         subsequent_indent=" " * indent)


def sep(char: str = "─") -> None:
    print(char * W)


# ── Test inputs (same as Round 1) ────────────────────────────────────────────

WALK_IN_TUB_BRIEF = """\
Walk-in shower conversion funnel for 65+ homeowners in Florida.
Traffic source: Meta (Facebook/Instagram). Goal: ZIP code submit for free estimate.
Target: seniors with mobility limitations or fall risk who struggle with traditional
tub access. Also targeting adult children researching renovation options for aging parents.
Renovation budget tier: $8,000–$25,000. Local Florida licensed contractors handle install.
Key differentiator: no long renovations, installed in one day.
"""

WALK_IN_TUB_DEPS = DrafterDeps(
    niche="walk-in-shower",
    parent_category="home-improvement",
    market="US-FL",
    language="en",
    traffic_source_primary="meta",
    page_goal="zip_submit",
    primary_metric="cost_per_lead",
    brief=WALK_IN_TUB_BRIEF,
    business_constraints="Must comply with Meta Special Ad Categories (housing)",
    retrieved_chunks=[],
)

HOMEIQ_MARKDOWN = """\
# No More Long Shower Renovations… Try This Instead.

Worried about the cost and time of a major bathroom overhaul? Walk-in showers offer
a surprisingly fast and affordable solution for homeowners who are tired of struggling
with traditional tub access.

## You don't have to pay a fortune OR spend weeks remodelling your bathroom

Many homeowners assume that upgrading their bathroom means weeks of construction and
tens of thousands of dollars. But modern walk-in shower systems can be installed in
as little as one day — without tearing out your entire bathroom.

**Get a Free Price** — no obligation, no high-pressure sales.

## What is walk-in shower?

A walk-in shower is a barrier-free bathing area with no tub to step over. This makes
it significantly safer for seniors, people with limited mobility, or anyone who has
experienced a slip or fall in the bathroom.

Key benefits:
- No threshold to step over (eliminates trip hazard)
- Easy wheelchair and walker access
- Lower maintenance than traditional tubs
- Can be installed over existing tub space

## What kind of options are there?

Walk-in showers come in a variety of sizes and configurations:
- Pre-fabricated kits (fastest install, lowest cost)
- Custom tile work (most personalized, higher cost)
- Roll-in designs (ADA compliant, ideal for wheelchair users)

## What is the cost?

Installation typically ranges from $3,000 to $15,000 depending on size,
materials, and local labor rates. Many contractors offer financing.

**Click to Get a Price** — free, no-obligation estimate from local installers.

## How can I get started?

Simply enter your ZIP code above to be connected with licensed local contractors
in your area who specialize in walk-in shower installation.

Step 1: Enter ZIP code
Step 2: Receive quotes from 2-3 local contractors
Step 3: Choose the option that fits your budget and timeline

★★★★★ "We had ours installed in one day. My mother can now shower safely without help."
— Linda K., Tampa FL

BBB Accredited | Licensed & Insured | Serving Florida Since 2008
"""

SEMANTIC_PROMPT = f"""\
Analyze this landing page content and extract its key semantic elements.
Be precise — extract what's actually present on the page.

PAGE CONTENT:
\"\"\"
{HOMEIQ_MARKDOWN}
\"\"\"

Extract: primary CTA, hero headline, lead form presence, trust signals, key benefits.
Rate your confidence from 0.0 to 1.0.
"""

PAIN_POINT_PROMPT = f"""\
You are analyzing a landing page for walk-in shower installations targeting seniors (65+)
and their adult children. Mine 3-5 concrete pain points embedded in this page copy.

Each pain point MUST have a trigger situation. Format:
"<when this situation happens> → <specific fear/pain felt>"

NO platitudes like "peace of mind" or "better life" — those are forbidden.

PAGE:
\"\"\"
{HOMEIQ_MARKDOWN}
\"\"\"

Identify: pain points with triggers, primary emotion, urgency level, audience age skew.
"""

HYPOTHESIS_PROMPT = """\
You are a senior CRO strategist. Generate ONE high-priority A/B test hypothesis
for this landing page.

PAGE CONTEXT:
- URL: homeiq.io/article/walk-in-shower/
- Traffic: Meta (Facebook/Instagram) — visitor was NOT actively searching
- Goal: ZIP code submit for free estimate
- Audience: 65+ homeowners + adult children in Florida
- Headline: "No More Long Shower Renovations… Try This Instead."
- CTA: "Get a Free Price" / "Click to Get a Price"
- Trust: BBB badge, "Licensed & Insured", one 5-star testimonial

Observation: Headline uses negative framing. CTA has no urgency or benefit specificity.
Meta visitors were not searching — they need a stronger interrupt hook.

Produce: specific element to test, exact control vs. variant copy, rationale grounded
in conversion psychology, primary metric, expected lift %, risk level.
"""


# ── Output printers ───────────────────────────────────────────────────────────

def print_header(test_id: int, operation: str, model_id: str) -> None:
    sep("═")
    print(f"  TEST {test_id:02d}: {operation}  /  {model_id}")
    sep("═")


def print_stats(latency_ms: int, inp: int, out: int, model_id: str) -> None:
    cost = estimate_cost(model_id, inp, out)
    print(f"  Time: {latency_ms/1000:.1f}s  |  Tokens: {inp}in / {out}out  |  Cost: ${cost:.4f}")
    sep()


def print_drafter_summary(ctx: MarketingContext) -> None:
    print(f"\n  PERSONAS ({len(ctx.personas)} total):\n")
    for i, p in enumerate(ctx.personas[:3], 1):
        role_tag = f"[{p.role}]" if hasattr(p, "role") else ""
        income = getattr(p, "income_band", "?")
        print(f"  [{i}] \"{p.name}\" {role_tag} income:{income}")
        job = getattr(p, "primary_job", "")
        if job:
            print(wrap(f"JTBD → {job}"))
        pains = getattr(p, "pain_points", [])
        if pains:
            first_pain = pains[0]
            pain_text = getattr(first_pain, "description", str(first_pain))
            print(wrap(f"Pain → {pain_text}"))
        print()

    ch = ctx.channel_profile
    ch_channel = getattr(ch, "channel", "?")
    hook = getattr(ch, "interrupt_hook", None) or getattr(ch, "value_prop", None) or ""
    trust = getattr(ch, "trust_needs", [])
    print(f"  CHANNEL: {ch_channel}")
    if hook:
        print(wrap(f"Hook → {hook}"))
    if trust:
        print(f"  Trust needs: {', '.join(str(t) for t in trust[:3])}")


def print_semantic_summary(el: PageElements) -> None:
    print(f"\n  PRIMARY CTA:  \"{el.primary_cta}\"")
    print(f"  HERO:         \"{el.hero_headline[:70]}\"")
    print(f"  FORM:         {'YES' if el.lead_form_present else 'NO'}")
    print(f"  CONFIDENCE:   {el.confidence:.2f}")
    print(f"\n  TRUST SIGNALS ({len(el.trust_signals)}):")
    for ts in el.trust_signals[:4]:
        print(f"    • {ts}")
    print(f"\n  KEY BENEFITS ({len(el.key_benefits)}):")
    for b in el.key_benefits[:3]:
        print(f"    • {b}")


def print_pain_points_summary(pp: PainPointList) -> None:
    print(f"\n  EMOTION:  {pp.target_emotion}")
    print(f"  URGENCY:  {pp.urgency_level}  |  AGE SKEW: {pp.audience_age_skew}")
    print(f"\n  PAIN POINTS ({len(pp.pain_points)}):\n")
    for i, pain in enumerate(pp.pain_points[:4], 1):
        print(f"  [{i}] {pain[:100]}")
        if len(pain) > 100:
            print(wrap(pain[100:], indent=6))
        print()


def print_hypothesis_summary(h: ABHypothesis) -> None:
    print(f"\n  ELEMENT:    {h.element}")
    print(f"  RISK:       {h.risk_level.upper()}")
    print(f"  METRIC:     {h.primary_metric}")
    print(f"  LIFT:       {h.expected_lift}")
    print(f"\n  CONTROL:")
    print(wrap(h.control))
    print(f"\n  VARIANT:")
    print(wrap(h.variant))
    print(f"\n  RATIONALE:")
    print(wrap(h.rationale))


# ── Per-operation runners ─────────────────────────────────────────────────────

async def run_drafter(model_id: str, verbose_errors: bool = True) -> tuple[MarketingContext | None, int, int, str | None]:
    """Returns (output, input_tokens, output_tokens, error_msg)."""
    agent: Agent[None, MarketingContext] = Agent(
        model=make_model(model_id),
        output_type=MarketingContext,
        system_prompt=SYSTEM_PROMPT,
        model_settings={"temperature": 0.3},
        retries=2,
    )
    constraints_line = f"- business_constraints: {WALK_IN_TUB_DEPS.business_constraints}"
    prompt = _BRIEF_PROMPT.format(
        brief=WALK_IN_TUB_DEPS.brief,
        niche=WALK_IN_TUB_DEPS.niche,
        parent_category=WALK_IN_TUB_DEPS.parent_category,
        market=WALK_IN_TUB_DEPS.market,
        language=WALK_IN_TUB_DEPS.language,
        traffic_source_primary=WALK_IN_TUB_DEPS.traffic_source_primary,
        page_goal=WALK_IN_TUB_DEPS.page_goal,
        primary_metric=WALK_IN_TUB_DEPS.primary_metric,
        constraints_line=constraints_line,
    )
    try:
        result = await agent.run(prompt)
        u = result.usage()
        return result.output, u.input_tokens or 0, u.output_tokens or 0, None
    except Exception as exc:
        err = str(exc)
        return None, 0, 0, err


async def run_semantic(model_id: str) -> tuple[PageElements | None, int, int, str | None]:
    agent: Agent[None, PageElements] = Agent(
        model=make_model(model_id),
        output_type=PageElements,
        system_prompt="You are a CRO analyst extracting semantic elements from landing pages.",
        model_settings={"temperature": 0.1},
        retries=1,
    )
    try:
        result = await agent.run(SEMANTIC_PROMPT)
        u = result.usage()
        return result.output, u.input_tokens or 0, u.output_tokens or 0, None
    except Exception as exc:
        return None, 0, 0, str(exc)


async def run_pain_points(model_id: str) -> tuple[PainPointList | None, int, int, str | None]:
    agent: Agent[None, PainPointList] = Agent(
        model=make_model(model_id),
        output_type=PainPointList,
        system_prompt="You are a direct-response copywriter identifying pain points.",
        model_settings={"temperature": 0.2},
        retries=1,
    )
    try:
        result = await agent.run(PAIN_POINT_PROMPT)
        u = result.usage()
        return result.output, u.input_tokens or 0, u.output_tokens or 0, None
    except Exception as exc:
        return None, 0, 0, str(exc)


async def run_hypothesis(model_id: str) -> tuple[ABHypothesis | None, int, int, str | None]:
    agent: Agent[None, ABHypothesis] = Agent(
        model=make_model(model_id),
        output_type=ABHypothesis,
        system_prompt="You are a senior CRO strategist generating A/B test hypotheses.",
        model_settings={"temperature": 0.3},
        retries=1,
    )
    try:
        result = await agent.run(HYPOTHESIS_PROMPT)
        u = result.usage()
        return result.output, u.input_tokens or 0, u.output_tokens or 0, None
    except Exception as exc:
        return None, 0, 0, str(exc)


# ── Test matrix ───────────────────────────────────────────────────────────────

TEST_CASES = [
    # (test_id, operation, model_id)
    # ── Drafter: needs smart model (cheap models fail strict Pydantic schema) ──
    (1,  "drafter",             "openai/gpt-4o"),                 # proven baseline
    (2,  "drafter",             "anthropic/claude-sonnet-4.6"),   # newest Claude
    (3,  "drafter",             "deepseek/deepseek-chat"),        # dark horse: cheap+smart
    # ── Semantic extractor: test ultra-cheap models ──
    (4,  "semantic_extractor",  "openai/gpt-4.1-nano"),           # $0.10/1M
    (5,  "semantic_extractor",  "openai/gpt-5-nano"),             # $0.05/1M (cheapest)
    (6,  "semantic_extractor",  "google/gemini-2.5-flash"),       # Google mid-tier
    # ── Pain point miner: mid-range ──
    (7,  "pain_point_miner",    "openai/gpt-4.1-mini"),           # $0.40/1M
    (8,  "pain_point_miner",    "deepseek/deepseek-chat"),        # $0.32/1M
    # ── Hypothesis generator: premium comparison ──
    (9,  "hypothesis_generator","openai/gpt-5"),                  # newest OpenAI
    (10, "hypothesis_generator","anthropic/claude-sonnet-4.6"),   # newest Claude
]

RUNNERS = {
    "drafter":             (run_drafter,     print_drafter_summary),
    "semantic_extractor":  (run_semantic,    print_semantic_summary),
    "pain_point_miner":    (run_pain_points, print_pain_points_summary),
    "hypothesis_generator":(run_hypothesis,  print_hypothesis_summary),
}


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    sep("═")
    print("  Sprint 5.5 — Round 2: Premium Models | Human Evaluation")
    print(f"  {len(TEST_CASES)} tests  |  Models: gpt-4o, claude-3-5-sonnet, claude-3-opus")
    print("  No auto-scoring — review output below and grade manually.")
    sep("═")
    print()

    total_cost = 0.0
    results_log: list[str] = []

    for test_id, operation, model_id in TEST_CASES:
        print_header(test_id, operation, model_id)

        runner_fn, printer_fn = RUNNERS[operation]
        t0 = time.monotonic()
        output, inp, out, error = await runner_fn(model_id)
        latency_ms = int((time.monotonic() - t0) * 1000)

        if error:
            print(f"\n  ✗ FAILED ({latency_ms/1000:.1f}s)")
            sep()
            # Show first 300 chars of error for diagnosis
            short_err = error[:300].replace("\n", " ")
            print(f"  ERROR: {short_err}")
            results_log.append(f"✗ {test_id:02d} {operation}/{model_id} — FAILED: {short_err[:80]}")
        else:
            print_stats(latency_ms, inp, out, model_id)
            printer_fn(output)
            cost = estimate_cost(model_id, inp, out)
            total_cost += cost
            results_log.append(f"✓ {test_id:02d} {operation}/{model_id} — OK (${cost:.4f}, {latency_ms/1000:.1f}s)")

        print()

    # Final cost summary
    sep("═")
    print(f"  ROUND 2 COMPLETE  |  Total cost: ${total_cost:.4f}")
    sep()
    print("  Results log:")
    for line in results_log:
        print(f"    {line}")
    sep("═")

    # Save log
    log_path = ROOT / "docs" / "benchmark_r2_log.txt"
    log_path.parent.mkdir(exist_ok=True)
    log_path.write_text("\n".join(results_log), encoding="utf-8")
    print(f"\n  Log saved: {log_path}")


if __name__ == "__main__":
    asyncio.run(main())
