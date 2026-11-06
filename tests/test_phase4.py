"""Lightweight software-structure tests for the Phase 4 evaluation layer.

These tests run on SYNTHETIC fixtures (in-memory bundles, tiny registries,
and one small real Phase 3 run on synthetic feature data). They validate the
software contract -- registry/bundle/metadata validation, row_id alignment,
score orientation, metric formulas, manifest handling, protection mechanisms
-- and never touch the real repository dataset or the canonical artifacts.
"""
from __future__ import annotations

import json
import pickle
import re
import subprocess
import sys
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor

from mplad.common import config
from mplad.common import io as mplad_io
from mplad.common.manifest import (
    ManifestError,
    ManifestVerificationError,
    artifact_entry,
    build_manifest,
    load_manifest,
    save_manifest,
    verify_manifest,
)
from mplad.stream_a import phase3, phase4

REPO_ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------
# Synthetic data helpers (schemas identical to the real artifacts)
# --------------------------------------------------------------------------

MINI_IF_CONFIGS = [{"n_estimators": 10, "max_samples": 64, "random_state": 42}]
MINI_LOF_CONFIGS = [{"n_neighbors": 5, "metric": "euclidean"}]


def make_synthetic_fs(n_rows: int = 800, seed: int = 0) -> pd.DataFrame:
    """Schema-compatible FS-A stand-in: Time, V1..V28, Amount, row_id."""
    rng = np.random.RandomState(seed)
    df = pd.DataFrame({f"V{i}": rng.normal(size=n_rows) for i in range(1, 29)})
    df.insert(0, "Time", rng.uniform(0, 172792, size=n_rows))
    df["Amount"] = np.abs(rng.normal(88, 250, size=n_rows))
    df[config.ID_COLUMN] = np.arange(n_rows)
    return df


def make_metadata(run_ids, flagged_counts) -> pd.DataFrame:
    """Metadata frame with the exact phase3_run_metadata.csv schema."""
    rows = []
    for run_id, flagged in zip(run_ids, flagged_counts):
        if run_id.startswith("IF"):
            rows.append({
                "run_id": run_id, "model": "IsolationForest",
                "n_estimators": 100, "max_samples": 256, "random_state": 42,
                "runtime_seconds": 0.10,
                "threshold_rule": config.THRESHOLD_RULE_LABEL,
                "flagged_count": int(flagged), "n_neighbors": np.nan, "metric": np.nan,
            })
        else:
            rows.append({
                "run_id": run_id, "model": "LOF",
                "n_estimators": np.nan, "max_samples": np.nan, "random_state": "N/A",
                "runtime_seconds": 0.10,
                "threshold_rule": config.THRESHOLD_RULE_LABEL,
                "flagged_count": int(flagged), "n_neighbors": 30, "metric": "euclidean",
            })
    return pd.DataFrame(rows, columns=config.METADATA_COLUMNS)


def make_bundle(row_ids, fraud_row_ids, seed=0, run_ids=("IF_001",)):
    """Bundle in the canonical pickle structure; frauds biased to LOW native
    scores (the native orientation: lower = more anomalous). Flags follow the
    bottom-1% rule, mimicking Phase 3."""
    rng = np.random.RandomState(seed)
    row_ids = np.asarray(row_ids)
    fraud_mask = np.isin(row_ids, list(fraud_row_ids))
    predictions = {}
    flagged_counts = []
    for i, run_id in enumerate(run_ids):
        native = rng.normal(0.0, 1.0, size=len(row_ids))
        native[fraud_mask] = rng.normal(-6.0 - 0.1 * i, 0.5, size=int(fraud_mask.sum()))
        threshold = np.percentile(native, config.THRESHOLD_PERCENTILE)
        flags = np.where(native <= threshold, 1, 0).astype(np.uint8)
        predictions[run_id] = {"scores": native.astype(np.float32), "flags": flags}
        flagged_counts.append(int(flags.sum()))
    return (
        {"row_ids": row_ids, "predictions": predictions},
        make_metadata(list(run_ids), flagged_counts),
    )


def make_registry(pairs) -> pd.DataFrame:
    """Registry frame from (row_id, Class) pairs, in the given order."""
    return pd.DataFrame(pairs, columns=[config.ID_COLUMN, config.LABEL_COLUMN])


def write_phase3_inputs(tmp_path, bundle, metadata_df):
    """Write a synthetic Phase 3 artifact pair to disk (pickle + CSV)."""
    p3_dir = tmp_path / "phase3"
    p3_dir.mkdir(parents=True, exist_ok=True)
    pkl_path = p3_dir / config.PREDICTIONS_FILENAME
    with open(pkl_path, "wb") as f:
        pickle.dump(bundle, f, protocol=pickle.HIGHEST_PROTOCOL)
    csv_path = p3_dir / config.METADATA_FILENAME
    metadata_df.to_csv(csv_path, index=False)
    return pkl_path, csv_path


def evaluate_with(bundle, metadata_df, registry_df, tmp_path, expected_run_ids, **kwargs):
    """Full run_phase4_evaluation on synthetic inputs written to tmp_path."""
    pkl_path, csv_path = write_phase3_inputs(tmp_path, bundle, metadata_df)
    registry_path = tmp_path / "ground_truth_registry.csv"
    registry_df.to_csv(registry_path, index=False)
    return phase4.run_phase4_evaluation(
        predictions_path=pkl_path,
        run_metadata_path=csv_path,
        ground_truth_path=registry_path,
        output_dir=tmp_path / "out",
        expected_run_ids=expected_run_ids,
        verbose=False,
        **kwargs,
    )


# --------------------------------------------------------------------------
# The hand-computed fixture (all values verified by hand; see assertions)
# --------------------------------------------------------------------------
# 10 rows, prediction order; frauds: row_ids 12 and 17 (positions 2 and 7).
HAND_ROW_IDS = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
HAND_FRAUDS = {12, 17}
# native scores (lower = more anomalous); anomaly = -native:
#   [10, 9, 12, 6, 5, 4, 3, 7, 2, 1]
# anomaly ranking (desc): 12(F,pos2), 10(N,pos0), 9(N,pos1), 7(F,pos7), 6..1
#   -> fraud ranks 1 and 4 of 10 -> AP = (1/1 + 2/4)/2 = 0.75
#   -> AUC = (8 + 6) / (2*8)   = 0.875
HAND_NATIVE = np.array(
    [-10.0, -9.0, -12.0, -6.0, -5.0, -4.0, -3.0, -7.0, -2.0, -1.0],
    dtype=np.float32,
)
# Supplied flags (positions 0 and 2) deliberately differ from the bottom-1%
# rule (which would flag only position 2): TP=1, FP=1, FN=1, TN=7,
# precision = recall = f1 = 0.5.
HAND_FLAGS = np.array([1, 0, 1, 0, 0, 0, 0, 0, 0, 0], dtype=np.uint8)
# Registry in a SHUFFLED order whose fraud positions (3 and 4) differ from
# the prediction-order fraud positions (2 and 7): any positional alignment
# produces wrong labels.
HAND_REGISTRY = make_registry([
    (15, 0), (10, 0), (19, 0), (12, 1), (17, 1),
    (11, 0), (18, 0), (14, 0), (13, 0), (16, 0),
])


