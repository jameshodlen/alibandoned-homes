"""Alembic environment configuration for async migrations.

This module configures Alembic to work with SQLAlchemy's
async engine and GeoAlchemy2 spatial types.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from geoalchemy2 import Geometry  # noqa: F401 - Required for PostGIS type registration
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.models.base import Base

# Import all models to ensure they're registered with Base.metadata
from app.models.location import Location  # noqa: F401
from app.models.photo import Photo  # noqa: F401
from app.models.prediction import Prediction  # noqa: F401

# Alembic Config object
config = context.config

# Override sqlalchemy.url with our settings
config.set_main_option("sqlalchemy.url", settings.SQLALCHEMY_DATABASE_URI)

# Configure logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL scripts without connecting to the database.
    """
    url = config.get_main_option("sqlalchemy.url")
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
    """Execute migrations within a connection context.

    Args:
        connection: SQLAlchemy connection to use.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates an async engine and runs migrations.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
