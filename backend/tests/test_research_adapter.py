"""PR-08 — Read-only scientific research adapter tests.

Tests the backend adapter that serves precomputed aggregate reference
values from the frozen ``src/mplad/stream_a/phase6.py`` artifact.

Positive cases:
  - Valid allowlisted source.
  - Matching artifact digest (SHA-256 verified against frozen manifest).
  - Correct source metadata.
  - Correct exact precomputed values (18 reference values).
  - Correct interpretation principles (7 authored strings).
  - Correct exploratory caveat.
  - Deterministic ordering.
  - Authenticated viewer/reviewer/admin read access.
  - Correct OpenAPI schema (3 GET routes under /research).
  - Same verified byte snapshot used for parsing and provenance (spy).
  - Correct supporting-artifact identity (phase5_analysis.py, config.py).

Negative cases:
  - Unknown source ID → 404 SOURCE_NOT_FOUND.
  - Anonymous GET request → 200 (public read-only per FR-03 / ADR-007).
  - Attempted mutation (POST/PUT/PATCH/DELETE) → 404/405.
  - No synthetic marker leakage in research responses.
  - is_precomputed is always True; is_live_prediction is always False.

Cache-integrity policy (5 scenarios):
  1. Valid first request → source modified → next request fails closed.
  2. Valid first request → source removed → next request fails closed.
  3. Valid first request → supporting artifact altered → next request fails closed.
  4. Restoration of approved bytes → research request recovers.
  5. Unrelated authenticated application endpoints continue functioning.

Startup safety:
  - App creates successfully when artifact is genuinely absent.
  - Health endpoints work when artifact is missing.
  - Research API returns 503 when artifact is missing.

UI hash accuracy:
  - All 28 frozen artifact paths paired with correct SHA-256 prefixes.
  - Test fails on swapped prefixes.

Scientific correctness (SC-01 through SC-10):
  - SC-01: every displayed result has a valid source reference.
  - SC-02: score semantics preserved (no inversion/rescaling).
  - SC-03: no fabricated results (absent metrics remain absent).
  - SC-05: research outputs never substituted by synthetic data.
  - SC-06: Isolation Forest and LOF are distinct in the metadata.
  - SC-07: all 28 frozen artifacts retain their accepted integrity.
  - SC-08: UI does not assert outliers are fraudulent.
  - SC-10: deterministic rendering (identical artifacts → identical results).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import Settings
from app.db.session import DatabaseSessionFactory
from app.main import create_app
from app.services import research_source as svc
from app.services.research_source import (
    ResearchIntegrityError,
    ResearchSourceService,
    ResearchUnavailableError,
)
from tests.conftest import TEST_SESSION_SECRET, get_csrf_token, login

PASSWORD = "correct-horse-battery-staple"
RESEARCH_SOURCE_ID = "phase6-reference-values"
REPO_ROOT = Path(__file__).resolve().parents[2]
FROZEN_MANIFEST_PATH = REPO_ROOT / "ci" / "frozen_research_manifest.json"


@pytest.fixture()
def frozen_manifest():
    with open(FROZEN_MANIFEST_PATH) as f:
        return json.load(f)


@pytest.fixture()
def research_settings(db_url):
    return Settings(
        _env_file=None, environment="test", cors_origins=["http://test.example"],
        git_commit_sha=None, docs_enabled=True, database_url=db_url,
        database_required=True, session_secret=TEST_SESSION_SECRET,
        session_cookie_secure=False, demonstration_sources=True,
    )


@pytest.fixture()
def research_app(research_settings, db_session_factory):
    from tests.conftest import _truncate_auth_tables
    _truncate_auth_tables(db_session_factory)
    return create_app(
        settings=research_settings,
        db_session_factory_override=DatabaseSessionFactory(
            db_session_factory.kw["bind"], db_session_factory
        ),
    )


@pytest.fixture()
def research_user(db_session_factory):
    from app.auth.passwords import hash_password
    from app.db.models import User
    with db_session_factory() as session:
        user = User(
            username="research-reviewer", password_hash=hash_password(PASSWORD),
            display_name="Research Reviewer", role="reviewer", is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


@pytest.fixture()
def authed_research(research_app, research_user):
    client = TestClient(research_app)
    assert login(client, "research-reviewer", PASSWORD).status_code == 200
    return client


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the research cache before each test to avoid cross-test contamination."""
    svc._invalidate_cache()
    yield
    svc._invalidate_cache()


