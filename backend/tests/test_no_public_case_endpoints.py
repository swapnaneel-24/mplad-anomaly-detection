"""Verify no public case CRUD endpoints exist in PR-03 (PR-03 §14, AC-03-10).

PR-03 deliberately does not expose HTTP endpoints for case creation,
update, note addition, or decision recording. Those are deferred until
an authenticated principal and authorization policy exist (PR-04).

The OpenAPI schema and the router must not advertise any ``/cases``
routes. Internal repository/service interfaces are fully implemented
and tested elsewhere.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestNoPublicCaseEndpoints:
    def test_openapi_has_no_cases_paths(self, client: TestClient):
        schema = client.get("/openapi.json").json()
        paths = set(schema["paths"].keys())
        case_paths = [p for p in paths if "cases" in p.lower()]
        assert case_paths == [], f"unexpected case endpoints in OpenAPI: {case_paths}"

    def test_post_cases_returns_404(self, client: TestClient):
        response = client.post("/api/v1/cases", json={"title": "x"})
        assert response.status_code == 404

    def test_patch_case_returns_404(self, client: TestClient):
        response = client.patch("/api/v1/cases/abc-123", json={"title": "x"})
        assert response.status_code == 404

    def test_post_case_note_returns_404(self, client: TestClient):
        response = client.post("/api/v1/cases/abc-123/notes", json={"note_text": "x"})
        assert response.status_code == 404

    def test_post_case_decision_returns_404(self, client: TestClient):
        response = client.post("/api/v1/cases/abc-123/decisions", json={"rationale": "x"})
        assert response.status_code == 404

    def test_get_cases_returns_404(self, client: TestClient):
        response = client.get("/api/v1/cases")
        assert response.status_code == 404

    def test_get_case_history_returns_404(self, client: TestClient):
        response = client.get("/api/v1/cases/abc-123/history")
        assert response.status_code == 404
