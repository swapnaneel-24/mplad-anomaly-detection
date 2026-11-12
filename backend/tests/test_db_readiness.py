"""Database readiness integration tests (real PostgreSQL + TestClient).

Verifies (PR-03 §13, AC-03-08, AC-03-09):

* When PostgreSQL is configured as required, readiness tests actual
  connectivity and reports 200 with the probe name.
* When PostgreSQL is configured but unavailable, readiness reports 503
  with the sanitized SERVICE_NOT_READY contract.
* Liveness remains independent of PostgreSQL availability.
* When the database is not configured, readiness behaves as in PR-02
  (no required dependencies — not an implicit DB verification).
* No connection strings, credentials, or internal exception details leak.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.session import DatabaseSessionFactory, create_session_factory
from app.main import create_app
from app.services.db_readiness import maybe_build_postgres_readiness_probe
from app.services.readiness import ReadinessProbe


class TestReadinessNotConfigured:
    """When the database is not configured, readiness is as in PR-02."""

    def test_no_db_probe_when_not_required(self, test_settings):
        probes = maybe_build_postgres_readiness_probe(test_settings, None)
        assert probes == []

    def test_ready_returns_200_with_empty_checks(self, client):
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["checks"] == []

    def test_live_independent_of_db(self, client):
        response = client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"


class TestReadinessConfiguredHealthy:
    """When PostgreSQL is configured and healthy, readiness reports 200."""

    def test_db_probe_reports_ready(self, db_settings, db_session_factory):
        db = DatabaseSessionFactory(db_session_factory.kw["bind"], db_session_factory)
        probes = maybe_build_postgres_readiness_probe(db_settings, db)
        # PR-06A final correction §5: two probes — connectivity (SELECT 1)
        # and read-only schema state (alembic_version == committed head).
        assert [p.name for p in probes] == ["postgresql", "migrations"]
        assert all(p.check() is True for p in probes)

    def test_migrations_probe_matches_committed_head(self, db_session_factory):
        """The schema-state probe compares against the committed head.

        The migrated test database sits at head, and the committed
        migrations directory's head must be exactly that revision.
        """
        from sqlalchemy import text

        from app.services.db_readiness import _committed_head_revision

        db = DatabaseSessionFactory(db_session_factory.kw["bind"], db_session_factory)
        with db.engine.connect() as conn:
            applied = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert _committed_head_revision() == applied

    def test_ready_endpoint_200_with_db(self, db_client):
        response = db_client.get("/api/v1/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        check_names = [c["name"] for c in body["checks"]]
        assert "postgresql" in check_names
        assert "migrations" in check_names

    def test_live_still_200_with_db(self, db_client):
        response = db_client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"


class TestReadinessConfiguredUnavailable:
    """When PostgreSQL is configured but unavailable, readiness reports 503."""

    def _bad_url(self, db_url):
        from sqlalchemy import make_url

        url = make_url(db_url)
        return str(url.set(database="peiars_nonexistent_db"))

    def test_db_probe_reports_unavailable_when_down(self, db_url):
        bad_url = self._bad_url(db_url)
        settings = Settings(
            _env_file=None,
            environment="test",
            database_url=bad_url,
            database_required=True,
        )
        bad_engine = create_engine(bad_url, pool_pre_ping=True)
        db = DatabaseSessionFactory(bad_engine, create_session_factory(bad_engine))
        probes = maybe_build_postgres_readiness_probe(settings, db)
        # Both probes fail when the server rejects the connection: the
        # schema-state probe cannot run without connectivity either.
        assert [p.name for p in probes] == ["postgresql", "migrations"]
        assert all(p.check() is False for p in probes)

    def test_ready_endpoint_503_when_db_unavailable(self, db_url):
        bad_url = self._bad_url(db_url)
        settings = Settings(
            _env_file=None,
            environment="test",
            cors_origins=["http://test.example"],
            database_url=bad_url,
            database_required=True,
        )
        app = create_app(settings=settings)
        client = TestClient(app)
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["error"]["code"] == "SERVICE_NOT_READY"
        # No connection details leak.
        body_text = str(body).lower()
        for forbidden in ("password", "postgres@", "connection string", "psycopg"):
            assert forbidden not in body_text
        # The probe name is reported.
        assert "postgresql" in str(body)

    def test_live_still_200_when_db_unavailable(self, db_url):
        bad_url = self._bad_url(db_url)
        settings = Settings(
            _env_file=None,
            environment="test",
            cors_origins=["http://test.example"],
            database_url=bad_url,
            database_required=True,
        )
        app = create_app(settings=settings)
        client = TestClient(app)
        response = client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"


class TestReadinessNoLeakage:
    def test_readiness_response_contains_no_credentials(self, db_client):
        response = db_client.get("/api/v1/health/ready")
        text = response.text.lower()
        for forbidden in ("password", "secret", "credential", "postgresql://", "psycopg"):
            assert forbidden not in text
