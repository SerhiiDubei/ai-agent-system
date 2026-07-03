"""Snapshot quality validator — N1.

Scores a PageSnapshot 0..1 based on heuristic checks.
Low score → flag for human review, don't pass to agents.

Per N1: quality_score < 0.6 = unacceptable (DualSnapshot.is_acceptable).
"""

from __future__ import annotations

from ai_agent_system.snapshot.models import PageSnapshot

MIN_HTML_BYTES = 5_000
MIN_MARKDOWN_CHARS = 300
MIN_SCREENSHOT_BYTES = 5_000

# Cloudflare / Datadome challenge fingerprints
_BOT_MARKERS = (
    "just a moment",
    "cf-challenge-running",
    "datadome-captcha",
    "enable javascript",
    "ray id",
    "checking if the site connection is secure",
)

# Lead-gen conversion signals — at least one expected on a real LP
_CTA_SIGNALS = (
    "get a quote",
    "click here",
    "free estimate",
    "call now",
    "schedule",
    "request",
    "get started",
    "learn more",
    "contact us",
    "sign up",
    "zip",
    "submit",
)


def score_snapshot(snap: PageSnapshot) -> tuple[float, list[str]]:
    """Compute quality_score ∈ [0, 1] and quality_flags for a snapshot.

    Returns:
        (score, flags) — caller should set snap.quality_score and snap.quality_flags.
    """
    flags: list[str] = []
    score = 1.0

    if len(snap.html) < MIN_HTML_BYTES:
        flags.append("html_too_short")
        score -= 0.35

    if len(snap.markdown) < MIN_MARKDOWN_CHARS:
        flags.append("markdown_too_short")
        score -= 0.25

    if snap.screenshot_size_bytes > 0 and snap.screenshot_size_bytes < MIN_SCREENSHOT_BYTES:
        flags.append("screenshot_blank_or_tiny")
        score -= 0.30
    elif snap.screenshot_path is None and snap.provider_used != "jina":
        flags.append("no_screenshot")
        score -= 0.20

    if not snap.title:
        flags.append("no_title")
        score -= 0.10

    html_lower = snap.html.lower()

    if any(m in html_lower for m in _BOT_MARKERS):
        flags.append("bot_challenge_detected")
        score -= 0.50

    # Lead-gen pages should have at least one CTA signal
    markdown_lower = snap.markdown.lower()
    combined = html_lower + " " + markdown_lower
    if not snap.forms and not any(sig in combined for sig in _CTA_SIGNALS):
        flags.append("no_form_or_cta_detected")
        score -= 0.10

    return max(0.0, min(1.0, score)), flags
