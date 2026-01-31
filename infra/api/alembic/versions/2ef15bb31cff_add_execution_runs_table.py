"""add execution_runs table (sqlite-compatible)

Revision ID: run_0001
Revises: approval_0001
Create Date: 2026-01-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "run_0001"
down_revision = "approval_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Minimal execution_runs table to anchor approvals (Phase 0/1 bridge)
    op.create_table(
        "execution_runs",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),

        sa.Column("project_id", sa.String(128), nullable=False),
        sa.Column("decision_card_id", sa.String(64), nullable=True),

        sa.Column("execution_scope", sa.String(32), nullable=False, server_default="automation"),
        sa.Column("idempotency_key", sa.String(128), nullable=False),

        # status lifecycle (minimal)
        sa.Column("status", sa.String(24), nullable=False, server_default="created"),
        # created/approved/executing/succeeded/failed/denied/expired (확장은 앱에서)

        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),

        sa.CheckConstraint(
            "execution_scope IN ('automation','manual','adapter')",
            name="ck_execution_runs_scope",
        ),
    )

    # Dedup anchor: same idempotency_key per project must be unique
    op.create_index(
        "ux_execution_runs_project_id_idempotency_key",
        "execution_runs",
        ["project_id", "idempotency_key"],
        unique=True,
    )

    op.create_index(
        "ix_execution_runs_status_created_at",
        "execution_runs",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_execution_runs_status_created_at", table_name="execution_runs")
    op.drop_index("ux_execution_runs_project_id_idempotency_key", table_name="execution_runs")
    op.drop_table("execution_runs")
