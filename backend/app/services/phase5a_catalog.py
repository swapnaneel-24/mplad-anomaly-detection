"""Read-only Phase 5A evidence adapter (PR-10).

Serves the frozen Stream A Phase 5A quantitative-diagnostic evidence
(uncertainty, agreement, review-policy and discovery-curve artifacts) through
two distinct evidence layers, reusing the shared trust-chain framework in
``app.services.frozen_evidence_trust``:

**Layer A — Git-verified protocol metadata.**
Consumes only Git-tracked, frozen, manifest-verified files
(``src/mplad/common/config.py``, ``src/mplad/stream_a/phase5_analysis.py``
and the Phase 5 reproduction metadata under
``results/stream a/phase 5/reproduction/``). Never executes a frozen module.
The Phase 5 commit manifest is verified through the windows-commit-manifest-
compatible identity rule (LF→CRLF reconstruction), and the Phase 4 input
lineage SHA-256 recorded in the Phase 5 metadata is cross-checked against the
PR-09 admitted Phase 4 identity.

**Layer B — optional DVC-backed evidence families.**
Eight independent artifact families (bootstrap, paired differences, Spearman,
Jaccard, multi-threshold, hypergeometric, agreement groups, discovery
curve). Each has its own loader, cache and availability probe, so one
missing/absent payload never disables an unrelated result. Each payload is
resolved from a fixed server-side allowlist, verified against its ``.dvc``
pointer (md5+size), its commit-manifest SHA-256, and the frozen Phase 5
column contract before parsing.

Cache-integrity policy (identical to the accepted PR-08/09 contract): each
cache stores parsed payloads together with the digests verified at parse
time; on every request the artifact digests are recomputed and compared, so a
changed or removed payload fails closed and a restored payload recovers
without restart.

Scientific protections enforced:

* No model fitting, scoring, threshold recomputation, bootstrap resampling,
  pickle deserialization, DVC execution or downloads.
* Saved Phase 3 flags are never recomputed; derived top-k selections are
  labelled as derived.
* The paired-comparison direction ``LOF_004 − IF_003`` is never inverted.
* Hypergeometric log-probabilities are preserved (never exponentiated to a
  misleading zero); the null is stated alongside every p-value.
* The four review policies are labelled with their actual (unequal) review
  costs — never as an equal-budget comparison.
* The discovery curve is served through strictly bounded pagination; the full
  15 MB is never serialized into one response.
* Sanitized errors only: no server paths, no stack traces.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

from app.services import frozen_evidence_trust as trust
from app.services.source_registry import SourceNotFoundError

# ---------------------------------------------------------------------------
# Fixed paths and identities (server-side allowlist)
# ---------------------------------------------------------------------------

REPO_ROOT: Path = Path(__file__).resolve().parents[3]

CONFIG_REL_PATH: str = "src/mplad/common/config.py"
PHASE5_ANALYSIS_REL_PATH: str = "src/mplad/stream_a/phase5_analysis.py"
FROZEN_MANIFEST_REL_PATH: str = "ci/frozen_research_manifest.json"

PHASE5_REPRO_REL_DIR: str = "results/stream a/phase 5/reproduction"
RUN_METADATA_REL_PATH: str = f"{PHASE5_REPRO_REL_DIR}/phase5_run_metadata.json"
COMMIT_MANIFEST_REL_PATH: str = f"{PHASE5_REPRO_REL_DIR}/phase5_commit_manifest.json"

CONFIG_PATH: Path = REPO_ROOT / CONFIG_REL_PATH
PHASE5_ANALYSIS_PATH: Path = REPO_ROOT / PHASE5_ANALYSIS_REL_PATH
FROZEN_MANIFEST_PATH: Path = REPO_ROOT / FROZEN_MANIFEST_REL_PATH
RUN_METADATA_PATH: Path = REPO_ROOT / RUN_METADATA_REL_PATH
COMMIT_MANIFEST_PATH: Path = REPO_ROOT / COMMIT_MANIFEST_REL_PATH

#: Fixed Phase 4 lineage identities (PR-09 admitted; cross-checked against
#: the Phase 5 metadata's recorded input_manifest).
PHASE4_EVAL_DATASET_SHA256: str = (
    "affbf02c63da594d1fdb2c66d07121f39221f7e24082eed4770b59d4598bb048"
)
PHASE4_METRICS_SHA256: str = (
    "6535001ce38766d7e52fef84253a7d95e6335b6183fd34f6ead12210eec99acd"
)
PHASE4_RUN_METADATA_SHA256: str = (
    "b17f40635e73cbc11932447a9616bc9288f9bfbbc50103e2441b8d3aeb736ac1"
)

#: Catalog/source identities surfaced by the API.
PHASE5A_SOURCE_ID: str = "phase5a-uncertainty-agreement-evidence"
DATASET_ID: str = "ULB credit-card transactions (Stream A, FS-A baseline)"

#: The ten canonical runs and the three highlighted bootstrap runs (frozen).
CANONICAL_RUN_IDS: tuple[str, ...] = (
    "IF_001", "IF_002", "IF_003", "IF_004", "IF_005",
    "LOF_001", "LOF_002", "LOF_003", "LOF_004", "LOF_005",
)
BOOTSTRAP_RUN_IDS: tuple[str, ...] = ("IF_003", "IF_004", "LOF_004")
PAIRED_RUN_A: str = "IF_003"
PAIRED_RUN_B: str = "LOF_004"
PAIRED_COMPARISON_DEFINITION: str = "LOF_004 - IF_003"
OVERLAP_RUN_A: str = "IF_003"
OVERLAP_RUN_B: str = "LOF_004"

#: Frozen bootstrap protocol constants (from the verified metadata).
BOOTSTRAP_REPLICATES: int = 2_000
BOOTSTRAP_CI_LEVEL: float = 0.95
BOOTSTRAP_CI_METHOD: str = "percentile"
BOOTSTRAP_SEED: int = 42
SAMPLE_SIZE: int = 30_000
FRAUD_COUNT: int = 47
CANONICAL_THRESHOLD_PCT: float = 1.0
MULTI_THRESHOLD_PERCENTS: tuple[float, ...] = (0.1, 0.2, 0.5, 1.0, 2.0, 5.0)

#: Frozen column contracts (mirrored from phase5_analysis.py for schema
#: validation; the adapter never executes the frozen module).
BOOTSTRAP_METRICS_COLUMNS: tuple[str, ...] = (
    "run_id", "metric", "point_estimate", "bootstrap_mean",
    "bootstrap_std", "ci_lower", "ci_upper", "n_replicates",
)
PAIRED_DIFFERENCES_COLUMNS: tuple[str, ...] = (
    "comparison", "run_a", "run_b", "metric", "point_estimate",
    "bootstrap_mean", "bootstrap_std", "ci_lower", "ci_upper", "n_replicates",
)
MULTITHRESHOLD_AGREEMENT_COLUMNS: tuple[str, ...] = (
    "threshold_pct", "k_nominal", "selection_source",
    "n_methods", "observation_count",
)
HYPERGEOMETRIC_OVERLAP_COLUMNS: tuple[str, ...] = (
    "run_a", "run_b", "threshold_pct", "n_observations",
    "run_a_flagged", "run_b_flagged", "observed_intersection",
    "union_size", "expected_intersection",
    "enrichment_observed_over_expected", "survival_upper_tail",
    "log_survival", "log10_survival", "null_model",
)
AGREEMENT_GROUPS_COLUMNS: tuple[str, ...] = (
    "run_a", "run_b", "threshold_pct", "group", "observation_count",
    "fraud_count", "non_fraud_count", "fraud_proportion",
    "recall_contribution",
)
FRAUD_DISCOVERY_CURVE_COLUMNS: tuple[str, ...] = (
    "run_id", "budget", "fraud_found", "precision", "recall",
)
BOOTSTRAP_METRIC_NAMES: tuple[str, ...] = (
    "average_precision", "roc_auc", "precision_at_1pct",
    "recall_at_1pct", "f1_at_1pct",
)
AGREEMENT_GROUP_LABELS: tuple[str, ...] = (
    "both", "if_only", "lof_only", "neither",
)

#: Discovery-curve pagination bounds (PR-10 §6.I).
DISCOVERY_DEFAULT_LIMIT: int = 100
DISCOVERY_MAX_LIMIT: int = 200

#: Scientific limitations attached to every Phase 5A response.
LIMITATIONS: tuple[str, ...] = (
    "A statistical anomaly flag is not fraud and never implies misconduct or "
    "any legal finding.",
    "The ULB dataset is a credit-card benchmark, not public-expenditure "
    "transactions; results must not be assumed to transfer to PMGSY/MPLADS.",
    "IF_003, IF_004, LOF_004 and the IF_003/LOF_004 pair were selected "
    "post-hoc after inspecting label-informed results; comparisons are "
    "exploratory, not confirmatory.",
    "Rank agreement (Spearman) and flag overlap (Jaccard) are distinct "
    "concepts; neither establishes fraud-detection correctness.",
    "Review workload is the number of records requiring manual attention, "
    "not computation time; the four review policies have unequal costs.",
    "A hypergeometric p-value describes the stated overlap null only — not "
    "the probability that flagged records are fraudulent or that any "
    "detector is correct.",
    "Both-only, IF-only, LOF-only and Union are saved canonical selections "
    "with different review costs; they are NOT an equal-budget comparison "
    "and are distinct from the future R2 rank-consensus strategy.",
    "A bootstrap confidence interval is not a calibrated probability of "
    "wrongdoing; overlapping/non-overlapping intervals do not by themselves "
    "establish statistical significance without the paired comparison.",
    "All values are precomputed and frozen; the API never fits a model, "
    "runs a bootstrap, recomputes a threshold or produces a live prediction.",
)

#: Per-family DVC payload spec: (family, payload_rel, pointer_rel, role).
_FAMILY_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("bootstrap", f"{PHASE5_REPRO_REL_DIR}/phase5_bootstrap_metrics.csv",
     f"{PHASE5_REPRO_REL_DIR}/phase5_bootstrap_metrics.csv.dvc", "bootstrap_metrics"),
    ("paired", f"{PHASE5_REPRO_REL_DIR}/phase5_paired_bootstrap_differences.csv",
     f"{PHASE5_REPRO_REL_DIR}/phase5_paired_bootstrap_differences.csv.dvc", "paired_differences"),
    ("spearman", f"{PHASE5_REPRO_REL_DIR}/phase5_pairwise_spearman.csv",
     f"{PHASE5_REPRO_REL_DIR}/phase5_pairwise_spearman.csv.dvc", "pairwise_spearman"),
    ("jaccard", f"{PHASE5_REPRO_REL_DIR}/phase5_pairwise_jaccard_1pct.csv",
     f"{PHASE5_REPRO_REL_DIR}/phase5_pairwise_jaccard_1pct.csv.dvc", "pairwise_jaccard_1pct"),
    ("multithreshold", f"{PHASE5_REPRO_REL_DIR}/phase5_multithreshold_agreement.csv",
     f"{PHASE5_REPRO_REL_DIR}/phase5_multithreshold_agreement.csv.dvc", "multithreshold_agreement"),
    ("hypergeometric", f"{PHASE5_REPRO_REL_DIR}/phase5_hypergeometric_overlap.csv",
     f"{PHASE5_REPRO_REL_DIR}/phase5_hypergeometric_overlap.csv.dvc", "hypergeometric_overlap"),
    ("groups", f"{PHASE5_REPRO_REL_DIR}/phase5_agreement_groups.csv",
     f"{PHASE5_REPRO_REL_DIR}/phase5_agreement_groups.csv.dvc", "agreement_groups"),
    ("discovery", f"{PHASE5_REPRO_REL_DIR}/phase5_fraud_discovery_curve.csv",
     f"{PHASE5_REPRO_REL_DIR}/phase5_fraud_discovery_curve.csv.dvc", "fraud_discovery_curve"),
)

_RUN_ID_RE = __import__("re").compile(r"^(IF|LOF)_(00[1-5])$")

# Independent pinned identity of the Windows-generated Phase 5 commit manifest.
# Verify this pin against the actual authoritative Git file in the maintainer's
# checkout before merge (the bundled source representation is not Git itself).
TRUSTED_PHASE5_COMMIT_MANIFEST_SHA256: str = (
    "5e8311f2246bf3b8295648fb727d8277edeb340863002109a41ac2dc1dba7d5d"
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class Phase5AIntegrityError(Exception):
    """A consumed Phase 5A artifact failed integrity verification.

    Mapped by the API layer to a sanitized 503 ``SERVICE_NOT_READY`` with
    reason ``integrity_failed``.
    """


class Phase5AUnavailableError(Exception):
    """A required Phase 5A artifact is missing (e.g. DVC payload absent).

    Mapped by the API layer to a sanitized 503 ``SERVICE_NOT_READY`` with
    reason ``artifact_missing`` (or ``source_not_admitted`` when the whole
    capability is not admitted).
    """


_INTEGRITY_CLS = Phase5AIntegrityError
_UNAVAILABLE_CLS = Phase5AUnavailableError


# ---------------------------------------------------------------------------
# Layer A: Git-verified protocol metadata
# ---------------------------------------------------------------------------


def _load_frozen_manifest_digests() -> dict[str, str]:
    return trust.load_frozen_manifest_digests(
        FROZEN_MANIFEST_PATH, unavailable_cls=_UNAVAILABLE_CLS
    )


def _extract_phase5a_constants(source: str) -> dict[str, Any]:
    """Extract the frozen Phase 5A constants from ``config.py`` via AST.

    Only module-level simple/annotated assignments of bounded literals are
    parsed; the module is never executed.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise Phase5AIntegrityError(
            "The frozen config module could not be parsed."
        ) from exc
    wanted = {
        "PHASE5_BOOTSTRAP_REPLICATES_DEFAULT",
        "PHASE5_BOOTSTRAP_SEED_DEFAULT",
        "PHASE5_CI_LEVEL",
        "PHASE5_MULTI_THRESHOLD_PERCENTS",
        "PHASE5_CANONICAL_THRESHOLD_PCT",
    }
    targets: dict[str, Any] = {}
    for node in tree.body:
        names: list[str] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            value = node.value
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            if isinstance(node.target, ast.Name):
                names = [node.target.id]
        if value is None:
            continue
        for name in names:
            if name in wanted | {
                "PHASE5_BOOTSTRAP_RUN_IDS",
                "PHASE5_PAIRED_COMPARISON_RUNS",
                "PHASE5_OVERLAP_RUN_A",
                "PHASE5_OVERLAP_RUN_B",
            }:
                try:
                    targets[name] = ast.literal_eval(value)
                except ValueError:
                    continue
    missing = wanted - targets.keys()
    if missing:
        raise Phase5AIntegrityError(
            f"The frozen config module is missing Phase 5A constants: {sorted(missing)}."
        )
    return targets


