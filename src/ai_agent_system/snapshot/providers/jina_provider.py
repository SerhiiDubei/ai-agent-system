"""Jina Reader emergency fallback — N1.

Text-only fallback when Firecrawl is down. No screenshots, no forms.
Per N1: quality_score capped at 0.3 (text-only fallback penalty).
"""

from __future__ import annotations

import logging
import time

import httpx

from ai_agent_system.snapshot.models import PageSnapshot, Viewport
from ai_agent_system.snapshot.providers.base import SnapshotProvider

log = logging.getLogger(__name__)

JINA_BASE = "https://r.jina.ai/"


class JinaReaderProvider(SnapshotProvider):
    name = "jina"

    def __init__(self, api_key: str | None = None) -> None:
        self._headers = {"Accept": "text/markdown", "X-Return-Format": "markdown"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"

    async def snapshot(
        self,
        url: str,
        viewport: Viewport = Viewport.DESKTOP,
        wait_for_ms: int | None = None,
        actions: list[dict] | None = None,
    ) -> PageSnapshot:
        log.warning("using Jina fallback for %s (no screenshot, no forms)", url)
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(JINA_BASE + url, headers=self._headers)
            r.raise_for_status()

        markdown = r.text

        # Extract title from first H1 in Jina markdown if available
        title: str | None = None
        for line in markdown.splitlines()[:10]:
            if line.startswith("# "):
                title = line[2:].strip()
                break

        return PageSnapshot(
            url=url,
            final_url=url,
            viewport=viewport,
            fetched_at=time.time(),
            html="",
            markdown=markdown,
            title=title,
            quality_score=0.3,
            quality_flags=["fallback:jina", "no_screenshot", "no_forms"],
            provider_used="jina",
        )
