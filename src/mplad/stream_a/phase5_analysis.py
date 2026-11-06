"""Stream A -- Phase 5A: quantitative diagnostic analysis (compute only).

Role and boundaries
-------------------
Phase 5A consumes the **verified Phase 4 reproduction outputs** (read-only):

* ``results/stream a/phase 4/reproduction/phase4_evaluation_dataset.csv``
* ``results/stream a/phase 4/reproduction/phase4_run_metadata.json``

and produces the quantitative half of the historical Phase 5 diagnostics:
stratified bootstrap confidence intervals, a paired method comparison, the
10x10 Spearman and top-1% Jaccard matrices, multi-threshold agreement, the
hypergeometric overlap test, agreement-group composition and fraud-discovery
curve data. **Plotting is deliberately out of scope** (Phase 5B); every
output of this module is a numerical table.

This module NEVER fits, refits, retunes or constructs a detector (its only
scikit-learn import is ``sklearn.metrics``), NEVER modifies the canonical
30,000-row sample, and NEVER recomputes the saved Phase 3 bottom-1% flags:
the canonical flags are consumed exactly as supplied through the Phase 4
evaluation dataset.

Cross-run alignment guard
-------------------------
Every pairwise analysis (Spearman, Jaccard, multi-threshold agreement,
paired bootstrap) compares runs **positionally** on the shared 30,000-row
sequence. That is only legitimate because the Phase 4 evaluation dataset
stores every run against the SAME ``row_ids`` sequence. Phase 5A re-asserts
this before any analysis: all ten runs must carry an IDENTICAL ``row_id``
sequence (same values, same order) and identical ``Class`` sequences. A
run whose rows were permuted -- the Phase 4 label-misalignment bug class,
reappearing one layer up -- is a hard error, never a silent positional
comparison.

Score and threshold conventions
-------------------------------
* Ranking analyses use ``anomaly_score`` (higher = more anomalous), the
  canonical Phase 4 orientation.
* Fixed-threshold analyses use the SAVED Phase 3 flags. Inside bootstrap
  replicates the saved flags are simply carried along with the resampled
  observations -- the 1% threshold is never reselected. This is explicitly
  different from an optional top-1%-reselected bootstrap, which is NOT
  performed here.
* Derived top-k selections (thresholds other than the canonical 1%) rank
  by descending ``anomaly_score`` with a deterministic tie policy: ties are
  resolved by ascending position in the canonical evaluation-dataset row
  order (first-stored row wins; stable sort). Derived masks are kept in
  local variables and separate output columns -- they never replace or
  overwrite the canonical ``flag`` field anywhere.

Exploratory status of the highlighted runs
------------------------------------------
IF_003, IF_004, LOF_004 and the IF_003/LOF_004 pair were highlighted AFTER
inspecting the label-informed Phase 4 evaluation results. Every comparison
reported for them is therefore **exploratory** (post-hoc selection), and
this caveat is recorded in the run metadata and printed by the runner.

Interpretation limits
---------------------
The hypergeometric overlap test is interpreted ONLY against its stated
null: two independent uniform random selections of sizes k_a and k_b out of
n observations. Rejecting that null says nothing about whether flagged
observations are true anomalies.
"""
from __future__ import annotations

import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import scipy
import sklearn
from scipy.stats import hypergeom, rankdata
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from mplad.common import config
from mplad.common.io import (
    assert_outputs_writable,
    publish_phase5_artifacts,
    save_dataframe_csv,
    save_json,
)
from mplad.common.manifest import (
    ManifestVerificationError,
    build_manifest,
    load_manifest,
    save_manifest,
    verify_manifest,
)

__all__ = [
    "Phase5Error",
    "Phase4DatasetError",
    "Phase4ProvenanceError",
    "validate_phase4_run_metadata",
    "load_phase4_run_metadata",
    "validate_phase4_dataset",
    "load_phase4_dataset",
    "extract_aligned_runs",
    "iter_stratified_bootstrap_indices",
    "evaluate_bootstrap_metrics",
    "run_bootstrap_diagnostics",
    "compute_pairwise_spearman",
    "compute_pairwise_jaccard",
    "derive_topk_selection",
    "compute_multithreshold_agreement",
    "compute_hypergeometric_overlap",
    "compute_agreement_groups",
    "compute_fraud_discovery_curve",
    "collect_phase5_preflight",
    "run_phase5_analysis",
    "EVALUATION_DATASET_COLUMNS",
    "BOOTSTRAP_METRIC_NAMES",
    "BOOTSTRAP_METRICS_COLUMNS",
    "PAIRED_DIFFERENCES_COLUMNS",
    "MULTITHRESHOLD_AGREEMENT_COLUMNS",
    "HYPERGEOMETRIC_OVERLAP_COLUMNS",
    "AGREEMENT_GROUPS_COLUMNS",
    "FRAUD_DISCOVERY_CURVE_COLUMNS",
    "TIE_BREAK_POLICY",
    "NULL_MODEL_DESCRIPTION",
    "EXPLORATORY_SELECTION_CAVEAT",
    "BOOTSTRAP_THRESHOLD_POLICY",
]


# ---------------------------------------------------------------------------
# Errors (all ValueError subclasses, matching the Phase 3/4 convention)
# ---------------------------------------------------------------------------

class Phase5Error(ValueError):
    """Base class for Phase 5A contract violations."""


class Phase4DatasetError(Phase5Error):
    """The Phase 4 evaluation dataset violates its contract."""


class Phase4ProvenanceError(Phase5Error):
    """The Phase 4 run-metadata JSON violates its contract."""


# ---------------------------------------------------------------------------
# Schemas and documented conventions
# ---------------------------------------------------------------------------

#: Expected input schema: the Phase 4 evaluation dataset (long form, one row
#: per (run_id, row_id) -- see docs/phase4_contract.md section 6.1).
EVALUATION_DATASET_COLUMNS: list = [
    "run_id",
    "row_id",
    "Class",
    "native_score",
    "anomaly_score",
    "flag",
]

#: Metrics bootstrapped per highlighted run (names identical to Phase 4).
BOOTSTRAP_METRIC_NAMES: list = [
    "average_precision",
    "roc_auc",
    "precision_at_1pct",
    "recall_at_1pct",
    "f1_at_1pct",
]

#: phase5_bootstrap_metrics.csv schema.
BOOTSTRAP_METRICS_COLUMNS: list = [
    "run_id",
    "metric",
    "point_estimate",
    "bootstrap_mean",
    "bootstrap_std",
    "ci_lower",
    "ci_upper",
    "n_replicates",
]

#: phase5_paired_bootstrap_differences.csv schema.
PAIRED_DIFFERENCES_COLUMNS: list = [
    "comparison",
    "run_a",
    "run_b",
    "metric",
    "point_estimate",
    "bootstrap_mean",
    "bootstrap_std",
    "ci_lower",
    "ci_upper",
    "n_replicates",
]

#: phase5_multithreshold_agreement.csv schema.
MULTITHRESHOLD_AGREEMENT_COLUMNS: list = [
    "threshold_pct",
    "k_nominal",
    "selection_source",
    "n_methods",
    "observation_count",
]

#: phase5_hypergeometric_overlap.csv schema (one row).
HYPERGEOMETRIC_OVERLAP_COLUMNS: list = [
    "run_a",
    "run_b",
    "threshold_pct",
    "n_observations",
    "run_a_flagged",
    "run_b_flagged",
    "observed_intersection",
    "union_size",
    "expected_intersection",
    "enrichment_observed_over_expected",
    "survival_upper_tail",
    "log_survival",
    "log10_survival",
    "null_model",
]

#: phase5_agreement_groups.csv schema (one row per group).
AGREEMENT_GROUPS_COLUMNS: list = [
    "run_a",
    "run_b",
    "threshold_pct",
    "group",
    "observation_count",
    "fraud_count",
    "non_fraud_count",
    "fraud_proportion",
    "recall_contribution",
]

#: phase5_fraud_discovery_curve.csv schema.
FRAUD_DISCOVERY_CURVE_COLUMNS: list = [
    "run_id",
    "budget",
    "fraud_found",
    "precision",
    "recall",
]

#: Deterministic tie-breaking policy for every derived ranking / top-k
#: selection (canonical saved flags are never affected).
TIE_BREAK_POLICY: str = (
    "descending anomaly_score; ties resolved by ascending position in the "
    "canonical Phase 4 evaluation dataset row order (first-stored row wins; "
    "stable sort)"
)

#: The null the hypergeometric overlap test is interpreted against -- and
#: nothing else.
NULL_MODEL_DESCRIPTION: str = (
    "independent uniform random selection: run_a's flags and run_b's flags "
    "are two independent uniform random subsets of the n observations; the "
    "upper-tail probability is the extremity of the observed overlap under "
    "THIS null only and does not establish that flagged observations are "
    "true anomalies"
)

#: Post-hoc selection caveat recorded with every highlighted-run output.
EXPLORATORY_SELECTION_CAVEAT: str = (
    "Exploratory analysis: the highlighted runs (IF_003, IF_004, LOF_004 and "
    "the IF_003/LOF_004 pair) were selected after inspecting the "
    "label-informed Phase 4 evaluation results; comparisons involving them "
    "are post-hoc and must not be read as confirmatory."
)

#: Fixed-threshold policy inside bootstrap replicates.
BOOTSTRAP_THRESHOLD_POLICY: str = (
    "saved Phase 3 flags consumed as supplied on every replicate (attached "
    "to the resampled observations); the 1% threshold is never reselected, "
    "re-optimised or recomputed inside replicates -- deliberately distinct "
    "from an optional top-1%-reselected bootstrap, which is NOT performed"
)


