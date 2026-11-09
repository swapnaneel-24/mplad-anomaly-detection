"""Structured error contract tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


class TestErrorEnvelope:
    def test_unknown_route_returns_structured_404(self, client):
        response = client.get("/api/v1/does-not-exist")
        assert response.status_code == 404
        error = response.json()["error"]
        assert set(error) == {"code", "message", "request_id", "details"}
        assert error["code"] == "NOT_FOUND"
        assert error["request_id"]
        assert response.headers.get("X-Request-ID") == error["request_id"]

    def test_method_not_allowed_returns_structured_405(self, client):
        response = client.post("/api/v1/health/live")
        assert response.status_code == 405
        assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"

    def test_validation_error_uses_the_envelope(self, client):
        response = client.get("/api/v1/sources", params={"dataset_kind": "not-a-kind"})
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert error["details"]["errors"]
        first = error["details"]["errors"][0]
        assert set(first) == {"loc", "msg", "type"}
        assert first["loc"] == ["query", "dataset_kind"]

    def test_validation_error_does_not_echo_request_input(self, client):
        """Request bodies/values must never be reflected in error responses."""
        response = client.get(
            "/api/v1/sources", params={"dataset_kind": "SECRET_TOKEN_VALUE_42"}
        )
        assert response.status_code == 422
        assert "SECRET_TOKEN_VALUE_42" not in response.text

    def test_invalid_source_id_returns_422_envelope(self, client):
        response = client.get("/api/v1/sources/..%5Cetc%5Cpasswd")  # "..\etc\passwd"
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "INVALID_SOURCE_ID"

    def test_unknown_but_wellformed_source_returns_404_envelope(self, client):
        response = client.get("/api/v1/sources/ulb-benchmark")
        assert response.status_code == 404
        error = response.json()["error"]
        assert error["code"] == "SOURCE_NOT_FOUND"
        assert error["details"] == {"source_id": "ulb-benchmark"}


class TestUnhandledExceptions:
    def _boom_app(self) -> TestClient:
        settings = Settings(_env_file=None, environment="test")
        app = create_app(settings=settings)

        @app.get("/api/v1/_test/boom")
        async def _boom() -> dict:
            raise RuntimeError("internal detail /home/secret/path must not leak")

        return TestClient(app, raise_server_exceptions=False)

    def test_unhandled_exception_returns_sanitized_500(self):
        client = self._boom_app()
        response = client.get("/api/v1/_test/boom")
        assert response.status_code == 500
        error = response.json()["error"]
        assert error["code"] == "INTERNAL_SERVER_ERROR"
        assert error["request_id"]
        assert response.headers.get("X-Request-ID") == error["request_id"]

    def test_unhandled_exception_hides_tracebacks_and_paths(self):
        client = self._boom_app()
        text = client.get("/api/v1/_test/boom").text
        for forbidden in ("Traceback", "RuntimeError", "/home/secret/path", "raise "):
            assert forbidden not in text

    def test_error_messages_are_stable_across_calls(self):
        client = self._boom_app()
        first = client.get("/api/v1/_test/boom").json()["error"]
        second = client.get("/api/v1/_test/boom").json()["error"]
        assert first["code"] == second["code"]
        assert first["message"] == second["message"]
