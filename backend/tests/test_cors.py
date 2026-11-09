"""CORS configuration tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


class TestCors:
    def test_allowed_origin_is_permitted(self, client):
        response = client.get(
            "/api/v1/health/live", headers={"Origin": "http://test.example"}
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://test.example"
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_disallowed_origin_gets_no_cors_headers(self, client):
        response = client.get(
            "/api/v1/health/live", headers={"Origin": "http://evil.example"}
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers

    def test_preflight_from_allowed_origin_succeeds(self, client):
        response = client.options(
            "/api/v1/health/live",
            headers={
                "Origin": "http://test.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://test.example"

    def test_preflight_from_disallowed_origin_is_rejected(self, client):
        response = client.options(
            "/api/v1/health/live",
            headers={
                "Origin": "http://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers

    def test_no_wildcard_origin_anywhere(self, client):
        for origin in (None, "http://test.example", "http://evil.example"):
            headers = {"Origin": origin} if origin else {}
            response = client.get("/api/v1/health/live", headers=headers)
            allow = response.headers.get("access-control-allow-origin")
            assert allow != "*"

    def test_multiple_configured_origins_are_all_allowed(self):
        settings = Settings(
            _env_file=None,
            environment="development",
            cors_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        )
        client = TestClient(create_app(settings=settings))
        for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
            response = client.get("/api/v1/health/live", headers={"Origin": origin})
            assert response.headers.get("access-control-allow-origin") == origin
