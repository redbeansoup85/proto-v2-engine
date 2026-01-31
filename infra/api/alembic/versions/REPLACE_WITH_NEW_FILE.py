"""add execution_run phase1 columns

Revision ID: phase1_0002
Revises: fk_0001
Create Date: 2026-01-21
"""
from alembic import op
import sqlalchemy as sa

# 임시 문자열 리비전. 실제 운영에서는 alembic이 생성한 revision id/다운리비전으로 관리해도 됨.
revision = "phase1_0002"
down_revision = "fk_0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("execution_runs") as batch:
        batch.add_column(sa.Column("request_fingerprint", sa.String(64), nullable=True))
        batch.add_column(sa.Column("blocked_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("started_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("ended_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("execution_runs") as batch:
        batch.drop_column("ended_at")
        batch.drop_column("started_at")
        batch.drop_column("blocked_reason")
        batch.drop_column("request_fingerprint")
