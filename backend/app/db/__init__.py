"""Database package: SQLAlchemy declarative base, session factory, ORM models.

Import-time safety (PR-03 §11):

* No module in this package opens a database connection at import time.
* The engine and session factory are created lazily by
  :func:`app.db.session.create_session_factory`, which the application
  factory calls with the configured settings (or which tests call with an
  injected URL).
* No ``create_all()`` is ever called in production execution; Alembic is
  the authoritative schema-management mechanism (PR-03 §12).
"""

from __future__ import annotations

from app.db.base import Base
from app.db.session import (
    DatabaseSessionFactory,
    SessionFactory,
    create_engine_from_settings,
    create_session_factory,
)

__all__ = [
    "Base",
    "DatabaseSessionFactory",
    "SessionFactory",
    "create_engine_from_settings",
    "create_session_factory",
]
