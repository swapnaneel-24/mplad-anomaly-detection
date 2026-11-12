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
        assert body["app_version"] == "0.4.0"
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
        # PR-03 added implemented persistence features.
        assert features["review_case_persistence"] == "implemented"
        assert features["append_only_case_history"] == "implemented"
        assert features["optimistic_concurrency"] == "implemented"
        # PR-04 added implemented authentication features.
        assert features["local_account_authentication"] == "implemented"
        assert features["server_side_sessions"] == "implemented"
        assert features["role_based_authorization"] == "implemented"
        assert features["csrf_protection"] == "implemented"
        assert features["login_throttling"] == "implemented"
        assert features["authenticated_actor_identity"] == "implemented"
        # PR-05B added implemented case API + synthetic source.
        assert features["public_case_api"] == "implemented"
        assert features["synthetic_demonstration_source"] == "implemented"
        assert features["investigation_workflow"] == "implemented"
        # Still planned.
        assert features["user_management_api"] == "planned"
        assert features["research_evidence_access"] == "planned"
        assert set(features.values()) <= {"implemented", "planned"}

    def test_subsystems_report_availability(self, client):
        subsystems = client.get("/api/v1/meta").json()["subsystems"]
        assert subsystems["api"] == "available"
        assert subsystems["source_registry"] == "available"
        # PR-03: persistence subsystem is available (internal repo/service).
        assert subsystems["review_case_persistence"] == "available"
        assert subsystems["database"] == "available"
        # PR-04: authentication is available.
        assert subsystems["authentication"] == "available"
        # PR-05B: public case API + synthetic source are available.
        assert subsystems["public_case_api"] == "available"
        assert subsystems["synthetic_demonstration_source"] == "available"
        # Not yet integrated.
        assert subsystems["research_evidence_service"] == "not_integrated"

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