def _load_layer_a() -> dict[str, Any]:
    """Load and verify every Layer A artifact; return the protocol payload.

    Verification chain (PR10_SOURCE_ADMISSION.md §3.1):

    * ``config.py`` and ``phase5_analysis.py`` digests vs the frozen research
      manifest (frozen-checker-compatible rule).
    * ``phase5_run_metadata.json`` and ``phase5_commit_manifest.json`` digests
      vs the commit manifest's own artifacts section (windows-commit-manifest-
      compatible rule: LF→CRLF reconstruction).
    * Phase 4 input lineage SHA-256 cross-checked against the PR-09 admitted
      identity.
    """
    # --- frozen source modules against the frozen research manifest --------
    frozen_digests = _load_frozen_manifest_digests()
    config_bytes = trust.read_git_file(
        CONFIG_PATH, CONFIG_REL_PATH, unavailable_cls=_UNAVAILABLE_CLS
    )
    config_digest = trust.sha256_frozen_checker(config_bytes)
    if frozen_digests.get(CONFIG_REL_PATH) != config_digest:
        raise Phase5AIntegrityError(
            f"Frozen research integrity verification failed: {CONFIG_REL_PATH}"
        )
    config_constants = _extract_phase5a_constants(config_bytes.decode("utf-8"))

    analysis_bytes = trust.read_git_file(
        PHASE5_ANALYSIS_PATH, PHASE5_ANALYSIS_REL_PATH, unavailable_cls=_UNAVAILABLE_CLS
    )
    analysis_digest = trust.sha256_frozen_checker(analysis_bytes)
    if frozen_digests.get(PHASE5_ANALYSIS_REL_PATH) != analysis_digest:
        raise Phase5AIntegrityError(
            f"Frozen research integrity verification failed: {PHASE5_ANALYSIS_REL_PATH}"
        )

    # --- commit manifest (self-consistent artifacts section) ---------------
    commit_manifest_bytes = trust.read_git_file(
        COMMIT_MANIFEST_PATH, COMMIT_MANIFEST_REL_PATH, unavailable_cls=_UNAVAILABLE_CLS
    )
    commit_manifest_digest = trust.sha256_windows_manifest(commit_manifest_bytes)
    if commit_manifest_digest != TRUSTED_PHASE5_COMMIT_MANIFEST_SHA256:
        raise Phase5AIntegrityError("Untrusted Phase 5 commit manifest.")
    commit_manifest = trust.parse_json_metadata(
        commit_manifest_bytes, COMMIT_MANIFEST_REL_PATH, integrity_cls=_INTEGRITY_CLS
    )
    artifacts = commit_manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise Phase5AIntegrityError(
            "The Phase 5 commit manifest has no artifacts section."
        )

    # --- run metadata against the commit manifest --------------------------
    run_meta_bytes = trust.read_git_file(
        RUN_METADATA_PATH, RUN_METADATA_REL_PATH, unavailable_cls=_UNAVAILABLE_CLS
    )
    run_meta_digest = trust.sha256_windows_manifest(run_meta_bytes)
    recorded_run_meta = artifacts.get("phase5_run_metadata.json")
    if not isinstance(recorded_run_meta, dict):
        raise Phase5AIntegrityError(
            "The Phase 5 commit manifest does not pin the run metadata."
        )
    if recorded_run_meta.get("sha256") != run_meta_digest:
        raise Phase5AIntegrityError(
            f"Phase 5A metadata integrity verification failed: {RUN_METADATA_REL_PATH}"
        )
    if isinstance(recorded_run_meta.get("size_bytes"), int):
        crlf_size = len(trust.reconstruct_crlf(run_meta_bytes))
        if crlf_size != recorded_run_meta["size_bytes"]:
            raise Phase5AIntegrityError("Phase 5A run metadata size mismatch.")
    run_meta = trust.parse_json_metadata(
        run_meta_bytes, RUN_METADATA_REL_PATH, integrity_cls=_INTEGRITY_CLS
    )

    # --- protocol identity cross-checks ------------------------------------
    if run_meta.get("phase") != "5A" or run_meta.get("stream") != "A":
        raise Phase5AIntegrityError(
            "Phase 5A metadata phase/stream identity is unexpected."
        )
    if not isinstance(run_meta.get("model_fitting"), dict) or \
            run_meta["model_fitting"].get("models_fitted") != 0:
        raise Phase5AIntegrityError(
            "Phase 5A metadata must report models_fitted == 0."
        )
    bootstrap = run_meta.get("bootstrap") or {}
    if not isinstance(bootstrap, dict):
        raise Phase5AIntegrityError("Phase 5A metadata has no bootstrap section.")
    if list(bootstrap.get("runs_evaluated") or []) != list(BOOTSTRAP_RUN_IDS):
        raise Phase5AIntegrityError(
            "Phase 5A bootstrap evaluated runs disagree with the frozen config."
        )
    paired = bootstrap.get("paired_comparison") or {}
    if paired.get("run_a") != PAIRED_RUN_A or paired.get("run_b") != PAIRED_RUN_B:
        raise Phase5AIntegrityError(
            "Phase 5A paired-comparison runs disagree with the frozen config."
        )
    if paired.get("definition") != PAIRED_COMPARISON_DEFINITION:
        raise Phase5AIntegrityError(
            "Phase 5A paired-comparison direction is unexpected."
        )

    # --- Phase 4 input lineage cross-check ---------------------------------
    input_manifest = run_meta.get("input_manifest") or {}
    if not isinstance(input_manifest, dict) or not input_manifest.get("verified"):
        raise Phase5AIntegrityError(
            "Phase 5A input manifest is not verified."
        )
    input_artifacts = input_manifest.get("artifacts") or {}
    if not isinstance(input_artifacts, dict):
        raise Phase5AIntegrityError(
            "Phase 5A input manifest has no artifacts section."
        )
    lineage_checks = (
        ("phase4_evaluation_dataset.csv", PHASE4_EVAL_DATASET_SHA256),
        ("phase4_metrics.csv", PHASE4_METRICS_SHA256),
        ("phase4_run_metadata.json", PHASE4_RUN_METADATA_SHA256),
    )
    for name, expected_sha in lineage_checks:
        entry = input_artifacts.get(name)
        if not isinstance(entry, dict) or entry.get("sha256") != expected_sha:
            raise Phase5AIntegrityError(
                f"Phase 5A input lineage verification failed for {name!r}."
            )

    sample = run_meta.get("sample") or {}
    if not isinstance(sample, dict):
        raise Phase5AIntegrityError("Phase 5A metadata has no sample section.")

    # --- assemble commit-manifest sha256 lookup for Layer B ----------------
    manifest_sha256: dict[str, str] = {}
    manifest_size: dict[str, int] = {}
    for name, info in artifacts.items():
        if isinstance(info, dict) and isinstance(info.get("sha256"), str):
            manifest_sha256[name] = info["sha256"]
            if isinstance(info.get("size_bytes"), int):
                manifest_size[name] = info["size_bytes"]

    return {
        "protocol": {
            "phase": run_meta["phase"],
            "stream": run_meta["stream"],
            "layer": run_meta.get("layer", ""),
            "run_mode": run_meta.get("run_mode", ""),
            "models_fitted": 0,
            "created_utc": run_meta.get("created_utc", ""),
            "environment": dict(run_meta.get("environment") or {}),
            "model_fitting": dict(run_meta.get("model_fitting") or {}),
            "analytical_conventions": dict(run_meta.get("analytical_conventions") or {}),
        },
        "bootstrap_protocol": {
            "n_replicates": int(bootstrap.get("n_replicates", BOOTSTRAP_REPLICATES)),
            "ci_level": float(bootstrap.get("ci_level", BOOTSTRAP_CI_LEVEL)),
            "ci_method": str(bootstrap.get("ci_method", BOOTSTRAP_CI_METHOD)),
            "seed": int(bootstrap.get("seed", BOOTSTRAP_SEED)),
            "rng": str(bootstrap.get("rng", "")),
            "resampling": str(bootstrap.get("resampling", "")),
            "runs_evaluated": list(bootstrap.get("runs_evaluated") or []),
            "paired_comparison": dict(paired),
            "threshold_policy": str(bootstrap.get("threshold_policy", "")),
        },
        "selection_caveat": str(run_meta.get("selection_caveat", "")),
        "sample": {
            "sample_size": int(sample["sample_size"]),
            "fraud_count": int(sample["fraud_count"]),
            "fraud_prevalence": float(sample["fraud_prevalence"]),
        },
        "multi_threshold_percents": list(config_constants.get(
            "PHASE5_MULTI_THRESHOLD_PERCENTS", list(MULTI_THRESHOLD_PERCENTS)
        )),
        "canonical_threshold_pct": float(config_constants.get(
            "PHASE5_CANONICAL_THRESHOLD_PCT", CANONICAL_THRESHOLD_PCT
        )),
        "config_sha256": config_digest,
        "analysis_sha256": analysis_digest,
        "run_metadata_sha256": run_meta_digest,
        "commit_manifest_sha256": commit_manifest_digest,
        "manifest_sha256": manifest_sha256,
        "manifest_size": manifest_size,
        "_verified_digests": {
            CONFIG_REL_PATH: config_digest,
            PHASE5_ANALYSIS_REL_PATH: analysis_digest,
            RUN_METADATA_REL_PATH: run_meta_digest,
            COMMIT_MANIFEST_REL_PATH: commit_manifest_digest,
        },
    }


