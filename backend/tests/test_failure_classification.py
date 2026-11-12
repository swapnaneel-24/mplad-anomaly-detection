"""Focused failure-classification tests (PR-06A correction §5; final
correction §5/§6 for schema readiness and SCRAM isolation).

These tests use a REAL PostgreSQL server (pgserver) to pin the failure
classes the architecture actually separates — replacing the earlier
delivery report's false claim that application login-401 tests proved
PostgreSQL credential-failure diagnostics. A 401 from ``POST
/api/v1/auth/login`` is an authentication outcome, not a PostgreSQL
connection diagnostic.

Classes the architecture distinguishes:

1. **Missing settings** — ``database_required=true`` with no
   ``database_url``: startup fails with ``DatabaseConfigurationError``
   (an actionable, sanitized configuration error raised before any
   connection attempt).
2. **Database connection failure (network)** — nothing listening on the
   configured endpoint: readiness reports ``503 SERVICE_NOT_READY`` with
   the ``postgresql`` failed check; liveness stays ``200``.
3. **Database credential failure** — a real PostgreSQL that requires SCRAM
   authentication rejecting a wrong password (SQLSTATE 28P01). The
   readiness contract deliberately classifies this identically to (2):
   a sanitized ``postgresql: unavailable`` check that does not reveal
   *why* the connection failed (no information leakage). Verified with a
   dedicated database on a DEDICATED DISPOSABLE PostgreSQL instance
   whose ``pg_hba.conf`` line requires scram-sha-256 (see the
   ``scram_database`` fixture for the isolation guarantee).
4. **Migration readiness** — an empty (unmigrated) database, or one at an
   older revision: since the PR-06A final correction the documented boot
   verification (``/health/ready``) detects this — the read-only
   ``migrations`` check compares ``alembic_version`` with the committed
   migrations' head and fails clearly (503) while the ``postgresql``
   connectivity check stays ready. Migrations are still NEVER applied
   automatically at startup; the documented remediation is an explicit
   ``alembic upgrade head``.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.exc import ProgrammingError

from app.core.config import Settings
from app.core.config_errors import DatabaseConfigurationError
from app.main import create_app


def _test_settings(database_url: str) -> Settings:
    """Settings with the database required, pointed at the given URL."""
    return Settings(
        _env_file=None,
        environment="test",
        cors_origins=["http://test.example"],
        git_commit_sha=None,
        docs_enabled=True,
        database_url=database_url,
        database_required=True,
    )


#: Revision the committed migrations consider head (0003 is current;
#: 0002 is its direct ancestor — used for the incompatible-schema case).
_HEAD_REVISION = "0003_add_users_sessions_auth"
_PARENT_REVISION = "0002_add_event_seq"


@pytest.fixture()
def scram_database():
    """A DEDICATED DISPOSABLE PostgreSQL instance + database + login role
    that REQUIRE SCRAM password authentication.

    Isolation guarantee (PR-06A final correction §6): this fixture starts
    its OWN ``pgserver`` instance in a private temporary data directory.
    It never touches the session-scoped ``pg_server`` fixture shared by
    the rest of the suite, and by construction it can never modify a
    shared or developer-owned PostgreSQL server: the only
    ``pg_hba.conf`` it edits belongs to the throwaway instance it just
    created in its own temp directory.

    Why the edit is needed: pgserver's generated ``pg_hba.conf`` uses
    ``trust`` for every local and loopback connection, which would make
    password tests meaningless (any password is accepted). The fixture
    prepends a single first-match ``local peiars_credtest all
    scram-sha-256`` line, so ONLY the dedicated ``peiars_credtest``
    database on this private instance requires SCRAM.

    Cleanup behaviour: the ``finally`` block calls ``server.cleanup()``,
    which stops the server process and DELETES the entire private data
    directory — including the edited ``pg_hba.conf``, the database and
    the role. Nothing survives the test; no other test in the session
    can observe the modified configuration.
    """
    try:
        import pgserver
    except ImportError:
        pytest.skip("pgserver is not installed; SCRAM integration tests skipped")
    import tempfile

    data_dir = tempfile.mkdtemp(prefix="peiars_scramtest_")
    server = pgserver.get_server(data_dir)
    try:
        server.ensure_postgres_running()
        admin_uri = server.get_uri()
        admin_engine = create_engine(admin_uri, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            hba_path = Path(conn.execute(text("SHOW hba_file")).scalar_one())
            conn.execute(text("DROP DATABASE IF EXISTS peiars_credtest"))
            conn.execute(text("CREATE DATABASE peiars_credtest"))
            conn.execute(text("DROP ROLE IF EXISTS peiars_cred_user"))
            conn.execute(
                text("CREATE ROLE peiars_cred_user LOGIN "
                     "PASSWORD 'correct-horse-battery-staple'")
            )
        admin_engine.dispose()

        # Scope the SCRAM requirement to the dedicated database only
        # (pg_hba matches per-database, first match wins).
        hba_path.write_text(
            "local   peiars_credtest   all   scram-sha-256\n"
            + hba_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        reload_engine = create_engine(admin_uri, isolation_level="AUTOCOMMIT")
        with reload_engine.connect() as conn:
            conn.execute(text("SELECT pg_reload_conf()"))
        reload_engine.dispose()
        yield admin_uri
    finally:
        # Removes the whole disposable instance: server process, socket
        # and data directory (including the edited pg_hba.conf).
        server.cleanup()


class TestMissingSettingsClassification:
    """Class 1 — missing settings fail at startup, not at probe time."""

    def test_missing_url_raises_actionable_configuration_error(self):
        settings = Settings(
            _env_file=None,
            environment="test",
            database_required=True,
            database_url=None,
        )
        with pytest.raises(DatabaseConfigurationError) as excinfo:
            create_app(settings=settings)
        message = str(excinfo.value)
        # Actionable: names the settings to fix.
        assert "PEIARS_DATABASE_URL" in message
        assert "database_required" in message
        # Sanitized: no credentials, connection strings, or paths.
        for forbidden in ("password", "postgresql://", "postgres@", "/tmp"):
            assert forbidden not in message.lower()


class TestConnectionFailureClassification:
    """Class 2 — an unreachable endpoint is a readiness failure, not a
    startup configuration error, and never affects liveness."""

    @staticmethod
    def _free_port() -> int:
        """A TCP port that is guaranteed to have nothing listening."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def test_connection_refused_readiness_503_liveness_200(self):
        port = self._free_port()
        url = f"postgresql+psycopg://peiars:unused@127.0.0.1:{port}/peiars"
        app = create_app(settings=_test_settings(url))
        client = TestClient(app)

        ready = client.get("/api/v1/health/ready")
        assert ready.status_code == 503
        body = ready.json()
        assert body["error"]["code"] == "SERVICE_NOT_READY"
        failed_names = [
            check["name"] for check in body["error"]["details"]["failed_checks"]
        ]
        assert "postgresql" in failed_names
        # Sanitized: no endpoint, port, or driver detail leaks.
        body_text = str(body).lower()
        for forbidden in (str(port), "password", "psycopg", "connection refused"):
            assert forbidden not in body_text

        live = client.get("/api/v1/health/live")
        assert live.status_code == 200
        assert live.json()["status"] == "alive"

    def test_nonexistent_database_same_sanitized_class(self, db_url):
        """A reachable server rejecting the database (3D000) classifies
        identically to an unreachable endpoint — by design, no detail
        about the rejection reason is exposed."""
        bad_url = str(make_url(db_url).set(database="peiars_nonexistent_db"))
        app = create_app(settings=_test_settings(bad_url))
        client = TestClient(app)

        ready = client.get("/api/v1/health/ready")
        assert ready.status_code == 503
        body = ready.json()
        failed_names = [
            check["name"] for check in body["error"]["details"]["failed_checks"]
        ]
        assert "postgresql" in failed_names
        assert "peiars_nonexistent_db" not in str(body)


