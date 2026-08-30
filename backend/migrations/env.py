"""
Location: 24fps/backend/migrations/env.py

Alembic migration environment for the forensic case/evidence metadata
database. The database URL and target metadata are sourced from the
application's own configuration and ORM models rather than duplicated
in `alembic.ini`, so there is exactly one source of truth for both.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.storage.db import Base

# Import every ORM model module here so its table definitions register
# on `Base.metadata` before Alembic compares schema state.
from app.models import (  # noqa: F401
    Artifact,
    Case,
    CaseStatus,
    Device,
    Evidence,
    EvidenceHash,
    HashAlgorithm,
    Recording,
    Storage,
    VerificationStatus,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode, emitting SQL without a live connection.

    Configures the migration context using only a URL, not an `Engine`,
    allowing SQL scripts to be generated for review before being applied
    against evidence infrastructure.
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


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()