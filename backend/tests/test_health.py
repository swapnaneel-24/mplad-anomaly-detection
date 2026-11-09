"""Health endpoint tests: liveness and readiness behaviour."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.readiness import ReadinessProbe


class TestLiveness:
    def test_live_returns_200_alive(self, client):
        response = client.get("/api/v1/health/live")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "alive"
        assert body["service"] == "PEIARS API"
        assert set(body) == {"status", "service", "version"}

    def test_live_has_request_id_header(self, client):
        response = client.get("/api/v1/health/live")
        assert response.headers.get("X-Request-ID")

    def test_live_ignores_failing_readiness_probes(self, test_settings):
        app = create_app(
            settings=test_settings,
            readiness_probes=(ReadinessProbe(name="broken", check=lambda: False),),
        )
        response = TestClient(app).get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"


class TestReadiness:
    def test_default_ready_with_no_configured_dependencies(self, client):
        """PR-02 policy: zero required dependencies configured."""
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["checks"] == []

    def test_default_does_not_pretend_to_check_a_database(self, client):
        """No fake DB readiness assertions: the checks list is honestly empty."""
        body = client.get("/api/v1/health/ready").json()
        assert all("database" != check["name"] for check in body["checks"])

    def test_ready_with_healthy_injected_probe(self, test_settings):
        app = create_app(
            settings=test_settings,
            readiness_probes=(ReadinessProbe(name="stub-dependency", check=lambda: True),),
        )
        response = TestClient(app).get("/api/v1/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["checks"] == [{"name": "stub-dependency", "status": "ready"}]

    def test_ready_503_when_injected_probe_fails(self, test_settings):
        app = create_app(
            settings=test_settings,
            readiness_probes=(ReadinessProbe(name="stub-dependency", check=lambda: False),),
        )
        response = TestClient(app).get("/api/v1/health/ready")
        assert response.status_code == 503
        error = response.json()["error"]
        assert error["code"] == "SERVICE_NOT_READY"
        assert error["request_id"]
        failed = error["details"]["failed_checks"]
        assert failed == [{"name": "stub-dependency", "status": "unavailable"}]
        assert error["details"]["ready_checks"] == []

    def test_ready_503_reports_only_names_not_exception_details(self, test_settings):
        def exploding():
            raise RuntimeError("postgres://secret-user:secret-password@internal-host:5432/db")

        app = create_app(
            settings=test_settings,
            readiness_probes=(ReadinessProbe(name="stub-dependency", check=exploding),),
        )
        response = TestClient(app).get("/api/v1/health/ready")
        assert response.status_code == 503
        text = response.text
        assert "secret-password" not in text
        assert "internal-host" not in text
        assert "RuntimeError" not in text

    def test_ready_mixed_probes_yield_503_with_both_states(self, test_settings):
        probes = (
            ReadinessProbe(name="healthy", check=lambda: True),
            ReadinessProbe(name="unhealthy", check=lambda: False),
        )
        app = create_app(settings=test_settings, readiness_probes=probes)
        response = TestClient(app).get("/api/v1/health/ready")
        assert response.status_code == 503
        details = response.json()["error"]["details"]
        assert [c["name"] for c in details["failed_checks"]] == ["unhealthy"]
        assert details["ready_checks"] == ["healthy"]

    def test_ready_response_contract_shape(self, client):
        body = client.get("/api/v1/health/ready").json()
        assert set(body) == {"status", "checks"}

    def test_probe_requires_non_empty_name(self):
        try:
            ReadinessProbe(name=" ", check=lambda: True)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("empty probe name must be rejected")