class TestCredentialFailureClassification:
    """Class 3 — real PostgreSQL rejecting a wrong password.

    Uses the ``scram_database`` fixture (its own dedicated disposable
    pgserver instance — see the fixture docstring for the isolation
    guarantee and cleanup behaviour) so the server genuinely verifies
    the password; pgserver's default trust auth would accept anything.
    """

    def test_wrong_password_readiness_503_sanitized(self, scram_database):
        admin_uri = scram_database
        base = make_url(admin_uri)
        good_url = base.set(
            username="peiars_cred_user",
            password="correct-horse-battery-staple",
            database="peiars_credtest",
        ).render_as_string(hide_password=False)
        wrong_url = base.set(
            username="peiars_cred_user",
            password="totally-wrong-password",
            database="peiars_credtest",
        ).render_as_string(hide_password=False)

        # Control: the CORRECT password connects — proves the SCRAM rule is
        # active and the failure below is credential-based, not an unrelated
        # connection problem.
        control_engine = create_engine(good_url)
        with control_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        control_engine.dispose()

        app = create_app(settings=_test_settings(wrong_url))
        with TestClient(app) as client:
            ready = client.get("/api/v1/health/ready")
            assert ready.status_code == 503
            body = ready.json()
            assert body["error"]["code"] == "SERVICE_NOT_READY"
            failed_names = [
                check["name"] for check in body["error"]["details"]["failed_checks"]
            ]
            assert "postgresql" in failed_names
        # Sanitized: neither password nor the server's rejection detail leaks.
        body_text = str(body).lower()
        for forbidden in (
            "totally-wrong-password",
            "correct-horse",
            "password authentication failed",
            "28p01",
        ):
            assert forbidden not in body_text


