"""Media Planner — Wave 1 agent.

Responsibility: define the channel context the LP lives inside.
Channel-specific mechanics, channel temperature, creative grammar.

Input: Brief
Output: MediaPlanOutput (channel_profile + temperature + creative_grammar)
"""

from __future__ import annotations

import logging

from ai_agent_system.marketing.agents._base import (
    load_character_card,
    run_with_fallback,
)
from ai_agent_system.marketing.brief import MarketingBrief
from ai_agent_system.marketing.sub_schemas import MediaPlanOutput
from ai_agent_system.observability.agent_logger import RunLogger
from ai_agent_system.observability.config_loader import AgentsConfig

log = logging.getLogger(__name__)

AGENT_NAME = "media_planner"


def _build_user_prompt(brief: MarketingBrief) -> str:
    return (
        f"BRIEF:\n{brief.brief}\n\n"
        f"METADATA:\n"
        f"- traffic_source_primary: {brief.traffic_source_primary}\n"
        f"- page_goal: {brief.page_goal}\n"
        f"- niche: {brief.niche}\n"
        f"- parent_category: {brief.parent_category}\n"
        f"- market: {brief.market}\n"
        + (f"- business_constraints: {brief.business_constraints}\n"
           if brief.business_constraints else "")
        + f"\n"
        f"CRITICAL: channel_profile.channel MUST equal '{brief.traffic_source_primary}'.\n"
        f"Generate the MediaPlanOutput JSON now."
    )


async def run_media_planner(
    brief: MarketingBrief,
    *,
    run_logger: RunLogger,
    cfg: AgentsConfig,
) -> MediaPlanOutput:
    agent_cfg = cfg.get_agent(AGENT_NAME)
    prompt_version = cfg.prompt_versions.get(AGENT_NAME, "v1")
    system_prompt = load_character_card(AGENT_NAME, prompt_version)
    user_prompt = _build_user_prompt(brief)

    inv = run_logger.start_agent(
        AGENT_NAME,
        input_full={"brief": brief.model_dump()},
        config_used=agent_cfg.model_dump(),
    )
    try:
        output = await run_with_fallback(
            agent_name=AGENT_NAME,
            config=agent_cfg,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_type=MediaPlanOutput,
            invocation_logger=inv,
        )
        inv.complete(
            succeeded=True,
            output_full=output.model_dump(),
            output_summary=(
                f"channel={output.channel_profile.channel} "
                f"temp={output.channel_temperature}"
            ),
        )
        return output
    except Exception as e:
        inv.complete(succeeded=False, final_error=f"{type(e).__name__}: {e}")
        raise
