"""Full Pipeline v3 (Phase 5) — agent-as-system + page-works + product-director.

This is the production-grade pipeline that incorporates everything from
Phases 0-5h:
  - Page-Works Analyzer (NEW first step — preservation analysis)
  - Customer Insights v2 (agent-as-system)
  - Voice Message, Media Planner, Audience Strategist, Conversion Architect (still v1)
  - Hypothesis Generator (with operating constraints)
  - Hypothesis Judge
  - Product Director (NEW final synthesizer)

All experts log to a single RunLogger so inspect_run.py shows the full chain.

Topology:
  WAVE 0: Page-Works Analyzer (sees the page first; informs everyone)

  WAVE 1 (parallel, 3 agents):
    - Customer Insights v2 (gets page_works warnings via context)
    - Media Planner
    - Conversion Architect (gets page_works warnings via context)

  WAVE 2 (parallel, 2 agents):
    - Voice Message (gets CI output + page_works warnings)
    - Audience Strategist (gets CI + Media)

  WAVE 3:
    - Assembler (combines into MarketingContext)
    - Hypothesis Generator (consumes everything + operating_constraints)

  WAVE 4:
    - Hypothesis Judge

  WAVE 5:
    - Product Director (synthesizes everything → ranked decision package)

If `brief.client_id` is provided, every expert reads/writes persistent state.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ai_agent_system.hypotheses.generator import generate_hypotheses
from ai_agent_system.hypotheses.judge import judge_hypotheses
from ai_agent_system.hypotheses.judge_schemas import HypothesisJudgeOutput
from ai_agent_system.hypotheses.schemas import HypothesisGeneratorOutput
from ai_agent_system.marketing.agents import (
    run_audience_strategist,
    run_conversion_architect,
    run_media_planner,
    run_voice_message,
)
from ai_agent_system.marketing.agents_v2 import run_customer_insights_v2
from ai_agent_system.marketing.agents_v2.persistent_state import (
    load_current_state,
    render_state_for_prompt,
    save_current_state,
)
from ai_agent_system.marketing.assembler import assemble_marketing_context
from ai_agent_system.marketing.brief import MarketingBrief
from ai_agent_system.marketing.models import MarketingContext
from ai_agent_system.marketing.orchestrator import _try_load_page_context
from ai_agent_system.marketing.page_context import PageContext
from ai_agent_system.observability.agent_logger import get_agent_logger
from ai_agent_system.observability.config_loader import load_agents_config
from ai_agent_system.page_works.analyzer import run_page_works_analyzer
from ai_agent_system.page_works.schemas import PageWorksAnalysis
from ai_agent_system.product_director.director import run_product_director
from ai_agent_system.product_director.schemas import ProductDirectorDecision

log = logging.getLogger(__name__)


async def run_full_pipeline_v3(
    brief: MarketingBrief,
    *,
    retrieved_chunks: list[str] | None = None,
    page_context: PageContext | None = None,
    run_label: str | None = None,
    tags: list[str] | None = None,
) -> tuple[
    PageWorksAnalysis | None,
    MarketingContext,
    dict[str, Any],
    HypothesisGeneratorOutput,
    HypothesisJudgeOutput,
    ProductDirectorDecision,
    str,
]:
    """Run the full v3 pipeline. Returns all outputs + run_id."""
    cfg = load_agents_config()
    logger = get_agent_logger()

    label = run_label or f"v3:{brief.niche}"
    run = logger.start_run(label=label, tags=(tags or []) + ["pipeline_v3"])
    log.info("Starting v3 pipeline run %s for niche=%s client=%s",
             run.run_id, brief.niche, brief.client_id)

    chunks = retrieved_chunks or []

    # ── PRE-WAVE: resolve page context ────────────────────────────────────────
    resolved_pc = await _try_load_page_context(brief, page_context)
    if resolved_pc:
        run.note(f"Page context loaded: {resolved_pc.short_summary()}")
    else:
        run.note("No page context — Page-Works will operate in structural-only mode")

    # ── WAVE 0: Page-Works Analyzer (FIRST — informs everyone) ───────────────
    run.note("Wave 0: Page-Works Analyzer (preservation map)")
    page_works = None
    try:
        page_works = await run_page_works_analyzer(
            brief, page_context=resolved_pc, run_logger=run, cfg=cfg,
        )
        run.note(
            f"Page-Works complete: baseline={page_works.baseline_assessment} "
            f"preservation={len(page_works.preservation_zones)} "
            f"warnings={len(page_works.warnings_for_downstream)}"
        )
        # Persistent state save
        if brief.client_id:
            save_current_state(
                "page_works_analyzer", brief.client_id,
                page_works.model_dump(),
                version_note=f"run {run.run_id}",
            )
    except Exception as e:
        log.warning("Page-Works failed (non-blocking): %s — continuing without preservation map", e)
        run.note(f"Page-Works failed (continuing): {type(e).__name__}: {e}")

    # ── WAVE 1: 3 parallel agents (CI v2 + Media + CRO) ──────────────────────
    run.note("Wave 1: customer_insights_v2 + media_planner + conversion_architect")

    insights, media, cro = await asyncio.gather(
        run_customer_insights_v2(brief, chunks, run_logger=run, cfg=cfg),
        run_media_planner(brief, run_logger=run, cfg=cfg),
        run_conversion_architect(
            brief, run_logger=run, cfg=cfg, page_context=resolved_pc,
        ),
    )

    # Persist state for each
    if brief.client_id:
        save_current_state("customer_insights_v2", brief.client_id, insights.model_dump())
        save_current_state("media_planner", brief.client_id, media.model_dump())
        save_current_state("conversion_architect", brief.client_id, cro.model_dump())

    run.note(
        "Wave 1 complete",
        payload={
            "personas_count": len(insights.personas),
            "channel": media.channel_profile.channel,
            "test_priorities_count": len(cro.test_priorities),
        },
    )

    # ── WAVE 2: VoiceMessage + AudienceStrategist (depend on Wave 1) ─────────
    run.note("Wave 2: voice_message + audience_strategist")

    voice, audience = await asyncio.gather(
        run_voice_message(
            brief, insights, run_logger=run, cfg=cfg, page_context=resolved_pc,
        ),
        run_audience_strategist(brief, insights, media, run_logger=run, cfg=cfg),
    )

    if brief.client_id:
        save_current_state("voice_message", brief.client_id, voice.model_dump())
        save_current_state("audience_strategist", brief.client_id, audience.model_dump())

    # ── WAVE 3: Assembler + Hypothesis Generator ─────────────────────────────
    run.note("Wave 3: assembler → hypothesis_generator")
    ctx, extras = assemble_marketing_context(
        brief=brief, insights=insights, voice=voice,
        media=media, audience=audience, cro=cro,
        grounding_chunks=chunks,
    )

    # Generator now has access to operating_constraints via brief
    hg_output = await generate_hypotheses(
        brief=brief, ctx=ctx, extras=extras,
        page_context=resolved_pc, run_logger=run, cfg=cfg,
    )
    if brief.client_id:
        save_current_state("hypothesis_generator", brief.client_id, hg_output.model_dump())

    # ── WAVE 4: Hypothesis Judge ─────────────────────────────────────────────
    run.note(f"Wave 4: hypothesis_judge ({len(hg_output.plans)} plans)")
    j_output = await judge_hypotheses(
        brief=brief, ctx=ctx, extras=extras,
        hg_output=hg_output, page_context=resolved_pc,
        run_logger=run, cfg=cfg,
    )
    if brief.client_id:
        save_current_state("hypothesis_judge", brief.client_id, j_output.model_dump())

    # ── WAVE 5: Product Director (final synthesizer) ─────────────────────────
    run.note("Wave 5: product_director (final decision package)")
    director_output = await run_product_director(
        brief=brief, page_works=page_works,
        ctx=ctx, extras=extras,
        hg_output=hg_output, judge_output=j_output,
        run_logger=run, cfg=cfg,
    )
    if brief.client_id:
        save_current_state(
            "product_director", brief.client_id, director_output.model_dump(),
            version_note=f"run {run.run_id}",
        )

    run.complete(payload={
        "succeeded": True,
        "ship_count": len(director_output.shipped_plans),
        "iterate_count": len(director_output.iterate_plans),
        "kill_count": len(director_output.killed_plans),
        "confidence": director_output.confidence,
    })

    return page_works, ctx, extras, hg_output, j_output, director_output, run.run_id
