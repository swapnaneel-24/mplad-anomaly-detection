"""Stream A -- Phase 4: label-based evaluation layer (compute only).

Role and boundaries
-------------------
Phase 4 consumes the **frozen Phase 3 canonical artifacts** (read-only):

* ``results/stream a/phase 3/phase3_canonical_predictions.pkl``
* ``results/stream a/phase 3/phase3_run_metadata.csv``

together with the separately stored ground truth
``data/processed/stream-a/labels/ground_truth_registry.csv`` (schema
``row_id, Class``; 284,807 unique row IDs and 492 positive labels on the
full registry, 47 positives inside the 30,000-row primary sample), and
produces a long-form evaluation dataset plus a per-run metrics table.

This module NEVER fits, refits, retunes or even constructs a detector. It
imports only ``sklearn.metrics``. Ground-truth labels are used exclusively
AFTER Phase 3 has produced its scores and flags -- never to select, modify
or re-threshold anything.

Historical bug this module makes impossible
--------------------------------------------
The original Colab Phase 4 sorted the ground truth by ``row_id`` while
leaving the prediction arrays in draw order, then aligned the two by ARRAY
POSITION. Every metric was computed against the wrong labels. The corrected
rule implemented here: predictions and labels are joined **on ``row_id``
with a validated one-to-one merge**, prediction order is preserved
end-to-end, and any unmatched or duplicated identifier is a hard error --
rows are never silently dropped or reordered.

Score orientation
-----------------
Phase 3 stores NATIVE estimator scores in which **lower = more anomalous**
(Isolation Forest ``decision_function``, LOF ``negative_outlier_factor_``).
Phase 4 makes the canonical orientation explicit::

    anomaly_score = -native_score

so that higher ``anomaly_score`` means more anomalous. Ranking metrics
(Average Precision, ROC-AUC) use ``anomaly_score``; the fixed-threshold
classification metrics use the **saved Phase 3 flags exactly as supplied**
(the post-hoc bottom-1% rule is never recomputed here).

Phase 3 integrity manifest
--------------------------
If a ``phase3_commit_manifest.json`` exists next to the Phase 3 artifacts,
its hashes are verified BEFORE anything is consumed. The hardened Stage 1
Phase 3 does not generate manifests, so on the current repository the
canonical inputs are handled as a **legacy unmanifested pair**: strict
structural validation, SHA-256 hashes recorded in the Phase 4 provenance
record, and an explicit statement that manifest verification was NOT
performed. Verification is never claimed falsely.
"""
from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from mplad.common import config
from mplad.common.io import (
    assert_outputs_writable,
    load_predictions_pickle,
    publish_phase4_artifacts,
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
    "Phase4Error",
    "GroundTruthRegistryError",
    "Phase3MetadataError",
    "PredictionBundleError",
    "LabelAlignmentError",
    "validate_ground_truth_registry",
    "load_ground_truth_registry",
    "validate_phase3_run_metadata",
    "load_phase3_run_metadata",
    "validate_prediction_bundle",
    "align_predictions_to_labels",
    "evaluate_single_run",
    "compute_phase4_metrics",
    "compare_metrics_to_reference",
    "collect_phase4_preflight",
    "run_phase4_evaluation",
    "EVALUATION_DATASET_COLUMNS",
    "METRIC_COLUMNS",
    "METRICS_TABLE_COLUMNS",
    "HISTORICAL_METRIC_COLUMN_ALIASES",
]


# ---------------------------------------------------------------------------
# Errors (all ValueError subclasses, matching the Phase 3 convention)
# ---------------------------------------------------------------------------

class Phase4Error(ValueError):
    """Base class for Phase 4 contract violations."""


class GroundTruthRegistryError(Phase4Error):
    """The ground-truth registry violates its contract."""


class Phase3MetadataError(Phase4Error):
    """The Phase 3 run-metadata CSV violates its contract."""


class PredictionBundleError(Phase4Error):
    """The Phase 3 prediction bundle violates its contract."""


class LabelAlignmentError(Phase4Error):
    """Predictions and labels cannot be aligned one-to-one on row_id."""


# ---------------------------------------------------------------------------
# Output schemas (documented in docs/phase4_contract.md)
# ---------------------------------------------------------------------------

#: Long-form evaluation dataset: one row per (run_id, row_id) observation.
EVALUATION_DATASET_COLUMNS: list = [
    "run_id",
    "row_id",
    "Class",
    "native_score",
    "anomaly_score",
    "flag",
]

#: The run-identifier column of the metrics table and reference tables.
RUN_ID_COLUMN: str = "run_id"

#: Metric columns calculated per run (snake_case).
METRIC_COLUMNS: list = [
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
]

#: Full metrics table: Phase 3 metadata passthrough (flagged_count is
#: cross-checked against the bundle during validation and then represented
#: by the recomputed metric column) followed by the metric columns.
METRICS_TABLE_COLUMNS: list = [
    "run_id",
    "model",
    "n_estimators",
    "max_samples",
    "random_state",
    "n_neighbors",
    "metric",
    "runtime_seconds",
    "threshold_rule",
] + METRIC_COLUMNS

#: Explicit mapping from historical Phase 4 metric column names to the
#: canonical snake_case Phase 4 schema.
HISTORICAL_METRIC_COLUMN_ALIASES: Dict[str, str] = {
    "AP (Layer 1)": "average_precision",
    "AP": "average_precision",
    "ROC_AUC (Layer 1)": "roc_auc",
    "ROC-AUC": "roc_auc",
    "ROC_AUC": "roc_auc",
    "Precision @1%": "precision_at_1pct",
    "Recall @1%": "recall_at_1pct",
    "F1 @1%": "f1_at_1pct",
    "TN": "tn",
    "FP": "fp",
    "FN": "fn",
    "TP": "tp",
    "Flagged_Count": "flagged_count",
}


# ---------------------------------------------------------------------------
# Ground-truth registry
# ---------------------------------------------------------------------------

