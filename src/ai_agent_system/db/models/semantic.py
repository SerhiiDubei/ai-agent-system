"""ORM model for semantic role maps — N2.

One row per (snapshot_id, viewport).  The full list of RoleAssignment objects
is stored as JSONB — normalizing into a separate assignments table would add
complexity without query benefits at this scale.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ai_agent_system.db.base import Base, TimestampMixin


class SemanticMap(Base, TimestampMixin):
    """One semantic-role classification result for a single snapshot viewport."""

    __tablename__ = "semantic_maps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("page_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    viewport: Mapped[str] = mapped_column(String(16), nullable=False)  # "desktop" | "mobile"

    page_archetype: Mapped[str] = mapped_column(String(64), nullable=False)
    archetype_confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # List of RoleAssignment dicts: [{mark_id, role, confidence, rationale, bbox?}, ...]
    assignments: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    model_used: Mapped[str] = mapped_column(String(128), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
