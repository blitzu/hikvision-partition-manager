import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import the shared Base and ALL model modules so autogenerate detects every table.
# See RESEARCH.md Pattern 5: every model must be imported before target_metadata assignment.
from app.core.database import Base  # noqa: E402
from app.locations.models import Location  # noqa: E402, F401
from app.nvrs.models import NVRDevice  # noqa: E402, F401
from app.cameras.models import Camera  # noqa: E402, F401
from app.partitions.models import (  # noqa: E402, F401
    Partition,
    PartitionCamera,
    PartitionState,
    CameraDetectionSnapshot,
    CameraDisarmRefcount,
    PartitionAuditLog,
)

target_metadata = Base.metadata

# Override sqlalchemy.url with the value from settings (supports .env loading).
# Falls back to alembic.ini value if settings not available.
try:
    from app.core.config import settings

    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
except Exception:
    pass  # Use alembic.ini sqlalchemy.url as fallback


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