def hand_bundle():
    return {
        "row_ids": np.array(HAND_ROW_IDS),
        "predictions": {"IF_001": {
            "scores": HAND_NATIVE.copy(), "flags": HAND_FLAGS.copy(),
        }},
    }


HAND_METADATA = make_metadata(["IF_001"], [int(HAND_FLAGS.sum())])
HAND_TRUTH = {rid: int(rid in HAND_FRAUDS) for rid in HAND_ROW_IDS}


# ==========================================================================
# Ground-truth registry validation
# ==========================================================================

class TestGroundTruthRegistryValidation:
    def test_valid_registry_passes_and_reports_counts(self):
        registry = make_registry([(0, 0), (1, 1), (2, 0), (3, 1), (4, 0)])
        summary = phase4.validate_ground_truth_registry(registry)
        assert summary == {"total_observations": 5, "positive_labels": 2}

    def test_missing_row_id_column_rejected(self):
        registry = pd.DataFrame({"Class": [0, 1]})
        with pytest.raises(phase4.GroundTruthRegistryError, match="row_id"):
            phase4.validate_ground_truth_registry(registry)

    def test_missing_class_column_rejected(self):
        registry = pd.DataFrame({"row_id": [1, 2]})
        with pytest.raises(phase4.GroundTruthRegistryError, match="Class"):
            phase4.validate_ground_truth_registry(registry)

    def test_extra_column_rejected(self):
        registry = make_registry([(0, 0), (1, 1)])
        registry["extra"] = 1
        with pytest.raises(phase4.GroundTruthRegistryError, match="extra"):
            phase4.validate_ground_truth_registry(registry)

    def test_null_row_ids_rejected(self):
        registry = make_registry([(0, 0), (np.nan, 1)])
        with pytest.raises(phase4.GroundTruthRegistryError, match="missing values"):
            phase4.validate_ground_truth_registry(registry)

    def test_duplicate_registry_ids_rejected(self):
        registry = make_registry([(0, 0), (1, 1), (1, 0)])
        with pytest.raises(phase4.GroundTruthRegistryError, match="duplicate"):
            phase4.validate_ground_truth_registry(registry)

    def test_missing_labels_rejected(self):
        registry = make_registry([(0, 0), (1, np.nan)])
        with pytest.raises(phase4.GroundTruthRegistryError, match="missing label"):
            phase4.validate_ground_truth_registry(registry)

    def test_non_binary_labels_rejected(self):
        registry = make_registry([(0, 0), (1, 2)])
        with pytest.raises(phase4.GroundTruthRegistryError, match="non-binary"):
            phase4.validate_ground_truth_registry(registry)

    def test_string_labels_rejected(self):
        registry = make_registry([(0, "0"), (1, "fraud")])
        with pytest.raises(phase4.GroundTruthRegistryError, match="non-binary"):
            phase4.validate_ground_truth_registry(registry)

    def test_missing_registry_file_raises_clear_error(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="ground_truth_registry"):
            phase4.load_ground_truth_registry(tmp_path / "ground_truth_registry.csv")


# ==========================================================================
# Phase 3 run-metadata validation
# ==========================================================================

class TestPhase3MetadataValidation:
    def test_canonical_ten_runs_accepted(self):
        metadata = make_metadata(
            config.PHASE3_CANONICAL_RUN_IDS, [300] * len(config.PHASE3_CANONICAL_RUN_IDS)
        )
        run_ids = phase4.validate_phase3_run_metadata(metadata)
        assert run_ids == list(config.PHASE3_CANONICAL_RUN_IDS)

    def test_missing_column_rejected(self):
        metadata = make_metadata(["IF_001"], [2]).drop(columns=["model"])
        with pytest.raises(phase4.Phase3MetadataError, match="missing column"):
            phase4.validate_phase3_run_metadata(metadata)

    def test_extra_column_rejected(self):
        metadata = make_metadata(["IF_001"], [2])
        metadata["extra"] = 1
        with pytest.raises(phase4.Phase3MetadataError, match="extra"):
            phase4.validate_phase3_run_metadata(metadata)

    def test_duplicate_run_id_rejected(self):
        metadata = pd.concat(
            [make_metadata(["IF_001"], [2]), make_metadata(["IF_001"], [2])],
            ignore_index=True,
        )
        with pytest.raises(phase4.Phase3MetadataError, match="duplicate"):
            phase4.validate_phase3_run_metadata(metadata)

    def test_missing_run_vs_expected_rejected(self):
        metadata = make_metadata(["IF_001"], [2])
        with pytest.raises(phase4.Phase3MetadataError, match="missing run"):
            phase4.validate_phase3_run_metadata(metadata, expected_run_ids=["IF_001", "LOF_001"])

    def test_unexpected_run_vs_expected_rejected(self):
        metadata = make_metadata(["IF_001", "IF_099"], [2, 2])
        with pytest.raises(phase4.Phase3MetadataError, match="unexpected run"):
            phase4.validate_phase3_run_metadata(metadata, expected_run_ids=["IF_001"])

    def test_non_integral_flagged_count_rejected(self):
        metadata = make_metadata(["IF_001"], [2])
        metadata["flagged_count"] = metadata["flagged_count"].astype(float)
        metadata.loc[0, "flagged_count"] = 2.5
        with pytest.raises(phase4.Phase3MetadataError, match="flagged_count"):
            phase4.validate_phase3_run_metadata(metadata, expected_run_ids=["IF_001"])

    def test_canonical_run_ids_constant(self):
        assert config.PHASE3_CANONICAL_RUN_IDS == (
            "IF_001", "IF_002", "IF_003", "IF_004", "IF_005",
            "LOF_001", "LOF_002", "LOF_003", "LOF_004", "LOF_005",
        )


# ==========================================================================
# Prediction-bundle validation
# ==========================================================================

