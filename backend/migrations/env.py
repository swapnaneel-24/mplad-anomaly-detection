"""Alembic environment for the PEIARS backend.

The migration URL is resolved from (in priority order):

1. the ``PEIARS_DATABASE_URL`` environment variable;
2. the ``PEIARS_DATABASE_URL`` key in the repository-root ``.env`` file
   (the same single local-configuration file that ``backend/scripts/serve.py``
   loads — one documented procedure for every backend process, with no
   manual export steps; see ``docs/dev/CONFIGURATION_INVENTORY.md``);
3. the ``sqlalchemy.url`` key in ``alembic.ini`` (placeholder).

Real credentials are never committed: they come from the uncommitted
``.env`` file or the deployment environment. Migrations never run
automatically at server startup (PR-03 §12): they are an explicit,
reviewed operation.

The URL is passed directly to ``create_engine`` rather than through
``config.set_main_option`` to avoid configparser interpolation issues
with URL-encoded characters (e.g. ``%2F`` in socket paths).

The ``.env`` file is parsed with ``dotenv_values`` — which reads the
file WITHOUT mutating ``os.environ`` — so explicitly exported
environment variables keep their documented precedence over the file
and the surrounding process environment is left untouched.
"""

from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

from app.db.base import Base
from app.db.models import CaseEvent, ReviewCase  # noqa: F401 — ensure models are imported

#: Repository root: <repo>/backend/migrations/env.py -> parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]

config = context.config

# Note: we intentionally do NOT call fileConfig() here. Alembic's default
# env.py calls fileConfig(config.config_file_name) which reconfigures the
# root logger (setting its level to WARN and replacing its handlers). This
# interferes with pytest's caplog fixture and with the application's own
# logging configuration. The alembic.ini [loggers] section is kept for
# manual `alembic` CLI usage but is not applied during programmatic
# migration calls (command.upgrade / command.downgrade).


def _local_env_database_url() -> str | None:
    """Return ``PEIARS_DATABASE_URL`` from the repository-root ``.env``.

    Uses ``dotenv_values`` (parse without mutating ``os.environ``) so the
    documented precedence is preserved: an explicitly exported
    environment variable always wins over the file. If ``python-dotenv``
    is not installed this raises :class:`RuntimeError` with an actionable
    message — a missing required local-boot dependency is never silently
    ignored.
    """
    try:
        from dotenv import dotenv_values
    except ImportError as exc:  # pragma: no cover — simulated in tests
        raise RuntimeError(
            "python-dotenv is required to resolve the migration database URL "
            "from the repository-root .env file. It is declared in "
            "backend/requirements.txt — install the backend dependencies "
            "with: pip install -r requirements.txt (or requirements-lock.txt "
            "for the exact transitive freeze)."
        ) from exc
    value = dotenv_values(_REPO_ROOT / ".env").get("PEIARS_DATABASE_URL")
    return value or None


# Resolve the database URL: explicit environment variable first, then the
# repository-root .env, then the alembic.ini placeholder.
_migration_url = (
    os.environ.get("PEIARS_DATABASE_URL")
    or _local_env_database_url()
    or config.get_main_option("sqlalchemy.url")
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
