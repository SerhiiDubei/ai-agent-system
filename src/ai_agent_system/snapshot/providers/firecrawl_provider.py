"""Firecrawl provider — primary snapshot backend — N1.

Per N1 research:
- Two separate calls for desktop + mobile (NOT viewport switch)
- wait_for=2500ms floor for JS hydration
- Retry on network errors only (not 4xx/5xx)
- Screenshots stored to local filesystem (MVP), path returned in snapshot
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from pathlib import Path

import httpx
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from ai_agent_system.snapshot.models import PageSnapshot, Viewport
from ai_agent_system.snapshot.providers.base import SnapshotProvider

log = logging.getLogger(__name__)

RETRYABLE = (httpx.HTTPError, asyncio.TimeoutError, ConnectionError)
DEFAULT_WAIT_MS = 2500      # minimum JS hydration buffer


class FirecrawlProvider(SnapshotProvider):
    name = "firecrawl"

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout_s: float = 60.0,
        screenshot_dir: Path | None = None,
    ) -> None:
        from firecrawl import AsyncV1FirecrawlApp  # type: ignore[import]

        self._client = AsyncV1FirecrawlApp(
            api_key=api_key,
            api_url=base_url or "https://api.firecrawl.dev",
        )
        self._timeout_s = timeout_s
        self._screenshot_dir = screenshot_dir or Path("./storage/screenshots")
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)

    async def _download_screenshot(self, screenshot_url: str, url: str, viewport: Viewport) -> tuple[str | None, int]:
        """Download screenshot from Firecrawl GCS URL and save to disk."""
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.get(screenshot_url, follow_redirects=True)
                r.raise_for_status()
                screenshot_bytes = r.content
            name = hashlib.sha256(url.encode()).hexdigest()[:16]
            fname = f"{name}_{viewport.value}_{int(time.time())}.png"
            fpath = self._screenshot_dir / fname
            fpath.write_bytes(screenshot_bytes)
            log.debug("screenshot saved: %s (%d bytes)", fpath, len(screenshot_bytes))
            return str(fpath), len(screenshot_bytes)
        except Exception as exc:
            log.warning("screenshot download failed: %s", exc)
            return None, 0

    async def snapshot(
        self,
        url: str,
        viewport: Viewport = Viewport.DESKTOP,
        wait_for_ms: int | None = None,
        actions: list[dict] | None = None,
    ) -> PageSnapshot:
        wait_ms = max(wait_for_ms or DEFAULT_WAIT_MS, DEFAULT_WAIT_MS)

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential_jitter(initial=2, max=20),
            retry=retry_if_exception_type(RETRYABLE),
            before_sleep=before_sleep_log(log, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                doc = await self._client.scrape_url(
                    url=url,
                    formats=["markdown", "html", "screenshot@fullPage", "links"],
                    mobile=(viewport == Viewport.MOBILE),
                    wait_for=wait_ms,
                    timeout=int(self._timeout_s * 1000),
                    only_main_content=False,
                )

        screenshot_path: str | None = None
        screenshot_size = 0
        raw_screenshot: str | None = doc.screenshot if doc else None
        if raw_screenshot:
            # Firecrawl Cloud returns a signed GCS URL, not base64
            if raw_screenshot.startswith("http"):
                screenshot_path, screenshot_size = await self._download_screenshot(
                    raw_screenshot, url, viewport
                )
            elif raw_screenshot.startswith("data:"):
                import base64
                b64_data = raw_screenshot.split(",", 1)[1]
                try:
                    screenshot_bytes = base64.b64decode(b64_data)
                    name = hashlib.sha256(url.encode()).hexdigest()[:16]
                    fname = f"{name}_{viewport.value}_{int(time.time())}.png"
                    fpath = self._screenshot_dir / fname
                    fpath.write_bytes(screenshot_bytes)
                    screenshot_path = str(fpath)
                    screenshot_size = len(screenshot_bytes)
                except Exception as exc:
                    log.warning("screenshot base64 decode failed: %s", exc)

        meta: dict = {}
        if doc and doc.metadata:
            meta = doc.metadata if isinstance(doc.metadata, dict) else {}

        image_urls = [
            img for img in (doc.links or [])
            if isinstance(img, str) and any(
                img.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg")
            )
        ]

        return PageSnapshot(
            url=url,
            final_url=meta.get("sourceURL") or meta.get("url") or url,
            viewport=viewport,
            fetched_at=time.time(),
            html=(doc.html or "") if doc else "",
            markdown=(doc.markdown or "") if doc else "",
            screenshot_path=screenshot_path,
            screenshot_size_bytes=screenshot_size,
            title=meta.get("title") or (doc.title if doc else None),
            meta_description=meta.get("description") or (doc.description if doc else None),
            image_urls=image_urls,
            provider_used="firecrawl",
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(f"{self._client.api_url.rstrip('/')}/v1/health")
                return r.status_code == 200
        except Exception:
            return False