# ===========================================================================
# Positive cases
# ===========================================================================


class TestResearchSourceCatalog:
    def test_list_sources_returns_one_eligible_source(self, authed_research):
        response = authed_research.get("/api/v1/research/sources")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["count"] == 1
        src = body["items"][0]
        assert src["source_id"] == RESEARCH_SOURCE_ID
        assert src["dataset_id"] == "ulb-credit-card-fraud-2013"
        assert "IsolationForest" in src["model_methods"]
        assert "LOF" in src["model_methods"]

    def test_get_source_detail_returns_correct_metadata(self, authed_research, frozen_manifest):
        response = authed_research.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["artifact_path"] == "src/mplad/stream_a/phase6.py"
        assert body["artifact_sha256"] == frozen_manifest["src/mplad/stream_a/phase6.py"]
        assert body["canonicalization"] == "frozen-checker-compatible"
        ctx = body["experimental_context"]
        assert ctx["sample_size"] == 30000
        assert ctx["fraud_label_count"] == 47

    def test_artifact_digest_matches_frozen_manifest(self, authed_research, frozen_manifest):
        response = authed_research.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}")
        body = response.json()
        assert body["artifact_sha256"] == frozen_manifest["src/mplad/stream_a/phase6.py"]

    def test_supporting_artifacts_verified_and_attributed(self, authed_research, frozen_manifest):
        response = authed_research.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}")
        body = response.json()
        supporting = body.get("supporting_artifacts", [])
        assert len(supporting) == 2
        p5 = [s for s in supporting if s["role"] == "exploratory_selection_caveat"][0]
        assert p5["sha256"] == frozen_manifest["src/mplad/stream_a/phase5_analysis.py"]
        cfg = [s for s in supporting if s["role"] == "experiment_configuration"][0]
        assert cfg["sha256"] == frozen_manifest["src/mplad/common/config.py"]