# ---------------------------------------------------------------------------
# Layer A cache (PR-08/09 contract)
# ---------------------------------------------------------------------------

_LAYER_A_CACHE: dict[str, Any] | None = None


def _invalidate_layer_a() -> None:
    global _LAYER_A_CACHE
    _LAYER_A_CACHE = None


def _load_protocol() -> dict[str, Any]:
    """Verify current trust anchors on EVERY request, including cache hits."""
    global _LAYER_A_CACHE
    try:
        # The trust-chain is rechecked independently of the cached digest map.
        # This includes the frozen manifest, pinned Phase 5 manifest, metadata,
        # and Phase 4 input lineage. Parsing only the small Git metadata is
        # acceptable here; no DVC data is loaded in this function.
        current = _load_layer_a()
    except (Phase5AIntegrityError, Phase5AUnavailableError):
        _LAYER_A_CACHE = None
        _invalidate_layer_b()
        raise
    if (_LAYER_A_CACHE is not None and
            current["_verified_digests"] == _LAYER_A_CACHE["_verified_digests"]):
        return _LAYER_A_CACHE
    _LAYER_A_CACHE = current
    _invalidate_layer_b()
    return current


# ---------------------------------------------------------------------------
# Layer B: independent per-family loaders
# ---------------------------------------------------------------------------

