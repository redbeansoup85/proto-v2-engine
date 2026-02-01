"""ensure execution_runs exists (fail-closed hotfix)

Revision ID: ensure_execution_runs_0001
Revises: 7f0b460002ff
Create Date: 2026-01-22
"""

from alembic import op

revision = "ensure_execution_runs_0001"
down_revision = "7f0b460002ff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from infra.api.endpoints.models.execution_run import ExecutionRun  # noqa
    ExecutionRun.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS execution_runs")