def validate_ground_truth_registry(registry_df: pd.DataFrame) -> Dict:
    """Validate the ground-truth registry and return its summary counts.

    Contract (``row_id, Class`` only):

    1. a pandas DataFrame;
    2. both required columns present;
    3. no unexpected extra columns (the registry schema is frozen);
    4. ``row_id`` has no missing values and no duplicates;
    5. ``Class`` has no missing values (missing labels are rejected);
    6. ``Class`` is strictly binary -- only 0 and 1 are valid.

    Returns
    -------
    dict
        ``{"total_observations": n, "positive_labels": n_pos}`` -- the
        registry's total row count and its positive-label count.
    """
    if not isinstance(registry_df, pd.DataFrame):
        raise GroundTruthRegistryError(
            f"Expected a pandas DataFrame, got {type(registry_df).__name__}."
        )

    id_col, label_col = config.ID_COLUMN, config.LABEL_COLUMN
    columns = list(registry_df.columns)
    problems = []

    for col in (id_col, label_col):
        if col not in columns:
            problems.append(f"missing required column '{col}'")
    unexpected = [c for c in columns if c not in (id_col, label_col)]
    if unexpected:
        problems.append(
            "unexpected extra column(s): " + ", ".join(unexpected)
            + " -- the registry schema is frozen as 'row_id, Class'"
        )
    if problems:
        raise GroundTruthRegistryError(_format_problems(problems, "schema"))

    problems = []
    if registry_df[id_col].isna().any():
        problems.append(f"'{id_col}' contains missing values")
    duplicated = registry_df[id_col][registry_df[id_col].duplicated()]
    if not duplicated.empty:
        problems.append(
            f"'{id_col}' contains {len(duplicated)} duplicate value(s), "
            f"e.g. {sorted(duplicated.unique().tolist())[:5]}"
        )
    if registry_df[label_col].isna().any():
        n_missing = int(registry_df[label_col].isna().sum())
        problems.append(
            f"'{label_col}' contains {n_missing} missing label(s) -- every "
            f"registry row must carry a label"
        )
    valid = config.VALID_LABEL_VALUES
    invalid_mask = ~registry_df[label_col].isin(valid)
    if invalid_mask.any():
        bad = registry_df.loc[invalid_mask, label_col].unique().tolist()
        problems.append(
            f"'{label_col}' contains non-binary value(s): {bad[:5]} -- only "
            f"{list(valid)} are valid"
        )
    if problems:
        raise GroundTruthRegistryError(_format_problems(problems, "integrity"))

    return {
        "total_observations": int(len(registry_df)),
        "positive_labels": int(registry_df[label_col].sum()),
    }


def load_ground_truth_registry(path: Path) -> pd.DataFrame:
    """Load and validate the ground-truth registry CSV.

    Returns the validated frame (columns ``row_id`` and ``Class``, file
    order preserved -- the order is irrelevant because alignment is by key).
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f"Ground-truth registry not found: {path}\n"
            f"Expected the frozen label store at "
            f"{config.DEFAULT_GROUND_TRUTH_PATH}. Pass --ground-truth if it "
            f"lives somewhere else."
        )
    registry_df = pd.read_csv(path)
    validate_ground_truth_registry(registry_df)
    return registry_df


# ---------------------------------------------------------------------------
# Phase 3 run metadata
# ---------------------------------------------------------------------------

def validate_phase3_run_metadata(
    metadata_df: pd.DataFrame,
    expected_run_ids: Optional[Sequence[str]] = None,
) -> List[str]:
    """Validate a Phase 3 run-metadata frame; return the ordered run IDs.

    Validates: a pandas DataFrame; the exact frozen column schema
    (``config.METADATA_COLUMNS``); unique non-null ``run_id`` values; a
    run-ID set equal to ``expected_run_ids`` (default: the ten canonical
    Phase 3 runs); and an integral, non-negative ``flagged_count`` (used for
    the bundle cross-check).
    """
    if expected_run_ids is None:
        expected_run_ids = config.PHASE3_CANONICAL_RUN_IDS
    expected_run_ids = list(expected_run_ids)

    if not isinstance(metadata_df, pd.DataFrame):
        raise Phase3MetadataError(
            f"Expected a pandas DataFrame, got {type(metadata_df).__name__}."
        )
    columns = list(metadata_df.columns)
    problems = []

    missing = [c for c in config.METADATA_COLUMNS if c not in columns]
    if missing:
        problems.append("missing column(s): " + ", ".join(missing))
    unexpected = [c for c in columns if c not in config.METADATA_COLUMNS]
    if unexpected:
        problems.append(
            "unexpected extra column(s): " + ", ".join(unexpected)
            + " -- the Phase 3 metadata schema is frozen"
        )
    if "run_id" in columns and metadata_df["run_id"].isna().any():
        problems.append("'run_id' contains missing values")
    if "run_id" in columns:
        dup = metadata_df["run_id"][metadata_df["run_id"].duplicated()]
        if not dup.empty:
            problems.append(f"'run_id' contains {len(dup)} duplicate value(s)")
    if problems:
        raise Phase3MetadataError(_format_problems(problems, "schema"))

    actual = set(metadata_df["run_id"].tolist())
    expected = set(expected_run_ids)
    missing_runs = sorted(expected - actual)
    unexpected_runs = sorted(actual - expected)
    if missing_runs or unexpected_runs:
        parts = []
        if missing_runs:
            parts.append("missing run(s): " + ", ".join(missing_runs))
        if unexpected_runs:
            parts.append("unexpected run(s): " + ", ".join(unexpected_runs))
        raise Phase3MetadataError(
            "Phase 3 metadata run IDs do not match the expected experiment runs "
            f"({len(expected_run_ids)} expected). " + "; ".join(parts)
        )

    flagged = metadata_df["flagged_count"]
    if not pd.api.types.is_numeric_dtype(flagged):
        raise Phase3MetadataError("'flagged_count' must be numeric")
    flagged_arr = flagged.to_numpy(dtype=float, na_value=np.nan)
    if not np.isfinite(flagged_arr).all():
        raise Phase3MetadataError(
            "'flagged_count' must contain finite non-negative integers "
            "(NaN and +/-inf are rejected)"
        )
    if (flagged_arr < 0).any() or not np.allclose(flagged_arr, np.round(flagged_arr)):
        raise Phase3MetadataError(
            "'flagged_count' must contain non-negative integers "
            "(used for the bundle cross-check)"
        )

    # Validate that each run_id maps to its intended model and frozen hyperparameters
    canonical_expected = {}
    for i, cfg in enumerate(config.ISOLATION_FOREST_CONFIGS, start=1):
        canonical_expected[f"IF_{i:03d}"] = {"model": config.MODEL_NAME_IF, **cfg}
    for i, cfg in enumerate(config.LOF_CONFIGS, start=1):
        canonical_expected[f"LOF_{i:03d}"] = {"model": config.MODEL_NAME_LOF, **cfg}

    for _, row in metadata_df.iterrows():
        rid = str(row["run_id"])
        model_val = str(row["model"])
        if rid.startswith("IF_") and model_val != config.MODEL_NAME_IF:
            raise Phase3MetadataError(
                f"run '{rid}': expected model '{config.MODEL_NAME_IF}', got '{model_val}'"
            )
        if rid.startswith("LOF_") and model_val != config.MODEL_NAME_LOF:
            raise Phase3MetadataError(
                f"run '{rid}': expected model '{config.MODEL_NAME_LOF}', got '{model_val}'"
            )
        if rid in canonical_expected and set(expected_run_ids) == set(config.PHASE3_CANONICAL_RUN_IDS):
            exp = canonical_expected[rid]
            if rid.startswith("IF_"):
                if (
                    pd.isna(row["n_estimators"])
                    or int(round(float(row["n_estimators"]))) != int(exp["n_estimators"])
                    or pd.isna(row["max_samples"])
                    or not np.isclose(float(row["max_samples"]), float(exp["max_samples"]))
                    or pd.isna(row["random_state"])
                    or int(round(float(row["random_state"]))) != int(exp["random_state"])
                ):
                    raise Phase3MetadataError(
                        f"run '{rid}': hyperparameters do not match frozen configuration {exp}"
                    )
            elif rid.startswith("LOF_"):
                if (
                    pd.isna(row["n_neighbors"])
                    or int(round(float(row["n_neighbors"]))) != int(exp["n_neighbors"])
                    or str(row["metric"]) != str(exp["metric"])
                ):
                    raise Phase3MetadataError(
                        f"run '{rid}': hyperparameters do not match frozen configuration {exp}"
                    )

    return metadata_df["run_id"].tolist()


def load_phase3_run_metadata(
    path: Path,
    expected_run_ids: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """Load and validate the Phase 3 run-metadata CSV.

    Returns the validated frame in file order (the canonical artifact lists
    IF_001..IF_005 then LOF_001..LOF_005).
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f"Phase 3 run metadata not found: {path}\n"
            f"Expected the frozen artifact at {config.PHASE3_RUN_METADATA_PATH}. "
            f"Pass --run-metadata if it lives somewhere else."
        )
    metadata_df = pd.read_csv(path)
    validate_phase3_run_metadata(metadata_df, expected_run_ids)
    return metadata_df


