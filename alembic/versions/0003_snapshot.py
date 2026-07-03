"""Page Snapshot schema (N1).

Tables: page_snapshots, page_forms, validation_reports.

Revision ID: 0003_snapshot
Revises: 0002_knowledge_base
Create Date: 2026-04-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_snapshot"
down_revision: Union[str, None] = "0002_knowledge_base"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── page_snapshots ──
    op.create_table(
        "page_snapshots",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("project_id", sa.String(64), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "quality_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("meta_description", sa.Text(), nullable=True),
        sa.Column("desktop_screenshot_path", sa.Text(), nullable=True),
        sa.Column("mobile_screenshot_path", sa.Text(), nullable=True),
        sa.Column(
            "tech_stack",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_snapshots")),
    )
    op.create_index(op.f("ix_page_snapshots_project_id"), "page_snapshots", ["project_id"])
    op.create_index(
        "ix_page_snapshots_project_captured", "page_snapshots", ["project_id", "captured_at"]
    )

    # ── page_forms ──
    op.create_table(
        "page_forms",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("viewport", sa.String(16), nullable=False),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("method", sa.String(8), nullable=False, server_default="POST"),
        sa.Column("submit_text", sa.Text(), nullable=True),
        sa.Column(
            "fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
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
            name=op.f("fk_page_forms_snapshot_id_page_snapshots"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_forms")),
    )
    op.create_index(op.f("ix_page_forms_snapshot_id"), "page_forms", ["snapshot_id"])

    # ── validation_reports ──
    op.create_table(
        "validation_reports",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column(
            "flags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
            name=op.f("fk_validation_reports_snapshot_id_page_snapshots"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_validation_reports")),
    )
    op.create_index(
        op.f("ix_validation_reports_snapshot_id"), "validation_reports", ["snapshot_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_validation_reports_snapshot_id"), table_name="validation_reports")
    op.drop_table("validation_reports")
    op.drop_index(op.f("ix_page_forms_snapshot_id"), table_name="page_forms")
    op.drop_table("page_forms")
    op.drop_index("ix_page_snapshots_project_captured", table_name="page_snapshots")
    op.drop_index(op.f("ix_page_snapshots_project_id"), table_name="page_snapshots")
    op.drop_table("page_snapshots")
