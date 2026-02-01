"""align execution_runs schema to orm

Revision ID: 621ff94db9fd
Revises: fk_0001
Create Date: 2026-01-21 18:36:07.511332

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '621ff94db9fd'
down_revision: Union[str, Sequence[str], None] = 'fk_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