class TestPredictionBundleValidation:
    def test_valid_bundle_summary(self):
        bundle, metadata = make_bundle(
            np.arange(100, 120), fraud_row_ids={105, 112}, seed=3
        )
        summary = phase4.validate_prediction_bundle(bundle, metadata)
        assert summary["sample_size"] == 20
        assert summary["run_ids"] == ["IF_001"]

    def test_wrong_top_level_keys_rejected(self):
        with pytest.raises(phase4.PredictionBundleError, match="row_ids"):
            phase4.validate_prediction_bundle({"predictions": {}}, make_metadata(["IF_001"], [0]))

    def test_duplicate_prediction_ids_rejected(self):
        bundle, metadata = make_bundle(np.arange(100, 110), {105})
        bundle["row_ids"] = np.array([100, 100, 102, 103, 104, 105, 106, 107, 108, 109])
        with pytest.raises(phase4.PredictionBundleError, match="duplicate"):
            phase4.validate_prediction_bundle(bundle, metadata)

    def test_float_row_ids_rejected(self):
        bundle, metadata = make_bundle(np.arange(100, 110), {105})
        bundle["row_ids"] = bundle["row_ids"].astype(np.float64)
        with pytest.raises(phase4.PredictionBundleError, match="integer"):
            phase4.validate_prediction_bundle(bundle, metadata)

    def test_non_finite_scores_rejected(self):
        bundle, metadata = make_bundle(np.arange(100, 110), {105})
        for bad in (np.nan, np.inf, -np.inf):
            corrupted = pickle.loads(pickle.dumps(bundle))
            corrupted["predictions"]["IF_001"]["scores"] = corrupted[
                "predictions"]["IF_001"]["scores"].copy()
            corrupted["predictions"]["IF_001"]["scores"][3] = bad
            with pytest.raises(phase4.PredictionBundleError, match="non-finite"):
                phase4.validate_prediction_bundle(corrupted, metadata)

    def test_wrong_score_length_rejected(self):
        bundle, metadata = make_bundle(np.arange(100, 110), {105})
        entry = bundle["predictions"]["IF_001"]
        entry["scores"] = entry["scores"][:-1]
        with pytest.raises(phase4.PredictionBundleError, match="'scores' must be 1-D"):
            phase4.validate_prediction_bundle(bundle, metadata)

    def test_wrong_flag_length_rejected(self):
        bundle, metadata = make_bundle(np.arange(100, 110), {105})
        entry = bundle["predictions"]["IF_001"]
        entry["flags"] = entry["flags"][:-2]
        with pytest.raises(phase4.PredictionBundleError, match="'flags' must be 1-D"):
            phase4.validate_prediction_bundle(bundle, metadata)

    def test_non_binary_flags_rejected(self):
        bundle, metadata = make_bundle(np.arange(100, 110), {105})
        flags = bundle["predictions"]["IF_001"]["flags"].astype(np.int64)
        flags[2] = 2
        bundle["predictions"]["IF_001"]["flags"] = flags
        with pytest.raises(phase4.PredictionBundleError, match="binary"):
            phase4.validate_prediction_bundle(bundle, metadata)

    def test_integer_scores_rejected(self):
        bundle, metadata = make_bundle(np.arange(100, 110), {105})
        entry = bundle["predictions"]["IF_001"]
        entry["scores"] = np.arange(10, dtype=np.int64)
        with pytest.raises(phase4.PredictionBundleError, match="floating"):
            phase4.validate_prediction_bundle(bundle, metadata)

    def test_missing_run_in_bundle_rejected(self):
        bundle, metadata = make_bundle(
            np.arange(100, 110), {105}, run_ids=("IF_001", "LOF_001")
        )
        del bundle["predictions"]["IF_001"]
        with pytest.raises(phase4.PredictionBundleError, match="missing run"):
            phase4.validate_prediction_bundle(bundle, metadata)

    def test_unexpected_run_in_bundle_rejected(self):
        bundle, metadata = make_bundle(np.arange(100, 110), {105})
        bundle["predictions"]["IF_099"] = dict(bundle["predictions"]["IF_001"])
        with pytest.raises(phase4.PredictionBundleError, match="unexpected run"):
            phase4.validate_prediction_bundle(bundle, metadata)

    def test_flagged_count_mismatch_vs_metadata_rejected(self):
        bundle, metadata = make_bundle(np.arange(100, 110), {105})
        metadata.loc[0, "flagged_count"] = int(metadata.loc[0, "flagged_count"]) + 1
        with pytest.raises(phase4.PredictionBundleError, match="flag count mismatch"):
            phase4.validate_prediction_bundle(bundle, metadata)

    def test_extra_entry_keys_rejected(self):
        bundle, metadata = make_bundle(np.arange(100, 110), {105})
        bundle["predictions"]["IF_001"]["threshold_value"] = 0.5
        with pytest.raises(phase4.PredictionBundleError, match="scores"):
            phase4.validate_prediction_bundle(bundle, metadata)


# ==========================================================================
# Label alignment (the historical-bug killer)
# ==========================================================================

class TestLabelAlignment:
    def test_alignment_correct_when_registry_is_shuffled(self, tmp_path):
        """Required case: correct row-ID alignment when the registry is
        shuffled. Every (row_id, Class) pair must match the truth mapping."""
        result = evaluate_with(hand_bundle(), HAND_METADATA, HAND_REGISTRY, tmp_path, ["IF_001"])
        evaluation = result["evaluation_dataset"]
        assert all(
            HAND_TRUTH[rid] == cls
            for rid, cls in zip(evaluation["row_id"], evaluation["Class"])
        )

    def test_positional_alignment_would_fail_this_test(self, tmp_path):
        """The explicitly required test: it FAILS if labels are aligned by
        array position rather than row_id. The shuffled registry places the
        fraud labels at positions 3 and 4, while the true fraud positions in
        prediction order are 2 and 7 -- a positional alignment would assign
        the wrong Class to four rows and produce wrong metrics."""
        result = evaluate_with(hand_bundle(), HAND_METADATA, HAND_REGISTRY, tmp_path, ["IF_001"])
        evaluation = result["evaluation_dataset"]

        positional_classes = HAND_REGISTRY[config.LABEL_COLUMN].to_numpy()
        assert not np.array_equal(positional_classes, evaluation["Class"].to_numpy()), (
            "registry shuffle is not discriminating -- test setup is broken"
        )
        assert all(
            HAND_TRUTH[rid] == cls
            for rid, cls in zip(evaluation["row_id"], evaluation["Class"])
        )
        metrics = result["metrics"].iloc[0]
        assert metrics["average_precision"] == pytest.approx(0.75)
        assert metrics["roc_auc"] == pytest.approx(0.875)

    def test_metrics_invariant_to_registry_row_order(self, tmp_path):
        shuffled = evaluate_with(hand_bundle(), HAND_METADATA, HAND_REGISTRY, tmp_path / "a", ["IF_001"])
        sorted_registry = HAND_REGISTRY.sort_values(config.ID_COLUMN).reset_index(drop=True)
        ordered = evaluate_with(hand_bundle(), HAND_METADATA, sorted_registry, tmp_path / "b", ["IF_001"])
        pd.testing.assert_frame_equal(shuffled["metrics"], ordered["metrics"])

    def test_unmatched_prediction_ids_rejected(self, tmp_path):
        """Required case: missing prediction IDs (present in the sample, absent
        from the registry) are rejected, never silently dropped."""
        incomplete = HAND_REGISTRY[HAND_REGISTRY[config.ID_COLUMN] != 13]
        with pytest.raises(phase4.LabelAlignmentError, match="13"):
            evaluate_with(hand_bundle(), HAND_METADATA, incomplete, tmp_path, ["IF_001"])

    def test_join_never_changes_row_count(self):
        evaluation = phase4.align_predictions_to_labels(
            hand_bundle(), HAND_REGISTRY, ["IF_001"]
        )
        assert len(evaluation) == len(HAND_ROW_IDS)

    def test_prediction_row_order_is_preserved(self, tmp_path):
        """Required case: the evaluation dataset keeps the bundle's row-ID
        sequence exactly, per run."""
        run_ids = list(config.PHASE3_CANONICAL_RUN_IDS)
        bundle, metadata = make_bundle(
            np.arange(200, 400), fraud_row_ids={205, 250, 390}, seed=11, run_ids=run_ids
        )
        registry = make_registry(
            [(rid, int(rid in {205, 250, 390})) for rid in range(200, 400)]
            + [(900 + i, 0) for i in range(50)]
        )
        result = evaluate_with(bundle, metadata, registry, tmp_path, run_ids)
        evaluation = result["evaluation_dataset"]
        shared_ids = list(bundle["row_ids"])
        for run_id in run_ids:
            run_rows = evaluation[evaluation["run_id"] == run_id]
            assert run_rows["row_id"].tolist() == shared_ids


