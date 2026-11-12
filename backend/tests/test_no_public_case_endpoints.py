"""Verify the authenticated case API is present and requires auth (PR-05B §6).

PR-05B introduces the public case API (``/api/v1/cases`` and sub-routes).
This test replaces the PR-03 ``test_no_public_case_endpoints.py`` which
asserted the absence of those endpoints. The case endpoints now exist
but every endpoint requires authentication (401 without a session).
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestCaseEndpointsRequireAuth:
    """The case API exists but rejects anonymous requests."""

    def test_openapi_has_cases_paths(self, client: TestClient):
        schema = client.get("/openapi.json").json()
        paths = set(schema["paths"].keys())
        case_paths = [p for p in paths if "cases" in p.lower()]
        assert case_paths, f"expected /cases endpoints in OpenAPI, got: {paths}"

    def test_get_cases_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/cases")
        assert response.status_code == 401

    def test_post_cases_requires_auth(self, client: TestClient):
        response = client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "x",
                "created_by": "someone",
            },
        )
        # 401 (no session) or 503 (CSRF cannot sign without session_secret)
        # — both mean the request was rejected without creating a case.
        assert response.status_code in (401, 503)

    def test_get_case_by_id_requires_auth(self, client: TestClient):
        response = client.get("/api/v1/cases/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 401

    def test_get_case_history_requires_auth(self, client: TestClient):
        response = client.get(
            "/api/v1/cases/00000000-0000-0000-0000-000000000000/history"
        )
        assert response.status_code == 401

    def test_post_case_note_requires_auth(self, client: TestClient):
        response = client.post(
            "/api/v1/cases/00000000-0000-0000-0000-000000000000/notes",
            json={"note_text": "x", "actor_ref": "r1", "expected_version": 1},
        )
        assert response.status_code in (401, 503)

    def test_post_case_transition_requires_auth(self, client: TestClient):
        response = client.post(
            "/api/v1/cases/00000000-0000-0000-0000-000000000000/transitions",
            json={
                "to_status": "under_review",
                "reason": "starting review",
                "actor_ref": "r1",
                "expected_version": 1,
            },
        )
        assert response.status_code in (401, 503)

    def test_post_case_decision_requires_auth(self, client: TestClient):
        response = client.post(
            "/api/v1/cases/00000000-0000-0000-0000-000000000000/decisions",
            json={
                "outcome": "explained_deviation",
                "rationale": "explained",
                "actor_ref": "r1",
                "expected_version": 1,
            },
        )
        assert response.status_code in (401, 503)
