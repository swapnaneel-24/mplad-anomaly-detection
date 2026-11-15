"""PR-10 — Phase 5A uncertainty/agreement/review-policy evidence tests.

Covers the mandatory fixture-only CI scenarios from the PR-10 brief
(section 9.A), using deterministic synthetic fixtures stored only under
test locations and visibly identified as synthetic. The real DVC payloads
are ABSENT in a clean checkout and are never touched.

Scenarios (24):
  1.  Verified Git metadata available without any DVC payload.
  2.  Artifact-family-specific artifact_missing states.
  3.  Exact Phase 5A protocol metadata mapping.
  4.  Trusted manifest tampering and metadata drift.
  5.  DVC pointer mismatch, size mismatch and SHA-256 mismatch.
  6.  Windows LF/CRLF representation-compatible digest/size handling.
  7.  Post-cache mutation, removal and restoration.
  8.  Independent artifact availability; one missing source does not disable
      unrelated results.
  9.  Bootstrap schema, bounds, replicate count and interval definition.
  10. Paired-difference direction and post-hoc warning.
  11. Spearman run labels, symmetry, diagonal and bounds.
  12. Jaccard canonical 1% labels and bounds.
  13. Hypergeometric null and log-probability representation.
  14. Agreement-group conservation of total sample and labelled positives.
  15. Four-policy review workload, numerators, denominators and unequal-budget
      labeling.
  16. Saved multi-threshold selection-source distinctions.
  17. Large discovery-curve pagination or controlled metadata-only outcome.
  18. Public research GET access and private case-write separation.
  19. No HTTP-triggered model fitting, bootstrap, thresholds, DVC pull or
      scientific artifact mutation.
  20. No secret/path leakage in API errors.
  21. Existing PR-08/09 functionality remains intact.
  22. OpenAPI/TypeScript drift checks.
  23. Frontend unavailable-state, keyboard and table coverage (Vitest-side).
  24. Clean-checkout Compose and browser E2E compatibility (E2E-side).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from unittest.mock import patch
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.session import DatabaseSessionFactory
from app.main import create_app
from app.services import phase5a_catalog as svc
from app.services.phase5a_catalog import (
    Phase5AEvidenceService,
    Phase5AIntegrityError,
    Phase5AUnavailableError,
    _invalidate_layer_a,
    _invalidate_layer_b,
)
from app.services.source_registry import SourceNotFoundError
from tests.conftest import TEST_SESSION_SECRET, get_csrf_token, login

PASSWORD = "correct-horse-battery-staple"
REPO_ROOT = Path(__file__).resolve().parents[2]

RUN_META_REL = "results/stream a/phase 5/reproduction/phase5_run_metadata.json"
COMMIT_MANIFEST_REL = "results/stream a/phase 5/reproduction/phase5_commit_manifest.json"
REPRO_DIR = "results/stream a/phase 5/reproduction"

RUN_IDS = [
    "IF_001", "IF_002", "IF_003", "IF_004", "IF_005",
    "LOF_001", "LOF_002", "LOF_003", "LOF_004", "LOF_005",
]
BOOTSTRAP_RUNS = ["IF_003", "IF_004", "LOF_004"]
METRIC_NAMES = [
    "average_precision", "roc_auc", "precision_at_1pct",
    "recall_at_1pct", "f1_at_1pct",
]
THRESHOLDS = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]

PROTOCOL_PATH = "/api/v1/research/phase5a"


# ---------------------------------------------------------------------------
# App fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def p5a_settings(db_url):
    return Settings(
        _env_file=None, environment="test", cors_origins=["http://test.example"],
        git_commit_sha=None, docs_enabled=True, database_url=db_url,
        database_required=True, session_secret=TEST_SESSION_SECRET,
        session_cookie_secure=False, demonstration_sources=True,
    )


@pytest.fixture()
def p5a_app(p5a_settings, db_session_factory):
    from tests.conftest import _truncate_auth_tables
    _truncate_auth_tables(db_session_factory)
    return create_app(
        settings=p5a_settings,
        db_session_factory_override=DatabaseSessionFactory(
            db_session_factory.kw["bind"], db_session_factory
        ),
    )


@pytest.fixture()
def p5a_user(db_session_factory):
    from app.auth.passwords import hash_password
    from app.db.models import User
    from tests.conftest import _truncate_auth_tables
    _truncate_auth_tables(db_session_factory)
    with db_session_factory() as session:
        user = User(
            username="p5a-reviewer",
            password_hash=hash_password(PASSWORD),
            role="reviewer",
            is_active=True,
            display_name="P5A Reviewer",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


@pytest.fixture()
def p5a_client(p5a_app, p5a_user):
    client = TestClient(p5a_app)
    assert login(client, "p5a-reviewer", PASSWORD).status_code == 200
    return client


@pytest.fixture(autouse=True)
def clear_caches():
    _invalidate_layer_a()
    _invalidate_layer_b()
    yield
    _invalidate_layer_a()
    _invalidate_layer_b()


# ---------------------------------------------------------------------------
# Synthetic DVC payload builders (SYNTHETIC — test-only, never canonical)
# ---------------------------------------------------------------------------


def _syn_bootstrap_csv() -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(svc.BOOTSTRAP_METRICS_COLUMNS)
    for rid in BOOTSTRAP_RUNS:
        for i, metric in enumerate(METRIC_NAMES):
            w.writerow([
                rid, metric, f"{0.5 + i * 0.01:.6f}",
                f"{0.51 + i * 0.01:.6f}", "0.02",
                f"{0.4 + i * 0.01:.6f}", f"{0.6 + i * 0.01:.6f}", 2000,
            ])
    return out.getvalue()


def _syn_paired_csv() -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(svc.PAIRED_DIFFERENCES_COLUMNS)
    for i, metric in enumerate(METRIC_NAMES):
        w.writerow([
            "LOF_004 - IF_003", "IF_003", "LOF_004", metric,
            f"{0.05 + i * 0.01:.6f}", f"{0.06 + i * 0.01:.6f}", "0.03",
            f"{-0.02 + i * 0.01:.6f}", f"{0.12 + i * 0.01:.6f}", 2000,
        ])
    return out.getvalue()


def _syn_matrix_csv(kind: str) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["run_id"] + RUN_IDS)
    for i, rid in enumerate(RUN_IDS):
        row = [rid]
        for j, _ in enumerate(RUN_IDS):
            if i == j:
                row.append("1.0")
            else:
                val = 0.3 + 0.05 * ((i + j) % 5)
                if kind == "spearman" and val > 1.0:
                    val = 0.9
                row.append(f"{val:.6f}")
        w.writerow(row)
    return out.getvalue()


def _syn_multithreshold_csv() -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(svc.MULTITHRESHOLD_AGREEMENT_COLUMNS)
    for pct in THRESHOLDS:
        k = round(30000 * pct / 100)
        source = "saved_canonical" if abs(pct - 1.0) < 1e-9 else "derived_topk"
        w.writerow([pct, k, source, 4 + int(pct * 10) % 3, 30000])
    return out.getvalue()


def _syn_hypergeom_csv() -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(svc.HYPERGEOMETRIC_OVERLAP_COLUMNS)
    w.writerow([
        "IF_003", "LOF_004", 1.0, 30000, 300, 300, 120, 480,
        3.0, 40.0, 1e-30, -69.0, -30.0,
        "independent uniform random selection null",
    ])
    return out.getvalue()


def _syn_groups_csv() -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(svc.AGREEMENT_GROUPS_COLUMNS)
    # both=120, if_only=180, lof_only=180, neither=29520 → sum=30000
    # fraud: both=30, if_only=10, lof_only=5, neither=2 → sum=47
    groups = [
        ("both", 120, 30, 0.25, 30 / 47),
        ("if_only", 180, 10, 10 / 180, 10 / 47),
        ("lof_only", 180, 5, 5 / 180, 5 / 47),
        ("neither", 29520, 2, 2 / 29520, 2 / 47),
    ]
    for g, obs, fraud, _, recall in groups:
        w.writerow([
            "IF_003", "LOF_004", 1.0, g, obs, fraud, obs - fraud,
            f"{fraud / obs:.6f}", f"{recall:.6f}",
        ])
    return out.getvalue()


def _syn_discovery_csv(rows_per_run: int = 50) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(svc.FRAUD_DISCOVERY_CURVE_COLUMNS)
    for rid in RUN_IDS:
        for b in range(rows_per_run):
            w.writerow([rid, b, min(b, 5), f"{min(b, 5) / max(b, 1):.6f}", f"{min(b, 5) / 47:.6f}"])
    return out.getvalue()


def _dvc_pointer(md5: str, size: int, path: str) -> bytes:
    return f"outs:\n- md5: {md5}\n  size: {size}\n  hash: md5\n  path: {path}\n".encode()


def _write_payload(root: Path, rel: str, data: bytes) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def _deploy_family(root: Path, family: str, csv_text: str) -> dict:
    """Materialize one SYNTHETIC family payload + pointer under ``root``."""
    specs = {
        "bootstrap": ("phase5_bootstrap_metrics.csv", csv_text),
        "paired": ("phase5_paired_bootstrap_differences.csv", csv_text),
        "spearman": ("phase5_pairwise_spearman.csv", csv_text),
        "jaccard": ("phase5_pairwise_jaccard_1pct.csv", csv_text),
        "multithreshold": ("phase5_multithreshold_agreement.csv", csv_text),
        "hypergeometric": ("phase5_hypergeometric_overlap.csv", csv_text),
        "groups": ("phase5_agreement_groups.csv", csv_text),
        "discovery": ("phase5_fraud_discovery_curve.csv", csv_text),
    }
    name, text = specs[family]
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    data = normalised.encode("utf-8")
    payload_rel = f"{REPRO_DIR}/{name}"
    pointer_rel = f"{payload_rel}.dvc"
    payload_path = _write_payload(root, payload_rel, data)
    pointer_path = _write_payload(
        root, pointer_rel,
        _dvc_pointer(hashlib.md5(data).hexdigest(), len(data), name),
    )
    return {"name": name, "payload_rel": payload_rel, "pointer_rel": pointer_rel,
            "payload_path": payload_path, "pointer_path": pointer_path, "data": data}


def _deploy_all(root: Path) -> dict:
    families = {
        "bootstrap": _syn_bootstrap_csv(),
        "paired": _syn_paired_csv(),
        "spearman": _syn_matrix_csv("spearman"),
        "jaccard": _syn_matrix_csv("jaccard"),
        "multithreshold": _syn_multithreshold_csv(),
        "hypergeometric": _syn_hypergeom_csv(),
        "groups": _syn_groups_csv(),
        "discovery": _syn_discovery_csv(),
    }
    return {fam: _deploy_family(root, fam, text) for fam, text in families.items()}


def use_synthetic_payloads(deploy: dict):
    """Replace only the test's dependency bundle, never production trust state.

    The approved production trust anchor remains immutable. Synthetic SHA
    identities are installed via unittest.mock.patch of the protocol loader
    inside the test context. No mutable production override exists.
    """
    new_specs = []
    hashes: dict[str, str] = {}
    sizes: dict[str, int] = {}
    for fam, _payload_rel, _pointer_rel, role in svc._FAMILY_SPECS:
        d = deploy[fam]
        new_specs.append((fam, str(d["payload_path"]), str(d["pointer_path"]), role))
        hashes[d["name"]] = hashlib.sha256(d["data"]).hexdigest()
        sizes[d["name"]] = len(d["data"])
    return _SyntheticPatch(new_specs, hashes, sizes)

@contextmanager
def _absent_family_specs(tmp_path: Path):
    """Force every family's payload/pointer to nonexistent paths."""
    original = svc._FAMILY_SPECS
    absent_root = tmp_path / "absent"
    absent_root.mkdir(exist_ok=True)
    absent_specs = tuple(
        (fam, str(absent_root / Path(rel).name),
              str(absent_root / Path(ptr).name), role)
        for fam, rel, ptr, role in original
    )
    with patch.object(svc, "_FAMILY_SPECS", absent_specs):
        _invalidate_layer_b()
        try:
            yield
        finally:
            _invalidate_layer_b()

