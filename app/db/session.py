"""Async SQLAlchemy engine e session factory."""

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Usa DATABASE_URL do env (asyncpg) com fallback para POSTGRES_URL das settings
_raw_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL", "")

# Garante driver asyncpg
if _raw_url.startswith("postgresql://"):
    _raw_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _raw_url.startswith("postgresql+psycopg://"):
    _raw_url = _raw_url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    _raw_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency que fornece uma sessão async para cada request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
