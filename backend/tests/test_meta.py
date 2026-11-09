"""Metadata endpoint tests."""

from __future__ import annotations

import json


class TestMeta:
    def test_meta_returns_expected_fields(self, client):
        response = client.get("/api/v1/meta")
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {
            "application",
            "api_version",
            "app_version",
            "git_commit_sha",
            "environment",
            "features",
            "subsystems",
        }
        assert body["application"] == "PEIARS API"
        assert body["api_version"] == "v1"
        assert body["app_version"] == "0.2.0"
        assert body["environment"] == "test"

    def test_git_commit_sha_is_null_when_not_supplied(self, client):
        """The API never fabricates a commit SHA."""
        body = client.get("/api/v1/meta").json()
        assert body["git_commit_sha"] is None

    def test_git_commit_sha_echoed_when_supplied_by_deployment(self):
        from app.core.config import Settings
        from app.main import create_app
        from fastapi.testclient import TestClient

        settings = Settings(
            _env_file=None,
            environment="production",
            git_commit_sha="abc123def4567890",
        )
        client = TestClient(create_app(settings=settings))
        body = client.get("/api/v1/meta").json()
        assert body["git_commit_sha"] == "abc123def4567890"
        assert body["environment"] == "production"

    def test_features_distinguish_implemented_from_planned(self, client):
        features = client.get("/api/v1/meta").json()["features"]
        assert features["health_endpoints"] == "implemented"
        assert features["source_registry_interface"] == "implemented"
        assert features["database"] == "planned"
        assert features["authentication"] == "planned"
        assert features["case_management"] == "planned"
        assert set(features.values()) <= {"implemented", "planned"}

    def test_subsystems_report_availability(self, client):
        subsystems = client.get("/api/v1/meta").json()["subsystems"]
        assert subsystems["api"] == "available"
        assert subsystems["source_registry"] == "available"
        assert subsystems["database"] == "not_integrated"
        assert subsystems["authentication"] == "not_integrated"

    def test_meta_contains_no_secrets_paths_or_hostnames(self, client):
        text = client.get("/api/v1/meta").text.lower()
        for forbidden in (
            "peiars_db_password",
            "peiars_session_secret",
            "change_me",
            "password",
            "secret",
            "/home/",
            "c:\\",
            "localhost:5173",
            "127.0.0.1",
        ):
            assert forbidden not in text, f"meta leaked {forbidden!r}"

    def test_meta_is_valid_json_with_stable_key_order_independent_content(self, client):
        body = json.loads(client.get("/api/v1/meta").text)
        assert isinstance(body["features"], dict)
        assert isinstance(body["subsystems"], dict)
