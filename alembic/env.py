"""Alembic environment configuration."""

import asyncio
import os
from logging.config import fileConfig
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from dotenv import load_dotenv

# Carrega o .env da raiz do projeto
load_dotenv(Path(__file__).parent.parent / ".env")

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# Alembic Config object
config = context.config

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _build_db_url() -> tuple[str, dict]:
    """Normaliza a DATABASE_URL para asyncpg e extrai connect_args (SSL).

    Mesma lógica de app/db/session.py — garante compatibilidade com
    provedores como Neon/Supabase que mandam sslmode/channel_binding.
    """
    raw = os.environ["DATABASE_URL"]
    if raw.startswith("postgresql://"):
        raw = raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif raw.startswith("postgresql+psycopg://"):
        raw = raw.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)

    connect_args: dict = {}
    parts = urlsplit(raw)
    query = dict(parse_qsl(parts.query))
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)  # asyncpg não suporta
    raw = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )
    if sslmode and sslmode != "disable":
        connect_args["ssl"] = True
    return raw, connect_args


_DB_URL, _CONNECT_ARGS = _build_db_url()
config.set_main_option('sqlalchemy.url', _DB_URL)

# Modelos CRM DRX
from app.db.models import Base  # noqa: E402
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the script output.
    """
    url = config.get_main_option('sqlalchemy.url')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = create_async_engine(
        _DB_URL,
        poolclass=pool.NullPool,
        connect_args=_CONNECT_ARGS,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Windows usa ProactorEventLoop por padrão, incompatível com psycopg async.
    # Força SelectorEventLoop para compatibilidade.
    if asyncio.get_event_loop_policy().__class__.__name__ == "WindowsProactorEventLoopPolicy":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
