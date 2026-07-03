"""Knowledge Base schema (N3).

Tables: kb_documents, kb_chunks.
Extensions: pgvector (vector), pg_trgm (trigram similarity).
Indexes: HNSW on embedding, GIN on tsv + niches + tags + trgm.

Revision ID: 0002_knowledge_base
Revises: 0001_llm_gateway
Create Date: 2026-04-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_knowledge_base"
down_revision: Union[str, None] = "0001_llm_gateway"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extensions ──
    # pgvector: must be installed in Postgres (included in pgvector/pgvector image).
    # pg_trgm: trigram similarity for fuzzy third leg of hybrid search.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── kb_documents ──
    op.create_table(
        "kb_documents",
        sa.Column("rel_path", sa.String(512), nullable=False),
        sa.Column("doc_id", sa.String(128), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column(
            "frontmatter",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("rel_path", name=op.f("pk_kb_documents")),
    )
    op.create_index(op.f("ix_kb_documents_doc_id"), "kb_documents", ["doc_id"])

    # ── kb_chunks ──
    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("rel_path", sa.String(512), nullable=False),
        sa.Column("doc_id", sa.String(128), nullable=False),
        sa.Column("section", sa.Text(), nullable=False, server_default=""),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("chunk_hash", sa.String(64), nullable=False),
        sa.Column("authority_tier", sa.SmallInteger(), nullable=False),
        sa.Column("authority_weight", sa.Float(), nullable=False),
        sa.Column("parent_category", sa.String(64), nullable=False),
        sa.Column(
            "niches",
            postgresql.ARRAY(sa.String(64)),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String(64)),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("source_url", sa.String(512), nullable=True),
        # vector(1536): pgvector type — requires CREATE EXTENSION vector above.
        sa.Column("embedding", sa.Text(), nullable=False),   # placeholder; altered below
        sa.Column("tsv", sa.Text(), nullable=True),          # placeholder; altered below
        sa.ForeignKeyConstraint(
            ["rel_path"],
            ["kb_documents.rel_path"],
            ondelete="CASCADE",
            name=op.f("fk_kb_chunks_rel_path_kb_documents"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kb_chunks")),
        sa.UniqueConstraint("rel_path", "ord", name="uq_kb_chunks_relpath_ord"),
    )

    # Alter columns to proper pgvector + tsvector types (SQLAlchemy doesn't have
    # native types for these, so we use raw DDL).
    op.execute("ALTER TABLE kb_chunks ALTER COLUMN embedding TYPE vector(1536) USING NULL::vector(1536)")
    op.execute("ALTER TABLE kb_chunks ALTER COLUMN embedding SET NOT NULL")
    op.execute("ALTER TABLE kb_chunks ALTER COLUMN tsv TYPE tsvector USING NULL::tsvector")

    # ── Scalar indexes ──
    op.create_index(op.f("ix_kb_chunks_rel_path"), "kb_chunks", ["rel_path"])
    op.create_index(op.f("ix_kb_chunks_doc_id"), "kb_chunks", ["doc_id"])
    op.create_index(op.f("ix_kb_chunks_parent_category"), "kb_chunks", ["parent_category"])
    op.create_index(op.f("ix_kb_chunks_kind"), "kb_chunks", ["kind"])
    op.create_index(
        "ix_kb_chunks_filters", "kb_chunks", ["parent_category", "kind", "authority_tier"]
    )

    # ── GIN indexes (array + tsvector + trigram) ──
    # These must be raw DDL because op.create_index doesn't support GIN with
    # these operator classes natively.
    op.execute("CREATE INDEX ix_kb_chunks_tsv    ON kb_chunks USING gin (tsv)")
    op.execute("CREATE INDEX ix_kb_chunks_niches ON kb_chunks USING gin (niches)")
    op.execute("CREATE INDEX ix_kb_chunks_tags   ON kb_chunks USING gin (tags)")
    op.execute(
        "CREATE INDEX ix_kb_chunks_text_trgm ON kb_chunks USING gin (text gin_trgm_ops)"
    )

    # ── HNSW index for ANN vector search ──
    # Per N3: m=16, ef_construction=64 — optimal at our scale (≤100K chunks).
    # IVFFlat is for >10M vectors; HNSW wins here on every dimension.
    op.execute(
        """
        CREATE INDEX ix_kb_chunks_embedding_hnsw
            ON kb_chunks USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_kb_chunks_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_kb_chunks_text_trgm")
    op.execute("DROP INDEX IF EXISTS ix_kb_chunks_tags")
    op.execute("DROP INDEX IF EXISTS ix_kb_chunks_niches")
    op.execute("DROP INDEX IF EXISTS ix_kb_chunks_tsv")
    op.drop_index("ix_kb_chunks_filters", table_name="kb_chunks")
    op.drop_index(op.f("ix_kb_chunks_kind"), table_name="kb_chunks")
    op.drop_index(op.f("ix_kb_chunks_parent_category"), table_name="kb_chunks")
    op.drop_index(op.f("ix_kb_chunks_doc_id"), table_name="kb_chunks")
    op.drop_index(op.f("ix_kb_chunks_rel_path"), table_name="kb_chunks")
    op.drop_table("kb_chunks")
    op.drop_index(op.f("ix_kb_documents_doc_id"), table_name="kb_documents")
    op.drop_table("kb_documents")
