"""Source-registry service and endpoint tests (architectural seam)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.services.source_registry import (
    EMPTY_SOURCE_REGISTRY,
    SourceDescriptor,
    SourceIdValidationError,
    SourceNotFoundError,
    StaticSourceRegistry,
    validate_source_id,
)

PATH_LIKE_ATTACKS = [
    "../etc/passwd",
    "..",
    "../..",
    "a/b",
    "/absolute/path",
    "C:\\data\\secret",
    "a\\b",
    "src/mplad",
    "results/stream a",
    "..%2Fetc",
    "http://evil.example",
    "file:///etc/passwd",
    "a:b",
    " leading-space",
    "trailing-space ",
    "tab\tid",
    "-leading-dash",
    "trailing-dash-",
    "double--dash",
    "UPPERCASE",
    "under_score",
    "dot.id",
    "a" * 65,
    "",
]

VALID_IDS = [
    "ulb-benchmark",
    "a",
    "pmgsy-iii-2026-snapshot",
    "0starts-with-digit",
    "x" * 64,
]


class TestSourceIdValidation:
    @pytest.mark.parametrize("attack", PATH_LIKE_ATTACKS)
    def test_path_like_and_malformed_ids_rejected(self, attack):
        with pytest.raises(SourceIdValidationError):
            validate_source_id(attack)

    @pytest.mark.parametrize("valid", VALID_IDS)
    def test_valid_opaque_slugs_accepted(self, valid):
        assert validate_source_id(valid) == valid

    def test_non_string_types_rejected(self):
        for bad in (None, 123, 4.5, ["ulb"], {"a": 1}, b"bytes"):
            with pytest.raises(SourceIdValidationError):
                validate_source_id(bad)


class TestStaticRegistry:
    def test_default_registry_is_empty(self):
        assert list(EMPTY_SOURCE_REGISTRY.list_sources()) == []

    def test_unknown_source_raises_not_found(self):
        with pytest.raises(SourceNotFoundError):
            EMPTY_SOURCE_REGISTRY.get_source("ulb-benchmark")

    def test_registry_with_descriptor_lists_and_gets(self):
        descriptor = SourceDescriptor(
            source_id="ulb-benchmark",
            dataset_kind="ulb_benchmark",
            integrity_status="verified",
            analysis_status="verified_benchmark",
        )
        registry = StaticSourceRegistry([descriptor])
        assert list(registry.list_sources()) == [descriptor]
        assert registry.get_source("ulb-benchmark") is descriptor

    def test_duplicate_registration_rejected(self):
        descriptor = SourceDescriptor(
            source_id="dup",
            dataset_kind="ulb_benchmark",
            integrity_status="verified",
            analysis_status="verified_benchmark",
        )
        with pytest.raises(ValueError, match="Duplicate source registration"):
            StaticSourceRegistry([descriptor, descriptor])

    def test_descriptor_construction_validates_the_id(self):
        with pytest.raises(SourceIdValidationError):
            SourceDescriptor(
                source_id="../etc/passwd",
                dataset_kind="ulb_benchmark",
                integrity_status="verified",
                analysis_status="verified_benchmark",
            )


class TestNoFilesystemAccess:
    def test_registry_never_touches_the_filesystem(self, monkeypatch):
        """Prove the seam performs no filesystem operations at all."""

        def _forbidden(*args, **kwargs):
            raise AssertionError("the source registry must not touch the filesystem")

        monkeypatch.setattr("builtins.open", _forbidden)
        monkeypatch.setattr(os, "listdir", _forbidden, raising=True)
        monkeypatch.setattr(os, "scandir", _forbidden, raising=True)
        monkeypatch.setattr(os, "walk", _forbidden, raising=True)

        assert list(EMPTY_SOURCE_REGISTRY.list_sources()) == []
        with pytest.raises(SourceNotFoundError):
            EMPTY_SOURCE_REGISTRY.get_source("ulb-benchmark")


class TestSourceEndpoints:
    def test_list_sources_returns_empty_registry(self, client):
        response = client.get("/api/v1/sources")
        assert response.status_code == 200
        assert response.json() == {"sources": [], "count": 0}

    def test_detail_for_wellformed_unknown_id_is_source_not_found(self, client):
        response = client.get("/api/v1/sources/ulb-benchmark")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "SOURCE_NOT_FOUND"

    @pytest.mark.parametrize(
        "payload",
        [
            "..%5Cetc%5Cpasswd",  # ..\etc\passwd
            "lead%20space",
            "UNDER_score",
            "%2E%2E",  # ..
        ],
    )
    def test_malformed_ids_rejected_through_the_api(self, client, payload):
        response = client.get(f"/api/v1/sources/{payload}")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_SOURCE_ID"

    @pytest.mark.parametrize("payload", ["a%2Fb", "..%2F..%2Fetc%2Fpasswd"])
    def test_slash_containing_paths_degrade_to_routing_404(self, client, payload):
        """Slash payloads are normalized by the HTTP layer and never reach
        a filesystem: they fail routing with the structured 404 envelope."""
        response = client.get(f"/api/v1/sources/{payload}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_registry_endpoint_returns_no_paths(self, client):
        text = client.get("/api/v1/sources").text
        for forbidden in ("/", "\\", "..", "data", "results"):
            assert forbidden not in text
