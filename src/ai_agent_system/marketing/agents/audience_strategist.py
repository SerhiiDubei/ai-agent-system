"""Audience Strategist — Wave 2 agent.

Depends on Customer Insights (personas) and Media Planner (channel context).

Responsibility: translate personas into actionable targeting recipes.
Lookalike seeds, exclusion signals, audience_profile with primary_persona_name.

Input: Brief + CustomerInsightsOutput + MediaPlanOutput
Output: AudienceSegmentationOutput
"""

from __future__ import annotations

import logging

from ai_agent_system.marketing.agents._base import (
    load_character_card,
    run_with_fallback,
)
from ai_agent_system.marketing.brief import MarketingBrief
from ai_agent_system.marketing.sub_schemas import (
    AudienceSegmentationOutput,
    CustomerInsightsOutput,
    MediaPlanOutput,
)
from ai_agent_system.observability.agent_logger import RunLogger
from ai_agent_system.observability.config_loader import AgentsConfig

log = logging.getLogger(__name__)

AGENT_NAME = "audience_strategist"


def _build_user_prompt(
    brief: MarketingBrief,
    insights: CustomerInsightsOutput,
    media: MediaPlanOutput,
) -> str:
    persona_names = [p.name for p in insights.personas]
    persona_list = "\n".join(f"  - {n}" for n in persona_names)

    sac_note = ""
    if hasattr(media.channel_profile, "age_targeting_note"):
        ant = getattr(media.channel_profile, "age_targeting_note", None)
        if ant:
            sac_note = f"\n⚠ Special Ad Category constraint: {ant}\n"

    return (
        f"BRIEF:\n{brief.brief}\n\n"
        f"METADATA:\n"
        f"- market: {brief.market}\n"
        f"- language: {brief.language}\n"
        f"- traffic_source_primary: {brief.traffic_source_primary}\n"
        f"- page_goal: {brief.page_goal}\n\n"
        f"PERSONAS (from Customer Insights — use these EXACT names for primary_persona_name):\n"
        f"{persona_list}\n\n"
        f"CHANNEL CONTEXT (from Media Planner):\n"
        f"  channel = {media.channel_profile.channel}\n"
        f"  temperature = {media.channel_temperature}\n"
        f"{sac_note}\n"
        f"Generate the AudienceSegmentationOutput JSON now. "
        f"audience_profile.primary_persona_name MUST be character-for-character "
        f"identical to one of the persona names listed above. "
        f"lookalike_seeds must be CONCRETE behavioural signals, not 'people interested in X'."
    )


async def run_audience_strategist(
    brief: MarketingBrief,
    insights: CustomerInsightsOutput,
    media: MediaPlanOutput,
    *,
    run_logger: RunLogger,
    cfg: AgentsConfig,
) -> AudienceSegmentationOutput:
    agent_cfg = cfg.get_agent(AGENT_NAME)
    prompt_version = cfg.prompt_versions.get(AGENT_NAME, "v1")
    system_prompt = load_character_card(AGENT_NAME, prompt_version)
    user_prompt = _build_user_prompt(brief, insights, media)

    inv = run_logger.start_agent(
        AGENT_NAME,
        input_full={
            "brief": brief.model_dump(),
            "personas": [p.name for p in insights.personas],
            "channel": media.channel_profile.channel,
        },
        config_used=agent_cfg.model_dump(),
    )
    try:
        output = await run_with_fallback(
            agent_name=AGENT_NAME,
            config=agent_cfg,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_type=AudienceSegmentationOutput,
            invocation_logger=inv,
        )
        inv.complete(
            succeeded=True,
            output_full=output.model_dump(),
            output_summary=(
                f"primary={output.audience_profile.primary_persona_name!r}, "
                f"{len(output.lookalike_seeds)} seeds, "
                f"{len(output.exclusion_signals)} exclusions"
            ),
        )
        return output
    except Exception as e:
        inv.complete(succeeded=False, final_error=f"{type(e).__name__}: {e}")
        raise
