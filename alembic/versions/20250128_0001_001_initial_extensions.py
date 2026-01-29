"""Initial database setup with extensions.

Revision ID: 001
Revises:
Create Date: 2025-01-28
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create PostgreSQL extensions required by the application."""
    # Enable pgvector extension for embeddings/vector similarity search
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Enable uuid-ossp for UUID generation
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')


def downgrade() -> None:
    """Remove PostgreSQL extensions."""
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
    op.execute('DROP EXTENSION IF EXISTS vector')
