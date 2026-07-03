"""Sprint 5.5 — Model Benchmark Gate.

Runs 10 (operation × model) combinations and produces:
  - Terminal table with results
  - docs/benchmark_report.md
  - configs/llm_routing.yml (recommended routing)

Usage:
    python scripts/run_benchmark.py

No server required — runs directly against OpenRouter API.
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

# Resolve project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from ai_agent_system.config import settings
from ai_agent_system.benchmark.types import (
    PageElements, PainPointList, ABHypothesis,
    TestResult, estimate_cost,
)
from ai_agent_system.benchmark.scorer import (
    score_drafter, score_semantic, score_pain_points, score_hypothesis,
)
from ai_agent_system.marketing.models import MarketingContext
from ai_agent_system.marketing.drafter import DrafterDeps, SYSTEM_PROMPT, _BRIEF_PROMPT


# ── Shared helpers ────────────────────────────────────────────────────────────

def make_model(model_id: str) -> OpenAIModel:
    return OpenAIModel(
        model_name=model_id,
        provider=OpenAIProvider(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key.get_secret_value(),
        ),
    )


# ── Test inputs ───────────────────────────────────────────────────────────────

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

# Excerpt from homeiq.io article (walk-in shower niche — real competitor page)
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
Be precise and extract what's actually present on the page.

PAGE CONTENT:
\"\"\"
{HOMEIQ_MARKDOWN}
\"\"\"

Extract: primary CTA, hero headline, lead form presence, trust signals, key benefits.
Rate your confidence in the extraction from 0.0 to 1.0.
"""

PAIN_POINT_PROMPT = f"""\
You are analyzing a landing page for walk-in shower installations targeting seniors (65+)
and their adult children. Mine the concrete pain points embedded in this page copy.

Each pain point must have a TRIGGER SITUATION, not be a vague sentiment.
Format: "<when this situation happens> → <specific pain/fear felt>"

PAGE CONTENT:
\"\"\"
{HOMEIQ_MARKDOWN}
\"\"\"

Extract 3-5 pain points with triggers. Identify target emotion and urgency level.
"""

HYPOTHESIS_PROMPT = """\
You are a senior CRO strategist. Based on the following landing page analysis,
generate ONE high-priority A/B test hypothesis.

PAGE CONTEXT:
- URL: homeiq.io/article/walk-in-shower/no-more-long-shower-renovations/
- Traffic: Meta (Facebook/Instagram) — push interrupt, visitor was not searching
- Goal: ZIP code submit for free estimate
- Audience: 65+ homeowners + adult children in Florida
- Current headline: "No More Long Shower Renovations… Try This Instead."
- Current CTA: "Get a Free Price" / "Click to Get a Price"
- Trust signals: BBB badge, "Licensed & Insured", one testimonial

Key observation: The headline uses negative framing ("No More Long...") and
the CTA copy "Get a Price" is generic with no urgency or specific benefit.
Visitors from Meta were not actively searching — they need a stronger hook.

Generate one specific, actionable A/B hypothesis with concrete control vs. variant.
"""


# ── Test case definitions ─────────────────────────────────────────────────────

TEST_CASES = [
    # (test_id, operation, model_id)
    (1,  "drafter",             "openai/gpt-4o-mini"),
    (2,  "drafter",             "anthropic/claude-3-5-haiku"),          # claude-3-haiku fails complex schema
    (3,  "drafter",             "meta-llama/llama-3.1-8b-instruct"),    # free tier
    (4,  "semantic_extractor",  "openai/gpt-4o-mini"),
    (5,  "semantic_extractor",  "anthropic/claude-3-haiku"),
    (6,  "semantic_extractor",  "meta-llama/llama-3.1-8b-instruct"),    # free tier
    (7,  "pain_point_miner",    "openai/gpt-4o-mini"),
    (8,  "pain_point_miner",    "anthropic/claude-3-haiku"),
    (9,  "hypothesis_generator","openai/gpt-4o-mini"),
    (10, "hypothesis_generator","anthropic/claude-3-haiku"),
]


# ── Per-operation runners ─────────────────────────────────────────────────────

async def run_drafter(model_id: str) -> tuple[MarketingContext, int, int]:
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
    result = await agent.run(prompt)
    u = result.usage()
    return result.output, u.input_tokens or 0, u.output_tokens or 0


async def run_semantic(model_id: str) -> tuple[PageElements, int, int]:
    agent: Agent[None, PageElements] = Agent(
        model=make_model(model_id),
        output_type=PageElements,
        system_prompt="You are a CRO analyst extracting semantic elements from landing pages. Be precise and factual.",
        model_settings={"temperature": 0.1},
        retries=1,
    )
    result = await agent.run(SEMANTIC_PROMPT)
    u = result.usage()
    return result.output, u.input_tokens or 0, u.output_tokens or 0


