"""ORM model for Marketing Contexts — N4."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ai_agent_system.db.base import Base, TimestampMixin


class MarketingContextModel(Base, TimestampMixin):
    __tablename__ = "marketing_contexts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")  # draft | approved | archived

    niche: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    parent_category: Mapped[str] = mapped_column(String(128), nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")

    traffic_source_primary: Mapped[str] = mapped_column(String(32), nullable=False)
    page_goal: Mapped[str] = mapped_column(String(32), nullable=False)
    primary_metric: Mapped[str] = mapped_column(String(64), nullable=False)
    business_constraints: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    source_brief: Mapped[str] = mapped_column(Text, nullable=False)

    personas: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    pain_points_aggregate: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    user_flow: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    audience_profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    channel_profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    grounding_chunks_used: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    judge_verdict: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
