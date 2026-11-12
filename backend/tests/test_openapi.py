"""OpenAPI schema determinism, drift and contract-coverage tests."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import canonical_settings
from app.main import create_app

CONTRACTS_DIR = Path(__file__).resolve().parents[1] / "contracts"
SNAPSHOT_PATH = CONTRACTS_DIR / "openapi.json"

EXPECTED_PATHS = {
    "/api/v1/health/live",
    "/api/v1/health/ready",
    "/api/v1/meta",
    "/api/v1/sources",
    "/api/v1/sources/{source_id}",
    # PR-04: authentication routes.
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/api/v1/auth/me",
    "/api/v1/auth/csrf",
    # PR-05B: synthetic demonstration records + authenticated case API.
    "/api/v1/synthetic/records",
    "/api/v1/synthetic/records/{record_ref}",
    "/api/v1/cases",
    "/api/v1/cases/{case_id}",
    "/api/v1/cases/{case_id}/decisions",
    "/api/v1/cases/{case_id}/history",
    "/api/v1/cases/{case_id}/notes",
    "/api/v1/cases/{case_id}/transitions",
}


def _serialize(schema: dict) -> str:
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


class TestOpenApiDeterminism:
    def test_schema_is_stable_within_one_app(self):
        app = create_app(settings=canonical_settings())
        first = _serialize(app.openapi())
        second = _serialize(app.openapi())
        assert first == second

    def test_schema_is_stable_across_independent_apps(self):
        first = _serialize(create_app(settings=canonical_settings()).openapi())
        second = _serialize(create_app(settings=canonical_settings()).openapi())
        assert first == second

    def test_schema_has_no_timestamps_or_random_ids(self):
        text = _serialize(create_app(settings=canonical_settings()).openapi())
        # The schema must not embed runtime timestamps or per-process
        # random identifiers. The word "uuid" may appear in stable
        # descriptions (e.g. "Case UUID.") — we check for actual UUID
        # values and timestamp patterns instead.
        import re

        assert "timestamp" not in text.lower()
        assert "generated_at" not in text.lower()
        assert "random" not in text.lower()
        # No concrete UUID values (only the descriptive word "UUID").
        assert not re.search(r'"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"', text)


class TestOpenApiContract:
    def test_schema_contains_exactly_the_implemented_paths(self):
        schema = create_app(settings=canonical_settings()).openapi()
        assert set(schema["paths"]) == EXPECTED_PATHS

    def test_error_envelope_is_documented(self):
        schema = create_app(settings=canonical_settings()).openapi()
        assert "ErrorEnvelope" in schema["components"]["schemas"]
        assert "ErrorBody" in schema["components"]["schemas"]

    def test_ready_documents_the_503_error_contract(self):
        schema = create_app(settings=canonical_settings()).openapi()
        responses = schema["paths"]["/api/v1/health/ready"]["get"]["responses"]
        assert "503" in responses
        assert "ErrorEnvelope" in json.dumps(responses["503"])

    def test_source_detail_documents_error_contracts(self):
        schema = create_app(settings=canonical_settings()).openapi()
        responses = schema["paths"]["/api/v1/sources/{source_id}"]["get"]["responses"]
        assert "404" in responses and "422" in responses

    def test_only_get_and_options_methods_present(self):
        schema = create_app(settings=canonical_settings()).openapi()
        for path, operations in schema["paths"].items():
            for method in operations:
                # PR-04 adds POST (auth login/logout); writes remain CSRF-protected.
                assert method in {"get", "options", "post"}, f"unexpected {method} on {path}"

    def test_served_openapi_json_matches_export(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert _serialize(response.json()) == _serialize(
            create_app(settings=canonical_settings()).openapi()
        )


class TestOpenApiDrift:
    def test_committed_snapshot_matches_current_schema(self):
        """Drift guard: regenerate via ``python backend/scripts/export_openapi.py``."""
        assert SNAPSHOT_PATH.exists(), (
            f"missing committed OpenAPI snapshot at {SNAPSHOT_PATH}; "
            "run backend/scripts/export_openapi.py"
        )
        committed = SNAPSHOT_PATH.read_text(encoding="utf-8")
        current = _serialize(create_app(settings=canonical_settings()).openapi())
        assert committed == current, (
            "OpenAPI schema drifted from the committed snapshot. Regenerate "
            "with: python backend/scripts/export_openapi.py"
        )

    def test_export_script_writes_identical_bytes(self, tmp_path):
        import importlib.util

        script_path = Path(__file__).resolve().parents[1] / "scripts" / "export_openapi.py"
        spec = importlib.util.spec_from_file_location("export_openapi_under_test", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        target = tmp_path / "openapi.json"
        target.write_bytes(module.export_schema(target))
        assert target.read_text(encoding="utf-8") == _serialize(
            create_app(settings=canonical_settings()).openapi()
        )