#: Each family has its own cache: family -> {payload, pointer_sha256, payload_md5}.
_LAYER_B_CACHES: dict[str, dict[str, Any]] = {}


def _invalidate_layer_b(family: str | None = None) -> None:
    if family is None:
        _LAYER_B_CACHES.clear()
    else:
        _LAYER_B_CACHES.pop(family, None)


def _family_spec(family: str) -> tuple[str, str, str, str]:
    for spec in _FAMILY_SPECS:
        if spec[0] == family:
            return spec
    raise Phase5AIntegrityError(f"Unknown Phase 5A artifact family {family!r}.")


def _load_family_raw(family: str) -> dict[str, Any]:
    """Fully verify pointer, payload and trusted metadata before cache reuse.

    Checks are performed on the same payload snapshot; the cached object
    contains only parsed rows, not cached authorization to trust stale bytes.
    """
    protocol = _load_protocol()
    _, payload_rel, pointer_rel, _role = _family_spec(family)
    pointer_bytes = trust.read_git_file(
        REPO_ROOT / pointer_rel, pointer_rel, unavailable_cls=_UNAVAILABLE_CLS
    )
    pointer = trust.parse_dvc_pointer(
        pointer_bytes, pointer_rel, integrity_cls=_INTEGRITY_CLS
    )
    expected_name = payload_rel.rsplit("/", 1)[-1]
    if pointer["path"] != expected_name:
        _invalidate_layer_b(family)
        raise Phase5AIntegrityError("The DVC pointer targets an unexpected output.")
    manifest_sha = protocol["manifest_sha256"].get(expected_name)
    manifest_size = protocol["manifest_size"].get(expected_name)
    if not isinstance(manifest_sha, str) or not isinstance(manifest_size, int):
        _invalidate_layer_b(family)
        raise Phase5AIntegrityError("The trusted manifest does not pin the payload.")
    try:
        payload_bytes = (REPO_ROOT / payload_rel).read_bytes()
    except (FileNotFoundError, OSError) as exc:
        _invalidate_layer_b(family)
        raise Phase5AUnavailableError("The Phase 5A payload is missing.") from exc
    try:
        # Validate BOTH recorded identities against a consistent candidate
        # representation, not independently against incompatible candidates.
        verified_bytes = trust.verify_payload_identity(
            payload_bytes, pointer, manifest_sha, manifest_size, payload_rel,
            integrity_cls=_INTEGRITY_CLS,
        )
    except Phase5AIntegrityError:
        _invalidate_layer_b(family)
        raise
    signature = (
        hashlib.sha256(pointer_bytes).hexdigest(),
        hashlib.sha256(verified_bytes).hexdigest(),
        protocol["commit_manifest_sha256"],
    )
    cached = _LAYER_B_CACHES.get(family)
    if cached is not None and cached["signature"] == signature:
        return cached
    rows = trust.parse_csv_rows(
        verified_bytes, payload_rel, integrity_cls=_INTEGRITY_CLS
    )
    entry = {
        "family": family,
        "payload_rel": payload_rel,
        "pointer_rel": pointer_rel,
        "pointer_sha256": signature[0],
        "payload_md5": trust.md5_raw(verified_bytes),
        "payload_sha256": manifest_sha,
        "signature": signature,
        "rows": rows,
    }
    _LAYER_B_CACHES[family] = entry
    return entry


# ---------------------------------------------------------------------------
# Family-specific schema validators
# ---------------------------------------------------------------------------


def _validate_run_id(run_id: str) -> None:
    if not isinstance(run_id, str) or not _RUN_ID_RE.fullmatch(run_id):
        raise Phase5AIntegrityError(
            f"Unexpected Phase 5A run identifier {run_id!r}."
        )


def _validate_bootstrap_rows(rows: list[dict[str, str]], rel: str) -> list[dict[str, str]]:
    trust.require_columns(rows, BOOTSTRAP_METRICS_COLUMNS, rel, integrity_cls=_INTEGRITY_CLS)
    if len(rows) != len(BOOTSTRAP_RUN_IDS) * len(BOOTSTRAP_METRIC_NAMES):
        raise Phase5AIntegrityError(
            f"Phase 5A bootstrap metrics row count is unexpected ({len(rows)})."
        )
    seen: set[tuple[str, str]] = set()
    for row in rows:
        rid = (row.get("run_id") or "").strip()
        metric = (row.get("metric") or "").strip()
        _validate_run_id(rid)
        if rid not in BOOTSTRAP_RUN_IDS:
            raise Phase5AIntegrityError(
                f"Phase 5A bootstrap metrics contain unexpected run {rid!r}."
            )
        if metric not in BOOTSTRAP_METRIC_NAMES:
            raise Phase5AIntegrityError(
                f"Phase 5A bootstrap metrics contain unexpected metric {metric!r}."
            )
        key = (rid, metric)
        if key in seen:
            raise Phase5AIntegrityError(
                f"Phase 5A bootstrap metrics contain duplicate ({rid}, {metric})."
            )
        seen.add(key)
        lower = trust.coerce_float(row["ci_lower"], integrity_cls=_INTEGRITY_CLS)
        upper = trust.coerce_float(row["ci_upper"], integrity_cls=_INTEGRITY_CLS)
        if lower > upper:
            raise Phase5AIntegrityError(
                f"Phase 5A bootstrap CI lower > upper for ({rid}, {metric})."
            )
        if trust.coerce_int(row["n_replicates"], integrity_cls=_INTEGRITY_CLS) != BOOTSTRAP_REPLICATES:
            raise Phase5AIntegrityError(
                f"Phase 5A bootstrap n_replicates is not {BOOTSTRAP_REPLICATES}."
            )
    return rows


