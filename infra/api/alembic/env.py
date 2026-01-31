from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Alembic Config object
config = context.config

# Logging config (safe-guard)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import your metadata
# Adjust this import if your project uses a different module path.
from infra.api.endpoints.models.base import Base  # noqa: E402

target_metadata = Base.metadata


def _get_db_url() -> str:
    # Prefer env var for test/prod isolation.
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    # Fallback to alembic.ini setting.
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    url = _get_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # Push resolved URL into config for engine creation.
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _get_db_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio

    asyncio.run(run_migrations_online())