# ---------------------------------------------------------------------------
# Phase 4 run-metadata JSON (provenance record of the consumed outputs)
# ---------------------------------------------------------------------------

def validate_phase4_run_metadata(payload: object) -> Dict:
    """Validate the Phase 4 run-metadata JSON payload; return its summary.

    Contract (``docs/phase4_contract.md`` section 6.3 -- the fields Phase 5A
    actually consumes):

    1. a JSON object (dict);
    2. ``phase`` identifies the Phase 4 provenance record (``"4"``);
    3. ``run_ids`` is a non-empty list of unique non-null strings;
    4. ``sample.sample_size`` is an integer >= 1;
    5. ``sample.fraud_count`` is an integer with
       ``1 <= fraud_count <= sample_size - 1`` (Phase 4 rejects single-class
       samples, so any genuine Phase 4 record satisfies this).

    Returns ``{"run_ids": [...], "sample_size": n, "fraud_count": p}``.
    """
    if not isinstance(payload, dict):
        raise Phase4ProvenanceError(
            f"Phase 4 run metadata must be a JSON object, got "
            f"{type(payload).__name__}."
        )

    problems = []
    if str(payload.get("phase")) != "4":
        problems.append(
            f"'phase' must identify the Phase 4 provenance record ('4'), got "
            f"{payload.get('phase')!r}"
        )

    run_ids = payload.get("run_ids")
    if not isinstance(run_ids, list) or not run_ids:
        problems.append("'run_ids' must be a non-empty list")
    elif any(not isinstance(r, str) or not r for r in run_ids):
        problems.append("'run_ids' entries must be non-empty strings")
    elif len(set(run_ids)) != len(run_ids):
        problems.append("'run_ids' contains duplicate values")

    sample = payload.get("sample")
    sample_size = fraud_count = None
    if not isinstance(sample, dict):
        problems.append("'sample' must be a JSON object")
    else:
        sample_size = sample.get("sample_size")
        fraud_count = sample.get("fraud_count")
        if not isinstance(sample_size, int) or isinstance(sample_size, bool) or sample_size < 1:
            problems.append("'sample.sample_size' must be an integer >= 1")
            sample_size = None
        if not isinstance(fraud_count, int) or isinstance(fraud_count, bool) or fraud_count < 0:
            problems.append("'sample.fraud_count' must be an integer >= 0")
            fraud_count = None
        elif sample_size is not None and not (1 <= fraud_count <= sample_size - 1):
            problems.append(
                "'sample.fraud_count' must satisfy 1 <= fraud_count <= "
                "sample_size - 1 (Phase 4 rejects single-class samples, so a "
                "genuine Phase 4 record cannot be outside this range)"
            )

    if problems:
        raise Phase4ProvenanceError(_format_problems(problems, "schema"))

    return {
        "run_ids": list(run_ids),
        "sample_size": int(sample_size),
        "fraud_count": int(fraud_count),
    }


def load_phase4_run_metadata(path: Path) -> Dict:
    """Load and validate the Phase 4 run-metadata JSON (provenance record)."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f"Phase 4 run metadata not found: {path}\n"
            f"Expected the Phase 4 provenance record at "
            f"{config.PHASE4_RUN_METADATA_JSON_PATH}. Pass --phase4-metadata "
            f"if it lives somewhere else."
        )
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as exc:
        raise Phase4ProvenanceError(f"Phase 4 run metadata is not valid JSON: {path}\n{exc}") from exc
    validate_phase4_run_metadata(payload)
    return payload


# ---------------------------------------------------------------------------
# Phase 4 evaluation dataset
# ---------------------------------------------------------------------------

def validate_phase4_dataset(
    dataset_df: pd.DataFrame,
    expected_run_ids: Optional[Sequence[str]] = None,
    run_metadata: Optional[Dict] = None,
) -> Dict:
    """Validate the Phase 4 evaluation dataset; return its summary.

    ``run_metadata`` is the VALIDATED Phase 4 provenance summary as returned
    by :func:`validate_phase4_run_metadata` (``{"run_ids", "sample_size",
    "fraud_count"}``); supply it to enable the provenance cross-checks.

    Checks (two stages, matching the house convention):

    Structural (schema):
      1. a pandas DataFrame;
      2. every required column present (``EVALUATION_DATASET_COLUMNS``);
      3. no unexpected extra columns (the Phase 4 output schema is frozen);
      4. the run-ID set equals ``expected_run_ids`` (default: the ten
         canonical Phase 3 runs).

    Content (integrity), per run and across runs:
      5. no missing values anywhere;
      6. each run contributes exactly ``sample_size`` rows (total rows ==
         sample_size x n_runs -- a duplicated or partial run block is
         rejected);
      7. ``row_id`` is integer-typed and unique within each run;
      8. ``Class`` and ``flag`` are strictly binary;
      9. ``native_score`` / ``anomaly_score`` are floating and finite;
      10. ``anomaly_score == -native_score`` exactly (the canonical Phase 4
          orientation -- a mangled orientation column is rejected);
      11. every run carries the IDENTICAL ``row_id`` sequence, same values
          and same order (the cross-run positional-alignment guard), and the
          identical ``Class`` sequence;
      12. cross-checks against the Phase 4 provenance record when supplied:
          identical run-ID set, matching sample size, matching fraud count.

    Returns a summary dict (sample size, run IDs in canonical order, fraud
    count and prevalence, per-run saved-flag counts).
    """
    if expected_run_ids is None:
        expected_run_ids = config.PHASE3_CANONICAL_RUN_IDS
    expected_run_ids = list(expected_run_ids)

    if not isinstance(dataset_df, pd.DataFrame):
        raise Phase4DatasetError(
            f"Expected a pandas DataFrame, got {type(dataset_df).__name__}."
        )

    columns = list(dataset_df.columns)
    problems = []
    missing = [c for c in EVALUATION_DATASET_COLUMNS if c not in columns]
    if missing:
        problems.append("missing column(s): " + ", ".join(missing))
    unexpected = [c for c in columns if c not in EVALUATION_DATASET_COLUMNS]
    if unexpected:
        problems.append(
            "unexpected extra column(s): " + ", ".join(unexpected)
            + " -- the Phase 4 evaluation dataset schema is frozen"
        )
    if problems:
        raise Phase4DatasetError(_format_problems(problems, "schema"))

    if dataset_df.empty:
        raise Phase4DatasetError(_format_problems(["the dataset is empty"], "integrity"))

    actual_runs = dataset_df["run_id"].unique().tolist()
    missing_runs = sorted(set(expected_run_ids) - set(actual_runs))
    unexpected_runs = sorted(set(actual_runs) - set(expected_run_ids))
    if missing_runs or unexpected_runs:
        parts = []
        if missing_runs:
            parts.append("missing run(s): " + ", ".join(missing_runs))
        if unexpected_runs:
            parts.append("unexpected run(s): " + ", ".join(unexpected_runs))
        raise Phase4DatasetError(
            "evaluation dataset runs do not match the expected experiment "
            f"runs ({len(expected_run_ids)} expected). " + "; ".join(parts)
        )

    problems = []
    if dataset_df.isna().any().any():
        nan_counts = dataset_df.isna().sum()
        problems.append(
            "missing values in column(s): "
            + ", ".join(f"{c} ({int(n)})" for c, n in nan_counts.items() if n)
        )

    per_run: Dict[str, Dict] = {}
    reference_ids: Optional[np.ndarray] = None
    reference_class: Optional[np.ndarray] = None
    for run_id in expected_run_ids:
        run = dataset_df[dataset_df["run_id"] == run_id]
        n_rows = len(run)
        row_ids = run["row_id"].to_numpy()
        class_values = run[config.LABEL_COLUMN].to_numpy()
        native = run["native_score"].to_numpy()
        anomaly = run["anomaly_score"].to_numpy()
        flags = run["flag"].to_numpy()

        if row_ids.dtype.kind not in "iu":
            problems.append(f"run '{run_id}': 'row_id' must have an integer dtype, got {row_ids.dtype}")
        elif np.unique(row_ids).size != row_ids.size:
            problems.append(f"run '{run_id}': 'row_id' contains duplicate values")
        if class_values.dtype.kind not in "iuf" or not np.isin(class_values, (0, 1)).all():
            problems.append(
                f"run '{run_id}': 'Class' must be strictly binary (0/1), got values "
                f"{np.unique(class_values).tolist()[:5]}"
            )
        if flags.dtype.kind not in "iuf" or not np.isin(flags, (0, 1)).all():
            problems.append(
                f"run '{run_id}': 'flag' must be strictly binary (0/1), got values "
                f"{np.unique(flags).tolist()[:5]}"
            )
        for name, arr in (("native_score", native), ("anomaly_score", anomaly)):
            if arr.dtype.kind != "f":
                problems.append(f"run '{run_id}': '{name}' must have a floating dtype, got {arr.dtype}")
            elif not np.isfinite(arr).all():
                n_bad = int((~np.isfinite(arr)).sum())
                problems.append(
                    f"run '{run_id}': '{name}' contains {n_bad} non-finite value(s)"
                )
        if native.dtype.kind == "f" and anomaly.dtype.kind == "f":
            if not np.array_equal(anomaly, -native):
                n_bad = int((anomaly != -native).sum())
                problems.append(
                    f"run '{run_id}': 'anomaly_score' != -'native_score' for "
                    f"{n_bad} row(s) -- the canonical Phase 4 orientation "
                    f"(anomaly_score = -native_score) is violated"
                )

        if reference_ids is None:
            reference_ids = row_ids
            reference_class = class_values
        else:
            if not np.array_equal(row_ids, reference_ids):
                problems.append(
                    f"run '{run_id}': the row_id sequence differs from the other "
                    f"runs (values or order) -- all runs must share the identical "
                    f"row_id sequence; a positional cross-run comparison would be "
                    f"invalid"
                )
            if not np.array_equal(class_values, reference_class):
                problems.append(
                    f"run '{run_id}': the 'Class' sequence differs from the other "
                    f"runs -- labels are joined on row_id and must be identical "
                    f"across runs"
                )

        per_run[run_id] = {
            "n_rows": n_rows,
            "flagged_count": int(np.count_nonzero(flags == 1)) if flags.dtype.kind in "iuf" else -1,
        }

    if problems:
        raise Phase4DatasetError(_format_problems(problems, "integrity"))

    sample_size = per_run[expected_run_ids[0]]["n_rows"]
    if any(v["n_rows"] != sample_size for v in per_run.values()):
        sizes = {r: v["n_rows"] for r, v in per_run.items()}
        raise Phase4DatasetError(
            _format_problems(
                [f"runs contribute different row counts: {sizes}"], "integrity"
            )
        )
    total_rows = int(len(dataset_df))
    if total_rows != sample_size * len(expected_run_ids):
        raise Phase4DatasetError(
            _format_problems(
                [
                    f"total row count ({total_rows:,}) != sample_size x n_runs "
                    f"({sample_size:,} x {len(expected_run_ids)}) -- a duplicated "
                    f"or partial run block is present"
                ],
                "integrity",
            )
        )

    fraud_count = int(np.count_nonzero(reference_class == 1))

    # Cross-checks against the Phase 4 provenance record.
    if run_metadata is not None:
        meta_runs = set(run_metadata["run_ids"])
        if meta_runs != set(expected_run_ids):
            raise Phase4DatasetError(
                "the Phase 4 provenance record lists a different run set than "
                f"the expected experiment runs (metadata: {sorted(meta_runs)}, "
                f"expected: {sorted(expected_run_ids)})"
            )
        if run_metadata["sample_size"] != sample_size:
            raise Phase4DatasetError(
                f"sample size mismatch: the dataset carries {sample_size:,} rows "
                f"per run, the Phase 4 provenance record says "
                f"{run_metadata['sample_size']:,}"
            )
        if run_metadata["fraud_count"] != fraud_count:
            raise Phase4DatasetError(
                f"fraud count mismatch: the dataset contains {fraud_count} "
                f"positive labels, the Phase 4 provenance record says "
                f"{run_metadata['fraud_count']}"
            )

    return {
        "sample_size": sample_size,
        "run_ids": expected_run_ids,
        "total_rows": total_rows,
        "fraud_count": fraud_count,
        "fraud_prevalence": fraud_count / sample_size,
        "per_run_flagged_counts": {r: v["flagged_count"] for r, v in per_run.items()},
    }


def load_phase4_dataset(
    path: Path,
    expected_run_ids: Optional[Sequence[str]] = None,
    run_metadata: Optional[Dict] = None,
) -> pd.DataFrame:
    """Load and validate the Phase 4 evaluation dataset CSV.

    Returns the validated frame (schema checked, run set checked, cross-run
    consistency checked). Row order within each run is preserved exactly as
    stored -- it defines the canonical positional order every later analysis
    relies on.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f"Phase 4 evaluation dataset not found: {path}\n"
            f"Expected the verified Phase 4 output at "
            f"{config.PHASE4_EVALUATION_DATASET_PATH}. Pass "
            f"--evaluation-dataset if it lives somewhere else."
        )
    dataset_df = pd.read_csv(path)
    validate_phase4_dataset(dataset_df, expected_run_ids, run_metadata)
    return dataset_df


