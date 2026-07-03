"""Snapshot service — dual capture orchestrator — N1.

Per N1 research: desktop + mobile run as TWO PARALLEL Firecrawl calls.
NOT a single call with viewport switch (hydration timing issue).

Post-processing pipeline per snapshot:
  1. PII sanitize HTML + markdown
  2. Extract forms (desktop + mobile)
  3. Detect tech stack (desktop only — mobile UA returns same backend)
  4. Score quality
  5. Persist to DB + filesystem
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ai_agent_system.config import settings
from ai_agent_system.snapshot.detect.forms import extract_forms
from ai_agent_system.snapshot.detect.tech import detect_tech
from ai_agent_system.snapshot.models import DualSnapshot, PageSnapshot, Viewport
from ai_agent_system.snapshot.providers.base import SnapshotProvider
from ai_agent_system.snapshot.sanitize.pii import sanitize_html_keep_structure, sanitize_text
from ai_agent_system.snapshot.validate.quality import score_snapshot

log = logging.getLogger(__name__)


def _post_process(snap: PageSnapshot, *, is_desktop: bool) -> PageSnapshot:
    """In-place post-processing: PII → forms → tech (desktop) → quality."""
    snap.html = sanitize_html_keep_structure(snap.html)
    snap.markdown = sanitize_text(snap.markdown, on_page=True)

    snap.forms = extract_forms(snap.html, snap.url)

    if is_desktop:
        snap.tech_stack = detect_tech(snap.url, snap.html, headers={})

    snap.quality_score, snap.quality_flags = score_snapshot(snap)
    snap.pii_redacted = True
    return snap


async def capture_dual(
    provider: SnapshotProvider,
    url: str,
    *,
    project_id: str | None = None,
    wait_for_ms: int | None = None,
    fallback_provider: SnapshotProvider | None = None,
) -> DualSnapshot:
    """Capture desktop + mobile snapshots in parallel.

    Args:
        provider: Primary snapshot provider (Firecrawl).
        url: Target URL.
        project_id: Optional tag for cost/audit attribution.
        wait_for_ms: JS hydration wait; defaults to Firecrawl's own default.
        fallback_provider: Jina or another provider if primary fails.

    Returns:
        DualSnapshot with both viewports post-processed.
    """
    async def _safe_snapshot(vp: Viewport) -> PageSnapshot:
        try:
            return await provider.snapshot(url, viewport=vp, wait_for_ms=wait_for_ms)
        except Exception as exc:
            log.error("primary provider failed for %s (%s): %s", url, vp.value, exc)
            if fallback_provider is not None:
                log.warning("falling back to %s for %s (%s)", fallback_provider.name, url, vp.value)
                return await fallback_provider.snapshot(url, viewport=vp)
            raise

    desktop_snap, mobile_snap = await asyncio.gather(
        _safe_snapshot(Viewport.DESKTOP),
        _safe_snapshot(Viewport.MOBILE),
    )

    desktop_snap = _post_process(desktop_snap, is_desktop=True)
    mobile_snap = _post_process(mobile_snap, is_desktop=False)
    # Mobile gets tech_stack from desktop (same backend)
    mobile_snap.tech_stack = desktop_snap.tech_stack

    dual = DualSnapshot(
        url=url,
        project_id=project_id,
        desktop=desktop_snap,
        mobile=mobile_snap,
        captured_at=time.time(),
    )

    log.info(
        "dual snapshot complete: %s — quality desktop=%.2f mobile=%.2f acceptable=%s",
        url,
        dual.desktop.quality_score,
        dual.mobile.quality_score,
        dual.is_acceptable,
    )
    return dual


async def persist_snapshot(
    session: AsyncSession,
    dual: DualSnapshot,
) -> int:
    """Persist DualSnapshot to DB. Returns page_snapshots.id."""
    from sqlalchemy import text

    result = await session.execute(
        text(
            """
            INSERT INTO page_snapshots
                (project_id, url, final_url, quality_score, quality_flags,
                 title, meta_description, desktop_screenshot_path,
                 mobile_screenshot_path, html_desktop, html_mobile,
                 markdown_desktop, markdown_mobile, tech_stack, captured_at)
            VALUES
                (:project_id, :url, :final_url, :quality_score,
                 CAST(:quality_flags AS jsonb), :title, :meta_description,
                 :desktop_screenshot_path, :mobile_screenshot_path,
                 :html_desktop, :html_mobile, :markdown_desktop, :markdown_mobile,
                 CAST(:tech_stack AS jsonb), to_timestamp(:captured_at))
            RETURNING id
            """
        ),
        {
            "project_id": dual.project_id,
            "url": dual.url,
            "final_url": dual.desktop.final_url,
            "quality_score": dual.quality_score,
            "quality_flags": _flags_json(dual),
            "title": dual.desktop.title,
            "meta_description": dual.desktop.meta_description,
            "desktop_screenshot_path": dual.desktop.screenshot_path,
            "mobile_screenshot_path": dual.mobile.screenshot_path,
            "html_desktop": dual.desktop.html,
            "html_mobile": dual.mobile.html,
            "markdown_desktop": dual.desktop.markdown,
            "markdown_mobile": dual.mobile.markdown,
            "tech_stack": _tech_json(dual.desktop.tech_stack),
            "captured_at": dual.captured_at,
        },
    )
    row = result.fetchone()
    snapshot_id = int(row[0])

    # Persist forms (desktop)
    for form in dual.desktop.forms:
        await session.execute(
            text(
                """
                INSERT INTO page_forms
                    (snapshot_id, viewport, action, method, submit_text, fields)
                VALUES
                    (:snapshot_id, 'desktop', :action, :method, :submit_text,
                     CAST(:fields AS jsonb))
                """
            ),
            {
                "snapshot_id": snapshot_id,
                "action": form.action,
                "method": form.method,
                "submit_text": form.submit_text,
                "fields": _fields_json(form.fields),
            },
        )

    log.debug("persisted snapshot id=%d for %s", snapshot_id, dual.url)
    return snapshot_id


def _flags_json(dual: DualSnapshot) -> str:
    import json
    return json.dumps({
        "desktop": dual.desktop.quality_flags,
        "mobile": dual.mobile.quality_flags,
    })


def _tech_json(tech_stack: dict) -> str:
    import json
    return json.dumps(tech_stack)


def _fields_json(fields: list) -> str:
    import json
    return json.dumps([f.model_dump() for f in fields])
