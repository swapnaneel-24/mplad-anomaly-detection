"""Request-ID middleware and logging tests."""

from __future__ import annotations

import logging
import re

from app.core.middleware import (
    REQUEST_ID_PATTERN,
    JsonFormatter,
    generate_request_id,
    resolve_request_id,
)

_GENERATED = re.compile(r"^[0-9a-f]{32}$")


class TestRequestIdGeneration:
    def test_header_generated_when_absent(self, client):
        response = client.get("/api/v1/health/live")
        request_id = response.headers.get("X-Request-ID")
        assert request_id and _GENERATED.fullmatch(request_id)

    def test_valid_caller_id_is_echoed(self, client):
        response = client.get(
            "/api/v1/health/live", headers={"X-Request-ID": "client-correlation-123"}
        )
        assert response.headers["X-Request-ID"] == "client-correlation-123"

    def test_invalid_caller_id_is_replaced(self, client):
        response = client.get(
            "/api/v1/health/live", headers={"X-Request-ID": "bad id with spaces!"}
        )
        request_id = response.headers["X-Request-ID"]
        assert request_id != "bad id with spaces!"
        assert _GENERATED.fullmatch(request_id)

    def test_overlong_caller_id_is_replaced(self, client):
        overlong = "a" * 65
        response = client.get("/api/v1/health/live", headers={"X-Request-ID": overlong})
        assert response.headers["X-Request-ID"] != overlong

    def test_error_responses_carry_the_request_id(self, client):
        response = client.get("/api/v1/does-not-exist")
        error = response.json()["error"]
        assert response.headers["X-Request-ID"] == error["request_id"]

    def test_unit_resolve_request_id_rules(self):
        assert resolve_request_id(None) != ""
        assert resolve_request_id("valid-id.1_x-2") == "valid-id.1_x-2"
        for invalid in ("", "spaces inside", "斜杠/", "a" * 65, "tab\tchar", "injection\r\nC:"):
            assert not REQUEST_ID_PATTERN.fullmatch(invalid)
            assert resolve_request_id(invalid) != invalid


class TestRequestLogging:
    def test_request_id_appears_in_structured_logs(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="peiars.api"):
            response = client.get("/api/v1/health/live")
        request_id = response.headers["X-Request-ID"]
        matching = [
            record
            for record in caplog.records
            if record.message == "http_request" and getattr(record, "request_id", None) == request_id
        ]
        assert matching, "expected an http_request log line carrying the request id"
        record = matching[0]
        assert record.method == "GET"
        assert record.path == "/api/v1/health/live"
        assert record.status_code == 200

    def test_logs_never_contain_headers_query_or_body_secrets(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="peiars.api"):
            client.get(
                "/api/v1/health/live?api_key=SECRETQUERY",
                headers={
                    "Authorization": "Bearer SECRETTOKEN",
                    "Cookie": "session=SECRETCOOKIE",
                },
            )
        formatted = "\n".join(JsonFormatter().format(record) for record in caplog.records)
        for secret in ("SECRETTOKEN", "SECRETCOOKIE", "SECRETQUERY", "api_key"):
            assert secret not in formatted

    def test_json_log_line_shape(self, client, caplog):
        import json

        with caplog.at_level(logging.INFO, logger="peiars.api"):
            client.get("/api/v1/health/live")
        record = next(r for r in caplog.records if r.message == "http_request")
        payload = json.loads(JsonFormatter().format(record))
        assert payload["message"] == "http_request"
        assert payload["level"] == "INFO"
        assert {"request_id", "method", "path", "status_code", "duration_ms"} <= set(payload)
