"""add approval layer tables (sqlite-compatible)

Revision ID: approval_0001
Revises: 
Create Date: 2026-01-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "approval_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite compatibility:
    # - Use String + CHECK constraints instead of ENUM types.
    # - Use CURRENT_TIMESTAMP for timestamps.
    # - FK to execution_runs is omitted until we confirm execution_runs schema.

    op.create_table(
        "approvals",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),

        # 1:1 with execution_runs
        sa.Column("execution_run_id", sa.String(36), nullable=False, unique=True),

        sa.Column("requester_type", sa.String(16), nullable=False),
        sa.Column("requester_id", sa.String(128), nullable=False),

        sa.Column("mode", sa.String(16), nullable=False, server_default="single"),
        sa.Column("required_approvers", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="3600"),

        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),

        sa.Column("requested_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),

        sa.Column("approved_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),

        # enum-like checks
        sa.CheckConstraint("requester_type IN ('system','human')", name="ck_approvals_requester_type"),
        sa.CheckConstraint("mode IN ('single','multi')", name="ck_approvals_mode"),
        sa.CheckConstraint("status IN ('pending','approved','rejected','expired')", name="ck_approvals_status"),
    )

    op.create_index(
        "ix_approvals_status_requested_at",
        "approvals",
        ["status", "requested_at"],
        unique=False,
    )

    op.create_table(
        "approval_decision_events",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),

        sa.Column("approval_id", sa.String(36), nullable=False),
        sa.Column("approver_id", sa.String(128), nullable=False),

        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("note", sa.Text(), nullable=True),

        sa.CheckConstraint("decision IN ('approved','rejected')", name="ck_approval_decision_events_decision"),
        sa.UniqueConstraint("approval_id", "approver_id", name="uq_approval_one_decision_per_approver"),
    )

    op.create_index(
        "ix_approval_events_approval_id_decided_at",
        "approval_decision_events",
        ["approval_id", "decided_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_approval_events_approval_id_decided_at", table_name="approval_decision_events")
    op.drop_table("approval_decision_events")

    op.drop_index("ix_approvals_status_requested_at", table_name="approvals")
    op.drop_table("approvals")