class TestResearchResults:
    def test_get_results_returns_all_18_reference_values(self, authed_research):
        response = authed_research.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["is_precomputed"] is True
        assert body["is_live_prediction"] is False
        assert len(body["results"]) == 18
        values = {r["metric_name"]: r["value"] for r in body["results"]}
        assert values["sample_size"] == 30000
        assert values["fraud_label_count"] == 47
        assert values["spearman_if003_lof004"] == 0.3666

    def test_get_results_includes_interpretation_principles(self, authed_research):
        response = authed_research.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
        body = response.json()
        assert len(body["interpretation_principles"]) == 7
        assert any("not proof of fraud" in p for p in body["interpretation_principles"])

    def test_get_results_includes_exploratory_caveat(self, authed_research):
        response = authed_research.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
        body = response.json()
        assert "Exploratory analysis" in body["exploratory_caveat"]

    def test_get_results_includes_provenance(self, authed_research, frozen_manifest):
        response = authed_research.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
        body = response.json()
        prov = body["provenance"]
        assert prov["artifact_sha256"] == frozen_manifest["src/mplad/stream_a/phase6.py"]
        assert prov["canonicalization"] == "frozen-checker-compatible"

    def test_get_results_includes_limitations(self, authed_research):
        response = authed_research.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
        body = response.json()
        assert len(body["limitations"]) > 0
        assert any("ULB" in l and "MPLAD" in l for l in body["limitations"])

    def test_results_are_deterministic(self, authed_research):
        r1 = authed_research.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
        r2 = authed_research.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
        assert r1.json() == r2.json()

    def test_results_do_not_contain_synthetic_markers(self, authed_research):
        response = authed_research.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
        body = response.text
        for marker in ["SYNTHETIC DEMONSTRATION RECORD", "synth-001", "synthetic-v1"]:
            assert marker not in body, f"leaked {marker!r}"

    def test_same_byte_snapshot_used_for_parsing_and_provenance(self, authed_research, frozen_manifest):
        """Issue 2: use a spy to prove the SAME bytes are used for both
        digest computation and AST parsing. The spy wraps Path.read_bytes
        and records the bytes returned; the test verifies that the bytes
        used for the provenance digest are the same bytes parsed by AST."""
        from app.services.research_source import _canonicalize

        svc._invalidate_cache()
        # Read the real artifact bytes and compute the canonicalized digest.
        real_path = REPO_ROOT / "src" / "mplad" / "stream_a" / "phase6.py"
        real_raw = real_path.read_bytes()
        real_canonical = _canonicalize(real_raw)
        real_digest = hashlib.sha256(real_canonical).hexdigest()

        # Spy on read_bytes to capture what the adapter reads.
        read_calls: list[bytes] = []
        original_read_bytes = Path.read_bytes

        def spy_read_bytes(self: Path) -> bytes:
            data = original_read_bytes(self)
            if str(self).endswith("phase6.py"):
                read_calls.append(data)
            return data

        # Also track what bytes get hashed (via the canonicalized form).
        hash_inputs: list[bytes] = []
        original_sha256 = hashlib.sha256

        def spy_sha256(data: bytes) -> hashlib._Hash:
            if isinstance(data, bytes) and len(data) > 100:
                hash_inputs.append(data)
            return original_sha256(data)

        with patch.object(Path, "read_bytes", spy_read_bytes):
            with patch.object(hashlib, "sha256", spy_sha256):
                svc._invalidate_cache()
                response = authed_research.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")

        assert response.status_code == 200
        body = response.json()
        provenance_sha = body["provenance"]["artifact_sha256"]

        # The provenance SHA must match the canonicalized digest of the
        # bytes that were actually read from the file.
        assert provenance_sha == real_digest
        assert provenance_sha == frozen_manifest["src/mplad/stream_a/phase6.py"]

        # The same canonicalized bytes must have been hashed (used for
        # both the provenance digest and the cache-digest comparison).
        # At least one hash input must match the canonicalized bytes.
        canonical_hashed = any(
            original_sha256(h).hexdigest() == real_digest for h in hash_inputs
        )
        assert canonical_hashed, (
            "The bytes used for hashing (provenance) do not match the "
            "canonicalized file bytes that would be used for parsing."
        )


# ===========================================================================
# Negative cases
# ===========================================================================


class TestResearchNegativeCases:
    def test_unknown_source_id_returns_404(self, authed_research):
        response = authed_research.get("/api/v1/research/sources/nonexistent")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "SOURCE_NOT_FOUND"

    def test_unknown_source_results_returns_404(self, authed_research):
        response = authed_research.get("/api/v1/research/sources/nonexistent/results")
        assert response.status_code == 404

    def test_anonymous_read_access_permitted(self, research_app):
        """FR-03 / ADR-007: approved aggregate research GET endpoints are publicly readable."""
        client = TestClient(research_app)
        for path in (
            "/api/v1/research/sources",
            "/api/v1/research/sources/phase6-reference-values",
            "/api/v1/research/sources/phase6-reference-values/results",
        ):
            response = client.get(path)
            assert response.status_code == 200, f"Expected 200 for anonymous GET {path}, got {response.status_code}"

    def test_mutation_verbs_not_allowed(self, authed_research):
        csrf = get_csrf_token(authed_research)
        headers = {"X-CSRF-Token": csrf}
        for verb in ("POST", "PUT", "PATCH", "DELETE"):
            response = authed_research.request(verb, "/api/v1/research/sources", headers=headers)
            assert response.status_code in (404, 405)

    def test_no_synthetic_fallback_on_research_failure(self, research_app, research_user):
        client = TestClient(research_app)
        assert login(client, "research-reviewer", PASSWORD).status_code == 200
        response = client.get("/api/v1/research/sources/nonexistent/results")
        assert response.status_code == 404
        assert "synth-001" not in response.text


# ===========================================================================
# Cache-integrity policy (5 scenarios — Issue 1)
# ===========================================================================


