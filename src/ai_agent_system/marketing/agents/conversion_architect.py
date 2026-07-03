"""Conversion Architect (CRO Lead) — Wave 1 agent.

Responsibility: design user_flow stages, identify friction inventory,
generate ICE-scored A/B test priorities.

Input: Brief
Output: ConversionArchitectureOutput (user_flow + test_priorities + friction_inventory)
"""

from __future__ import annotations

import logging

from ai_agent_system.marketing.agents._base import (
    load_character_card,
    run_with_fallback,
)
from ai_agent_system.marketing.brief import MarketingBrief
from ai_agent_system.marketing.page_context import (
    PageContext,
    render_page_context_for_prompt,
)
from ai_agent_system.marketing.sub_schemas import ConversionArchitectureOutput
from ai_agent_system.observability.agent_logger import RunLogger
from ai_agent_system.observability.config_loader import AgentsConfig

log = logging.getLogger(__name__)

AGENT_NAME = "conversion_architect"


def _build_user_prompt(
    brief: MarketingBrief,
    page_context: PageContext | None,
) -> str:
    page_block = ""
    if page_context:
        page_block = (
            f"\n\nPAGE CAPTURED — use this to ground your analysis in REAL friction, "
            f"not predicted friction. Your test_priorities should reference specific "
            f"elements you can see in the page below.\n\n"
            f"{render_page_context_for_prompt(page_context)}\n"
        )

    return (
        f"BRIEF:\n{brief.brief}\n\n"
        f"METADATA:\n"
        f"- niche: {brief.niche}\n"
        f"- parent_category: {brief.parent_category}\n"
        f"- traffic_source_primary: {brief.traffic_source_primary}\n"
        f"- page_goal: {brief.page_goal}\n"
        f"- primary_metric: {brief.primary_metric}\n"
        + (f"- business_constraints: {brief.business_constraints}\n"
           if brief.business_constraints else "")
        + page_block
        + f"\n"
        f"Generate the ConversionArchitectureOutput JSON now. "
        f"Walk through LIFT diagnostically. Score every test_priority via ICE. "
        f"At least one test should have ICE total ≥ 18."
        + (
            "\n\nWith page captured: ground every friction_inventory entry to a specific "
            "element you saw above. Vague friction without page evidence is forbidden."
            if page_context else ""
        )
    )


async def run_conversion_architect(
    brief: MarketingBrief,
    *,
    run_logger: RunLogger,
    cfg: AgentsConfig,
    page_context: PageContext | None = None,
) -> ConversionArchitectureOutput:
    agent_cfg = cfg.get_agent(AGENT_NAME)
    prompt_version = cfg.prompt_versions.get(AGENT_NAME, "v1")
    system_prompt = load_character_card(AGENT_NAME, prompt_version)
    user_prompt = _build_user_prompt(brief, page_context)

    inv = run_logger.start_agent(
        AGENT_NAME,
        input_full={
            "brief": brief.model_dump(),
            "page_context": (
                page_context.short_summary() if page_context else "none"
            ),
        },
        config_used=agent_cfg.model_dump(),
    )
    try:
        output = await run_with_fallback(
            agent_name=AGENT_NAME,
            config=agent_cfg,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_type=ConversionArchitectureOutput,
            invocation_logger=inv,
        )
        inv.complete(
            succeeded=True,
            output_full=output.model_dump(),
            output_summary=(
                f"{len(output.user_flow.stages)} stages, "
                f"{len(output.test_priorities)} tests, "
                f"top ICE={max((t.ice_total for t in output.test_priorities), default=0)}"
            ),
        )
        return output
    except Exception as e:
        inv.complete(succeeded=False, final_error=f"{type(e).__name__}: {e}")
        raise
