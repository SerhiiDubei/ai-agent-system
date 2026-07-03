"""ORM models для Knowledge Base — N3.

Tables:
- kb_documents — one row per Obsidian note (hash + frontmatter snapshot)
- kb_chunks    — one row per chunk of a note (embedding + tsvector for hybrid search)

Note: tsv column is NEVER set by Python — it's always computed via
to_tsvector('english', text) inside raw SQL INSERT. Defined here for
SQLAlchemy to know about it when querying.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from ai_agent_system.db.base import Base

EMBEDDING_DIM = 1536


class KbDocument(Base):
    """One row per Obsidian note file.

    rel_path is the primary key — it's the path relative to vault root,
    e.g. "01_Patterns/home_improvement/walk_in_tub_trust_blocks.md".

    file_hash is SHA-256 of the raw file bytes. ETL skips re-embedding
    when hash matches (per N3 hash-diff pattern).
    """

    __tablename__ = "kb_documents"

    rel_path: Mapped[str] = mapped_column(String(512), primary_key=True)
    doc_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    frontmatter: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class KbChunk(Base):
    """One row per text chunk of an Obsidian note.

    Per N3 research:
    - Per-H2 chunking with doc-title prefix
    - HNSW index (m=16, ef_construction=64) — NOT IVFFlat
    - tsvector for BM25-like full-text leg of hybrid search
    - authority_weight stored as column, blended at retrieval time (NOT in vector space)
    - niches / tags as TEXT[] for gin-indexed filtering
    """

    __tablename__ = "kb_chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # ── Document link ──
    rel_path: Mapped[str] = mapped_column(
        String(512),
        ForeignKey("kb_documents.rel_path", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doc_id: Mapped[str] = mapped_column(String(128), nullable=False)

    # ── Chunk identity ──
    section: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    ord: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # ── Authority (per N3: stored as column, blended at re-rank) ──
    authority_tier: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    authority_weight: Mapped[float] = mapped_column(Float, nullable=False)

    # ── Filterable metadata ──
    parent_category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    niches: Mapped[list[str]] = mapped_column(ARRAY(String(64)), nullable=False, default=list)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(64)), nullable=False, default=list)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # ── Vector + full-text ──
    embedding: Mapped[list] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    # tsv is always set by DB via to_tsvector(); Python never writes it directly.
    tsv: Mapped[Optional[object]] = mapped_column(TSVECTOR, nullable=True)

    __table_args__ = (
        UniqueConstraint("rel_path", "ord", name="uq_kb_chunks_relpath_ord"),
        # Compound filter index — parent_category + kind + authority_tier
        Index("ix_kb_chunks_filters", "parent_category", "kind", "authority_tier"),
    )
    # HNSW + GIN indexes are created via raw DDL in the Alembic migration
    # (SQLAlchemy doesn't have a native HNSW index type).