# ==========================================================================
# Score orientation
# ==========================================================================

class TestScoreOrientation:
    def test_anomaly_score_is_exactly_negated_native(self, tmp_path):
        result = evaluate_with(hand_bundle(), HAND_METADATA, HAND_REGISTRY, tmp_path, ["IF_001"])
        evaluation = result["evaluation_dataset"]
        assert np.allclose(
            evaluation["anomaly_score"].to_numpy(),
            -evaluation["native_score"].to_numpy(),
        )

    def test_perfect_separation_gives_perfect_ranking(self, tmp_path):
        """Required case: incorrect score orientation would be caught. With
        frauds carrying the LOWEST native scores (the Phase 3 orientation),
        AP and ROC-AUC equal 1.0 on anomaly_score = -native_score; had the
        metrics been computed on the native scores, both would collapse
        towards 0 and this test would fail."""
        n, n_frauds = 200, 20
        row_ids = np.arange(1000, 1000 + n)
        native = np.concatenate([
            -10.0 - 0.01 * np.arange(n_frauds, dtype=np.float64),   # frauds: lowest
            np.linspace(1.0, 5.0, n - n_frauds),                    # normals
        ]).astype(np.float32)
        flags = np.zeros(n, dtype=np.uint8)
        flags[:n_frauds] = 1
        bundle = {"row_ids": row_ids, "predictions": {"IF_001": {
            "scores": native, "flags": flags,
        }}}
        metadata = make_metadata(["IF_001"], [n_frauds])
        registry = make_registry(
            [(int(rid), int(i < n_frauds)) for i, rid in enumerate(row_ids)]
        )
        result = evaluate_with(bundle, metadata, registry, tmp_path, ["IF_001"])
        metrics = result["metrics"].iloc[0]
        assert metrics["average_precision"] == pytest.approx(1.0)
        assert metrics["roc_auc"] == pytest.approx(1.0)
        assert metrics["tp"] == n_frauds and metrics["fp"] == 0
        assert metrics["precision_at_1pct"] == pytest.approx(1.0)
        assert metrics["recall_at_1pct"] == pytest.approx(1.0)


# ==========================================================================
# Metric computation (hand-verified values)
# ==========================================================================

@pytest.fixture()
def hand_result(tmp_path):
    return evaluate_with(hand_bundle(), HAND_METADATA, HAND_REGISTRY, tmp_path, ["IF_001"])


