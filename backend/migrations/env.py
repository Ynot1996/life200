"""Alembic environment: tells Alembic which database to change and what the tables should be.

Common commands (from backend/):
    uv run alembic revision --autogenerate -m "add x"   # write a migration from model changes
    uv run alembic upgrade head                          # apply all migrations
    uv run alembic downgrade -1                          # undo the last one
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from life200.core.config import get_settings
from life200.db.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic compares this (what the code says) with the real database to autogenerate migrations.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Write SQL to the screen instead of running it (alembic upgrade head --sql)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
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
