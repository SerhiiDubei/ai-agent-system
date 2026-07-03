"""LLM-as-judge for Marketing Context — N4.

Runs a cheap second model over the drafted MarketingContext and checks
for generic personas, platitude pain points, channel mismatches, and
missing dual-persona for senior demographics.
"""

from __future__ import annotations

import logging

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from ai_agent_system.config import settings
from ai_agent_system.marketing.models import MarketingContext, SanityVerdict

log = logging.getLogger(__name__)

_JUDGE_SYSTEM = """\
You are a critical reviewer of AI-drafted Marketing Contexts for paid-traffic
lead-gen landing pages. Your job is to flag issues BEFORE the draft reaches
a human marketer for approval.

Check the MarketingContext against ALL criteria below.

A. PERSONA QUALITY
   - Names must be memorable and niche-specific (NOT "John, 35, marketing manager").
   - 3-5 personas must be present.
   - For 55+ niches (walk-in tub, stairlift, hearing aid, senior living, Medicare):
     BOTH a senior primary_buyer AND a decision_helper (adult child / spouse) are
     required. Missing the helper is a critical failure.
   - Age ranges must fit the niche.

B. LOGICAL CONSISTENCY
   - Does each persona's age fit their pain_points?
     (A 30-year-old should not fear "falling in tub due to age".)
   - Does income_band fit location_context?
     (Florida retiree on Social Security is unlikely to be over_200k.)
   - Does digital_literacy fit age + income?
     (65+, low income, rural → almost always "low".)

C. PAIN POINT QUALITY
   - All pain_points must be concrete with observable triggers.
   - Platitudes like "wants better life", "save money", "be happy" are CRITICAL failures.
   - Each pain must plausibly relate to the stated offer.

D. CHANNEL FIT
   - channel_profile.channel must match traffic_source_primary exactly.
   - Trust needs must be channel-appropriate:
     Meta + 65+ = high credibility burden (BBB, local installer photo, no pressure sales).
     Google Search = match query intent, show pricing or proof above fold.
   - Decision triggers must be realistic for the channel context.

E. JTBD
   - Each primary_job must follow JTBD format: "When ___, I want to ___, so I can ___."
   - Vague statements like "wants to improve bathroom" fail this check.

F. SCHEMA COMPLETENESS
   - audience_profile.primary_persona_name must exactly match a persona name.
   - No required fields contain placeholder values ("TBD", "TODO", etc.).

Set passed=false if ANY critical issue is found (A, C, D, E are critical;
B and F are critical only when egregious). Return specific issues and fixes.
"""


_judge: Agent[None, SanityVerdict] | None = None


def _get_judge() -> Agent[None, SanityVerdict]:
    global _judge
    if _judge is None:
        _judge = Agent(
            model=OpenAIModel(
                model_name="openai/gpt-4o-mini",
                provider=OpenAIProvider(
                    base_url=settings.openrouter_base_url,
                    api_key=settings.openrouter_api_key.get_secret_value(),
                ),
            ),
            output_type=SanityVerdict,
            system_prompt=_JUDGE_SYSTEM,
            model_settings={"temperature": 0.0},
            retries=1,
        )
    return _judge


async def judge_context(ctx: MarketingContext) -> SanityVerdict:
    user_msg = (
        f"MarketingContext to review (niche={ctx.niche}, "
        f"traffic={ctx.traffic_source_primary}):\n\n"
        f"{ctx.model_dump_json(indent=2)}"
    )
    result = await _get_judge().run(user_msg)
    verdict = result.output
    log.info(
        "marketing:judge niche=%s passed=%s issues=%d",
        ctx.niche, verdict.passed, len(verdict.issues),
    )
    return verdict
