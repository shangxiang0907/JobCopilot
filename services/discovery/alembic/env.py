import asyncio
from logging.config import fileConfig

import jobcopilot_discovery.models  # noqa: F401  — registers models on Base.metadata
from alembic import context
from jobcopilot_discovery.config import settings
from jobcopilot_shared.models.base import Base
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

alembic_config = context.config
if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

target_metadata = Base.metadata

_SCHEMA = "discovery_schema"


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table="alembic_version",
        version_table_schema=_SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table="alembic_version",
        version_table_schema=_SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(settings.database_url)
    # Schema must exist before Alembic creates its version table.
    # Migration 0001 also runs CREATE SCHEMA IF NOT EXISTS for idempotency
    # when executed standalone — both occurrences are intentional and safe.
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}"))
    async with engine.connect() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
