"""Alembic async migration environment for NexusFlow.

Supports both SQLite (dev, offline) and PostgreSQL+asyncpg (production).
DATABASE_URL env var overrides the default; postgres:// and postgresql://
URLs are automatically rewritten to postgresql+asyncpg://.
"""
from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from src.db.models import Base
from src.db.session import normalize_database_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    raw = os.environ.get("DATABASE_URL", "").strip()
    if raw:
        return normalize_database_url(raw)
    # Fall back to whatever is in alembic.ini (SQLite for local dev)
    return normalize_database_url(config.get_main_option("sqlalchemy.url", ""))


def run_migrations_offline() -> None:
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    engine = create_async_engine(_get_url())
    async with engine.connect() as conn:
        await conn.run_sync(_do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