class TestMetricComputation:
    def test_hand_computed_ap_and_roc_auc(self, hand_result):
        """Required case: AP and ROC-AUC are correct (hand-derived: fraud
        anomaly ranks 1 and 4 of 10 -> AP = 0.75, AUC = 14/16 = 0.875)."""
        metrics = hand_result["metrics"].iloc[0]
        assert metrics["average_precision"] == pytest.approx(0.75)
        assert metrics["roc_auc"] == pytest.approx(0.875)

    def test_fixed_threshold_metrics_from_saved_flags(self, hand_result):
        """Required case: threshold metrics are computed FROM the saved flags.
        The supplied flags (positions 0 and 2) differ from the bottom-1% rule
        (position 2 only), so the correct numbers prove the flags were used
        as supplied rather than recomputed."""
        metrics = hand_result["metrics"].iloc[0]
        assert metrics["precision_at_1pct"] == pytest.approx(0.5)
        assert metrics["recall_at_1pct"] == pytest.approx(0.5)
        assert metrics["f1_at_1pct"] == pytest.approx(0.5)

    def test_flags_used_exactly_as_supplied(self, tmp_path):
        """Second proof that flags are never recomputed: flags placed on the
        LEAST anomalous rows yield TP=0 and precision 0 (zero_division=0),
        which contradicts any recomputed bottom-1% rule."""
        bundle = hand_bundle()
        bundle["predictions"]["IF_001"]["flags"] = np.array(
            [1, 1, 0, 0, 0, 0, 0, 0, 0, 0], dtype=np.uint8
        )
        metadata = make_metadata(["IF_001"], [2])
        result = evaluate_with(bundle, metadata, HAND_REGISTRY, tmp_path, ["IF_001"])
        metrics = result["metrics"].iloc[0]
        assert (metrics["tp"], metrics["fp"], metrics["fn"], metrics["tn"]) == (0, 2, 2, 6)
        assert metrics["precision_at_1pct"] == 0.0
        assert metrics["recall_at_1pct"] == 0.0
        assert metrics["f1_at_1pct"] == 0.0

    def test_confusion_matrix_counts(self, hand_result):
        """Required case: TN/FP/FN/TP hand-verified (7/1/1/1)."""
        metrics = hand_result["metrics"].iloc[0]
        assert (metrics["tn"], metrics["fp"], metrics["fn"], metrics["tp"]) == (7, 1, 1, 1)
        assert metrics["tn"] + metrics["fp"] + metrics["fn"] + metrics["tp"] == 10

    def test_zero_flags_yield_zero_division_zero_metrics(self, tmp_path):
        bundle = hand_bundle()
        bundle["predictions"]["IF_001"]["flags"] = np.zeros(10, dtype=np.uint8)
        metadata = make_metadata(["IF_001"], [0])
        result = evaluate_with(bundle, metadata, HAND_REGISTRY, tmp_path, ["IF_001"])
        metrics = result["metrics"].iloc[0]
        assert metrics["precision_at_1pct"] == 0.0
        assert metrics["recall_at_1pct"] == 0.0
        assert metrics["f1_at_1pct"] == 0.0
        assert metrics["flagged_count"] == 0

    def test_sample_bookkeeping_columns(self, hand_result):
        metrics = hand_result["metrics"].iloc[0]
        assert metrics["sample_size"] == 10
        assert metrics["fraud_count"] == 2
        assert metrics["fraud_prevalence"] == pytest.approx(0.2)
        assert metrics["flagged_count"] == 2
        assert metrics["flagged_proportion"] == pytest.approx(0.2)

    def test_all_ten_runs_represented(self, tmp_path):
        """Required case: every one of the ten Phase 3 runs appears in the
        output, in canonical order, with the full sample each."""
        run_ids = list(config.PHASE3_CANONICAL_RUN_IDS)
        bundle, metadata = make_bundle(
            np.arange(200, 600), fraud_row_ids={205, 250, 390, 599}, seed=11, run_ids=run_ids
        )
        registry = make_registry(
            [(rid, int(rid in {205, 250, 390, 599})) for rid in range(200, 600)]
            + [(900 + i, int(i % 97 == 0)) for i in range(100)]
        )
        result = evaluate_with(bundle, metadata, registry, tmp_path, run_ids)
        evaluation, metrics = result["evaluation_dataset"], result["metrics"]

        assert metrics["run_id"].tolist() == run_ids
        assert len(metrics) == 10
        assert evaluation["run_id"].nunique() == 10
        assert len(evaluation) == 10 * 400
        assert evaluation.groupby("run_id").size().eq(400).all()
        assert (metrics["sample_size"] == 400).all()
        assert (metrics["fraud_count"] == 4).all()

    def test_metadata_joined_one_to_one(self, tmp_path):
        run_ids = list(config.PHASE3_CANONICAL_RUN_IDS)
        bundle, metadata = make_bundle(
            np.arange(200, 600), fraud_row_ids={205}, seed=5, run_ids=run_ids
        )
        metadata.loc[metadata["run_id"] == "LOF_005", "metric"] = "manhattan"
        registry = make_registry([(rid, int(rid == 205)) for rid in range(200, 600)])
        result = evaluate_with(bundle, metadata, registry, tmp_path, run_ids)
        metrics = result["metrics"].set_index("run_id")
        assert metrics.loc["IF_001", "model"] == "IsolationForest"
        assert metrics.loc["LOF_001", "model"] == "LOF"
        assert metrics.loc["LOF_005", "n_neighbors"] == 30
        assert metrics.loc["LOF_005", "metric"] == "manhattan"
        assert (result["metrics"]["threshold_rule"] == config.THRESHOLD_RULE_LABEL).all()
        assert list(result["metrics"].columns) == phase4.METRICS_TABLE_COLUMNS

    def test_evaluation_dataset_schema(self, hand_result):
        evaluation = hand_result["evaluation_dataset"]
        assert list(evaluation.columns) == phase4.EVALUATION_DATASET_COLUMNS
        assert len(evaluation) == 10

    def test_single_class_sample_rejected(self, tmp_path):
        all_negative = make_registry([(rid, 0) for rid in HAND_ROW_IDS])
        with pytest.raises(phase4.Phase4Error, match="single ground-truth class"):
            evaluate_with(hand_bundle(), HAND_METADATA, all_negative, tmp_path, ["IF_001"])


# ==========================================================================
# No model fitting or refitting
# ==========================================================================

class TestNoFitting:
    def test_no_detector_is_fitted_or_refitted(self, tmp_path):
        """Required case: the full Phase 4 evaluation runs to completion while
        every detector fitting entry point is poisoned -- nothing may fit."""
        with mock.patch.object(
            IsolationForest, "fit", side_effect=AssertionError("must not fit")
        ), mock.patch.object(
            IsolationForest, "fit_predict", side_effect=AssertionError("must not fit")
        ), mock.patch.object(
            LocalOutlierFactor, "fit", side_effect=AssertionError("must not fit")
        ), mock.patch.object(
            LocalOutlierFactor, "fit_predict", side_effect=AssertionError("must not fit")
        ), mock.patch.object(
            phase3, "run_isolation_forest", side_effect=AssertionError("must not fit")
        ), mock.patch.object(
            phase3, "run_lof", side_effect=AssertionError("must not fit")
        ):
            result = evaluate_with(
                hand_bundle(), HAND_METADATA, HAND_REGISTRY, tmp_path, ["IF_001"]
            )
        assert len(result["metrics"]) == 1
        assert result["provenance"]["model_fitting"]["models_fitted"] == 0


# ==========================================================================
# Dry-run behaviour
# ==========================================================================

class TestDryRun:
    @pytest.fixture()
    def phase3_inputs(self, tmp_path):
        pkl_path, csv_path = write_phase3_inputs(tmp_path, hand_bundle(), HAND_METADATA)
        registry_path = tmp_path / "ground_truth_registry.csv"
        HAND_REGISTRY.to_csv(registry_path, index=False)
        return pkl_path, csv_path, registry_path

    def test_preflight_writes_nothing(self, phase3_inputs, tmp_path):
        """Required case: no output writes during dry-run (the output
        directory is not even created)."""
        pkl_path, csv_path, registry_path = phase3_inputs
        output_dir = tmp_path / "never_created"
        report = phase4.collect_phase4_preflight(
            predictions_path=pkl_path,
            run_metadata_path=csv_path,
            ground_truth_path=registry_path,
            output_dir=output_dir,
            expected_run_ids=["IF_001"],
            verbose=False,
        )
        assert not output_dir.exists()
        assert report["writes_performed"] is False
        assert report["outputs"]["blocked"] is False

    def test_preflight_calculates_no_metrics(self, phase3_inputs, tmp_path):
        """Preflight validates and aligns, but never computes a metric."""
        pkl_path, csv_path, registry_path = phase3_inputs
        with mock.patch.object(
            phase4, "evaluate_single_run", side_effect=AssertionError("must not calculate")
        ):
            report = phase4.collect_phase4_preflight(
                predictions_path=pkl_path,
                run_metadata_path=csv_path,
                ground_truth_path=registry_path,
                output_dir=tmp_path / "out",
                expected_run_ids=["IF_001"],
                verbose=False,
            )
        assert report["metrics_calculated"] is False
        assert set(report["metrics_planned"]) == set(phase4.METRIC_COLUMNS)
        assert report["models_fitted"] == 0

    def test_preflight_reports_blocked_outputs(self, phase3_inputs, tmp_path):
        pkl_path, csv_path, registry_path = phase3_inputs
        output_dir = tmp_path / "blocked_out"
        output_dir.mkdir()
        (output_dir / config.PHASE4_METRICS_FILENAME).write_text("existing")
        report = phase4.collect_phase4_preflight(
            predictions_path=pkl_path,
            run_metadata_path=csv_path,
            ground_truth_path=registry_path,
            output_dir=output_dir,
            expected_run_ids=["IF_001"],
            verbose=False,
        )
        assert report["outputs"]["blocked"] is True
        assert (output_dir / config.PHASE4_METRICS_FILENAME).read_text() == "existing"