def extract_aligned_runs(dataset_df: pd.DataFrame, run_ids: Sequence[str]) -> Dict:
    """Extract the per-run aligned arrays every analysis operates on.

    Returns::

        {"row_ids":   (n,) int array,       # the shared sequence
         "labels":    (n,) int array,       # ground truth, 0/1
         "runs":      {run_id: {"anomaly_score": (n,), "flag": (n,)}},
         "run_ids":   list[str],            # canonical order
         "sample_size": int,
         "fraud_count": int}

    The identical-sequence guarantee is re-asserted here (cheap) so that
    callers building the frame themselves cannot bypass it.
    """
    run_ids = list(run_ids)
    available = set(dataset_df["run_id"].unique().tolist())
    missing = [r for r in run_ids if r not in available]
    if missing:
        raise Phase4DatasetError(
            "cannot extract runs missing from the dataset: " + ", ".join(missing)
        )

    labels: Optional[np.ndarray] = None
    row_ids: Optional[np.ndarray] = None
    runs: Dict[str, Dict[str, np.ndarray]] = {}
    for run_id in run_ids:
        run = dataset_df[dataset_df["run_id"] == run_id]
        run_row_ids = run["row_id"].to_numpy()
        run_labels = run[config.LABEL_COLUMN].to_numpy()
        if row_ids is None:
            row_ids, labels = run_row_ids, run_labels
        elif not np.array_equal(run_row_ids, row_ids) or not np.array_equal(run_labels, labels):
            raise Phase4DatasetError(
                f"run '{run_id}': row_id/Class sequence differs from the other "
                f"runs -- positional cross-run comparison would be invalid"
            )
        runs[run_id] = {
            "anomaly_score": run["anomaly_score"].to_numpy(),
            "flag": run["flag"].to_numpy(),
        }

    assert row_ids is not None and labels is not None  # guaranteed non-empty run_ids
    return {
        "row_ids": row_ids,
        "labels": labels.astype(np.int64),
        "runs": runs,
        "run_ids": run_ids,
        "sample_size": int(row_ids.shape[0]),
        "fraud_count": int(np.count_nonzero(labels == 1)),
    }


# ---------------------------------------------------------------------------
# Phase 4 input manifest (optional) / legacy handling
# ---------------------------------------------------------------------------

def _check_phase4_input_manifest(
    evaluation_dataset_path: Path, run_metadata_path: Path
) -> Dict:
    """Verify the Phase 4 output manifest, or classify the inputs as legacy.

    The manifest is expected at
    ``<dataset directory>/phase4_commit_manifest.json``. The hardened Phase 4
    publishes one, so on a healthy repository it EXISTS: every listed
    artifact is hash-verified (and the manifest must cover both consumed
    Phase 4 outputs) BEFORE anything is consumed.

    If it is absent, the inputs are marked as a legacy unmanifested pair:
    strict structural validation and SHA-256 recording are the integrity
    controls, and the result says so explicitly -- verification is never
    claimed when none was performed.
    """
    manifest_path = Path(evaluation_dataset_path).parent / config.PHASE5_INPUT_MANIFEST_FILENAME
    if not manifest_path.is_file():
        return {
            "present": False,
            "verified": False,
            "mode": "legacy_unmanifested",
            "path": str(manifest_path),
            "note": (
                "No Phase 4 commit manifest exists next to the consumed "
                "outputs. Strict structural validation was applied and the "
                "input SHA-256 hashes are recorded in this provenance "
                "record. Manifest verification was NOT performed."
            ),
        }

    manifest = load_manifest(manifest_path)
    report = verify_manifest(
        manifest,
        base_dir=manifest_path.parent,
        required_artifacts=(
            Path(evaluation_dataset_path).name,
            Path(run_metadata_path).name,
        ),
    )
    return {
        "present": True,
        "verified": True,
        "mode": "manifest_verified",
        "path": str(manifest_path),
        "artifacts": report,
    }


# ---------------------------------------------------------------------------
# A. Bootstrap diagnostics (class-stratified, paired)
# ---------------------------------------------------------------------------

def iter_stratified_bootstrap_indices(
    labels: np.ndarray, n_replicates: int, seed: int
) -> Iterator[np.ndarray]:
    """Yield ``n_replicates`` class-stratified bootstrap index arrays.

    Each replicate draws, WITH replacement and separately per class, exactly
    as many indices as the class has observations: ``n_pos`` draws from the
    positive positions and ``n_neg`` draws from the negative positions. The
    class prevalence is therefore preserved EXACTLY in every replicate.

    The generator is ``numpy.random.default_rng(seed)`` (PCG64) -- a new,
    explicitly recorded stream, fully independent of the Phase 3 legacy
    RandomState sampling. The same seed always yields the same replicate
    sequence. Replicate row order (positives first) is irrelevant to every
    metric computed on it.
    """
    labels = np.asarray(labels)
    if labels.ndim != 1 or labels.size == 0:
        raise Phase5Error("'labels' must be a non-empty 1-D array")
    if not isinstance(n_replicates, (int, np.integer)) or n_replicates < 1:
        raise Phase5Error(f"n_replicates must be an integer >= 1, got {n_replicates!r}")

    pos = np.flatnonzero(labels == 1)
    neg = np.flatnonzero(labels != 1)
    if pos.size == 0 or neg.size == 0:
        raise Phase5Error(
            "stratified bootstrap requires both classes to be present "
            f"(got {pos.size} positive and {neg.size} negative observations)"
        )

    rng = np.random.default_rng(seed)
    for _ in range(int(n_replicates)):
        pos_draw = rng.choice(pos, size=pos.size, replace=True)
        neg_draw = rng.choice(neg, size=neg.size, replace=True)
        yield np.concatenate([pos_draw, neg_draw])