def _validate_paired_rows(rows: list[dict[str, str]], rel: str) -> list[dict[str, str]]:
    trust.require_columns(rows, PAIRED_DIFFERENCES_COLUMNS, rel, integrity_cls=_INTEGRITY_CLS)
    if len(rows) != len(BOOTSTRAP_METRIC_NAMES):
        raise Phase5AIntegrityError(
            f"Phase 5A paired-differences row count is unexpected ({len(rows)})."
        )
    for row in rows:
        if (row.get("run_a") or "").strip() != PAIRED_RUN_A:
            raise Phase5AIntegrityError("Phase 5A paired run_a is unexpected.")
        if (row.get("run_b") or "").strip() != PAIRED_RUN_B:
            raise Phase5AIntegrityError("Phase 5A paired run_b is unexpected.")
        if (row.get("comparison") or "").strip() != PAIRED_COMPARISON_DEFINITION:
            raise Phase5AIntegrityError("Phase 5A paired comparison direction is unexpected.")
        metric = (row.get("metric") or "").strip()
        if metric not in BOOTSTRAP_METRIC_NAMES:
            raise Phase5AIntegrityError(
                f"Phase 5A paired metric {metric!r} is unexpected."
            )
        lower = trust.coerce_float(row["ci_lower"], integrity_cls=_INTEGRITY_CLS)
        upper = trust.coerce_float(row["ci_upper"], integrity_cls=_INTEGRITY_CLS)
        if lower > upper:
            raise Phase5AIntegrityError("Phase 5A paired CI lower > upper.")
    return rows


def _validate_matrix_rows(rows: list[dict[str, str]], rel: str, kind: str) -> None:
    """Validate a 10×10 pairwise matrix (Spearman or Jaccard)."""
    if len(rows) != len(CANONICAL_RUN_IDS):
        raise Phase5AIntegrityError(
            f"Phase 5A {kind} matrix row count is not {len(CANONICAL_RUN_IDS)}."
        )
    for row in rows:
        rid = (row.get("run_id") or "").strip()
        _validate_run_id(rid)
        for col in CANONICAL_RUN_IDS:
            if col not in row:
                raise Phase5AIntegrityError(
                    f"Phase 5A {kind} matrix is missing column {col!r}."
                )
            value = trust.coerce_float(row[col], integrity_cls=_INTEGRITY_CLS)
            lo, hi = (-1.0, 1.0) if kind == "spearman" else (0.0, 1.0)
            if value < lo or value > hi:
                raise Phase5AIntegrityError(
                    f"Phase 5A {kind} matrix value out of bounds for {col!r}."
                )
    # Symmetry + diagonal check.
    by_id = {(r.get("run_id") or "").strip(): r for r in rows}
    for a in CANONICAL_RUN_IDS:
        for b in CANONICAL_RUN_IDS:
            va = trust.coerce_float(by_id[a][a] if a == b else by_id[a][b],
                                    integrity_cls=_INTEGRITY_CLS)
            vb = trust.coerce_float(by_id[b][a] if a == b else by_id[b][a],
                                    integrity_cls=_INTEGRITY_CLS)
            if a == b:
                if abs(va - 1.0) > 1e-9:
                    raise Phase5AIntegrityError(
                        f"Phase 5A {kind} diagonal for {a!r} is not 1.0."
                    )
            elif abs(va - vb) > 1e-9:
                raise Phase5AIntegrityError(
                    f"Phase 5A {kind} matrix is not symmetric for ({a}, {b})."
                )


def _validate_multithreshold_rows(rows: list[dict[str, str]], rel: str) -> list[dict[str, str]]:
    trust.require_columns(rows, MULTITHRESHOLD_AGREEMENT_COLUMNS, rel, integrity_cls=_INTEGRITY_CLS)
    if len(rows) != len(MULTI_THRESHOLD_PERCENTS):
        raise Phase5AIntegrityError(
            f"Phase 5A multithreshold row count is unexpected ({len(rows)})."
        )
    seen: set[float] = set()
    for row in rows:
        pct = trust.coerce_float(row["threshold_pct"], integrity_cls=_INTEGRITY_CLS)
        if pct not in MULTI_THRESHOLD_PERCENTS:
            raise Phase5AIntegrityError(
                f"Phase 5A multithreshold pct {pct} is not approved."
            )
        if pct in seen:
            raise Phase5AIntegrityError(
                f"Phase 5A multithreshold pct {pct} is duplicated."
            )
        seen.add(pct)
        source = (row.get("selection_source") or "").strip().lower()
        if source not in {"saved_canonical", "derived_topk"}:
            raise Phase5AIntegrityError(
                f"Phase 5A multithreshold selection_source {source!r} is unexpected."
            )
        trust.coerce_int(row["k_nominal"], integrity_cls=_INTEGRITY_CLS)
        trust.coerce_int(row["n_methods"], integrity_cls=_INTEGRITY_CLS)
        trust.coerce_int(row["observation_count"], integrity_cls=_INTEGRITY_CLS)
    return rows


def _validate_hypergeometric_rows(rows: list[dict[str, str]], rel: str) -> list[dict[str, str]]:
    trust.require_columns(rows, HYPERGEOMETRIC_OVERLAP_COLUMNS, rel, integrity_cls=_INTEGRITY_CLS)
    if len(rows) != 1:
        raise Phase5AIntegrityError(
            f"Phase 5A hypergeometric overlap must have exactly one row ({len(rows)})."
        )
    row = rows[0]
    if (row.get("run_a") or "").strip() != OVERLAP_RUN_A:
        raise Phase5AIntegrityError("Phase 5A hypergeometric run_a is unexpected.")
    if (row.get("run_b") or "").strip() != OVERLAP_RUN_B:
        raise Phase5AIntegrityError("Phase 5A hypergeometric run_b is unexpected.")
    if abs(trust.coerce_float(row["threshold_pct"], integrity_cls=_INTEGRITY_CLS) - CANONICAL_THRESHOLD_PCT) > 1e-9:
        raise Phase5AIntegrityError("Phase 5A hypergeometric threshold_pct is unexpected.")
    if trust.coerce_int(row["n_observations"], integrity_cls=_INTEGRITY_CLS) != SAMPLE_SIZE:
        raise Phase5AIntegrityError("Phase 5A hypergeometric n_observations mismatch.")
    return rows


