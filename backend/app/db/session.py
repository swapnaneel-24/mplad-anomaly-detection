"""Database engine and session-factory construction.

Usage:

* Tests call :func:`create_session_factory` with the URL of a disposable
  PostgreSQL database (e.g. one started by ``pgserver``) and receive a
  callable that yields a ``Session``.
* The application factory calls the same function with the configured
  ``Settings.database_url`` and stores the resulting factory on
  ``app.state.db_session_factory``. The readiness probe and the service
  layer consume it from there.

Import-time safety (PR-03 §11): no engine is created at import time. The
engine is created only when :func:`create_engine_from_settings` or
:func:`create_session_factory` is explicitly called.

Production safety (PR-03 §11): ``create_all()`` is never called here and
must never be called by the application factory. Alembic is the sole
schema-management mechanism.
"""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings

#: Type alias for the injectable session factory. It is a callable that
#: returns a new ``Session``; callers are responsible for closing it
#: (typically via a ``with`` block).
SessionFactory = Callable[[], Session]


def create_engine_from_settings(
    settings: Settings,
    *,
    echo: bool = False,
    **engine_kwargs: Any,
) -> Engine:
    """Create a SQLAlchemy ``Engine`` for the configured PostgreSQL URL.

    The URL is taken from ``settings.database_url``. If no URL is
    configured (``None``), :class:`RuntimeError` is raised: the engine
    factory must not be called when the database is not configured.

    Pool parameters come from the typed settings so that connection
    lifecycle is explicit and testable.
    """
    if not settings.database_url:
        raise RuntimeError(
            "create_engine_from_settings called without a configured database_url. "
            "The database engine must not be created when PostgreSQL is not configured."
        )
    if "connect_timeout" not in settings.database_url and "connect_args" not in engine_kwargs:
        engine_kwargs["connect_args"] = {"connect_timeout": 3}
    return create_engine(
        settings.database_url,
        echo=echo,
        pool_pre_ping=settings.db_pool_pre_ping,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle_seconds,
        future=True,
        **engine_kwargs,
    )


def create_session_factory(
    engine: Engine,
    *,
    expire_on_commit: bool = False,
) -> SessionFactory:
    """Build an injectable session factory over ``engine``.

    ``expire_on_commit=False`` keeps loaded ORM objects usable after a
    commit, which is the desired behaviour for the service layer (it
    returns domain objects whose attributes must remain readable after
    the transaction commits).
    """
    factory = sessionmaker(
        bind=engine,
        expire_on_commit=expire_on_commit,
        autoflush=False,
        class_=Session,
    )
    return factory


class DatabaseSessionFactory:
    """Bundles an engine and its session factory for lifecycle management.

    The application factory creates one instance, stores it on
    ``app.state``, and calls :meth:`dispose` during shutdown so that the
    connection pool is closed cleanly (PR-03 §11: "proper cleanup during
    application shutdown").
    """

    def __init__(self, engine: Engine, session_factory: SessionFactory) -> None:
        self.engine = engine
        self.session_factory = session_factory

    @classmethod
    def from_settings(cls, settings: Settings, **engine_kwargs: Any) -> "DatabaseSessionFactory":
        engine = create_engine_from_settings(settings, **engine_kwargs)
        return cls(engine, create_session_factory(engine))

    def dispose(self) -> None:
        """Close the connection pool. Idempotent."""
        self.engine.dispose()
