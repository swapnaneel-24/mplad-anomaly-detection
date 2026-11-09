"""Application factory and settings-isolation tests."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.readiness import ReadinessProbe
from app.services.source_registry import EMPTY_SOURCE_REGISTRY, StaticSourceRegistry


class TestAppFactory:
    def test_create_app_returns_fastapi_with_identity(self, app):
        assert isinstance(app, FastAPI)
        assert app.title == "PEIARS API"
        assert app.version == "0.2.0"

    def test_routes_are_served_under_configured_prefix(self, client):
        response = client.get("/api/v1/health/live")
        assert response.status_code == 200

    def test_prefix_is_configurable(self):
        settings = Settings(_env_file=None, environment="test", api_root_path="/api/v2")
        other = create_app(settings=settings)
        response = TestClient(other).get("/api/v2/health/live")
        assert response.status_code == 200
        assert TestClient(other).get("/api/v1/health/live").status_code == 404

    def test_apps_are_isolated_instances(self):
        first = create_app(settings=Settings(_env_file=None, environment="test"))
        second = create_app(settings=Settings(_env_file=None, environment="test"))
        assert first is not second
        assert first.state.settings is not second.state.settings
        # Both share the immutable empty registry singleton, which is safe.
        assert first.state.source_registry is second.state.source_registry

    def test_default_state_has_empty_source_registry(self, app):
        registry = app.state.source_registry
        assert isinstance(registry, StaticSourceRegistry)
        assert registry is EMPTY_SOURCE_REGISTRY
        assert list(registry.list_sources()) == []

    def test_default_state_has_no_readiness_probes(self, app):
        assert app.state.readiness_probes == ()

    def test_readiness_probes_are_injectable(self, test_settings):
        probes = (ReadinessProbe(name="stub", check=lambda: True),)
        app = create_app(settings=test_settings, readiness_probes=probes)
        assert app.state.readiness_probes == probes

    def test_docs_can_be_disabled(self):
        settings = Settings(_env_file=None, environment="production", docs_enabled=False)
        app = create_app(settings=settings)
        assert app.docs_url is None
        assert app.openapi_url is None

    def test_settings_cors_string_parsing(self):
        settings = Settings(
            _env_file=None,
            cors_origins="http://a.example, http://b.example ,",
        )
        assert settings.cors_origins == ["http://a.example", "http://b.example"]

    def test_settings_rejects_bad_prefix(self):
        try:
            Settings(_env_file=None, api_root_path="api/v1/")
        except Exception as exc:  # pydantic ValidationError
            assert "api_root_path" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("expected validation failure for malformed prefix")

    def test_settings_empty_commit_sha_becomes_none(self):
        settings = Settings(_env_file=None, git_commit_sha="   ")
        assert settings.git_commit_sha is None
