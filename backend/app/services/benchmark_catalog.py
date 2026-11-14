"""Read-only canonical benchmark adapter (PR-09).

Serves the authentic ten canonical Stream A Isolation Forest / Local Outlier
Factor experiments through two distinct evidence layers:

**Layer A ? Git-verified benchmark catalog.**
Consumes only Git-tracked, frozen, manifest-verified files
(``src/mplad/common/config.py`` and the Phase 4 reproduction metadata under
``results/stream a/phase 4/reproduction/``). Never executes a frozen module:
configuration grids are extracted with AST parsing; the Phase 4 metadata is
parsed as JSON. Every consumed file is verified against a trusted digest
chain (``ci/frozen_research_manifest.json`` for ``config.py``; the pinned
Phase 4 commit manifest trust anchor for the reproduction metadata) on every
request before any cache hit is accepted.

**Layer B ? independent optional DVC-backed benchmark data.**
The authoritative Phase 4 metrics CSV (``phase4_metrics.csv``) and long-form
evaluation dataset (``phase4_evaluation_dataset.csv``) have independent
loading paths and caches. Each payload is resolved exclusively from a fixed
server-side allowlist, verified against both its Git-tracked ``.dvc`` pointer
(MD5 + size) and the trusted Phase 4 commit manifest (SHA-256 + size) using a
representation-consistent byte policy (raw bytes or CRLF-reconstructed text
bytes), and validated against canonical schema and population invariants.
Pickle payloads are never deserialized in the request process.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import math
import re
from pathlib import Path
from typing import Any

from app.services.source_registry import SourceNotFoundError

# ---------------------------------------------------------------------------
# Fixed paths and identities (server-side allowlist)
# ---------------------------------------------------------------------------

REPO_ROOT: Path = Path(__file__).resolve().parents[3]

CONFIG_REL_PATH: str = "src/mplad/common/config.py"
FROZEN_MANIFEST_REL_PATH: str = "ci/frozen_research_manifest.json"

PHASE4_REPRO_REL_DIR: str = "results/stream a/phase 4/reproduction"
RUN_METADATA_REL_PATH: str = f"{PHASE4_REPRO_REL_DIR}/phase4_run_metadata.json"
COMMIT_MANIFEST_REL_PATH: str = f"{PHASE4_REPRO_REL_DIR}/phase4_commit_manifest.json"

METRICS_REL_PATH: str = f"{PHASE4_REPRO_REL_DIR}/phase4_metrics.csv"
METRICS_POINTER_REL_PATH: str = f"{METRICS_REL_PATH}.dvc"
EVAL_REL_PATH: str = f"{PHASE4_REPRO_REL_DIR}/phase4_evaluation_dataset.csv"
EVAL_POINTER_REL_PATH: str = f"{EVAL_REL_PATH}.dvc"

CONFIG_PATH: Path = REPO_ROOT / CONFIG_REL_PATH
FROZEN_MANIFEST_PATH: Path = REPO_ROOT / FROZEN_MANIFEST_REL_PATH
RUN_METADATA_PATH: Path = REPO_ROOT / RUN_METADATA_REL_PATH
COMMIT_MANIFEST_PATH: Path = REPO_ROOT / COMMIT_MANIFEST_REL_PATH

#: Code-pinned SHA-256 of the canonical Windows-CRLF Phase 4 commit manifest
#: (prevents pure self-signing if phase4_commit_manifest.json is tampered with).
TRUSTED_COMMIT_MANIFEST_SHA256: str = "e6d8d9306310af578b90011b407fd953312aeb67c61b5c5f90c41c8faa6d358d"

#: Digest algorithm and canonicalization labels recorded in provenance.
DIGEST_ALGORITHM: str = "sha-256"
FROZEN_CHECKER_CANONICALIZATION: str = "frozen-checker-compatible"
WINDOWS_MANIFEST_CANONICALIZATION: str = "windows-commit-manifest-compatible"

#: Catalog source id (Layer A) and dataset identity.
BENCHMARK_SOURCE_ID: str = "canonical-if-lof-benchmark"
DATASET_ID: str = "ULB credit-card transactions (Stream A, FS-A baseline)"

#: Layer B payload specs: (payload_rel_path, dvc_pointer_rel_path, role).
_DVC_PAYLOAD_SPECS: tuple[tuple[str, str, str], ...] = (
    (METRICS_REL_PATH, METRICS_POINTER_REL_PATH, "metrics"),
    (EVAL_REL_PATH, EVAL_POINTER_REL_PATH, "row_level"),
)

#: Optional test-only override for row-level population counts when exercising
#: small synthetic fixtures; ``None`` enforces the canonical 30,000-row contract.
_SYNTHETIC_POPULATION_OVERRIDE: dict[str, int] | None = None

METRICS_COLUMNS: tuple[str, ...] = (
    "run_id",
    "model",
    "n_estimators",
    "max_samples",
    "random_state",
    "n_neighbors",
    "metric",
    "runtime_seconds",
    "threshold_rule",
    "average_precision",
    "roc_auc",
    "precision_at_1pct",
    "recall_at_1pct",
    "f1_at_1pct",
    "tn",
    "fp",
    "fn",
    "tp",
    "sample_size",
    "fraud_count",
    "fraud_prevalence",
    "flagged_count",
    "flagged_proportion",
)

EVALUATION_DATASET_COLUMNS: tuple[str, ...] = (
    "run_id",
    "row_id",
    "Class",
    "native_score",
    "anomaly_score",
    "flag",
)

CANONICAL_RUN_IDS: tuple[str, ...] = (
    "IF_001",
    "IF_002",
    "IF_003",
    "IF_004",
    "IF_005",
    "LOF_001",
    "LOF_002",
    "LOF_003",
    "LOF_004",
    "LOF_005",
)

_ALGO_BY_PREFIX: dict[str, str] = {"IF": "IsolationForest", "LOF": "LOF"}

_METRIC_DEFINITIONS: tuple[dict[str, str], ...] = (
    {
        "metric_name": "average_precision",
        "definition": (
            "sklearn average_precision_score(Class, anomaly_score) on the "
            "30,000-row sample; higher anomaly_score = more anomalous."
        ),
        "denominator": "30,000-row benchmark sample",
    },
    {
        "metric_name": "roc_auc",
        "definition": (
            "sklearn roc_auc_score(Class, anomaly_score) on the 30,000-row "
            "sample; higher anomaly_score = more anomalous."
        ),
        "denominator": "30,000-row benchmark sample",
    },
    {
        "metric_name": "precision_at_1pct",
        "definition": (
            "Precision of the saved Phase 3 bottom-1% flags (never "
            "recomputed); positives / 300 flagged."
        ),
        "denominator": "300 flagged rows (saved bottom-1% rule)",
    },
    {
        "metric_name": "recall_at_1pct",
        "definition": (
            "Recall of the saved Phase 3 bottom-1% flags against the 47 "
            "sample fraud labels (never recomputed)."
        ),
        "denominator": "47 fraud-labelled rows in the sample",
    },
    {
        "metric_name": "f1_at_1pct",
        "definition": (
            "F1 of the saved Phase 3 bottom-1% flags (never recomputed)."
        ),
        "denominator": "harmonic mean of the saved-flag precision and recall",
    },
    {
        "metric_name": "tn",
        "definition": "True negatives of the saved flags vs Class.",
        "denominator": "30,000-row benchmark sample",
    },
    {
        "metric_name": "fp",
        "definition": "False positives of the saved flags vs Class.",
        "denominator": "300 flagged rows (saved bottom-1% rule)",
    },
    {
        "metric_name": "fn",
        "definition": "False negatives of the saved flags vs Class.",
        "denominator": "47 fraud-labelled rows in the sample",
    },
    {
        "metric_name": "tp",
        "definition": "True positives of the saved flags vs Class.",
        "denominator": "47 fraud-labelled rows in the sample",
    },
    {
        "metric_name": "sample_size",
        "definition": "Rows in the evaluation sample.",
        "denominator": "count",
    },
    {
        "metric_name": "fraud_count",
        "definition": "Ground-truth positive labels in the sample.",
        "denominator": "count",
    },
    {
        "metric_name": "fraud_prevalence",
        "definition": "fraud_count / sample_size.",
        "denominator": "30,000-row benchmark sample",
    },
    {
        "metric_name": "flagged_count",
        "definition": "Saved Phase 3 flags equal to 1 (bottom-1% rule).",
        "denominator": "count",
    },
    {
        "metric_name": "flagged_proportion",
        "definition": "flagged_count / sample_size.",
        "denominator": "30,000-row benchmark sample",
    },
)

LIMITATIONS: tuple[str, ...] = (
    "Anomaly flags are statistical outputs of unsupervised detectors; they "
    "never imply fraud, misconduct or any legal finding.",
    "Metrics were computed on a 30,000-row ULB benchmark sample (47 fraud "
    "labels), not on the full 284,807-row population; the full-data "
    "companion results are a separate, non-comparable evidence set and are "
    "not served here.",
    "The bottom-1% flags are saved Phase 3 outputs; Phase 4 never "
    "recomputed, re-optimised or re-thresholded them.",
    "The benchmark domain is ULB credit-card transactions; results must not "
    "be assumed to transfer to PMGSY or MPLADS data.",
    "IF_002/IF_003 (parameter sensitivity) and IF_004/IF_005 (seed "
    "stability) are within-method variations, not independent evidence; "
    "no run was selected as confirmatory.",
    "All values are precomputed and frozen; the API never fits a model, "
    "recomputes a threshold or produces a live prediction.",
)

_DVC_OUT_REQUIRED_KEYS: frozenset[str] = frozenset({"md5", "size", "hash", "path"})
_DVC_OUT_ALLOWED_KEYS: frozenset[str] = frozenset(
    {"md5", "size", "hash", "path", "etag"}
)

_RUN_ID_RE = re.compile(r"^(IF|LOF)_(00[1-5])$")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class BenchmarkIntegrityError(Exception):
    """A consumed benchmark artifact failed integrity verification."""


class BenchmarkUnavailableError(Exception):
    """A required benchmark artifact is missing (e.g. DVC payload absent)."""


# ---------------------------------------------------------------------------
# Digest helpers
# ---------------------------------------------------------------------------


def _canonicalize_frozen_checker(data: bytes) -> bytes:
    """The frozen integrity checker's rule: CRLF->LF for text (no NUL) bytes."""
    if b"\x00" not in data:
        return data.replace(b"\r\n", b"\n")
    return data


