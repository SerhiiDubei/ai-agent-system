"""Hypothesis Judge agent (N7).

Consumes a HypothesisGeneratorOutput and produces structured verdicts +
ship/iterate/kill recommendations per plan.

Architecture:
  - Same direct-API pattern as Hypothesis Generator (deeply-nested schema)
  - Cheaper model (gpt-4o-mini) — judge is pattern matching, not creative production
  - Logs everything via observability for full inspection
"""

from __future__ import annotations

import logging
from typing import Any

from ai_agent_system.hypotheses.judge_schemas import HypothesisJudgeOutput
from ai_agent_system.hypotheses.schemas import HypothesisGeneratorOutput
from ai_agent_system.marketing.agents._base import (
    load_character_card,
    run_with_fallback_direct,
)
from ai_agent_system.marketing.brief import MarketingBrief
from ai_agent_system.marketing.models import MarketingContext
from ai_agent_system.marketing.page_context import (
    PageContext,
    render_page_context_for_prompt,
)
from ai_agent_system.observability.agent_logger import RunLogger
from ai_agent_system.observability.config_loader import AgentsConfig

log = logging.getLogger(__name__)

AGENT_NAME = "hypothesis_judge"


def _build_user_prompt(
    *,
    brief: MarketingBrief,
    ctx: MarketingContext,
    extras: dict[str, Any],
    hg_output: HypothesisGeneratorOutput,
    page_context: PageContext | None,
) -> str:
    """Pack: brief, drafter outputs (for context), generator's plans (for review)."""
    cro_x = extras.get("cro_extras", {})
    voice = extras.get("voice_message", {})
    banned = voice.get("banned_words", [])

    # Friction context (judge needs to see what the CRO documented)
    friction_lines = [
        f"  [{f['severity']}] {f['location']}: {f['issue']}"
        for f in cro_x.get("friction_inventory", [])
    ]

    # Persona names (judge checks persona_anchor)
    persona_names = [p.name for p in ctx.personas]

    # Plans to evaluate
    plans_block_lines: list[str] = []
    for p in hg_output.plans:
        plans_block_lines.append(f"\n=== {p.test_id}: {p.name} ===")
        plans_block_lines.append(f"  ICE: {p.ice_total} (I={p.impact_score} C={p.confidence_score} E={p.ease_score})")
        plans_block_lines.append(f"  target_persona_name: {p.target_persona_name!r}")
        plans_block_lines.append(f"  awareness_stage_targeted: {p.awareness_stage_targeted}")
        plans_block_lines.append(f"  addressed_friction: {p.addressed_friction!r}")
        plans_block_lines.append(f"  hypothesis_statement: {p.hypothesis_statement}")
        plans_block_lines.append(f"  Variants ({len(p.variants)}):")
        for v in p.variants:
            plans_block_lines.append(f"    [{v.label}] {v.description}")
            for c in v.copy_changes:
                plans_block_lines.append(f"      copy: {c}")
            for d in v.design_changes:
                plans_block_lines.append(f"      design: {d}")
        plans_block_lines.append(f"  success_criteria:")
        for sc in p.success_criteria:
            primary = " [PRIMARY]" if sc.is_primary else ""
            plans_block_lines.append(
                f"    - {sc.metric_name} {sc.direction} ≥{sc.minimum_detectable_lift_pct}%{primary}"
            )
        plans_block_lines.append(f"  expected_lift_range_pct: {p.expected_lift_range_pct}")
        plans_block_lines.append(f"  risk_level: {p.risk_level}")
        plans_block_lines.append(f"  implementation_effort: {p.implementation_effort}")
        plans_block_lines.append(f"  sample_size_per_arm_estimate: {p.sample_size_per_arm_estimate}")
        plans_block_lines.append(f"  duration_estimate_days: {p.duration_estimate_days}")
        plans_block_lines.append(f"  rationale: {p.rationale}")
        plans_block_lines.append(f"  rollback_criteria: {p.rollback_criteria}")

    page_block = ""
    if page_context:
        page_block = (
            f"\n\nPAGE OBSERVED — use this to verify plans' addressed_friction "
            f"actually exists on the page:\n\n{render_page_context_for_prompt(page_context)}"
        )

    return (
        "BRIEF METADATA\n"
        "==============\n"
        f"  niche: {brief.niche}\n"
        f"  page_goal: {brief.page_goal}\n"
        f"  primary_metric: {brief.primary_metric}\n"
        f"  traffic_source_primary: {brief.traffic_source_primary}\n"
        + (f"  business_constraints: {brief.business_constraints}\n"
           if brief.business_constraints else "")
        + "\n"

        "PERSONAS AVAILABLE (verify target_persona_name matches one of these)\n"
        "===================================================================\n"
        + "\n".join(f"  - {n}" for n in persona_names) + "\n\n"

        f"BANNED WORDS (Voice Strategist forbade these)\n"
        f"==============================================\n"
        f"  {banned}\n\n"

        "FRICTION INVENTORY (verify addressed_friction quotes one of these)\n"
        "===================================================================\n"
        + ("\n".join(friction_lines) or "  (no friction inventory)") + "\n"
        + page_block + "\n\n"

        "GENERATOR'S TEST PROGRAM SUMMARY\n"
        "=================================\n"
        f"  {hg_output.test_program_summary}\n\n"

        f"PLANS TO REVIEW ({len(hg_output.plans)} total)\n"
        + "=" * 50 + "\n"
        + "\n".join(plans_block_lines) + "\n\n"

        "DEFERRED IDEAS FROM GENERATOR\n"
        "==============================\n"
        + "\n".join(f"  • {d}" for d in hg_output.deferred_ideas) + "\n\n"

        "TASK\n"
        "====\n"
        f"Generate the HypothesisJudgeOutput JSON now.\n"
        f"  • One JudgeVerdict per plan above ({len(hg_output.plans)} verdicts total)\n"
        f"  • verdicts[i].test_id MUST match the plan's test_id (T1-..., T2-..., etc.)\n"
        f"  • Score every per-dimension field (hypothesis_quality, variant_concreteness, "
        f"persona_anchor, friction_grounding, sample_size_realism, ice_defensibility)\n"
        f"  • verdict triad: ship (overall ≥ 8) / iterate (5-7) / kill (≤ 4)\n"
        f"  • ship_count + iterate_count + kill_count MUST equal {len(hg_output.plans)}\n"
        f"  • cross_plan_observations should flag: missing persona coverage, no big-rock "
        f"test (Impact ≥ 7), all-same-risk-level batches, banned-word violations\n"
    )


