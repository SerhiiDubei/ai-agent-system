"""Hypothesis Generator agent (N6).

Consumes the full output of N4 (decomposed drafter) + optional page_context,
and generates 3-6 production-ready A/B test plans.

Architecture pattern reused from marketing/agents/_base.py:
  - Loads character card from prompts/hypothesis_generator/v<N>.md
  - Resolves model via tier system in agents.yml
  - Uses run_with_fallback for primary→fallback chain
  - Logs every step via observability/agent_logger
"""

from __future__ import annotations

import logging
from typing import Any

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
from ai_agent_system.marketing.performance_renderer import (
    render_budget_block,
    render_performance_block,
)
from ai_agent_system.observability.agent_logger import RunLogger
from ai_agent_system.observability.config_loader import AgentsConfig

log = logging.getLogger(__name__)

AGENT_NAME = "hypothesis_generator"


def _build_user_prompt(
    *,
    brief: MarketingBrief,
    ctx: MarketingContext,
    extras: dict[str, Any],
    page_context: PageContext | None,
) -> str:
    """Pack the full upstream context into a single dense prompt.

    Order matters: brief metadata first (anchoring), then personas (the human),
    then voice/copy material (your raw words), then channel/audience (where they
    arrive), then CRO (what's broken), then page (what we observed). Hypothesis
    generator reads top-to-bottom and synthesizes.
    """
    voice = extras.get("voice_message", {})
    media_x = extras.get("media_extras", {})
    audience_x = extras.get("audience_extras", {})
    cro_x = extras.get("cro_extras", {})
    audience_psych = extras.get("audience_psychology_summary", "")

    # ── Personas block ────────────────────────────────────────────────────────
    persona_lines: list[str] = []
    for p in ctx.personas:
        persona_lines.append(
            f"  • {p.name}\n"
            f"      role={p.role}, age={p.age_range}, income={p.income_band}, "
            f"digital_literacy={p.digital_literacy}\n"
            f"      JTBD: {p.primary_job}\n"
            f"      top pains: " + "; ".join(pp.label for pp in p.pain_points[:3])
        )

    # ── Voice & message block ─────────────────────────────────────────────────
    headline_lines = [
        f"      [{h['awareness_stage']}] {h['angle_name']!r} → {h['sample_headline']!r}"
        for h in voice.get("headline_angles", [])
    ]

    voice_examples = voice.get("voice_examples", [])
    voice_lines = "\n".join(f"      \"{q}\"" for q in voice_examples[:5])

    # ── CRO block ─────────────────────────────────────────────────────────────
    test_priorities_lines: list[str] = []
    for t in cro_x.get("test_priorities", []):
        ice = t["impact_score"] + t["confidence_score"] + t["ease_score"]
        test_priorities_lines.append(
            f"      [ICE={ice}] {t['element']}\n"
            f"          {t['hypothesis']}"
        )

    friction_lines = [
        f"      [{f['severity']}] {f['location']}: {f['issue']}"
        for f in cro_x.get("friction_inventory", [])
    ]

    user_flow_lines = [
        f"      [{s.stage}] ({s.typical_duration}) — {s.description}"
        for s in ctx.user_flow.stages
    ]

    # ── Optional page context ─────────────────────────────────────────────────
    page_block = ""
    if page_context:
        page_block = (
            "\n\nPAGE CAPTURED — when designing variants, use the visible copy below "
            "as the explicit control. Your variant copy should be defensible against "
            "what is currently on the page.\n\n"
            f"{render_page_context_for_prompt(page_context)}\n"
        )

    # ── Phase 5d.1: real performance metrics + budget ────────────────────────
    budget_block = render_budget_block(brief.operating_constraints)
    performance_block = render_performance_block(brief.current_performance)
    has_real_data = bool(performance_block or budget_block)

    return (
        "MARKETING BRIEF\n"
        "===============\n"
        f"  niche: {brief.niche}\n"
        f"  page_goal: {brief.page_goal}\n"
        f"  primary_metric: {brief.primary_metric}\n"
        f"  traffic_source: {brief.traffic_source_primary}\n"
        f"  market: {brief.market}\n"
        + (f"  business_constraints: {brief.business_constraints}\n"
           if brief.business_constraints else "")
        + "\n"
        + f"  Brief text:\n  {brief.brief}\n\n"

        "PERSONAS (from Customer Insights)\n"
        "==================================\n"
        + "\n".join(persona_lines) + "\n\n"
        f"  Audience psychology summary:\n  {audience_psych}\n\n"

        "VOICE & MESSAGE (from Voice Strategist)\n"
        "========================================\n"
        f"  Primary value prop: \"{voice.get('primary_value_prop', '')}\"\n"
        f"  Hooks (paid social):\n"
        + "\n".join(f"    - {h}" for h in voice.get("hook_variations", []))
        + "\n  Headline angles:\n"
        + ("\n".join(headline_lines) if headline_lines else "    (none provided)")
        + "\n  Verbatim voice examples:\n"
        + (voice_lines if voice_lines else "      (none provided)")
        + f"\n  Banned words: {voice.get('banned_words', [])}\n\n"

        "CHANNEL CONTEXT (from Media Planner)\n"
        "=====================================\n"
        f"  channel: {ctx.channel_profile.channel}\n"
        f"  channel_temperature: {media_x.get('channel_temperature')}\n"
        f"  creative_grammar: {media_x.get('creative_grammar', '')[:300]}\n\n"

        "AUDIENCE STRATEGY (from Audience Strategist)\n"
        "=============================================\n"
        f"  primary_persona_name: {ctx.audience_profile.primary_persona_name!r}\n"
        f"  estimated_primary_share: {ctx.audience_profile.estimated_primary_share:.0%}\n"
        f"  lookalike seeds: {audience_x.get('lookalike_seeds', [])}\n"
        f"  exclusion signals: {audience_x.get('exclusion_signals', [])}\n\n"

        "CONVERSION ARCHITECTURE (from CRO Lead)\n"
        "========================================\n"
        f"  user flow ({len(ctx.user_flow.stages)} stages):\n"
        + "\n".join(user_flow_lines) + "\n"
        f"  primary_friction_point: {ctx.user_flow.primary_friction_point}\n"
        f"  drop_off_hypothesis: {ctx.user_flow.drop_off_hypothesis}\n\n"
        "  CRO seed test priorities (consider these as strong candidates):\n"
        + "\n".join(test_priorities_lines) + "\n\n"
        "  Friction inventory:\n"
        + ("\n".join(friction_lines) if friction_lines else "      (none recorded)")
        + page_block
        + budget_block
        + performance_block
        + "\n\n"

        "TASK\n"
        "====\n"
        "Generate the HypothesisGeneratorOutput JSON now.\n"
        "  • 3-6 plans, ranked by ICE descending in the array\n"
        "  • At least one plan with Impact >= 7 (a 'big rock' test)\n"
        "  • Each plan's target_persona_name MUST exactly match a persona name above\n"
        "  • Each plan's hypothesis_statement MUST follow the "
        "'Because we observed [X], we believe [variant] will cause [metric direction], "
        "which we'll know by [criterion]' format\n"
        "  • Each variant MUST contain concrete copy_changes or design_changes — "
        "no 'shorten the headline' fluff\n"
        "  • Exactly one success_criterion per plan has is_primary=True\n"
        "  • If page_context is provided, ground variants to specific elements you saw\n"
        + (
            "  • ⭐ REAL ANALYTICS PROVIDED — prioritize plans that target documented funnel "
            "drop-off steps; cite specific numbers from the data in `rationale` (e.g. "
            "'mobile CR is 12% vs desktop 28% — this test addresses mobile-only friction').\n"
            "  • If `current_cpa_usd` and `target_cpa_usd` provided: each plan's `expected_lift_range_pct` "
            "should also imply economic feasibility (lift that closes the CPA gap).\n"
            if has_real_data else ""
        )
    )