def evaluate_bootstrap_metrics(
    y_true: np.ndarray, anomaly_score: np.ndarray, flag: np.ndarray
) -> Dict:
    """Compute the five Phase 5 metrics for one (sub)sample of one run.

    Ranking metrics (Average Precision, ROC-AUC) use ``anomaly_score``
    (higher = more anomalous). Fixed-threshold metrics
    (Precision/Recall/F1 @1%) use the SAVED Phase 3 flags supplied in
    ``flag`` -- never a reselected threshold. ``pos_label=1`` and
    ``zero_division=0`` throughout; a single-class input is rejected
    (AP and ROC-AUC are undefined there).
    """
    y_true = np.asarray(y_true)
    anomaly_score = np.asarray(anomaly_score)
    flag = np.asarray(flag)
    if y_true.ndim != 1 or anomaly_score.shape != y_true.shape or flag.shape != y_true.shape:
        raise Phase5Error(
            "y_true, anomaly_score and flag must be 1-D arrays of equal length "
            f"(got {y_true.shape}, {anomaly_score.shape}, {flag.shape})"
        )
    unique_labels = np.unique(y_true)
    if unique_labels.size < 2:
        raise Phase5Error(
            "the sample contains a single ground-truth class "
            f"({unique_labels.tolist()}); ranking metrics are undefined"
        )
    return {
        "average_precision": float(average_precision_score(y_true, anomaly_score)),
        "roc_auc": float(roc_auc_score(y_true, anomaly_score)),
        "precision_at_1pct": float(precision_score(y_true, flag, pos_label=1, zero_division=0)),
        "recall_at_1pct": float(recall_score(y_true, flag, pos_label=1, zero_division=0)),
        "f1_at_1pct": float(f1_score(y_true, flag, pos_label=1, zero_division=0)),
    }


def _percentile_interval(values: np.ndarray, ci_level: float) -> Tuple[float, float]:
    alpha = 100.0 * (1.0 - ci_level) / 2.0
    lower, upper = np.percentile(values, [alpha, 100.0 - alpha])
    return float(lower), float(upper)


def run_bootstrap_diagnostics(
    aligned: Dict,
    n_replicates: int = config.PHASE5_BOOTSTRAP_REPLICATES_DEFAULT,
    seed: int = config.PHASE5_BOOTSTRAP_SEED_DEFAULT,
    bootstrap_run_ids: Optional[Sequence[str]] = None,
    paired_runs: Optional[Sequence[str]] = None,
    ci_level: float = config.PHASE5_CI_LEVEL,
    verbose: bool = False,
) -> Dict:
    """Stratified bootstrap CIs + the paired run_b-minus-run_a comparison.

    Protocol (frozen in ``config``): ``n_replicates`` class-stratified
    bootstrap replicates of the 30,000-row sample; per replicate the SAME
    index array is applied to EVERY highlighted run, which is what makes the
    comparison **paired** -- both methods are evaluated on identical
    resampled observations. Metrics: AP, ROC-AUC and the saved-flag
    Precision/Recall/F1 @1%.

    Point estimates are computed on the FULL aligned sample (not on the
    bootstrap means); intervals are percentile bootstrap intervals at
    ``ci_level``. The fixed-threshold metrics inside replicates use the
    saved Phase 3 flags as supplied -- see ``BOOTSTRAP_THRESHOLD_POLICY``.

    Returns ``{"bootstrap_metrics", "paired_differences", "replicate_values",
    "point_estimates", "diagnostics"}`` where ``replicate_values`` holds the
    raw per-replicate metric values (in-memory only, never written).
    """
    if bootstrap_run_ids is None:
        bootstrap_run_ids = list(config.PHASE5_BOOTSTRAP_RUN_IDS)
    bootstrap_run_ids = list(bootstrap_run_ids)
    if paired_runs is None:
        paired_runs = tuple(config.PHASE5_PAIRED_COMPARISON_RUNS)
    paired_runs = tuple(paired_runs)

    if not 0.0 < ci_level < 1.0:
        raise Phase5Error(f"ci_level must be in (0, 1), got {ci_level!r}")
    available = set(aligned["run_ids"])
    if not bootstrap_run_ids:
        raise Phase5Error("bootstrap_run_ids must be non-empty")
    missing = [r for r in bootstrap_run_ids if r not in available]
    if missing:
        raise Phase5Error(
            "bootstrap runs missing from the aligned data: " + ", ".join(missing)
        )
    if len(set(bootstrap_run_ids)) != len(bootstrap_run_ids):
        raise Phase5Error("bootstrap_run_ids contains duplicates")
    if len(paired_runs) != 2 or paired_runs[0] == paired_runs[1]:
        raise Phase5Error(
            f"paired_runs must be two distinct run IDs, got {list(paired_runs)}"
        )
    for r in paired_runs:
        if r not in bootstrap_run_ids:
            raise Phase5Error(
                f"paired run '{r}' must be part of the bootstrapped runs "
                "(the paired comparison reuses the replicate indices)"
            )

    labels = aligned["labels"]
    run_a, run_b = paired_runs

    # Point estimates on the full aligned sample.
    point_estimates = {
        r: evaluate_bootstrap_metrics(
            labels, aligned["runs"][r]["anomaly_score"], aligned["runs"][r]["flag"]
        )
        for r in bootstrap_run_ids
    }

    # Bootstrap loop: ONE index array per replicate, shared by every run.
    values: Dict[str, Dict[str, np.ndarray]] = {
        r: {m: np.empty(int(n_replicates), dtype=np.float64) for m in BOOTSTRAP_METRIC_NAMES}
        for r in bootstrap_run_ids
    }
    for i, idx in enumerate(iter_stratified_bootstrap_indices(labels, n_replicates, seed)):
        y_b = labels[idx]
        for r in bootstrap_run_ids:
            run_data = aligned["runs"][r]
            replicate_metrics = evaluate_bootstrap_metrics(
                y_b, run_data["anomaly_score"][idx], run_data["flag"][idx]
            )
            for metric_name, value in replicate_metrics.items():
                values[r][metric_name][i] = value
        if verbose and ((i + 1) % 500 == 0 or (i + 1) == int(n_replicates)):
            print(f"  bootstrap replicate {i + 1:,}/{int(n_replicates):,}")

    metric_rows = []
    for r in bootstrap_run_ids:
        for metric_name in BOOTSTRAP_METRIC_NAMES:
            arr = values[r][metric_name]
            ci_lower, ci_upper = _percentile_interval(arr, ci_level)
            metric_rows.append(
                {
                    "run_id": r,
                    "metric": metric_name,
                    "point_estimate": point_estimates[r][metric_name],
                    "bootstrap_mean": float(arr.mean()),
                    "bootstrap_std": float(arr.std(ddof=1)) if int(n_replicates) > 1 else 0.0,
                    "ci_lower": ci_lower,
                    "ci_upper": ci_upper,
                    "n_replicates": int(n_replicates),
                }
            )
    bootstrap_metrics = pd.DataFrame(metric_rows, columns=BOOTSTRAP_METRICS_COLUMNS)

    paired_rows = []
    for metric_name in BOOTSTRAP_METRIC_NAMES:
        differences = values[run_b][metric_name] - values[run_a][metric_name]
        ci_lower, ci_upper = _percentile_interval(differences, ci_level)
        paired_rows.append(
            {
                "comparison": f"{run_b} - {run_a}",
                "run_a": run_a,
                "run_b": run_b,
                "metric": metric_name,
                "point_estimate": point_estimates[run_b][metric_name]
                - point_estimates[run_a][metric_name],
                "bootstrap_mean": float(differences.mean()),
                "bootstrap_std": float(differences.std(ddof=1)) if int(n_replicates) > 1 else 0.0,
                "ci_lower": ci_lower,
                "ci_upper": ci_upper,
                "n_replicates": int(n_replicates),
            }
        )
    paired_differences = pd.DataFrame(paired_rows, columns=PAIRED_DIFFERENCES_COLUMNS)

    return {
        "bootstrap_metrics": bootstrap_metrics,
        "paired_differences": paired_differences,
        "replicate_values": values,
        "point_estimates": point_estimates,
        "diagnostics": {
            "n_replicates": int(n_replicates),
            "seed": int(seed),
            "rng": "numpy.random.default_rng (PCG64)",
            "resampling": (
                "class-stratified with replacement; positives and negatives "
                "resampled separately; prevalence preserved exactly per replicate"
            ),
            "runs_evaluated": list(bootstrap_run_ids),
            "paired_comparison": {
                "run_a": run_a,
                "run_b": run_b,
                "definition": f"{run_b} - {run_a}",
                "paired": True,
                "shared_indices": True,
            },
            "threshold_policy": BOOTSTRAP_THRESHOLD_POLICY,
            "ci_method": "percentile",
            "ci_level": float(ci_level),
            "selection_caveat": EXPLORATORY_SELECTION_CAVEAT,
        },
    }


# ---------------------------------------------------------------------------
# B. Pairwise Spearman correlation (10 x 10, on anomaly_score)
# ---------------------------------------------------------------------------

