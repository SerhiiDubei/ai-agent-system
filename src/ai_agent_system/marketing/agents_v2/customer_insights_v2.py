"""Customer Insights agent v2 — built as a SYSTEM, not a single prompt.

Differences from v1:
  - Loads agent's identity, beliefs, workflow from agents/customer_insights/*.md
  - Selects market_segment + frameworks + golden_sets dynamically per brief
  - Domain-agnostic core; niche-specific knowledge attached at runtime
  - Same output schema (CustomerInsightsOutput) — backward compatible
  - Uses run_with_fallback_direct (the long assembled prompt is best handled
    by direct API + json_object mode; pydantic-ai tool calling can choke on
    very large system prompts)
"""

from __future__ import annotations

import logging

from ai_agent_system.marketing.agents._base import run_with_fallback_direct
from ai_agent_system.marketing.agents_v2.system_loader import load_agent_system
from ai_agent_system.marketing.brief import MarketingBrief
from ai_agent_system.marketing.sub_schemas import CustomerInsightsOutput
from ai_agent_system.observability.agent_logger import RunLogger
from ai_agent_system.observability.config_loader import AgentsConfig

log = logging.getLogger(__name__)

AGENT_NAME = "customer_insights_v2"


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
        f"Apply the 6-step workflow from your AGENT system above. "
        f"Walk through each step mentally before producing the JSON. "
        f"Output the CustomerInsightsOutput JSON as specified in your "
        f"`persona_filling_guide.md`. Pass all cardinal-error checks before shipping."
    )


async def run_customer_insights_v2(
    brief: MarketingBrief,
    retrieved_chunks: list[str],
    *,
    run_logger: RunLogger,
    cfg: AgentsConfig,
) -> CustomerInsightsOutput:
    """Run the v2 Customer Insights agent — system-based, domain-agnostic.

    The agent's behavior adapts based on brief signals:
      - niche="walk_in_tubs" → loads senior_care segment + caregiver_burden + ...
      - niche="saas_workflow" → loads b2b_saas segment + moesta_forces + ...
      - etc.
    """
    # Reuse 'customer_insights' config from agents.yml — same schema, same model
    agent_cfg = cfg.get_agent("customer_insights")

    # Assemble the system prompt by loading + composing the agent's files
    system = load_agent_system(
        agent_name="customer_insights",          # folder name in agents/
        niche=brief.niche,
        brief_text=brief.brief,
    )

    log.info(
        "agent_v2 routing: agent=%s matched_via=%s token=%s segment=%s frameworks=%d goldens=%d",
        AGENT_NAME, system.routing.matched_via, system.routing.matched_token,
        system.routing.segment, len(set(system.routing.frameworks)),
        len(system.routing.golden_sets),
    )

    user_prompt = _build_user_prompt(brief, retrieved_chunks)

    inv = run_logger.start_agent(
        AGENT_NAME,
        input_full={
            "brief": brief.model_dump(),
            "retrieved_chunks_count": len(retrieved_chunks),
            "system_prompt_length_chars": len(system.system_prompt),
            "files_loaded": system.files_loaded,
            "routing": {
                "matched_via": system.routing.matched_via,
                "matched_token": system.routing.matched_token,
                "segment": system.routing.segment,
                "frameworks": list(set(system.routing.frameworks)),
                "golden_sets": system.routing.golden_sets,
            },
        },
        config_used=agent_cfg.model_dump(),
    )
    try:
        output = await run_with_fallback_direct(
            agent_name=AGENT_NAME,
            config=agent_cfg,
            system_prompt=system.system_prompt,
            user_prompt=user_prompt,
            output_type=CustomerInsightsOutput,
            invocation_logger=inv,
        )
        inv.complete(
            succeeded=True,
            output_full=output.model_dump(),
            output_summary=(
                f"{len(output.personas)} personas, "
                f"{len(output.pain_points_aggregate)} aggregate pains "
                f"(routing: {system.routing.matched_via}/{system.routing.segment})"
            ),
        )
        return output
    except Exception as e:
        inv.complete(succeeded=False, final_error=f"{type(e).__name__}: {e}")
        raise
