"""PageContext — summary of a captured landing page, prompt-friendly.

Phase 2: bridges N1 (snapshot) + N2 (semantic) data into the drafter pipeline.
Agents that benefit from "seeing the page":
  - Conversion Architect → real friction inventory (not predicted), real test priorities
  - Voice & Message Strategist → tear down existing copy, find verbatim hooks

Loading strategy:
  - If DB available + snapshot_id present → fetch full data
  - If snapshot exists but no semantic_map → fall back to markdown-only context
  - If no snapshot at all → return None, agents work in brief-only mode

Graceful degradation is intentional: Phase 2 should NEVER block Phase 1's
working pipeline. Adding page context is value-add, not requirement.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

MAX_MARKDOWN_CHARS = 4000      # don't blow up agent context with full page
MAX_FORM_FIELDS_DISPLAY = 8


# ── Pydantic schema (what agents consume) ────────────────────────────────────

class PageContext(BaseModel):
    """A captured landing page summarized for LLM consumption.

    Designed to be small (a few hundred tokens), high-signal, and stable
    across the brief / niche. Not the raw HTML or full markdown — those
    blow up context and add noise.
    """

    # Identity
    url: str
    title: str | None = None
    meta_description: str | None = None

    # Existing on-page copy (the most valuable input for Voice & Message)
    visible_copy_excerpt: str = Field(
        ...,
        description="First ~4000 chars of clean markdown — the actual words on the page.",
    )

    # Form mechanics (most valuable input for Conversion Architect)
    forms_summary: list[str] = Field(
        default_factory=list,
        description=(
            "Plain-English summary of each form on the page. "
            "Format: '<viewport> form: <N> fields (<types>) — submit=\"<label>\"'."
        ),
    )

    # Semantic page elements (from N2 classifier)
    page_archetype: str | None = Field(
        None,
        description="N2 classification: lead_capture, ecom_product, content_article, etc.",
    )
    archetype_confidence: float | None = None
    detected_element_roles: list[str] = Field(
        default_factory=list,
        description="High-confidence semantic elements N2 found, e.g. ['hero_headline', 'primary_cta', 'trust_badge', 'lead_form']",
    )

    # Friction signals derived from the above
    friction_signals: list[str] = Field(
        default_factory=list,
        description=(
            "Heuristic friction indicators computed from forms + semantic. "
            "Examples: 'mobile form has 5+ fields', 'no visible phone number', "
            "'no trust badges detected', 'CTA copy is generic'."
        ),
    )

    # Tech context (for future cross-agent use)
    tech_stack: list[str] = Field(default_factory=list)

    # Meta
    snapshot_id: int
    viewport_used: str = Field(..., description="'desktop' or 'mobile' — which viewport this summary describes")

    def short_summary(self) -> str:
        """One-line summary for log messages."""
        return (
            f"snapshot={self.snapshot_id} url={self.url} "
            f"archetype={self.page_archetype or 'unknown'} "
            f"forms={len(self.forms_summary)} friction={len(self.friction_signals)}"
        )


# ── Loader ───────────────────────────────────────────────────────────────────

async def load_page_context(
    snapshot_id: int,
    *,
    session: AsyncSession,
    viewport: str = "desktop",
) -> PageContext | None:
    """Load + summarize a captured page from the DB.

    Returns None gracefully if the snapshot doesn't exist (so callers can
    fall back to brief-only mode without try/except gymnastics).
    """
    from ai_agent_system.db.models.semantic import SemanticMap
    from ai_agent_system.db.models.snapshot import PageForm, PageSnapshot
    from sqlalchemy import select

    snap = await session.get(PageSnapshot, snapshot_id)
    if snap is None:
        log.warning("page_context: snapshot_id=%s not found", snapshot_id)
        return None

    # Pull semantic map for this viewport (might be None if N2 didn't run)
    sm_q = await session.execute(
        select(SemanticMap).where(
            SemanticMap.snapshot_id == snapshot_id,
            SemanticMap.viewport == viewport,
        )
    )
    semantic_map = sm_q.scalar_one_or_none()

    # Pull forms for this viewport
    forms_q = await session.execute(
        select(PageForm).where(
            PageForm.snapshot_id == snapshot_id,
            PageForm.viewport == viewport,
        )
    )
    forms: list[PageForm] = list(forms_q.scalars().all())

    # ── Build markdown excerpt ──────────────────────────────────────────────
    md = (snap.markdown_desktop if viewport == "desktop" else snap.markdown_mobile) or ""
    md = md.strip()
    if len(md) > MAX_MARKDOWN_CHARS:
        md = md[:MAX_MARKDOWN_CHARS] + f"\n\n[...truncated, full was {len(md)} chars]"

    # ── Build form summaries ────────────────────────────────────────────────
    forms_summary: list[str] = []
    for f in forms:
        field_types = []
        for fld in (f.fields or [])[:MAX_FORM_FIELDS_DISPLAY]:
            t = fld.get("type") or fld.get("name") or "unknown"
            field_types.append(t)
        n = len(f.fields or [])
        more = f" (+{n - MAX_FORM_FIELDS_DISPLAY} more)" if n > MAX_FORM_FIELDS_DISPLAY else ""
        forms_summary.append(
            f"{f.viewport} form: {n} fields ({', '.join(field_types)}){more} — "
            f"submit={(f.submit_text or '?')!r}"
        )

    # ── Extract semantic elements (high-confidence only) ────────────────────
    archetype: str | None = None
    archetype_conf: float | None = None
    element_roles: list[str] = []
    if semantic_map:
        archetype = semantic_map.page_archetype
        archetype_conf = semantic_map.archetype_confidence
        for assignment in (semantic_map.assignments or []):
            if assignment.get("confidence", 0) >= 0.7:
                role = assignment.get("role")
                if role and role not in element_roles:
                    element_roles.append(role)

    # ── Compute friction signals ────────────────────────────────────────────
    # Pure heuristics — agents can override with their own analysis.
    friction: list[str] = []

    for f in forms:
        if f.viewport == "mobile" and len(f.fields or []) >= 4:
            friction.append(
                f"Mobile form has {len(f.fields)} fields — typical drop-off ~5-10% per field after 3"
            )
        if (f.submit_text or "").lower() in {"submit", "go", "send", "ok"}:
            friction.append(
                f"Form CTA copy is generic ({f.submit_text!r}) — specific value-prop CTAs convert ~25% better"
            )

    if "trust_badge" not in element_roles and "trust_signal" not in element_roles:
        friction.append("No trust signals (BBB, badges, certifications) detected by semantic analyzer")

    if "phone_number" not in element_roles and "click_to_call" not in element_roles:
        friction.append("No visible phone number / click-to-call detected — common for senior audiences")

    if archetype == "lead_capture" and len(forms) == 0:
        friction.append("Page archetype is lead_capture but no forms were extracted — possible JS-rendered form")

    # Tech stack as flat list
    tech_list: list[str] = []
    if isinstance(snap.tech_stack, dict):
        for category, items in snap.tech_stack.items():
            if isinstance(items, list):
                tech_list.extend(str(x) for x in items)
            elif items:
                tech_list.append(str(items))

    return PageContext(
        url=snap.url,
        title=snap.title,
        meta_description=snap.meta_description,
        visible_copy_excerpt=md or "(no markdown captured)",
        forms_summary=forms_summary,
        page_archetype=archetype,
        archetype_confidence=archetype_conf,
        detected_element_roles=element_roles,
        friction_signals=friction,
        tech_stack=tech_list,
        snapshot_id=snapshot_id,
        viewport_used=viewport,
    )


# ── Prompt-friendly serialization ────────────────────────────────────────────

def render_page_context_for_prompt(ctx: PageContext) -> str:
    """Format a PageContext block to inject into agent system prompts.

    Goal: dense, scannable, stable structure. Each section is optional —
    we only include fields that have signal.
    """
    lines: list[str] = []
    lines.append("<page_context>")
    lines.append(f"  URL: {ctx.url}")
    if ctx.title:
        lines.append(f"  Title: {ctx.title}")
    if ctx.meta_description:
        lines.append(f"  Meta description: {ctx.meta_description[:200]}")

    if ctx.page_archetype:
        conf = f" (confidence={ctx.archetype_confidence:.2f})" if ctx.archetype_confidence else ""
        lines.append(f"  Page archetype (N2 classifier): {ctx.page_archetype}{conf}")

    if ctx.detected_element_roles:
        lines.append(f"  Detected page elements: {', '.join(ctx.detected_element_roles)}")

    if ctx.forms_summary:
        lines.append(f"  Forms ({len(ctx.forms_summary)}):")
        for f in ctx.forms_summary:
            lines.append(f"    - {f}")

    if ctx.friction_signals:
        lines.append(f"  Heuristic friction signals (consider these in your analysis):")
        for s in ctx.friction_signals:
            lines.append(f"    - {s}")

    if ctx.tech_stack:
        lines.append(f"  Tech stack: {', '.join(ctx.tech_stack[:8])}")

    lines.append("")
    lines.append("  ----- VISIBLE COPY (markdown excerpt) -----")
    lines.append(ctx.visible_copy_excerpt)
    lines.append("  ----- END VISIBLE COPY -----")
    lines.append("</page_context>")
    return "\n".join(lines)