def compute_pairwise_spearman(aligned: Dict, run_ids: Optional[Sequence[str]] = None) -> pd.DataFrame:
    """Pairwise Spearman rank-correlation matrix of the ``anomaly_score``.

    Spearman is computed as the Pearson correlation of tie-corrected
    (average) ranks, exactly ``scipy.stats.spearmanr``'s definition. Higher
    score = more anomalous, so a positive correlation means the two runs
    rank the same observations as anomalous. The identical cross-run
    ``row_id`` sequence has already been validated upstream, which is what
    makes the positional comparison legitimate.

    The diagonal is exactly 1.0; a run whose scores are constant (rank
    variance zero) is rejected -- its correlations are undefined.
    """
    run_ids = list(aligned["run_ids"]) if run_ids is None else list(run_ids)
    _require_runs(aligned, run_ids)

    score_matrix = np.column_stack(
        [np.asarray(aligned["runs"][r]["anomaly_score"], dtype=np.float64) for r in run_ids]
    )
    ranks = np.apply_along_axis(rankdata, 0, score_matrix)  # method="average"

    zero_variance = [r for r, col in zip(run_ids, ranks.T) if np.ptp(col) == 0.0]
    if zero_variance:
        raise Phase5Error(
            "Spearman correlation is undefined for constant anomaly scores "
            "(all ranks tied): " + ", ".join(zero_variance)
        )

    correlation = np.corrcoef(ranks, rowvar=False)
    correlation = np.clip(correlation, -1.0, 1.0)
    np.fill_diagonal(correlation, 1.0)
    return pd.DataFrame(correlation, index=run_ids, columns=run_ids)


# ---------------------------------------------------------------------------
# C. Pairwise Jaccard similarity (10 x 10, on the saved 1% flags)
# ---------------------------------------------------------------------------

def compute_pairwise_jaccard(aligned: Dict, run_ids: Optional[Sequence[str]] = None) -> pd.DataFrame:
    """Pairwise Jaccard similarity of the SAVED Phase 3 1% flags.

    J(i, j) = |flags_i AND flags_j| / |flags_i OR flags_j|. The canonical
    1% flags are consumed exactly as supplied -- never recomputed from
    scores. By convention two empty selections (both runs flag nothing) have
    Jaccard 1.0 (perfect agreement). The diagonal is exactly 1.0.
    """
    run_ids = list(aligned["run_ids"]) if run_ids is None else list(run_ids)
    _require_runs(aligned, run_ids)

    flag_matrix = np.column_stack(
        [np.asarray(aligned["runs"][r]["flag"]) == 1 for r in run_ids]
    )
    n_runs = len(run_ids)
    jaccard = np.eye(n_runs, dtype=np.float64)
    for i in range(n_runs):
        for j in range(i + 1, n_runs):
            intersection = int(np.count_nonzero(flag_matrix[:, i] & flag_matrix[:, j]))
            union = int(np.count_nonzero(flag_matrix[:, i] | flag_matrix[:, j]))
            value = 1.0 if union == 0 else intersection / union
            jaccard[i, j] = value
            jaccard[j, i] = value
    return pd.DataFrame(jaccard, index=run_ids, columns=run_ids)


# ---------------------------------------------------------------------------
# D. Multi-threshold agreement
# ---------------------------------------------------------------------------

def derive_topk_selection(anomaly_score: np.ndarray, k: int) -> np.ndarray:
    """Derive a deterministic top-k selection mask from continuous scores.

    Ranking: descending ``anomaly_score``; ties are resolved by ascending
    position in the canonical evaluation-dataset row order (first-stored row
    wins) via a stable sort. Returns a uint8 mask of 0/1. This is a DERIVED
    selection -- it must never be confused with, or written over, the
    canonical saved Phase 3 flags.
    """
    anomaly_score = np.asarray(anomaly_score)
    k = int(k)
    n = anomaly_score.shape[0]
    if k < 1 or k > n:
        raise Phase5Error(f"k must satisfy 1 <= k <= n ({n}), got {k}")
    order = np.argsort(-anomaly_score, kind="stable")
    selection = np.zeros(n, dtype=np.uint8)
    selection[order[:k]] = 1
    return selection


def compute_multithreshold_agreement(
    aligned: Dict,
    threshold_percentages: Optional[Sequence[float]] = None,
    run_ids: Optional[Sequence[str]] = None,
) -> Tuple[pd.DataFrame, Dict]:
    """Cross-method agreement across top-k thresholds; return (table, details).

    For each percentage in ``threshold_percentages`` (default
    ``0.1%, 0.2%, 0.5%, 1%, 2%, 5%``) with ``k = round(n * pct / 100)``:

    * at the CANONICAL 1% the SAVED Phase 3 flags are used as supplied
      (``selection_source = "canonical_saved_flags"``) -- the bottom-1% rule
      is never recomputed;
    * at every other percentage selections are DERIVED from the continuous
      ``anomaly_score`` under ``TIE_BREAK_POLICY``
      (``selection_source = "derived_topk"``) and kept strictly separate
      from the canonical flags.

    The table reports, per threshold, how many of the ``n`` observations are
    selected by exactly ``m`` methods (``m = 0..n_runs``); the details dict
    records the per-run selection sizes, the k rule and the tie policy.
    """
    if threshold_percentages is None:
        threshold_percentages = config.PHASE5_MULTI_THRESHOLD_PERCENTS
    threshold_percentages = list(threshold_percentages)
    run_ids = list(aligned["run_ids"]) if run_ids is None else list(run_ids)
    _require_runs(aligned, run_ids)

    n = int(aligned["sample_size"])
    n_runs = len(run_ids)

    rows = []
    per_run_selection_sizes: Dict[str, Dict[str, int]] = {}
    for pct in threshold_percentages:
        k = int(round(n * float(pct) / 100.0))
        if k < 1 or k > n:
            raise Phase5Error(
                f"threshold {pct}% yields k={k} outside 1..{n} on a sample of "
                f"{n} observations -- the agreement grid must fit the sample"
            )
        canonical = float(pct) == config.PHASE5_CANONICAL_THRESHOLD_PCT
        if canonical:
            selections = {
                r: np.asarray(aligned["runs"][r]["flag"]) == 1 for r in run_ids
            }
            source = "canonical_saved_flags"
        else:
            selections = {
                r: derive_topk_selection(aligned["runs"][r]["anomaly_score"], k) == 1
                for r in run_ids
            }
            source = "derived_topk"
        per_run_selection_sizes[str(float(pct))] = {
            r: int(sel.sum()) for r, sel in selections.items()
        }

        selection_matrix = np.column_stack([selections[r] for r in run_ids])
        methods_per_observation = selection_matrix.sum(axis=1)
        level_counts = {
            m: int(np.count_nonzero(methods_per_observation == m))
            for m in range(n_runs + 1)
        }
        if sum(level_counts.values()) != n:
            raise Phase5Error(
                f"threshold {pct}%: agreement levels do not partition the "
                f"sample (sum {sum(level_counts.values())} != {n})"
            )
        for m in range(n_runs + 1):
            rows.append(
                {
                    "threshold_pct": float(pct),
                    "k_nominal": k,
                    "selection_source": source,
                    "n_methods": m,
                    "observation_count": level_counts[m],
                }
            )

    agreement_table = pd.DataFrame(rows, columns=MULTITHRESHOLD_AGREEMENT_COLUMNS)
    details = {
        "k_rule": "k = round(n * pct / 100), required to satisfy 1 <= k <= n",
        "tie_breaking": TIE_BREAK_POLICY,
        "canonical_threshold_pct": config.PHASE5_CANONICAL_THRESHOLD_PCT,
        "canonical_threshold_source": "saved Phase 3 flags (never rederived)",
        "per_run_selection_sizes": per_run_selection_sizes,
    }
    return agreement_table, details


# ---------------------------------------------------------------------------
# E. Hypergeometric overlap analysis
# ---------------------------------------------------------------------------

def compute_hypergeometric_overlap(
    flags_a: np.ndarray,
    flags_b: np.ndarray,
    n_observations: Optional[int] = None,
    run_a: str = "run_a",
    run_b: str = "run_b",
    threshold_pct: float = config.PHASE5_CANONICAL_THRESHOLD_PCT,
) -> Dict:
    """Hypergeometric overlap analysis of two canonical flag vectors.

    Given the saved 1% flags of ``run_a`` (k_a flagged) and ``run_b`` (k_b
    flagged) over ``n`` observations, reports: both flagged counts, the
    observed intersection and union, the expected intersection under the
    independent uniform-selection null (``k_a * k_b / n``), the
    observed/expected enrichment, and the upper-tail probability
    ``P(X >= observed)`` with X ~ Hypergeometric(N=n, successes=k_a,
    draws=k_b) -- computed via the survival / log-survival function so
    extremely small probabilities do not underflow.

    Interpretation is valid ONLY against the stated null (see
    ``NULL_MODEL_DESCRIPTION``); it does not establish that flagged
    observations are true anomalies.
    """
    flags_a = np.asarray(flags_a)
    flags_b = np.asarray(flags_b)
    if flags_a.ndim != 1 or flags_b.ndim != 1 or flags_a.shape != flags_b.shape:
        raise Phase5Error("flags_a and flags_b must be 1-D arrays of equal length")
    n = int(flags_a.shape[0]) if n_observations is None else int(n_observations)
    if n < 1 or n != flags_a.shape[0]:
        raise Phase5Error(
            f"n_observations ({n}) must equal the flag vector length "
            f"({flags_a.shape[0]}) and be >= 1"
        )

    a = flags_a == 1
    b = flags_b == 1
    k_a = int(np.count_nonzero(a))
    k_b = int(np.count_nonzero(b))
    observed = int(np.count_nonzero(a & b))
    union = int(np.count_nonzero(a | b))

    if observed > min(k_a, k_b) or union != k_a + k_b - observed:
        raise Phase5Error(
            "internally inconsistent flag vectors: intersection/union do not "
            "match the marginal counts"
        )

    expected = (k_a * k_b) / n
    enrichment = observed / expected if expected > 0 else float("nan")

    # scipy.stats.hypergeom positional signature: (k, M, n_successes, n_draws)
    # with M = population size, n = success states, N = draws. sf(k - 1, ...)
    # = P(X >= k). logsf is the natural-log survival function.
    survival = float(hypergeom.sf(observed - 1, n, k_a, k_b))
    log_survival = float(hypergeom.logsf(observed - 1, n, k_a, k_b))
    log10_survival = log_survival / math.log(10.0)

    return {
        "run_a": run_a,
        "run_b": run_b,
        "threshold_pct": float(threshold_pct),
        "n_observations": n,
        "run_a_flagged": k_a,
        "run_b_flagged": k_b,
        "observed_intersection": observed,
        "union_size": union,
        "expected_intersection": expected,
        "enrichment_observed_over_expected": enrichment,
        "survival_upper_tail": survival,
        "log_survival": log_survival,
        "log10_survival": log10_survival,
        "null_model": NULL_MODEL_DESCRIPTION,
    }


