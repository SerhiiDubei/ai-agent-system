"""ORM models for Page Snapshot pipeline — N1.

Tables:
- page_snapshots  — one row per dual-viewport capture session
- page_forms      — extracted forms per snapshot + viewport
- technical_profiles — tech stack per snapshot (denormalized from page_snapshots)
- validation_reports — quality assessment per snapshot

Per M3: screenshots stored on filesystem; path stored here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ai_agent_system.db.base import Base, TimestampMixin


class PageSnapshot(Base, TimestampMixin):
    """One row per dual-viewport capture (covers both desktop + mobile).

    markdown_desktop / markdown_mobile stored separately so agents can
    pick the relevant viewport for their analysis.
    """

    __tablename__ = "page_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    url: Mapped[str] = mapped_column(Text, nullable=False)
    final_url: Mapped[str] = mapped_column(Text, nullable=False)

    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quality_flags: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    desktop_screenshot_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mobile_screenshot_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Added in 0004_semantic: HTML + markdown for N2 DOM mark extraction
    html_desktop: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    html_mobile: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    markdown_desktop: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    markdown_mobile: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tech_stack: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_page_snapshots_project_captured", "project_id", "captured_at"),
    )


class PageForm(Base, TimestampMixin):
    """Extracted form per snapshot + viewport."""

    __tablename__ = "page_forms"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("page_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    viewport: Mapped[str] = mapped_column(String(16), nullable=False)  # "desktop" | "mobile"
    action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    method: Mapped[str] = mapped_column(String(8), nullable=False, default="POST")
    submit_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class ValidationReport(Base, TimestampMixin):
    """Quality assessment per snapshot. Separate table for audit trail."""

    __tablename__ = "validation_reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("page_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
