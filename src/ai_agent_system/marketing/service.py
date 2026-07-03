"""Marketing Context pipeline service — N4.

Orchestrates: RAG retrieval → drafter → judge → optional retry → DB persist.

Human approval gate: context starts in 'draft' status. Downstream agents
(N5+) only consume contexts with status='approved'.
"""

from __future__ import annotations

import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from ai_agent_system.marketing.drafter import DrafterDeps, draft_marketing_context
from ai_agent_system.marketing.judge import judge_context
from ai_agent_system.marketing.models import MarketingContext, SanityVerdict

log = logging.getLogger(__name__)


async def _retrieve_grounding_chunks(
    *,
    niche: str,
    top_k: int = 5,
) -> list[str]:
    """Pull niche-relevant knowledge chunks from pgvector.

    Uses its own session so a failure doesn't poison the caller's transaction.
    Gracefully returns [] when knowledge base is empty.
    """
    from ai_agent_system.db.session import async_session_factory
    from sqlalchemy import text

    try:
        async with async_session_factory() as s:
            rows = await s.execute(
                text("""
                    SELECT text FROM kb_chunks
                    WHERE
                        parent_category ILIKE :niche
                        OR niches::text ILIKE :niche_like
                    ORDER BY authority_weight DESC NULLS LAST
                    LIMIT :k
                """),
                {"niche": f"%{niche}%", "niche_like": f"%{niche}%", "k": top_k},
            )
            return [r[0] for r in rows.fetchall()]
    except Exception as exc:
        log.warning("marketing:grounding_retrieval_failed: %s", exc)
        return []


async def generate_marketing_context(
    *,
    session: AsyncSession,
    brief: str,
    niche: str,
    parent_category: str,
    market: str,
    language: str,
    traffic_source_primary: str,
    page_goal: str,
    primary_metric: str,
    business_constraints: str | None = None,
    max_judge_retries: int = 0,  # kept for API compat; retries disabled (judge is informational)
) -> dict:
    """Full N4 pipeline: draft → judge → retry → persist.

    Returns dict with keys: context_id, status, verdict_history, latency_ms.
    """
    t0 = time.monotonic()

    chunks = await _retrieve_grounding_chunks(niche=niche)
    log.info("marketing:grounding niche=%s chunks=%d", niche, len(chunks))

    deps = DrafterDeps(
        niche=niche,
        parent_category=parent_category,
        market=market,
        language=language,
        traffic_source_primary=traffic_source_primary,
        page_goal=page_goal,
        primary_metric=primary_metric,
        brief=brief,
        business_constraints=business_constraints,
        retrieved_chunks=chunks,
    )

    ctx = await draft_marketing_context(deps)
    verdict = await judge_context(ctx)

    # Judge is informational — issues are surfaced to human for approval.
    # We do NOT retry on judge failure: the drafter's Pydantic validation
    # already catches hard structural errors; judge catches softer quality issues
    # that the human reviewer should decide on.
    final_verdict = verdict
    verdict_history = [verdict]

    # Persist to DB
    import json
    from sqlalchemy import text

    dump = ctx.model_dump(mode="json", warnings=False)

    from psycopg.types.json import Jsonb

    row = await session.execute(
        text("""
            INSERT INTO marketing_contexts (
                niche, parent_category, market, language,
                traffic_source_primary, page_goal, primary_metric,
                business_constraints, source_brief,
                personas, pain_points_aggregate, user_flow,
                audience_profile, channel_profile,
                grounding_chunks_used, judge_verdict,
                status, schema_version
            ) VALUES (
                :niche, :parent_category, :market, :language,
                :traffic_source_primary, :page_goal, :primary_metric,
                :business_constraints, :source_brief,
                :personas, :pain_points, :user_flow,
                :audience_profile, :channel_profile,
                :chunks, :verdict,
                'draft', 1
            )
            RETURNING id
        """),
        {
            "niche": ctx.niche,
            "parent_category": ctx.parent_category,
            "market": ctx.market,
            "language": ctx.language,
            "traffic_source_primary": ctx.traffic_source_primary,
            "page_goal": ctx.page_goal,
            "primary_metric": ctx.primary_metric,
            "business_constraints": ctx.business_constraints,
            "source_brief": ctx.source_brief,
            "personas": Jsonb(dump["personas"]),
            "pain_points": Jsonb(dump["pain_points_aggregate"]),
            "user_flow": Jsonb(dump["user_flow"]),
            "audience_profile": Jsonb(dump["audience_profile"]),
            "channel_profile": Jsonb(dump["channel_profile"]),
            "chunks": Jsonb(dump["grounding_chunks_used"]),
            "verdict": Jsonb(json.loads(final_verdict.model_dump_json())),
        },
    )
    context_id = row.scalar_one()
    await session.commit()

    latency_ms = int((time.monotonic() - t0) * 1000)
    log.info(
        "marketing:done context_id=%d passed=%s attempts=%d latency_ms=%d",
        context_id, final_verdict.passed, len(verdict_history), latency_ms,
    )

    return {
        "context_id": context_id,
        "status": "draft",
        "judge_passed": final_verdict.passed,
        "judge_issues": final_verdict.issues,
        "attempts": 1,
        "latency_ms": latency_ms,
    }


async def approve_context(*, session: AsyncSession, context_id: int) -> None:
    from sqlalchemy import text
    await session.execute(
        text("UPDATE marketing_contexts SET status='approved', updated_at=now() WHERE id=:id"),
        {"id": context_id},
    )
    await session.commit()


async def get_context(*, session: AsyncSession, context_id: int) -> dict | None:
    from sqlalchemy import text
    r = await session.execute(
        text("""
            SELECT id, niche, parent_category, market, language,
                   traffic_source_primary, page_goal, primary_metric,
                   source_brief, personas, pain_points_aggregate,
                   user_flow, audience_profile, channel_profile,
                   judge_verdict, status, created_at, updated_at
            FROM marketing_contexts WHERE id=:id
        """),
        {"id": context_id},
    )
    row = r.fetchone()
    if not row:
        return None
    return dict(zip(r.keys(), row))
