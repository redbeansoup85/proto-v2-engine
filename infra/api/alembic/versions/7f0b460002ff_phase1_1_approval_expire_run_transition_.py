"""phase1_1 approval expire + run transition columns

Revision ID: 7f0b460002ff
Revises: 39ef760028ef
Create Date: 2026-01-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "7f0b460002ff"
down_revision: Union[str, Sequence[str], None] = "39ef760028ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # approvals.expires_at (nullable)
    with op.batch_alter_table("approvals") as b:
        b.add_column(sa.Column("expires_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    # SQLite: drop column requires table rebuild; use batch_alter_table
    with op.batch_alter_table("approvals") as b:
        b.drop_column("expires_at")