async def judge_hypotheses(
    *,
    brief: MarketingBrief,
    ctx: MarketingContext,
    extras: dict[str, Any],
    hg_output: HypothesisGeneratorOutput,
    page_context: PageContext | None = None,
    run_logger: RunLogger,
    cfg: AgentsConfig,
) -> HypothesisJudgeOutput:
    """Run the Hypothesis Judge agent.

    Inputs:
      - brief, ctx, extras: original context (so judge sees what plans should be anchored to)
      - hg_output: the Generator's plans batch to evaluate
      - page_context: optional, helps judge verify friction_grounding

    Returns: structured verdicts + program-level assessment.
    """
    agent_cfg = cfg.get_agent(AGENT_NAME)
    prompt_version = cfg.prompt_versions.get(AGENT_NAME, "v1")
    system_prompt = load_character_card(AGENT_NAME, prompt_version)
    user_prompt = _build_user_prompt(
        brief=brief, ctx=ctx, extras=extras,
        hg_output=hg_output, page_context=page_context,
    )

    inv = run_logger.start_agent(
        AGENT_NAME,
        input_full={
            "plans_count": len(hg_output.plans),
            "plan_ids": [p.test_id for p in hg_output.plans],
        },
        config_used=agent_cfg.model_dump(),
    )
    try:
        output = await run_with_fallback_direct(
            agent_name=AGENT_NAME,
            config=agent_cfg,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_type=HypothesisJudgeOutput,
            invocation_logger=inv,
        )
        inv.complete(
            succeeded=True,
            output_full=output.model_dump(),
            output_summary=(
                f"{output.ship_count} ship / {output.iterate_count} iterate / "
                f"{output.kill_count} kill ({len(output.verdicts)} plans)"
            ),
        )
        return output
    except Exception as e:
        inv.complete(succeeded=False, final_error=f"{type(e).__name__}: {e}")
        raise