def _validate_groups_rows(rows: list[dict[str, str]], rel: str) -> list[dict[str, str]]:
    trust.require_columns(rows, AGREEMENT_GROUPS_COLUMNS, rel, integrity_cls=_INTEGRITY_CLS)
    if len(rows) != len(AGREEMENT_GROUP_LABELS):
        raise Phase5AIntegrityError(
            f"Phase 5A agreement groups must have {len(AGREEMENT_GROUP_LABELS)} rows ({len(rows)})."
        )
    seen: set[str] = set()
    for row in rows:
        if (row.get("run_a") or "").strip() != OVERLAP_RUN_A:
            raise Phase5AIntegrityError("Phase 5A groups run_a is unexpected.")
        if (row.get("run_b") or "").strip() != OVERLAP_RUN_B:
            raise Phase5AIntegrityError("Phase 5A groups run_b is unexpected.")
        group = (row.get("group") or "").strip()
        if group not in AGREEMENT_GROUP_LABELS:
            raise Phase5AIntegrityError(
                f"Phase 5A groups label {group!r} is unexpected."
            )
        if group in seen:
            raise Phase5AIntegrityError(
                f"Phase 5A groups label {group!r} is duplicated."
            )
        seen.add(group)
    # Conservation: total observation_count == sample_size; total fraud_count == fraud_count.
    total_obs = sum(
        trust.coerce_int(r["observation_count"], integrity_cls=_INTEGRITY_CLS) for r in rows
    )
    total_fraud = sum(
        trust.coerce_int(r["fraud_count"], integrity_cls=_INTEGRITY_CLS) for r in rows
    )
    total_recall = sum(
        trust.coerce_float(r["recall_contribution"], integrity_cls=_INTEGRITY_CLS) for r in rows
    )
    if total_obs != SAMPLE_SIZE:
        raise Phase5AIntegrityError(
            f"Phase 5A groups observation_count does not conserve {SAMPLE_SIZE} ({total_obs})."
        )
    if total_fraud != FRAUD_COUNT:
        raise Phase5AIntegrityError(
            f"Phase 5A groups fraud_count does not conserve {FRAUD_COUNT} ({total_fraud})."
        )
    if abs(total_recall - 1.0) > 1e-6:
        raise Phase5AIntegrityError(
            f"Phase 5A groups recall_contribution does not sum to 1.0 ({total_recall})."
        )
    return rows


def _validate_discovery_rows(rows: list[dict[str, str]], rel: str) -> list[dict[str, str]]:
    trust.require_columns(rows, FRAUD_DISCOVERY_CURVE_COLUMNS, rel, integrity_cls=_INTEGRITY_CLS)
    seen: set[tuple[str, Any]] = set()
    for row in rows:
        rid = (row.get("run_id") or "").strip()
        _validate_run_id(rid)
        budget = (row.get("budget") or "").strip()
        try:
            budget_key: Any = int(budget)
        except ValueError:
            budget_key = budget
        key = (rid, budget_key)
        if key in seen:
            raise Phase5AIntegrityError(
                f"Phase 5A discovery curve duplicate ({rid}, {budget})."
            )
        seen.add(key)
    return rows


_FAMILY_VALIDATORS: dict[str, Any] = {
    "bootstrap": lambda rows, rel: _validate_bootstrap_rows(rows, rel),
    "paired": lambda rows, rel: _validate_paired_rows(rows, rel),
    "spearman": lambda rows, rel: _validate_matrix_rows(rows, rel, "spearman"),
    "jaccard": lambda rows, rel: _validate_matrix_rows(rows, rel, "jaccard"),
    "multithreshold": lambda rows, rel: _validate_multithreshold_rows(rows, rel),
    "hypergeometric": lambda rows, rel: _validate_hypergeometric_rows(rows, rel),
    "groups": lambda rows, rel: _validate_groups_rows(rows, rel),
    "discovery": lambda rows, rel: _validate_discovery_rows(rows, rel),
}


def _load_family(family: str) -> dict[str, Any]:
    """Load, verify, validate and cache one family's payload."""
    entry = _load_family_raw(family)
    validator = _FAMILY_VALIDATORS.get(family)
    if validator is not None:
        validator(entry["rows"], entry["payload_rel"])
    return entry


# ---------------------------------------------------------------------------
# Availability probe (never raises)
# ---------------------------------------------------------------------------


def _family_availability(family: str) -> dict[str, Any]:
    """Report available only after the full admitted source validation."""
    try:
        _load_family(family)
        return {"available": True, "reason": None, "detail": None}
    except Phase5AIntegrityError:
        return {"available": False, "reason": "integrity_failed",
                "detail": "The source artifact failed verified admission."}
    except Phase5AUnavailableError:
        return {"available": False, "reason": "artifact_missing",
                "detail": "The DVC-backed payload has not been provisioned."}


