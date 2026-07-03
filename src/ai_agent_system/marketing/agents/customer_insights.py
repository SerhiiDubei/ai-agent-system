"""Customer Insights Strategist — Wave 1 agent.

Responsibility: turn brief + metadata into 3-5 sharp niche-specific personas
with JTBD, pain triggers, decision-helper for 55+ niches, and an audience
psychology summary that downstream agents consume.

Input: Brief (the marketing brief + metadata)
Output: CustomerInsightsOutput (personas + pain_points_aggregate + psychology_summary)
"""

from __future__ import annotations

import logging

from ai_agent_system.marketing.agents._base import (
    load_character_card,
    run_with_fallback,
)
from ai_agent_system.marketing.brief import MarketingBrief
from ai_agent_system.marketing.sub_schemas import CustomerInsightsOutput
from ai_agent_system.observability.agent_logger import RunLogger
from ai_agent_system.observability.config_loader import AgentsConfig

log = logging.getLogger(__name__)

AGENT_NAME = "customer_insights"


def _build_user_prompt(brief: MarketingBrief, retrieved_chunks: list[str]) -> str:
    chunks_block = (
        "\n\n---\n\n".join(retrieved_chunks)
        if retrieved_chunks
        else "(No prior knowledge found for this niche. Produce a conservative draft.)"
    )
    return (
        f"BRIEF:\n{brief.brief}\n\n"
        f"METADATA:\n"
        f"- niche: {brief.niche}\n"
        f"- parent_category: {brief.parent_category}\n"
        f"- market: {brief.market}\n"
        f"- language: {brief.language}\n"
        f"- traffic_source_primary: {brief.traffic_source_primary}\n"
        f"- page_goal: {brief.page_goal}\n"
        f"- primary_metric: {brief.primary_metric}\n"
        + (f"- business_constraints: {brief.business_constraints}\n"
           if brief.business_constraints else "")
        + f"\n<retrieved_context>\n{chunks_block}\n</retrieved_context>\n\n"
        f"Generate the CustomerInsightsOutput JSON now. "
        f"Remember: niche-specific persona names, JTBD format, decision_helper for 55+ niches, "
        f"income bands assigned honestly, no platitudes in pain descriptions."
    )


async def run_customer_insights(
    brief: MarketingBrief,
    retrieved_chunks: list[str],
    *,
    run_logger: RunLogger,
    cfg: AgentsConfig,
) -> CustomerInsightsOutput:
    """Run the Customer Insights Strategist agent."""
    agent_cfg = cfg.get_agent(AGENT_NAME)
    prompt_version = cfg.prompt_versions.get(AGENT_NAME, "v1")
    system_prompt = load_character_card(AGENT_NAME, prompt_version)
    user_prompt = _build_user_prompt(brief, retrieved_chunks)

    inv = run_logger.start_agent(
        AGENT_NAME,
        input_full={
            "brief": brief.model_dump(),
            "retrieved_chunks_count": len(retrieved_chunks),
        },
        config_used=agent_cfg.model_dump(),
    )
    try:
        output = await run_with_fallback(
            agent_name=AGENT_NAME,
            config=agent_cfg,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_type=CustomerInsightsOutput,
            invocation_logger=inv,
        )
        inv.complete(
            succeeded=True,
            output_full=output.model_dump(),
            output_summary=(
                f"{len(output.personas)} personas, "
                f"{len(output.pain_points_aggregate)} aggregate pains"
            ),
        )
        return output
    except Exception as e:
        inv.complete(succeeded=False, final_error=f"{type(e).__name__}: {e}")
        raise
