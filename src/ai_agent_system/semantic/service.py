"""SemanticService — N2 orchestration layer.

Loads a persisted snapshot from DB, runs semantic classification for both
viewports, and writes results to semantic_maps.

Why the service reads html from DB instead of re-fetching:
  Reproducibility — the same HTML that was captured and sanitized in N1
  must drive the DOM marks.  Re-fetching would give a different page state.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ai_agent_system.db.models.semantic import SemanticMap
from ai_agent_system.db.models.snapshot import PageSnapshot
from ai_agent_system.semantic.classifier import classify_snapshot
from ai_agent_system.semantic.extractor import extract_dom_marks
from ai_agent_system.semantic.models import DomMark
from ai_agent_system.semantic.som import render_som

log = logging.getLogger(__name__)

# (viewport_label, screenshot_path_attr, html_attr, markdown_attr)
_VIEWPORTS = [
    ("desktop", "desktop_screenshot_path", "html_desktop", "markdown_desktop"),
    ("mobile", "mobile_screenshot_path", "html_mobile", "markdown_mobile"),
]


class SemanticService:
    async def map_snapshot(
        self,
        session: AsyncSession,
        snapshot_id: int,
    ) -> dict[str, int]:
        """Classify both viewports of ``snapshot_id``.

        Returns ``{"desktop": semantic_map_id, "mobile": semantic_map_id}``.
        Missing screenshots or HTML degrade gracefully (viewport skipped with warning).
        Raises ``ValueError`` if snapshot_id not found.
        """
        snap: PageSnapshot | None = await session.get(PageSnapshot, snapshot_id)
        if snap is None:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        results: dict[str, int] = {}

        for viewport, ss_attr, html_attr, md_attr in _VIEWPORTS:
            screenshot_path: str | None = getattr(snap, ss_attr, None)
            html: str = getattr(snap, html_attr, None) or ""
            markdown: str = getattr(snap, md_attr, None) or ""

            if not screenshot_path:
                log.warning(
                    "semantic:skip viewport=%s snapshot_id=%s reason=no_screenshot_path",
                    viewport,
                    snapshot_id,
                )
                continue

            path = Path(screenshot_path)
            if not path.exists():
                log.warning(
                    "semantic:skip viewport=%s snapshot_id=%s reason=screenshot_file_missing path=%s",
                    viewport,
                    snapshot_id,
                    path,
                )
                continue

            screenshot_bytes = path.read_bytes()

            marks: list[DomMark] = extract_dom_marks(html) if html else []
            if not marks:
                log.warning(
                    "semantic:no_dom_marks viewport=%s snapshot_id=%s — classifying from screenshot only",
                    viewport,
                    snapshot_id,
                )

            annotated = render_som(screenshot_bytes, marks)

            t0 = time.monotonic()
            sem_map, model_used = await classify_snapshot(
                viewport=viewport,
                url=snap.url,
                markdown=markdown,
                marks=marks,
                screenshot_bytes=annotated,
            )
            latency_ms = int((time.monotonic() - t0) * 1000)

            orm_row = SemanticMap(
                snapshot_id=snapshot_id,
                viewport=viewport,
                page_archetype=sem_map.page_archetype,
                archetype_confidence=sem_map.archetype_confidence,
                assignments=sem_map.model_dump()["assignments"],
                notes=sem_map.notes,
                model_used=model_used,
                latency_ms=latency_ms,
            )
            session.add(orm_row)
            await session.flush()
            results[viewport] = orm_row.id

            log.info(
                "semantic:mapped snapshot_id=%s viewport=%s archetype=%s conf=%.2f marks=%d latency_ms=%d model=%s",
                snapshot_id,
                viewport,
                sem_map.page_archetype,
                sem_map.archetype_confidence,
                len(marks),
                latency_ms,
                model_used,
            )

        return results
