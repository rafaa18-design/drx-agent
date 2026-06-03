"""Async SQLAlchemy engine e session factory."""

import os
from collections.abc import AsyncGenerator
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Usa DATABASE_URL do env (asyncpg) com fallback para POSTGRES_URL das settings
_raw_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL", "")

# Garante driver asyncpg
if _raw_url.startswith("postgresql://"):
    _raw_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _raw_url.startswith("postgresql+psycopg://"):
    _raw_url = _raw_url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)

# Provedores como Neon mandam params (sslmode, channel_binding) que o asyncpg
# não entende na URL. Remove esses params e ativa SSL via connect_args.
_connect_args: dict = {}
if _raw_url:
    _parts = urlsplit(_raw_url)
    _query = dict(parse_qsl(_parts.query))
    _sslmode = _query.pop("sslmode", None)
    _query.pop("channel_binding", None)  # asyncpg não suporta
    # Reconstrói a URL sem os params incompatíveis
    _raw_url = urlunsplit(
        (_parts.scheme, _parts.netloc, _parts.path, urlencode(_query), _parts.fragment)
    )
    # Ativa SSL quando o provedor exige (Neon/Supabase usam sslmode=require)
    if _sslmode and _sslmode != "disable":
        _connect_args["ssl"] = True

engine = create_async_engine(
    _raw_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args=_connect_args,
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
