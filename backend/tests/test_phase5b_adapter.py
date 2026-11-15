"""Phase 5B adapter tests (PR-11).

Covers the test matrix from the PR-11 implementation contract:

* Catalog identity (8 canonical figures, correct numbering, allowlisted filenames).
* Three-way consistency (PNG <-> catalog <-> figure manifest).
* Manifest trust (pin stability, tamper detection, cache-mutation detection).
* Plot metadata and catalog CSV tampering.
* DVC absence handling (individual payload, individual pointer, catalog CSV).
* Independent per-image availability.
* Digest verification (MD5, SHA-256, size).
* Binary format validation (signature, IHDR, dimensions, size bounds).
* Path security (figure_no is the only input; no filename/path parameter).
* Cache-mutation recovery (tamper -> fail closed -> restore -> verified).
* Publication gate (default disabled, explicit enabled, direct URL blocked).
* API security (no filesystem paths, secrets, or stack traces in errors).
* Traceability (source-native (a)/(b)/(c), RQ1-RQ6, historical companion).
* Frozen evidence integrity (28/28).
* Real-DVC trusted-lane acceptance (skipped when payloads absent).

The tests never mutate the real DVC payloads. The `_isolated_figure_tree`
context manager copies the figures directory into a temp repo and patches
the module-level constants so the service reads from the copy. Manifest
bytes are preserved byte-for-byte, so the trusted pin continues to match
unless a test explicitly tampers with the manifest.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
import subprocess
import sys
import zlib
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services import phase5b_catalog as svc
from app.services.phase5b_catalog import (
    PHASE5B_CATALOG_SERVICE,
    Phase5BIntegrityError,
    TRUSTED_PHASE5_PLOT_COMMIT_MANIFEST_SHA256,
    _validate_png,
)

PROTOCOL_PATH = "/api/v1/research/phase5b"
_REAL_FIGURES_DIR = svc.PHASE5_FIGURES_DIR


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, environment="test", docs_enabled=True, **overrides)


def _client(publication_enabled: bool = False) -> TestClient:
    app = create_app(
        settings=_settings(phase5b_public_figures_enabled=publication_enabled)
    )
    return TestClient(app)


@contextmanager
def _isolated_figure_tree(tmp_path: Path):
    """Copy the real figures tree into a temp repo and patch module constants.

    The manifest bytes are preserved exactly, so the trusted pin matches
    unless a test explicitly tampered with the manifest.
    """
    fake_repo = tmp_path / "repo"
    figures_dir = (
        fake_repo / "results" / "stream a" / "phase 5" / "figures" / "reproduction"
    )
    figures_dir.mkdir(parents=True, exist_ok=True)
    for item in _REAL_FIGURES_DIR.iterdir():
        if item.is_file():
            shutil.copy2(item, figures_dir / item.name)
    with patch.object(svc, "REPO_ROOT", fake_repo), patch.object(
        svc, "PHASE5_FIGURES_DIR", figures_dir
    ):
        yield {"repo": fake_repo, "figures_dir": figures_dir}


def _png_with_dimensions(width: int, height: int, *, include_ihdr: bool = True) -> bytes:
    """Build a minimal PNG-like byte sequence with controllable structure."""
    sig = b"\x89PNG\r\n\x1a\n"
    if not include_ihdr:
        return sig + b"\x00" * 2000
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    return sig + ihdr + b"\x00" * 2000


# ---------------------------------------------------------------------------
# A. Catalog identity
# ---------------------------------------------------------------------------


class TestCatalogIdentity:
    def test_returns_exactly_eight_figures(self):
        client = _client()
        r = client.get(f"{PROTOCOL_PATH}/catalog")
        assert r.status_code == 200
        assert len(r.json()["figures"]) == 8

    def test_figure_numbers_are_1_through_8_in_order(self):
        client = _client()
        figures = client.get(f"{PROTOCOL_PATH}/catalog").json()["figures"]
        assert [f["figure_no"] for f in figures] == list(range(1, 9))

    def test_filenames_match_allowlist(self):
        client = _client()
        figures = client.get(f"{PROTOCOL_PATH}/catalog").json()["figures"]
        for f in figures:
            assert f["filename"] == svc._CANONICAL_FIGURES[f["figure_no"]]

    def test_source_and_dataset_identity(self):
        client = _client()
        data = client.get(f"{PROTOCOL_PATH}/catalog").json()
        assert data["phase"] == "5B"
        assert data["stream"] == "A"
        assert data["models_fitted"] == 0
        assert data["source_id"] == "phase5b-figure-gallery"

    def test_manifest_status_is_verified(self):
        client = _client()
        data = client.get(f"{PROTOCOL_PATH}/catalog").json()
        assert data["manifest_status"] == "verified"


# ---------------------------------------------------------------------------
# B. Three-way consistency
# ---------------------------------------------------------------------------


class TestThreeWayConsistency:
    def test_catalog_metadata_available(self):
        client = _client()
        data = client.get(f"{PROTOCOL_PATH}/catalog").json()
        assert data["catalog_metadata_available"] is True

    def test_each_png_matches_catalog_filename_and_title(self):
        client = _client()
        figures = client.get(f"{PROTOCOL_PATH}/catalog").json()["figures"]
        for f in figures:
            assert f["filename"].endswith(".png")
            # Title comes from the catalog CSV; present when CSV is materialized.
            assert f["title"] is not None
            assert isinstance(f["title"], str)


# ---------------------------------------------------------------------------
# C. Manifest trust
# ---------------------------------------------------------------------------


class TestManifestTrust:
    def test_pin_matches_current_manifest_lf_hash(self):
        raw = (svc.REPO_ROOT / svc.PHASE5_PLOT_MANIFEST_REL).read_bytes()
        canonical = svc.trust.canonicalize_frozen_checker(raw)
        actual = hashlib.sha256(canonical).hexdigest()
        assert actual == TRUSTED_PHASE5_PLOT_COMMIT_MANIFEST_SHA256

    def test_tampered_manifest_fails_pin(self, tmp_path):
        with _isolated_figure_tree(tmp_path) as tree:
            manifest = tree["figures_dir"] / "phase5_plot_commit_manifest.json"
            manifest.write_bytes(manifest.read_bytes() + b"\n")
            client = _client()
            r = client.get(f"{PROTOCOL_PATH}/catalog")
            assert r.status_code == 503
            assert r.json()["error"]["details"]["reason"] == "integrity_failed"

    def test_missing_manifest_is_artifact_missing(self, tmp_path):
        with _isolated_figure_tree(tmp_path) as tree:
            (tree["figures_dir"] / "phase5_plot_commit_manifest.json").unlink()
            client = _client()
            r = client.get(f"{PROTOCOL_PATH}/catalog")
            assert r.status_code == 503
            assert r.json()["error"]["details"]["reason"] == "artifact_missing"


# ---------------------------------------------------------------------------
# D. Metadata tampering
# ---------------------------------------------------------------------------


class TestMetadataTampering:
    def test_tampered_plot_metadata_fails(self, tmp_path):
        with _isolated_figure_tree(tmp_path) as tree:
            p = tree["figures_dir"] / "phase5_plot_metadata.json"
            raw = p.read_bytes()
            p.write_bytes(raw[:-1] + b" ")  # change last byte
            client = _client()
            r = client.get(f"{PROTOCOL_PATH}/catalog")
            assert r.status_code == 503
            assert r.json()["error"]["details"]["reason"] == "integrity_failed"

    def test_tampered_catalog_csv_fails(self, tmp_path):
        with _isolated_figure_tree(tmp_path) as tree:
            p = tree["figures_dir"] / "phase5_figure_catalog.csv"
            raw = p.read_bytes()
            p.write_bytes(raw + b"\n")  # size + SHA mismatch
            client = _client()
            r = client.get(f"{PROTOCOL_PATH}/catalog")
            assert r.status_code == 503

    def test_missing_catalog_csv_downgrades_metadata(self, tmp_path):
        with _isolated_figure_tree(tmp_path) as tree:
            (tree["figures_dir"] / "phase5_figure_catalog.csv").unlink()
            client = _client()
            r = client.get(f"{PROTOCOL_PATH}/catalog")
            assert r.status_code == 200
            data = r.json()
            assert data["catalog_metadata_available"] is False
            for f in data["figures"]:
                assert f["title"] is None
                # PNG binaries still verify against the manifest
                assert f["integrity"]["state"] == "verified"


# ---------------------------------------------------------------------------
# E. DVC absence
# ---------------------------------------------------------------------------


class TestDvcAbsence:
    def test_missing_png_marks_artifact_missing(self, tmp_path):
        with _isolated_figure_tree(tmp_path) as tree:
            (tree["figures_dir"] / "phase5_plot3_hypergeometric_overlap.png").unlink()
            client = _client()
            data = client.get(f"{PROTOCOL_PATH}/catalog").json()
            f3 = data["figures"][2]
            assert f3["integrity"]["state"] == "artifact_missing"
            assert f3["availability"]["available"] is False
            assert f3["availability"]["reason"] == "artifact_missing"

    def test_missing_pointer_fails_integrity(self, tmp_path):
        with _isolated_figure_tree(tmp_path) as tree:
            (tree["figures_dir"] / "phase5_plot2_fraud_discovery.png.dvc").unlink()
            client = _client()
            data = client.get(f"{PROTOCOL_PATH}/catalog").json()
            f2 = data["figures"][1]
            assert f2["integrity"]["state"] == "integrity_failed"


# ---------------------------------------------------------------------------
# F. Independent availability
# ---------------------------------------------------------------------------


class TestIndependentAvailability:
    def test_one_missing_figure_does_not_affect_others(self, tmp_path):
        with _isolated_figure_tree(tmp_path) as tree:
            (tree["figures_dir"] / "phase5_plot5_jaccard_matrix.png").unlink()
            client = _client()
            data = client.get(f"{PROTOCOL_PATH}/catalog").json()
            for i, f in enumerate(data["figures"]):
                if i == 4:
                    assert f["integrity"]["state"] == "artifact_missing"
                else:
                    assert f["integrity"]["state"] == "verified"


# ---------------------------------------------------------------------------
# G. Digest verification
# ---------------------------------------------------------------------------


class TestDigestVerification:
    def test_byte_flip_in_png_fails_sha(self, tmp_path):
        with _isolated_figure_tree(tmp_path) as tree:
            p = tree["figures_dir"] / "phase5_plot1_precision_recall.png"
            raw = p.read_bytes()
            tampered = raw[:100] + bytes([raw[100] ^ 0xFF]) + raw[101:]
            p.write_bytes(tampered)
            client = _client()
            data = client.get(f"{PROTOCOL_PATH}/catalog").json()
            assert data["figures"][0]["integrity"]["state"] == "integrity_failed"

    def test_truncated_png_fails_size(self, tmp_path):
        with _isolated_figure_tree(tmp_path) as tree:
            p = tree["figures_dir"] / "phase5_plot7_rank_vs_rank.png"
            raw = p.read_bytes()
            p.write_bytes(raw[:1000])  # truncated
            client = _client()
            data = client.get(f"{PROTOCOL_PATH}/catalog").json()
            assert data["figures"][6]["integrity"]["state"] == "integrity_failed"


# ---------------------------------------------------------------------------
# H. Binary format validation (direct function tests)
# ---------------------------------------------------------------------------


class TestPngFormatValidation:
    def test_real_png_passes(self):
        raw = (_REAL_FIGURES_DIR / "phase5_plot1_precision_recall.png").read_bytes()
        _validate_png(raw, "test.png")  # no exception

    def test_invalid_signature_rejected(self):
        raw = b"NOT_A_PNG" + b"\x00" * 2000
        with pytest.raises(Phase5BIntegrityError, match="Invalid PNG signature"):
            _validate_png(raw, "test.png")

    def test_missing_ihdr_rejected(self):
        raw = _png_with_dimensions(100, 100, include_ihdr=False)
        with pytest.raises(Phase5BIntegrityError, match="missing IHDR"):
            _validate_png(raw, "test.png")

    def test_too_short_rejected(self):
        with pytest.raises(Phase5BIntegrityError, match="PNG too short"):
            _validate_png(b"\x89PNG\r\n\x1a\n", "test.png")

    def test_dimensions_too_small_rejected(self):
        with pytest.raises(Phase5BIntegrityError, match="dimensions out of range"):
            _validate_png(_png_with_dimensions(50, 100), "test.png")

    def test_dimensions_too_large_rejected(self):
        with pytest.raises(Phase5BIntegrityError, match="dimensions out of range"):
            _validate_png(_png_with_dimensions(9999, 100), "test.png")


# ---------------------------------------------------------------------------
# I. Path security
# ---------------------------------------------------------------------------


class TestPathSecurity:
    def test_figure_no_zero_rejected(self):
        client = _client()
        assert client.get(f"{PROTOCOL_PATH}/figures/0/image").status_code == 422

    def test_figure_no_nine_rejected(self):
        client = _client()
        assert client.get(f"{PROTOCOL_PATH}/figures/9/image").status_code == 422

    def test_figure_no_non_integer_rejected(self):
        client = _client()
        assert client.get(f"{PROTOCOL_PATH}/figures/abc/image").status_code == 422

    def test_no_filename_or_path_in_route(self):
        app = create_app(settings=_settings())
        phase5b_image_paths = [
            r.path for r in app.routes
            if hasattr(r, "path") and "phase5b" in r.path and "image" in r.path
        ]
        assert phase5b_image_paths, "no phase5b image route found"
        for p in phase5b_image_paths:
            assert "{filename" not in p
            assert "{path" not in p
            assert "{figure_no}" in p


# ---------------------------------------------------------------------------
# J. Cache mutation and restoration
# ---------------------------------------------------------------------------


class TestCacheMutationRecovery:
    def test_tamper_then_restore(self, tmp_path):
        with _isolated_figure_tree(tmp_path) as tree:
            client = _client()
            p = tree["figures_dir"] / "phase5_plot1_precision_recall.png"
            original = p.read_bytes()

            # 1. Verified
            assert client.get(f"{PROTOCOL_PATH}/catalog").json()["figures"][0][
                "integrity"
            ]["state"] == "verified"

            # 2. Tamper -> integrity_failed
            p.write_bytes(original[:100] + b"\x00" + original[101:])
            assert client.get(f"{PROTOCOL_PATH}/catalog").json()["figures"][0][
                "integrity"
            ]["state"] == "integrity_failed"

            # 3. Restore -> verified
            p.write_bytes(original)
            assert client.get(f"{PROTOCOL_PATH}/catalog").json()["figures"][0][
                "integrity"
            ]["state"] == "verified"


# ---------------------------------------------------------------------------
# K. Publication gate
# ---------------------------------------------------------------------------


class TestPublicationGate:
    def test_default_settings_flag_is_false(self):
        s = Settings(_env_file=None, environment="test")
        assert s.phase5b_public_figures_enabled is False

    def test_catalog_shows_publication_disabled(self):
        client = _client(publication_enabled=False)
        data = client.get(f"{PROTOCOL_PATH}/catalog").json()
        assert data["publication_gate"]["enabled"] is False
        assert data["publication_gate"]["reason"] == "publication_not_approved"

    def test_image_blocked_when_disabled(self):
        client = _client(publication_enabled=False)
        r = client.get(f"{PROTOCOL_PATH}/figures/1/image")
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "PUBLICATION_NOT_APPROVED"

    def test_image_served_when_enabled(self, tmp_path):
        with _isolated_figure_tree(tmp_path) as tree:
            client = _client(publication_enabled=True)
            r = client.get(f"{PROTOCOL_PATH}/figures/1/image")
            assert r.status_code == 200
            assert r.headers["content-type"] == "image/png"
            assert r.headers["x-content-type-options"] == "nosniff"
            assert r.headers["cache-control"] == "no-store"
            expected = (
                tree["figures_dir"] / "phase5_plot1_precision_recall.png"
            ).read_bytes()
            assert r.content == expected

    def test_gate_precedes_binary_read(self, tmp_path):
        """When publication is disabled, the payload is never read."""
        with _isolated_figure_tree(tmp_path) as tree:
            # Corrupt the PNG so any read would raise; the gate should still 403
            (tree["figures_dir"] / "phase5_plot1_precision_recall.png").write_bytes(
                b"garbage"
            )
            client = _client(publication_enabled=False)
            r = client.get(f"{PROTOCOL_PATH}/figures/1/image")
            assert r.status_code == 403
            assert r.json()["error"]["code"] == "PUBLICATION_NOT_APPROVED"


# ---------------------------------------------------------------------------
# L. API security (sanitized errors)
# ---------------------------------------------------------------------------


class TestApiSecurity:
    def test_publication_error_has_no_paths(self):
        client = _client()
        r = client.get(f"{PROTOCOL_PATH}/figures/1/image")
        body = json.dumps(r.json())
        assert "C:\\" not in body
        assert "C:/" not in body
        assert "results/stream a" not in body
        assert "results\\stream a" not in body

    def test_integrity_error_has_no_paths(self, tmp_path):
        with _isolated_figure_tree(tmp_path) as tree:
            manifest = tree["figures_dir"] / "phase5_plot_commit_manifest.json"
            manifest.write_bytes(manifest.read_bytes() + b"\n")
            client = _client()
            r = client.get(f"{PROTOCOL_PATH}/catalog")
            assert r.status_code == 503
            body = json.dumps(r.json())
            assert str(tmp_path) not in body
            assert "Traceback" not in body
            assert "File " not in body


# ---------------------------------------------------------------------------
# M. Traceability
# ---------------------------------------------------------------------------


class TestTraceability:
    def test_three_objectives_abc(self):
        client = _client()
        data = client.get(f"{PROTOCOL_PATH}/traceability").json()
        assert [o["objective_id"] for o in data["objectives"]] == ["(a)", "(b)", "(c)"]

    def test_six_rqs_in_order(self):
        client = _client()
        data = client.get(f"{PROTOCOL_PATH}/traceability").json()
        assert [r["rq_id"] for r in data["research_questions"]] == [
            "RQ1", "RQ2", "RQ3", "RQ4", "RQ5", "RQ6",
        ]

    def test_source_identity(self):
        client = _client()
        data = client.get(f"{PROTOCOL_PATH}/traceability").json()
        assert data["source_identity"]["document"] == "docs/provenance_log.md"
        assert data["source_identity"]["section"] == "1"
        assert data["source_identity"]["status"] == "source_verified"

    def test_objective_b_links_pr09_pr10_pr11(self):
        client = _client()
        data = client.get(f"{PROTOCOL_PATH}/traceability").json()
        obj_b = next(o for o in data["objectives"] if o["objective_id"] == "(b)")
        evidence_types = {e["type"] for e in obj_b["evidence"]}
        assert "canonical_benchmark" in evidence_types
        assert "phase5a_agreement" in evidence_types
        assert "phase5b_figures" in evidence_types

    def test_historical_companion_non_comparable(self):
        client = _client()
        data = client.get(f"{PROTOCOL_PATH}/traceability").json()
        hc = data["historical_companion"]
        assert hc["population"] == 284807
        assert hc["canonical_comparable"] is False
        assert len(hc["limitations"]) >= 1


# ---------------------------------------------------------------------------
# N. OpenAPI
# ---------------------------------------------------------------------------


class TestOpenApi:
    def test_three_endpoints_registered(self):
        app = create_app(settings=_settings())
        spec = app.openapi()
        paths = set(spec["paths"].keys())
        assert "/api/v1/research/phase5b/catalog" in paths
        assert "/api/v1/research/phase5b/figures/{figure_no}/image" in paths
        assert "/api/v1/research/phase5b/traceability" in paths

    def test_publication_error_code_documented(self):
        app = create_app(settings=_settings())
        text = json.dumps(app.openapi())
        assert "PUBLICATION_NOT_APPROVED" in text


# ---------------------------------------------------------------------------
# O. Frozen evidence integrity
# ---------------------------------------------------------------------------


class TestFrozenEvidence:
    def test_frozen_integrity_unchanged(self):
        repo = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, str(repo / "ci" / "check_frozen_integrity.py")],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=90,
        )
        assert result.returncode == 0, result.stderr
        assert "28/28" in result.stdout


# ---------------------------------------------------------------------------
# P. Real-DVC trusted-lane acceptance (skipped when payloads absent)
# ---------------------------------------------------------------------------


class TestTrustedLocalRealDvcPayloads:
    def test_all_eight_pngs_verified_when_materialized(self):
        missing = [
            name for name in svc._CANONICAL_FIGURES.values()
            if not (_REAL_FIGURES_DIR / name).is_file()
        ]
        if missing:
            pytest.skip(f"DVC payloads absent: {missing}")
        catalog = PHASE5B_CATALOG_SERVICE.get_catalog(publication_enabled=False)
        for f in catalog["figures"]:
            assert f["integrity"]["state"] == "verified", f["figure_no"]
            assert f["availability"]["available"] is True
            assert f["integrity"]["size_bytes"] is not None
            assert f["integrity"]["sha256"] is not None

    def test_catalog_csv_materialized(self):
        if not (svc.REPO_ROOT / svc.PHASE5_CATALOG_REL).is_file():
            pytest.skip("DVC catalog CSV absent")
        catalog = PHASE5B_CATALOG_SERVICE.get_catalog(publication_enabled=False)
        assert catalog["catalog_metadata_available"] is True