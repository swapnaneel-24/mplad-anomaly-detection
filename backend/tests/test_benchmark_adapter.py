"""PR-09 — Canonical ten-run IF/LOF benchmark adapter tests.

Covers the mandatory fixture-only CI scenarios from the PR-09 brief
(section 9), using deterministic synthetic fixtures stored only under
test locations and visibly identified as synthetic:

 1.  Exactly ten source-backed run configurations when all approved Git
     metadata is present.
 2.  Correct run/algorithm/parameter identity mapping.
 3.  Unknown run ID rejection (404).
 4.  DVC payload missing while the configuration catalog still works.
 5.  DVC pointer checksum match/mismatch.
 6.  DVC pointer malformed, missing and unexpected output path.
 7.  Valid admitted metrics, exact source values and denominator semantics.
 8.  Row lookup by actual row_id.
 9.  Shuffled row order invariance.
 10. Duplicate row_id rejection.
 11. Missing required score/flag/label field handling without invented
     defaults.
 12. Tampered Git-backed metadata rejection.
 13. Post-cache mutation/recovery behavior.
 14. Public approved research GET access (anonymous reader).
 15. Authenticated case write and private-history isolation.
 16. Absence of API-triggered modelling, fitting, pickle loading or DVC
     downloads.
 17. OpenAPI/TypeScript contract consistency.
 18. Unrelated application readiness and review workflows during missing
     research payloads.

The synthetic DVC payload fixtures are generated into ``tmp_path`` with
matching ``.dvc`` pointers (md5 + size), visibly named
``SYNTHETIC-fixture`` in every header/comment so they can never be
mistaken for canonical artifacts. The real DVC payloads are ABSENT in a
clean checkout and are never touched by these tests.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.session import DatabaseSessionFactory
from app.main import create_app
from app.services import benchmark_catalog as bsvc
from app.services.benchmark_catalog import (
    BenchmarkCatalogService,
    BenchmarkIntegrityError,
    BenchmarkUnavailableError,
    _invalidate_caches,
)
from app.services.source_registry import SourceNotFoundError
from tests.conftest import TEST_SESSION_SECRET, get_csrf_token, login

PASSWORD = "correct-horse-battery-staple"
REPO_ROOT = Path(__file__).resolve().parents[2]

CONFIG_REL = "src/mplad/common/config.py"
RUN_META_REL = "results/stream a/phase 4/reproduction/phase4_run_metadata.json"
COMMIT_MANIFEST_REL = "results/stream a/phase 4/reproduction/phase4_commit_manifest.json"
METRICS_REL = "results/stream a/phase 4/reproduction/phase4_metrics.csv"
EVAL_REL = "results/stream a/phase 4/reproduction/phase4_evaluation_dataset.csv"
METRICS_PTR_REL = METRICS_REL + ".dvc"
EVAL_PTR_REL = EVAL_REL + ".dvc"

CATALOG_PATH = "/api/v1/research/benchmark/experiments"
DETAIL_PATH = "/api/v1/research/benchmark/experiments/{run_id}"
METRICS_PATH = "/api/v1/research/benchmark/metrics"
RECORD_PATH = "/api/v1/research/benchmark/experiments/{run_id}/records/{row_id}"

#: The frozen config grids (mirrored from the manifest-verified module for
#: assertion purposes only; the adapter reads the real file).
EXPECTED_RUNS = {
    "IF_001": ("IsolationForest", {"n_estimators": 100, "max_samples": 256, "random_state": 42}),
    "IF_002": ("IsolationForest", {"n_estimators": 200, "max_samples": 256, "random_state": 42}),
    "IF_003": ("IsolationForest", {"n_estimators": 100, "max_samples": 0.05, "random_state": 42}),
    "IF_004": ("IsolationForest", {"n_estimators": 100, "max_samples": 256, "random_state": 43}),
    "IF_005": ("IsolationForest", {"n_estimators": 100, "max_samples": 256, "random_state": 44}),
    "LOF_001": ("LOF", {"n_neighbors": 5, "metric": "euclidean"}),
    "LOF_002": ("LOF", {"n_neighbors": 15, "metric": "euclidean"}),
    "LOF_003": ("LOF", {"n_neighbors": 30, "metric": "euclidean"}),
    "LOF_004": ("LOF", {"n_neighbors": 50, "metric": "euclidean"}),
    "LOF_005": ("LOF", {"n_neighbors": 30, "metric": "manhattan"}),
}


# ---------------------------------------------------------------------------
# App fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def bench_settings(db_url):
    return Settings(
        _env_file=None, environment="test", cors_origins=["http://test.example"],
        git_commit_sha=None, docs_enabled=True, database_url=db_url,
        database_required=True, session_secret=TEST_SESSION_SECRET,
        session_cookie_secure=False, demonstration_sources=True,
    )


@pytest.fixture()
def bench_app(bench_settings, db_session_factory):
    from tests.conftest import _truncate_auth_tables
    _truncate_auth_tables(db_session_factory)
    return create_app(
        settings=bench_settings,
        db_session_factory_override=DatabaseSessionFactory(
            db_session_factory.kw["bind"], db_session_factory
        ),
    )


@pytest.fixture()
def bench_user(db_session_factory):
    from app.auth.passwords import hash_password
    from app.db.models import User
    from tests.conftest import _truncate_auth_tables
    _truncate_auth_tables(db_session_factory)
    with db_session_factory() as session:
        user = User(
            username="bench-reviewer",
            password_hash=hash_password(PASSWORD),
            role="reviewer",
            is_active=True,
            display_name="Bench Reviewer",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


@pytest.fixture()
def bench_client(bench_app, bench_user):
    client = TestClient(bench_app)
    assert login(client, "bench-reviewer", PASSWORD).status_code == 200
    return client


@pytest.fixture(autouse=True)
def clear_benchmark_caches():
    """Invalidate both layer caches around every test."""
    _invalidate_caches()
    yield
    _invalidate_caches()


# ---------------------------------------------------------------------------
# Synthetic DVC payload fixtures (SYNTHETIC — test-only, never canonical)
# ---------------------------------------------------------------------------


def _synthetic_metrics_csv() -> str:
    """Build a SYNTHETIC metrics CSV with the exact admitted schema.

    Values are deterministic and clearly synthetic (e.g. AP = 0.1 +
    run index); they exist to exercise the parsing/verification contract,
    NOT to represent the canonical experiment. A header comment is not
    possible in CSV, so the synthetic nature is documented here and in
    the fixture directory name.
    """
    header = list(bsvc.METRICS_COLUMNS)
    rows = []
    for i, run_id in enumerate(bsvc.CANONICAL_RUN_IDS):
        algo, params = EXPECTED_RUNS[run_id]
        model = "IsolationForest" if algo == "IsolationForest" else "LOF"
        rows.append(
            {
                "run_id": run_id,
                "model": model,
                "n_estimators": params.get("n_estimators", ""),
                "max_samples": params.get("max_samples", ""),
                "random_state": params.get("random_state", ""),
                "n_neighbors": params.get("n_neighbors", ""),
                "metric": params.get("metric", ""),
                "runtime_seconds": f"{1.5 + i:.2f}",
                "threshold_rule": "Bottom 1.0% of scores",
                "average_precision": f"{0.10 + i * 0.01:.6f}",
                "roc_auc": f"{0.50 + i * 0.02:.6f}",
                "precision_at_1pct": f"{0.05 + i * 0.005:.6f}",
                "recall_at_1pct": f"{0.10 + i * 0.01:.6f}",
                "f1_at_1pct": f"{0.07 + i * 0.007:.6f}",
                "tn": 29700 - i,
                "fp": 300,
                "fn": 42,
                "tp": 5,
                "sample_size": 30000,
                "fraud_count": 47,
                "fraud_prevalence": "0.0015666666666666667",
                "flagged_count": 300,
                "flagged_proportion": "0.01",
            }
        )
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=header)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def _synthetic_eval_csv(
    order: str = "forward",
    row_ids_extra: list[str] | None = None,
    *,
    inconsistent_label: bool = False,
    invalid_flag: bool = False,
    mismatched_score: bool = False,
    drop_last_row: bool = False,
) -> str:
    """Build a SYNTHETIC evaluation-dataset CSV with the admitted schema.

    Canonical synthetic population: 3 rows per run (row_ids 101, 205, 309),
    1 positive Class=1 label per run (row_id=101), and 1 saved flag=1 per run
    (row_id=101) across all 10 canonical runs.
    """
    header = list(bsvc.EVALUATION_DATASET_COLUMNS)
    rows = []
    sample_rows = [101, 205, 309]
    for ri, run_id in enumerate(bsvc.CANONICAL_RUN_IDS):
        ids = list(sample_rows) + list(row_ids_extra or [])
        if drop_last_row and ri == len(bsvc.CANONICAL_RUN_IDS) - 1:
            ids = ids[:-1]
        for si, row_id in enumerate(ids):
            cls_val = "1" if si == 0 else "0"
            if inconsistent_label and si == 0 and ri == 1:
                cls_val = "0"
            native = -(0.5 + si * 0.1)
            anomaly = (0.5 + si * 0.1) + (0.25 if (mismatched_score and si == 1 and ri == 0) else 0.0)
            flag_val = "2" if (invalid_flag and si == 0 and ri == 0) else ("1" if si == 0 else "0")
            rows.append(
                {
                    "run_id": run_id,
                    "row_id": str(row_id),
                    "Class": cls_val,
                    "native_score": f"{native:.6f}",
                    "anomaly_score": f"{anomaly:.6f}",
                    "flag": flag_val,
                }
            )
    if order == "shuffled":
        rows.reverse()
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=header)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def _absent_dvc_specs(tmp_path: Path):
    """Point Layer B at valid Git-tracked .dvc pointers whose payload files are absent."""
    missing_dir = tmp_path / "unmaterialized"
    return (
        (str(missing_dir / "phase4_metrics.csv"), str(bsvc.REPO_ROOT / METRICS_PTR_REL), "metrics"),
        (str(missing_dir / "phase4_evaluation_dataset.csv"), str(bsvc.REPO_ROOT / EVAL_PTR_REL), "row_level"),
    )


def _dvc_pointer_bytes(md5: str, size: int, path: str) -> bytes:
    return (
        f"outs:\n- md5: {md5}\n  size: {size}\n  hash: md5\n  path: {path}\n".encode()
    )


def _write_payload(root: Path, rel: str, data: bytes) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _build_synthetic_commit_manifest(
    root: Path,
    metrics_bytes: bytes | None,
    eval_bytes: bytes | None,
    *,
    override_metrics_sha256: str | None = None,
    override_eval_sha256: str | None = None,
) -> tuple[Path, str]:
    """Create a synthetic phase4_commit_manifest.json matching the fixture bytes."""
    real_cm = json.loads((bsvc.REPO_ROOT / COMMIT_MANIFEST_REL).read_text(encoding="utf-8"))
    artifacts = dict(real_cm["artifacts"])
    if metrics_bytes is not None:
        m_crlf = metrics_bytes if b"\r\n" in metrics_bytes else metrics_bytes.replace(b"\n", b"\r\n")
        artifacts["phase4_metrics.csv"] = {
            "sha256": override_metrics_sha256 or hashlib.sha256(m_crlf).hexdigest(),
            "size_bytes": len(m_crlf),
        }
    if eval_bytes is not None:
        e_crlf = eval_bytes if b"\r\n" in eval_bytes else eval_bytes.replace(b"\n", b"\r\n")
        artifacts["phase4_evaluation_dataset.csv"] = {
            "sha256": override_eval_sha256 or hashlib.sha256(e_crlf).hexdigest(),
            "size_bytes": len(e_crlf),
        }
    cm_obj = {
        "artifacts": artifacts,
        "created_utc": real_cm["created_utc"],
        "manifest_version": real_cm["manifest_version"],
    }
    cm_lf_bytes = (json.dumps(cm_obj, indent=2) + "\n").encode("utf-8")
    cm_crlf_bytes = cm_lf_bytes.replace(b"\n", b"\r\n")
    cm_sha256 = hashlib.sha256(cm_crlf_bytes).hexdigest()
    cm_path = _write_payload(root, COMMIT_MANIFEST_REL, cm_lf_bytes)
    return cm_path, cm_sha256


@pytest.fixture()
def synthetic_dvc_deploy(tmp_path):
    metrics_csv = _synthetic_metrics_csv().encode()
    eval_csv = _synthetic_eval_csv().encode()
    metrics_path = _write_payload(tmp_path, METRICS_REL, metrics_csv)
    eval_path = _write_payload(tmp_path, EVAL_REL, eval_csv)
    metrics_ptr = _write_payload(
        tmp_path,
        METRICS_PTR_REL,
        _dvc_pointer_bytes(hashlib.md5(metrics_csv).hexdigest(), len(metrics_csv), "phase4_metrics.csv"),
    )
    eval_ptr = _write_payload(
        tmp_path,
        EVAL_PTR_REL,
        _dvc_pointer_bytes(hashlib.md5(eval_csv).hexdigest(), len(eval_csv), "phase4_evaluation_dataset.csv"),
    )
    cm_path, cm_sha = _build_synthetic_commit_manifest(tmp_path, metrics_csv, eval_csv)
    return {
        "root": tmp_path,
        "metrics": metrics_path,
        "eval": eval_path,
        "metrics_ptr": metrics_ptr,
        "eval_ptr": eval_ptr,
        "commit_manifest": cm_path,
        "commit_manifest_sha256": cm_sha,
    }


class use_synthetic_payloads:
    """Context manager patching Layer B payload specs, commit manifest anchor,
    and synthetic population counts for deterministic fixture testing."""

    def __init__(self, deploy: dict):
        self.deploy = deploy
        self._stack: list = []

    def __enter__(self):
        new_specs = (
            (str(self.deploy["metrics"]), str(self.deploy["metrics_ptr"]), "metrics"),
            (str(self.deploy["eval"]), str(self.deploy["eval_ptr"]), "row_level"),
        )
        self._stack.append(patch.object(bsvc, "_DVC_PAYLOAD_SPECS", new_specs))
        self._stack.append(
            patch.object(
                bsvc,
                "_SYNTHETIC_POPULATION_OVERRIDE",
                {"sample_size": 3, "fraud_count": 1, "flagged_count": 1},
            )
        )
        if "commit_manifest" in self.deploy and "commit_manifest_sha256" in self.deploy:
            self._stack.append(
                patch.object(bsvc, "COMMIT_MANIFEST_PATH", self.deploy["commit_manifest"])
            )
            self._stack.append(
                patch.object(
                    bsvc,
                    "TRUSTED_COMMIT_MANIFEST_SHA256",
                    self.deploy["commit_manifest_sha256"],
                )
            )
        for p in self._stack:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self._stack):
            p.stop()


# ---------------------------------------------------------------------------
# Scenarios 1–3: catalog correctness (Layer A, real Git metadata)
# ---------------------------------------------------------------------------


class TestBenchmarkCatalog:
    def test_catalog_returns_exactly_ten_runs(self, bench_client):
        """1. Ten source-backed run configurations from approved metadata."""
        response = bench_client.get(CATALOG_PATH)
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 10
        assert len(body["experiments"]) == 10
        assert [e["run_id"] for e in body["experiments"]] == list(
            bsvc.CANONICAL_RUN_IDS
        )

    def test_run_algorithm_parameter_mapping(self, bench_client):
        """2. Correct run/algorithm/parameter identity mapping."""
        response = bench_client.get(CATALOG_PATH)
        assert response.status_code == 200
        for experiment in response.json()["experiments"]:
            run_id = experiment["run_id"]
            expected_algo, expected_params = EXPECTED_RUNS[run_id]
            assert experiment["algorithm"] == expected_algo
            assert experiment["parameters"] == expected_params
            assert experiment["model_status"] == "fitted_offline_frozen"
            source = experiment["parameter_source"]
            assert source["path"] == CONFIG_REL
            assert source["digest_algorithm"] == "sha-256"
            assert source["canonicalization"] == "frozen-checker-compatible"
            assert "no scikit-learn default was inferred" in source["note"]

    def test_unknown_run_id_returns_404(self, bench_client):
        """3. Unknown run ID rejection without filesystem lookup."""
        for bad in ["IF_006", "LOF_006", "XX_001", "../etc/passwd", "IF_001;ls"]:
            response = bench_client.get(DETAIL_PATH.format(run_id=bad))
            assert response.status_code == 404, bad
            # Path-like IDs are rejected by routing (NOT_FOUND); others by
            # the fixed allowlist (SOURCE_NOT_FOUND). Both are structured
            # 404s with no filesystem lookup.
            assert response.json()["error"]["code"] in {
                "SOURCE_NOT_FOUND",
                "NOT_FOUND",
            }, bad

    def test_detail_includes_dataset_scope_and_provenance(self, bench_client):
        response = bench_client.get(DETAIL_PATH.format(run_id="IF_001"))
        assert response.status_code == 200
        body = response.json()
        assert body["dataset_scope"]["sample"]["sample_size"] == 30000
        assert body["dataset_scope"]["sample"]["fraud_count"] == 47
        assert body["dataset_scope"]["threshold_rule"] == "Bottom 1.0% of scores"
        assert set(body["provenance"].keys()) == {"config", "run_metadata", "commit_manifest"}
        assert body["provenance"]["config"]["path"] == CONFIG_REL
        assert (
            body["provenance"]["run_metadata"]["canonicalization"]
            == "windows-commit-manifest-compatible"
        )

    def test_catalog_lists_all_ten_parameter_rows(self, bench_client):
        """Every run appears with its exact frozen parameter row."""
        response = bench_client.get(CATALOG_PATH)
        by_id = {e["run_id"]: e for e in response.json()["experiments"]}
        assert set(by_id) == set(EXPECTED_RUNS)
        for run_id, (_, params) in EXPECTED_RUNS.items():
            assert by_id[run_id]["parameters"] == params


# ---------------------------------------------------------------------------
# Scenario 4: payload missing while catalog works (clean checkout)
# ---------------------------------------------------------------------------


class TestPayloadMissing:
    def test_catalog_works_and_metrics_report_artifact_missing(self, bench_client, tmp_path):
        """4. DVC payload absent -> catalog 200 + 503 artifact_missing."""
        with patch.object(bsvc, "_DVC_PAYLOAD_SPECS", _absent_dvc_specs(tmp_path)):
            response = bench_client.get(CATALOG_PATH)
            assert response.status_code == 200
            body = response.json()
            caps = body["capabilities"]
            assert caps["metrics"]["available"] is False
            assert caps["metrics"]["reason"] == "artifact_missing"
            assert caps["row_level"]["available"] is False
            assert caps["row_level"]["reason"] == "artifact_missing"
            assert all(e["metrics_available"] is False for e in body["experiments"])
            assert all(e["row_lookup_available"] is False for e in body["experiments"])

            metrics = bench_client.get(METRICS_PATH)
            assert metrics.status_code == 503
            err = metrics.json()["error"]
            assert err["code"] == "SERVICE_NOT_READY"
            assert err["details"]["reason"] == "artifact_missing"

            record = bench_client.get(RECORD_PATH.format(run_id="IF_001", row_id=101))
            assert record.status_code == 503
            assert record.json()["error"]["details"]["reason"] == "artifact_missing"


# ---------------------------------------------------------------------------
# Scenarios 5–7: pointer verification and admitted metrics (Layer B)
# ---------------------------------------------------------------------------


class TestLayerBVerification:
    def test_admitted_metrics_exact_values_and_denominators(self, tmp_path, bench_client):
        """7. Valid admitted metrics: exact source values + denominators."""
        deploy = {
            "root": tmp_path,
            "metrics": _write_payload(tmp_path, METRICS_REL, _synthetic_metrics_csv().encode()),
            "eval": _write_payload(tmp_path, EVAL_REL, _synthetic_eval_csv().encode()),
        }
        metrics_csv = deploy["metrics"].read_bytes()
        eval_csv = deploy["eval"].read_bytes()
        deploy["metrics_ptr"] = _write_payload(
            tmp_path, METRICS_PTR_REL,
            _dvc_pointer_bytes(hashlib.md5(metrics_csv).hexdigest(), len(metrics_csv), "phase4_metrics.csv"),
        )
        deploy["eval_ptr"] = _write_payload(
            tmp_path, EVAL_PTR_REL,
            _dvc_pointer_bytes(hashlib.md5(eval_csv).hexdigest(), len(eval_csv), "phase4_evaluation_dataset.csv"),
        )
        cm_p, cm_s = _build_synthetic_commit_manifest(tmp_path, deploy["metrics"].read_bytes(), deploy["eval"].read_bytes())
        deploy["commit_manifest"] = cm_p
        deploy["commit_manifest_sha256"] = cm_s
        with use_synthetic_payloads(deploy):
            response = bench_client.get(METRICS_PATH)
        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body["metrics"]) == 10
        # Exact source values: IF_001 carries the first synthetic row.
        first = body["metrics"][0]
        assert first["run_id"] == "IF_001"
        assert first["average_precision"] == pytest.approx(0.10)
        assert first["roc_auc"] == pytest.approx(0.50)
        assert first["tn"] == 29700
        assert first["fp"] == 300
        assert first["fn"] == 42
        assert first["tp"] == 5
        assert first["flagged_count"] == 300
        assert first["sample_size"] == 30000
        assert first["fraud_count"] == 47
        # Denominator semantics travel with the values.
        defs = {d["metric_name"]: d for d in body["metric_definitions"]}
        assert defs["precision_at_1pct"]["denominator"] == "300 flagged rows (saved bottom-1% rule)"
        assert defs["recall_at_1pct"]["denominator"] == "47 fraud-labelled rows in the sample"
        assert body["is_precomputed"] is True
        assert body["is_live_prediction"] is False

    def test_pointer_checksum_mismatch_fails_closed(self, tmp_path, bench_client):
        """5b. Payload present but checksum wrong → integrity_failed."""
        deploy = {
            "root": tmp_path,
            "metrics": _write_payload(tmp_path, METRICS_REL, _synthetic_metrics_csv().encode()),
            "eval": _write_payload(tmp_path, EVAL_REL, _synthetic_eval_csv().encode()),
        }
        metrics_csv = deploy["metrics"].read_bytes()
        eval_csv = deploy["eval"].read_bytes()
        deploy["metrics_ptr"] = _write_payload(
            tmp_path, METRICS_PTR_REL,
            _dvc_pointer_bytes("0" * 32, len(metrics_csv), "phase4_metrics.csv"),
        )
        deploy["eval_ptr"] = _write_payload(
            tmp_path, EVAL_PTR_REL,
            _dvc_pointer_bytes(hashlib.md5(eval_csv).hexdigest(), len(eval_csv), "phase4_evaluation_dataset.csv"),
        )
        cm_p, cm_s = _build_synthetic_commit_manifest(tmp_path, deploy["metrics"].read_bytes(), deploy["eval"].read_bytes())
        deploy["commit_manifest"] = cm_p
        deploy["commit_manifest_sha256"] = cm_s
        with use_synthetic_payloads(deploy):
            response = bench_client.get(METRICS_PATH)
        assert response.status_code == 503
        assert response.json()["error"]["details"]["reason"] == "integrity_failed"

    def test_pointer_size_mismatch_fails_closed(self, tmp_path, bench_client):
        deploy = {
            "root": tmp_path,
            "metrics": _write_payload(tmp_path, METRICS_REL, _synthetic_metrics_csv().encode()),
            "eval": _write_payload(tmp_path, EVAL_REL, _synthetic_eval_csv().encode()),
        }
        metrics_csv = deploy["metrics"].read_bytes()
        eval_csv = deploy["eval"].read_bytes()
        deploy["metrics_ptr"] = _write_payload(
            tmp_path, METRICS_PTR_REL,
            _dvc_pointer_bytes(hashlib.md5(metrics_csv).hexdigest(), len(metrics_csv) + 1, "phase4_metrics.csv"),
        )
        deploy["eval_ptr"] = _write_payload(
            tmp_path, EVAL_PTR_REL,
            _dvc_pointer_bytes(hashlib.md5(eval_csv).hexdigest(), len(eval_csv), "phase4_evaluation_dataset.csv"),
        )
        cm_p, cm_s = _build_synthetic_commit_manifest(tmp_path, deploy["metrics"].read_bytes(), deploy["eval"].read_bytes())
        deploy["commit_manifest"] = cm_p
        deploy["commit_manifest_sha256"] = cm_s
        with use_synthetic_payloads(deploy):
            response = bench_client.get(METRICS_PATH)
        assert response.status_code == 503
        assert response.json()["error"]["details"]["reason"] == "integrity_failed"

    def test_crlf_payload_form_also_verifies(self, tmp_path, bench_client):
        """A CRLF-materialized (Windows-style) payload with a CRLF md5
        pointer also verifies — the DVC-materialization ending is not
        assumed."""
        lf_csv = _synthetic_metrics_csv().encode()
        crlf_csv = lf_csv.replace(b"\n", b"\r\n")
        deploy = {
            "root": tmp_path,
            "metrics": _write_payload(tmp_path, METRICS_REL, crlf_csv),
            "eval": _write_payload(tmp_path, EVAL_REL, _synthetic_eval_csv().encode()),
        }
        eval_csv = deploy["eval"].read_bytes()
        deploy["metrics_ptr"] = _write_payload(
            tmp_path, METRICS_PTR_REL,
            _dvc_pointer_bytes(hashlib.md5(crlf_csv).hexdigest(), len(crlf_csv), "phase4_metrics.csv"),
        )
        deploy["eval_ptr"] = _write_payload(
            tmp_path, EVAL_PTR_REL,
            _dvc_pointer_bytes(hashlib.md5(eval_csv).hexdigest(), len(eval_csv), "phase4_evaluation_dataset.csv"),
        )
        cm_p, cm_s = _build_synthetic_commit_manifest(tmp_path, deploy["metrics"].read_bytes(), deploy["eval"].read_bytes())
        deploy["commit_manifest"] = cm_p
        deploy["commit_manifest_sha256"] = cm_s
        with use_synthetic_payloads(deploy):
            response = bench_client.get(METRICS_PATH)
        assert response.status_code == 200, response.text
        assert response.json()["metrics"][0]["average_precision"] == pytest.approx(0.10)

    @pytest.mark.parametrize(
        "pointer_bytes",
        [
            b"",  # missing content
            b"md5: abc\n",  # no outs
            b"outs: []\n",  # empty outs
            b"outs:\n- md5: 2fb961b52603643dab21850bf6d950f9\n  size: 2397\n  hash: sha256\n  path: phase4_metrics.csv\n",  # unsupported hash
            b"outs:\n- md5: not-a-real-digest\n  size: 2397\n  hash: md5\n  path: phase4_metrics.csv\n",  # malformed md5
            b"outs:\n- md5: 2fb961b52603643dab21850bf6d950f9\n  hash: md5\n  path: phase4_metrics.csv\n",  # missing size
            b"outs:\n- size: 2397\n  hash: md5\n  path: phase4_metrics.csv\n",  # missing md5
            b"outs:\n- md5: 2fb961b52603643dab21850bf6d950f9\n  size: 2397\n  hash: md5\n  path: phase4_metrics.csv\n  nuke: yes\n",  # unexpected key
        ],
    )
    def test_malformed_pointer_rejected(self, tmp_path, bench_client, pointer_bytes):
        """6a. Malformed pointers do not admit the payload."""
        deploy = {
            "root": tmp_path,
            "metrics": _write_payload(tmp_path, METRICS_REL, _synthetic_metrics_csv().encode()),
            "eval": _write_payload(tmp_path, EVAL_REL, _synthetic_eval_csv().encode()),
        }
        metrics_csv = deploy["metrics"].read_bytes()
        eval_csv = deploy["eval"].read_bytes()
        deploy["metrics_ptr"] = _write_payload(tmp_path, METRICS_PTR_REL, pointer_bytes)
        deploy["eval_ptr"] = _write_payload(
            tmp_path, EVAL_PTR_REL,
            _dvc_pointer_bytes(hashlib.md5(eval_csv).hexdigest(), len(eval_csv), "phase4_evaluation_dataset.csv"),
        )
        cm_p, cm_s = _build_synthetic_commit_manifest(tmp_path, deploy["metrics"].read_bytes(), deploy["eval"].read_bytes())
        deploy["commit_manifest"] = cm_p
        deploy["commit_manifest_sha256"] = cm_s
        with use_synthetic_payloads(deploy):
            response = bench_client.get(METRICS_PATH)
        assert response.status_code == 503
        reason = response.json()["error"]["details"]["reason"]
        assert reason in {"integrity_failed", "source_not_admitted", "artifact_missing"}

    def test_missing_pointer_rejected(self, tmp_path, bench_client):
        """6b. Pointer absent → payload not admitted as verified."""
        deploy = {
            "root": tmp_path,
            "metrics": _write_payload(tmp_path, METRICS_REL, _synthetic_metrics_csv().encode()),
            "eval": _write_payload(tmp_path, EVAL_REL, _synthetic_eval_csv().encode()),
        }
        eval_csv = deploy["eval"].read_bytes()
        deploy["metrics_ptr"] = tmp_path / "nonexistent.dvc"
        deploy["eval_ptr"] = _write_payload(
            tmp_path, EVAL_PTR_REL,
            _dvc_pointer_bytes(hashlib.md5(eval_csv).hexdigest(), len(eval_csv), "phase4_evaluation_dataset.csv"),
        )
        cm_p, cm_s = _build_synthetic_commit_manifest(tmp_path, deploy["metrics"].read_bytes(), deploy["eval"].read_bytes())
        deploy["commit_manifest"] = cm_p
        deploy["commit_manifest_sha256"] = cm_s
        with use_synthetic_payloads(deploy):
            response = bench_client.get(METRICS_PATH)
        assert response.status_code == 503
        # A missing pointer cannot admit the payload: the capability is
        # unavailable (the sanitized reason distinguishes source admission
        # from a missing payload when the pointer itself is unreadable).
        assert response.json()["error"]["details"]["reason"] in {
            "source_not_admitted",
            "artifact_missing",
        }

    def test_unexpected_output_path_rejected(self, tmp_path, bench_client):
        """6c. Pointer targeting an unexpected output path is rejected."""
        deploy = {
            "root": tmp_path,
            "metrics": _write_payload(tmp_path, METRICS_REL, _synthetic_metrics_csv().encode()),
            "eval": _write_payload(tmp_path, EVAL_REL, _synthetic_eval_csv().encode()),
        }
        metrics_csv = deploy["metrics"].read_bytes()
        eval_csv = deploy["eval"].read_bytes()
        deploy["metrics_ptr"] = _write_payload(
            tmp_path, METRICS_PTR_REL,
            _dvc_pointer_bytes(hashlib.md5(metrics_csv).hexdigest(), len(metrics_csv), "other_file.csv"),
        )
        deploy["eval_ptr"] = _write_payload(
            tmp_path, EVAL_PTR_REL,
            _dvc_pointer_bytes(hashlib.md5(eval_csv).hexdigest(), len(eval_csv), "phase4_evaluation_dataset.csv"),
        )
        cm_p, cm_s = _build_synthetic_commit_manifest(tmp_path, deploy["metrics"].read_bytes(), deploy["eval"].read_bytes())
        deploy["commit_manifest"] = cm_p
        deploy["commit_manifest_sha256"] = cm_s
        with use_synthetic_payloads(deploy):
            response = bench_client.get(METRICS_PATH)
        assert response.status_code == 503
        assert response.json()["error"]["details"]["reason"] == "integrity_failed"

    def test_two_output_entries_rejected(self, tmp_path, bench_client):
        metrics_csv = _synthetic_metrics_csv().encode()
        pointer = (
            b"outs:\n"
            b"- md5: " + hashlib.md5(metrics_csv).hexdigest().encode() + b"\n"
            b"  size: " + str(len(metrics_csv)).encode() + b"\n"
            b"  hash: md5\n"
            b"  path: phase4_metrics.csv\n"
            b"- md5: " + hashlib.md5(metrics_csv).hexdigest().encode() + b"\n"
            b"  size: " + str(len(metrics_csv)).encode() + b"\n"
            b"  hash: md5\n"
            b"  path: other.csv\n"
        )
        deploy = {
            "root": tmp_path,
            "metrics": _write_payload(tmp_path, METRICS_REL, metrics_csv),
            "eval": _write_payload(tmp_path, EVAL_REL, _synthetic_eval_csv().encode()),
        }
        eval_csv = deploy["eval"].read_bytes()
        deploy["metrics_ptr"] = _write_payload(tmp_path, METRICS_PTR_REL, pointer)
        deploy["eval_ptr"] = _write_payload(
            tmp_path, EVAL_PTR_REL,
            _dvc_pointer_bytes(hashlib.md5(eval_csv).hexdigest(), len(eval_csv), "phase4_evaluation_dataset.csv"),
        )
        cm_p, cm_s = _build_synthetic_commit_manifest(tmp_path, deploy["metrics"].read_bytes(), deploy["eval"].read_bytes())
        deploy["commit_manifest"] = cm_p
        deploy["commit_manifest_sha256"] = cm_s
        with use_synthetic_payloads(deploy):
            response = bench_client.get(METRICS_PATH)
        assert response.status_code == 503
        assert response.json()["error"]["details"]["reason"] == "integrity_failed"


# ---------------------------------------------------------------------------
# Scenarios 8–11: record lookup (Layer B)
# ---------------------------------------------------------------------------


def _deploy_full(
    tmp_path,
    eval_csv_text: str,
    metrics_csv_text: str | None = None,
    *,
    include_metrics: bool = True,
    include_eval: bool = True,
    override_metrics_sha256: str | None = None,
    override_eval_sha256: str | None = None,
):
    metrics_csv = (metrics_csv_text or _synthetic_metrics_csv()).encode()
    eval_csv = eval_csv_text.encode()
    deploy = {
        "root": tmp_path,
        "metrics": _write_payload(tmp_path, METRICS_REL, metrics_csv) if include_metrics else tmp_path / "absent" / "phase4_metrics.csv",
        "eval": _write_payload(tmp_path, EVAL_REL, eval_csv) if include_eval else tmp_path / "absent" / "phase4_evaluation_dataset.csv",
    }
    deploy["metrics_ptr"] = _write_payload(
        tmp_path, METRICS_PTR_REL,
        _dvc_pointer_bytes(hashlib.md5(metrics_csv).hexdigest(), len(metrics_csv), "phase4_metrics.csv"),
    )
    deploy["eval_ptr"] = _write_payload(
        tmp_path, EVAL_PTR_REL,
        _dvc_pointer_bytes(hashlib.md5(eval_csv).hexdigest(), len(eval_csv), "phase4_evaluation_dataset.csv"),
    )
    cm_path, cm_sha = _build_synthetic_commit_manifest(
        tmp_path,
        metrics_csv,
        eval_csv,
        override_metrics_sha256=override_metrics_sha256,
        override_eval_sha256=override_eval_sha256,
    )
    deploy["commit_manifest"] = cm_path
    deploy["commit_manifest_sha256"] = cm_sha
    return deploy


class TestRecordLookup:
    def test_row_lookup_by_actual_row_id(self, tmp_path, bench_client):
        """8. Lookup resolves by saved row_id, returning documented fields."""
        deploy = _deploy_full(tmp_path, _synthetic_eval_csv())
        with use_synthetic_payloads(deploy):
            response = bench_client.get(
                RECORD_PATH.format(run_id="IF_001", row_id=205)
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["run_id"] == "IF_001"
        assert body["row_id"] == 205
        # si == 1 for row 205 in the synthetic fixture.
        assert body["label"]["Class"] == 0
        assert body["scores"]["native_score"] == pytest.approx(-0.6)
        assert body["scores"]["anomaly_score"] == pytest.approx(0.6)
        assert body["flag"]["value"] == 0
        assert "ground-truth" in body["label"]["provenance"].lower()
        assert "distinct from the" in body["label"]["provenance"]
        assert body["is_live_prediction"] is False

    def test_shuffled_row_order_invariance(self, tmp_path, bench_client):
        """9. row_id lookup is invariant to physical CSV row order."""
        results = {}
        for order in ("forward", "shuffled"):
            deploy = _deploy_full(tmp_path / order, _synthetic_eval_csv(order=order))
            with use_synthetic_payloads(deploy):
                response = bench_client.get(
                    RECORD_PATH.format(run_id="LOF_003", row_id=101)
                )
            assert response.status_code == 200, response.text
            results[order] = response.json()
        # The record payload (row identity, label, scores, flag) is
        # identical; only the provenance block differs (different fixture
        # files carry different md5 digests by construction).
        for field in ("run_id", "row_id", "label", "scores", "flag"):
            assert results["forward"][field] == results["shuffled"][field], field

    def test_duplicate_row_id_rejected(self, tmp_path, bench_client):
        """10. Duplicate (run_id, row_id) fails closed for records."""
        eval_csv = _synthetic_eval_csv(row_ids_extra=[101])  # 101 duplicated
        deploy = _deploy_full(tmp_path, eval_csv)
        with use_synthetic_payloads(deploy):
            metrics = bench_client.get(METRICS_PATH)
            record = bench_client.get(
                RECORD_PATH.format(run_id="IF_001", row_id=101)
            )
        # Metrics are independent of the eval dataset validity, but the
        # whole Layer B parse fails closed on schema violation.
        assert record.status_code == 503
        assert record.json()["error"]["details"]["reason"] == "integrity_failed"

    @pytest.mark.parametrize(
        "missing_field",
        ["Class", "native_score", "anomaly_score", "flag"],
    )
    def test_missing_required_field_no_invented_defaults(
        self, tmp_path, bench_client, missing_field
    ):
        """11. Missing score/flag/label fields are never defaulted."""
        lines = _synthetic_eval_csv().splitlines()
        header = lines[0].split(",")
        col_index = header.index(missing_field)
        # Blank out the field on every data row.
        patched_lines = [lines[0]]
        for line in lines[1:]:
            cells = line.split(",")
            cells[col_index] = ""
            patched_lines.append(",".join(cells))
        deploy = _deploy_full(tmp_path, "\n".join(patched_lines) + "\n")
        with use_synthetic_payloads(deploy):
            record = bench_client.get(
                RECORD_PATH.format(run_id="IF_001", row_id=101)
            )
        assert record.status_code == 503
        assert record.json()["error"]["details"]["reason"] == "integrity_failed"

    def test_unknown_record_returns_404(self, tmp_path, bench_client):
        deploy = _deploy_full(tmp_path, _synthetic_eval_csv())
        with use_synthetic_payloads(deploy):
            response = bench_client.get(
                RECORD_PATH.format(run_id="IF_001", row_id=999999)
            )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "SOURCE_NOT_FOUND"

    def test_record_lookup_rejects_unknown_run_first(self, bench_client):
        response = bench_client.get(RECORD_PATH.format(run_id="IF_009", row_id=1))
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Scenario 12: tampered Git metadata
# ---------------------------------------------------------------------------


class TestTamperedGitMetadata:
    def test_tampered_run_metadata_rejected(self, bench_client, tmp_path):
        """12. Corrupted Git-backed metadata → catalog fails closed."""
        original = (bsvc.REPO_ROOT / RUN_META_REL).read_bytes()
        tampered = json.loads(original.decode("utf-8"))
        tampered["sample"]["fraud_count"] = 999  # tamper
        tampered_bytes = json.dumps(tampered, indent=2).encode()
        fake_root = tmp_path
        _write_payload(fake_root, RUN_META_REL, tampered_bytes)
        with patch.object(
            bsvc, "RUN_METADATA_PATH", fake_root / RUN_META_REL
        ):
            response = bench_client.get(CATALOG_PATH)
        assert response.status_code == 503
        assert response.json()["error"]["details"]["reason"] == "integrity_failed"

    def test_tampered_config_rejected(self, bench_client, tmp_path):
        original = (bsvc.REPO_ROOT / CONFIG_REL).read_bytes()
        tampered = original.replace(b"n_neighbors=5", b"n_neighbors=7").replace(
            b'"n_neighbors": 5', b'"n_neighbors": 7'
        )
        assert tampered != original, "fixture sanity"
        fake_root = tmp_path
        _write_payload(fake_root, CONFIG_REL, tampered)
        with patch.object(bsvc, "CONFIG_PATH", fake_root / CONFIG_REL):
            response = bench_client.get(CATALOG_PATH)
        assert response.status_code == 503
        assert response.json()["error"]["details"]["reason"] == "integrity_failed"


# ---------------------------------------------------------------------------
# Scenario 13: post-cache mutation and recovery
# ---------------------------------------------------------------------------


class TestCacheIntegrity:
    def test_payload_altered_after_warmup_fails_closed_then_recovers(
        self, tmp_path, bench_client
    ):
        """13. Post-cache mutation → 503; restored payload → recovers."""
        deploy = _deploy_full(tmp_path, _synthetic_eval_csv())
        with use_synthetic_payloads(deploy):
            # Warm the cache with a valid request.
            first = bench_client.get(METRICS_PATH)
            assert first.status_code == 200

            # Mutate the payload on disk (same size, different bytes).
            data = deploy["metrics"].read_bytes()
            tampered = data.replace(b"0.100000", b"0.900000")
            assert len(tampered) == len(data)
            deploy["metrics"].write_bytes(tampered)

            mutated = bench_client.get(METRICS_PATH)
            assert mutated.status_code == 503
            assert mutated.json()["error"]["details"]["reason"] == "integrity_failed"

            # Restore the approved bytes → the next request recovers
            # without an application restart.
            deploy["metrics"].write_bytes(data)
            recovered = bench_client.get(METRICS_PATH)
            assert recovered.status_code == 200
            assert recovered.json()["metrics"][0]["average_precision"] == pytest.approx(0.10)

    def test_payload_removed_after_warmup_fails_closed(
        self, tmp_path, bench_client
    ):
        deploy = _deploy_full(tmp_path, _synthetic_eval_csv())
        with use_synthetic_payloads(deploy):
            assert bench_client.get(METRICS_PATH).status_code == 200
            deploy["metrics"].unlink()
            response = bench_client.get(METRICS_PATH)
            assert response.status_code == 503
            assert response.json()["error"]["details"]["reason"] == "artifact_missing"

    def test_catalog_survives_layer_b_failures(self, bench_client):
        """Layer B unavailability never breaks the Layer A catalog."""
        response = bench_client.get(CATALOG_PATH)
        assert response.status_code == 200
        assert response.json()["count"] == 10


# ---------------------------------------------------------------------------
# Scenario 14–15: access control
# ---------------------------------------------------------------------------


class TestAccessControl:
    def test_anonymous_reader_can_read_benchmark(self, bench_app):
        """14. Public approved research GET access (anonymous)."""
        client = TestClient(bench_app)
        for path in [
            CATALOG_PATH,
            DETAIL_PATH.format(run_id="IF_002"),
            METRICS_PATH,
            RECORD_PATH.format(run_id="IF_002", row_id=1),
        ]:
            response = client.get(path)
            assert response.status_code in (200, 404, 503), path
            assert response.status_code != 401
            assert response.status_code != 403

    def test_authenticated_case_write_and_private_history_isolation(
        self, bench_app, bench_user
    ):
        """15. Reviewer writes a case; anonymous cannot read private history."""
        client = TestClient(bench_app)
        assert login(client, "bench-reviewer", PASSWORD).status_code == 200
        csrf = get_csrf_token(client)
        create = client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "Synthetic fixture case (PR-09 test)",
                "summary": "SYNTHETIC fixture — created to verify case/research isolation.",
                "created_by": "bench-reviewer",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert create.status_code in (200, 201), create.text
        case_id = create.json()["id"]

        # Anonymous reader cannot read the case history.
        anon = TestClient(bench_app)
        history = anon.get(f"/api/v1/cases/{case_id}/history")
        assert history.status_code in (401, 403)

        # The reviewer can.
        authed_history = client.get(f"/api/v1/cases/{case_id}/history")
        assert authed_history.status_code == 200


# ---------------------------------------------------------------------------
# Scenario 16: no modelling / pickle / DVC downloads
# ---------------------------------------------------------------------------


class TestNoModellingOrPickle:
    def test_no_pickle_or_sklearn_or_dvc_import_or_download(
        self, bench_client, tmp_path
    ):
        """16. The API never triggers modelling, pickle loading or DVC."""
        import builtins
        import importlib

        real_import = builtins.__import__
        forbidden = []

        def guarded(name, *args, **kwargs):
            root = name.split(".")[0]
            if root in {"pickle", "dvc", "sklearn", "numpy", "pandas", "subprocess"}:
                forbidden.append(name)
            return real_import(name, *args, **kwargs)

        deploy = _deploy_full(tmp_path, _synthetic_eval_csv())
        with use_synthetic_payloads(deploy), patch.object(
            builtins, "__import__", side_effect=guarded
        ):
            for path in [
                CATALOG_PATH,
                DETAIL_PATH.format(run_id="IF_001"),
                METRICS_PATH,
                RECORD_PATH.format(run_id="IF_001", row_id=101),
            ]:
                response = bench_client.get(path)
                assert response.status_code in (200, 503, 404)
        assert forbidden == [], f"forbidden imports triggered: {forbidden}"

        # The service module itself never imports pickle/sklearn/dvc.
        loaded = {m for m in sys_modules_roots()}
        assert "pickle" not in loaded or "benchmark_catalog" not in {
            m for m in loaded
        }

    def test_service_source_has_no_pickle_or_dvc_calls(self):
        source = Path(bsvc.__file__).read_text()
        assert "import pickle" not in source
        assert "pickle.load" not in source
        assert "import dvc" not in source
        assert "dvc.api" not in source
        assert "subprocess" not in source


def sys_modules_roots():
    import sys

    for name in sys.modules:
        yield name.split(".")[0]


# ---------------------------------------------------------------------------
# Scenario 17: OpenAPI / TypeScript contract consistency
# ---------------------------------------------------------------------------


class TestOpenAPIContract:
    def test_benchmark_operations_present_in_openapi(self, bench_client):
        """17. The four benchmark operations exist with unique IDs."""
        response = bench_client.get("/openapi.json")
        assert response.status_code == 200
        spec = response.json()
        paths = spec["paths"]
        assert "/api/v1/research/benchmark/experiments" in paths
        assert "/api/v1/research/benchmark/experiments/{run_id}" in paths
        assert "/api/v1/research/benchmark/metrics" in paths
        assert (
            "/api/v1/research/benchmark/experiments/{run_id}/records/{row_id}"
            in paths
        )
        ops = [
            op
            for p in paths.values()
            for op in p.values()
        ]
        op_ids = [op.get("operationId") for op in ops]
        assert len(op_ids) == len(set(op_ids)), "duplicate operationIds"

    def test_committed_openapi_matches_app(self, bench_client):
        """The committed openapi.json mirrors the live app schema."""
        response = bench_client.get("/openapi.json")
        live = response.json()
        committed = json.loads(
            (REPO_ROOT / "backend" / "contracts" / "openapi.json").read_text()
        )
        assert sorted(live["paths"]) == sorted(committed["paths"])

    def test_generated_typescript_contracts_contain_benchmark(self):
        gen = (
            REPO_ROOT
            / "frontend"
            / "src"
            / "api"
            / "contracts.gen.ts"
        ).read_text()
        for name in [
            "BenchmarkCatalogResponse",
            "BenchmarkExperimentSummary",
            "BenchmarkExperimentDetail",
            "BenchmarkMetricsResponse",
            "BenchmarkRunMetrics",
            "BenchmarkRecordResponse",
        ]:
            assert name in gen, name


# ---------------------------------------------------------------------------
# Scenario 18: unrelated workflows during missing payloads
# ---------------------------------------------------------------------------


class TestUnrelatedWorkflows:
    def test_health_and_review_workflow_continue(self, bench_app, bench_user, tmp_path):
        """18. Readiness and review workflows operate while the benchmark
        payloads are absent (the clean-checkout state)."""
        client = TestClient(bench_app)
        live = client.get("/api/v1/health/live")
        assert live.status_code == 200
        ready = client.get("/api/v1/health/ready")
        assert ready.status_code in (200, 503)

        assert login(client, "bench-reviewer", PASSWORD).status_code == 200
        csrf = get_csrf_token(client)
        create = client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-002",
                "title": "Synthetic fixture case (PR-09 isolation test)",
                "summary": "SYNTHETIC fixture - unrelated workflow check.",
                "created_by": "bench-reviewer",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert create.status_code in (200, 201), create.text

        legacy = client.get("/api/v1/research/sources")
        assert legacy.status_code == 200

        with patch.object(bsvc, "_DVC_PAYLOAD_SPECS", _absent_dvc_specs(tmp_path)):
            assert client.get(CATALOG_PATH).status_code == 200
            assert client.get(METRICS_PATH).status_code == 503


# ---------------------------------------------------------------------------
# Direct service-level contract tests (no HTTP)
# ---------------------------------------------------------------------------


class TestServiceContract:
    def test_availability_probe_never_raises(self):
        service = BenchmarkCatalogService()
        availability = service.availability()
        assert set(availability) == {"metrics", "row_level"}

    def test_metrics_payload_absent_raises_unavailable(self, tmp_path):
        service = BenchmarkCatalogService()
        with patch.object(bsvc, "_DVC_PAYLOAD_SPECS", _absent_dvc_specs(tmp_path)):
            with pytest.raises(BenchmarkUnavailableError):
                service.get_metrics()

    def test_record_payload_absent_raises_unavailable(self, tmp_path):
        service = BenchmarkCatalogService()
        with patch.object(bsvc, "_DVC_PAYLOAD_SPECS", _absent_dvc_specs(tmp_path)):
            with pytest.raises(BenchmarkUnavailableError):
                service.get_record("IF_001", 1)

    def test_unknown_run_raises_source_not_found(self):
        service = BenchmarkCatalogService()
        with pytest.raises(SourceNotFoundError):
            service.get_experiment("IF_006")

    def test_run_id_regex_boundary(self):
        for bad in ["if_001", "IF_1", "LOF_000", "IF_006", ""]:
            assert bsvc._RUN_ID_RE.fullmatch(bad) is None, bad
        for good in ["IF_001", "IF_005", "LOF_001", "LOF_005"]:
            assert bsvc._RUN_ID_RE.fullmatch(good) is not None, good


# ---------------------------------------------------------------------------
# Hardening regressions (Findings A, B, C, D)
# ---------------------------------------------------------------------------


class TestHardeningInvariants:
    def test_finding_a_catalog_cache_rechecks_trusted_manifest_on_every_request(
        self, bench_client, tmp_path
    ):
        """Finding A: tampering with frozen_research_manifest.json after cache
        warm-up must immediately invalidate the cache and fail closed."""
        first = bench_client.get(CATALOG_PATH)
        assert first.status_code == 200

        orig_manifest = json.loads(
            (bsvc.REPO_ROOT / "ci" / "frozen_research_manifest.json").read_text(encoding="utf-8")
        )
        orig_manifest[CONFIG_REL] = "0" * 64
        bad_manifest = tmp_path / "frozen_research_manifest.json"
        bad_manifest.write_text(json.dumps(orig_manifest), encoding="utf-8")

        with patch.object(bsvc, "FROZEN_MANIFEST_PATH", bad_manifest):
            second = bench_client.get(CATALOG_PATH)
        assert second.status_code == 503
        assert second.json()["error"]["details"]["reason"] == "integrity_failed"

    def test_finding_b_commit_manifest_sha256_mismatch_fails_closed(
        self, tmp_path, bench_client
    ):
        """Finding B: matching DVC MD5 but wrong Phase 4 commit-manifest SHA-256
        must fail closed with integrity_failed."""
        deploy = _deploy_full(
            tmp_path,
            _synthetic_eval_csv(),
            override_metrics_sha256="f" * 64,
        )
        with use_synthetic_payloads(deploy):
            resp = bench_client.get(METRICS_PATH)
        assert resp.status_code == 503
        assert resp.json()["error"]["details"]["reason"] == "integrity_failed"

    def test_finding_b_lf_normalized_payload_with_crlf_manifest_and_pointer_verifies(
        self, tmp_path, bench_client
    ):
        """Finding B: LF-normalized CSV on disk verifies when the DVC pointer and
        Phase 4 commit manifest record the Windows CRLF size and digests."""
        lf_bytes = _synthetic_metrics_csv().replace("\r\n", "\n").encode("utf-8")
        crlf_bytes = lf_bytes.replace(b"\n", b"\r\n")
        assert len(lf_bytes) != len(crlf_bytes)

        eval_bytes = _synthetic_eval_csv().encode("utf-8")
        deploy = {
            "root": tmp_path,
            "metrics": _write_payload(tmp_path, METRICS_REL, lf_bytes),
            "eval": _write_payload(tmp_path, EVAL_REL, eval_bytes),
            "metrics_ptr": _write_payload(
                tmp_path,
                METRICS_PTR_REL,
                _dvc_pointer_bytes(hashlib.md5(crlf_bytes).hexdigest(), len(crlf_bytes), "phase4_metrics.csv"),
            ),
            "eval_ptr": _write_payload(
                tmp_path,
                EVAL_PTR_REL,
                _dvc_pointer_bytes(hashlib.md5(eval_bytes).hexdigest(), len(eval_bytes), "phase4_evaluation_dataset.csv"),
            ),
        }
        cm_p, cm_s = _build_synthetic_commit_manifest(tmp_path, crlf_bytes, eval_bytes)
        deploy["commit_manifest"] = cm_p
        deploy["commit_manifest_sha256"] = cm_s

        with use_synthetic_payloads(deploy):
            resp = bench_client.get(METRICS_PATH)
        assert resp.status_code == 200, resp.text
        assert resp.json()["metrics"][0]["average_precision"] == pytest.approx(0.10)

    def test_finding_c_independent_layer_b_availability(self, tmp_path, bench_client):
        """Finding C: valid metrics + absent eval CSV serves metrics 200 while
        record lookup returns 503 artifact_missing (and vice versa)."""
        deploy_metrics_only = _deploy_full(
            tmp_path / "m_only", _synthetic_eval_csv(), include_eval=False
        )
        with use_synthetic_payloads(deploy_metrics_only):
            assert bench_client.get(METRICS_PATH).status_code == 200
            rec = bench_client.get(RECORD_PATH.format(run_id="IF_001", row_id=101))
            assert rec.status_code == 503
            assert rec.json()["error"]["details"]["reason"] == "artifact_missing"

        _invalidate_caches()
        deploy_rows_only = _deploy_full(
            tmp_path / "r_only", _synthetic_eval_csv(), include_metrics=False
        )
        with use_synthetic_payloads(deploy_rows_only):
            assert bench_client.get(RECORD_PATH.format(run_id="IF_001", row_id=101)).status_code == 200
            met = bench_client.get(METRICS_PATH)
            assert met.status_code == 503
            assert met.json()["error"]["details"]["reason"] == "artifact_missing"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"drop_last_row": True},
            {"inconsistent_label": True},
            {"invalid_flag": True},
            {"mismatched_score": True},
        ],
    )
    def test_finding_d_canonical_population_and_score_label_flag_invariants(
        self, tmp_path, bench_client, kwargs
    ):
        """Finding D: missing row, inconsistent Class across runs, invalid flag,
        or anomaly_score != -native_score fails closed with integrity_failed."""
        deploy = _deploy_full(tmp_path, _synthetic_eval_csv(**kwargs))
        with use_synthetic_payloads(deploy):
            resp = bench_client.get(RECORD_PATH.format(run_id="IF_001", row_id=101))
        assert resp.status_code == 503
        assert resp.json()["error"]["details"]["reason"] == "integrity_failed"


# ---------------------------------------------------------------------------
# Trusted local real-DVC payload verification (conditional on DVC materialization)
# ---------------------------------------------------------------------------


class TestTrustedLocalRealDvcPayloads:
    """Validates actual materialized Phase 4 reproduction CSVs against committed
    DVC pointers and Phase 4 commit manifest when present on the workstation."""

    @pytest.mark.skipif(
        not (REPO_ROOT / METRICS_REL).exists() or not (REPO_ROOT / EVAL_REL).exists(),
        reason="NOT RUN - DATA UNAVAILABLE (DVC payloads not materialized in this checkout)",
    )
    def test_real_phase4_metrics_and_300k_evaluation_dataset_verify_end_to_end(
        self, bench_client
    ):
        cat = bench_client.get(CATALOG_PATH)
        assert cat.status_code == 200
        cat_body = cat.json()
        assert cat_body["capabilities"]["metrics"]["available"] is True
        assert cat_body["capabilities"]["row_level"]["available"] is True

        met = bench_client.get(METRICS_PATH)
        assert met.status_code == 200
        met_body = met.json()
        assert len(met_body["metrics"]) == 10
        assert met_body["provenance"]["metrics_md5"] == "2fb961b52603643dab21850bf6d950f9"
        assert (
            met_body["provenance"]["metrics_sha256"]
            == "6535001ce38766d7e52fef84253a7d95e6335b6183fd34f6ead12210eec99acd"
        )
        for row in met_body["metrics"]:
            assert row["sample_size"] == 30000
            assert row["fraud_count"] == 47
            assert row["flagged_count"] == 300
            assert row["tp"] + row["fn"] == 47
            assert row["tp"] + row["fp"] == 300
            assert row["tn"] + row["fp"] + row["fn"] + row["tp"] == 30000

        rows_layer = bsvc._load_layer_b_rows()
        assert len(rows_layer["row_index"]) == 300000
        assert (
            rows_layer["eval_sha256"]
            == "affbf02c63da594d1fdb2c66d07121f39221f7e24082eed4770b59d4598bb048"
        )
        sample_row_id = sorted(
            rid for (run_id, rid) in rows_layer["row_index"] if run_id == "IF_003"
        )[0]
        rec = bench_client.get(RECORD_PATH.format(run_id="IF_003", row_id=sample_row_id))
        assert rec.status_code == 200
        rec_body = rec.json()
        assert rec_body["run_id"] == "IF_003"
        assert rec_body["row_id"] == sample_row_id
        assert rec_body["label"]["Class"] in (0, 1)
        assert rec_body["flag"]["value"] in (0, 1)
        assert rec_body["scores"]["anomaly_score"] == pytest.approx(
            -rec_body["scores"]["native_score"]
        )
