"""add follow_up fields to leads

Revision ID: a1b2c3d4e5f6
Revises: 5807b21acd69
Create Date: 2026-05-25 00:01:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = '5807b21acd69'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('leads', sa.Column('follow_up_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('leads', sa.Column('follow_up_last_sent_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('leads', 'follow_up_last_sent_at')
    op.drop_column('leads', 'follow_up_count')
