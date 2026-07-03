"""Semantic role maps (N2) + HTML/markdown columns for page_snapshots.

Why add html_desktop/html_mobile to page_snapshots:
  N2 needs the sanitized HTML that N1 already captured to extract DOM marks
  for Set-of-Mark prompting.  Re-fetching is non-reproducible.
  Storing in DB avoids a separate filesystem artefact for relatively small
  HTML payloads (typical landing page: 200–800 KB).

Revision ID: 0004_semantic
Revises: 0003_snapshot
Create Date: 2026-04-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_semantic"
down_revision: Union[str, None] = "0003_snapshot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extend page_snapshots with HTML + markdown storage ──
    op.add_column("page_snapshots", sa.Column("html_desktop", sa.Text(), nullable=True))
    op.add_column("page_snapshots", sa.Column("html_mobile", sa.Text(), nullable=True))
    op.add_column("page_snapshots", sa.Column("markdown_desktop", sa.Text(), nullable=True))
    op.add_column("page_snapshots", sa.Column("markdown_mobile", sa.Text(), nullable=True))

    # ── semantic_maps ──
    op.create_table(
        "semantic_maps",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("viewport", sa.String(16), nullable=False),
        sa.Column("page_archetype", sa.String(64), nullable=False),
        sa.Column("archetype_confidence", sa.Float(), nullable=False),
        sa.Column(
            "assignments",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("model_used", sa.String(128), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["page_snapshots.id"],
            ondelete="CASCADE",
            name=op.f("fk_semantic_maps_snapshot_id_page_snapshots"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_semantic_maps")),
    )
    op.create_index(op.f("ix_semantic_maps_snapshot_id"), "semantic_maps", ["snapshot_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_semantic_maps_snapshot_id"), table_name="semantic_maps")
    op.drop_table("semantic_maps")

    op.drop_column("page_snapshots", "markdown_mobile")
    op.drop_column("page_snapshots", "markdown_desktop")
    op.drop_column("page_snapshots", "html_mobile")
    op.drop_column("page_snapshots", "html_desktop")
