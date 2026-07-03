"""Pydantic AI drafter agent — N4.

Takes a brief + metadata, injects retrieved knowledge chunks,
returns a validated MarketingContext.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from ai_agent_system.config import settings
from ai_agent_system.marketing.models import MarketingContext

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a senior performance-marketing strategist drafting a MarketingContext
for a paid-traffic landing-page A/B test program.

Your output must conform exactly to the MarketingContext Pydantic schema.

HARD RULES — violations cause automatic retry:

1. Generate 3-5 DISTINCT personas. Each name must be a memorable niche-specific
   label tied to a concrete life situation, e.g.:
   - "Florida Helen, 72, fall-risk widow"
   - "Adult-child Marcus, 47, helping mom from out of state"
   NEVER produce generic names like "John, 35, marketing manager".

2. For senior demographics (55+) ALWAYS include BOTH:
   - The senior themselves (primary_buyer)
   - A "decision_helper" persona — adult child, spouse, or caregiver
   Skipping the helper is a cardinal error for home-services, medical, insurance niches.

3. Pain points must be CONCRETE and OBSERVABLE with a trigger. NO platitudes.
   WRONG: "Concerned about safety"
   RIGHT: "Slipped getting out of the tub last winter; afraid it will happen again
          without anyone home"

4. Each persona's primary_job MUST be a JTBD statement:
   "When ___, I want to ___, so I can ___."

5. Channel profile rules:
   - meta: push interrupt. User was scrolling, not looking for you. Hook in 2 sec.
     Note Special Ad Categories (housing, credit, employment) that block age/zip in US.
   - google_search: pull intent. Match the query immediately above the fold.
   - tiktok: entertainment scroll. Hook in <3 sec. No corporate polish.
   - snapchat: under-25 skew, ephemeral feel.

6. Trust needs must be channel-appropriate:
   - meta + 65+ needs explicit credibility signals (BBB, local installer photo,
     "no high-pressure sales") — the user did NOT seek you out.
   - google_search: match query intent, show clear pricing or social proof.

7. Use retrieved knowledge chunks (in <retrieved_context>) as anchors.
   If chunks mention specific patterns (e.g. "walk-in tub buyers want visible
   pricing"), reflect them in trust_needs or decision_triggers.

8. Income band: be honest. Walk-in tub / Medicare / debt-relief buyers are often
   fixed-income (under_30k or 30_60k). Do NOT default everyone to 60_100k.

9. audience_profile.primary_persona_name MUST exactly match one persona name.

10. channel_profile.channel MUST equal traffic_source_primary.

If you cannot fully satisfy a constraint from the brief alone, produce your best
draft and explain assumptions in the source_brief field.
"""

_BRIEF_PROMPT = """\
Project brief:
\"\"\"
{brief}
\"\"\"

Project metadata:
- niche: {niche}
- parent_category: {parent_category}
- market: {market}
- language: {language}
- traffic_source_primary: {traffic_source_primary}
- page_goal: {page_goal}
- primary_metric: {primary_metric}
{constraints_line}

Reasoning checklist (think step by step before producing the final object):
1. Parse the brief: who, where, what offer, what action.
2. Identify primary buyer(s). For 55+ verticals: also identify the adult-child helper.
3. Assign income_band realistically — do not default to middle class.
4. For each persona: draft JTBD first, then derive pain_points / trust_needs /
   decision_triggers / objections from the JTBD.
5. Select user_flow stages appropriate to commitment level
   (zip_submit = short; book_demo = longer).
6. Fill channel_profile matching traffic_source_primary with real mechanics,
   not generic marketing language.
7. Final consistency check:
   - audience_profile.primary_persona_name is in personas (exact match)
   - channel_profile.channel == traffic_source_primary
   - 3-5 personas total
   - all pain_points are concrete with triggers (no platitudes)

Produce the complete MarketingContext object.
"""


@dataclass
class DrafterDeps:
    niche: str
    parent_category: str
    market: str
    language: str
    traffic_source_primary: str
    page_goal: str
    primary_metric: str
    brief: str
    business_constraints: str | None
    retrieved_chunks: list[str]


def _provider() -> OpenAIProvider:
    return OpenAIProvider(
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key.get_secret_value(),
    )


_drafter: Agent[DrafterDeps, MarketingContext] | None = None


def _get_drafter() -> Agent[DrafterDeps, MarketingContext]:
    global _drafter
    if _drafter is None:
        _drafter = Agent(
            model=OpenAIModel(
                model_name="openai/gpt-4o-mini",
                provider=_provider(),
            ),
            deps_type=DrafterDeps,
            output_type=MarketingContext,
            system_prompt=SYSTEM_PROMPT,
            model_settings={"temperature": 0.3},
            retries=2,
        )

        @_drafter.system_prompt
        async def _inject_grounding(ctx: RunContext[DrafterDeps]) -> str:
            if not ctx.deps.retrieved_chunks:
                return (
                    "<retrieved_context>\n"
                    "No prior knowledge found for this niche. "
                    "Produce a conservative draft and flag assumptions.\n"
                    "</retrieved_context>"
                )
            body = "\n\n---\n\n".join(ctx.deps.retrieved_chunks)
            return f"<retrieved_context>\n{body}\n</retrieved_context>"

    return _drafter


async def draft_marketing_context(deps: DrafterDeps) -> MarketingContext:
    constraints_line = (
        f"- business_constraints: {deps.business_constraints}"
        if deps.business_constraints
        else ""
    )
    user_prompt = _BRIEF_PROMPT.format(
        brief=deps.brief,
        niche=deps.niche,
        parent_category=deps.parent_category,
        market=deps.market,
        language=deps.language,
        traffic_source_primary=deps.traffic_source_primary,
        page_goal=deps.page_goal,
        primary_metric=deps.primary_metric,
        constraints_line=constraints_line,
    )

    log.info(
        "marketing:draft niche=%s traffic=%s goal=%s",
        deps.niche, deps.traffic_source_primary, deps.page_goal,
    )
    result = await _get_drafter().run(user_prompt, deps=deps)
    ctx = result.output
    ctx.source_brief = deps.brief
    ctx.grounding_chunks_used = deps.retrieved_chunks[:5]
    return ctx
