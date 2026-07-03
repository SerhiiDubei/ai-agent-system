"""Snapshot API router — N1.

Endpoints:
  POST /          — capture a new dual-viewport snapshot
  GET  /{id}      — retrieve snapshot metadata
  GET  /{id}/quality — quality report for a snapshot
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ai_agent_system.api.dependencies import require_internal_key
from ai_agent_system.db.session import get_session
from ai_agent_system.snapshot.service import capture_dual, persist_snapshot

log = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_internal_key)])


def _get_provider(request: Request):
    provider = getattr(request.app.state, "snapshot_provider", None)
    if provider is None:
        raise HTTPException(status_code=503, detail="snapshot provider not initialized")
    return provider


def _get_fallback(request: Request):
    return getattr(request.app.state, "snapshot_fallback_provider", None)


# ── Models ────────────────────────────────────────────────────────────

class SnapshotRequest(BaseModel):
    url: str = Field(..., description="Target URL to snapshot")
    project_id: str | None = None
    wait_for_ms: int | None = Field(
        None,
        description="JS hydration wait in ms. Defaults to 2500.",
        ge=0,
        le=30_000,
    )


class SnapshotResponse(BaseModel):
    snapshot_id: int
    url: str
    quality_score: float
    quality_flags: dict
    acceptable: bool
    desktop_quality: float
    mobile_quality: float
    forms_detected: int
    tech_stack: dict


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post("", response_model=SnapshotResponse, status_code=201)
async def create_snapshot(
    body: SnapshotRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SnapshotResponse:
    """Capture a new dual-viewport (desktop + mobile) snapshot."""
    provider = _get_provider(request)
    fallback = _get_fallback(request)

    dual = await capture_dual(
        provider,
        body.url,
        project_id=body.project_id,
        wait_for_ms=body.wait_for_ms,
        fallback_provider=fallback,
    )

    snapshot_id = await persist_snapshot(session, dual)
    await session.commit()

    return SnapshotResponse(
        snapshot_id=snapshot_id,
        url=dual.url,
        quality_score=round(dual.quality_score, 3),
        quality_flags={
            "desktop": dual.desktop.quality_flags,
            "mobile": dual.mobile.quality_flags,
        },
        acceptable=dual.is_acceptable,
        desktop_quality=round(dual.desktop.quality_score, 3),
        mobile_quality=round(dual.mobile.quality_score, 3),
        forms_detected=len(dual.desktop.forms),
        tech_stack=dual.desktop.tech_stack,
    )


@router.get("/{snapshot_id}", response_model=dict)
async def get_snapshot(
    snapshot_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Return snapshot metadata by ID."""
    row = (
        await session.execute(
            text(
                """
                SELECT id, project_id, url, final_url, quality_score, quality_flags,
                       title, meta_description, tech_stack, captured_at
                FROM page_snapshots
                WHERE id = :id
                """
            ),
            {"id": snapshot_id},
        )
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"snapshot {snapshot_id} not found")

    return {
        "id": row.id,
        "project_id": row.project_id,
        "url": row.url,
        "final_url": row.final_url,
        "quality_score": row.quality_score,
        "quality_flags": row.quality_flags,
        "title": row.title,
        "meta_description": row.meta_description,
        "tech_stack": row.tech_stack,
        "captured_at": row.captured_at.isoformat() if row.captured_at else None,
    }


@router.get("/{snapshot_id}/quality", response_model=dict)
async def get_snapshot_quality(
    snapshot_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Return quality report + forms for a snapshot."""
    snap_row = (
        await session.execute(
            text("SELECT quality_score, quality_flags FROM page_snapshots WHERE id = :id"),
            {"id": snapshot_id},
        )
    ).fetchone()

    if snap_row is None:
        raise HTTPException(status_code=404, detail=f"snapshot {snapshot_id} not found")

    form_rows = (
        await session.execute(
            text(
                "SELECT viewport, action, method, submit_text, fields FROM page_forms WHERE snapshot_id = :id"
            ),
            {"id": snapshot_id},
        )
    ).fetchall()

    return {
        "snapshot_id": snapshot_id,
        "quality_score": snap_row.quality_score,
        "quality_flags": snap_row.quality_flags,
        "acceptable": snap_row.quality_score >= 0.6,
        "forms": [
            {
                "viewport": r.viewport,
                "action": r.action,
                "method": r.method,
                "submit_text": r.submit_text,
                "fields": r.fields,
            }
            for r in form_rows
        ],
    }
