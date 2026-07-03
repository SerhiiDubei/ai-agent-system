"""Product Director agent runtime (Phase 5h).

The synthesizer + final decision-maker. Runs LAST in the pipeline, after
all expert outputs are produced. Reads everything, applies operating
constraints, produces ranked ship/iterate/kill recommendations.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ai_agent_system.hypotheses.judge_schemas import HypothesisJudgeOutput
from ai_agent_system.hypotheses.mde_calculator import assess_feasibility
from ai_agent_system.hypotheses.schemas import HypothesisGeneratorOutput
from ai_agent_system.marketing.agents._base import run_with_fallback_direct
from ai_agent_system.marketing.agents_v2.system_loader import load_agent_system
from ai_agent_system.marketing.brief import MarketingBrief
from ai_agent_system.marketing.models import MarketingContext
from ai_agent_system.marketing.performance_renderer import (
    render_budget_block,
    render_performance_block,
)
from ai_agent_system.observability.agent_logger import RunLogger
from ai_agent_system.observability.config_loader import AgentsConfig
from ai_agent_system.page_works.schemas import PageWorksAnalysis
from ai_agent_system.product_director.schemas import ProductDirectorDecision

log = logging.getLogger(__name__)

AGENT_NAME = "product_director"


def _build_user_prompt(
    *,
    brief: MarketingBrief,
    page_works: PageWorksAnalysis | None,
    ctx: MarketingContext,
    extras: dict[str, Any],
    hg_output: HypothesisGeneratorOutput,
    judge_output: HypothesisJudgeOutput,
) -> str:
    constraints = brief.operating_constraints
    constraints_block = "\n\nOPERATING CONSTRAINTS:\n"
    if constraints:
        constraints_block += (
            f"  monthly_traffic_volume: {constraints.monthly_traffic_volume or '(not provided)'}\n"
            f"  baseline_conversion_rate_pct: {constraints.baseline_conversion_rate_pct or '(not provided)'}\n"
            f"  time_window_days: {constraints.time_window_days or '(not provided)'}\n"
            f"  expected_lift_floor_pct: {constraints.expected_lift_floor_pct or '(not provided)'}\n"
            f"  risk_appetite: {constraints.risk_appetite}\n"
        )
        if constraints.prior_tests_tried:
            constraints_block += "  prior_tests_tried:\n"
            for t in constraints.prior_tests_tried:
                constraints_block += f"    - {t}\n"
    else:
        constraints_block += "  (no operating constraints provided — confidence will be reduced)\n"

    # Phase 5d.1 — budget + real performance metrics (if operator provided)
    budget_block = render_budget_block(constraints)
    performance_block = render_performance_block(brief.current_performance)

    # Page-Works summary
    pw_block = "\n\nPAGE-WORKS ANALYSIS (preservation map):\n"
    if page_works:
        pw_block += f"  baseline_assessment: {page_works.baseline_assessment}\n"
        pw_block += f"  confidence: {page_works.confidence:.2f}\n"
        pw_block += "  trust_anatomy:\n"
        for tm in page_works.trust_anatomy:
            pw_block += f"    - {tm.element} (~{tm.estimated_load_pct}% load): {tm.why_working}\n"
        pw_block += "  preservation_zones (DO NOT TOUCH unless extraordinary evidence):\n"
        for pz in page_works.preservation_zones:
            pw_block += f"    - {pz.element}: {pz.reason[:200]}\n"
        pw_block += "  warnings_for_downstream:\n"
        for w in page_works.warnings_for_downstream:
            pw_block += f"    ⚠ {w}\n"
    else:
        pw_block += "  (Page-Works analysis not provided — preservation discipline reduced)\n"

    # Persona context (compact)
    persona_block = "\n\nPERSONAS (from Customer Insights):\n"
    for p in ctx.personas:
        persona_block += f"  - {p.name} (role={p.role})\n"

    # HG plans (compact — full data is in the plans themselves)
    plans_block = f"\n\nHYPOTHESIS GENERATOR PLANS ({len(hg_output.plans)}):\n"
    for p in hg_output.plans:
        depth = getattr(p, "test_depth_level", "unspecified")
        plans_block += (
            f"\n  {p.test_id}: {p.name}\n"
            f"    depth={depth}, ICE={p.ice_total} (I={p.impact_score} C={p.confidence_score} E={p.ease_score})\n"
            f"    target_persona={p.target_persona_name!r}, awareness={p.awareness_stage_targeted}\n"
            f"    addresses_friction: {p.addressed_friction or '(none)'}\n"
            f"    hypothesis: {p.hypothesis_statement[:200]}\n"
            f"    elements_changed: {getattr(p, 'elements_changed', '(unspecified)')}\n"
            f"    sample_size_per_arm: {p.sample_size_per_arm_estimate or '(missing)'}\n"
            f"    duration_days: {p.duration_estimate_days or '(missing)'}\n"
            f"    risk={p.risk_level}, effort={p.implementation_effort}\n"
        )

    # Judge verdicts (compact)
    judge_block = "\n\nJUDGE VERDICTS:\n"
    for v in judge_output.verdicts:
        judge_block += (
            f"  {v.test_id}: {v.verdict.upper()} ({v.overall_score}/10) — "
            f"strengths_count={len(v.strengths)}, weaknesses_count={len(v.weaknesses)}\n"
        )
    judge_block += f"  program_assessment: {judge_output.program_assessment}\n"
    judge_block += f"  ship={judge_output.ship_count} iterate={judge_output.iterate_count} kill={judge_output.kill_count}\n"

    # MDE pre-check (deterministic — gives the model the math)
    mde_block = ""
    if constraints and constraints.monthly_traffic_volume and constraints.baseline_conversion_rate_pct and constraints.time_window_days:
        mde_block = "\n\nMDE FEASIBILITY (pre-computed for each plan):\n"
        for p in hg_output.plans:
            primary_mc = next((sc for sc in p.success_criteria if sc.is_primary), None)
            if not primary_mc:
                continue
            verdict = assess_feasibility(
                monthly_traffic=constraints.monthly_traffic_volume,
                time_window_days=constraints.time_window_days,
                baseline_rate_pct=constraints.baseline_conversion_rate_pct,
                desired_lift_pct=primary_mc.minimum_detectable_lift_pct,
                n_arms=2,
            )
            tag = "✓ feasible" if verdict.feasible else "✗ INFEASIBLE"
            mde_block += f"  {p.test_id}: {tag}. {verdict.reason}\n"

    has_real_data = bool(performance_block or budget_block)
    real_data_reminder = ""
    if has_real_data:
        real_data_reminder = (
            "  - ⭐ REAL ANALYTICS provided — use BUDGET / CPA / ROAS for ROI math, not just MDE math:\n"
            "      • If `target_cpa_usd` and `current_cpa_usd` known: ship plans likely to LOWER CPA\n"
            "      • If `roas`, `aov_usd`, `monthly_conversions` known: estimate REVENUE LIFT, not just CR lift\n"
            "      • If `funnel_steps` show biggest drop-off: prioritize plans that address THAT step\n"
            "      • Mention the dollar/ROI math in `strategic_recommendation` and per-plan `why_this_first`\n"
            "      • Test cost = sample_size × n_arms × cpc_usd; flag if cost > total_program_budget_usd\n"
        )

    return (
        f"BRIEF: {brief.niche} / {brief.parent_category} / {brief.market}\n"
        f"  page_goal: {brief.page_goal}\n"
        f"  primary_metric: {brief.primary_metric}\n"
        f"  brief: {brief.brief}\n"
        + constraints_block
        + budget_block
        + performance_block
        + pw_block
        + persona_block
        + plans_block
        + judge_block
        + mde_block
        + "\n\nTASK\n"
        "====\n"
        "Apply your 7-step workflow. Produce a ProductDirectorDecision JSON.\n\n"
        "Critical reminders:\n"
        "  - Read EVERYTHING before deciding (no first-impression verdicts)\n"
        "  - Page-Works preservation_zones override Generator cleverness\n"
        "  - prior_tests_tried = kill repeats with specific reason\n"
        "  - MDE infeasible = downgrade or kill (not 'ship and hope')\n"
        "  - Sequence tests for constrained traffic; parallelize only when math supports it\n"
        "  - strategic_recommendation must be PROGRAM-LEVEL, not test-level\n"
        "  - Default to defer (iterate) over ship for borderline plans\n"
        + real_data_reminder
    )


async def run_product_director(
    *,
    brief: MarketingBrief,
    page_works: PageWorksAnalysis | None,
    ctx: MarketingContext,
    extras: dict[str, Any],
    hg_output: HypothesisGeneratorOutput,
    judge_output: HypothesisJudgeOutput,
    run_logger: RunLogger,
    cfg: AgentsConfig,
) -> ProductDirectorDecision:
    """Run the Product Director — final decision-maker.

    Inputs include ALL upstream expert outputs + operating constraints +
    judge verdicts. Output is a single ranked decision package.
    """
    agent_cfg = cfg.get_agent(AGENT_NAME)

    system = load_agent_system(
        agent_name="product_director",
        niche=brief.niche,
        brief_text=brief.brief,
    )

    user_prompt = _build_user_prompt(
        brief=brief, page_works=page_works, ctx=ctx, extras=extras,
        hg_output=hg_output, judge_output=judge_output,
    )

    inv = run_logger.start_agent(
        AGENT_NAME,
        input_full={
            "plans_to_decide": len(hg_output.plans),
            "judge_ship_count": judge_output.ship_count,
            "has_page_works": page_works is not None,
            "has_constraints": brief.operating_constraints is not None,
            "system_prompt_length_chars": len(system.system_prompt),
            "files_loaded": system.files_loaded,
        },
        config_used=agent_cfg.model_dump(),
    )
    try:
        output = await run_with_fallback_direct(
            agent_name=AGENT_NAME,
            config=agent_cfg,
            system_prompt=system.system_prompt,
            user_prompt=user_prompt,
            output_type=ProductDirectorDecision,
            invocation_logger=inv,
        )
        inv.complete(
            succeeded=True,
            output_full=output.model_dump(),
            output_summary=(
                f"ship={len(output.shipped_plans)} "
                f"iterate={len(output.iterate_plans)} "
                f"kill={len(output.killed_plans)} "
                f"confidence={output.confidence:.2f}"
            ),
        )
        return output
    except Exception as e:
        inv.complete(succeeded=False, final_error=f"{type(e).__name__}: {e}")
        raise