async def run_pain_points(model_id: str) -> tuple[PainPointList, int, int]:
    agent: Agent[None, PainPointList] = Agent(
        model=make_model(model_id),
        output_type=PainPointList,
        system_prompt="You are a direct-response copywriter identifying concrete pain points in landing page copy.",
        model_settings={"temperature": 0.2},
        retries=1,
    )
    result = await agent.run(PAIN_POINT_PROMPT)
    u = result.usage()
    return result.output, u.input_tokens or 0, u.output_tokens or 0


async def run_hypothesis(model_id: str) -> tuple[ABHypothesis, int, int]:
    agent: Agent[None, ABHypothesis] = Agent(
        model=make_model(model_id),
        output_type=ABHypothesis,
        system_prompt="You are a senior CRO strategist generating data-driven A/B test hypotheses.",
        model_settings={"temperature": 0.3},
        retries=1,
    )
    result = await agent.run(HYPOTHESIS_PROMPT)
    u = result.usage()
    return result.output, u.input_tokens or 0, u.output_tokens or 0


# ── Single test executor ──────────────────────────────────────────────────────

async def run_one(test_id: int, operation: str, model_id: str) -> TestResult:
    print(f"  [{test_id:02d}] {operation:<22} {model_id:<35} ", end="", flush=True)
    t0 = time.monotonic()

    try:
        if operation == "drafter":
            output, inp, out = await run_drafter(model_id)
            score, notes = score_drafter(output)
            preview = f"{len(output.personas)} personas | {output.personas[0].name if output.personas else '?'}"

        elif operation == "semantic_extractor":
            output, inp, out = await run_semantic(model_id)
            score, notes = score_semantic(output)
            preview = f"cta='{output.primary_cta[:30]}' | conf={output.confidence:.2f}"

        elif operation == "pain_point_miner":
            output, inp, out = await run_pain_points(model_id)
            score, notes = score_pain_points(output)
            preview = f"{len(output.pain_points)} pain points | urgency={output.urgency_level}"

        elif operation == "hypothesis_generator":
            output, inp, out = await run_hypothesis(model_id)
            score, notes = score_hypothesis(output)
            preview = f"element='{output.element}' | risk={output.risk_level}"

        else:
            raise ValueError(f"Unknown operation: {operation}")

        latency = int((time.monotonic() - t0) * 1000)
        cost = estimate_cost(model_id, inp, out)
        print(f"✓ {latency/1000:.1f}s  score={score}/10  ${cost:.4f}")

        return TestResult(
            test_id=test_id, operation=operation, model_id=model_id,
            success=True, latency_ms=latency, retries=0,
            input_tokens=inp, output_tokens=out,
            cost_usd=cost, quality_score=score,
            quality_notes=notes, output_preview=preview,
        )

    except Exception as exc:
        latency = int((time.monotonic() - t0) * 1000)
        err = str(exc)[:120]
        print(f"✗ {err}")
        return TestResult(
            test_id=test_id, operation=operation, model_id=model_id,
            success=False, latency_ms=latency, retries=0,
            input_tokens=0, output_tokens=0,
            cost_usd=0.0, quality_score=0.0,
            quality_notes=[f"ERROR: {err}"], output_preview="",
            error=err,
        )


# ── Report generator ──────────────────────────────────────────────────────────

def print_summary(results: list[TestResult]) -> None:
    print("\n" + "═" * 90)
    print(f"{'#':>3}  {'Operation':<22} {'Model':<35} {'Score':>6} {'Cost':>8} {'Latency':>9}  {'Preview'}")
    print("─" * 90)

    total_cost = 0.0
    for r in results:
        status = "✓" if r.success else "✗"
        cost_str = f"${r.cost_usd:.4f}"
        lat_str = f"{r.latency_ms/1000:.1f}s"
        score_str = f"{r.quality_score:.1f}/10" if r.success else "fail"
        preview = r.output_preview[:35] if r.output_preview else (r.error or "")[:35]
        print(f"{status}{r.test_id:>3}  {r.operation:<22} {r.model_id:<35} {score_str:>6} {cost_str:>8} {lat_str:>9}  {preview}")
        total_cost += r.cost_usd

    print("─" * 90)
    print(f"{'Total cost:':>72} ${total_cost:.4f}")
    print("═" * 90)


