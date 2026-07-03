"""Orchestrator for the decomposed drafter pipeline.

For Phase 1 we use plain asyncio.gather for parallelism — it's enough for
3-then-2 wave topology and avoids LangGraph dependency for the initial build.

Topology:
  WAVE 1 (parallel):
    - customer_insights      (no deps)
    - media_planner          (no deps)
    - conversion_architect   (no deps)

  WAVE 2 (parallel):
    - voice_message          (deps: customer_insights)
    - audience_strategist    (deps: customer_insights + media_planner)

  WAVE 3:
    - assembler              (combines all into MarketingContext)

If Phase 5 reveals we need: per-node retry policies, conditional fallback
to a "degraded draft" assembler, checkpointing of partial runs — we'll swap
this for a LangGraph StateGraph. For now, simpler is better.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ai_agent_system.marketing.agents import (
    run_audience_strategist,
    run_conversion_architect,
    run_customer_insights,
    run_media_planner,
    run_voice_message,
)
from ai_agent_system.marketing.assembler import assemble_marketing_context
from ai_agent_system.marketing.brief import MarketingBrief
from ai_agent_system.marketing.models import MarketingContext
from ai_agent_system.marketing.page_context import PageContext, load_page_context
from ai_agent_system.observability.agent_logger import get_agent_logger
from ai_agent_system.observability.config_loader import load_agents_config

log = logging.getLogger(__name__)


async def _try_load_page_context(
    brief: MarketingBrief,
    page_context_override: PageContext | None,
) -> PageContext | None:
    """Resolve page context from override OR from DB if brief.page_snapshot_id set.

    Graceful: any DB error → log + return None. Phase 2 must NEVER block Phase 1.
    """
    if page_context_override is not None:
        return page_context_override
    if brief.page_snapshot_id is None:
        return None

    try:
        from ai_agent_system.db.session import async_session_factory
        async with async_session_factory() as session:
            ctx = await load_page_context(brief.page_snapshot_id, session=session)
            if ctx:
                log.info("Loaded page context: %s", ctx.short_summary())
            return ctx
    except Exception as exc:
        log.warning(
            "Failed to load page context for snapshot_id=%s: %s — proceeding without",
            brief.page_snapshot_id, exc,
        )
        return None


async def draft_marketing_context_v2(
    brief: MarketingBrief,
    *,
    retrieved_chunks: list[str] | None = None,
    page_context: PageContext | None = None,
    run_label: str | None = None,
    tags: list[str] | None = None,
) -> tuple[MarketingContext, dict[str, Any], str]:
    """Run the 5-agent decomposed drafter pipeline.

    Returns:
        (MarketingContext, extra_assembler_metadata, run_id)

    The run_id can be passed to scripts/inspect_run.py for full timeline.
    """
    cfg = load_agents_config()
    logger = get_agent_logger()

    label = run_label or f"draft:{brief.niche}"
    run = logger.start_run(label=label, tags=(tags or []) + ["drafter_v2"])
    log.info("Starting decomposed drafter run %s for niche=%s", run.run_id, brief.niche)

    chunks = retrieved_chunks or []

    # ── PRE-WAVE: resolve page_context (DB lookup if available, override if passed) ──
    resolved_page_ctx = await _try_load_page_context(brief, page_context)
    if resolved_page_ctx:
        run.note(
            f"Page context loaded: {resolved_page_ctx.short_summary()}",
            payload={
                "snapshot_id": resolved_page_ctx.snapshot_id,
                "url": resolved_page_ctx.url,
                "archetype": resolved_page_ctx.page_archetype,
                "friction_signals_count": len(resolved_page_ctx.friction_signals),
            },
        )
    else:
        run.note(
            "No page context — drafter operating in brief-only mode",
            payload={"page_snapshot_id": brief.page_snapshot_id},
        )

    try:
        # ── WAVE 1: 3 parallel agents (no inter-deps) ────────────────────────
        run.note("Wave 1 starting: customer_insights, media_planner, conversion_architect")

        insights, media, cro = await asyncio.gather(
            run_customer_insights(brief, chunks, run_logger=run, cfg=cfg),
            run_media_planner(brief, run_logger=run, cfg=cfg),
            run_conversion_architect(
                brief, run_logger=run, cfg=cfg,
                page_context=resolved_page_ctx,
            ),
        )

        run.note(
            "Wave 1 complete",
            payload={
                "personas_count": len(insights.personas),
                "channel": media.channel_profile.channel,
                "test_priorities": len(cro.test_priorities),
            },
        )

        # ── WAVE 2: 2 parallel agents (depend on Wave 1 outputs) ─────────────
        run.note("Wave 2 starting: voice_message, audience_strategist")

        voice, audience = await asyncio.gather(
            run_voice_message(
                brief, insights, run_logger=run, cfg=cfg,
                page_context=resolved_page_ctx,
            ),
            run_audience_strategist(brief, insights, media, run_logger=run, cfg=cfg),
        )

        run.note(
            "Wave 2 complete",
            payload={
                "value_prop": voice.primary_value_prop[:80],
                "primary_persona": audience.audience_profile.primary_persona_name,
                "lookalike_seeds": len(audience.lookalike_seeds),
            },
        )

        # ── WAVE 3: assembler (no LLM, just composition + cross-field validation) ──
        run.note("Wave 3 starting: assembler (cross-field validation)")
        ctx, extras = assemble_marketing_context(
            brief=brief,
            insights=insights,
            voice=voice,
            media=media,
            audience=audience,
            cro=cro,
            grounding_chunks=chunks,
        )
        run.note(
            "Assembler succeeded — MarketingContext validated",
            payload={"extras_keys": list(extras.keys())},
        )

        run.complete(payload={
            "succeeded": True,
            "personas": len(ctx.personas),
            "channel": ctx.channel_profile.channel,
            "primary_persona": ctx.audience_profile.primary_persona_name,
        })
        return ctx, extras, run.run_id

    except Exception as e:
        log.exception("Decomposed drafter run %s failed: %s", run.run_id, e)
        run.abort(
            reason=f"{type(e).__name__}: {e}",
            payload={"error_type": type(e).__name__, "error_msg": str(e)[:500]},
        )
        raise
