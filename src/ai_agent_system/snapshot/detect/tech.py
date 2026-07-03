"""Tech stack detector via wappalyzer-next — N1.

Uses s0md3v/wappalyzer-next (PyPI: wappalyzer), NOT the archived
chorsley or scrapinghub forks. Fingerprints auto-loaded from live data.

Per N1 research: run on desktop HTML only (mobile UA returns same backend).
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_wap = None


def _get_wap():
    global _wap
    if _wap is None:
        try:
            from wappalyzer import Wappalyzer  # type: ignore[import]
            _wap = Wappalyzer()
        except ImportError:
            log.warning("wappalyzer not installed; tech detection disabled")
    return _wap


def detect_tech(
    url: str,
    html: str,
    headers: dict[str, str] | None = None,
) -> dict[str, list[str]]:
    """Detect technologies from URL + HTML + response headers.

    Args:
        url: Page URL (used for pattern matching against known URL patterns).
        html: Raw page HTML.
        headers: HTTP response headers (improves detection of CDN, server tech).

    Returns:
        Dict mapping category → list of technology names.
        Example: {"CMS": ["WordPress"], "Analytics": ["Google Analytics", "Facebook Pixel"]}
    """
    wap = _get_wap()
    if wap is None:
        return {}

    try:
        results = wap.analyze(url=url, html=html, headers=headers or {})
        out: dict[str, list[str]] = {}
        for tech, meta in results.items():
            categories = meta.get("categories") if isinstance(meta, dict) else ["Other"]
            for cat in (categories or ["Other"]):
                out.setdefault(cat, []).append(tech)
        return out
    except Exception as exc:
        log.warning("tech detection failed for %s: %s", url, exc)
        return {}
