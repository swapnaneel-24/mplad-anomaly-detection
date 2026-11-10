"""PostgreSQL readiness probe factory.

PR-03 §13 requires that when PostgreSQL is configured as a required
dependency, readiness tests actual connectivity using a bounded
operation. This module builds an injectable :class:`ReadinessProbe`
whose ``check`` runs a cheap ``SELECT 1`` against the configured engine.

The probe is constructed only when the database is configured as
required (``Settings.database_required`` is true and
``Settings.database_url`` is set). When the database is not configured,
no probe is created and readiness remains as in PR-02 (empty checks
list) — this is the explicit "database not configured" state (PR-03 §13).

The probe never exposes connection strings, credentials or internal
exception details: the ``check`` callable returns a boolean and the
readiness endpoint only ever reports the dependency name and status.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.db.session import DatabaseSessionFactory
from app.services.readiness import ReadinessProbe

#: Name reported by the readiness endpoint for the PostgreSQL dependency.
POSTGRES_PROBE_NAME = "postgresql"


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


def maybe_build_postgres_readiness_probe(
    settings: Settings,
    db: DatabaseSessionFactory | None,
) -> list[ReadinessProbe]:
    """Return the PostgreSQL probe when the database is required, else ``[]``.

    Three-state policy (PR-03 §13):

    * **Database not configured** (``database_required`` is false or
      ``database_url`` is unset): no probe is returned. Readiness
      remains as in PR-02 (empty checks list). "No required dependencies"
      cannot accidentally imply PostgreSQL was verified.
    * **Database configured and healthy**: the probe returns ``True`` and
      readiness reports ``postgresql: ready``.
    * **Database configured but unavailable**: the probe returns ``False``
      and readiness reports 503 ``SERVICE_NOT_READY`` with
      ``postgresql: unavailable``. No connection details leak.
    """
    if not settings.database_required:
        return []
    if not settings.database_url:
        return []
    if db is None:
        return []
    return [build_postgres_readiness_probe(db)]