class TestMigrationReadinessClassification:
    """Class 4 — the boot verification detects missing/incompatible schema.

    PR-06A final correction §5: an empty database used to pass
    ``/health/ready`` because the probe was only ``SELECT 1``. The
    endpoint now ALSO runs a read-only schema-state check: the
    database's ``alembic_version`` must equal the committed migrations'
    head revision. A reachable-but-unmigrated (or older-revision)
    database therefore fails readiness with the ``migrations`` check
    while the ``postgresql`` connectivity check stays ready — the two
    failure classes are distinguishable without leaking schema detail.
    Migrations are still never applied automatically; the documented
    remediation is an explicit ``alembic upgrade head`` (verified in the
    third test below).
    """

    @staticmethod
    def _create_database(pg_server, name: str) -> str:
        """Create (dropping first) a dedicated database; return its URL."""
        admin_uri = pg_server.get_uri()
        admin_engine = create_engine(admin_uri, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {name}"))
            conn.execute(text(f"CREATE DATABASE {name}"))
        admin_engine.dispose()
        return str(make_url(admin_uri).set(database=name))

    @staticmethod
    def _drop_database(pg_server, name: str) -> None:
        admin_engine = create_engine(pg_server.get_uri(), isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {name}"))
        admin_engine.dispose()

    @staticmethod
    def _alembic_config():
        from alembic.config import Config

        cfg = Config("alembic.ini")
        cfg.set_main_option("script_location", "migrations")
        return cfg

    def test_unmigrated_database_fails_boot_verification(self, pg_server):
        """Empty database: connectivity ready, migrations check failed → 503."""
        empty_url = self._create_database(pg_server, "peiars_unmigrated")
        try:
            app = create_app(settings=_test_settings(empty_url))
            with TestClient(app) as client:
                # The context manager runs the shutdown event, which
                # disposes the application's connection pool — required
                # before the DROP DATABASE below.
                ready = client.get("/api/v1/health/ready")
                assert ready.status_code == 503
                body = ready.json()
                assert body["error"]["code"] == "SERVICE_NOT_READY"
                details = body["error"]["details"]
                failed_names = [c["name"] for c in details["failed_checks"]]
                # NOTE: failed_checks is a list of {name, status} objects;
                # ready_checks is a plain sorted list of names (existing
                # 503 contract — preserved).
                ready_names = details["ready_checks"]
                # The schema failure is distinguished from a connection
                # failure: connectivity itself is READY.
                assert "migrations" in failed_names
                assert "postgresql" in ready_names
                # Sanitized: no schema internals or revision ids leak.
                body_text = str(body)
                assert "alembic_version" not in body_text
                assert _HEAD_REVISION not in body_text
        finally:
            self._drop_database(pg_server, "peiars_unmigrated")

    def test_older_revision_fails_boot_verification(self, pg_server, monkeypatch):
        """A database at the parent revision is incompatible → 503.

        Migrations are applied EXPLICITLY here (never by the application)
        up to the parent of head, proving the check detects an outdated
        schema even when every applied migration succeeded.
        """
        from alembic import command

        partial_url = self._create_database(pg_server, "peiars_partial_schema")
        monkeypatch.setenv("PEIARS_DATABASE_URL", partial_url)
        command.upgrade(self._alembic_config(), _PARENT_REVISION)
        try:
            app = create_app(settings=_test_settings(partial_url))
            with TestClient(app) as client:
                ready = client.get("/api/v1/health/ready")
                assert ready.status_code == 503
                details = ready.json()["error"]["details"]
                failed_names = [c["name"] for c in details["failed_checks"]]
                ready_names = details["ready_checks"]
                assert "migrations" in failed_names
                assert "postgresql" in ready_names
        finally:
            self._drop_database(pg_server, "peiars_partial_schema")

    def test_upgrade_to_head_restores_readiness(self, pg_server, monkeypatch):
        """The documented remediation (``alembic upgrade head``) → 200."""
        from alembic import command

        recover_url = self._create_database(pg_server, "peiars_recovered_schema")
        monkeypatch.setenv("PEIARS_DATABASE_URL", recover_url)
        command.upgrade(self._alembic_config(), "head")
        try:
            app = create_app(settings=_test_settings(recover_url))
            with TestClient(app) as client:
                ready = client.get("/api/v1/health/ready")
                assert ready.status_code == 200
                body = ready.json()
                check_names = [c["name"] for c in body["checks"]]
                assert "postgresql" in check_names
                assert "migrations" in check_names
                assert all(c["status"] == "ready" for c in body["checks"])
        finally:
            self._drop_database(pg_server, "peiars_recovered_schema")

    def test_schema_queries_fail_against_unmigrated_database(self, pg_server):
        """What the pre-correction test pinned directly: schema queries
        on an empty database fail with a missing-relation error — the
        failure mode the readiness check exists to catch. The failure
        mode is unchanged; only its detection moved into the boot
        verification (first test in this class)."""
        empty_url = self._create_database(pg_server, "peiars_unmigrated2")
        try:
            engine = create_engine(empty_url)
            with pytest.raises(ProgrammingError) as excinfo:
                with engine.connect() as conn:
                    conn.execute(text("SELECT * FROM review_cases"))
            assert "review_cases" in str(excinfo.value)
            engine.dispose()
        finally:
            self._drop_database(pg_server, "peiars_unmigrated2")
