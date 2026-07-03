"""0005 — marketing_contexts table (N4).

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_marketing"
down_revision = "0004_semantic"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketing_contexts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),

        sa.Column("niche", sa.String(128), nullable=False),
        sa.Column("parent_category", sa.String(128), nullable=False),
        sa.Column("market", sa.String(32), nullable=False),
        sa.Column("language", sa.String(8), nullable=False, server_default="en"),

        sa.Column("traffic_source_primary", sa.String(32), nullable=False),
        sa.Column("page_goal", sa.String(32), nullable=False),
        sa.Column("primary_metric", sa.String(64), nullable=False),
        sa.Column("business_constraints", sa.Text(), nullable=True),

        sa.Column("source_brief", sa.Text(), nullable=False),

        sa.Column("personas", JSONB(), nullable=False, server_default="[]"),
        sa.Column("pain_points_aggregate", JSONB(), nullable=False, server_default="[]"),
        sa.Column("user_flow", JSONB(), nullable=False, server_default="{}"),
        sa.Column("audience_profile", JSONB(), nullable=False, server_default="{}"),
        sa.Column("channel_profile", JSONB(), nullable=False, server_default="{}"),

        sa.Column("grounding_chunks_used", JSONB(), nullable=False, server_default="[]"),
        sa.Column("judge_verdict", JSONB(), nullable=True),

        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_marketing_contexts_niche", "marketing_contexts", ["niche"])
    op.create_index("ix_marketing_contexts_status", "marketing_contexts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_marketing_contexts_status", table_name="marketing_contexts")
    op.drop_index("ix_marketing_contexts_niche", table_name="marketing_contexts")
    op.drop_table("marketing_contexts")
