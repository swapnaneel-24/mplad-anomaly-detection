"""Alembic environment for the PEIARS backend.

The migration URL is resolved from (in priority order):

1. the ``PEIARS_DATABASE_URL`` environment variable;
2. the ``sqlalchemy.url`` key in ``alembic.ini`` (placeholder).

Real credentials are never committed: they come from the uncommitted
``.env`` file or the deployment environment. Migrations never run
automatically at server startup (PR-03 §12): they are an explicit,
reviewed operation.

The URL is passed directly to ``create_engine`` rather than through
``config.set_main_option`` to avoid configparser interpolation issues
with URL-encoded characters (e.g. ``%2F`` in socket paths).
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.db.base import Base
from app.db.models import CaseEvent, ReviewCase  # noqa: F401 — ensure models are imported

config = context.config

# Note: we intentionally do NOT call fileConfig() here. Alembic's default
# env.py calls fileConfig(config.config_file_name) which reconfigures the
# root logger (setting its level to WARN and replacing its handlers). This
# interferes with pytest's caplog fixture and with the application's own
# logging configuration. The alembic.ini [loggers] section is kept for
# manual `alembic` CLI usage but is not applied during programmatic
# migration calls (command.upgrade / command.downgrade).

# Resolve the database URL from the environment, falling back to the
# alembic.ini placeholder.
_migration_url = os.environ.get("PEIARS_DATABASE_URL") or config.get_main_option(
    "sqlalchemy.url"
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a live connection)."""
    context.configure(
        url=_migration_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    connectable = create_engine(_migration_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