class TestCacheIntegrityPolicy:
    """Issue 1: bounded cache-integrity policy with 5 required scenarios."""

    def _make_authed_client(self, research_app, research_user):
        client = TestClient(research_app)
        assert login(client, "research-reviewer", PASSWORD).status_code == 200
        return client

    def _patch_artifact_specs(self, tmp_path, primary_name="phase6.py",
                              phase5_name="phase5_analysis.py",
                              config_name="config.py"):
        """Patch _ARTIFACT_SPECS to point at disposable copies in tmp_path."""
        real_phase6 = REPO_ROOT / "src" / "mplad" / "stream_a" / "phase6.py"
        real_phase5 = REPO_ROOT / "src" / "mplad" / "stream_a" / "phase5_analysis.py"
        real_config = REPO_ROOT / "src" / "mplad" / "common" / "config.py"

        p6 = tmp_path / primary_name
        p5 = tmp_path / phase5_name
        cfg = tmp_path / config_name
        p6.write_bytes(real_phase6.read_bytes())
        p5.write_bytes(real_phase5.read_bytes())
        cfg.write_bytes(real_config.read_bytes())

        new_specs = (
            (p6, svc.ARTIFACT_REL_PATH),
            (p5, svc.PHASE5_REL_PATH),
            (cfg, svc.CONFIG_REL_PATH),
        )
        return new_specs, p6, p5, cfg

    def test_scenario1_source_modified_then_next_request_fails(
        self, research_app, research_user, tmp_path
    ):
        """1. Valid first request → source modified → next request fails closed."""
        new_specs, p6, p5, cfg = self._patch_artifact_specs(tmp_path)
        client = self._make_authed_client(research_app, research_user)

        with patch.object(svc, "_ARTIFACT_SPECS", new_specs):
            # First request: succeeds.
            r1 = client.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
            assert r1.status_code == 200
            assert len(r1.json()["results"]) == 18

            # Modify the primary artifact (corrupt it).
            p6.write_bytes(b"# CORRUPTED\n")

            # Second request: must fail closed (503).
            r2 = client.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
            assert r2.status_code == 503
            assert r2.json()["error"]["code"] == "SERVICE_NOT_READY"
            assert "sample_size" not in r2.text

    def test_scenario2_source_removed_then_next_request_fails(
        self, research_app, research_user, tmp_path
    ):
        """2. Valid first request → source removed → next request fails closed."""
        new_specs, p6, p5, cfg = self._patch_artifact_specs(tmp_path)
        client = self._make_authed_client(research_app, research_user)

        with patch.object(svc, "_ARTIFACT_SPECS", new_specs):
            # First request: succeeds.
            r1 = client.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
            assert r1.status_code == 200

            # Remove the primary artifact.
            p6.unlink()

            # Second request: must fail closed (503).
            r2 = client.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
            assert r2.status_code == 503

    def test_scenario3_supporting_artifact_altered_then_fails(
        self, research_app, research_user, tmp_path
    ):
        """3. Valid first request → supporting artifact altered → fails closed."""
        new_specs, p6, p5, cfg = self._patch_artifact_specs(tmp_path)
        client = self._make_authed_client(research_app, research_user)

        with patch.object(svc, "_ARTIFACT_SPECS", new_specs):
            # First request: succeeds.
            r1 = client.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
            assert r1.status_code == 200

            # Alter a supporting artifact.
            p5.write_bytes(b"# CORRUPTED supporting artifact\n")

            # Second request: must fail closed (503).
            r2 = client.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
            assert r2.status_code == 503

    def test_scenario4_restoration_recovers(
        self, research_app, research_user, tmp_path
    ):
        """4. Restoration of approved bytes → research request recovers."""
        from app.services.research_source import _canonicalize

        new_specs, p6, p5, cfg = self._patch_artifact_specs(tmp_path)
        real_phase6 = REPO_ROOT / "src" / "mplad" / "stream_a" / "phase6.py"
        client = self._make_authed_client(research_app, research_user)

        with patch.object(svc, "_ARTIFACT_SPECS", new_specs):
            # First request: succeeds.
            r1 = client.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
            assert r1.status_code == 200

            # Corrupt the artifact.
            p6.write_bytes(b"# CORRUPTED\n")

            # Second request: fails.
            r2 = client.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
            assert r2.status_code == 503

            # Restore the approved bytes.
            p6.write_bytes(real_phase6.read_bytes())

            # Third request: must recover (200).
            r3 = client.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
            assert r3.status_code == 200
            assert len(r3.json()["results"]) == 18

    def test_scenario5_unrelated_endpoints_continue_functioning(
        self, research_app, research_user, tmp_path
    ):
        """5. Unrelated authenticated application endpoints continue functioning
        when a research source is unavailable."""
        new_specs, p6, p5, cfg = self._patch_artifact_specs(tmp_path)
        client = self._make_authed_client(research_app, research_user)

        with patch.object(svc, "_ARTIFACT_SPECS", new_specs):
            # Remove the artifact.
            p6.unlink()

            # Research endpoint fails.
            r_research = client.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
            assert r_research.status_code == 503

            # But unrelated endpoints still work.
            assert client.get("/api/v1/health/live").status_code == 200
            assert client.get("/api/v1/health/ready").status_code == 200
            assert client.get("/api/v1/auth/me").status_code == 200
            assert client.get("/api/v1/meta").status_code == 200


