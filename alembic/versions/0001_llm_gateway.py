"""LLM Gateway initial schema (N10).

Tables: llm_calls, llm_daily_rollup, kill_switch_state.

Revision ID: 0001_llm_gateway
Revises:
Create Date: 2026-04-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_llm_gateway"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── llm_calls ──
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("operation_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("model_requested", sa.String(length=128), nullable=False),
        sa.Column("model_used", sa.String(length=128), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("openrouter_generation_id", sa.String(length=128), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "extras",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_calls")),
    )
    op.create_index(op.f("ix_llm_calls_operation_id"), "llm_calls", ["operation_id"])
    op.create_index(op.f("ix_llm_calls_project_id"), "llm_calls", ["project_id"])
    op.create_index(op.f("ix_llm_calls_openrouter_generation_id"), "llm_calls", ["openrouter_generation_id"])
    op.create_index(op.f("ix_llm_calls_trace_id"), "llm_calls", ["trace_id"])
    op.create_index("ix_llm_calls_operation_created", "llm_calls", ["operation_id", "created_at"])
    op.create_index("ix_llm_calls_project_created", "llm_calls", ["project_id", "created_at"])

    # ── llm_daily_rollup ──
    op.create_table(
        "llm_daily_rollup",
        sa.Column("rollup_date", sa.Date(), nullable=False),
        sa.Column("operation_id", sa.String(length=128), nullable=False),
        sa.Column("total_calls", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_input_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_output_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_cost_usd", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "rollup_date", "operation_id", name=op.f("pk_llm_daily_rollup")
        ),
    )

    # ── kill_switch_state ──
    op.create_table(
        "kill_switch_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("engaged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("engaged_reason", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kill_switch_state")),
        sa.CheckConstraint("id = 1", name=op.f("ck_kill_switch_state_singleton")),
    )

    # Seed singleton row
    op.execute("INSERT INTO kill_switch_state (id, is_active, revision) VALUES (1, false, 0)")


def downgrade() -> None:
    op.drop_table("kill_switch_state")
    op.drop_table("llm_daily_rollup")
    op.drop_index("ix_llm_calls_project_created", table_name="llm_calls")
    op.drop_index("ix_llm_calls_operation_created", table_name="llm_calls")
    op.drop_index(op.f("ix_llm_calls_trace_id"), table_name="llm_calls")
    op.drop_index(op.f("ix_llm_calls_openrouter_generation_id"), table_name="llm_calls")
    op.drop_index(op.f("ix_llm_calls_project_id"), table_name="llm_calls")
    op.drop_index(op.f("ix_llm_calls_operation_id"), table_name="llm_calls")
    op.drop_table("llm_calls")