# ---------------------------------------------------------------------------
# Phase 3 prediction bundle
# ---------------------------------------------------------------------------

def validate_prediction_bundle(bundle: object, metadata_df: pd.DataFrame) -> Dict:
    """Validate the Phase 3 prediction bundle against its contract.

    Real structure (verified against the canonical artifact)::

        {'row_ids': <1-D int array, the shared experiment sample>,
         'predictions': {run_id: {'scores': float32 array,
                                  'flags':   uint8  array}}}

    Checks: exact bundle keys; a single shared, unique, integer row-ID
    sequence; the run-ID set equals the metadata run IDs (no missing, no
    unexpected); per-run ``scores``/``flags`` keys; 1-D floating scores of
    the right length with finite values; 1-D binary flags of the right
    length; and per-run flag counts equal to the metadata ``flagged_count``
    (the two Phase 3 artifacts must agree with each other).

    Returns a summary dict (sample size, run IDs, dtypes). Never mutates or
    reorders anything inside the bundle.
    """
    if not isinstance(bundle, dict):
        raise PredictionBundleError(
            f"Prediction bundle must be a dict, got {type(bundle).__name__}."
        )
    problems = []

    bundle_keys = set(bundle)
    if bundle_keys != {"row_ids", "predictions"}:
        problems.append(
            f"bundle keys must be exactly {{'row_ids', 'predictions'}}, got "
            f"{sorted(bundle_keys)}"
        )
        raise PredictionBundleError(_format_problems(problems, "schema"))

    row_ids = np.asarray(bundle["row_ids"])
    if row_ids.ndim != 1:
        problems.append(f"'row_ids' must be 1-D, got shape {row_ids.shape}")
    elif row_ids.dtype.kind not in "iu":
        problems.append(
            f"'row_ids' must have an integer dtype, got {row_ids.dtype}"
        )
    elif np.unique(row_ids).size != row_ids.shape[0]:
        problems.append(
            f"'row_ids' contains {row_ids.shape[0] - np.unique(row_ids).size} "
            "duplicate value(s) -- prediction IDs must be unique"
        )
    elif row_ids.shape[0] == 0:
        problems.append("'row_ids' is empty")
    if problems:
        raise PredictionBundleError(_format_problems(problems, "row_ids"))

    sample_size = int(row_ids.shape[0])

    predictions = bundle["predictions"]
    if not isinstance(predictions, dict) or not predictions:
        raise PredictionBundleError(
            "'predictions' must be a non-empty dict of {run_id: {'scores','flags'}}"
        )

    metadata_runs = metadata_df["run_id"].tolist()
    metadata_flagged = metadata_df.set_index("run_id")["flagged_count"].to_dict()

    missing_runs = [r for r in metadata_runs if r not in predictions]
    unexpected_runs = [r for r in predictions if r not in metadata_runs]
    if missing_runs or unexpected_runs:
        parts = []
        if missing_runs:
            parts.append("missing run(s): " + ", ".join(missing_runs))
        if unexpected_runs:
            parts.append("unexpected run(s): " + ", ".join(unexpected_runs))
        raise PredictionBundleError(
            "Prediction bundle run IDs do not match the Phase 3 metadata. "
            + "; ".join(parts)
        )

    score_dtypes: Dict[str, str] = {}
    flag_dtypes: Dict[str, str] = {}
    for run_id in metadata_runs:
        entry = predictions[run_id]
        if not isinstance(entry, dict) or set(entry) != {"scores", "flags"}:
            raise PredictionBundleError(
                f"run '{run_id}': entry must be a dict with exactly "
                f"{{'scores', 'flags'}}, got "
                f"{sorted(entry) if isinstance(entry, dict) else type(entry).__name__}"
            )
        scores = np.asarray(entry["scores"])
        flags = np.asarray(entry["flags"])

        if scores.ndim != 1 or scores.shape[0] != sample_size:
            raise PredictionBundleError(
                f"run '{run_id}': 'scores' must be 1-D of length {sample_size}, "
                f"got shape {scores.shape}"
            )
        if not np.issubdtype(scores.dtype, np.floating):
            raise PredictionBundleError(
                f"run '{run_id}': 'scores' must have a floating dtype, got {scores.dtype}"
            )
        if not np.isfinite(scores).all():
            n_bad = int((~np.isfinite(scores)).sum())
            raise PredictionBundleError(
                f"run '{run_id}': 'scores' contains {n_bad} non-finite value(s) "
                "(NaN or +/-inf) -- scores must be finite"
            )
        if flags.ndim != 1 or flags.shape[0] != sample_size:
            raise PredictionBundleError(
                f"run '{run_id}': 'flags' must be 1-D of length {sample_size}, "
                f"got shape {flags.shape}"
            )
        if not np.isin(flags, (0, 1)).all():
            raise PredictionBundleError(
                f"run '{run_id}': 'flags' must be binary (0/1), found values "
                f"{np.unique(flags).tolist()[:5]}"
            )

        actual_flagged = int(np.count_nonzero(flags == 1))
        expected_flagged = int(round(float(metadata_flagged[run_id])))
        if actual_flagged != expected_flagged:
            raise PredictionBundleError(
                f"run '{run_id}': flag count mismatch between the Phase 3 "
                f"artifacts (metadata flagged_count={expected_flagged}, bundle "
                f"contains {actual_flagged}) -- the pickle and the metadata "
                f"disagree; refusing to evaluate"
            )
        score_dtypes[run_id] = str(scores.dtype)
        flag_dtypes[run_id] = str(flags.dtype)

    return {
        "sample_size": sample_size,
        "run_ids": list(metadata_runs),
        "score_dtypes": score_dtypes,
        "flag_dtypes": flag_dtypes,
    }


