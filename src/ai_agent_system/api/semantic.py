"""REST API for N2 semantic role mapping.

Endpoints:
  POST /api/v1/semantic/{snapshot_id}   — run classification (both viewports)
  GET  /api/v1/semantic/{snapshot_id}   — fetch stored results
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_agent_system.api.dependencies import get_db
from ai_agent_system.db.models.semantic import SemanticMap
from ai_agent_system.semantic.service import SemanticService

router = APIRouter()
_service = SemanticService()


class MapResponse(BaseModel):
    snapshot_id: int
    semantic_map_ids: dict[str, int]  # {"desktop": id, "mobile": id}
    viewports_mapped: int


class SemanticMapRecord(BaseModel):
    id: int
    snapshot_id: int
    viewport: str
    page_archetype: str
    archetype_confidence: float
    assignments: list[dict]
    notes: str | None
    model_used: str
    latency_ms: int


@router.post("/{snapshot_id}", response_model=MapResponse, status_code=201)
async def map_snapshot(
    snapshot_id: int,
    session: AsyncSession = Depends(get_db),
) -> MapResponse:
    """Run N2 semantic role classification for both viewports of a snapshot.

    Idempotent: calling again re-classifies and adds new rows (history preserved).
    Use GET to retrieve the most recent results.
    """
    try:
        ids = await _service.map_snapshot(session, snapshot_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    await session.commit()
    return MapResponse(
        snapshot_id=snapshot_id,
        semantic_map_ids=ids,
        viewports_mapped=len(ids),
    )


@router.get("/{snapshot_id}", response_model=list[SemanticMapRecord])
async def get_semantic_maps(
    snapshot_id: int,
    session: AsyncSession = Depends(get_db),
) -> list[SemanticMapRecord]:
    """Return all stored semantic maps for a snapshot (most recent first)."""
    rows = (
        await session.execute(
            select(SemanticMap)
            .where(SemanticMap.snapshot_id == snapshot_id)
            .order_by(SemanticMap.created_at.desc())
        )
    ).scalars().all()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No semantic maps for snapshot {snapshot_id}")

    return [
        SemanticMapRecord(
            id=r.id,
            snapshot_id=r.snapshot_id,
            viewport=r.viewport,
            page_archetype=r.page_archetype,
            archetype_confidence=r.archetype_confidence,
            assignments=r.assignments,
            notes=r.notes,
            model_used=r.model_used,
            latency_ms=r.latency_ms,
        )
        for r in rows
    ]
