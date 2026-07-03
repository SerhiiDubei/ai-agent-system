"""Pydantic models for Page Snapshot — N1.

PageSnapshot is the canonical output of the browser capture pipeline.
DualSnapshot wraps desktop + mobile pair.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class Viewport(str, Enum):
    DESKTOP = "desktop"
    MOBILE = "mobile"


class FormField(BaseModel):
    name: str
    type: str           # "email", "tel", "text", "select", "checkbox", ...
    label: str | None = None
    required: bool = False
    placeholder: str | None = None


class DetectedForm(BaseModel):
    action: str | None      # submit URL
    method: str = "POST"
    fields: list[FormField] = Field(default_factory=list)
    submit_text: str | None = None


class PageSnapshot(BaseModel):
    """Complete snapshot of a single URL at a given viewport.

    Produced by SnapshotProvider + post-processors (forms, tech, PII, quality).
    """

    url: str
    final_url: str              # after redirects
    viewport: Viewport
    fetched_at: float           # Unix timestamp

    html: str                   # raw post-JS HTML (PII-sanitized)
    markdown: str               # Firecrawl markdown (PII-sanitized)

    screenshot_path: str | None = None     # local filesystem path
    screenshot_size_bytes: int = 0

    title: str | None = None
    meta_description: str | None = None

    forms: list[DetectedForm] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)
    tech_stack: dict[str, list[str]] = Field(default_factory=dict)  # category → [tech]

    quality_score: float = 0.0          # 0..1
    quality_flags: list[str] = Field(default_factory=list)
    pii_redacted: bool = True

    provider_used: str = "firecrawl"    # "firecrawl" | "jina"


class DualSnapshot(BaseModel):
    """Desktop + mobile snapshot pair for a single URL."""

    url: str
    project_id: str | None = None
    desktop: PageSnapshot
    mobile: PageSnapshot
    captured_at: float

    @property
    def quality_score(self) -> float:
        """Average quality across both viewports."""
        return (self.desktop.quality_score + self.mobile.quality_score) / 2

    @property
    def is_acceptable(self) -> bool:
        """True if both viewports meet the minimum quality bar."""
        return self.desktop.quality_score >= 0.6 and self.mobile.quality_score >= 0.6
