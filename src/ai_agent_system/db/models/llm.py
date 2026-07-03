"""ORM models для LLM gateway — N10.

Tables:
- llm_calls — one row per LLM call (canonical cost source of truth)
- llm_daily_rollup — pre-aggregated daily totals per operation (UPSERT pattern)
- kill_switch_state — single-row table for global LLM kill switch
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ai_agent_system.db.base import Base, TimestampMixin


class LlmCall(Base, TimestampMixin):
    """Canonical record per LLM call. Source of truth for cost.

    Per N10 research:
    - Capture model_used (resolved після fallback) and model_requested separately
    - openrouter_generation_id для re-query reconciliation
    - trace_id links to LangSmith trace
    """

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Routing context ──
    operation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # ── Model ──
    model_requested: Mapped[str] = mapped_column(String(128), nullable=False)
    model_used: Mapped[str] = mapped_column(String(128), nullable=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # ── Usage / cost ──
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── External refs (per N10: re-query OpenRouter generation для reconciliation) ──
    openrouter_generation_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True
    )
    trace_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    # ── Status ──
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="success")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Extras ──
    extras: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_llm_calls_operation_created", "operation_id", "created_at"),
        Index("ix_llm_calls_project_created", "project_id", "created_at"),
    )


class LlmDailyRollup(Base):
    """Pre-aggregated daily totals per (date, operation_id).

    Per N10: UPSERT pattern (`ON CONFLICT DO UPDATE`) inside same transaction
    as `llm_calls` insert. Read-side queries для daily summary fast.
    """

    __tablename__ = "llm_daily_rollup"

    rollup_date: Mapped[date] = mapped_column(Date, nullable=False)
    operation_id: Mapped[str] = mapped_column(String(128), nullable=False)

    total_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (PrimaryKeyConstraint("rollup_date", "operation_id"),)


class KillSwitchState(Base):
    """Single-row table (id=1 always) для global LLM kill switch.

    Per N10:
    - is_active=True → reject all NEW LLM calls
    - In-flight calls продовжують (no cancel — corrupted state)
    - revision bumped on every change для cache invalidation logic
    """

    __tablename__ = "kill_switch_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # always 1
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    engaged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    engaged_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
