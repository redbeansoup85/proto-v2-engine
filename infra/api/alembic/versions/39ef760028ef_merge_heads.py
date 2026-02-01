"""merge heads

Revision ID: 39ef760028ef
Revises: 621ff94db9fd, phase1_0002
Create Date: 2026-01-21 19:01:02.567283

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '39ef760028ef'
down_revision: Union[str, Sequence[str], None] = ('621ff94db9fd', 'phase1_0002')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