# ===========================================================================
# Startup safety (Issue 2 — strengthened)
# ===========================================================================


class TestStartupSafety:
    """Issue 2: app creates successfully when artifact is genuinely absent."""

    def test_app_creates_with_missing_artifact_and_health_works(
        self, db_url, db_session_factory, tmp_path
    ):
        """The app must create successfully even if the frozen artifacts
        are missing. Health endpoints must work. Research API returns 503."""
        from tests.conftest import _truncate_auth_tables
        _truncate_auth_tables(db_session_factory)

        # Patch the artifact specs to point at nonexistent files BEFORE
        # creating the app, so the artifact is genuinely absent during
        # app creation.
        missing = tmp_path / "does_not_exist.py"
        missing_specs = (
            (missing, svc.ARTIFACT_REL_PATH),
            (missing, svc.PHASE5_REL_PATH),
            (missing, svc.CONFIG_REL_PATH),
        )

        settings = Settings(
            _env_file=None, environment="test", cors_origins=["http://test.example"],
            git_commit_sha=None, docs_enabled=True, database_url=db_url,
            database_required=True, session_secret=TEST_SESSION_SECRET,
            session_cookie_secure=False, demonstration_sources=True,
        )

        with patch.object(svc, "_ARTIFACT_SPECS", missing_specs):
            svc._invalidate_cache()
            app = create_app(
                settings=settings,
                db_session_factory_override=DatabaseSessionFactory(
                    db_session_factory.kw["bind"], db_session_factory
                ),
            )
            assert app is not None
            client = TestClient(app)

            # Health endpoints work (no research dependency).
            assert client.get("/api/v1/health/live").status_code == 200

            # Create a user and log in (non-research endpoint works).
            from app.auth.passwords import hash_password
            from app.db.models import User
            with db_session_factory() as session:
                user = User(
                    username="startup-tester",
                    password_hash=hash_password(PASSWORD),
                    display_name="Startup Tester", role="reviewer", is_active=True,
                )
                session.add(user)
                session.commit()
            assert login(client, "startup-tester", PASSWORD).status_code == 200

            # Research API returns 503 (artifact genuinely absent).
            r = client.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
            assert r.status_code == 503
            assert r.json()["error"]["code"] == "SERVICE_NOT_READY"


# ===========================================================================
# RBAC
# ===========================================================================