async def generate_hypotheses(
    *,
    brief: MarketingBrief,
    ctx: MarketingContext,
    extras: dict[str, Any],
    page_context: PageContext | None = None,
    run_logger: RunLogger,
    cfg: AgentsConfig,
) -> HypothesisGeneratorOutput:
    """Run the Hypothesis Generator agent.

    Inputs come from a completed N4 (decomposed drafter) run:
      - brief, ctx, extras, page_context (already passed through orchestrator)

    Logs everything via the same RunLogger used by the upstream agents,
    so the inspect_run.py timeline shows N4 + N6 in one continuous trace.
    """
    agent_cfg = cfg.get_agent(AGENT_NAME)
    prompt_version = cfg.prompt_versions.get(AGENT_NAME, "v1")
    system_prompt = load_character_card(AGENT_NAME, prompt_version)
    user_prompt = _build_user_prompt(
        brief=brief, ctx=ctx, extras=extras, page_context=page_context,
    )

    inv = run_logger.start_agent(
        AGENT_NAME,
        input_full={
            "brief_niche": brief.niche,
            "personas_count": len(ctx.personas),
            "test_priorities_count": len(extras.get("cro_extras", {}).get("test_priorities", [])),
            "page_context": page_context.short_summary() if page_context else "none",
        },
        config_used=agent_cfg.model_dump(),
    )
    try:
        output = await run_with_fallback_direct(
            agent_name=AGENT_NAME,
            config=agent_cfg,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_type=HypothesisGeneratorOutput,
            invocation_logger=inv,
        )
        top_ice = max((p.ice_total for p in output.plans), default=0)
        inv.complete(
            succeeded=True,
            output_full=output.model_dump(),
            output_summary=(
                f"{len(output.plans)} plans, top ICE={top_ice}, "
                f"{len(output.deferred_ideas)} deferred"
            ),
        )
        return output
    except Exception as e:
        inv.complete(succeeded=False, final_error=f"{type(e).__name__}: {e}")
        raise