def _reconstruct_crlf(data: bytes) -> bytes:
    """Reconstruct the Windows-produced CRLF form from LF-normalized bytes."""
    if b"\x00" in data or b"\r\n" in data:
        return data
    return data.replace(b"\n", b"\r\n")


def _sha256_frozen_checker(data: bytes) -> str:
    return hashlib.sha256(_canonicalize_frozen_checker(data)).hexdigest()


def _sha256_windows_manifest(data: bytes) -> str:
    return hashlib.sha256(_reconstruct_crlf(data)).hexdigest()


def _sha256_raw(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _md5_raw(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


# ---------------------------------------------------------------------------
# Layer A: Git-verified catalog + trust-anchor chain
# ---------------------------------------------------------------------------


def _load_frozen_manifest_digests() -> dict[str, str]:
    """Load the trusted frozen-research manifest (path -> sha256)."""
    try:
        raw = FROZEN_MANIFEST_PATH.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise BenchmarkUnavailableError(
            "The trusted frozen-research manifest is missing; the benchmark "
            "catalog cannot be verified."
        ) from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BenchmarkIntegrityError(
            "The trusted frozen-research manifest is not valid JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise BenchmarkIntegrityError(
            "The trusted frozen-research manifest has an unexpected shape."
        )
    return {str(k): str(v) for k, v in payload.items()}


def _read_git_file(path: Path, rel_path: str) -> bytes:
    """Read a Git-tracked file, with a sanitized unavailable error."""
    try:
        return path.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise BenchmarkUnavailableError(
            f"The benchmark metadata file {rel_path!r} is missing or "
            f"unreadable; the catalog cannot be served."
        ) from exc


def _parse_json_metadata(data: bytes, rel_path: str) -> dict[str, Any]:
    """Parse a Git-tracked JSON metadata file (bounded, no execution)."""
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BenchmarkIntegrityError(
            f"The benchmark metadata file {rel_path!r} is not valid JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise BenchmarkIntegrityError(
            f"The benchmark metadata file {rel_path!r} has an unexpected shape."
        )
    return payload


def _verify_layer_a_trust_chain() -> tuple[bytes, bytes, bytes, dict[str, Any], str, str, str]:
    """Verify all Layer A files against their external trust anchors.

    Called on EVERY request before accepting a cache hit so tampering with
    ``ci/frozen_research_manifest.json``, ``phase4_commit_manifest.json``,
    ``phase4_run_metadata.json``, or ``src/mplad/common/config.py`` cannot be
    masked by a warm cache.
    """
    frozen_digests = _load_frozen_manifest_digests()
    config_bytes = _read_git_file(CONFIG_PATH, CONFIG_REL_PATH)
    config_digest = _sha256_frozen_checker(config_bytes)
    if frozen_digests.get(CONFIG_REL_PATH) != config_digest:
        raise BenchmarkIntegrityError(
            f"Frozen research integrity verification failed: {CONFIG_REL_PATH}"
        )

    commit_manifest_bytes = _read_git_file(
        COMMIT_MANIFEST_PATH, COMMIT_MANIFEST_REL_PATH
    )
    commit_manifest_digest = _sha256_windows_manifest(commit_manifest_bytes)
    if commit_manifest_digest != TRUSTED_COMMIT_MANIFEST_SHA256:
        raise BenchmarkIntegrityError(
            "Phase 4 commit manifest failed trusted anchor verification."
        )

    commit_manifest = _parse_json_metadata(
        commit_manifest_bytes, COMMIT_MANIFEST_REL_PATH
    )
    artifacts = commit_manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise BenchmarkIntegrityError(
            "The Phase 4 commit manifest has no artifacts section."
        )
    recorded_manifest_entry = artifacts.get("phase4_commit_manifest.json")
    if isinstance(recorded_manifest_entry, dict):
        recorded_sha = recorded_manifest_entry.get("sha256")
        if isinstance(recorded_sha, str) and recorded_sha != commit_manifest_digest:
            raise BenchmarkIntegrityError(
                "Phase 4 commit manifest self-verification failed."
            )

    run_meta_bytes = _read_git_file(RUN_METADATA_PATH, RUN_METADATA_REL_PATH)
    run_meta_digest = _sha256_windows_manifest(run_meta_bytes)
    recorded_run_meta = artifacts.get("phase4_run_metadata.json")
    if not isinstance(recorded_run_meta, dict):
        raise BenchmarkIntegrityError(
            "The Phase 4 commit manifest does not pin the run metadata."
        )
    if recorded_run_meta.get("sha256") != run_meta_digest:
        raise BenchmarkIntegrityError(
            f"Phase 4 metadata integrity verification failed: {RUN_METADATA_REL_PATH}"
        )
    if isinstance(recorded_run_meta.get("size_bytes"), int):
        crlf_size = len(_reconstruct_crlf(run_meta_bytes))
        if crlf_size != recorded_run_meta["size_bytes"]:
            raise BenchmarkIntegrityError(
                "Phase 4 run metadata size mismatch."
            )

    return (
        config_bytes,
        run_meta_bytes,
        commit_manifest_bytes,
        artifacts,
        config_digest,
        run_meta_digest,
        commit_manifest_digest,
    )


def _extract_config_constants(source: str) -> dict[str, Any]:
    """Extract the frozen experiment constants from ``config.py`` via AST."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise BenchmarkIntegrityError(
            "The frozen config module could not be parsed."
        ) from exc

    targets: dict[str, Any] = {}
    for node in tree.body:
        names: list[str] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            value = node.value
            names = [
                t.id for t in node.targets if isinstance(t, ast.Name)
            ]
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            if isinstance(node.target, ast.Name):
                names = [node.target.id]
        if value is None:
            continue
        for name in names:
            if name not in {
                "ISOLATION_FOREST_CONFIGS",
                "LOF_CONFIGS",
                "IF_FIXED_PARAMS",
                "LOF_FIXED_PARAMS",
                "SAMPLE_SIZE_DEFAULT",
                "SAMPLE_SEED_DEFAULT",
                "THRESHOLD_PERCENTILE",
                "THRESHOLD_RULE_LABEL",
            }:
                continue
            try:
                targets[name] = ast.literal_eval(value)
            except ValueError:
                continue
    required = {
        "ISOLATION_FOREST_CONFIGS",
        "LOF_CONFIGS",
        "SAMPLE_SIZE_DEFAULT",
        "SAMPLE_SEED_DEFAULT",
        "THRESHOLD_PERCENTILE",
    }
    missing = required - targets.keys()
    if missing:
        raise BenchmarkIntegrityError(
            f"The frozen config module is missing constants: {sorted(missing)}."
        )
    if "THRESHOLD_RULE_LABEL" not in targets:
        percentile = targets["THRESHOLD_PERCENTILE"]
        targets["THRESHOLD_RULE_LABEL"] = f"Bottom {percentile}% of scores"
    return targets


def _parse_layer_a(
    config_bytes: bytes,
    run_meta_bytes: bytes,
    artifacts: dict[str, Any],
    config_digest: str,
    run_meta_digest: str,
    commit_manifest_digest: str,
) -> dict[str, Any]:
    """Parse already-verified Layer A bytes into the catalog payload."""
    constants = _extract_config_constants(config_bytes.decode("utf-8"))
    run_meta = _parse_json_metadata(run_meta_bytes, RUN_METADATA_REL_PATH)

    if_configs = list(constants["ISOLATION_FOREST_CONFIGS"])
    lof_configs = list(constants["LOF_CONFIGS"])
    expected_run_ids = (
        [f"IF_{i:03d}" for i in range(1, len(if_configs) + 1)]
        + [f"LOF_{i:03d}" for i in range(1, len(lof_configs) + 1)]
    )
    if tuple(expected_run_ids) != CANONICAL_RUN_IDS:
        raise BenchmarkIntegrityError(
            "The frozen config grids do not produce the canonical ten run IDs."
        )
    run_meta_ids = run_meta.get("run_ids")
    if list(run_meta_ids or []) != expected_run_ids:
        raise BenchmarkIntegrityError(
            "The Phase 4 run metadata run_ids disagree with the frozen config grids."
        )
    sample = run_meta.get("sample") or {}
    if not isinstance(sample, dict):
        raise BenchmarkIntegrityError(
            "The Phase 4 run metadata has no sample section."
        )

    runs: list[dict[str, Any]] = []
    for run_id, config in zip(expected_run_ids, if_configs + lof_configs, strict=True):
        algo = _ALGO_BY_PREFIX[run_id.split("_")[0]]
        params = {k: v for k, v in dict(config).items()}
        fixed = (
            dict(constants.get("IF_FIXED_PARAMS", {}))
            if algo == "IsolationForest"
            else dict(constants.get("LOF_FIXED_PARAMS", {}))
        )
        runs.append(
            {
                "run_id": run_id,
                "algorithm": algo,
                "parameters": params,
                "fixed_pipeline_settings": fixed,
                "parameter_source": {
                    "path": CONFIG_REL_PATH,
                    "sha256": config_digest,
                    "digest_algorithm": DIGEST_ALGORITHM,
                    "canonicalization": FROZEN_CHECKER_CANONICALIZATION,
                    "note": (
                        "Parameters are frozen experiment inputs extracted "
                        "verbatim from the manifest-verified config module; "
                        "no scikit-learn default was inferred."
                    ),
                },
            }
        )

    return {
        "runs": runs,
        "sample": {
            "sample_size": int(sample["sample_size"]),
            "fraud_count": int(sample["fraud_count"]),
            "fraud_prevalence": float(sample["fraud_prevalence"]),
        },
        "registry_summary": dict(run_meta.get("registry_summary") or {}),
        "score_orientation": dict(run_meta.get("score_orientation") or {}),
        "environment": dict(run_meta.get("environment") or {}),
        "model_fitting": dict(run_meta.get("model_fitting") or {}),
        "threshold_rule": str(constants.get("THRESHOLD_RULE_LABEL", "")),
        "threshold_percentile": float(constants["THRESHOLD_PERCENTILE"]),
        "sample_seed": int(constants["SAMPLE_SEED_DEFAULT"]),
        "config_sha256": config_digest,
        "run_metadata_sha256": run_meta_digest,
        "commit_manifest_sha256": commit_manifest_digest,
        "commit_manifest_artifacts": {
            str(k): dict(v) for k, v in artifacts.items() if isinstance(v, dict)
        },
        "metric_definitions": [dict(d) for d in _METRIC_DEFINITIONS],
        "_verified_digests": {
            CONFIG_REL_PATH: config_digest,
            RUN_METADATA_REL_PATH: run_meta_digest,
            COMMIT_MANIFEST_REL_PATH: commit_manifest_digest,
        },
    }


# ---------------------------------------------------------------------------
# Layer B: DVC pointer parsing and payload verification (MD5 + SHA-256 + size)
# ---------------------------------------------------------------------------


def _parse_dvc_pointer(data: bytes, pointer_rel_path: str) -> dict[str, Any]:
    """Parse a Git-tracked ``.dvc`` pointer with a bounded safe loader."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BenchmarkIntegrityError(
            "The DVC pointer is not valid UTF-8."
        ) from exc
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not lines or lines[0].strip() != "outs:":
        raise BenchmarkIntegrityError(
            f"The DVC pointer {pointer_rel_path!r} does not start with 'outs:'."
        )
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in lines[1:]:
        if not line.startswith((" ", "\t", "-")):
            raise BenchmarkIntegrityError(
                f"The DVC pointer {pointer_rel_path!r} has unexpected top-level content."
            )
        stripped = line.strip()
        if stripped.startswith("- "):
            if current is not None:
                entries.append(current)
            current = {}
            stripped = stripped[2:].strip()
            if not stripped:
                continue
        if current is None:
            raise BenchmarkIntegrityError(
                f"The DVC pointer {pointer_rel_path!r} is malformed."
            )
        if ":" not in stripped:
            raise BenchmarkIntegrityError(
                f"The DVC pointer {pointer_rel_path!r} has a malformed entry."
            )
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if key not in _DVC_OUT_ALLOWED_KEYS:
            raise BenchmarkIntegrityError(
                f"The DVC pointer {pointer_rel_path!r} has an unexpected key {key!r}."
            )
        current[key] = value
    if current is not None:
        entries.append(current)
    if len(entries) != 1:
        raise BenchmarkIntegrityError(
            f"The DVC pointer {pointer_rel_path!r} must have exactly one "
            f"output entry (got {len(entries)})."
        )
    entry = entries[0]
    missing = _DVC_OUT_REQUIRED_KEYS - entry.keys()
    if missing:
        raise BenchmarkIntegrityError(
            f"The DVC pointer {pointer_rel_path!r} is missing keys: {sorted(missing)}."
        )
    if entry["hash"] != "md5":
        raise BenchmarkIntegrityError(
            f"The DVC pointer {pointer_rel_path!r} uses an unsupported hash "
            f"algorithm {entry['hash']!r}."
        )
    if not re.fullmatch(r"[0-9a-f]{32}", entry["md5"]):
        raise BenchmarkIntegrityError(
            f"The DVC pointer {pointer_rel_path!r} has a malformed md5 digest."
        )
    try:
        size = int(entry["size"])
    except ValueError as exc:
        raise BenchmarkIntegrityError(
            f"The DVC pointer {pointer_rel_path!r} has a malformed size."
        ) from exc
    return {"md5": entry["md5"], "size": size, "path": entry["path"]}


def _verify_payload_bytes(
    data: bytes,
    pointer: dict[str, Any],
    manifest_entry: dict[str, Any],
    payload_rel_path: str,
) -> tuple[str, str]:
    """Verify payload bytes against BOTH the .dvc pointer (MD5 + size) and
    the trusted Phase 4 commit manifest (SHA-256 + size_bytes).

    Uses a representation-consistent policy: checks the raw byte snapshot
    first, and for text payloads (no NUL bytes) also checks the
    CRLF-reconstructed representation so an LF-normalized checkout is not
    rejected by a pre-normalization raw byte-length check.
    Returns ``(verified_md5, verified_sha256)`` for the matched representation.
    """
    expected_sha256 = manifest_entry.get("sha256")
    expected_manifest_size = manifest_entry.get("size_bytes")
    if not isinstance(expected_sha256, str) or not isinstance(expected_manifest_size, int):
        raise BenchmarkIntegrityError(
            f"The Phase 4 commit manifest is missing a valid provenance entry for {payload_rel_path!r}."
        )

    candidates: list[bytes] = [data]
    if b"\x00" not in data:
        crlf = _reconstruct_crlf(data)
        if crlf != data:
            candidates.append(crlf)

    for candidate in candidates:
        if len(candidate) != pointer["size"] or len(candidate) != expected_manifest_size:
            continue
        md5_hex = _md5_raw(candidate)
        sha256_hex = _sha256_raw(candidate)
        if md5_hex == pointer["md5"] and sha256_hex == expected_sha256:
            return md5_hex, sha256_hex

    raise BenchmarkIntegrityError(
        f"Benchmark payload integrity verification failed: {payload_rel_path!r}"
    )


# ---------------------------------------------------------------------------
# CSV schema and scientific population validation
# ---------------------------------------------------------------------------


def _parse_csv_rows(data: bytes, rel_path: str) -> list[dict[str, str]]:
    """Parse a verified CSV byte snapshot into rows (bounded dict reader)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BenchmarkIntegrityError(
            f"The benchmark payload {rel_path!r} is not valid UTF-8."
        ) from exc
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise BenchmarkIntegrityError(
            f"The benchmark payload {rel_path!r} has no header row."
        )
    return list(reader)


def _validate_metrics_rows(
    rows: list[dict[str, str]], catalog: dict[str, Any], rel_path: str
) -> list[dict[str, str]]:
    """Validate the metrics CSV schema, run identity, and population counts."""
    header = set(rows[0].keys()) if rows else set()
    missing = [c for c in METRICS_COLUMNS if c not in header]
    if missing:
        raise BenchmarkIntegrityError(
            f"The metrics payload is missing required columns: {missing}."
        )
    if len(rows) != len(CANONICAL_RUN_IDS):
        raise BenchmarkIntegrityError(
            f"The metrics payload must have exactly {len(CANONICAL_RUN_IDS)} "
            f"rows (got {len(rows)})."
        )
    seen: list[str] = []
    for row in rows:
        run_id = (row.get("run_id") or "").strip()
        if not _RUN_ID_RE.fullmatch(run_id):
            raise BenchmarkIntegrityError(
                "The metrics payload contains an unexpected run identifier."
            )
        if run_id in seen:
            raise BenchmarkIntegrityError(
                "The metrics payload contains a duplicate run identifier."
            )
        if _coerce_int(row["sample_size"]) != catalog["sample"]["sample_size"]:
            raise BenchmarkIntegrityError(
                "The metrics payload sample_size disagrees with the verified run metadata."
            )
        if _coerce_int(row["fraud_count"]) != catalog["sample"]["fraud_count"]:
            raise BenchmarkIntegrityError(
                "The metrics payload fraud_count disagrees with the verified run metadata."
            )
        seen.append(run_id)
    if set(seen) != set(CANONICAL_RUN_IDS):
        raise BenchmarkIntegrityError(
            "The metrics payload run set does not match the canonical ten runs."
        )
    return rows


def _validate_evaluation_rows(
    rows: list[dict[str, str]], catalog: dict[str, Any], rel_path: str
) -> dict[tuple[str, int], dict[str, Any]]:
    """Validate canonical population, label, flag, and score invariants.

    Enforces:
    - Required columns present and all 10 canonical runs represented.
    - Exact expected record count per run (30,000 in canonical data).
    - Unique (run_id, row_id) keys and identical canonical row_id set across
      all 10 runs.
    - Consistent ground-truth Class in {0, 1} for each row_id across all runs,
      and positive label count per run matching verified metadata (47).
    - Valid saved flag in {0, 1} and saved flag cardinality per run matching
      the bottom-1% threshold budget (300 for 30,000 rows at 1.0%).
    - Finite scores and anomaly_score == -native_score consistency.
    Returns an O(1) lookup index keyed by ``(run_id, row_id)``.
    """
    header = set(rows[0].keys()) if rows else set()
    missing = [c for c in EVALUATION_DATASET_COLUMNS if c not in header]
    if missing:
        raise BenchmarkIntegrityError(
            f"The evaluation payload is missing required columns: {missing}."
        )

    if _SYNTHETIC_POPULATION_OVERRIDE is not None:
        expected_sample_size = _SYNTHETIC_POPULATION_OVERRIDE["sample_size"]
        expected_fraud_count = _SYNTHETIC_POPULATION_OVERRIDE["fraud_count"]
        expected_flagged_count = _SYNTHETIC_POPULATION_OVERRIDE["flagged_count"]
    else:
        expected_sample_size = int(catalog["sample"]["sample_size"])
        expected_fraud_count = int(catalog["sample"]["fraud_count"])
        pct = float(catalog["threshold_percentile"])
        expected_flagged_count = int(round(expected_sample_size * pct / 100.0))

    index: dict[tuple[str, int], dict[str, Any]] = {}
    row_ids_by_run: dict[str, set[int]] = {r: set() for r in CANONICAL_RUN_IDS}
    fraud_by_run: dict[str, int] = {r: 0 for r in CANONICAL_RUN_IDS}
    flagged_by_run: dict[str, int] = {r: 0 for r in CANONICAL_RUN_IDS}
    canonical_labels: dict[int, int] = {}

    for row in rows:
        run_id = (row.get("run_id") or "").strip()
        if not _RUN_ID_RE.fullmatch(run_id):
            raise BenchmarkIntegrityError(
                "The evaluation payload contains an unexpected run identifier."
            )
        raw_row_id = (row.get("row_id") or "").strip()
        if not raw_row_id:
            raise BenchmarkIntegrityError(
                "The evaluation payload contains an empty row_id."
            )
        row_id = _coerce_int(raw_row_id)
        for field in ("Class", "native_score", "anomaly_score", "flag"):
            value = (row.get(field) or "").strip()
            if value == "":
                raise BenchmarkIntegrityError(
                    "The evaluation payload contains a missing required field "
                    f"({field}); missing values are never defaulted."
                )

        key = (run_id, row_id)
        if key in index:
            raise BenchmarkIntegrityError(
                "The evaluation payload contains a duplicate (run_id, row_id)."
            )

        cls_val = _coerce_int(row["Class"])
        if cls_val not in (0, 1):
            raise BenchmarkIntegrityError(
                "The evaluation payload contains an invalid Class label."
            )
        if row_id in canonical_labels:
            if canonical_labels[row_id] != cls_val:
                raise BenchmarkIntegrityError(
                    "Ground-truth Class label is inconsistent across runs for the same row_id."
                )
        else:
            canonical_labels[row_id] = cls_val

        flag_val = _coerce_int(row["flag"])
        if flag_val not in (0, 1):
            raise BenchmarkIntegrityError(
                "The evaluation payload contains an invalid flag value."
            )

        native_val = _coerce_float(row["native_score"])
        anomaly_val = _coerce_float(row["anomaly_score"])
        if not (math.isfinite(native_val) and math.isfinite(anomaly_val)):
            raise BenchmarkIntegrityError(
                "The evaluation payload contains a non-finite score."
            )
        if not math.isclose(anomaly_val, -native_val, rel_tol=1e-7, abs_tol=1e-7):
            raise BenchmarkIntegrityError(
                "Oriented anomaly_score does not equal -native_score."
            )

        row_ids_by_run[run_id].add(row_id)
        fraud_by_run[run_id] += cls_val
        flagged_by_run[run_id] += flag_val
        index[key] = {
            "run_id": run_id,
            "row_id": row_id,
            "Class": cls_val,
            "native_score": native_val,
            "anomaly_score": anomaly_val,
            "flag": flag_val,
        }

    reference_row_ids: set[int] | None = None
    for run_id in CANONICAL_RUN_IDS:
        run_ids_set = row_ids_by_run[run_id]
        if len(run_ids_set) != expected_sample_size:
            raise BenchmarkIntegrityError(
                f"Run {run_id} has {len(run_ids_set)} records; expected {expected_sample_size}."
            )
        if reference_row_ids is None:
            reference_row_ids = run_ids_set
        elif run_ids_set != reference_row_ids:
            raise BenchmarkIntegrityError(
                f"Run {run_id} row_id population does not match the canonical sample."
            )
        if fraud_by_run[run_id] != expected_fraud_count:
            raise BenchmarkIntegrityError(
                f"Run {run_id} positive label count ({fraud_by_run[run_id]}) disagrees with expected {expected_fraud_count}."
            )
        if flagged_by_run[run_id] != expected_flagged_count:
            raise BenchmarkIntegrityError(
                f"Run {run_id} flagged count ({flagged_by_run[run_id]}) disagrees with expected {expected_flagged_count}."
            )

    return index


def _coerce_optional_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip()
    if text == "" or text.lower() == "n/a":
        return None
    try:
        val = float(text)
        if not math.isfinite(val):
            raise BenchmarkIntegrityError("Non-finite float in benchmark payload.")
        return val
    except ValueError:
        return None


def _coerce_float(value: str | None) -> float:
    text = (value or "").strip()
    try:
        val = float(text)
    except ValueError as exc:
        raise BenchmarkIntegrityError(
            "A required numeric field in the benchmark payload is malformed."
        ) from exc
    if not math.isfinite(val):
        raise BenchmarkIntegrityError(
            "A required numeric field in the benchmark payload is non-finite."
        )
    return val


def _coerce_int(value: str | None) -> int:
    text = (value or "").strip()
    try:
        return int(text)
    except ValueError as exc:
        raise BenchmarkIntegrityError(
            "A required integer field in the benchmark payload is malformed."
        ) from exc


# ---------------------------------------------------------------------------
# Bounded caches with per-request trust-anchor & digest re-verification
# ---------------------------------------------------------------------------

_LAYER_A_CACHE: dict[str, Any] | None = None
_LAYER_B_METRICS_CACHE: dict[str, Any] | None = None
_LAYER_B_ROWS_CACHE: dict[str, Any] | None = None


def _invalidate_caches() -> None:
    """Invalidate all layer caches (used by tests and integrity failures)."""
    global _LAYER_A_CACHE, _LAYER_B_METRICS_CACHE, _LAYER_B_ROWS_CACHE
    _LAYER_A_CACHE = None
    _LAYER_B_METRICS_CACHE = None
    _LAYER_B_ROWS_CACHE = None


def _load_catalog() -> dict[str, Any]:
    """Return the verified Layer A catalog.

    Re-verifies every Layer A artifact against its external trust anchor
    (``ci/frozen_research_manifest.json`` and ``TRUSTED_COMMIT_MANIFEST_SHA256``)
    on EVERY request BEFORE accepting ``_LAYER_A_CACHE``.
    """
    global _LAYER_A_CACHE

    try:
        (
            config_bytes,
            run_meta_bytes,
            _commit_manifest_bytes,
            artifacts,
            config_digest,
            run_meta_digest,
            commit_manifest_digest,
        ) = _verify_layer_a_trust_chain()
    except (BenchmarkUnavailableError, BenchmarkIntegrityError):
        _LAYER_A_CACHE = None
        raise

    current_digests = {
        CONFIG_REL_PATH: config_digest,
        RUN_METADATA_REL_PATH: run_meta_digest,
        COMMIT_MANIFEST_REL_PATH: commit_manifest_digest,
    }

    if _LAYER_A_CACHE is not None:
        if current_digests == _LAYER_A_CACHE["_verified_digests"]:
            return _LAYER_A_CACHE
        _LAYER_A_CACHE = None

    catalog = _parse_layer_a(
        config_bytes=config_bytes,
        run_meta_bytes=run_meta_bytes,
        artifacts=artifacts,
        config_digest=config_digest,
        run_meta_digest=run_meta_digest,
        commit_manifest_digest=commit_manifest_digest,
    )
    _LAYER_A_CACHE = catalog
    return catalog


def _get_spec_for_role(role: str) -> tuple[str, str]:
    for payload_rel, pointer_rel, spec_role in _DVC_PAYLOAD_SPECS:
        if spec_role == role:
            return payload_rel, pointer_rel
    raise BenchmarkIntegrityError(f"Unknown Layer B capability role: {role!r}.")


def _load_single_dvc_capability(
    role: str,
    manifest_key: str,
    cache_ref: dict[str, Any] | None,
) -> tuple[dict[str, Any], bool]:
    """Verify pointer + payload (MD5, SHA-256, size) for one Layer B role.

    Returns ``(state_or_cached_payload, is_cache_hit)``.
    """
    catalog = _load_catalog()
    payload_rel, pointer_rel = _get_spec_for_role(role)
    expected_name = payload_rel.replace("\\", "/").rsplit("/", 1)[-1]

    pointer_bytes = _read_git_file(REPO_ROOT / pointer_rel, pointer_rel)
    pointer = _parse_dvc_pointer(pointer_bytes, pointer_rel)
    if pointer["path"] != expected_name:
        raise BenchmarkIntegrityError(
            f"The DVC pointer {pointer_rel!r} points at an unexpected output path."
        )
    pointer_digest = hashlib.sha256(pointer_bytes).hexdigest()

    manifest_entry = catalog["commit_manifest_artifacts"].get(manifest_key)
    if not isinstance(manifest_entry, dict):
        raise BenchmarkIntegrityError(
            f"The Phase 4 commit manifest does not pin {manifest_key!r}."
        )

    payload_path = REPO_ROOT / payload_rel
    try:
        data = payload_path.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise BenchmarkUnavailableError(
            "The benchmark payload is missing; verified results cannot be served."
        ) from exc

    verified_md5, verified_sha256 = _verify_payload_bytes(
        data, pointer, manifest_entry, payload_rel
    )

    if cache_ref is not None:
        if (
            cache_ref.get("_pointer_sha256") == pointer_digest
            and cache_ref.get("_payload_md5") == verified_md5
            and cache_ref.get("_payload_sha256") == verified_sha256
            and cache_ref.get("_catalog_digests") == catalog["_verified_digests"]
        ):
            return cache_ref, True

    return (
        {
            "catalog": catalog,
            "data": data,
            "payload_rel": payload_rel,
            "pointer_digest": pointer_digest,
            "verified_md5": verified_md5,
            "verified_sha256": verified_sha256,
        },
        False,
    )


def _load_layer_b_metrics() -> dict[str, Any]:
    """Load and cache ONLY the admitted metrics CSV independently of row-level data."""
    global _LAYER_B_METRICS_CACHE
    try:
        res, hit = _load_single_dvc_capability(
            role="metrics",
            manifest_key="phase4_metrics.csv",
            cache_ref=_LAYER_B_METRICS_CACHE,
        )
    except (BenchmarkUnavailableError, BenchmarkIntegrityError):
        _LAYER_B_METRICS_CACHE = None
        raise
    if hit:
        return res

    catalog = res["catalog"]
    metrics_rel = res["payload_rel"]
    metrics_rows = _parse_csv_rows(res["data"], metrics_rel)
    metrics_rows = _validate_metrics_rows(metrics_rows, catalog, metrics_rel)

    cached: dict[str, Any] = {
        "metrics_rows": metrics_rows,
        "metrics_rel_path": metrics_rel,
        "metrics_md5": res["verified_md5"],
        "metrics_sha256": res["verified_sha256"],
        "_pointer_sha256": res["pointer_digest"],
        "_payload_md5": res["verified_md5"],
        "_payload_sha256": res["verified_sha256"],
        "_catalog_digests": dict(catalog["_verified_digests"]),
    }
    _LAYER_B_METRICS_CACHE = cached
    return cached


def _load_layer_b_rows() -> dict[str, Any]:
    """Load and cache ONLY the admitted row-level CSV independently of metrics."""
    global _LAYER_B_ROWS_CACHE
    try:
        res, hit = _load_single_dvc_capability(
            role="row_level",
            manifest_key="phase4_evaluation_dataset.csv",
            cache_ref=_LAYER_B_ROWS_CACHE,
        )
    except (BenchmarkUnavailableError, BenchmarkIntegrityError):
        _LAYER_B_ROWS_CACHE = None
        raise
    if hit:
        return res

    catalog = res["catalog"]
    eval_rel = res["payload_rel"]
    eval_rows = _parse_csv_rows(res["data"], eval_rel)
    row_index = _validate_evaluation_rows(eval_rows, catalog, eval_rel)

    cached: dict[str, Any] = {
        "row_index": row_index,
        "eval_rel_path": eval_rel,
        "eval_md5": res["verified_md5"],
        "eval_sha256": res["verified_sha256"],
        "_pointer_sha256": res["pointer_digest"],
        "_payload_md5": res["verified_md5"],
        "_payload_sha256": res["verified_sha256"],
        "_catalog_digests": dict(catalog["_verified_digests"]),
    }
    _LAYER_B_ROWS_CACHE = cached
    return cached


def _layer_b_availability() -> dict[str, Any]:
    """Probe Layer B availability independently per capability without raising."""
    capabilities: dict[str, Any] = {}
    try:
        catalog = _load_catalog()
        manifest_artifacts = catalog["commit_manifest_artifacts"]
    except (BenchmarkUnavailableError, BenchmarkIntegrityError) as exc:
        for _, _, role in _DVC_PAYLOAD_SPECS:
            capabilities[role] = {
                "available": False,
                "reason": "integrity_failed" if isinstance(exc, BenchmarkIntegrityError) else "artifact_missing",
                "detail": str(exc),
            }
        return capabilities

    role_to_manifest_key = {
        "metrics": "phase4_metrics.csv",
        "row_level": "phase4_evaluation_dataset.csv",
    }

    for payload_rel, pointer_rel, role in _DVC_PAYLOAD_SPECS:
        try:
            pointer_bytes = _read_git_file(REPO_ROOT / pointer_rel, pointer_rel)
            pointer = _parse_dvc_pointer(pointer_bytes, pointer_rel)
            expected_name = payload_rel.replace("\\", "/").rsplit("/", 1)[-1]
            if pointer["path"] != expected_name:
                capabilities[role] = {
                    "available": False,
                    "reason": "integrity_failed",
                    "detail": "The DVC pointer targets an unexpected output path.",
                }
                continue
            manifest_entry = manifest_artifacts.get(role_to_manifest_key[role])
            if not isinstance(manifest_entry, dict):
                capabilities[role] = {
                    "available": False,
                    "reason": "integrity_failed",
                    "detail": "The Phase 4 commit manifest does not pin this payload.",
                }
                continue
            try:
                data = (REPO_ROOT / payload_rel).read_bytes()
            except (FileNotFoundError, OSError):
                capabilities[role] = {
                    "available": False,
                    "reason": "artifact_missing",
                    "detail": (
                        "The DVC-backed payload has not been materialized in "
                        "this deployment; the verified catalog is available "
                        "but saved values cannot be served."
                    ),
                }
                continue
            _verify_payload_bytes(data, pointer, manifest_entry, payload_rel)
            capabilities[role] = {
                "available": True,
                "reason": None,
                "detail": None,
            }
        except BenchmarkIntegrityError as exc:
            capabilities[role] = {
                "available": False,
                "reason": "integrity_failed",
                "detail": str(exc),
            }
        except BenchmarkUnavailableError as exc:
            capabilities[role] = {
                "available": False,
                "reason": "artifact_missing",
                "detail": str(exc),
            }
    return capabilities


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class BenchmarkCatalogService:
    """Read-only service over the canonical ten-run benchmark (PR-09)."""

    source_id: str = BENCHMARK_SOURCE_ID
    dataset_id: str = DATASET_ID
    limitations: tuple[str, ...] = LIMITATIONS

    def availability(self) -> dict[str, Any]:
        return _layer_b_availability()

    def list_experiments(self) -> list[dict[str, Any]]:
        catalog = _load_catalog()
        availability = _layer_b_availability()
        metrics_available = bool(availability.get("metrics", {}).get("available"))
        row_available = bool(availability.get("row_level", {}).get("available"))
        return [
            {
                "run_id": run["run_id"],
                "algorithm": run["algorithm"],
                "parameters": dict(run["parameters"]),
                "parameter_source": dict(run["parameter_source"]),
                "dataset_id": DATASET_ID,
                "model_status": "fitted_offline_frozen",
                "metrics_available": metrics_available,
                "row_lookup_available": row_available,
            }
            for run in catalog["runs"]
        ]

    def get_experiment(self, run_id: str) -> dict[str, Any]:
        catalog = _load_catalog()
        run = self._find_run(catalog, run_id)
        availability = _layer_b_availability()
        return {
            "run_id": run["run_id"],
            "algorithm": run["algorithm"],
            "parameters": dict(run["parameters"]),
            "fixed_pipeline_settings": dict(run["fixed_pipeline_settings"]),
            "parameter_source": dict(run["parameter_source"]),
            "dataset_id": DATASET_ID,
            "model_status": "fitted_offline_frozen",
            "metrics_available": bool(
                availability.get("metrics", {}).get("available")
            ),
            "row_lookup_available": bool(
                availability.get("row_level", {}).get("available")
            ),
            "dataset_scope": {
                "sample": dict(catalog["sample"]),
                "registry_summary": dict(catalog["registry_summary"]),
                "threshold_rule": catalog["threshold_rule"],
                "threshold_percentile": catalog["threshold_percentile"],
                "sample_seed": catalog["sample_seed"],
                "score_orientation": dict(catalog["score_orientation"]),
                "environment": dict(catalog["environment"]),
                "model_fitting": dict(catalog["model_fitting"]),
            },
            "provenance": {
                "config": {
                    "path": CONFIG_REL_PATH,
                    "sha256": catalog["config_sha256"],
                    "digest_algorithm": DIGEST_ALGORITHM,
                    "canonicalization": FROZEN_CHECKER_CANONICALIZATION,
                },
                "run_metadata": {
                    "path": RUN_METADATA_REL_PATH,
                    "sha256": catalog["run_metadata_sha256"],
                    "digest_algorithm": DIGEST_ALGORITHM,
                    "canonicalization": WINDOWS_MANIFEST_CANONICALIZATION,
                },
                "commit_manifest": {
                    "path": COMMIT_MANIFEST_REL_PATH,
                    "sha256": catalog["commit_manifest_sha256"],
                    "digest_algorithm": DIGEST_ALGORITHM,
                    "canonicalization": WINDOWS_MANIFEST_CANONICALIZATION,
                },
            },
            "limitations": list(LIMITATIONS),
        }

    def get_metrics(self) -> dict[str, Any]:
        """Return verified saved metrics independently of row-level dataset."""
        catalog = _load_catalog()
        metrics_layer = _load_layer_b_metrics()
        metrics_rows = metrics_layer["metrics_rows"]
        items: list[dict[str, Any]] = []
        for row in metrics_rows:
            items.append(
                {
                    "run_id": row["run_id"].strip(),
                    "model": (row.get("model") or "").strip(),
                    "average_precision": _coerce_float(row["average_precision"]),
                    "roc_auc": _coerce_float(row["roc_auc"]),
                    "precision_at_1pct": _coerce_float(row["precision_at_1pct"]),
                    "recall_at_1pct": _coerce_float(row["recall_at_1pct"]),
                    "f1_at_1pct": _coerce_float(row["f1_at_1pct"]),
                    "tn": _coerce_int(row["tn"]),
                    "fp": _coerce_int(row["fp"]),
                    "fn": _coerce_int(row["fn"]),
                    "tp": _coerce_int(row["tp"]),
                    "sample_size": _coerce_int(row["sample_size"]),
                    "fraud_count": _coerce_int(row["fraud_count"]),
                    "fraud_prevalence": _coerce_float(row["fraud_prevalence"]),
                    "flagged_count": _coerce_int(row["flagged_count"]),
                    "flagged_proportion": _coerce_float(row["flagged_proportion"]),
                    "runtime_seconds": _coerce_optional_float(row.get("runtime_seconds")),
                    "threshold_rule": (row.get("threshold_rule") or "").strip(),
                }
            )
        return {
            "source_id": BENCHMARK_SOURCE_ID,
            "dataset_id": DATASET_ID,
            "sample": dict(catalog["sample"]),
            "metrics": items,
            "metric_definitions": [dict(d) for d in catalog["metric_definitions"]],
            "provenance": {
                "metrics_path": metrics_layer["metrics_rel_path"],
                "metrics_md5": metrics_layer["metrics_md5"],
                "metrics_sha256": metrics_layer["metrics_sha256"],
                "verification": (
                    "DVC pointer md5 + size and Phase 4 commit manifest sha256 + "
                    "size_bytes verified; schema and population cross-checked "
                    "against manifest-verified run metadata."
                ),
            },
            "limitations": list(LIMITATIONS),
            "is_precomputed": True,
            "is_live_prediction": False,
        }

    def get_record(self, run_id: str, row_id: int) -> dict[str, Any]:
        """Return one saved row for ``(run_id, row_id)`` independently of metrics."""
        catalog = _load_catalog()
        self._find_run(catalog, run_id)
        rows_layer = _load_layer_b_rows()
        row = rows_layer["row_index"].get((run_id, int(row_id)))
        if row is None:
            raise SourceNotFoundError(
                f"No canonical record {row_id!r} exists for run {run_id!r}."
            )
        return {
            "run_id": run_id,
            "row_id": row["row_id"],
            "label": {
                "Class": row["Class"],
                "provenance": (
                    "Ground-truth ULB evaluation label joined on row_id "
                    "during the frozen Phase 4 evaluation; distinct from the "
                    "detector flag."
                ),
            },
            "scores": {
                "native_score": row["native_score"],
                "anomaly_score": row["anomaly_score"],
                "native_definition": "Phase 3 native estimator score; lower = more anomalous",
                "anomaly_definition": "-native_score; higher = more anomalous (saved column)",
            },
            "flag": {
                "value": row["flag"],
                "provenance": "Saved Phase 3 bottom-1% flag; never recomputed.",
            },
            "dataset_id": DATASET_ID,
            "sample": dict(catalog["sample"]),
            "score_orientation": dict(catalog["score_orientation"]),
            "provenance": {
                "evaluation_dataset_path": rows_layer["eval_rel_path"],
                "evaluation_dataset_md5": rows_layer["eval_md5"],
                "evaluation_dataset_sha256": rows_layer["eval_sha256"],
                "verification": (
                    "DVC pointer md5 + size and Phase 4 commit manifest sha256 + "
                    "size_bytes verified; canonical row population and score/label/flag "
                    "invariants validated; resolved by exact saved row_id."
                ),
            },
            "limitations": list(LIMITATIONS),
            "is_precomputed": True,
            "is_live_prediction": False,
        }

    def _find_run(self, catalog: dict[str, Any], run_id: str) -> dict[str, Any]:
        if not isinstance(run_id, str) or not _RUN_ID_RE.fullmatch(run_id):
            raise SourceNotFoundError(
                f"No canonical benchmark run is registered under {run_id!r}."
            )
        for run in catalog["runs"]:
            if run["run_id"] == run_id:
                return run
        raise SourceNotFoundError(
            f"No canonical benchmark run is registered under {run_id!r}."
        )


BENCHMARK_CATALOG_SERVICE = BenchmarkCatalogService()
