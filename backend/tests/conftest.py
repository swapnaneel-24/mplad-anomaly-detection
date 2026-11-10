"""Pytest configuration for the PEIARS backend tests.

Makes ``backend/`` importable without package installation by inserting
it into ``sys.path``. The frozen research tree (``tests/`` at the
repository root) is untouched and never collected by this suite.

PR-03 adds PostgreSQL integration-test fixtures backed by ``pgserver``
(a pip-packaged PostgreSQL 16.x server). The server is started once per
test session, migrations are applied to a disposable database, and each
test gets a clean state via table truncation.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.db.session import DatabaseSessionFactory  # noqa: E402
from app.main import create_app  # noqa: E402

# --- Root logger level for caplog compatibility ---------------------------
# The `peiars` logger has a StreamHandler that handles its own output, but
# records propagate to the root logger where pytest's caplog handler lives.
# The root logger's default level (WARNING) drops INFO records before they
# reach caplog. This autouse fixture sets the root logger to INFO for every
# test so caplog can capture peiars.api records.
@pytest.fixture(autouse=True)
def _root_logger_info_level():
    import logging

    root = logging.getLogger()
    old_level = root.level
    root.setLevel(logging.INFO)
    # Clear the peiars logger's StreamHandler so it doesn't interfere with
    # caplog's record capture. configure_logging (called by create_app)
    # will re-attach a fresh handler.
    peiars = logging.getLogger("peiars")
    old_handlers = peiars.handlers[:]
    old_propagate = peiars.propagate
    peiars.handlers.clear()
    peiars.propagate = True
    # Suppress httpx INFO logs so they don't appear in caplog.records and
    # interfere with log-content assertions (httpx logs the full URL,
    # including query parameters, at INFO level).
    httpx_logger = logging.getLogger("httpx")
    old_httpx_level = httpx_logger.level
    httpx_logger.setLevel(logging.WARNING)
    yield
    peiars.handlers = old_handlers
    peiars.propagate = old_propagate
    httpx_logger.setLevel(old_httpx_level)
    root.setLevel(old_level)


# --- PR-02 fixtures (unchanged) -------------------------------------------

@pytest.fixture()
def test_settings() -> Settings:
    """Isolated, deterministic settings (no ``.env`` / environment reads).

    Explicitly clears database settings so DB-integration env vars (set by
    session-scoped DB fixtures) don't leak into non-DB tests.
    """
    return Settings(
        _env_file=None,
        environment="test",
        cors_origins=["http://test.example"],
        git_commit_sha=None,
        docs_enabled=True,
        database_url=None,
        database_required=False,
    )


@pytest.fixture()
def app(test_settings: Settings):
    """Application built from isolated settings and no readiness probes."""
    return create_app(settings=test_settings)


@pytest.fixture()
def client(app) -> TestClient:
    """Synchronous test client over the ASGI app."""
    return TestClient(app)


# --- PR-03 PostgreSQL integration fixtures --------------------------------

def _has_pgserver() -> bool:
    try:
        import pgserver  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.fixture(scope="session")
def pg_server():
    """Start a disposable PostgreSQL server for the test session.

    Uses ``pgserver`` (a pip-packaged PostgreSQL 16.x). The server
    auto-starts on first connection. The data directory is removed at
    session end via ``cleanup()``. If pgserver is not installed, the
    fixture skips tests that depend on it.
    """
    if not _has_pgserver():
        pytest.skip("pgserver is not installed; PostgreSQL integration tests skipped")
    import pgserver
    import tempfile

    data_dir = tempfile.mkdtemp(prefix="peiars_pgtest_")
    server = pgserver.get_server(data_dir)
    # Force the server to start now so the session is ready.
    server.ensure_postgres_running()
    yield server
    server.cleanup()


@pytest.fixture(scope="session")
def db_url(pg_server):
    """A PostgreSQL URL pointing at a disposable test database.

    Creates a dedicated ``peiars_test`` database within the pgserver
    instance so tests don't collide with each other or with the default
    ``postgres`` database.
    """
    admin_uri = pg_server.get_uri()
    # Connect to the default 'postgres' database and create a test database.
    admin_engine = create_engine(admin_uri, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS peiars_test"))
        conn.execute(text("CREATE DATABASE peiars_test"))
    admin_engine.dispose()
    # Return a URL pointing at the new database.
    # pgserver URIs look like: postgresql://postgres:@/postgres?host=/tmp/...
    # We replace the database path component only (not the username).
    from sqlalchemy import make_url

    url = make_url(admin_uri)
    return str(url.set(database="peiars_test"))


@pytest.fixture(scope="session")
def db_engine(db_url):
    """Engine with migrations applied to head. Session-scoped."""
    import os
    from alembic import command
    from alembic.config import Config

    engine = create_engine(db_url, future=True)

    # Apply migrations to head. The URL is passed via the environment
    # variable to avoid configparser interpolation issues with URL-encoded
    # characters in pgserver socket paths.
    os.environ["PEIARS_DATABASE_URL"] = db_url
    alembic_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    command.upgrade(alembic_cfg, "head")

    yield engine

    engine.dispose()


@pytest.fixture(scope="session")
def db_session_factory(db_engine):
    """Session factory bound to the migrated engine."""
    from app.db.session import create_session_factory
    return create_session_factory(db_engine)


@pytest.fixture()
def db_service(db_session_factory):
    """A ReviewCaseService with a clean database state per test.

    Truncates ``case_events`` and ``review_cases`` before each test so
    tests are independent. The service commits its own transactions.
    """
    from app.services.review_cases import ReviewCaseService

    # Clean slate: truncate both tables (case_events first due to FK).
    with db_session_factory() as session:
        session.execute(text("TRUNCATE TABLE case_events RESTART IDENTITY CASCADE"))
        session.execute(text("TRUNCATE TABLE review_cases RESTART IDENTITY CASCADE"))
        session.commit()

    return ReviewCaseService(db_session_factory)


@pytest.fixture()
def db_settings(db_url):
    """Settings with the database configured as required."""
    return Settings(
        _env_file=None,
        environment="test",
        cors_origins=["http://test.example"],
        git_commit_sha=None,
        docs_enabled=True,
        database_url=db_url,
        database_required=True,
    )


@pytest.fixture()
def db_app(db_settings, db_session_factory):
    """Application with the database wired in and the probe active."""
    return create_app(
        settings=db_settings,
        db_session_factory_override=DatabaseSessionFactory(
            db_session_factory.kw["bind"], db_session_factory
        ),
    )


@pytest.fixture()
def db_client(db_app):
    """TestClient over the DB-backed application."""
    return TestClient(db_app)
