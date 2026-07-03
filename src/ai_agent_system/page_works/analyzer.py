"""Page-Works Analyzer agent runtime (Phase 5f).

The FIRST expert in the pipeline. Runs BEFORE Customer Insights and other
"improvement" agents — its job is to identify what's already working on the
existing LP so downstream experts can preserve it.

Architecture mirrors Customer Insights v2:
  - Loads agent system from agents/page_works_analyzer/
  - Selects working_page_pattern + frameworks based on niche
  - Loads 1-2 golden_set examples
  - Runs single LLM call (direct API + json_object mode)
  - Logs everything via observability
"""

from __future__ import annotations

import logging
from typing import Any

from ai_agent_system.marketing.agents._base import run_with_fallback_direct
from ai_agent_system.marketing.agents_v2.system_loader import load_agent_system
from ai_agent_system.marketing.brief import MarketingBrief
from ai_agent_system.marketing.page_context import (
    PageContext,
    render_page_context_for_prompt,
)
from ai_agent_system.marketing.performance_renderer import (
    render_budget_block,
    render_performance_block,
)
from ai_agent_system.observability.agent_logger import RunLogger
from ai_agent_system.observability.config_loader import AgentsConfig
from ai_agent_system.page_works.schemas import PageWorksAnalysis

log = logging.getLogger(__name__)

AGENT_NAME = "page_works_analyzer"


def _build_user_prompt(
    brief: MarketingBrief,
    page_context: PageContext | None,
) -> str:
    constraints = brief.operating_constraints
    constraints_block = ""
    if constraints:
        prior_tests = ""
        if constraints.prior_tests_tried:
            prior_tests = "\nPrior tests tried (do not propose anything that repeats these):\n"
            prior_tests += "\n".join(f"  - {t}" for t in constraints.prior_tests_tried)

        constraints_block = (
            "\n\nOPERATING CONSTRAINTS:\n"
            f"  monthly_traffic_volume: {constraints.monthly_traffic_volume or '(not provided)'}\n"
            f"  baseline_conversion_rate_pct: {constraints.baseline_conversion_rate_pct or '(not provided)'}\n"
            f"  time_window_days: {constraints.time_window_days or '(not provided)'}\n"
            f"  expected_lift_floor_pct: {constraints.expected_lift_floor_pct or '(not provided)'}\n"
            f"  risk_appetite: {constraints.risk_appetite}\n"
            + (prior_tests if prior_tests else "")
        )

    page_block = ""
    if page_context:
        page_block = (
            "\n\nPAGE CAPTURED — analyze this:\n\n"
            f"{render_page_context_for_prompt(page_context)}\n"
        )
    else:
        page_block = (
            "\n\n⚠ NO PAGE CAPTURED. You can only do structural assessment based on niche "
            "patterns. Lower your confidence accordingly. Note this in warnings_for_downstream.\n"
        )

    # Phase 5d.1 — render real performance metrics + budget if operator provided
    budget_block = render_budget_block(brief.operating_constraints)
    performance_block = render_performance_block(brief.current_performance)

    has_real_data = bool(performance_block or budget_block)
    real_data_reminder = ""
    if has_real_data:
        real_data_reminder = (
            "\n  ⭐ REAL ANALYTICS DATA WAS PROVIDED above — USE IT for your assessment:\n"
            "    - High bounce_rate or low scroll_depth → Clarity/Relevance lever scores LOW (working signal weak)\n"
            "    - Mobile vs desktop CR gap → flag mobile-specific preservation_zones separately\n"
            "    - funnel_steps reveal EXACT drop-off step → preservation_zones near drop-off get extra scrutiny\n"
            "    - form_start_rate vs form_completion_rate → tells you if loss is at PAGE level vs FORM level\n"
        )

    return (
        f"BRIEF:\n{brief.brief}\n\n"
        f"METADATA:\n"
        f"  niche: {brief.niche}\n"
        f"  parent_category: {brief.parent_category}\n"
        f"  market: {brief.market}\n"
        f"  traffic_source_primary: {brief.traffic_source_primary}\n"
        f"  page_goal: {brief.page_goal}\n"
        f"  primary_metric: {brief.primary_metric}\n"
        + (f"  business_constraints: {brief.business_constraints}\n"
           if brief.business_constraints else "")
        + constraints_block
        + budget_block
        + performance_block
        + page_block
        + "\n"
        f"Apply your 5-step workflow from your AGENT system above.\n"
        f"Produce a PageWorksAnalysis JSON object.\n\n"
        f"Critical reminders:\n"
        f"  - Score every LIFT lever 1-5 (REVERSE: high score = preserve)\n"
        f"  - Identify 3-5 trust mechanisms with load-share estimates\n"
        f"  - preservation_zones MUST have specific reasons (not 'best practice')\n"
        f"  - warnings_for_downstream MUST be ACTIONABLE (DO NOT propose X without Y)\n"
        f"  - If page_context is missing, confidence ≤ 0.6\n"
        + real_data_reminder
    )


async def run_page_works_analyzer(
    brief: MarketingBrief,
    *,
    page_context: PageContext | None = None,
    run_logger: RunLogger,
    cfg: AgentsConfig,
) -> PageWorksAnalysis:
    """Run the Page-Works Analyzer.

    First expert in the pipeline — analyzes what's working on the existing LP
    before any "improvement" agent runs.
    """
    agent_cfg = cfg.get_agent(AGENT_NAME)

    system = load_agent_system(
        agent_name="page_works_analyzer",
        niche=brief.niche,
        brief_text=brief.brief,
    )

    log.info(
        "page_works routing: matched_via=%s token=%s segment=%s frameworks=%d goldens=%d",
        system.routing.matched_via, system.routing.matched_token,
        system.routing.segment, len(set(system.routing.frameworks)),
        len(system.routing.golden_sets),
    )

    user_prompt = _build_user_prompt(brief, page_context)

    inv = run_logger.start_agent(
        AGENT_NAME,
        input_full={
            "brief": brief.model_dump(),
            "has_page_context": page_context is not None,
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
            output_type=PageWorksAnalysis,
            invocation_logger=inv,
        )
        inv.complete(
            succeeded=True,
            output_full=output.model_dump(),
            output_summary=(
                f"baseline={output.baseline_assessment} "
                f"trust_mechanisms={len(output.trust_anatomy)} "
                f"preserve={len(output.preservation_zones)} "
                f"safe={len(output.change_safe_zones)} "
                f"warnings={len(output.warnings_for_downstream)} "
                f"confidence={output.confidence:.2f}"
            ),
        )
        return output
    except Exception as e:
        inv.complete(succeeded=False, final_error=f"{type(e).__name__}: {e}")
        raise
