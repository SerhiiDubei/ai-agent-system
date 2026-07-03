"""Knowledge API router — N3.

Endpoints:
  POST /sync        — trigger ETL for whole vault or single file
  POST /retrieve    — hybrid retrieval (for agents + debugging)
  GET  /stats       — vault stats (document + chunk counts)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ai_agent_system.api.dependencies import require_internal_key
from ai_agent_system.db.session import get_session
from ai_agent_system.knowledge.etl import IngestResult
from ai_agent_system.knowledge.reranker import RetrievalCandidate
from ai_agent_system.knowledge.service import KnowledgeService
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_internal_key)])


def _get_knowledge_service(request: Request) -> KnowledgeService:
    """Pull KnowledgeService from app state (mounted at startup)."""
    svc: KnowledgeService | None = getattr(request.app.state, "knowledge_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="knowledge service not initialized")
    return svc


# ── Request / Response models ─────────────────────────────────────────

class SyncRequest(BaseModel):
    rel_path: str | None = Field(
        None,
        description="Relative path of a single file to sync. Omit for full vault scan.",
    )


class SyncResponse(BaseModel):
    results: list[dict]
    total_files: int
    chunks_added: int
    chunks_reused: int
    errors: int


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=3)
    parent_category: str | None = None
    niche: str | None = None
    kind: str | None = None
    top_k: int = Field(8, ge=1, le=30)


class RetrieveResponse(BaseModel):
    query: str
    results: list[dict]


class StatsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    by_tier: dict[str, int]
    by_category: dict[str, int]


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post("/sync", response_model=SyncResponse)
async def sync(
    body: SyncRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SyncResponse:
    """Trigger ETL for the vault (or a single file).

    Uses the vault_root from app settings. Safe to call repeatedly —
    unchanged files are skipped via hash-diff.
    """
    svc = _get_knowledge_service(request)
    vault_root: Path = request.app.state.vault_root

    if body.rel_path:
        target = vault_root / body.rel_path
        if not target.exists():
            raise HTTPException(status_code=404, detail=f"file not found: {body.rel_path}")
        raw_results = [await svc.ingest_file(session, target, vault_root)]
    else:
        raw_results = await svc.ingest_vault(session, vault_root)

    await session.commit()

    return SyncResponse(
        results=[
            {
                "rel_path": r.rel_path,
                "chunks_added": r.chunks_added,
                "chunks_reused": r.chunks_reused,
                "skipped": r.skipped_file,
                "error": r.validation_error,
            }
            for r in raw_results
        ],
        total_files=len(raw_results),
        chunks_added=sum(r.chunks_added for r in raw_results),
        chunks_reused=sum(r.chunks_reused for r in raw_results),
        errors=sum(1 for r in raw_results if r.validation_error),
    )


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(
    body: RetrieveRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RetrieveResponse:
    """Hybrid knowledge retrieval.

    Intended for agent context building and manual debugging.
    """
    svc = _get_knowledge_service(request)

    candidates = await svc.search(
        session,
        body.query,
        parent_category=body.parent_category,
        niche=body.niche,
        kind=body.kind,
        top_k=body.top_k,
    )

    return RetrieveResponse(
        query=body.query,
        results=[
            {
                "id": c.id,
                "doc_id": c.doc_id,
                "section": c.section,
                "text": c.text[:300] + "..." if len(c.text) > 300 else c.text,
                "kind": c.kind,
                "authority_tier": c.authority_tier,
                "niches": c.niches,
                "final_score": round(c.final_score, 4),
                "rrf_norm": round(c.rrf_norm, 4),
                "authority_weight": c.authority_weight,
            }
            for c in candidates
        ],
    )


@router.get("/stats", response_model=StatsResponse)
async def stats(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StatsResponse:
    """Return vault index statistics."""
    total_docs_row = (
        await session.execute(text("SELECT COUNT(*) FROM kb_documents"))
    ).scalar_one()

    total_chunks_row = (
        await session.execute(text("SELECT COUNT(*) FROM kb_chunks"))
    ).scalar_one()

    tier_rows = (
        await session.execute(
            text(
                "SELECT authority_tier, COUNT(*) AS cnt FROM kb_chunks GROUP BY authority_tier"
            )
        )
    ).fetchall()

    cat_rows = (
        await session.execute(
            text(
                "SELECT parent_category, COUNT(*) AS cnt FROM kb_chunks GROUP BY parent_category"
            )
        )
    ).fetchall()

    return StatsResponse(
        total_documents=int(total_docs_row),
        total_chunks=int(total_chunks_row),
        by_tier={f"tier_{r[0]}": int(r[1]) for r in tier_rows},
        by_category={r[0]: int(r[1]) for r in cat_rows},
    )