def save_markdown_report(results: list[TestResult]) -> None:
    from datetime import date
    today = date.today().isoformat()
    lines = [
        f"# Benchmark Report — Sprint 5.5",
        f"",
        f"**Date:** {today}  ",
        f"**Input:** walk-in shower / homeiq.io (Florida, Meta, ZIP submit)",
        f"",
        f"## Results",
        f"",
        f"| # | Operation | Model | Score | Cost | Latency | Notes |",
        f"|---|---|---|---|---|---|---|",
    ]

    total_cost = 0.0
    for r in results:
        status = "✓" if r.success else "✗"
        score_str = f"{r.quality_score:.1f}/10" if r.success else "FAIL"
        cost_str = f"${r.cost_usd:.4f}"
        lat_str = f"{r.latency_ms/1000:.1f}s"
        first_note = r.quality_notes[0] if r.quality_notes else ""
        lines.append(
            f"| {status}{r.test_id} | {r.operation} | `{r.model_id}` | {score_str} | {cost_str} | {lat_str} | {first_note} |"
        )
        total_cost += r.cost_usd

    lines += ["", f"**Total benchmark cost: ${total_cost:.4f}**", ""]

    # Per-operation best model
    lines += ["## Recommended Model Per Operation", ""]
    by_op: dict[str, list[TestResult]] = {}
    for r in results:
        by_op.setdefault(r.operation, []).append(r)

    routing: dict[str, str] = {}
    for op, op_results in by_op.items():
        successful = [r for r in op_results if r.success]
        if successful:
            best = max(successful, key=lambda r: (r.quality_score, -r.cost_usd))
            routing[op] = best.model_id
            lines.append(f"- **{op}**: `{best.model_id}` (score={best.quality_score:.1f}, cost=${best.cost_usd:.4f})")
        else:
            routing[op] = "openai/gpt-4o-mini"  # fallback
            lines.append(f"- **{op}**: fallback to `openai/gpt-4o-mini` (all failed)")

    lines += ["", "## Quality Detail", ""]
    for r in results:
        lines.append(f"### Test {r.test_id}: {r.operation} / `{r.model_id}`")
        lines.append(f"- **Output:** {r.output_preview}")
        for note in r.quality_notes:
            lines.append(f"  - {note}")
        lines.append("")

    report_path = ROOT / "docs" / f"benchmark_{today}.md"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n📄 Report saved: {report_path}")

    return routing


def save_routing_config(routing: dict[str, str]) -> None:
    import yaml  # type: ignore[import]
    config = {
        "# Auto-generated by scripts/run_benchmark.py — Sprint 5.5": None,
        "# Edit manually after review": None,
        "routing": {
            "drafter":             routing.get("drafter",             "openai/gpt-4o-mini"),
            "judge":               routing.get("judge",               "openai/gpt-4o-mini"),
            "semantic_extractor":  routing.get("semantic_extractor",  "openai/gpt-4o-mini"),
            "pain_point_miner":    routing.get("pain_point_miner",    "openai/gpt-4o-mini"),
            "hypothesis_generator":routing.get("hypothesis_generator","openai/gpt-4o-mini"),
            "knowledge_reranker":  "openai/gpt-4o-mini",   # not benchmarked (deterministic)
            "agent_findings":      "openai/gpt-4o-mini",   # N5 — TBD
            "decision_engine":     "openai/gpt-4o-mini",   # N6 — TBD
        },
        "fallback_model": "openai/gpt-4o-mini",
        "temperature_defaults": {
            "drafter":             0.3,
            "judge":               0.0,
            "semantic_extractor":  0.1,
            "pain_point_miner":    0.2,
            "hypothesis_generator":0.3,
        },
    }
    # Remove None-keyed comments (yaml trick — just write as comments)
    config_path = ROOT / "configs" / "llm_routing.yml"
    with open(config_path, "w", encoding="utf-8") as f:
        f.write("# Auto-generated by scripts/run_benchmark.py — Sprint 5.5\n")
        f.write("# Edit manually after review\n\n")
        yaml.dump(
            {k: v for k, v in config.items() if k != "# Auto-generated by scripts/run_benchmark.py — Sprint 5.5" and k != "# Edit manually after review"},
            f,
            default_flow_style=False,
            allow_unicode=True,
        )
    print(f"⚙️  Routing config saved: {config_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    print("\n" + "═" * 90)
    print("  Sprint 5.5 — Model Benchmark Gate")
    print(f"  {len(TEST_CASES)} tests | Operations: drafter, semantic_extractor, pain_point_miner, hypothesis_generator")
    print(f"  Models: gpt-4o-mini, claude-3-haiku, gemini-flash-1.5")
    print("═" * 90 + "\n")

    results: list[TestResult] = []
    for test_id, operation, model_id in TEST_CASES:
        result = await run_one(test_id, operation, model_id)
        results.append(result)

    print_summary(results)
    routing = save_markdown_report(results)
    save_routing_config(routing)


if __name__ == "__main__":
    asyncio.run(main())