# ==========================================================================
# Output protection
# ==========================================================================

class TestOutputProtection:
    def test_execute_refuses_existing_outputs_and_preserves_them(self, tmp_path):
        """Required case: existing outputs block execution unless --overwrite
        is explicitly requested; the original files are left untouched."""
        output_dir = tmp_path / "out"
        output_dir.mkdir(parents=True)
        sentinel_files = [
            output_dir / config.PHASE4_EVALUATION_DATASET_FILENAME,
            output_dir / config.PHASE4_METRICS_FILENAME,
            output_dir / config.PHASE4_RUN_METADATA_FILENAME,
            output_dir / config.PHASE4_MANIFEST_FILENAME,
        ]
        for path in sentinel_files:
            path.write_text("EXISTING OUTPUT -- DO NOT TOUCH")

        with pytest.raises(mplad_io.OutputExistsError) as exc:
            evaluate_with(hand_bundle(), HAND_METADATA, HAND_REGISTRY, tmp_path, ["IF_001"])
        for path in sentinel_files:
            assert path.name in str(exc.value)
            assert path.read_text() == "EXISTING OUTPUT -- DO NOT TOUCH"

    def test_precheck_lists_all_four_conflicts(self, tmp_path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        for name in (
            config.PHASE4_EVALUATION_DATASET_FILENAME,
            config.PHASE4_METRICS_FILENAME,
            config.PHASE4_RUN_METADATA_FILENAME,
            config.PHASE4_MANIFEST_FILENAME,
        ):
            (output_dir / name).write_text("x")
        paths = [
            output_dir / config.PHASE4_EVALUATION_DATASET_FILENAME,
            output_dir / config.PHASE4_METRICS_FILENAME,
            output_dir / config.PHASE4_RUN_METADATA_FILENAME,
            output_dir / config.PHASE4_MANIFEST_FILENAME,
        ]
        with pytest.raises(mplad_io.OutputExistsError) as exc:
            mplad_io.assert_outputs_writable(paths, overwrite=False)
        assert all(p.name in str(exc.value) for p in paths)
        mplad_io.assert_outputs_writable(paths, overwrite=True)

    def test_overwrite_opt_in_replaces_outputs(self, tmp_path):
        inputs_dir = tmp_path / "inputs"
        pkl_path, csv_path = write_phase3_inputs(inputs_dir, hand_bundle(), HAND_METADATA)
        registry_path = inputs_dir / "ground_truth_registry.csv"
        HAND_REGISTRY.to_csv(registry_path, index=False)
        output_dir = tmp_path / "out"

        def run(overwrite):
            return phase4.run_phase4_evaluation(
                predictions_path=pkl_path, run_metadata_path=csv_path,
                ground_truth_path=registry_path, output_dir=output_dir,
                expected_run_ids=["IF_001"], overwrite=overwrite, verbose=False,
            )

        first = run(overwrite=False)                 # fresh directory: succeeds
        assert (output_dir / config.PHASE4_METRICS_FILENAME).is_file()
        with pytest.raises(mplad_io.OutputExistsError):
            run(overwrite=False)                     # blocked without opt-in
        replaced = run(overwrite=True)               # explicit opt-in: succeeds
        assert len(replaced["metrics"]) == 1
        assert first["paths"]["metrics"] == replaced["paths"]["metrics"]


# ==========================================================================
# Phase 3 manifest handling (present / absent)
# ==========================================================================

class TestManifestHandling:
    @pytest.fixture()
    def inputs(self, tmp_path):
        pkl_path, csv_path = write_phase3_inputs(tmp_path, hand_bundle(), HAND_METADATA)
        registry_path = tmp_path / "ground_truth_registry.csv"
        HAND_REGISTRY.to_csv(registry_path, index=False)
        return tmp_path, pkl_path, csv_path, registry_path

    def test_manifest_present_and_correct_is_verified(self, inputs, tmp_path):
        """Required case: when a Phase 3 manifest is present, its artifact
        hashes are verified before the inputs are consumed."""
        root, pkl_path, csv_path, registry_path = inputs
        manifest = build_manifest({
            config.PREDICTIONS_FILENAME: pkl_path,
            config.METADATA_FILENAME: csv_path,
        })
        save_manifest(manifest, pkl_path.parent / config.PHASE3_MANIFEST_FILENAME)

        result = phase4.run_phase4_evaluation(
            predictions_path=pkl_path, run_metadata_path=csv_path,
            ground_truth_path=registry_path, output_dir=tmp_path / "out",
            expected_run_ids=["IF_001"], verbose=False,
        )
        status = result["input_manifest"]
        assert status["present"] is True
        assert status["verified"] is True
        assert status["mode"] == "manifest_verified"
        assert result["provenance"]["input_manifest"]["verified"] is True

    def test_manifest_with_wrong_hash_rejected_before_evaluation(self, inputs, tmp_path):
        """A tampered artifact (hash mismatch) is rejected before anything is
        consumed or written."""
        root, pkl_path, csv_path, registry_path = inputs
        manifest = build_manifest({
            config.PREDICTIONS_FILENAME: pkl_path,
            config.METADATA_FILENAME: csv_path,
        })
        manifest["artifacts"][config.PREDICTIONS_FILENAME]["sha256"] = "0" * 64
        save_manifest(manifest, pkl_path.parent / config.PHASE3_MANIFEST_FILENAME)

        output_dir = tmp_path / "out"
        with pytest.raises(ManifestVerificationError, match="SHA-256 mismatch"):
            phase4.run_phase4_evaluation(
                predictions_path=pkl_path, run_metadata_path=csv_path,
                ground_truth_path=registry_path, output_dir=output_dir,
                expected_run_ids=["IF_001"], verbose=False,
            )
        assert not output_dir.exists() or not any(output_dir.iterdir())

    def test_manifest_not_covering_consumed_artifacts_rejected(self, inputs, tmp_path):
        root, pkl_path, csv_path, registry_path = inputs
        manifest = build_manifest({config.PREDICTIONS_FILENAME: pkl_path})
        save_manifest(manifest, pkl_path.parent / config.PHASE3_MANIFEST_FILENAME)
        with pytest.raises(ManifestVerificationError, match="does not cover required"):
            phase4.run_phase4_evaluation(
                predictions_path=pkl_path, run_metadata_path=csv_path,
                ground_truth_path=registry_path, output_dir=tmp_path / "out",
                expected_run_ids=["IF_001"], verbose=False,
            )

    def test_malformed_manifest_rejected(self, inputs, tmp_path):
        root, pkl_path, csv_path, registry_path = inputs
        bad = tmp_path / "phase3" / config.PHASE3_MANIFEST_FILENAME
        bad.write_text(json.dumps({"manifest_version": 1, "artifacts": {"x.csv": {}}}))
        with pytest.raises(ManifestError):
            load_manifest(bad)

    def test_legacy_inputs_marked_and_hashed(self, inputs, tmp_path):
        """Required case: when no Phase 3 manifest exists (the current
        repository state), inputs are marked as a legacy unmanifested pair,
        their SHA-256 hashes are recorded, and verification is never
        claimed."""
        root, pkl_path, csv_path, registry_path = inputs
        result = phase4.run_phase4_evaluation(
            predictions_path=pkl_path, run_metadata_path=csv_path,
            ground_truth_path=registry_path, output_dir=tmp_path / "out",
            expected_run_ids=["IF_001"], verbose=False,
        )
        status = result["input_manifest"]
        assert status["present"] is False
        assert status["verified"] is False
        assert status["mode"] == "legacy_unmanifested"

        provenance_path = result["paths"]["run_metadata"]
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        recorded = provenance["input_manifest"]
        assert recorded["mode"] == "legacy_unmanifested"
        assert "NOT performed" in recorded["note"]

        for key, path in (
            ("predictions", pkl_path), ("run_metadata", csv_path), ("ground_truth", registry_path)
        ):
            info = provenance["inputs"][key]
            assert re.fullmatch(r"[0-9a-f]{64}", info["sha256"])
            assert info["sha256"] == artifact_entry(path)["sha256"]
            assert info["size_bytes"] == path.stat().st_size

    def test_phase4_writes_and_roundtrips_own_manifest(self, inputs, tmp_path):
        root, pkl_path, csv_path, registry_path = inputs
        result = phase4.run_phase4_evaluation(
            predictions_path=pkl_path, run_metadata_path=csv_path,
            ground_truth_path=registry_path, output_dir=tmp_path / "out",
            expected_run_ids=["IF_001"], verbose=False,
        )
        output_dir = result["paths"]["metrics"].parent
        manifest_path = output_dir / config.PHASE4_MANIFEST_FILENAME
        assert manifest_path.is_file()

        manifest = load_manifest(manifest_path)
        assert set(manifest["artifacts"]) == {
            config.PHASE4_EVALUATION_DATASET_FILENAME,
            config.PHASE4_METRICS_FILENAME,
            config.PHASE4_RUN_METADATA_FILENAME,
        }
        report = verify_manifest(manifest, output_dir)
        assert all(entry["verified"] for entry in report.values())

    def test_tampered_phase4_output_fails_manifest_verification(self, inputs, tmp_path):
        root, pkl_path, csv_path, registry_path = inputs
        result = phase4.run_phase4_evaluation(
            predictions_path=pkl_path, run_metadata_path=csv_path,
            ground_truth_path=registry_path, output_dir=tmp_path / "out",
            expected_run_ids=["IF_001"], verbose=False,
        )
        output_dir = result["paths"]["metrics"].parent
        with open(output_dir / config.PHASE4_METRICS_FILENAME, "a", encoding="utf-8") as f:
            f.write("\n")
        manifest = load_manifest(output_dir / config.PHASE4_MANIFEST_FILENAME)
        with pytest.raises(ManifestVerificationError):
            verify_manifest(manifest, output_dir)


# ==========================================================================
# Reference comparison (post-hoc acceptance checks only)
# ==========================================================================

class TestReferenceComparison:
    def test_match_and_mismatch_are_detected(self, hand_result):
        metrics = hand_result["metrics"]
        reference = metrics.copy()
        reference.loc[0, "average_precision"] = 0.3126  # differs from 0.75
        comparison = phase4.compare_metrics_to_reference(metrics, reference)
        ap_rows = comparison[comparison["metric"] == "average_precision"]
        assert not ap_rows["matches_rounded_reference"].iloc[0]
        assert ap_rows["abs_diff"].iloc[0] == pytest.approx(abs(0.75 - 0.3126))
        other = comparison[comparison["metric"] != "average_precision"]
        assert other["matches_rounded_reference"].all()

    def test_rounded_reference_matches(self, hand_result):
        metrics = hand_result["metrics"]
        reference = metrics.copy()
        reference.loc[0, "roc_auc"] = round(float(metrics.loc[0, "roc_auc"]), 4)
        comparison = phase4.compare_metrics_to_reference(metrics, reference)
        assert comparison["matches_rounded_reference"].all()

    def test_no_shared_runs_rejected(self, hand_result):
        reference = hand_result["metrics"].copy()
        reference["run_id"] = "IF_099"
        with pytest.raises(phase4.Phase4Error, match="no shared run_id"):
            phase4.compare_metrics_to_reference(hand_result["metrics"], reference)

    def test_reference_without_run_id_rejected(self, hand_result):
        reference = hand_result["metrics"].drop(columns=["run_id"])
        with pytest.raises(phase4.Phase4Error, match="run_id"):
            phase4.compare_metrics_to_reference(hand_result["metrics"], reference)


# ==========================================================================
# End-to-end: real Phase 3 run on synthetic data -> Phase 4 (incl. CLI)
# ==========================================================================

@pytest.fixture(scope="session")
def mini_phase3(tmp_path_factory):
    """A genuine (small) Phase 3 run on synthetic FS-A data using the FULL
    canonical ten-run grid (sample reduced to 300 rows for speed), plus a
    synthetic full-population registry: 800 registry rows, 300 sampled, 15
    in-sample frauds and 5 out-of-sample frauds."""
    root = tmp_path_factory.mktemp("mini_phase3")
    fs_path = root / "ULB_FS_A_Baseline.csv"
    make_synthetic_fs(n_rows=800, seed=0).to_csv(fs_path, index=False)
    out_dir = root / "phase3_out"
    phase3.run_phase3_experiment(
        fs_a_path=fs_path, output_dir=out_dir,
        sample_size=300, sample_seed=42,
        if_configs=config.ISOLATION_FOREST_CONFIGS,
        lof_configs=config.LOF_CONFIGS,
        verbose=False,
    )
    with open(out_dir / config.PREDICTIONS_FILENAME, "rb") as f:
        bundle = pickle.load(f)

    rng = np.random.RandomState(123)
    sampled = bundle["row_ids"]
    population = np.arange(800)
    in_sample_frauds = set(rng.choice(sampled, size=15, replace=False).tolist())
    out_of_sample = np.setdiff1d(population, sampled)
    out_frauds = set(rng.choice(out_of_sample, size=5, replace=False).tolist())
    frauds = in_sample_frauds | out_frauds

    registry = pd.DataFrame({
        "row_id": population,
        "Class": [int(i in frauds) for i in population],
    })
    registry = registry.iloc[rng.permutation(len(registry))].reset_index(drop=True)
    registry_path = root / "ground_truth_registry.csv"
    registry.to_csv(registry_path, index=False)

    return {
        "root": root,
        "predictions": out_dir / config.PREDICTIONS_FILENAME,
        "metadata": out_dir / config.METADATA_FILENAME,
        "registry": registry_path,
        "expected_runs": list(config.PHASE3_CANONICAL_RUN_IDS),
        "in_sample_frauds": in_sample_frauds,
        "registry_total": 800,
        "registry_positives": 20,
    }


class TestEndToEndPhase3ToPhase4:
    def test_full_pipeline_from_real_phase3_artifacts(self, mini_phase3, tmp_path):
        result = phase4.run_phase4_evaluation(
            predictions_path=mini_phase3["predictions"],
            run_metadata_path=mini_phase3["metadata"],
            ground_truth_path=mini_phase3["registry"],
            output_dir=tmp_path / "phase4_out",
            expected_run_ids=mini_phase3["expected_runs"],
            verbose=False,
        )
        # all four artifacts exist and are non-empty
        for key in ("evaluation_dataset", "metrics", "run_metadata", "manifest"):
            path = result["paths"][key]
            assert path.is_file() and path.stat().st_size > 0, key

        evaluation = result["evaluation_dataset"]
        assert list(evaluation.columns) == phase4.EVALUATION_DATASET_COLUMNS
        assert len(evaluation) == 10 * 300
        assert evaluation["run_id"].nunique() == 10

        # row order per run equals the bundle's stored sequence
        with open(mini_phase3["predictions"], "rb") as f:
            bundle = pickle.load(f)
        for run_id in mini_phase3["expected_runs"]:
            run_rows = evaluation[evaluation["run_id"] == run_id]
            assert run_rows["row_id"].tolist() == bundle["row_ids"].tolist()

        # labels come from row_id, not position
        truth = dict(zip(
            pd.read_csv(mini_phase3["registry"])[config.ID_COLUMN],
            pd.read_csv(mini_phase3["registry"])[config.LABEL_COLUMN],
        ))
        assert all(
            truth[rid] == cls for rid, cls in zip(evaluation["row_id"], evaluation["Class"])
        )

        metrics = result["metrics"]
        assert list(metrics.columns) == phase4.METRICS_TABLE_COLUMNS
        assert metrics["run_id"].tolist() == mini_phase3["expected_runs"]
        assert (metrics["sample_size"] == 300).all()
        assert (metrics["fraud_count"] == 15).all()
        assert result["registry_summary"]["positive_labels"] == 20
        assert result["registry_summary"]["total_observations"] == 800

        # provenance: legacy unmanifested, hashes correct, nothing fitted
        provenance = json.loads(
            result["paths"]["run_metadata"].read_text(encoding="utf-8")
        )
        assert provenance["input_manifest"]["mode"] == "legacy_unmanifested"
        assert provenance["model_fitting"]["models_fitted"] == 0
        assert provenance["registry_summary"]["matched_to_sample"] == 300
        assert provenance["inputs"]["predictions"]["sha256"] == artifact_entry(
            mini_phase3["predictions"]
        )["sha256"]

        # the Phase 4 manifest verifies
        out_dir = result["paths"]["metrics"].parent
        assert verify_manifest(
            load_manifest(out_dir / config.PHASE4_MANIFEST_FILENAME), out_dir
        )

    def test_cli_preflight_then_execute(self, mini_phase3, tmp_path):
        """The CLI: preflight writes nothing; --execute writes everything."""
        output_dir = tmp_path / "cli_out"
        base = [
            sys.executable, "scripts/run_phase4.py",
            "--predictions", str(mini_phase3["predictions"]),
            "--run-metadata", str(mini_phase3["metadata"]),
            "--ground-truth", str(mini_phase3["registry"]),
            "--output-dir", str(output_dir),
        ]
        preflight = subprocess.run(base, cwd=REPO_ROOT, capture_output=True, text=True)
        assert preflight.returncode == 0, preflight.stderr
        assert "PREFLIGHT complete" in preflight.stdout
        assert not output_dir.exists()

        execute = subprocess.run(base + ["--execute"], cwd=REPO_ROOT, capture_output=True, text=True)
        assert execute.returncode == 0, execute.stderr
        for name in (
            config.PHASE4_EVALUATION_DATASET_FILENAME,
            config.PHASE4_METRICS_FILENAME,
            config.PHASE4_RUN_METADATA_FILENAME,
            config.PHASE4_MANIFEST_FILENAME,
        ):
            assert (output_dir / name).is_file(), name

        blocked = subprocess.run(
            base + ["--execute"], cwd=REPO_ROOT, capture_output=True, text=True
        )
        assert blocked.returncode == 1
        assert "already exist" in blocked.stderr

# ==========================================================================
# Hardening Regression Tests
# ==========================================================================
class TestPhase4HardeningRepairs:
    def test_compare_metrics_to_historical_schema_with_aliases(self):
        import pandas as pd
        from mplad.common import config
        from mplad.stream_a import phase4
        runs = list(config.PHASE3_CANONICAL_RUN_IDS)
        metrics_df = pd.DataFrame({
            "run_id": runs, "average_precision": [0.3] * 10, "roc_auc": [0.9] * 10,
            "precision_at_1pct": [0.1] * 10, "recall_at_1pct": [0.6] * 10, "f1_at_1pct": [0.1] * 10,
            "tp": [30] * 10, "fp": [270] * 10, "fn": [17] * 10, "tn": [29683] * 10
        })
        historical_ref = pd.DataFrame({
            "run_id": runs, "runtime_seconds": [999.99] * 10, 
            "AP (Layer 1)": [0.3] * 10, "ROC_AUC (Layer 1)": [0.9] * 10,
            "Precision @1%": [0.1] * 10, "Recall @1%": [0.6] * 10, "F1 @1%": [0.1] * 10,
            "TP": [30] * 10, "FP": [270] * 10, "FN": [17] * 10, "TN": [29683] * 10
        })
        comp = phase4.compare_metrics_to_reference(metrics_df, historical_ref, expected_run_ids=runs)
        assert comp["matches_rounded_reference"].all()

    def test_manifest_rejects_traversal_and_absolute_paths(self):
        import pytest
        from mplad.common.manifest import ManifestError, validate_manifest_structure
        for bad_name in ("../outside.csv", "sub/nested.csv", "/abs/file.csv"):
            bad_manifest = {"manifest_version": 1, "created_utc": "2026", "artifacts": {bad_name: {"sha256": "a"*64, "size_bytes": 10}}}
            with pytest.raises(ManifestError):
                validate_manifest_structure(bad_manifest)