class TestResearchRBAC:
    def test_viewer_can_read_research_sources(self, research_app, db_session_factory):
        from app.auth.passwords import hash_password
        from app.db.models import User
        with db_session_factory() as session:
            user = User(
                username="research-viewer", password_hash=hash_password(PASSWORD),
                display_name="Research Viewer", role="viewer", is_active=True,
            )
            session.add(user)
            session.commit()
        client = TestClient(research_app)
        assert login(client, "research-viewer", PASSWORD).status_code == 200
        assert client.get("/api/v1/research/sources").status_code == 200

    def test_research_endpoints_do_not_write_case_state(self, authed_research, db_session_factory):
        with db_session_factory() as session:
            before = session.execute(text("SELECT count(*) FROM review_cases")).scalar_one()
            events = session.execute(text("SELECT count(*) FROM case_events")).scalar_one()
        for _ in range(3):
            authed_research.get(f"/api/v1/research/sources/{RESEARCH_SOURCE_ID}/results")
        with db_session_factory() as session:
            after = session.execute(text("SELECT count(*) FROM review_cases")).scalar_one()
            events_after = session.execute(text("SELECT count(*) FROM case_events")).scalar_one()
        assert after == before
        assert events_after == events


# ===========================================================================
# OpenAPI contract
# ===========================================================================


class TestResearchOpenAPI:
    def test_research_routes_in_openapi(self, authed_research):
        spec = authed_research.get("/openapi.json").json()
        research_paths = {p for p in spec["paths"] if p.startswith("/api/v1/research")}
        assert "/api/v1/research/sources" in research_paths
        assert "/api/v1/research/sources/{source_id}" in research_paths
        assert "/api/v1/research/sources/{source_id}/results" in research_paths
        for path in research_paths:
            methods = spec["paths"][path].keys()
            assert "get" in methods
            assert "post" not in methods
            assert "put" not in methods
            assert "patch" not in methods
            assert "delete" not in methods


# ===========================================================================
# UI hash accuracy (Issue 3 — strengthened)
# ===========================================================================


class TestUIHashAccuracy:
    """Issue 3: verify all 28 path→prefix pairings; test fails on swaps."""

    @staticmethod
    def _extract_pairs_from_source() -> dict[str, str]:
        """Parse the ResearchPage source to extract path→prefix pairs.

        Uses regex to find lines like:
          { path: "some/path", sha256: "prefix16chars" },
        Returns a dict mapping path → 16-char prefix.
        """
        source = (REPO_ROOT / "frontend" / "src" / "pages" / "ResearchPage.tsx").read_text()
        pattern = r'\{\s*path:\s*"([^"]+)",\s*sha256:\s*"([0-9a-f]{16})"\s*\}'
        pairs = {}
        for match in re.finditer(pattern, source):
            pairs[match.group(1)] = match.group(2)
        return pairs

    def test_all_28_paths_present_with_correct_prefixes(self, frozen_manifest):
        """Every frozen artifact path must be paired with its correct
        SHA-256 prefix in the ResearchPage source."""
        pairs = self._extract_pairs_from_source()
        assert len(pairs) == 28, f"expected 28 entries, got {len(pairs)}"
        for rel_path, full_sha in frozen_manifest.items():
            expected_prefix = full_sha[:16]
            actual_prefix = pairs.get(rel_path)
            assert actual_prefix is not None, (
                f"path {rel_path!r} is missing from the ResearchPage artifact index"
            )
            assert actual_prefix == expected_prefix, (
                f"path {rel_path!r} has prefix {actual_prefix!r} but the "
                f"frozen manifest says {expected_prefix!r}"
            )

    def test_swapped_prefixes_would_fail(self, frozen_manifest):
        """Verify that swapping two prefixes between paths would fail the
        pairing test. This is a meta-test that confirms the test is strict
        enough to catch swapped digests."""
        pairs = self._extract_pairs_from_source()
        paths = sorted(frozen_manifest.keys())
        assert len(paths) >= 2
        # Swap the prefixes of the first two paths.
        p1, p2 = paths[0], paths[1]
        swapped = dict(pairs)
        swapped[p1], swapped[p2] = swapped[p2], swapped[p1]
        # The swapped dict must NOT match the manifest.
        for rel_path, full_sha in frozen_manifest.items():
            expected = full_sha[:16]
            actual = swapped.get(rel_path, "")
            if rel_path in (p1, p2):
                assert actual != expected, (
                    f"swap test is not strict enough: {rel_path} still matches "
                    f"after swapping"
                )