# ---------------------------------------------------------------------------
# F. Agreement-group composition
# ---------------------------------------------------------------------------

def compute_agreement_groups(
    flags_a: np.ndarray,
    flags_b: np.ndarray,
    labels: np.ndarray,
    run_a: str = "run_a",
    run_b: str = "run_b",
    threshold_pct: float = config.PHASE5_CANONICAL_THRESHOLD_PCT,
) -> pd.DataFrame:
    """Compose the four agreement groups of two canonical flag vectors.

    Groups (a disjoint, EXHAUSTIVE partition of all n observations):
    ``both`` (flagged by both runs), ``if_only`` (flagged by run_a only),
    ``lof_only`` (flagged by run_b only), ``neither``. Per group: the
    observation count, the Class=1 and Class=0 counts, the fraud proportion
    within the group, and the group's contribution to total recall
    (group frauds / total frauds).

    The partition property is validated before returning -- the four counts
    must sum to n and the fraud counts to the total fraud count.
    """
    flags_a = np.asarray(flags_a)
    flags_b = np.asarray(flags_b)
    labels = np.asarray(labels)
    if flags_a.shape != flags_b.shape or flags_a.shape != labels.shape or flags_a.ndim != 1:
        raise Phase5Error(
            "flags_a, flags_b and labels must be 1-D arrays of equal length"
        )

    a = flags_a == 1
    b = flags_b == 1
    fraud = labels == 1
    n = int(labels.shape[0])
    total_fraud = int(np.count_nonzero(fraud))

    groups = [
        ("both", a & b),
        ("if_only", a & ~b),
        ("lof_only", ~a & b),
        ("neither", ~a & ~b),
    ]
    rows = []
    for group_name, mask in groups:
        count = int(np.count_nonzero(mask))
        group_fraud = int(np.count_nonzero(mask & fraud))
        rows.append(
            {
                "run_a": run_a,
                "run_b": run_b,
                "threshold_pct": float(threshold_pct),
                "group": group_name,
                "observation_count": count,
                "fraud_count": group_fraud,
                "non_fraud_count": count - group_fraud,
                "fraud_proportion": (group_fraud / count) if count else 0.0,
                "recall_contribution": (group_fraud / total_fraud) if total_fraud else 0.0,
            }
        )
    groups_df = pd.DataFrame(rows, columns=AGREEMENT_GROUPS_COLUMNS)

    if int(groups_df["observation_count"].sum()) != n:
        raise Phase5Error(
            "agreement groups do not partition the sample "
            f"({int(groups_df['observation_count'].sum())} != {n})"
        )
    if int(groups_df["fraud_count"].sum()) != total_fraud:
        raise Phase5Error(
            "agreement-group fraud counts do not sum to the total fraud count"
        )
    return groups_df


# ---------------------------------------------------------------------------
# G. Fraud-discovery curve data
# ---------------------------------------------------------------------------