class _SyntheticPatch:
    def __init__(self, new_specs, hashes, sizes):
        self._specs_patch = patch.object(svc, "_FAMILY_SPECS", tuple(new_specs))
        self._hashes = hashes
        self._sizes = sizes

    def __enter__(self):
        from copy import deepcopy
        protocol = deepcopy(svc._load_protocol())
        protocol["manifest_sha256"].update(self._hashes)
        protocol["manifest_size"].update(self._sizes)
        self._protocol_patch = patch.object(svc, "_load_protocol", return_value=protocol)
        self._protocol_patch.start()
        self._specs_patch.start()
        _invalidate_layer_b()
        return self

    def __exit__(self, *exc):
        self._specs_patch.stop()
        self._protocol_patch.stop()
        _invalidate_layer_b()


# ---------------------------------------------------------------------------
# Scenarios 1–3: protocol metadata (Layer A, real Git metadata)
# ---------------------------------------------------------------------------


class TestProtocol:
    def test_protocol_available_without_dvc_payloads(self, p5a_client):
        """1. Verified Git metadata available without any DVC payload."""
        r = p5a_client.get(PROTOCOL_PATH)
        assert r.status_code == 200
        body = r.json()
        assert body["phase"] == "5A"
        assert body["stream"] == "A"
        assert body["models_fitted"] == 0
        assert set(body["capabilities"]) == {
            "bootstrap", "paired", "spearman", "jaccard",
            "multithreshold", "hypergeometric", "groups", "discovery",
        }

    def test_family_specific_artifact_missing_states(self, p5a_client, tmp_path):
        """2. Each family reports artifact_missing independently."""
        with _absent_family_specs(tmp_path):
            caps = p5a_client.get(PROTOCOL_PATH).json()["capabilities"]
            for fam, cap in caps.items():
                assert cap["available"] is False, fam
                assert cap["reason"] == "artifact_missing", fam

    def test_protocol_metadata_mapping(self, p5a_client):
        """3. Exact Phase 5A protocol metadata mapping."""
        body = p5a_client.get(PROTOCOL_PATH).json()
        bp = body["bootstrap_protocol"]
        assert bp["n_replicates"] == 2000
        assert bp["ci_level"] == 0.95
        assert bp["ci_method"] == "percentile"
        assert bp["seed"] == 42
        assert bp["runs_evaluated"] == ["IF_003", "IF_004", "LOF_004"]
        assert bp["paired_comparison"]["definition"] == "LOF_004 - IF_003"
        assert bp["paired_comparison"]["run_a"] == "IF_003"
        assert bp["paired_comparison"]["run_b"] == "LOF_004"
        assert body["sample"]["sample_size"] == 30000
        assert body["sample"]["fraud_count"] == 47
        assert body["canonical_threshold_pct"] == 1.0
        assert body["multi_threshold_percents"] == [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
        assert "exploratory" in body["selection_caveat"].lower()
        # Phase 4 lineage verified.
        assert body["provenance"]["phase4_lineage"]["verified"] is True

    def test_phase4_lineage_sha_matches_pr09(self, p5a_client):
        body = p5a_client.get(PROTOCOL_PATH).json()
        lin = body["provenance"]["phase4_lineage"]
        assert lin["evaluation_dataset_sha256"] == svc.PHASE4_EVAL_DATASET_SHA256
        assert lin["metrics_sha256"] == svc.PHASE4_METRICS_SHA256
        assert lin["run_metadata_sha256"] == svc.PHASE4_RUN_METADATA_SHA256


# ---------------------------------------------------------------------------
# Scenario 4: tampered Git metadata
# ---------------------------------------------------------------------------


class TestTamperedMetadata:
    def test_tampered_run_metadata_rejected(self, p5a_client, tmp_path):
        original = (svc.REPO_ROOT / RUN_META_REL).read_bytes()
        tampered = json.loads(original.decode("utf-8"))
        tampered["sample"]["fraud_count"] = 999
        fake = tmp_path / RUN_META_REL
        _write_payload(tmp_path, RUN_META_REL, json.dumps(tampered, indent=2).encode())
        with patch.object(svc, "RUN_METADATA_PATH", fake):
            r = p5a_client.get(PROTOCOL_PATH)
        assert r.status_code == 503
        assert r.json()["error"]["details"]["reason"] == "integrity_failed"

    def test_tampered_commit_manifest_after_cache_warmup(self, p5a_client, tmp_path):
        """Pinned commit-manifest SHA is rechecked on every catalog request."""
        assert p5a_client.get(PROTOCOL_PATH + "/catalog").status_code == 200
        original = svc.COMMIT_MANIFEST_PATH.read_bytes()
        fake = tmp_path / "modified_phase5_commit_manifest.json"
        fake.write_bytes(original + b" ")
        with patch.object(svc, "COMMIT_MANIFEST_PATH", fake):
            result = p5a_client.get(PROTOCOL_PATH + "/catalog")
        assert result.status_code == 503
        assert result.json()["error"]["details"]["reason"] == "integrity_failed"
        assert p5a_client.get(PROTOCOL_PATH + "/catalog").status_code == 200

    def test_synthetic_trust_override_is_not_in_production(self):
        assert not hasattr(svc, "_SYNTHETIC_MANIFEST_OVERRIDE")

    def test_tampered_config_rejected(self, p5a_client, tmp_path):
        original = (svc.REPO_ROOT / "src/mplad/common/config.py").read_bytes()
        tampered = original.replace(b"PHASE5_CI_LEVEL", b"PHASE5_CI_LEVEL_X")
        assert tampered != original
        fake = tmp_path / "src/mplad/common/config.py"
        _write_payload(tmp_path, "src/mplad/common/config.py", tampered)
        with patch.object(svc, "CONFIG_PATH", fake):
            r = p5a_client.get(PROTOCOL_PATH)
        assert r.status_code == 503
        assert r.json()["error"]["details"]["reason"] == "integrity_failed"


# ---------------------------------------------------------------------------
# Scenarios 5–6: DVC pointer verification + CRLF handling
# ---------------------------------------------------------------------------


class TestDVCVerification:
    def test_pointer_md5_mismatch_fails_closed(self, tmp_path, p5a_client):
        deploy = _deploy_all(tmp_path)
        bad = deploy["bootstrap"]
        bad["pointer_path"].write_bytes(
            _dvc_pointer("0" * 32, len(bad["data"]), bad["name"])
        )
        with use_synthetic_payloads(deploy):
            r = p5a_client.get(PROTOCOL_PATH + "/bootstrap")
        assert r.status_code == 503
        assert r.json()["error"]["details"]["reason"] == "integrity_failed"

    def test_pointer_size_mismatch_fails_closed(self, tmp_path, p5a_client):
        deploy = _deploy_all(tmp_path)
        bad = deploy["bootstrap"]
        bad["pointer_path"].write_bytes(
            _dvc_pointer(hashlib.md5(bad["data"]).hexdigest(), len(bad["data"]) + 1, bad["name"])
        )
        with use_synthetic_payloads(deploy):
            r = p5a_client.get(PROTOCOL_PATH + "/bootstrap")
        assert r.status_code == 503
        assert r.json()["error"]["details"]["reason"] == "integrity_failed"

    def test_crlf_payload_form_verifies(self, tmp_path, p5a_client):
        """6. Windows LF/CRLF representation-compatible digest handling."""
        deploy = _deploy_all(tmp_path)
        lf = deploy["bootstrap"]["data"]
        crlf = lf.replace(b"\n", b"\r\n")
        deploy["bootstrap"]["payload_path"].write_bytes(crlf)
        deploy["bootstrap"]["pointer_path"].write_bytes(
            _dvc_pointer(hashlib.md5(crlf).hexdigest(), len(crlf), "phase5_bootstrap_metrics.csv")
        )
        deploy["bootstrap"]["data"] = crlf
        with use_synthetic_payloads(deploy):
            r = p5a_client.get(PROTOCOL_PATH + "/bootstrap")
        assert r.status_code == 200, r.text

    def test_lf_checkout_matches_crlf_pointer_and_manifest(self, tmp_path, p5a_client):
        """DVC and SHA pin the CRLF form; the checked-out CSV is LF."""
        deploy = _deploy_all(tmp_path)
        lf = deploy["bootstrap"]["data"]
        crlf = lf.replace(b"\n", b"\r\n")
        deploy["bootstrap"]["pointer_path"].write_bytes(
            _dvc_pointer(hashlib.md5(crlf).hexdigest(), len(crlf),
                         "phase5_bootstrap_metrics.csv")
        )
        # Keep the LF file in place. The synthetic manifest must pin exactly
        # the same CRLF byte representation as the DVC pointer.
        deploy["bootstrap"]["data"] = crlf
        with use_synthetic_payloads(deploy):
            response = p5a_client.get(PROTOCOL_PATH + "/bootstrap")
        assert response.status_code == 200, response.text

    def test_unexpected_output_path_rejected(self, tmp_path, p5a_client):
        deploy = _deploy_all(tmp_path)
        bad = deploy["bootstrap"]
        bad["pointer_path"].write_bytes(
            _dvc_pointer(hashlib.md5(bad["data"]).hexdigest(), len(bad["data"]), "other.csv")
        )
        with use_synthetic_payloads(deploy):
            r = p5a_client.get(PROTOCOL_PATH + "/bootstrap")
        assert r.status_code == 503
        assert r.json()["error"]["details"]["reason"] == "integrity_failed"

    def test_malformed_pointer_rejected(self, tmp_path, p5a_client):
        deploy = _deploy_all(tmp_path)
        deploy["bootstrap"]["pointer_path"].write_bytes(b"outs: []\n")
        with use_synthetic_payloads(deploy):
            r = p5a_client.get(PROTOCOL_PATH + "/bootstrap")
        assert r.status_code == 503


# ---------------------------------------------------------------------------
# Scenario 7: post-cache mutation / removal / restoration
# ---------------------------------------------------------------------------


class TestCacheIntegrity:
    def test_payload_altered_after_warmup_then_recovers(self, tmp_path, p5a_client):
        deploy = _deploy_all(tmp_path)
        with use_synthetic_payloads(deploy):
            assert p5a_client.get(PROTOCOL_PATH + "/bootstrap").status_code == 200
            data = deploy["bootstrap"]["payload_path"].read_bytes()
            tampered = data.replace(b"0.500000", b"0.900000")
            assert len(tampered) == len(data)
            deploy["bootstrap"]["payload_path"].write_bytes(tampered)
            assert p5a_client.get(PROTOCOL_PATH + "/bootstrap").status_code == 503
            deploy["bootstrap"]["payload_path"].write_bytes(data)
            assert p5a_client.get(PROTOCOL_PATH + "/bootstrap").status_code == 200

    def test_payload_removed_after_warmup(self, tmp_path, p5a_client):
        deploy = _deploy_all(tmp_path)
        with use_synthetic_payloads(deploy):
            assert p5a_client.get(PROTOCOL_PATH + "/groups").status_code == 200
            deploy["groups"]["payload_path"].unlink()
            assert p5a_client.get(PROTOCOL_PATH + "/groups").status_code == 503


# ---------------------------------------------------------------------------
# Scenario 8: independent family availability
# ---------------------------------------------------------------------------


class TestIndependentAvailability:
    def test_one_missing_family_does_not_disable_others(self, tmp_path, p5a_client):
        deploy = _deploy_all(tmp_path)
        # Remove the discovery payload only.
        deploy["discovery"]["payload_path"].unlink()
        with use_synthetic_payloads(deploy):
            # Bootstrap still works.
            assert p5a_client.get(PROTOCOL_PATH + "/bootstrap").status_code == 200
            # Discovery is unavailable.
            r = p5a_client.get(PROTOCOL_PATH + "/discovery-curve?run_id=IF_001")
            assert r.status_code == 503
            assert r.json()["error"]["details"]["reason"] == "artifact_missing"
            # The catalog reports mixed availability.
            caps = p5a_client.get(PROTOCOL_PATH).json()["capabilities"]
            assert caps["bootstrap"]["available"] is True
            assert caps["discovery"]["available"] is False


# ---------------------------------------------------------------------------
# Scenarios 9–17: per-family scientific contracts (Layer B, synthetic payloads)
# ---------------------------------------------------------------------------


class TestFamilies:
    @pytest.fixture(autouse=True)
    def _deploy(self, tmp_path, p5a_client):
        self.deploy = _deploy_all(tmp_path)
        self._cm = use_synthetic_payloads(self.deploy)
        self._cm.__enter__()
        yield
        self._cm.__exit__(None, None, None)

    def test_bootstrap_schema_bounds_replicates(self, p5a_client):
        """9. Bootstrap schema, bounds, replicate count, interval definition."""
        r = p5a_client.get(PROTOCOL_PATH + "/bootstrap")
        assert r.status_code == 200
        body = r.json()
        assert len(body["metrics"]) == 3 * 5  # 3 runs × 5 metrics
        for m in body["metrics"]:
            assert m["run_id"] in BOOTSTRAP_RUNS
            assert m["metric"] in METRIC_NAMES
            assert m["n_replicates"] == 2000
            assert m["ci_lower"] <= m["ci_upper"]

    def test_paired_direction_and_posthoc_warning(self, p5a_client):
        """10. Paired-difference direction + post-hoc warning."""
        r = p5a_client.get(PROTOCOL_PATH + "/paired-differences")
        assert r.status_code == 200
        body = r.json()
        assert body["direction"] == "LOF_004 - IF_003"
        assert body["run_a"] == "IF_003"
        assert body["run_b"] == "LOF_004"
        assert len(body["differences"]) == 5
        assert "exploratory" in body["selection_caveat"].lower()

    def test_spearman_labels_symmetry_diagonal_bounds(self, p5a_client):
        """11. Spearman run labels, symmetry, diagonal and bounds."""
        r = p5a_client.get(PROTOCOL_PATH + "/agreement/spearman")
        assert r.status_code == 200
        body = r.json()
        assert body["kind"] == "spearman"
        assert body["run_labels"] == RUN_IDS
        assert len(body["matrix"]) == 10
        by_id = {row["run_id"]: row for row in body["matrix"]}
        for a in RUN_IDS:
            assert abs(by_id[a]["values"][a] - 1.0) < 1e-9
            for b in RUN_IDS:
                assert abs(by_id[a]["values"][b] - by_id[b]["values"][a]) < 1e-6

    def test_jaccard_labels_and_bounds(self, p5a_client):
        """12. Jaccard canonical 1% labels and bounds."""
        r = p5a_client.get(PROTOCOL_PATH + "/agreement/jaccard")
        assert r.status_code == 200
        body = r.json()
        assert body["kind"] == "jaccard"
        assert body["run_labels"] == RUN_IDS
        for row in body["matrix"]:
            for v in row["values"].values():
                assert 0.0 <= v <= 1.0

    def test_hypergeometric_null_and_log_probability(self, p5a_client):
        """13. Hypergeometric null + log-probability representation."""
        r = p5a_client.get(PROTOCOL_PATH + "/overlap-null")
        assert r.status_code == 200
        body = r.json()
        assert body["n_observations"] == 30000
        assert "uniform random" in body["null_model"].lower()
        # log_survival is preserved (not exponentiated).
        assert isinstance(body["log_survival"], float)
        assert body["log_survival"] < 0

    def test_groups_conservation(self, p5a_client):
        """14. Agreement-group conservation of sample and labelled positives."""
        r = p5a_client.get(PROTOCOL_PATH + "/groups")
        assert r.status_code == 200
        body = r.json()
        assert {g["group"] for g in body["groups"]} == {"both", "if_only", "lof_only", "neither"}
        assert sum(g["observation_count"] for g in body["groups"]) == 30000
        assert sum(g["fraud_count"] for g in body["groups"]) == 47
        assert abs(sum(g["recall_contribution"] for g in body["groups"]) - 1.0) < 1e-6

    def test_saved_disjoint_review_groups(self, p5a_client):
        """FR-17: serve direct saved counts, not runtime policy arithmetic."""
        response = p5a_client.get(PROTOCOL_PATH + "/review-policies")
        assert response.status_code == 200, response.text
        rows = response.json()["groups"]
        assert {r["group"] for r in rows} == {
            "both", "if_only", "lof_only", "neither"
        }
        assert sum(r["observation_count"] for r in rows) == 30000
        assert sum(r["fraud_count"] for r in rows) == 47
        assert all("fraud_proportion" in r and "recall_contribution" in r for r in rows)

    def test_requested_composite_endpoints(self, p5a_client):
        """Verify the four publicly readable PR-10 resource paths."""
        catalog = p5a_client.get(PROTOCOL_PATH + "/catalog")
        uncertainty = p5a_client.get(PROTOCOL_PATH + "/uncertainty")
        agreement = p5a_client.get(PROTOCOL_PATH + "/agreement")
        policies = p5a_client.get(PROTOCOL_PATH + "/review-policies")
        assert catalog.status_code == 200
        assert uncertainty.status_code == 200
        assert set(uncertainty.json()) == {"bootstrap", "paired_differences"}
        assert agreement.status_code == 200
        assert set(agreement.json()) == {"spearman", "jaccard"}
        assert policies.status_code == 200

    def test_thresholds_selection_source_distinction(self, p5a_client):
        """16. Multi-threshold saved vs derived distinction."""
        r = p5a_client.get(PROTOCOL_PATH + "/thresholds")
        assert r.status_code == 200
        body = r.json()
        assert len(body["thresholds"]) == 6
        canonical = [t for t in body["thresholds"] if t["is_canonical"]]
        assert len(canonical) == 1
        assert canonical[0]["selection_source"] == "saved_canonical"
        assert canonical[0]["threshold_pct"] == 1.0
        derived = [t for t in body["thresholds"] if not t["is_canonical"]]
        assert all(t["selection_source"] == "derived_topk" for t in derived)

    def test_discovery_curve_pagination_bounded(self, p5a_client):
        """17. Discovery-curve pagination is bounded."""
        r = p5a_client.get(PROTOCOL_PATH + "/discovery-curve?run_id=IF_001&limit=10&offset=0")
        assert r.status_code == 200
        body = r.json()
        assert body["limit"] == 10
        assert len(body["rows"]) <= 10
        assert body["total"] == 50  # syn fixture rows_per_run
        assert body["has_more"] is True
        # Page 2.
        r2 = p5a_client.get(PROTOCOL_PATH + "/discovery-curve?run_id=IF_001&limit=10&offset=40")
        assert r2.status_code == 200
        assert r2.json()["has_more"] is False

    def test_discovery_unknown_run_returns_404(self, p5a_client):
        r = p5a_client.get(PROTOCOL_PATH + "/discovery-curve?run_id=IF_009")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Scenario 18: public read access + private case-write isolation
# ---------------------------------------------------------------------------


class TestAccessControl:
    def test_anonymous_reader_can_read_phase5a(self, p5a_app):
        """18. Public research GET access; anonymous cannot write cases."""
        client = TestClient(p5a_app)
        for path in [PROTOCOL_PATH, PROTOCOL_PATH + "/bootstrap",
                     PROTOCOL_PATH + "/agreement/spearman"]:
            r = client.get(path)
            assert r.status_code in (200, 503), path
            assert r.status_code not in (401, 403)
        # Anonymous cannot create a case.
        csrf = get_csrf_token(client)
        create = client.post("/api/v1/cases", json={
            "dataset_id": "synthetic-demonstration",
            "snapshot_id": "synthetic-v1",
            "record_ref": "synth-001",
            "title": "should fail",
            "created_by": "anon",
        }, headers={"X-CSRF-Token": csrf})
        assert create.status_code in (401, 403, 422)

    def test_reviewer_can_write_case_and_history_is_private(self, p5a_app, p5a_user):
        client = TestClient(p5a_app)
        assert login(client, "p5a-reviewer", PASSWORD).status_code == 200
        csrf = get_csrf_token(client)
        create = client.post("/api/v1/cases", json={
            "dataset_id": "synthetic-demonstration",
            "snapshot_id": "synthetic-v1",
            "record_ref": "synth-001",
            "title": "Phase 5A isolation test",
            "created_by": "p5a-reviewer",
        }, headers={"X-CSRF-Token": csrf})
        assert create.status_code in (200, 201), create.text
        case_id = create.json()["id"]
        # Anonymous cannot read private history.
        anon = TestClient(p5a_app)
        assert anon.get(f"/api/v1/cases/{case_id}/history").status_code in (401, 403)
        # Reviewer can.
        assert client.get(f"/api/v1/cases/{case_id}/history").status_code == 200


# ---------------------------------------------------------------------------
# Scenario 19: no modelling / pickle / DVC downloads
# ---------------------------------------------------------------------------


class TestNoModelling:
    def test_no_pickle_sklearn_dvc_import_during_requests(self, tmp_path, p5a_client):
        """19. No HTTP-triggered model fitting, bootstrap, DVC pull or mutation."""
        import builtins
        real_import = builtins.__import__
        forbidden: list[str] = []

        def guarded(name, *args, **kwargs):
            root = name.split(".")[0]
            if root in {"pickle", "dvc", "sklearn", "numpy", "pandas", "scipy", "subprocess"}:
                forbidden.append(name)
            return real_import(name, *args, **kwargs)

        deploy = _deploy_all(tmp_path)
        with use_synthetic_payloads(deploy), patch.object(builtins, "__import__", side_effect=guarded):
            for path in [PROTOCOL_PATH, PROTOCOL_PATH + "/bootstrap",
                         PROTOCOL_PATH + "/groups", PROTOCOL_PATH + "/review-policies",
                         PROTOCOL_PATH + "/discovery-curve?run_id=IF_001"]:
                p5a_client.get(path)
        assert forbidden == [], f"forbidden imports: {forbidden}"

    def test_service_source_has_no_pickle_dvc(self):
        source = Path(svc.__file__).read_text()
        assert "import pickle" not in source
        assert "pickle.load" not in source
        assert "import dvc" not in source
        assert "subprocess" not in source
        assert "dvc.api" not in source


# ---------------------------------------------------------------------------
# Scenario 20: no secret/path leakage in errors
# ---------------------------------------------------------------------------


class TestNoLeakage:
    def test_error_responses_contain_no_server_paths(self, p5a_client):
        """20. No secret/path leakage in API errors."""
        paths = [
            PROTOCOL_PATH + "/bootstrap",
            PROTOCOL_PATH + "/agreement/foo",
            PROTOCOL_PATH + "/discovery-curve?run_id=IF_001",
        ]
        for path in paths:
            r = p5a_client.get(path)
            body_text = json.dumps(r.json())
            assert "/home/" not in body_text
            assert "C:\\\\Users" not in body_text
            assert "password" not in body_text.lower()
            assert "secret" not in body_text.lower()


# ---------------------------------------------------------------------------
# Scenario 21: PR-08/09 still intact
# ---------------------------------------------------------------------------


class TestRegressions:
    def test_pr08_research_sources_still_work(self, p5a_client):
        """21. Existing PR-08/09 functionality remains intact."""
        r = p5a_client.get("/api/v1/research/sources")
        assert r.status_code == 200
        assert r.json()["count"] >= 1

    def test_pr09_benchmark_catalog_still_works(self, p5a_client):
        r = p5a_client.get("/api/v1/research/benchmark/experiments")
        assert r.status_code == 200
        assert r.json()["count"] == 10


# ---------------------------------------------------------------------------
# Scenario 22: OpenAPI / TypeScript drift
# ---------------------------------------------------------------------------


class TestOpenAPI:
    def test_phase5a_operations_present(self, p5a_client):
        """22. OpenAPI/TypeScript drift checks."""
        spec = p5a_client.get("/openapi.json").json()
        paths = set(spec["paths"])
        for p in [
            "/api/v1/research/phase5a",
            "/api/v1/research/phase5a/bootstrap",
            "/api/v1/research/phase5a/paired-differences",
            "/api/v1/research/phase5a/agreement/{kind}",
            "/api/v1/research/phase5a/overlap-null",
            "/api/v1/research/phase5a/groups",
            "/api/v1/research/phase5a/policies",
            "/api/v1/research/phase5a/thresholds",
            "/api/v1/research/phase5a/discovery-curve",
            "/api/v1/research/phase5a/catalog",
            "/api/v1/research/phase5a/uncertainty",
            "/api/v1/research/phase5a/agreement",
            "/api/v1/research/phase5a/review-policies",
        ]:
            assert p in paths, p
        # Unique operation IDs.
        op_ids = [op.get("operationId") for p in spec["paths"].values() for op in p.values()]
        assert len(op_ids) == len(set(op_ids))

    def test_committed_openapi_matches_app(self, p5a_client):
        live = p5a_client.get("/openapi.json").json()
        committed = json.loads((REPO_ROOT / "backend" / "contracts" / "openapi.json").read_text())
        assert sorted(live["paths"]) == sorted(committed["paths"])

    def test_generated_ts_contains_phase5a_types(self):
        gen = (REPO_ROOT / "frontend" / "src" / "api" / "contracts.gen.ts").read_text()
        for name in ["Phase5AProtocolResponse", "BootstrapMetricsResponse",
                     "AgreementMatrixResponse", "HypergeometricResponse",
                     "ReviewPoliciesResponse", "DiscoveryCurveResponse"]:
            assert name in gen, name


# ---------------------------------------------------------------------------
# Scenario 24: clean-checkout readiness (health + unrelated routes)
# ---------------------------------------------------------------------------


class TestCleanCheckoutReadiness:
    def test_health_and_unrelated_routes_work_without_payloads(
        self, p5a_app, p5a_user, tmp_path
    ):
        """24. Unrelated application readiness during missing research payloads."""
        client = TestClient(p5a_app)
        assert client.get("/api/v1/health/live").status_code == 200
        with _absent_family_specs(tmp_path):
            assert client.get("/api/v1/research/phase5a").status_code == 200
            # Layer B routes report the sanitized unavailable state (not a crash).
            assert client.get("/api/v1/research/phase5a/bootstrap").status_code == 503
            assert client.get("/api/v1/research/sources").status_code == 200


# ---------------------------------------------------------------------------
# Service-level contract tests (no HTTP)
# ---------------------------------------------------------------------------


class TestServiceContract:
    def test_availability_probe_never_raises(self):
        svc_obj = Phase5AEvidenceService()
        caps = svc_obj.availability()
        assert set(caps) == {"bootstrap", "paired", "spearman", "jaccard",
                             "multithreshold", "hypergeometric", "groups", "discovery"}

    def test_family_absent_raises_unavailable(self, tmp_path):
        with _absent_family_specs(tmp_path):
            s = Phase5AEvidenceService()
            for method in [s.get_bootstrap, s.get_paired_differences,
                           s.get_hypergeometric, s.get_groups,
                           s.get_thresholds]:
                with pytest.raises(Phase5AUnavailableError):
                    method()
            with pytest.raises(Phase5AUnavailableError):
                s.get_agreement_matrix("spearman")
            with pytest.raises(Phase5AUnavailableError):
                s.get_discovery_curve("IF_001")

    def test_unknown_kind_raises_source_not_found(self):
        s = Phase5AEvidenceService()
        with pytest.raises(SourceNotFoundError):
            s.get_agreement_matrix("foo")

    def test_unknown_discovery_run_raises_404_before_payload(self):
        s = Phase5AEvidenceService()
        with pytest.raises(SourceNotFoundError):
            s.get_discovery_curve("IF_009")

    def test_discovery_limit_clamped(self, tmp_path):
        deploy = _deploy_all(tmp_path)
        with use_synthetic_payloads(deploy):
            s = Phase5AEvidenceService()
            r = s.get_discovery_curve("IF_001", limit=999, offset=-5)
            assert r["limit"] <= svc.DISCOVERY_MAX_LIMIT
            assert r["offset"] == 0


class TestTrustedLocalRealDvcPayloads:
    """Optional trusted-lane checks; never downloads or modifies DVC evidence.

    The clean-checkout lane explicitly SKIPS rather than fabricating success.
    When materialized source CSVs are present, the production reader verifies
    both DVC and Phase 5 manifest identities before these HTTP assertions.
    """

    REQUIRED_FAMILIES = ("bootstrap", "paired", "spearman", "jaccard", "groups")

    def test_materialized_phase5a_evidence_via_live_api(self, p5a_client):
        missing = [
            rel for fam, rel, _pointer, _role in svc._FAMILY_SPECS
            if fam in self.REQUIRED_FAMILIES and not (svc.REPO_ROOT / rel).is_file()
        ]
        if missing:
            pytest.skip("NOT RUN - DATA UNAVAILABLE: materialized Phase 5A CSVs absent")

        catalog = p5a_client.get(PROTOCOL_PATH + "/catalog")
        assert catalog.status_code == 200, catalog.text
        for family in self.REQUIRED_FAMILIES:
            status = catalog.json()["capabilities"][family]
            assert status["available"], f"{family}: {status}"

        uncertainty = p5a_client.get(PROTOCOL_PATH + "/uncertainty")
        assert uncertainty.status_code == 200, uncertainty.text
        assert len(uncertainty.json()["bootstrap"]["metrics"]) == 15
        assert len(uncertainty.json()["paired_differences"]["differences"]) == 5
        agreement = p5a_client.get(PROTOCOL_PATH + "/agreement")
        assert agreement.status_code == 200, agreement.text
        for kind in ("spearman", "jaccard"):
            assert len(agreement.json()[kind]["matrix"]) == 10
        policies = p5a_client.get(PROTOCOL_PATH + "/review-policies")
        assert policies.status_code == 200, policies.text
        rows = policies.json()["groups"]
        assert len(rows) == 4
        assert sum(r["observation_count"] for r in rows) == 30000
        assert sum(r["fraud_count"] for r in rows) == 47
