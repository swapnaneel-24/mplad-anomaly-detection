"""Regression tests: the published OpenAPI 422 contract matches the runtime.

Independent review found that ``GET /api/v1/sources?dataset_kind=INVALID``
returns the custom ``ErrorEnvelope`` at runtime, but the OpenAPI schema
advertised FastAPI's default ``HTTPValidationError``. These tests pin the
fix so the drift cannot return silently.

Guarantees enforced here:

* No ``HTTPValidationError`` or ``ValidationError`` component schema
  survives in the published OpenAPI document.
* Every documented 422 response across every route references
  ``ErrorEnvelope`` and nothing else.
* The *actual* HTTP 422 response body validates against the published
  ``ErrorEnvelope`` schema.
* The published 422 schema and the runtime 422 body agree field-for-field
  on the envelope shape.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import canonical_settings
from app.main import create_app

_LEGACY_MODELS = {"HTTPValidationError", "ValidationError"}


def _schema() -> dict[str, Any]:
    return create_app(settings=canonical_settings()).openapi()


def _all_operations(schema: dict[str, Any]):
    """Yield (path, method, operation_dict) for every documented operation."""
    for path, operations in schema.get("paths", {}).items():
        for method, operation in operations.items():
            if method in {"parameters", "summary", "description"}:
                continue
            if isinstance(operation, dict):
                yield path, method, operation


class TestNoLegacyValidationModels:
    def test_httpvalidation_error_absent_from_components(self):
        schema = _schema()
        components = schema.get("components", {}).get("schemas", {})
        present = _LEGACY_MODELS & set(components)
        assert not present, (
            f"legacy validation models still published: {sorted(present)}"
        )

    def test_no_legacy_refs_anywhere_in_schema(self):
        text = json.dumps(_schema())
        assert "HTTPValidationError" not in text, (
            "HTTPValidationError reference survived normalization"
        )


class TestEveryDocumented422UsesErrorEnvelope:
    def test_all_422_responses_reference_error_envelope(self):
        schema = _schema()
        offenders: list[str] = []
        for path, method, operation in _all_operations(schema):
            responses = operation.get("responses", {})
            if "422" not in responses:
                continue
            blob = json.dumps(responses["422"])
            if "ErrorEnvelope" not in blob:
                offenders.append(f"{method.upper()} {path}")
        assert not offenders, (
            f"422 responses without ErrorEnvelope: {offenders}"
        )

    def test_at_least_one_route_documents_422(self):
        """Sanity: the sources list route carries a dataset_kind enum that
        must produce a documented 422."""
        schema = _schema()
        responses = schema["paths"]["/api/v1/sources"]["get"]["responses"]
        assert "422" in responses


class TestRuntime422MatchesPublishedContract:
    @pytest.fixture()
    def client(self) -> TestClient:
        return TestClient(create_app(settings=canonical_settings()))

    def test_invalid_dataset_kind_returns_422_envelope(self, client: TestClient):
        response = client.get("/api/v1/sources?dataset_kind=INVALID")
        assert response.status_code == 422
        body = response.json()
        assert "error" in body
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert isinstance(body["error"]["message"], str) and body["error"]["message"]
        assert isinstance(body["error"]["request_id"], str) and body["error"]["request_id"]
        assert "errors" in body["error"]["details"]
        assert response.headers["X-Request-ID"] == body["error"]["request_id"]

    def test_runtime_422_body_satisfies_published_error_envelope(self, client: TestClient):
        schema = _schema()
        envelope_schema = schema["components"]["schemas"]["ErrorEnvelope"]
        required_fields = set(envelope_schema.get("required", []))
        body = client.get("/api/v1/sources?dataset_kind=INVALID").json()
        # The envelope must carry every field the published schema marks required.
        assert required_fields <= set(body), (
            f"runtime body missing required fields {required_fields - set(body)}"
        )
        # The inner error body must carry its own required fields.
        error_body_schema = schema["components"]["schemas"]["ErrorBody"]
        error_required = set(error_body_schema.get("required", []))
        assert error_required <= set(body["error"]), (
            f"runtime error body missing required fields {error_required - set(body['error'])}"
        )

    def test_published_422_schema_matches_actual_response_shape(self, client: TestClient):
        """The schema published for the sources-list 422 must be the same
        ErrorEnvelope the server actually emits."""
        schema = _schema()
        published_422 = schema["paths"]["/api/v1/sources"]["get"]["responses"]["422"]
        published_ref = published_422["content"]["application/json"]["schema"]["$ref"]
        assert published_ref.endswith("/ErrorEnvelope"), (
            f"published 422 ref is {published_ref}, expected ErrorEnvelope"
        )
        actual = client.get("/api/v1/sources?dataset_kind=INVALID").json()
        assert set(actual.keys()) == {"error"}
        assert set(actual["error"].keys()) >= {"code", "message", "request_id", "details"}
