"""Script para dropar todas as tabelas do banco antes de recriar via Alembic."""
import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

url = os.environ["DATABASE_URL"]
engine = create_async_engine(url)


async def drop_all():
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        tables = [row[0] for row in result.fetchall()]
        print(f"Tabelas encontradas: {tables}")

        for t in tables:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
            print(f"  Dropped: {t}")

        print("Concluído.")


asyncio.run(drop_all())
