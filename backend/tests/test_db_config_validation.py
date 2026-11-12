"""Database configuration validation tests (PR-03 hardening §1).

Covers the four required states:

1. **Database optional and unconfigured**: API starts without PostgreSQL;
   readiness returns 200 with an empty checks list.
2. **Database required but no URL**: application startup fails with a
   sanitized :class:`DatabaseConfigurationError` (the original bug
   produced a misleading 200 with an empty checks list).
3. **Database required and configured but unavailable**: readiness
   returns 503 ``SERVICE_NOT_READY``.
4. **Database required and healthy**: readiness returns 200 with the
   ``postgresql`` probe.

Liveness must remain independent of database connectivity in every state.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url

from app.core.config import Settings
from app.core.config_errors import DatabaseConfigurationError
from app.db.session import DatabaseSessionFactory, create_session_factory
from app.main import create_app
from app.services.db_readiness import maybe_build_postgres_readiness_probe


class TestState1OptionalAndUnconfigured:
    """Database optional and unconfigured: API starts without PostgreSQL."""

    def test_app_starts_without_database(self):
        settings = Settings(
            _env_file=None,
            environment="test",
            database_required=False,
            database_url=None,
        )
        app = create_app(settings=settings)  # must not raise
        assert app.state.db_session_factory is None

    def test_ready_returns_200_with_empty_checks(self):
        settings = Settings(
            _env_file=None,
            environment="test",
            cors_origins=["http://test.example"],
            database_required=False,
            database_url=None,
        )
        client = TestClient(create_app(settings=settings))
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["checks"] == []

    def test_live_independent_of_db(self):
        settings = Settings(
            _env_file=None,
            environment="test",
            database_required=False,
            database_url=None,
        )
        client = TestClient(create_app(settings=settings))
        response = client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_no_db_probe_built(self):
        settings = Settings(
            _env_file=None,
            environment="test",
            database_required=False,
            database_url=None,
        )
        probes = maybe_build_postgres_readiness_probe(settings, None)
        assert probes == []


class TestState2RequiredButNoUrl:
    """Database required but no URL: startup fails with a sanitized error."""

    def test_startup_raises_configuration_error(self):
        settings = Settings(
            _env_file=None,
            environment="test",
            database_required=True,
            database_url=None,
        )
        with pytest.raises(DatabaseConfigurationError) as exc_info:
            create_app(settings=settings)
        msg = str(exc_info.value)
        assert "database_required" in msg
        assert "database_url" in msg

    def test_error_message_contains_no_credentials_or_paths(self):
        settings = Settings(
            _env_file=None,
            environment="test",
            database_required=True,
            database_url=None,
        )
        with pytest.raises(DatabaseConfigurationError) as exc_info:
            create_app(settings=settings)
        msg = str(exc_info.value).lower()
        for forbidden in (
            "password",
            "postgres@",
            "connection string",
            "psycopg://",
            "/home/",
            "c:\\",
            "localhost:5432",
        ):
            assert forbidden not in msg, f"error message leaked {forbidden!r}"

    def test_empty_string_url_also_fails(self):
        """An empty-string URL is normalized to None by the validator."""
        settings = Settings(
            _env_file=None,
            environment="test",
            database_required=True,
            database_url="   ",
        )
        assert settings.database_url is None
        with pytest.raises(DatabaseConfigurationError):
            create_app(settings=settings)

    def test_override_does_not_bypass_validation(self):
        """Even with a session-factory override, required+no-URL must fail.

        The configuration error is a startup invariant: a misconfigured
        deployment must not start, regardless of test-injection shortcuts.
        """
        settings = Settings(
            _env_file=None,
            environment="test",
            database_required=True,
            database_url=None,
        )
        with pytest.raises(DatabaseConfigurationError):
            create_app(
                settings=settings,
                db_session_factory_override=object(),  # type: ignore[arg-type]
            )


class TestState3RequiredConfiguredUnavailable:
    """Database required and configured but unavailable: readiness 503."""

    def _bad_url(self, db_url):
        url = make_url(db_url)
        return str(url.set(database="peiars_nonexistent_db"))

    def test_ready_returns_503(self, db_url):
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

    def test_no_credentials_leak_in_503(self, db_url):
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
        body_text = response.text.lower()
        for forbidden in ("password", "postgres@", "connection string", "psycopg://"):
            assert forbidden not in body_text


class TestState4RequiredAndHealthy:
    """Database required and healthy: readiness 200 with postgresql probe."""

    def test_ready_returns_200_with_postgresql_probe(self, db_client):
        response = db_client.get("/api/v1/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        check_names = [c["name"] for c in body["checks"]]
        assert "postgresql" in check_names

    def test_live_still_200_with_db(self, db_client):
        response = db_client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_probe_reports_ready(self, db_settings, db_session_factory):
        db = DatabaseSessionFactory(
            db_session_factory.kw["bind"], db_session_factory
        )
        probes = maybe_build_postgres_readiness_probe(db_settings, db)
        # PR-06A final correction §5: connectivity + read-only schema state.
        assert [p.name for p in probes] == ["postgresql", "migrations"]
        assert all(p.check() is True for p in probes)