# ---------------------------------------------------------------------------
# Phase 3 input manifest (optional) / legacy handling
# ---------------------------------------------------------------------------

def _check_phase3_input_manifest(predictions_path: Path, run_metadata_path: Path) -> Dict:
    """Verify an optional Phase 3 manifest, or classify the inputs as legacy.

    A manifest is expected at
    ``<predictions directory>/phase3_commit_manifest.json``. If present, every
    listed artifact is hash-verified and the manifest must cover the two
    consumed Phase 3 outputs; any mismatch is a hard error raised BEFORE the
    artifacts are consumed.

    If absent (the current repository state: the hardened Stage 1 Phase 3
    predates manifest generation), the inputs are marked as a legacy
    unmanifested pair. Structural validation and SHA-256 recording are then
    the integrity controls, and this function's result says so explicitly --
    manifest verification is never claimed when none was performed.
    """
    manifest_path = Path(predictions_path).parent / config.PHASE3_MANIFEST_FILENAME
    if not manifest_path.is_file():
        return {
            "present": False,
            "verified": False,
            "mode": "legacy_unmanifested",
            "path": str(manifest_path),
            "note": (
                "No Phase 3 commit manifest exists (the canonical Phase 3 "
                "artifacts predate manifest generation). Strict structural "
                "validation was applied and the input SHA-256 hashes are "
                "recorded in this provenance record. Manifest verification "
                "was NOT performed."
            ),
        }

    manifest_dir = manifest_path.parent.resolve()
    pred_resolved = Path(predictions_path).resolve()
    meta_resolved = Path(run_metadata_path).resolve()
    if pred_resolved.parent != manifest_dir or meta_resolved.parent != manifest_dir:
        raise ManifestVerificationError(
            "Phase 3 manifest verification failed: when a Phase 3 manifest is "
            f"present at {manifest_path}, both predictions ({pred_resolved}) and "
            f"run_metadata ({meta_resolved}) must resolve to the manifest "
            f"directory ({manifest_dir})."
        )

    manifest = load_manifest(manifest_path)
    report = verify_manifest(
        manifest,
        base_dir=manifest_path.parent,
        required_artifacts=(
            pred_resolved.name,
            meta_resolved.name,
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
# Label alignment (the row_id-join that replaces the historical bug)
# ---------------------------------------------------------------------------

def align_predictions_to_labels(
    bundle: Dict,
    registry_df: pd.DataFrame,
    run_ids: Sequence[str],
) -> pd.DataFrame:
    """Align predictions and labels on ``row_id``; preserve prediction order.

    The bundle carries ONE shared row-ID sequence for the whole experiment;
    the ground truth is joined onto it with a **validated one-to-one merge**
    (``pandas.merge(..., validate='one_to_one')``) on ``row_id``, using a
    left join so the prediction sequence is preserved exactly. Registry rows
    outside the experiment sample are simply not part of the evaluation; the
    prediction side, however, must match the registry completely:

    * any prediction ``row_id`` missing from the registry is a hard error
      (unmatched IDs are listed, never silently dropped);
    * a changed row count after the join is a hard error (incomplete join);
    * neither side may contain duplicate IDs (already rejected upstream).

    Then, for each run in ``run_ids`` (the Phase 3 metadata order), the
    per-run scores and flags are attached positionally to that SAME shared,
    already-aligned sequence -- which is exactly how Phase 3 produced them --
    and the canonical orientation is made explicit::

        anomaly_score = -native_score

    Returns the long-form frame with columns
    ``[run_id, row_id, Class, native_score, anomaly_score, flag]``, one row
    per (run_id, row_id).
    """
    row_ids = np.asarray(bundle["row_ids"])
    id_col, label_col = config.ID_COLUMN, config.LABEL_COLUMN

    registry = registry_df[[id_col, label_col]]
    labels = pd.DataFrame({id_col: row_ids})
    aligned = labels.merge(registry, on=id_col, how="left", validate="one_to_one")

    if len(aligned) != len(labels):
        raise LabelAlignmentError(
            f"the row_id join changed the row count ({len(labels)} -> "
            f"{len(aligned)}); an incomplete join must never happen silently"
        )
    unmatched_mask = aligned[label_col].isna()
    if unmatched_mask.any():
        missing = aligned.loc[unmatched_mask, id_col].tolist()
        raise LabelAlignmentError(
            f"{len(missing)} prediction row_id(s) have no entry in the "
            f"ground-truth registry, e.g. {missing[:5]} -- unmatched "
            f"prediction IDs are rejected, never dropped"
        )

    class_values = aligned[label_col].to_numpy()
    frames = []
    for run_id in run_ids:
        entry = bundle["predictions"][run_id]
        native_scores = np.asarray(entry["scores"])
        flags = np.asarray(entry["flags"])
        frames.append(
            pd.DataFrame(
                {
                    "run_id": run_id,
                    "row_id": row_ids,
                    "Class": class_values,
                    "native_score": native_scores,
                    "anomaly_score": -native_scores,  # canonical: higher = more anomalous
                    "flag": flags,
                }
            )
        )
    evaluation_dataset = pd.concat(frames, ignore_index=True)
    return evaluation_dataset[EVALUATION_DATASET_COLUMNS]


# ---------------------------------------------------------------------------
# Per-run evaluation
# ---------------------------------------------------------------------------

def evaluate_single_run(run_id: str, run_frame: pd.DataFrame) -> Dict:
    """Compute the Phase 4 metrics for one run from its aligned frame.

    Ranking metrics (on ``anomaly_score``, higher = more anomalous):
    Average Precision and ROC-AUC. Fixed-threshold metrics (on the SAVED
    Phase 3 flags -- never recomputed): Precision/Recall/F1 @1%, and the
    confusion counts TN/FP/FN/TP. Plus the sample bookkeeping columns.

    ``pos_label=1`` and ``zero_division=0`` are used throughout. A run whose
    sample contains a single class is rejected: AP and ROC-AUC are undefined
    there and silently returning a number would be dishonest.
    """
    y_true = run_frame[config.LABEL_COLUMN].to_numpy()
    anomaly_score = run_frame["anomaly_score"].to_numpy()
    flag = run_frame["flag"].to_numpy()

    unique_labels = np.unique(y_true)
    if unique_labels.size < 2:
        raise Phase4Error(
            f"run '{run_id}': the aligned sample contains a single ground-truth "
            f"class ({unique_labels.tolist()}); ranking metrics are undefined"
        )

    tn, fp, fn, tp = (int(v) for v in confusion_matrix(y_true, flag, labels=[0, 1]).ravel())
    sample_size = int(len(run_frame))
    fraud_count = int(np.count_nonzero(y_true == 1))
    flagged_count = int(np.count_nonzero(flag == 1))

    return {
        "run_id": run_id,
        "average_precision": float(average_precision_score(y_true, anomaly_score)),
        "roc_auc": float(roc_auc_score(y_true, anomaly_score)),
        "precision_at_1pct": float(precision_score(y_true, flag, pos_label=1, zero_division=0)),
        "recall_at_1pct": float(recall_score(y_true, flag, pos_label=1, zero_division=0)),
        "f1_at_1pct": float(f1_score(y_true, flag, pos_label=1, zero_division=0)),
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "sample_size": sample_size,
        "fraud_count": fraud_count,
        "fraud_prevalence": fraud_count / sample_size,
        "flagged_count": flagged_count,
        "flagged_proportion": flagged_count / sample_size,
    }


def compute_phase4_metrics(
    evaluation_dataset: pd.DataFrame,
    metadata_df: pd.DataFrame,
) -> pd.DataFrame:
    """Evaluate every run and join the Phase 3 metadata one-to-one.

    One metrics row per run, in Phase 3 metadata order. The metadata join is
    validated one-to-one on ``run_id``. The metadata ``flagged_count`` is
    intentionally not duplicated: it was cross-checked against the bundle
    during validation and the recomputed ``flagged_count`` metric column
    carries the value forward.
    """
    eval_runs = set(evaluation_dataset["run_id"].unique().tolist())
    metadata_runs = set(metadata_df["run_id"].tolist())
    if eval_runs != metadata_runs:
        raise Phase4Error(
            "evaluation dataset runs do not match the Phase 3 metadata runs "
            f"(missing: {sorted(metadata_runs - eval_runs)}, unexpected: "
            f"{sorted(eval_runs - metadata_runs)})"
        )

    metric_rows = [
        evaluate_single_run(run_id, run_frame)
        for run_id, run_frame in evaluation_dataset.groupby("run_id", sort=False)
    ]
    metrics_df = pd.DataFrame(metric_rows)

    metadata_passthrough = metadata_df.drop(
        columns=["flagged_count"], errors="ignore"
    )
    joined = metadata_passthrough.merge(
        metrics_df, on="run_id", how="left", validate="one_to_one"
    )
    if len(joined) != len(metadata_df):
        raise Phase4Error(
            "the metadata/metrics join changed the row count -- an incomplete "
            "join must never happen silently"
        )
    return joined[METRICS_TABLE_COLUMNS].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Post-hoc reference comparison (acceptance checks; never metric computation)
# ---------------------------------------------------------------------------

def compare_metrics_to_reference(
    metrics_df: pd.DataFrame,
    reference_df: pd.DataFrame,
    expected_run_ids: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """Compare recalculated metrics against an external reference table.

    Supports both the canonical snake_case Phase 4 schema and the historical
    Phase 4 column names via ``HISTORICAL_METRIC_COLUMN_ALIASES``. Only
    meaningful evaluation metrics and confusion/sample counts in
    ``METRIC_COLUMNS`` are compared (never ``runtime_seconds`` or model
    hyperparameters). Complete run-ID coverage is required: partial overlap of
    run IDs is rejected.
    """
    for name, frame in (("metrics_df", metrics_df), ("reference_df", reference_df)):
        if RUN_ID_COLUMN not in frame.columns:
            raise Phase4Error(f"{name} must contain a 'run_id' column")
        if frame[RUN_ID_COLUMN].isna().any() or frame[RUN_ID_COLUMN].duplicated().any():
            raise Phase4Error(f"{name} 'run_id' column must contain unique non-null IDs")

    metrics_runs = set(metrics_df[RUN_ID_COLUMN].tolist())
    ref_runs = set(reference_df[RUN_ID_COLUMN].tolist())
    shared_runs = sorted(metrics_runs & ref_runs)
    if not shared_runs:
        raise Phase4Error(
            "no shared run_id between the recalculated metrics and the reference"
        )
    if expected_run_ids is not None:
        exp_set = set(expected_run_ids)
        if ref_runs != exp_set or metrics_runs != exp_set:
            raise Phase4Error(
                f"reference comparison requires all {len(exp_set)} expected run IDs "
                f"(missing in reference: {sorted(exp_set - ref_runs)}, "
                f"unexpected in reference: {sorted(ref_runs - exp_set)})"
            )
    if metrics_runs != ref_runs:
        raise Phase4Error(
            "reference run_id set does not match recalculated metrics; "
            f"missing in reference: {sorted(metrics_runs - ref_runs)}, "
            f"unexpected in reference: {sorted(ref_runs - metrics_runs)}"
        )

    rename_map = {
        legacy: canon
        for legacy, canon in HISTORICAL_METRIC_COLUMN_ALIASES.items()
        if legacy in reference_df.columns and canon not in reference_df.columns
    }
    ref_normalized = reference_df.rename(columns=rename_map)

    allowed_metrics = set(METRIC_COLUMNS)
    shared_columns = [
        c for c in METRIC_COLUMNS
        if c in metrics_df.columns
        and c in ref_normalized.columns
        and c in allowed_metrics
        and pd.api.types.is_numeric_dtype(metrics_df[c])
        and pd.api.types.is_numeric_dtype(ref_normalized[c])
    ]
    if not shared_columns:
        raise Phase4Error("no shared numeric metric columns between metrics and reference")

    exact_count_columns = {
        "tn", "fp", "fn", "tp", "sample_size", "fraud_count", "flagged_count",
    }
    ordered_runs = [r for r in metrics_df[RUN_ID_COLUMN].tolist() if r in ref_runs]

    rows = []
    metrics_indexed = metrics_df.set_index(RUN_ID_COLUMN)
    reference_indexed = ref_normalized.set_index(RUN_ID_COLUMN)
    for run_id in ordered_runs:
        for column in shared_columns:
            recalculated = metrics_indexed.loc[run_id, column]
            reference = reference_indexed.loc[run_id, column]
            both_nan = pd.isna(recalculated) and pd.isna(reference)
            if both_nan:
                matches = True
                diff = None
            elif column in exact_count_columns:
                matches = int(round(float(recalculated))) == int(round(float(reference)))
                diff = abs(float(recalculated) - float(reference))
            else:
                matches = round(float(recalculated), 4) == round(float(reference), 4)
                diff = abs(float(recalculated) - float(reference))
            rows.append(
                {
                    "run_id": run_id,
                    "metric": column,
                    "reference": reference,
                    "recalculated": recalculated,
                    "abs_diff": diff,
                    "matches_rounded_reference": bool(matches),
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Shared loading / validation
# ---------------------------------------------------------------------------

def _resolve_input_paths(
    predictions_path: Optional[Path],
    run_metadata_path: Optional[Path],
    ground_truth_path: Optional[Path],
) -> Tuple[Path, Path, Path]:
    return (
        Path(predictions_path) if predictions_path is not None else config.PHASE3_PREDICTIONS_PATH,
        Path(run_metadata_path) if run_metadata_path is not None else config.PHASE3_RUN_METADATA_PATH,
        Path(ground_truth_path) if ground_truth_path is not None else config.DEFAULT_GROUND_TRUTH_PATH,
    )


def _artifact_info(path: Path) -> Dict:
    """Path + SHA-256 + size for a consumed input (provenance record)."""
    from mplad.common.manifest import artifact_entry

    info = artifact_entry(path)
    return {"path": str(path), **info}


def _load_and_validate_inputs(
    predictions_path: Path,
    run_metadata_path: Path,
    ground_truth_path: Path,
    expected_run_ids: Optional[Sequence[str]],
    verbose: bool = True,
    require_canonical_sample_size: bool = False,
) -> Dict:
    """Load and validate every input; align labels; compute nothing else.

    Order of operations: the optional Phase 3 manifest is verified FIRST, so
    hash-verification genuinely happens before the artifacts are consumed.
    """
    if verbose:
        print(f"Checking for Phase 3 integrity manifest ...")
    input_manifest = _check_phase3_input_manifest(predictions_path, run_metadata_path)
    if verbose:
        if input_manifest["mode"] == "manifest_verified":
            print(
                f"  manifest FOUND and VERIFIED: {input_manifest['path']} "
                f"({len(input_manifest['artifacts'])} artifact(s) hash-checked)"
            )
        else:
            print(
                "  no manifest at "
                f"{input_manifest['path']} -> LEGACY UNMANIFESTED pair: strict "
                "structural validation + SHA-256 recording (verification NOT claimed)"
            )

    # Pre-hash existing input files before consumption to bind provenance to exact bytes read
    pre_input_hashes = {}
    for key, p in (
        ("predictions", predictions_path),
        ("run_metadata", run_metadata_path),
        ("ground_truth", ground_truth_path),
    ):
        if Path(p).is_file():
            pre_input_hashes[key] = _artifact_info(Path(p))

    if verbose:
        print(f"Loading ground-truth registry from {ground_truth_path} ...")
    registry_df = load_ground_truth_registry(ground_truth_path)
    registry_summary = validate_ground_truth_registry(registry_df)
    if verbose:
        print(
            f"  registry: {registry_summary['total_observations']:,} observations, "
            f"{registry_summary['positive_labels']:,} positive labels"
        )

    if verbose:
        print(f"Loading Phase 3 run metadata from {run_metadata_path} ...")
    metadata_df = load_phase3_run_metadata(run_metadata_path, expected_run_ids)
    run_ids = metadata_df["run_id"].tolist()
    if verbose:
        print(f"  metadata: {len(run_ids)} runs ({run_ids[0]} ... {run_ids[-1]})")

    if verbose:
        print(f"Loading Phase 3 prediction bundle from {predictions_path} ...")
    bundle = load_predictions_pickle(predictions_path)
    bundle_summary = validate_prediction_bundle(bundle, metadata_df)
    sample_size = bundle_summary["sample_size"]
    if verbose:
        print(
            f"  bundle: {len(run_ids)} runs x {sample_size:,} observations "
            f"(shared row-ID sequence, scores "
            f"{sorted(set(bundle_summary['score_dtypes'].values()))})"
        )
    if sample_size != config.SAMPLE_SIZE_DEFAULT:
        if require_canonical_sample_size:
            raise PredictionBundleError(
                f"Canonical Phase 4 execution requires sample_size="
                f"{config.SAMPLE_SIZE_DEFAULT:,}, got {sample_size:,}."
            )
        print(
            f"WARNING: the bundle sample size ({sample_size:,}) differs from the "
            f"established experiment size ({config.SAMPLE_SIZE_DEFAULT:,})."
        )

    if verbose:
        print("Aligning predictions to labels on row_id (validated one-to-one) ...")
    evaluation_dataset = align_predictions_to_labels(bundle, registry_df, run_ids)
    if verbose:
        outside = registry_summary["total_observations"] - sample_size
        print(
            f"  aligned: {sample_size:,} matched prediction IDs, "
            f"{outside:,} registry rows outside the sample (unused, as expected)"
        )

    sample_frauds = int(
        evaluation_dataset.loc[
            evaluation_dataset["run_id"] == run_ids[0], config.LABEL_COLUMN
        ].sum()
    )
    sample_summary = {
        "sample_size": sample_size,
        "fraud_count": sample_frauds,
        "fraud_prevalence": sample_frauds / sample_size,
    }
    if verbose:
        print(
            f"  sample: {sample_frauds} fraud labels in the {sample_size:,}-row "
            f"sample (prevalence {sample_summary['fraud_prevalence']:.6f})"
        )

    post_input_hashes = {
        "predictions": _artifact_info(predictions_path),
        "run_metadata": _artifact_info(run_metadata_path),
        "ground_truth": _artifact_info(ground_truth_path),
    }
    for key, post_info in post_input_hashes.items():
        pre_info = pre_input_hashes.get(key)
        if pre_info is not None and (
            pre_info["sha256"] != post_info["sha256"]
            or pre_info["size_bytes"] != post_info["size_bytes"]
        ):
            raise Phase4Error(
                f"Input artifact '{key}' changed on disk during Phase 4 execution."
            )

    return {
        "registry_df": registry_df,
        "metadata_df": metadata_df,
        "bundle": bundle,
        "run_ids": run_ids,
        "evaluation_dataset": evaluation_dataset,
        "registry_summary": registry_summary,
        "sample_summary": sample_summary,
        "bundle_summary": bundle_summary,
        "input_manifest": input_manifest,
        "input_hashes": post_input_hashes,
    }


def _build_provenance_record(
    predictions_path: Path,
    run_metadata_path: Path,
    ground_truth_path: Path,
    validated: Dict,
    output_paths: Dict,
    run_mode: str,
    reference_info: Optional[Dict] = None,
) -> Dict:
    """Assemble the phase4_run_metadata.json payload (JSON-safe types)."""
    return {
        "phase": "4",
        "stream": "A",
        "layer": "label_based_evaluation",
        "run_mode": run_mode,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": validated.get(
            "input_hashes",
            {
                "predictions": _artifact_info(predictions_path),
                "run_metadata": _artifact_info(run_metadata_path),
                "ground_truth": _artifact_info(ground_truth_path),
            },
        ),
        "input_manifest": validated["input_manifest"],
        "registry_summary": {
            **validated["registry_summary"],
            "matched_to_sample": validated["sample_summary"]["sample_size"],
        },
        "sample": validated["sample_summary"],
        "run_ids": list(validated["run_ids"]),
        "score_orientation": {
            "native_score": "Phase 3 native estimator score; lower = more anomalous",
            "anomaly_score": "-native_score; higher = more anomalous",
            "ranking_metrics_use": "anomaly_score",
            "threshold_metrics_use": "saved Phase 3 flags (never recomputed)",
        },
        "outputs": {k: str(v) for k, v in output_paths.items()},
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit-learn": sklearn.__version__,
            "executable": sys.executable,
        },
        "model_fitting": {
            "models_fitted": 0,
            "note": (
                "Phase 4 is an evaluation-only layer: no detector was "
                "constructed, fitted or refitted; Phase 3 scores and flags "
                "were consumed exactly as stored."
            ),
        },
        **({"reference_comparison": reference_info} if reference_info else {}),
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _output_paths(output_dir: Path) -> Dict:
    return {
        "evaluation_dataset": output_dir / config.PHASE4_EVALUATION_DATASET_FILENAME,
        "metrics": output_dir / config.PHASE4_METRICS_FILENAME,
        "run_metadata": output_dir / config.PHASE4_RUN_METADATA_FILENAME,
        "manifest": output_dir / config.PHASE4_MANIFEST_FILENAME,
    }


def collect_phase4_preflight(
    predictions_path: Optional[Path] = None,
    run_metadata_path: Optional[Path] = None,
    ground_truth_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    expected_run_ids: Optional[Sequence[str]] = None,
    overwrite: bool = False,
    verbose: bool = True,
    require_canonical_sample_size: bool = False,
) -> Dict:
    """Validate everything Phase 4 needs WITHOUT computing or writing.

    Verifies the optional Phase 3 manifest, loads and validates the
    registry, the Phase 3 metadata and the prediction bundle, and performs
    the row_id alignment -- so every failure mode of a real run is exercised
    here. No metric is calculated and no file is written (the output
    directory is not even created).
    """
    predictions_path, run_metadata_path, ground_truth_path = _resolve_input_paths(
        predictions_path, run_metadata_path, ground_truth_path
    )
    output_dir = Path(output_dir) if output_dir is not None else config.DEFAULT_PHASE4_OUTPUT_DIR
    paths = _output_paths(output_dir)

    validated = _load_and_validate_inputs(
        predictions_path, run_metadata_path, ground_truth_path,
        expected_run_ids, verbose=verbose,
        require_canonical_sample_size=require_canonical_sample_size,
    )

    return {
        "predictions_path": predictions_path,
        "run_metadata_path": run_metadata_path,
        "ground_truth_path": ground_truth_path,
        "input_manifest": validated["input_manifest"],
        "registry_summary": validated["registry_summary"],
        "sample": validated["sample_summary"],
        "run_ids": list(validated["run_ids"]),
        "alignment": {
            "join_key": config.ID_COLUMN,
            "join_validation": "one_to_one",
            "prediction_order_preserved": True,
            "unmatched_prediction_ids": 0,
        },
        "metrics_planned": list(METRIC_COLUMNS),
        "outputs": {
            "directory": output_dir,
            "paths": paths,
            "exists": {k: Path(v).exists() for k, v in paths.items()},
            "overwrite": bool(overwrite),
            "blocked": bool(any(Path(v).exists() for v in paths.values()) and not overwrite),
        },
        "writes_performed": False,
        "metrics_calculated": False,
        "models_fitted": 0,
    }


def run_phase4_evaluation(
    predictions_path: Optional[Path] = None,
    run_metadata_path: Optional[Path] = None,
    ground_truth_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    expected_run_ids: Optional[Sequence[str]] = None,
    overwrite: bool = False,
    reference_metrics_path: Optional[Path] = None,
    verbose: bool = True,
    require_canonical_sample_size: bool = False,
) -> Dict:
    """Execute the Phase 4 evaluation layer end to end.

    Steps: fail-fast output precheck -> verify the optional Phase 3 manifest
    (or classify the inputs as a legacy unmanifested pair) -> load and
    validate the registry, the Phase 3 metadata and the prediction bundle ->
    align predictions to labels on ``row_id`` (validated one-to-one, order
    preserving) -> calculate the metrics for every run -> write the
    evaluation dataset, the metrics table, the provenance record and the
    output manifest. **No detector is ever fitted or refitted.**

    Existing output files are never replaced unless ``overwrite=True``.
    ``reference_metrics_path`` optionally points at a reference metrics CSV
    (with a ``run_id`` column) used ONLY for a post-hoc acceptance
    comparison -- it never influences the calculation.
    """
    predictions_path, run_metadata_path, ground_truth_path = _resolve_input_paths(
        predictions_path, run_metadata_path, ground_truth_path
    )
    output_dir = Path(output_dir) if output_dir is not None else config.DEFAULT_PHASE4_OUTPUT_DIR
    paths = _output_paths(output_dir)

    # Fail fast: refuse to compute if outputs exist and cannot be replaced.
    assert_outputs_writable(list(paths.values()), overwrite=overwrite)

    validated = _load_and_validate_inputs(
        predictions_path, run_metadata_path, ground_truth_path,
        expected_run_ids, verbose=verbose,
        require_canonical_sample_size=require_canonical_sample_size,
    )
    evaluation_dataset = validated["evaluation_dataset"]
    metadata_df = validated["metadata_df"]

    if verbose:
        print(f"\nCalculating evaluation metrics for {len(validated['run_ids'])} runs ...")
    metrics_df = compute_phase4_metrics(evaluation_dataset, metadata_df)

    reference_info = None
    reference_comparison = None
    if reference_metrics_path is not None:
        reference_df = pd.read_csv(reference_metrics_path)
        reference_comparison = compare_metrics_to_reference(metrics_df, reference_df, expected_run_ids=validated['run_ids'])
        n_match = int(reference_comparison["matches_rounded_reference"].sum())
        n_total = int(len(reference_comparison))
        reference_info = {
            "path": str(reference_metrics_path),
            "comparisons": n_total,
            "matches": n_match,
            "all_match": bool(n_match == n_total),
        }
        if verbose:
            print(
                f"Reference comparison: {n_match}/{n_total} values match the "
                f"reference at 4-decimal rounding"
            )

    provenance = _build_provenance_record(
        predictions_path, run_metadata_path, ground_truth_path,
        validated, paths, run_mode="execute", reference_info=reference_info,
    )

    if verbose:
        print(f"\nSaving artifacts to {output_dir} ...")
    publish_phase4_artifacts(
        evaluation_dataset=evaluation_dataset,
        metrics_df=metrics_df,
        provenance=provenance,
        output_dir=output_dir,
        overwrite=overwrite,
    )

    if verbose:
        print("\n=== PHASE 4 METRICS (recalculated from the saved Phase 3 predictions) ===")
        display_columns = [
            "run_id", "model", "average_precision", "roc_auc",
            "precision_at_1pct", "recall_at_1pct", "f1_at_1pct",
            "tp", "fp", "fn", "tn", "fraud_count", "flagged_count",
        ]
        print(metrics_df[display_columns].to_string(index=False))
        print(
            "\nAll ten runs are reported; no model was selected, refitted or "
            "re-thresholded. Full table (incl. metadata passthrough columns): "
            f"{paths['metrics']}"
        )

    return {
        "evaluation_dataset": evaluation_dataset,
        "metrics": metrics_df,
        "provenance": provenance,
        "input_manifest": validated["input_manifest"],
        "registry_summary": validated["registry_summary"],
        "sample": validated["sample_summary"],
        "reference_comparison": reference_comparison,
        "paths": {
            "predictions": predictions_path,
            "run_metadata": run_metadata_path,
            "ground_truth": ground_truth_path,
            **{k: Path(v) for k, v in paths.items()},
        },
    }


def _format_problems(problems: List[str], category: str) -> str:
    lines = [f"Validation failed ({category}):"]
    lines.extend(f"  {i}. {p}" for i, p in enumerate(problems, start=1))
    return "\n".join(lines)
