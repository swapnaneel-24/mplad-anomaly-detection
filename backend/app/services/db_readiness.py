"""PostgreSQL readiness probe factory.

PR-03 §13 requires that when PostgreSQL is configured as a required
dependency, readiness tests actual connectivity using a bounded
operation. This module builds injectable :class:`ReadinessProbe`
objects whose ``check`` callables run cheap, bounded, READ-ONLY queries
against the configured engine:

* a connectivity probe (``SELECT 1``), and
* a schema-state probe (PR-06A final correction §5): the database's
  ``alembic_version`` must equal the head revision of the *committed*
  migrations directory. An empty (never-migrated) database passes
  ``SELECT 1`` but is NOT ready — the investigation tables are absent.

The probes are constructed only when the database is configured as
required (``Settings.database_required`` is true and
``Settings.database_url`` is set). When the database is not configured,
no probes are created and readiness remains as in PR-02 (empty checks
list) — this is the explicit "database not configured" state (PR-03 §13).

The schema-state probe is deliberately narrow and read-only: it never
runs migrations, never writes, and never modifies applied migrations
(migrations remain an explicit, reviewed ``alembic upgrade head``
operation per PR-03 §12). It reads the expected revision from the
committed ``backend/migrations`` directory via Alembic's
``ScriptDirectory`` (local files only — no database access) and
compares it with the single row of ``alembic_version``.

Neither probe ever exposes connection strings, credentials or internal
exception details: the ``check`` callables return booleans and the
readiness endpoint only ever reports dependency names and statuses.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.db.session import DatabaseSessionFactory
from app.services.readiness import ReadinessProbe

#: Name reported by the readiness endpoint for the PostgreSQL dependency.
POSTGRES_PROBE_NAME = "postgresql"

#: Name reported by the readiness endpoint for the schema-state check.
MIGRATIONS_PROBE_NAME = "migrations"

#: Backend root (backend/app/services/db_readiness.py -> parents[2]).
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _committed_head_revision() -> str | None:
    """Return the head revision of the committed migrations directory.

    Read-only: walks ``backend/migrations`` through Alembic's
    ``ScriptDirectory`` and never touches the database. The result is the
    schema revision the *application code shipped with* expects. Used by
    the schema-state probe to decide whether the database's
    ``alembic_version`` is compatible.
    """
    from alembic.config import Config as AlembicConfig
    from alembic.script import ScriptDirectory

    alembic_cfg = AlembicConfig(str(_BACKEND_ROOT / "alembic.ini"))
    # Absolute script_location: independent of the process working
    # directory (the probe may run from the repo root or backend/).
    alembic_cfg.set_main_option("script_location", str(_BACKEND_ROOT / "migrations"))
    return ScriptDirectory.from_config(alembic_cfg).get_current_head()


def build_postgres_readiness_probe(
    db: DatabaseSessionFactory,
) -> ReadinessProbe:
    """Build a readiness probe that runs ``SELECT 1`` on the configured engine.

    The check is bounded (a single cheap round-trip) and never raises out
    of the probe: any :class:`SQLAlchemyError` or unexpected exception is
    treated as "unavailable" so the readiness endpoint can report 503
    with the sanitized ``SERVICE_NOT_READY`` contract.
    """

    def _check() -> bool:
        try:
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False
        except Exception:  # noqa: BLE001 — probe must never raise
            return False

    return ReadinessProbe(name=POSTGRES_PROBE_NAME, check=_check)


def build_migration_readiness_probe(
    db: DatabaseSessionFactory,
) -> ReadinessProbe:
    """Build a read-only probe that the schema is at the committed head.

    Fails (returns ``False``) when the database is reachable but:

    * the ``alembic_version`` table does not exist (never migrated),
    * its revision differs from the committed migrations' head
      (older, newer, or foreign — incompatible), or
    * it contains anything other than exactly one row (corrupt state).

    Like the connectivity probe, this check never raises and never
    leaks details — a failure is reported as ``migrations: unavailable``.
    It never writes: no migration is created, applied, or modified.
    """

    def _check() -> bool:
        try:
            expected = _committed_head_revision()
            if expected is None:
                # No committed revisions found — a broken deployment;
                # never report ready for an unknown expected schema.
                return False
            with db.engine.connect() as conn:
                rows = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
            return len(rows) == 1 and rows[0][0] == expected
        except SQLAlchemyError:
            return False
        except Exception:  # noqa: BLE001 — probe must never raise
            return False

    return ReadinessProbe(name=MIGRATIONS_PROBE_NAME, check=_check)


def maybe_build_postgres_readiness_probe(
    settings: Settings,
    db: DatabaseSessionFactory | None,
) -> list[ReadinessProbe]:
    """Return the PostgreSQL probes when the database is required, else ``[]``.

    Three-state policy (PR-03 §13, extended by the PR-06A final
    correction §5):

    * **Database not configured** (``database_required`` is false or
      ``database_url`` is unset): no probes are returned. Readiness
      remains as in PR-02 (empty checks list). "No required dependencies"
      cannot accidentally imply PostgreSQL was verified.
    * **Database configured and healthy**: both the connectivity probe
      (``SELECT 1``) and the schema-state probe
      (``alembic_version`` == committed head) return ``True`` and
      readiness reports ``postgresql: ready`` and ``migrations: ready``.
    * **Database configured but unavailable** (unreachable, wrong
      credentials, missing database): both probes return ``False`` and
      readiness reports 503 ``SERVICE_NOT_READY``. Connectivity and
      credential failures intentionally share this one sanitized
      classification — no detail about *why* the connection failed is
      exposed.
    * **Database reachable but not migrated / not at head** (new in the
      PR-06A final correction): the connectivity probe reports ready
      while the schema-state probe fails, so readiness reports 503 with
      the failed ``migrations`` check and the ready ``postgresql`` check
      — the failure class is now distinguishable from a plain
      connection failure without leaking any connection detail.
    """
    if not settings.database_required:
        return []
    if not settings.database_url:
        return []
    if db is None:
        return []
    return [
        build_postgres_readiness_probe(db),
        build_migration_readiness_probe(db),
    ]