def compute_fraud_discovery_curve(
    aligned: Dict, run_ids: Optional[Sequence[str]] = None
) -> pd.DataFrame:
    """Recall and precision against review budget for every run (no plot).

    Each run's observations are ranked by descending ``anomaly_score`` under
    ``TIE_BREAK_POLICY`` (ground-truth labels are used ONLY post hoc, to
    evaluate the ranking). For every integer review budget
    ``b = 1..n`` the table reports the cumulative number of frauds found in
    the top-b ranked observations, the running precision (frauds found / b)
    and the running recall (frauds found / total frauds). The result is the
    numerical input for the Phase 5B discovery-curve plots.
    """
    run_ids = list(aligned["run_ids"]) if run_ids is None else list(run_ids)
    _require_runs(aligned, run_ids)

    labels = aligned["labels"]
    n = int(aligned["sample_size"])
    total_fraud = int(aligned["fraud_count"])
    if total_fraud < 1:
        raise Phase5Error("recall is undefined when the sample contains no fraud")

    budgets = np.arange(1, n + 1)
    frames = []
    for run_id in run_ids:
        order = np.argsort(-np.asarray(aligned["runs"][run_id]["anomaly_score"]), kind="stable")
        cumulative_frauds = np.cumsum(labels[order] == 1)
        frames.append(
            pd.DataFrame(
                {
                    "run_id": run_id,
                    "budget": budgets,
                    "fraud_found": cumulative_frauds,
                    "precision": cumulative_frauds / budgets,
                    "recall": cumulative_frauds / total_fraud,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)[FRAUD_DISCOVERY_CURVE_COLUMNS]


# ---------------------------------------------------------------------------
# Shared loading / validation
# ---------------------------------------------------------------------------

def _require_runs(aligned: Dict, run_ids: Sequence[str]) -> None:
    missing = [r for r in run_ids if r not in aligned["runs"]]
    if missing:
        raise Phase5Error(
            "runs missing from the aligned data: " + ", ".join(missing)
        )
    if len(set(run_ids)) != len(run_ids):
        raise Phase5Error("run_ids contains duplicates")


def _resolve_input_paths(
    evaluation_dataset_path: Optional[Path],
    phase4_run_metadata_path: Optional[Path],
) -> Tuple[Path, Path]:
    return (
        Path(evaluation_dataset_path)
        if evaluation_dataset_path is not None
        else config.PHASE4_EVALUATION_DATASET_PATH,
        Path(phase4_run_metadata_path)
        if phase4_run_metadata_path is not None
        else config.PHASE4_RUN_METADATA_JSON_PATH,
    )


def _artifact_info(path: Path) -> Dict:
    """Path + SHA-256 + size for a consumed input (provenance record)."""
    from mplad.common.manifest import artifact_entry

    info = artifact_entry(path)
    return {"path": str(path), **info}


def _load_and_validate_inputs(
    evaluation_dataset_path: Path,
    phase4_run_metadata_path: Path,
    expected_run_ids: Optional[Sequence[str]],
    verbose: bool = True,
    require_canonical_sample_size: bool = False,
) -> Dict:
    """Load and validate every input; compute no analysis.

    Order of operations: the optional Phase 4 output manifest is verified
    FIRST, so hash-verification genuinely happens before the artifacts are
    consumed.
    """
    pre_input_hashes = {}
    for key, p in (
        ("evaluation_dataset", evaluation_dataset_path),
        ("phase4_run_metadata", phase4_run_metadata_path),
    ):
        if Path(p).is_file():
            pre_input_hashes[key] = _artifact_info(Path(p))

    if verbose:
        print("Checking for the Phase 4 integrity manifest ...")
    input_manifest = _check_phase4_input_manifest(
        evaluation_dataset_path, phase4_run_metadata_path
    )
    if verbose:
        if input_manifest["mode"] == "manifest_verified":
            print(
                f"  manifest FOUND and VERIFIED: {input_manifest['path']} "
                f"({len(input_manifest['artifacts'])} artifact(s) hash-checked)"
            )
        else:
            print(
                "  no manifest at " + str(input_manifest["path"]) + " -> LEGACY "
                "UNMANIFESTED pair: strict structural validation + SHA-256 "
                "recording (verification NOT claimed)"
            )

    if verbose:
        print(f"Loading Phase 4 run metadata from {phase4_run_metadata_path} ...")
    run_metadata = load_phase4_run_metadata(phase4_run_metadata_path)
    metadata_summary = validate_phase4_run_metadata(run_metadata)
    if verbose:
        print(
            f"  provenance: {len(metadata_summary['run_ids'])} runs "
            f"({metadata_summary['run_ids'][0]} ... "
            f"{metadata_summary['run_ids'][-1]}), sample "
            f"{metadata_summary['sample_size']:,}, "
            f"{metadata_summary['fraud_count']} fraud labels"
        )

    if expected_run_ids is None:
        expected_run_ids = config.PHASE3_CANONICAL_RUN_IDS
    expected_run_ids = list(expected_run_ids)

    if verbose:
        print(f"Loading Phase 4 evaluation dataset from {evaluation_dataset_path} ...")
    dataset_df = load_phase4_dataset(evaluation_dataset_path, expected_run_ids, metadata_summary)
    dataset_summary = validate_phase4_dataset(dataset_df, expected_run_ids, metadata_summary)
    sample_size = dataset_summary["sample_size"]
    if verbose:
        print(
            f"  dataset: {dataset_summary['total_rows']:,} rows = "
            f"{len(expected_run_ids)} runs x {sample_size:,} observations "
            f"(identical row_id sequence across runs, verified)"
        )
    if sample_size != config.SAMPLE_SIZE_DEFAULT:
        if require_canonical_sample_size:
            raise Phase4DatasetError(
                f"Canonical Phase 5A execution requires sample_size="
                f"{config.SAMPLE_SIZE_DEFAULT:,}, got {sample_size:,}."
            )
        print(
            f"WARNING: the dataset sample size ({sample_size:,}) differs from "
            f"the established experiment size ({config.SAMPLE_SIZE_DEFAULT:,})."
        )

    aligned = extract_aligned_runs(dataset_df, expected_run_ids)
    if verbose:
        flags = dataset_summary["per_run_flagged_counts"]
        flag_range = f"{min(flags.values())}..{max(flags.values())}" if len(set(flags.values())) == 1 else "varies"
        print(
            f"  saved flags per run: {flag_range} | fraud labels in sample: "
            f"{dataset_summary['fraud_count']} "
            f"(prevalence {dataset_summary['fraud_prevalence']:.6f})"
        )

    post_input_hashes = {
        "evaluation_dataset": _artifact_info(evaluation_dataset_path),
        "phase4_run_metadata": _artifact_info(phase4_run_metadata_path),
    }
    for key, post_info in post_input_hashes.items():
        pre_info = pre_input_hashes.get(key)
        if pre_info is not None and (
            pre_info["sha256"] != post_info["sha256"]
            or pre_info["size_bytes"] != post_info["size_bytes"]
        ):
            raise Phase5Error(
                f"Input artifact '{key}' changed on disk during Phase 5A execution."
            )

    return {
        "run_metadata": run_metadata,
        "metadata_summary": metadata_summary,
        "dataset_df": dataset_df,
        "dataset_summary": dataset_summary,
        "aligned": aligned,
        "input_manifest": input_manifest,
        "input_hashes": post_input_hashes,
    }


# ---------------------------------------------------------------------------
# Provenance record
# ---------------------------------------------------------------------------

def _build_provenance_record(
    evaluation_dataset_path: Path,
    phase4_run_metadata_path: Path,
    validated: Dict,
    output_paths: Dict,
    bootstrap_params: Dict,
    multithreshold_details: Dict,
    run_mode: str,
) -> Dict:
    """Assemble the phase5_run_metadata.json payload (JSON-safe types)."""
    dataset_summary = validated["dataset_summary"]
    return {
        "phase": "5A",
        "stream": "A",
        "layer": "quantitative_diagnostic_analysis",
        "run_mode": run_mode,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": validated.get(
            "input_hashes",
            {
                "evaluation_dataset": _artifact_info(evaluation_dataset_path),
                "phase4_run_metadata": _artifact_info(phase4_run_metadata_path),
            }
        ),
        "input_manifest": validated["input_manifest"],
        "sample": {
            "sample_size": dataset_summary["sample_size"],
            "fraud_count": dataset_summary["fraud_count"],
            "fraud_prevalence": dataset_summary["fraud_prevalence"],
            "per_run_flagged_counts": dataset_summary["per_run_flagged_counts"],
        },
        "run_ids": list(dataset_summary["run_ids"]),
        "bootstrap": bootstrap_params,
        "analytical_conventions": {
            "score_orientation": (
                "anomaly_score from the Phase 4 evaluation dataset "
                "(higher = more anomalous); native_score never used for ranking"
            ),
            "fixed_threshold_policy": (
                "saved Phase 3 flags consumed exactly as supplied; the 1% "
                "rule is never recomputed or re-optimised"
            ),
            "spearman": (
                "Pearson correlation of tie-corrected average ranks "
                "(scipy.stats.rankdata) between anomaly_score vectors; the "
                "identical cross-run row_id sequence is validated first"
            ),
            "jaccard": (
                "intersection over union of the saved Phase 3 1% flags; "
                "two empty selections defined as 1.0"
            ),
            "multithreshold": multithreshold_details,
            "hypergeometric": {
                "null_model": NULL_MODEL_DESCRIPTION,
                "parameterisation": (
                    "P(X >= observed) with X ~ Hypergeometric(N=n, "
                    "successes=run_a flags, draws=run_b flags), evaluated "
                    "with scipy.stats.hypergeom.sf / logsf"
                ),
            },
            "agreement_groups": (
                "disjoint exhaustive partition (both / if_only / lof_only / "
                "neither) of the saved 1% flag pair; partition validated"
            ),
            "fraud_discovery_curve": (
                "ranking by descending anomaly_score under the shared "
                "tie-breaking policy; ground-truth labels used post hoc only"
            ),
            "tie_breaking": TIE_BREAK_POLICY,
        },
        "selection_caveat": EXPLORATORY_SELECTION_CAVEAT,
        "outputs": {k: str(v) for k, v in output_paths.items()},
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit-learn": sklearn.__version__,
            "scipy": scipy.__version__,
            "executable": sys.executable,
        },
        "model_fitting": {
            "models_fitted": 0,
            "note": (
                "Phase 5A is an analysis-only layer: no detector was "
                "constructed, fitted or refitted; Phase 4 scores and flags "
                "were consumed exactly as stored; no threshold was "
                "reselected and no plot was produced."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _output_paths(output_dir: Path) -> Dict:
    return {
        "bootstrap_metrics": output_dir / config.PHASE5_BOOTSTRAP_METRICS_FILENAME,
        "paired_bootstrap_differences": output_dir
        / config.PHASE5_PAIRED_BOOTSTRAP_DIFFERENCES_FILENAME,
        "pairwise_spearman": output_dir / config.PHASE5_PAIRWISE_SPEARMAN_FILENAME,
        "pairwise_jaccard_1pct": output_dir / config.PHASE5_PAIRWISE_JACCARD_FILENAME,
        "multithreshold_agreement": output_dir
        / config.PHASE5_MULTITHRESHOLD_AGREEMENT_FILENAME,
        "hypergeometric_overlap": output_dir
        / config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME,
        "agreement_groups": output_dir / config.PHASE5_AGREEMENT_GROUPS_FILENAME,
        "fraud_discovery_curve": output_dir / config.PHASE5_FRAUD_DISCOVERY_CURVE_FILENAME,
        "run_metadata": output_dir / config.PHASE5_RUN_METADATA_FILENAME,
        "manifest": output_dir / config.PHASE5_MANIFEST_FILENAME,
    }


def collect_phase5_preflight(
    evaluation_dataset_path: Optional[Path] = None,
    phase4_run_metadata_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    expected_run_ids: Optional[Sequence[str]] = None,
    n_replicates: int = config.PHASE5_BOOTSTRAP_REPLICATES_DEFAULT,
    bootstrap_seed: int = config.PHASE5_BOOTSTRAP_SEED_DEFAULT,
    overwrite: bool = False,
    verbose: bool = True,
    require_canonical_sample_size: bool = False,
) -> Dict:
    """Validate everything Phase 5A needs WITHOUT computing or writing.

    Verifies the optional Phase 4 output manifest, loads and validates the
    Phase 4 provenance record and the evaluation dataset (schema, run
    completeness, cross-run row_id consistency, finite scores, binary
    flags, orientation identity, provenance cross-checks) and extracts the
    aligned arrays -- so every failure mode of a real run is exercised here.
    No analysis is computed and no file is written (the output directory is
    not even created).
    """
    evaluation_dataset_path, phase4_run_metadata_path = _resolve_input_paths(
        evaluation_dataset_path, phase4_run_metadata_path
    )
    output_dir = Path(output_dir) if output_dir is not None else config.DEFAULT_PHASE5_OUTPUT_DIR
    paths = _output_paths(output_dir)

    validated = _load_and_validate_inputs(
        evaluation_dataset_path, phase4_run_metadata_path,
        expected_run_ids, verbose=verbose,
        require_canonical_sample_size=require_canonical_sample_size,
    )
    dataset_summary = validated["dataset_summary"]

    return {
        "evaluation_dataset_path": evaluation_dataset_path,
        "phase4_run_metadata_path": phase4_run_metadata_path,
        "input_manifest": validated["input_manifest"],
        "sample": {
            "sample_size": dataset_summary["sample_size"],
            "fraud_count": dataset_summary["fraud_count"],
            "fraud_prevalence": dataset_summary["fraud_prevalence"],
            "per_run_flagged_counts": dataset_summary["per_run_flagged_counts"],
        },
        "run_ids": list(dataset_summary["run_ids"]),
        "cross_run_alignment": {
            "join_key": config.ID_COLUMN,
            "identical_row_id_sequence_across_runs": True,
            "identical_class_sequence_across_runs": True,
            "positional_comparison_validated": True,
        },
        "analyses_planned": [
            "stratified_bootstrap (runs: " + ", ".join(config.PHASE5_BOOTSTRAP_RUN_IDS) + ")",
            "paired_bootstrap ("
            + config.PHASE5_PAIRED_COMPARISON_RUNS[1]
            + " - "
            + config.PHASE5_PAIRED_COMPARISON_RUNS[0]
            + ")",
            "pairwise_spearman_10x10",
            "pairwise_jaccard_1pct_10x10",
            "multithreshold_agreement ("
            + ", ".join(f"{p:g}%" for p in config.PHASE5_MULTI_THRESHOLD_PERCENTS)
            + ")",
            "hypergeometric_overlap ("
            + config.PHASE5_OVERLAP_RUN_A
            + " vs "
            + config.PHASE5_OVERLAP_RUN_B
            + ")",
            "agreement_groups ("
            + config.PHASE5_OVERLAP_RUN_A
            + " vs "
            + config.PHASE5_OVERLAP_RUN_B
            + ")",
            "fraud_discovery_curve (all runs)",
        ],
        "bootstrap_parameters": {
            "n_replicates": int(n_replicates),
            "seed": int(bootstrap_seed),
        },
        "outputs": {
            "directory": output_dir,
            "paths": paths,
            "exists": {k: Path(v).exists() for k, v in paths.items()},
            "overwrite": bool(overwrite),
            "blocked": bool(any(Path(v).exists() for v in paths.values()) and not overwrite),
        },
        "writes_performed": False,
        "analyses_computed": False,
        "models_fitted": 0,
    }


def run_phase5_analysis(
    evaluation_dataset_path: Optional[Path] = None,
    phase4_run_metadata_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    expected_run_ids: Optional[Sequence[str]] = None,
    n_replicates: int = config.PHASE5_BOOTSTRAP_REPLICATES_DEFAULT,
    bootstrap_seed: int = config.PHASE5_BOOTSTRAP_SEED_DEFAULT,
    overwrite: bool = False,
    verbose: bool = True,
    require_canonical_sample_size: bool = False,
) -> Dict:
    """Execute the Phase 5A quantitative diagnostic layer end to end.

    Steps: fail-fast output precheck -> verify the optional Phase 4 output
    manifest (or classify the inputs as a legacy unmanifested pair) -> load
    and validate the Phase 4 provenance record and evaluation dataset ->
    extract the aligned per-run arrays -> compute the bootstrap diagnostics
    (A), the Spearman (B) and Jaccard (C) matrices, the multi-threshold
    agreement (D), the hypergeometric overlap (E), the agreement groups (F)
    and the fraud-discovery curves (G) -> write the eight CSV tables, the
    provenance record and the output manifest.

    **No detector is ever fitted, no threshold is ever reselected and no
    plot is produced.** Existing output files are never replaced unless
    ``overwrite=True``.
    """
    evaluation_dataset_path, phase4_run_metadata_path = _resolve_input_paths(
        evaluation_dataset_path, phase4_run_metadata_path
    )
    output_dir = Path(output_dir) if output_dir is not None else config.DEFAULT_PHASE5_OUTPUT_DIR
    paths = _output_paths(output_dir)

    # Fail fast: refuse to compute if outputs exist and cannot be replaced.
    assert_outputs_writable(list(paths.values()), overwrite=overwrite)

    validated = _load_and_validate_inputs(
        evaluation_dataset_path, phase4_run_metadata_path,
        expected_run_ids, verbose=verbose,
        require_canonical_sample_size=require_canonical_sample_size,
    )
    aligned = validated["aligned"]

    # --- A. Bootstrap diagnostics --------------------------------------
    if verbose:
        print(
            f"\nRunning {int(n_replicates):,} stratified bootstrap replicates for "
            f"{', '.join(config.PHASE5_BOOTSTRAP_RUN_IDS)} ..."
        )
    bootstrap = run_bootstrap_diagnostics(
        aligned, n_replicates=n_replicates, seed=bootstrap_seed, verbose=verbose
    )

    # --- B/C. Pairwise matrices ----------------------------------------
    if verbose:
        print("Computing 10x10 pairwise Spearman and top-1% Jaccard matrices ...")
    spearman_df = compute_pairwise_spearman(aligned)
    jaccard_df = compute_pairwise_jaccard(aligned)

    # --- D. Multi-threshold agreement ----------------------------------
    if verbose:
        print(
            "Computing multi-threshold agreement ("
            + ", ".join(f"{p:g}%" for p in config.PHASE5_MULTI_THRESHOLD_PERCENTS)
            + ") ..."
        )
    agreement_table, multithreshold_details = compute_multithreshold_agreement(aligned)

    # --- E/F. Hypergeometric overlap + agreement groups -----------------
    run_a, run_b = config.PHASE5_OVERLAP_RUN_A, config.PHASE5_OVERLAP_RUN_B
    if verbose:
        print(f"Computing hypergeometric overlap and agreement groups ({run_a} vs {run_b}) ...")
    hypergeometric = compute_hypergeometric_overlap(
        aligned["runs"][run_a]["flag"],
        aligned["runs"][run_b]["flag"],
        n_observations=aligned["sample_size"],
        run_a=run_a,
        run_b=run_b,
    )
    agreement_groups_df = compute_agreement_groups(
        aligned["runs"][run_a]["flag"],
        aligned["runs"][run_b]["flag"],
        aligned["labels"],
        run_a=run_a,
        run_b=run_b,
    )

    # --- G. Fraud-discovery curves -------------------------------------
    if verbose:
        print("Computing fraud-discovery curve data for all runs ...")
    discovery_curve_df = compute_fraud_discovery_curve(aligned)

    hypergeometric_df = pd.DataFrame(
        [{k: v for k, v in hypergeometric.items() if k in HYPERGEOMETRIC_OVERLAP_COLUMNS}],
        columns=HYPERGEOMETRIC_OVERLAP_COLUMNS,
    )

    provenance = _build_provenance_record(
        evaluation_dataset_path,
        phase4_run_metadata_path,
        validated,
        paths,
        bootstrap_params=bootstrap["diagnostics"],
        multithreshold_details=multithreshold_details,
        run_mode="execute",
    )

    if verbose:
        print(f"\nSaving artifacts to {output_dir} ...")
    publish_phase5_artifacts(
        bootstrap_metrics=bootstrap["bootstrap_metrics"],
        paired_differences=bootstrap["paired_differences"],
        spearman_df=_matrix_with_row_labels(spearman_df),
        jaccard_df=_matrix_with_row_labels(jaccard_df),
        agreement_table=agreement_table,
        hypergeometric_df=hypergeometric_df,
        agreement_groups_df=agreement_groups_df,
        discovery_curve_df=discovery_curve_df,
        provenance=provenance,
        output_dir=output_dir,
        overwrite=overwrite,
    )

    if verbose:
        _print_execution_summary(
            validated, bootstrap, spearman_df, jaccard_df, hypergeometric,
            agreement_groups_df,
        )

    return {
        "bootstrap": bootstrap["bootstrap_metrics"],
        "bootstrap_diagnostics": bootstrap["diagnostics"],
        "replicate_values": bootstrap["replicate_values"],
        "point_estimates": bootstrap["point_estimates"],
        "paired_differences": bootstrap["paired_differences"],
        "spearman": spearman_df,
        "jaccard": jaccard_df,
        "multithreshold_agreement": agreement_table,
        "multithreshold_details": multithreshold_details,
        "hypergeometric": hypergeometric,
        "agreement_groups": agreement_groups_df,
        "fraud_discovery_curve": discovery_curve_df,
        "provenance": provenance,
        "input_manifest": validated["input_manifest"],
        "sample": validated["dataset_summary"],
        "paths": {
            "evaluation_dataset": evaluation_dataset_path,
            "phase4_run_metadata": phase4_run_metadata_path,
            **{k: Path(v) for k, v in paths.items()},
        },
    }


def _matrix_with_row_labels(matrix_df: pd.DataFrame) -> pd.DataFrame:
    """Convert a run-x-run matrix for CSV output: the row labels become an
    explicit leading ``run_id`` column (the guarded writer uses index=False,
    so without this the row labels would be silently dropped)."""
    return matrix_df.rename_axis("run_id").reset_index()


def _print_execution_summary(
    validated: Dict,
    bootstrap: Dict,
    spearman_df: pd.DataFrame,
    jaccard_df: pd.DataFrame,
    hypergeometric: Dict,
    agreement_groups_df: pd.DataFrame,
) -> None:
    """Print the computed headline values (for independent comparison)."""
    dataset_summary = validated["dataset_summary"]
    run_a, run_b = config.PHASE5_OVERLAP_RUN_A, config.PHASE5_OVERLAP_RUN_B

    print("\n=== PHASE 5A QUANTITATIVE DIAGNOSTICS (recalculated) ===")
    print(
        f"sample: {dataset_summary['sample_size']:,} observations, "
        f"{dataset_summary['fraud_count']} fraud labels"
    )
    flags = dataset_summary["per_run_flagged_counts"]
    print("saved 1% flags per run: " + ", ".join(f"{r}={flags[r]}" for r in flags))
    print(
        f"Spearman {run_a} vs {run_b}: "
        f"{spearman_df.loc[run_a, run_b]:.4f} | Top-1% Jaccard: "
        f"{jaccard_df.loc[run_a, run_b]:.4f}"
    )
    print(
        f"hypergeometric ({run_a} vs {run_b}): observed intersection "
        f"{hypergeometric['observed_intersection']}, union "
        f"{hypergeometric['union_size']}, expected "
        f"{hypergeometric['expected_intersection']:.2f}, enrichment "
        f"{hypergeometric['enrichment_observed_over_expected']:.2f}x, "
        f"log10 P(X>=observed) = {hypergeometric['log10_survival']:.2f}"
    )
    print("\nAgreement groups (canonical 1% flags):")
    print(agreement_groups_df.to_string(index=False))
    print("\nBootstrap point estimates and 95% percentile CIs:")
    print(bootstrap["bootstrap_metrics"].to_string(index=False))
    print("\nPaired bootstrap differences (" + bootstrap["paired_differences"]["comparison"].iloc[0] + "):")
    print(bootstrap["paired_differences"].to_string(index=False))
    print(f"\nNOTE: {EXPLORATORY_SELECTION_CAVEAT}")


def _format_problems(problems: List[str], category: str) -> str:
    lines = [f"Validation failed ({category}):"]
    lines.extend(f"  {i}. {p}" for i, p in enumerate(problems, start=1))
    return "\n".join(lines)