def _all_availability() -> dict[str, dict[str, Any]]:
    return {fam: _family_availability(fam) for fam, *_ in _FAMILY_SPECS}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class Phase5AEvidenceService:
    """Read-only service over the frozen Phase 5A evidence (PR-10).

    Layer A methods (``get_protocol``) always work on a clean checkout.
    Layer B methods additionally require the admitted DVC payloads to be
    present and verified; otherwise they raise sanitized unavailable /
    integrity errors which the API layer maps to 503 with a machine-readable
    reason. The service performs no writes, no model fitting, no pickle
    deserialization and holds no database state.
    """

    source_id: str = PHASE5A_SOURCE_ID
    dataset_id: str = DATASET_ID
    limitations: tuple[str, ...] = LIMITATIONS

    def availability(self) -> dict[str, dict[str, Any]]:
        """Return per-family availability of the DVC-backed layers.

        Never raises: catalog routes report availability rather than failing
        globally when a payload is absent (FR-05 / AT-10).
        """
        return _all_availability()

    def get_protocol(self) -> dict[str, Any]:
        """Return the verified Phase 5A protocol metadata (Layer A)."""
        protocol = _load_protocol()
        return {
            "source_id": self.source_id,
            "dataset_id": self.dataset_id,
            "phase": protocol["protocol"]["phase"],
            "stream": protocol["protocol"]["stream"],
            "layer": protocol["protocol"]["layer"],
            "run_mode": protocol["protocol"]["run_mode"],
            "models_fitted": 0,
            "created_utc": protocol["protocol"]["created_utc"],
            "environment": protocol["protocol"]["environment"],
            "model_fitting": protocol["protocol"]["model_fitting"],
            "analytical_conventions": protocol["protocol"]["analytical_conventions"],
            "bootstrap_protocol": protocol["bootstrap_protocol"],
            "selection_caveat": protocol["selection_caveat"],
            "sample": protocol["sample"],
            "multi_threshold_percents": protocol["multi_threshold_percents"],
            "canonical_threshold_pct": protocol["canonical_threshold_pct"],
            "evaluated_run_ids": list(BOOTSTRAP_RUN_IDS),
            "paired_comparison": {
                "definition": PAIRED_COMPARISON_DEFINITION,
                "run_a": PAIRED_RUN_A,
                "run_b": PAIRED_RUN_B,
            },
            "overlap_runs": {"run_a": OVERLAP_RUN_A, "run_b": OVERLAP_RUN_B},
            "capabilities": _all_availability(),
            "provenance": {
                "config": {
                    "path": CONFIG_REL_PATH,
                    "sha256": protocol["config_sha256"],
                    "digest_algorithm": trust.DIGEST_ALGORITHM,
                    "canonicalization": trust.FROZEN_CHECKER_CANONICALIZATION,
                },
                "phase5_analysis": {
                    "path": PHASE5_ANALYSIS_REL_PATH,
                    "sha256": protocol["analysis_sha256"],
                    "digest_algorithm": trust.DIGEST_ALGORITHM,
                    "canonicalization": trust.FROZEN_CHECKER_CANONICALIZATION,
                },
                "run_metadata": {
                    "path": RUN_METADATA_REL_PATH,
                    "sha256": protocol["run_metadata_sha256"],
                    "digest_algorithm": trust.DIGEST_ALGORITHM,
                    "canonicalization": trust.WINDOWS_MANIFEST_CANONICALIZATION,
                },
                "commit_manifest": {
                    "path": COMMIT_MANIFEST_REL_PATH,
                    "sha256": protocol["commit_manifest_sha256"],
                    "digest_algorithm": trust.DIGEST_ALGORITHM,
                    "canonicalization": trust.WINDOWS_MANIFEST_CANONICALIZATION,
                },
                "phase4_lineage": {
                    "evaluation_dataset_sha256": PHASE4_EVAL_DATASET_SHA256,
                    "metrics_sha256": PHASE4_METRICS_SHA256,
                    "run_metadata_sha256": PHASE4_RUN_METADATA_SHA256,
                    "verified": True,
                    "note": (
                        "Phase 4 input SHA-256 values recorded in the Phase 5 "
                        "metadata match the PR-09 admitted Phase 4 identity."
                    ),
                },
            },
            "limitations": list(self.limitations),
        }

    def get_bootstrap(self) -> dict[str, Any]:
        """Return the saved bootstrap uncertainty intervals (Layer B)."""
        protocol = _load_protocol()
        entry = _load_family("bootstrap")
        rows = _validate_bootstrap_rows(entry["rows"], entry["payload_rel"])
        items: list[dict[str, Any]] = []
        for row in rows:
            items.append({
                "run_id": (row["run_id"] or "").strip(),
                "metric": (row["metric"] or "").strip(),
                "point_estimate": trust.coerce_float(row["point_estimate"], integrity_cls=_INTEGRITY_CLS),
                "bootstrap_mean": trust.coerce_float(row["bootstrap_mean"], integrity_cls=_INTEGRITY_CLS),
                "bootstrap_std": trust.coerce_float(row["bootstrap_std"], integrity_cls=_INTEGRITY_CLS),
                "ci_lower": trust.coerce_float(row["ci_lower"], integrity_cls=_INTEGRITY_CLS),
                "ci_upper": trust.coerce_float(row["ci_upper"], integrity_cls=_INTEGRITY_CLS),
                "n_replicates": trust.coerce_int(row["n_replicates"], integrity_cls=_INTEGRITY_CLS),
            })
        return {
            "source_id": self.source_id,
            "dataset_id": self.dataset_id,
            "bootstrap_protocol": protocol["bootstrap_protocol"],
            "selection_caveat": protocol["selection_caveat"],
            "metrics": items,
            "provenance": self._family_provenance(entry),
            "limitations": list(self.limitations),
            "is_precomputed": True,
            "is_live_prediction": False,
        }

    def get_paired_differences(self) -> dict[str, Any]:
        """Return the saved paired bootstrap differences (Layer B)."""
        protocol = _load_protocol()
        entry = _load_family("paired")
        rows = _validate_paired_rows(entry["rows"], entry["payload_rel"])
        items: list[dict[str, Any]] = []
        for row in rows:
            items.append({
                "comparison": (row["comparison"] or "").strip(),
                "run_a": (row["run_a"] or "").strip(),
                "run_b": (row["run_b"] or "").strip(),
                "metric": (row["metric"] or "").strip(),
                "point_estimate": trust.coerce_float(row["point_estimate"], integrity_cls=_INTEGRITY_CLS),
                "bootstrap_mean": trust.coerce_float(row["bootstrap_mean"], integrity_cls=_INTEGRITY_CLS),
                "bootstrap_std": trust.coerce_float(row["bootstrap_std"], integrity_cls=_INTEGRITY_CLS),
                "ci_lower": trust.coerce_float(row["ci_lower"], integrity_cls=_INTEGRITY_CLS),
                "ci_upper": trust.coerce_float(row["ci_upper"], integrity_cls=_INTEGRITY_CLS),
                "n_replicates": trust.coerce_int(row["n_replicates"], integrity_cls=_INTEGRITY_CLS),
            })
        return {
            "source_id": self.source_id,
            "dataset_id": self.dataset_id,
            "direction": PAIRED_COMPARISON_DEFINITION,
            "run_a": PAIRED_RUN_A,
            "run_b": PAIRED_RUN_B,
            "selection_caveat": protocol["selection_caveat"],
            "differences": items,
            "provenance": self._family_provenance(entry),
            "limitations": list(self.limitations),
            "is_precomputed": True,
            "is_live_prediction": False,
        }

    def get_agreement_matrix(self, kind: str) -> dict[str, Any]:
        """Return a saved 10×10 agreement matrix (Layer B).

        ``kind`` is ``spearman`` or ``jaccard``.
        """
        if kind not in {"spearman", "jaccard"}:
            raise SourceNotFoundError(
                f"No Phase 5A agreement matrix is registered under {kind!r}."
            )
        protocol = _load_protocol()
        entry = _load_family(kind)
        _validate_matrix_rows(entry["rows"], entry["payload_rel"], kind)
        run_labels = list(CANONICAL_RUN_IDS)
        matrix: list[dict[str, Any]] = []
        for row in entry["rows"]:
            rid = (row.get("run_id") or "").strip()
            cells = {
                col: trust.coerce_float(row[col], integrity_cls=_INTEGRITY_CLS)
                for col in run_labels
            }
            matrix.append({"run_id": rid, "values": cells})
        bounds = {"min": -1.0, "max": 1.0} if kind == "spearman" else {"min": 0.0, "max": 1.0}
        return {
            "source_id": self.source_id,
            "dataset_id": self.dataset_id,
            "kind": kind,
            "run_labels": run_labels,
            "matrix": matrix,
            "bounds": bounds,
            "highlighted_pair": {"run_a": PAIRED_RUN_A, "run_b": PAIRED_RUN_B},
            "selection_caveat": protocol["selection_caveat"],
            "definition": (
                "Pearson correlation of tie-corrected average ranks of "
                "anomaly_score vectors (scipy.stats.spearmanr definition)."
                if kind == "spearman"
                else "Intersection over union of the saved Phase 3 1% flags."
            ),
            "provenance": self._family_provenance(entry),
            "limitations": list(self.limitations),
            "is_precomputed": True,
            "is_live_prediction": False,
        }

    def get_hypergeometric(self) -> dict[str, Any]:
        """Return the saved hypergeometric overlap result (Layer B)."""
        protocol = _load_protocol()
        entry = _load_family("hypergeometric")
        rows = _validate_hypergeometric_rows(entry["rows"], entry["payload_rel"])
        row = rows[0]
        return {
            "source_id": self.source_id,
            "dataset_id": self.dataset_id,
            "run_a": (row["run_a"] or "").strip(),
            "run_b": (row["run_b"] or "").strip(),
            "threshold_pct": trust.coerce_float(row["threshold_pct"], integrity_cls=_INTEGRITY_CLS),
            "n_observations": trust.coerce_int(row["n_observations"], integrity_cls=_INTEGRITY_CLS),
            "run_a_flagged": trust.coerce_int(row["run_a_flagged"], integrity_cls=_INTEGRITY_CLS),
            "run_b_flagged": trust.coerce_int(row["run_b_flagged"], integrity_cls=_INTEGRITY_CLS),
            "observed_intersection": trust.coerce_int(row["observed_intersection"], integrity_cls=_INTEGRITY_CLS),
            "union_size": trust.coerce_int(row["union_size"], integrity_cls=_INTEGRITY_CLS),
            "expected_intersection": trust.coerce_float(row["expected_intersection"], integrity_cls=_INTEGRITY_CLS),
            "enrichment_observed_over_expected": trust.coerce_float(row["enrichment_observed_over_expected"], integrity_cls=_INTEGRITY_CLS),
            "survival_upper_tail": trust.coerce_float(row["survival_upper_tail"], integrity_cls=_INTEGRITY_CLS),
            "log_survival": trust.coerce_float(row["log_survival"], integrity_cls=_INTEGRITY_CLS),
            "log10_survival": trust.coerce_float(row["log10_survival"], integrity_cls=_INTEGRITY_CLS),
            "null_model": (row["null_model"] or "").strip(),
            "selection_caveat": protocol["selection_caveat"],
            "provenance": self._family_provenance(entry),
            "limitations": list(self.limitations),
            "is_precomputed": True,
            "is_live_prediction": False,
        }

    def get_groups(self) -> dict[str, Any]:
        """Return the saved four-way agreement groups (Layer B)."""
        protocol = _load_protocol()
        entry = _load_family("groups")
        rows = _validate_groups_rows(entry["rows"], entry["payload_rel"])
        groups: list[dict[str, Any]] = []
        for row in rows:
            groups.append({
                "group": (row["group"] or "").strip(),
                "observation_count": trust.coerce_int(row["observation_count"], integrity_cls=_INTEGRITY_CLS),
                "fraud_count": trust.coerce_int(row["fraud_count"], integrity_cls=_INTEGRITY_CLS),
                "non_fraud_count": trust.coerce_int(row["non_fraud_count"], integrity_cls=_INTEGRITY_CLS),
                "fraud_proportion": trust.coerce_float(row["fraud_proportion"], integrity_cls=_INTEGRITY_CLS),
                "recall_contribution": trust.coerce_float(row["recall_contribution"], integrity_cls=_INTEGRITY_CLS),
            })
        return {
            "source_id": self.source_id,
            "dataset_id": self.dataset_id,
            "run_a": OVERLAP_RUN_A,
            "run_b": OVERLAP_RUN_B,
            "threshold_pct": CANONICAL_THRESHOLD_PCT,
            "groups": groups,
            "conservation": {
                "total_observations": SAMPLE_SIZE,
                "total_fraud_count": FRAUD_COUNT,
                "total_recall_contribution": sum(g["recall_contribution"] for g in groups),
            },
            "selection_caveat": protocol["selection_caveat"],
            "provenance": self._family_provenance(entry),
            "limitations": list(self.limitations),
            "is_precomputed": True,
            "is_live_prediction": False,
        }

    def get_policies(self) -> dict[str, Any]:
        """Do not synthesize policy-level precision or recall at request time.

        The approved Phase 5A agreement-groups artifact contains saved
        disjoint group counts and their saved proportions. Serve those direct
        records via get_groups()/review-policies. Derived four-policy summary
        metrics require an independently published, verified source artifact.
        """
        raise Phase5AUnavailableError(
            "Four-policy aggregate metrics have not been separately admitted."
        )

    def get_thresholds(self) -> dict[str, Any]:
        """Return the saved multi-threshold agreement (Layer B)."""
        protocol = _load_protocol()
        entry = _load_family("multithreshold")
        rows = _validate_multithreshold_rows(entry["rows"], entry["payload_rel"])
        items: list[dict[str, Any]] = []
        for row in rows:
            pct = trust.coerce_float(row["threshold_pct"], integrity_cls=_INTEGRITY_CLS)
            items.append({
                "threshold_pct": pct,
                "k_nominal": trust.coerce_int(row["k_nominal"], integrity_cls=_INTEGRITY_CLS),
                "selection_source": (row["selection_source"] or "").strip(),
                "is_canonical": abs(pct - CANONICAL_THRESHOLD_PCT) < 1e-9,
                "n_methods": trust.coerce_int(row["n_methods"], integrity_cls=_INTEGRITY_CLS),
                "observation_count": trust.coerce_int(row["observation_count"], integrity_cls=_INTEGRITY_CLS),
            })
        return {
            "source_id": self.source_id,
            "dataset_id": self.dataset_id,
            "canonical_threshold_pct": CANONICAL_THRESHOLD_PCT,
            "approved_thresholds": list(MULTI_THRESHOLD_PERCENTS),
            "thresholds": items,
            "selection_caveat": protocol["selection_caveat"],
            "provenance": self._family_provenance(entry),
            "limitations": list(self.limitations),
            "is_precomputed": True,
            "is_live_prediction": False,
        }

    def get_discovery_curve(
        self, run_id: str, *, limit: int = DISCOVERY_DEFAULT_LIMIT, offset: int = 0
    ) -> dict[str, Any]:
        """Return a bounded page of the saved discovery curve (Layer B).

        Strictly bounded: ``limit`` is clamped to [1, 200], ``offset`` >= 0.
        Rows are sorted by ``(run_id, budget)`` for stable paging. The
        ``run_id`` is validated against the fixed allowlist BEFORE the
        payload is loaded, so an unknown run returns 404 (not 503).
        """
        if not isinstance(run_id, str) or not _RUN_ID_RE.fullmatch(run_id):
            raise SourceNotFoundError(
                f"No canonical Phase 5A run is registered under {run_id!r}."
            )
        protocol = _load_protocol()
        entry = _load_family("discovery")
        rows = _validate_discovery_rows(entry["rows"], entry["payload_rel"])
        bounded_limit = max(1, min(int(limit), DISCOVERY_MAX_LIMIT))
        bounded_offset = max(0, int(offset))
        matching = [r for r in rows if (r.get("run_id") or "").strip() == run_id]
        matching.sort(key=lambda r: (
            (r.get("run_id") or "").strip(),
            _coerce_sortable_budget(r.get("budget")),
        ))
        total = len(matching)
        page = matching[bounded_offset: bounded_offset + bounded_limit]
        items: list[dict[str, Any]] = []
        for row in page:
            items.append({
                "run_id": (row["run_id"] or "").strip(),
                "budget": _coerce_sortable_budget(row.get("budget")),
                "fraud_found": trust.coerce_int(row["fraud_found"], integrity_cls=_INTEGRITY_CLS),
                "precision": trust.coerce_float(row["precision"], integrity_cls=_INTEGRITY_CLS),
                "recall": trust.coerce_float(row["recall"], integrity_cls=_INTEGRITY_CLS),
            })
        return {
            "source_id": self.source_id,
            "dataset_id": self.dataset_id,
            "run_id": run_id,
            "offset": bounded_offset,
            "limit": bounded_limit,
            "total": total,
            "has_more": (bounded_offset + bounded_limit) < total,
            "rows": items,
            "selection_caveat": protocol["selection_caveat"],
            "provenance": self._family_provenance(entry),
            "limitations": list(self.limitations),
            "is_precomputed": True,
            "is_live_prediction": False,
        }

    def _family_provenance(self, entry: dict[str, Any]) -> dict[str, Any]:
        return {
            "artifact_path": entry["payload_rel"],
            "artifact_md5": entry["payload_md5"],
            "artifact_sha256": entry["payload_sha256"],
            "digest_algorithm": trust.DIGEST_ALGORITHM,
            "verification": (
                "DVC pointer md5 + size verified against the payload bytes; "
                "SHA-256 verified against the Phase 5 commit manifest; "
                "schema validated against the frozen phase5_analysis.py "
                "column contract."
            ),
        }


def _coerce_sortable_budget(value: str | None) -> Any:
    """Return an int budget when possible, else the trimmed string (stable sort)."""
    if value is None:
        return 0
    text = value.strip()
    try:
        return int(text)
    except ValueError:
        return text


#: Module-level singleton; construction is cheap (no file I/O).
PHASE5A_EVIDENCE_SERVICE = Phase5AEvidenceService()
