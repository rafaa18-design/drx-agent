"""add lawyers table

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-07-08 00:01:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = 'b7c8d9e0f1a2'
down_revision: str | None = 'a1b2c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'lawyers',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('email', sa.String(length=200), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('calendar_id', sa.String(length=200), nullable=False, server_default='primary'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('google_refresh_token_encrypted', sa.Text(), nullable=True),
        sa.Column('google_account_email', sa.String(length=200), nullable=True),
        sa.Column('google_connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('email', name='uq_lawyers_email'),
        sa.UniqueConstraint('username', name='uq_lawyers_username'),
    )

    # appointments.lawyer_id era String(100) solto, sem FK — vira String(36) com FK real
    op.alter_column(
        'appointments', 'lawyer_id',
        existing_type=sa.String(length=100),
        type_=sa.String(length=36),
        existing_nullable=True,
        postgresql_using='NULL',
        # Qualquer valor livre já gravado (ex: "seed-demo") não é um UUID válido de
        # advogado — descartamos ao migrar em vez de tentar preservar texto solto.
    )
    op.create_index('ix_appointments_lawyer_id', 'appointments', ['lawyer_id'])
    op.create_foreign_key(
        'fk_appointments_lawyer_id', 'appointments', 'lawyers',
        ['lawyer_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_appointments_lawyer_id', 'appointments', type_='foreignkey')
    op.drop_index('ix_appointments_lawyer_id', table_name='appointments')
    op.alter_column(
        'appointments', 'lawyer_id',
        existing_type=sa.String(length=36),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
    op.drop_table('lawyers')
