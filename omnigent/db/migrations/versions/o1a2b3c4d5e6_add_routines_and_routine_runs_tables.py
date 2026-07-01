"""add routines and routine_runs tables

Revision ID: o1a2b3c4d5e6
Revises: n1a2b3c4d5e6
Create Date: 2026-07-01 12:00:00.000000

Adds the ``routines`` and ``routine_runs`` tables — the persistence
foundation for scheduled agent invocations. A routine is a saved
prompt plus launch context and cron expressions; a routine_run records
one firing. Nothing at runtime dispatches these rows yet; this
migration only lands the schema so later work can build on it.

Both tables are created with ``op.create_table`` (and dropped with
``op.drop_table``), which runs under Alembic's batch mode (env.py sets
``render_as_batch=True``) so the DDL applies cleanly on SQLite and
PostgreSQL alike.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "o1a2b3c4d5e6"
down_revision: str | None = "n1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the ``routines`` and ``routine_runs`` tables."""
    op.create_table(
        "routines",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("cron_expressions", sa.Text(), nullable=False),
        sa.Column("target_kind", sa.String(length=16), nullable=False),
        sa.Column("host_id", sa.String(length=64), nullable=True),
        sa.Column("workspace", sa.Text(), nullable=True),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("harness_override", sa.String(length=64), nullable=True),
        sa.Column("model_override", sa.String(length=128), nullable=True),
        sa.Column("reasoning_effort", sa.String(length=32), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column("owner_user_id", sa.String(length=256), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("last_run_at", sa.Integer(), nullable=True),
        sa.Column("last_run_conversation_id", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.Text(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "target_kind IN ('sandbox', 'host')",
            name="ck_routines_target_kind",
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["host_id"], ["hosts.host_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["last_run_conversation_id"], ["conversations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_routines_created_at", "routines", ["created_at"], unique=False)
    op.create_index("ix_routines_agent_id", "routines", ["agent_id"], unique=False)
    op.create_index("ix_routines_owner_user_id", "routines", ["owner_user_id"], unique=False)
    op.create_index(
        "ix_routines_enabled_created_at_id",
        "routines",
        ["enabled", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "routine_runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("routine_id", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("scheduled_at", sa.Integer(), nullable=False),
        sa.Column("fired_at", sa.Integer(), nullable=True),
        sa.Column("finished_at", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('scheduled', 'running', 'succeeded', 'failed', 'skipped')",
            name="ck_routine_runs_status",
        ),
        sa.ForeignKeyConstraint(["routine_id"], ["routines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_routine_runs_routine_id", "routine_runs", ["routine_id"], unique=False)


def downgrade() -> None:
    """Drop the ``routine_runs`` and ``routines`` tables."""
    op.drop_index("ix_routine_runs_routine_id", table_name="routine_runs")
    op.drop_table("routine_runs")
    op.drop_index("ix_routines_enabled_created_at_id", table_name="routines")
    op.drop_index("ix_routines_owner_user_id", table_name="routines")
    op.drop_index("ix_routines_agent_id", table_name="routines")
    op.drop_index("ix_routines_created_at", table_name="routines")
    op.drop_table("routines")
