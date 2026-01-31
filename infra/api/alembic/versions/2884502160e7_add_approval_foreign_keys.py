"""add approval foreign keys (sqlite table rebuild)

Revision ID: fk_0001
Revises: run_0001
Create Date: 2026-01-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "fk_0001"
down_revision = "run_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite: add FK by rebuilding tables
    op.execute("PRAGMA foreign_keys=OFF;")

    # --- approvals_new (with FK to execution_runs.id) ---
    op.create_table(
        "approvals_new",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),

        sa.Column(
            "execution_run_id",
            sa.String(36),
            sa.ForeignKey("execution_runs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),

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

        sa.CheckConstraint("requester_type IN ('system','human')", name="ck_approvals_requester_type"),
        sa.CheckConstraint("mode IN ('single','multi')", name="ck_approvals_mode"),
        sa.CheckConstraint("status IN ('pending','approved','rejected','expired')", name="ck_approvals_status"),
    )

    # copy approvals data
    op.execute("""
        INSERT INTO approvals_new (
            id, execution_run_id, requester_type, requester_id,
            mode, required_approvers, timeout_seconds,
            status, requested_at, resolved_at,
            approved_count, rejected_count
        )
        SELECT
            id, execution_run_id, requester_type, requester_id,
            mode, required_approvers, timeout_seconds,
            status, requested_at, resolved_at,
            approved_count, rejected_count
        FROM approvals;
    """)

    # drop old approvals + rename
    op.drop_index("ix_approvals_status_requested_at", table_name="approvals")
    op.drop_table("approvals")
    op.rename_table("approvals_new", "approvals")

    # recreate index
    op.create_index(
        "ix_approvals_status_requested_at",
        "approvals",
        ["status", "requested_at"],
        unique=False,
    )

    # --- approval_decision_events_new (with FK to approvals.id) ---
    op.create_table(
        "approval_decision_events_new",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),

        sa.Column(
            "approval_id",
            sa.String(36),
            sa.ForeignKey("approvals.id", ondelete="CASCADE"),
            nullable=False,
        ),

        sa.Column("approver_id", sa.String(128), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("note", sa.Text(), nullable=True),

        sa.CheckConstraint("decision IN ('approved','rejected')", name="ck_approval_decision_events_decision"),
        sa.UniqueConstraint("approval_id", "approver_id", name="uq_approval_one_decision_per_approver"),
    )

    # copy events data
    op.execute("""
        INSERT INTO approval_decision_events_new (
            id, approval_id, approver_id, decision, decided_at, note
        )
        SELECT
            id, approval_id, approver_id, decision, decided_at, note
        FROM approval_decision_events;
    """)

    # drop old events + rename
    op.drop_index("ix_approval_events_approval_id_decided_at", table_name="approval_decision_events")
    op.drop_table("approval_decision_events")
    op.rename_table("approval_decision_events_new", "approval_decision_events")

    # recreate index
    op.create_index(
        "ix_approval_events_approval_id_decided_at",
        "approval_decision_events",
        ["approval_id", "decided_at"],
        unique=False,
    )

    op.execute("PRAGMA foreign_keys=ON;")


def downgrade() -> None:
    # Downgrade FK removal also requires rebuild; keep it explicit and safe.
    op.execute("PRAGMA foreign_keys=OFF;")

    # approvals without FK
    op.create_table(
        "approvals_old",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
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
        sa.CheckConstraint("requester_type IN ('system','human')", name="ck_approvals_requester_type"),
        sa.CheckConstraint("mode IN ('single','multi')", name="ck_approvals_mode"),
        sa.CheckConstraint("status IN ('pending','approved','rejected','expired')", name="ck_approvals_status"),
    )

    op.execute("""
        INSERT INTO approvals_old (
            id, execution_run_id, requester_type, requester_id,
            mode, required_approvers, timeout_seconds,
            status, requested_at, resolved_at,
            approved_count, rejected_count
        )
        SELECT
            id, execution_run_id, requester_type, requester_id,
            mode, required_approvers, timeout_seconds,
            status, requested_at, resolved_at,
            approved_count, rejected_count
        FROM approvals;
    """)

    op.drop_index("ix_approvals_status_requested_at", table_name="approvals")
    op.drop_table("approvals")
    op.rename_table("approvals_old", "approvals")
    op.create_index(
        "ix_approvals_status_requested_at",
        "approvals",
        ["status", "requested_at"],
        unique=False,
    )

    # events without FK
    op.create_table(
        "approval_decision_events_old",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("approval_id", sa.String(36), nullable=False),
        sa.Column("approver_id", sa.String(128), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint("decision IN ('approved','rejected')", name="ck_approval_decision_events_decision"),
        sa.UniqueConstraint("approval_id", "approver_id", name="uq_approval_one_decision_per_approver"),
    )

    op.execute("""
        INSERT INTO approval_decision_events_old (
            id, approval_id, approver_id, decision, decided_at, note
        )
        SELECT
            id, approval_id, approver_id, decision, decided_at, note
        FROM approval_decision_events;
    """)

    op.drop_index("ix_approval_events_approval_id_decided_at", table_name="approval_decision_events")
    op.drop_table("approval_decision_events")
    op.rename_table("approval_decision_events_old", "approval_decision_events")
    op.create_index(
        "ix_approval_events_approval_id_decided_at",
        "approval_decision_events",
        ["approval_id", "decided_at"],
        unique=False,
    )

    op.execute("PRAGMA foreign_keys=ON;")
