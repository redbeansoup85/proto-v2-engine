"""add execution_run phase1 columns (sqlite-compatible)

Revision ID: phase1_0002
Revises: fk_0001
Create Date: 2026-02-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "phase1_0002"
down_revision: Union[str, Sequence[str], None] = "fk_0001"
branch_labels = None
depends_on = None


def _col_exists(table: str, name: str) -> bool:
    bind = op.get_bind()
    rows = bind.exec_driver_sql(f"PRAGMA table_info({table});").fetchall()
    existing = {r[1] for r in rows}  # r[1] = column name
    return name in existing


def _add_col_if_missing(batch, table: str, col: sa.Column) -> None:
    if not _col_exists(table, col.name):
        batch.add_column(col)


def upgrade() -> None:
    # SQLite-safe: batch_alter_table
    # Add-only-if-missing: tolerates mixed states (e.g., if another rev already added some cols)
    with op.batch_alter_table("execution_runs") as b:
        _add_col_if_missing(
            b,
            "execution_runs",
            sa.Column("request_fingerprint", sa.String(64), nullable=True),
        )
        _add_col_if_missing(
            b,
            "execution_runs",
            sa.Column("blocked_reason", sa.Text(), nullable=True),
        )
        _add_col_if_missing(
            b,
            "execution_runs",
            sa.Column("started_at", sa.DateTime(), nullable=True),
        )
        _add_col_if_missing(
            b,
            "execution_runs",
            sa.Column("ended_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    # SQLite DROP COLUMN is limited; keep downgrade no-op
    pass
