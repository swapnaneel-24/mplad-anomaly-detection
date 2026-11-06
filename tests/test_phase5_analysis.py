"""Lightweight software-structure tests for the Phase 5A analysis layer.

These tests run on SYNTHETIC fixtures (in-memory aligned dicts, small
synthetic Phase 4 evaluation datasets written to tmp_path). They validate
the software contract -- dataset/provenance validation, cross-run row_id
consistency, bootstrap protocol (determinism, stratification, pairing,
saved-flag threshold policy), metric formulas against hand-computed
examples, pairwise matrices, multi-threshold tie handling, hypergeometric
tails, agreement-group partition, discovery-curve correctness, manifest
handling, protection mechanisms -- and never touch the real repository
dataset or the canonical artifacts.
"""
from __future__ import annotations

import json
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
    ManifestVerificationError,
    artifact_entry,
    build_manifest,
    load_manifest,
    verify_manifest,
)
from mplad.stream_a import phase3
from mplad.stream_a import phase5_analysis as p5

REPO_ROOT = Path(__file__).resolve().parents[1]

PHASE5_OUTPUT_FILES = (
    config.PHASE5_BOOTSTRAP_METRICS_FILENAME,
    config.PHASE5_PAIRED_BOOTSTRAP_DIFFERENCES_FILENAME,
    config.PHASE5_PAIRWISE_SPEARMAN_FILENAME,
    config.PHASE5_PAIRWISE_JACCARD_FILENAME,
    config.PHASE5_MULTITHRESHOLD_AGREEMENT_FILENAME,
    config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME,
    config.PHASE5_AGREEMENT_GROUPS_FILENAME,
    config.PHASE5_FRAUD_DISCOVERY_CURVE_FILENAME,
    config.PHASE5_RUN_METADATA_FILENAME,
    config.PHASE5_MANIFEST_FILENAME,
)

# --------------------------------------------------------------------------
# Synthetic data helpers (schemas identical to the real Phase 4 outputs)
# --------------------------------------------------------------------------

ALL_RUNS = list(config.PHASE3_CANONICAL_RUN_IDS)


def make_eval_dataset(run_data: dict, row_ids, labels, run_order=None) -> pd.DataFrame:
    """Long-form evaluation dataset with the exact Phase 4 output schema.

    ``run_data`` maps run_id -> (anomaly_score array, flag array); the
    native_score column is derived as -anomaly_score (the canonical
    orientation).
    """
    frames = []
    for run_id in run_order or run_data:
        anomaly, flags = run_data[run_id]
        anomaly = np.asarray(anomaly, dtype=np.float64)
        flags = np.asarray(flags)
        frames.append(
            pd.DataFrame(
                {
                    "run_id": run_id,
                    "row_id": np.asarray(row_ids),
                    "Class": np.asarray(labels),
                    "native_score": -anomaly,
                    "anomaly_score": anomaly,
                    "flag": flags,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def make_metadata_payload(run_ids, sample_size, fraud_count) -> dict:
    """Phase 4 run-metadata JSON payload (the fields Phase 5A consumes)."""
    return {
        "phase": "4",
        "stream": "A",
        "layer": "label_based_evaluation",
        "run_mode": "execute",
        "run_ids": list(run_ids),
        "sample": {
            "sample_size": int(sample_size),
            "fraud_count": int(fraud_count),
            "fraud_prevalence": fraud_count / sample_size,
        },
    }


def write_phase4_outputs(tmp_path: Path, dataset_df: pd.DataFrame, payload: dict,
                         with_manifest: bool = False):
    """Write a synthetic Phase 4 output pair (CSV + JSON) to tmp_path."""
    p4_dir = tmp_path / "phase4"
    p4_dir.mkdir(parents=True, exist_ok=True)
    ds_path = p4_dir / config.PHASE4_EVALUATION_DATASET_FILENAME
    dataset_df.to_csv(ds_path, index=False)
    meta_path = p4_dir / config.PHASE4_RUN_METADATA_FILENAME
    meta_path.write_text(json.dumps(payload), encoding="utf-8")
    if with_manifest:
        manifest = build_manifest(
            {
                config.PHASE4_EVALUATION_DATASET_FILENAME: ds_path,
                config.PHASE4_RUN_METADATA_FILENAME: meta_path,
            }
        )
        (p4_dir / config.PHASE5_INPUT_MANIFEST_FILENAME).write_text(
            json.dumps(manifest), encoding="utf-8"
        )
    return ds_path, meta_path


def make_synthetic_phase4_outputs(n: int = 1000, n_frauds: int = 12, seed: int = 0):
    """A full ten-run synthetic Phase 4 output pair (frauds biased to high
    anomaly_score, flags following the bottom-1% native rule like Phase 3)."""
    rng = np.random.RandomState(seed)
    row_ids = np.arange(5000, 5000 + n)
    labels = np.zeros(n, dtype=np.int64)
    labels[rng.choice(n, size=n_frauds, replace=False)] = 1
    run_data = {}
    for i, run_id in enumerate(ALL_RUNS):
        native = rng.normal(0.0, 1.0, size=n)
        native[labels == 1] = rng.normal(-3.0 - 0.05 * i, 0.9, size=n_frauds)
        threshold = np.percentile(native, config.THRESHOLD_PERCENTILE)
        flags = np.where(native <= threshold, 1, 0).astype(np.uint8)
        run_data[run_id] = ((-native).astype(np.float64), flags)
    dataset = make_eval_dataset(run_data, row_ids, labels, ALL_RUNS)
    payload = make_metadata_payload(ALL_RUNS, n, int(labels.sum()))
    return dataset, payload


def make_aligned(n: int = 60, n_frauds: int = 6, seed: int = 0,
                 runs=("IF_003", "IF_004", "LOF_004")) -> dict:
    """A small in-memory aligned dict; flags are RANDOM (deliberately unlike
    any top-k selection) so saved-flag behaviour is observable."""
    rng = np.random.RandomState(seed)
    labels = np.zeros(n, dtype=np.int64)
    labels[rng.choice(n, size=n_frauds, replace=False)] = 1
    run_entries = {}
    for i, run_id in enumerate(runs):
        anomaly = rng.normal(0.0, 1.0, size=n)
        anomaly[labels == 1] += 2.5 + 0.1 * i
        flags = np.zeros(n, dtype=np.uint8)
        flags[rng.choice(n, size=max(2, n // 15), replace=False)] = 1
        run_entries[run_id] = {"anomaly_score": anomaly, "flag": flags}
    return {
        "row_ids": np.arange(100, 100 + n),
        "labels": labels,
        "runs": run_entries,
        "run_ids": list(runs),
        "sample_size": n,
        "fraud_count": int(labels.sum()),
    }


def aligned_from_runs(run_scores: dict, run_flags: dict = None, labels=None) -> dict:
    """Build an aligned dict directly from score arrays (tiny hand cases)."""
    run_flags = run_flags or {}
    n = len(next(iter(run_scores.values())))
    labels = np.zeros(n, dtype=np.int64) if labels is None else np.asarray(labels)
    runs = {}
    for run_id, scores in run_scores.items():
        flags = run_flags.get(run_id, np.zeros(n, dtype=np.uint8))
        runs[run_id] = {
            "anomaly_score": np.asarray(scores, dtype=np.float64),
            "flag": np.asarray(flags),
        }
    return {
        "row_ids": np.arange(n),
        "labels": labels,
        "runs": runs,
        "run_ids": list(run_scores),
        "sample_size": n,
        "fraud_count": int(np.count_nonzero(labels == 1)),
    }


# --------------------------------------------------------------------------
# The hand-computed fixtures (all values verified by hand; see assertions)
# --------------------------------------------------------------------------

# 10 rows; frauds at positions 2 and 7. anomaly = -native (higher = more
# anomalous). Ranked descending: pos2(F), pos0(N), pos1(N), pos7(F), rest.
#   AP  = (1/1 + 2/4) / 2      = 0.75
#   AUC = (8 + 6) / (2 * 8)    = 0.875
HAND_Y = np.array([0, 0, 1, 0, 0, 0, 0, 1, 0, 0])
HAND_ANOMALY = np.array([10, 9, 12, 6, 5, 4, 3, 7, 2, 1], dtype=np.float64)
# Saved flags at positions 0 and 2 (deliberately NOT the top-2 by score,
# which would be positions 2 and 0 -- close, but position 1 outranks 7):
#   TP=1 (pos2), FP=1 (pos0), FN=1 (pos7), TN=7 -> P = R = F1 = 0.5.
HAND_FLAGS_MIXED = np.array([1, 0, 1, 0, 0, 0, 0, 0, 0, 0], dtype=np.uint8)
HAND_FLAGS_BOTH_FRAUDS = np.array([0, 0, 1, 0, 0, 0, 0, 1, 0, 0], dtype=np.uint8)
HAND_FLAGS_NO_FRAUDS = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0], dtype=np.uint8)


# ==========================================================================
# Phase 4 run-metadata JSON validation
# ==========================================================================

class TestPhase4MetadataJSON:
    def test_valid_payload_summary(self):
        payload = make_metadata_payload(["IF_001", "LOF_001"], 300, 4)
        summary = p5.validate_phase4_run_metadata(payload)
        assert summary == {"run_ids": ["IF_001", "LOF_001"], "sample_size": 300, "fraud_count": 4}

    def test_non_dict_rejected(self):
        with pytest.raises(p5.Phase4ProvenanceError, match="JSON object"):
            p5.validate_phase4_run_metadata([1, 2, 3])

    def test_wrong_phase_rejected(self):
        payload = make_metadata_payload(["IF_001"], 10, 2)
        payload["phase"] = "3"
        with pytest.raises(p5.Phase4ProvenanceError, match="phase"):
            p5.validate_phase4_run_metadata(payload)

    def test_missing_run_ids_rejected(self):
        payload = make_metadata_payload(["IF_001"], 10, 2)
        del payload["run_ids"]
        with pytest.raises(p5.Phase4ProvenanceError, match="run_ids"):
            p5.validate_phase4_run_metadata(payload)

    def test_duplicate_run_ids_rejected(self):
        payload = make_metadata_payload(["IF_001", "IF_001"], 10, 2)
        with pytest.raises(p5.Phase4ProvenanceError, match="duplicate"):
            p5.validate_phase4_run_metadata(payload)

    def test_invalid_sample_size_rejected(self):
        payload = make_metadata_payload(["IF_001"], 10, 2)
        payload["sample"]["sample_size"] = 0
        with pytest.raises(p5.Phase4ProvenanceError, match="sample_size"):
            p5.validate_phase4_run_metadata(payload)

    def test_single_class_fraud_count_rejected(self):
        payload = make_metadata_payload(["IF_001"], 10, 10)
        with pytest.raises(p5.Phase4ProvenanceError, match="fraud_count"):
            p5.validate_phase4_run_metadata(payload)

    def test_missing_file_raises_clear_error(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="phase4_run_metadata"):
            p5.load_phase4_run_metadata(tmp_path / "phase4_run_metadata.json")

    def test_invalid_json_rejected(self, tmp_path):
        path = tmp_path / "phase4_run_metadata.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(p5.Phase4ProvenanceError, match="not valid JSON"):
            p5.load_phase4_run_metadata(path)


# ==========================================================================
# Phase 4 evaluation dataset validation
# ==========================================================================

class TestDatasetValidation:
    @pytest.fixture()
    def small_dataset(self):
        row_ids = np.arange(20, 26)
        # non-palindromic on purpose (the Class-mismatch test reverses it)
        labels = np.array([0, 1, 0, 0, 0, 1])
        run_data = {
            "IF_001": (np.array([3.0, 5.0, 1.0, 2.0, 4.0, 0.5]), np.array([0, 1, 1, 0, 0, 0], dtype=np.uint8)),
            "LOF_001": (np.array([2.5, 4.5, 1.5, 1.0, 3.5, 0.2]), np.array([0, 0, 1, 1, 1, 0], dtype=np.uint8)),
        }
        return make_eval_dataset(run_data, row_ids, labels), row_ids, labels

    def test_valid_dataset_summary(self, small_dataset):
        dataset, row_ids, labels = small_dataset
        summary = p5.validate_phase4_dataset(dataset, expected_run_ids=["IF_001", "LOF_001"])
        assert summary["sample_size"] == 6
        assert summary["total_rows"] == 12
        assert summary["fraud_count"] == 2
        assert summary["per_run_flagged_counts"] == {"IF_001": 2, "LOF_001": 3}

    def test_missing_column_rejected(self, small_dataset):
        dataset, _, _ = small_dataset
        dataset = dataset.drop(columns=["anomaly_score"])
        with pytest.raises(p5.Phase4DatasetError, match="missing column"):
            p5.validate_phase4_dataset(dataset, expected_run_ids=["IF_001", "LOF_001"])

    def test_extra_column_rejected(self, small_dataset):
        dataset, _, _ = small_dataset
        dataset["extra"] = 1
        with pytest.raises(p5.Phase4DatasetError, match="extra"):
            p5.validate_phase4_dataset(dataset, expected_run_ids=["IF_001", "LOF_001"])

    def test_missing_run_rejected(self, small_dataset):
        dataset, _, _ = small_dataset
        dataset = dataset[dataset["run_id"] != "LOF_001"]
        with pytest.raises(p5.Phase4DatasetError, match="missing run"):
            p5.validate_phase4_dataset(dataset, expected_run_ids=["IF_001", "LOF_001"])

    def test_unexpected_run_rejected(self, small_dataset):
        dataset, _, _ = small_dataset
        with pytest.raises(p5.Phase4DatasetError, match="unexpected run"):
            p5.validate_phase4_dataset(dataset, expected_run_ids=["IF_001"])

    def test_missing_values_rejected(self, small_dataset):
        dataset, _, _ = small_dataset
        dataset.loc[0, "anomaly_score"] = np.nan
        with pytest.raises(p5.Phase4DatasetError, match="missing values"):
            p5.validate_phase4_dataset(dataset, expected_run_ids=["IF_001", "LOF_001"])

    def test_non_finite_scores_rejected(self, small_dataset):
        dataset, _, _ = small_dataset
        dataset.loc[3, "native_score"] = np.inf
        dataset.loc[3, "anomaly_score"] = -np.inf
        with pytest.raises(p5.Phase4DatasetError, match="non-finite"):
            p5.validate_phase4_dataset(dataset, expected_run_ids=["IF_001", "LOF_001"])

    def test_non_binary_flags_rejected(self, small_dataset):
        dataset, _, _ = small_dataset
        dataset.loc[0, "flag"] = 2
        with pytest.raises(p5.Phase4DatasetError, match="binary"):
            p5.validate_phase4_dataset(dataset, expected_run_ids=["IF_001", "LOF_001"])

    def test_non_binary_labels_rejected(self, small_dataset):
        dataset, _, _ = small_dataset
        dataset.loc[1, "Class"] = 2
        with pytest.raises(p5.Phase4DatasetError, match="binary"):
            p5.validate_phase4_dataset(dataset, expected_run_ids=["IF_001", "LOF_001"])

    def test_float_row_ids_rejected(self, small_dataset):
        dataset, _, _ = small_dataset
        dataset["row_id"] = dataset["row_id"].astype(np.float64)
        with pytest.raises(p5.Phase4DatasetError, match="integer dtype"):
            p5.validate_phase4_dataset(dataset, expected_run_ids=["IF_001", "LOF_001"])

    def test_broken_orientation_rejected(self, small_dataset):
        dataset, _, _ = small_dataset
        dataset.loc[2, "anomaly_score"] = dataset.loc[2, "anomaly_score"] + 5.0
        with pytest.raises(p5.Phase4DatasetError, match="orientation"):
            p5.validate_phase4_dataset(dataset, expected_run_ids=["IF_001", "LOF_001"])

    def test_duplicated_run_block_rejected(self, small_dataset):
        dataset, _, _ = small_dataset
        doubled = pd.concat([dataset, dataset[dataset["run_id"] == "IF_001"]], ignore_index=True)
        with pytest.raises(p5.Phase4DatasetError, match="duplicate"):
            p5.validate_phase4_dataset(doubled, expected_run_ids=["IF_001", "LOF_001"])

    def test_positional_cross_run_alignment_would_fail_this_test(self, small_dataset):
        """Required regression: a run whose block was permuted (rows kept
        internally consistent but in a different row_id ORDER) must be a
        hard error -- otherwise any positional cross-run comparison
        (Spearman, Jaccard, paired bootstrap) would silently compare
        mismatched observations."""
        dataset, _, _ = small_dataset
        permuted = dataset[dataset["run_id"] == "LOF_001"].sample(
            frac=1.0, random_state=1
        )
        mixed = pd.concat(
            [dataset[dataset["run_id"] == "IF_001"], permuted], ignore_index=True
        )
        with pytest.raises(p5.Phase4DatasetError, match="row_id sequence differs"):
            p5.validate_phase4_dataset(mixed, expected_run_ids=["IF_001", "LOF_001"])

    def test_class_sequence_mismatch_rejected(self, small_dataset):
        dataset, _, _ = small_dataset
        lof = dataset[dataset["run_id"] == "LOF_001"].copy()
        lof["Class"] = lof["Class"].values[::-1]  # non-palindromic -> differs
        mixed = pd.concat([dataset[dataset["run_id"] == "IF_001"], lof], ignore_index=True)
        with pytest.raises(p5.Phase4DatasetError, match="sequence differs"):
            p5.validate_phase4_dataset(mixed, expected_run_ids=["IF_001", "LOF_001"])

    def test_metadata_sample_size_mismatch_rejected(self, small_dataset):
        dataset, _, _ = small_dataset
        summary = {"run_ids": ["IF_001", "LOF_001"], "sample_size": 7, "fraud_count": 2}
        with pytest.raises(p5.Phase4DatasetError, match="sample size mismatch"):
            p5.validate_phase4_dataset(dataset, expected_run_ids=["IF_001", "LOF_001"], run_metadata=summary)

    def test_metadata_fraud_count_mismatch_rejected(self, small_dataset):
        dataset, _, _ = small_dataset
        summary = {"run_ids": ["IF_001", "LOF_001"], "sample_size": 6, "fraud_count": 3}
        with pytest.raises(p5.Phase4DatasetError, match="fraud count mismatch"):
            p5.validate_phase4_dataset(dataset, expected_run_ids=["IF_001", "LOF_001"], run_metadata=summary)

    def test_metadata_run_set_mismatch_rejected(self, small_dataset):
        dataset, _, _ = small_dataset
        summary = {"run_ids": ["IF_001", "LOF_002"], "sample_size": 6, "fraud_count": 2}
        with pytest.raises(p5.Phase4DatasetError, match="run set"):
            p5.validate_phase4_dataset(dataset, expected_run_ids=["IF_001", "LOF_001"], run_metadata=summary)

    def test_load_roundtrip_from_csv(self, small_dataset, tmp_path):
        dataset, row_ids, labels = small_dataset
        path = tmp_path / "ds.csv"
        dataset.to_csv(path, index=False)
        loaded = p5.load_phase4_dataset(path, expected_run_ids=["IF_001", "LOF_001"])
        assert list(loaded.columns) == p5.EVALUATION_DATASET_COLUMNS
        summary = p5.validate_phase4_dataset(loaded, expected_run_ids=["IF_001", "LOF_001"])
        assert summary["per_run_flagged_counts"] == {"IF_001": 2, "LOF_001": 3}

    def test_missing_dataset_file_raises_clear_error(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="phase4_evaluation_dataset"):
            p5.load_phase4_dataset(tmp_path / "phase4_evaluation_dataset.csv")


# ==========================================================================
# Aligned extraction
# ==========================================================================

class TestAlignedExtraction:
    def test_extraction_preserves_order_and_values(self, small_dataset_like=None):
        row_ids = np.array([41, 40, 39, 38])
        labels = np.array([0, 1, 0, 1])
        run_data = {
            "IF_001": (np.array([1.0, 4.0, 2.0, 3.0]), np.array([0, 1, 0, 1], dtype=np.uint8)),
            "LOF_001": (np.array([0.5, 3.0, 2.5, 1.5]), np.array([0, 0, 1, 1], dtype=np.uint8)),
        }
        dataset = make_eval_dataset(run_data, row_ids, labels)
        aligned = p5.extract_aligned_runs(dataset, ["IF_001", "LOF_001"])
        assert aligned["row_ids"].tolist() == [41, 40, 39, 38]  # NOT sorted
        assert aligned["labels"].tolist() == [0, 1, 0, 1]
        assert aligned["runs"]["IF_001"]["anomaly_score"].tolist() == [1.0, 4.0, 2.0, 3.0]
        assert aligned["runs"]["LOF_001"]["flag"].tolist() == [0, 0, 1, 1]
        assert aligned["fraud_count"] == 2

    def test_extraction_rejects_inconsistent_sequences(self):
        row_ids = np.arange(4)
        labels = np.array([0, 1, 0, 0])
        run_data = {
            "IF_001": (np.array([1.0, 2.0, 3.0, 4.0]), np.zeros(4, dtype=np.uint8)),
            "LOF_001": (np.array([4.0, 3.0, 2.0, 1.0]), np.zeros(4, dtype=np.uint8)),
        }
        dataset = make_eval_dataset(run_data, row_ids, labels)
        dataset.loc[dataset["run_id"] == "LOF_001", "row_id"] = [3, 2, 1, 0]
        with pytest.raises(p5.Phase4DatasetError, match="sequence differs"):
            p5.extract_aligned_runs(dataset, ["IF_001", "LOF_001"])

    def test_extraction_rejects_missing_run(self):
        row_ids = np.arange(4)
        labels = np.zeros(4, dtype=np.int64)
        dataset = make_eval_dataset(
            {"IF_001": (np.arange(4, dtype=float), np.zeros(4, dtype=np.uint8))},
            row_ids, labels,
        )
        with pytest.raises(p5.Phase4DatasetError, match="missing from the dataset"):
            p5.extract_aligned_runs(dataset, ["IF_001", "LOF_001"])


# ==========================================================================
# Bootstrap protocol
# ==========================================================================

class TestBootstrapMetrics:
    def test_metrics_against_hand_computed_example(self):
        vals = p5.evaluate_bootstrap_metrics(HAND_Y, HAND_ANOMALY, HAND_FLAGS_MIXED)
        assert vals["average_precision"] == pytest.approx(0.75)
        assert vals["roc_auc"] == pytest.approx(0.875)
        assert vals["precision_at_1pct"] == pytest.approx(0.5)
        assert vals["recall_at_1pct"] == pytest.approx(0.5)
        assert vals["f1_at_1pct"] == pytest.approx(0.5)

    def test_perfect_flags_hand_case(self):
        vals = p5.evaluate_bootstrap_metrics(HAND_Y, HAND_ANOMALY, HAND_FLAGS_BOTH_FRAUDS)
        assert vals["precision_at_1pct"] == pytest.approx(1.0)
        assert vals["recall_at_1pct"] == pytest.approx(1.0)
        assert vals["f1_at_1pct"] == pytest.approx(1.0)

    def test_zero_division_hand_case(self):
        vals = p5.evaluate_bootstrap_metrics(HAND_Y, HAND_ANOMALY, HAND_FLAGS_NO_FRAUDS)
        assert vals["precision_at_1pct"] == 0.0
        assert vals["recall_at_1pct"] == 0.0
        assert vals["f1_at_1pct"] == 0.0

    def test_single_class_rejected(self):
        with pytest.raises(p5.Phase5Error, match="single ground-truth class"):
            p5.evaluate_bootstrap_metrics(
                np.zeros(5, dtype=int), np.arange(5.0), np.zeros(5, dtype=np.uint8)
            )

    def test_shape_mismatch_rejected(self):
        with pytest.raises(p5.Phase5Error, match="equal length"):
            p5.evaluate_bootstrap_metrics(HAND_Y, HAND_ANOMALY[:-1], HAND_FLAGS_MIXED)


class TestStratifiedResampling:
    def test_prevalence_preserved_exactly_in_every_replicate(self):
        aligned = make_aligned(n=50, n_frauds=6, seed=3)
        for idx in p5.iter_stratified_bootstrap_indices(aligned["labels"], 25, seed=9):
            assert idx.shape == (50,)
            assert int(aligned["labels"][idx].sum()) == 6

    def test_deterministic_given_seed(self):
        labels = make_aligned(n=40, seed=1)["labels"]
        a = list(p5.iter_stratified_bootstrap_indices(labels, 5, seed=42))
        b = list(p5.iter_stratified_bootstrap_indices(labels, 5, seed=42))
        assert len(a) == 5
        for x, y in zip(a, b):
            assert np.array_equal(x, y)

    def test_single_class_rejected(self):
        with pytest.raises(p5.Phase5Error, match="both classes"):
            list(p5.iter_stratified_bootstrap_indices(np.zeros(5, dtype=int), 3, seed=0))

    def test_invalid_replicate_count_rejected(self):
        labels = make_aligned(n=10, seed=0)["labels"]
        with pytest.raises(p5.Phase5Error, match="n_replicates"):
            list(p5.iter_stratified_bootstrap_indices(labels, 0, seed=0))


class TestBootstrapDiagnostics:
    def test_determinism_same_seed_identical_results(self):
        aligned = make_aligned(n=60, seed=5)
        r1 = p5.run_bootstrap_diagnostics(aligned, n_replicates=15, seed=7, verbose=False)
        r2 = p5.run_bootstrap_diagnostics(aligned, n_replicates=15, seed=7, verbose=False)
        pd.testing.assert_frame_equal(r1["bootstrap_metrics"], r2["bootstrap_metrics"])
        pd.testing.assert_frame_equal(r1["paired_differences"], r2["paired_differences"])
        for run_id, metrics in r1["replicate_values"].items():
            for metric, arr in metrics.items():
                assert np.array_equal(arr, r2["replicate_values"][run_id][metric])

    def test_different_seed_changes_replicate_values(self):
        aligned = make_aligned(n=60, seed=5)
        r1 = p5.run_bootstrap_diagnostics(aligned, n_replicates=15, seed=7, verbose=False)
        r3 = p5.run_bootstrap_diagnostics(aligned, n_replicates=15, seed=8, verbose=False)
        assert not np.array_equal(
            r1["replicate_values"]["IF_003"]["average_precision"],
            r3["replicate_values"]["IF_003"]["average_precision"],
        )

    def test_paired_bootstrap_uses_identical_indices(self):
        """Required case: the LOF_004-minus-IF_003 comparison resamples the
        SAME observations for both methods -- verified by regenerating the
        replicate indices from the same seed and recomputing by hand."""
        aligned = make_aligned(n=60, seed=11)
        n_rep, seed = 12, 123
        result = p5.run_bootstrap_diagnostics(aligned, n_replicates=n_rep, seed=seed, verbose=False)
        for i, idx in enumerate(p5.iter_stratified_bootstrap_indices(aligned["labels"], n_rep, seed)):
            y_b = aligned["labels"][idx]
            for run_id in ("IF_003", "LOF_004"):
                manual = p5.evaluate_bootstrap_metrics(
                    y_b,
                    aligned["runs"][run_id]["anomaly_score"][idx],
                    aligned["runs"][run_id]["flag"][idx],
                )
                for metric, value in manual.items():
                    assert result["replicate_values"][run_id][metric][i] == pytest.approx(value)

    def test_point_estimates_match_full_sample_evaluation(self):
        aligned = make_aligned(n=60, seed=2)
        result = p5.run_bootstrap_diagnostics(aligned, n_replicates=10, seed=3, verbose=False)
        for run_id in config.PHASE5_BOOTSTRAP_RUN_IDS:
            manual = p5.evaluate_bootstrap_metrics(
                aligned["labels"],
                aligned["runs"][run_id]["anomaly_score"],
                aligned["runs"][run_id]["flag"],
            )
            for metric, value in manual.items():
                row = result["bootstrap_metrics"][
                    (result["bootstrap_metrics"]["run_id"] == run_id)
                    & (result["bootstrap_metrics"]["metric"] == metric)
                ]
                assert row["point_estimate"].iloc[0] == pytest.approx(value)

    def test_saved_flags_policy_no_threshold_reselection(self):
        """Required case: fixed-threshold metrics inside replicates use the
        SAVED flags -- a run whose saved flags are all zero keeps P/R/F1 at
        exactly 0.0 in every replicate (a top-1% reselection would not)."""
        aligned = make_aligned(n=60, seed=13)
        aligned["runs"]["LOF_004"]["flag"] = np.zeros(60, dtype=np.uint8)
        result = p5.run_bootstrap_diagnostics(aligned, n_replicates=10, seed=4, verbose=False)
        lof = result["replicate_values"]["LOF_004"]
        for metric in ("precision_at_1pct", "recall_at_1pct", "f1_at_1pct"):
            assert np.all(lof[metric] == 0.0)
            row = result["bootstrap_metrics"][
                (result["bootstrap_metrics"]["run_id"] == "LOF_004")
                & (result["bootstrap_metrics"]["metric"] == metric)
            ]
            assert row["ci_lower"].iloc[0] == 0.0 and row["ci_upper"].iloc[0] == 0.0
        assert np.all(lof["average_precision"] > 0.0)

    def test_output_shapes_and_ci_ordering(self):
        aligned = make_aligned(n=60, seed=6)
        result = p5.run_bootstrap_diagnostics(aligned, n_replicates=20, seed=5, verbose=False)
        metrics = result["bootstrap_metrics"]
        assert list(metrics.columns) == p5.BOOTSTRAP_METRICS_COLUMNS
        assert len(metrics) == 3 * 5  # 3 runs x 5 metrics
        assert set(metrics["run_id"]) == set(config.PHASE5_BOOTSTRAP_RUN_IDS)
        assert (metrics["ci_lower"] <= metrics["ci_upper"]).all()
        assert (metrics["n_replicates"] == 20).all()
        paired = result["paired_differences"]
        assert list(paired.columns) == p5.PAIRED_DIFFERENCES_COLUMNS
        assert len(paired) == 5
        assert (paired["comparison"] == "LOF_004 - IF_003").all()
        assert (paired["ci_lower"] <= paired["ci_upper"]).all()

    def test_paired_point_estimate_is_full_sample_difference(self):
        aligned = make_aligned(n=60, seed=6)
        result = p5.run_bootstrap_diagnostics(aligned, n_replicates=5, seed=5, verbose=False)
        point = result["point_estimates"]
        for metric in p5.BOOTSTRAP_METRIC_NAMES:
            row = result["paired_differences"][
                result["paired_differences"]["metric"] == metric
            ]
            expected = point["LOF_004"][metric] - point["IF_003"][metric]
            assert row["point_estimate"].iloc[0] == pytest.approx(expected)

    def test_invalid_parameters_rejected(self):
        aligned = make_aligned(n=30, seed=0)
        with pytest.raises(p5.Phase5Error, match="n_replicates"):
            p5.run_bootstrap_diagnostics(aligned, n_replicates=0, seed=1)
        with pytest.raises(p5.Phase5Error, match="ci_level"):
            p5.run_bootstrap_diagnostics(aligned, n_replicates=5, seed=1, ci_level=1.5)
        with pytest.raises(p5.Phase5Error, match="missing from the aligned data"):
            p5.run_bootstrap_diagnostics(aligned, n_replicates=5, seed=1, bootstrap_run_ids=["IF_099"])
        with pytest.raises(p5.Phase5Error, match="part of the bootstrapped runs"):
            p5.run_bootstrap_diagnostics(
                aligned, n_replicates=5, seed=1,
                bootstrap_run_ids=["IF_003", "IF_004"],
                paired_runs=("IF_003", "LOF_004"),
            )

    def test_diagnostics_recorded_for_provenance(self):
        aligned = make_aligned(n=30, seed=0)
        result = p5.run_bootstrap_diagnostics(aligned, n_replicates=5, seed=99, verbose=False)
        d = result["diagnostics"]
        assert d["n_replicates"] == 5 and d["seed"] == 99
        assert d["paired_comparison"]["shared_indices"] is True
        assert d["paired_comparison"]["definition"] == "LOF_004 - IF_003"
        assert "never reselected" in d["threshold_policy"]
        assert "exploratory" in d["selection_caveat"].lower()


# ==========================================================================
# Pairwise Spearman correlation
# ==========================================================================

class TestPairwiseSpearman:
    def test_hand_cases_identity_and_reverse(self):
        aligned = aligned_from_runs(
            {"A": [1.0, 2.0, 3.0, 4.0], "B": [4.0, 3.0, 2.0, 1.0]}
        )
        corr = p5.compute_pairwise_spearman(aligned)
        assert corr.loc["A", "A"] == 1.0
        assert corr.loc["B", "B"] == 1.0
        assert corr.loc["A", "B"] == pytest.approx(-1.0)
        assert corr.loc["B", "A"] == pytest.approx(-1.0)

    def test_tie_handling_hand_case(self):
        # ranks A = [1.5, 1.5, 3], B = [1, 2.5, 2.5] -> Pearson = 0.5
        aligned = aligned_from_runs({"A": [1.0, 1.0, 2.0], "B": [1.0, 2.0, 2.0]})
        assert p5.compute_pairwise_spearman(aligned).loc["A", "B"] == pytest.approx(0.5)

    def test_matches_scipy_on_random_data(self):
        from scipy.stats import spearmanr

        rng = np.random.RandomState(7)
        scores = {
            "A": rng.normal(size=200),
            "B": 0.4 * np.arange(200) + rng.normal(size=200) * 20,
            "C": rng.normal(size=200),
        }
        scores["A"][::20] = 1.0  # inject ties
        aligned = aligned_from_runs(scores)
        corr = p5.compute_pairwise_spearman(aligned)
        expected = spearmanr(scores["A"], scores["B"]).statistic
        assert corr.loc["A", "B"] == pytest.approx(expected)

    def test_matrix_properties_on_ten_runs(self):
        dataset, payload = make_synthetic_phase4_outputs(n=400, n_frauds=6, seed=1)
        aligned = p5.extract_aligned_runs(dataset, ALL_RUNS)
        corr = p5.compute_pairwise_spearman(aligned)
        assert corr.shape == (10, 10)
        assert list(corr.index) == ALL_RUNS and list(corr.columns) == ALL_RUNS
        assert np.allclose(np.diag(corr), 1.0)
        assert np.allclose(corr.values, corr.values.T)
        assert ((corr.values > -1.000001) & (corr.values < 1.000001)).all()

    def test_constant_scores_rejected(self):
        aligned = aligned_from_runs({"A": [1.0, 2.0, 3.0], "B": [2.0, 2.0, 2.0]})
        with pytest.raises(p5.Phase5Error, match="constant"):
            p5.compute_pairwise_spearman(aligned)

    def test_higher_score_means_more_anomalous_orientation(self):
        # Identical rankings -> +1; the SAME vectors read as native scores
        # (lower = more anomalous) would be a perfect DISagreement.
        aligned = aligned_from_runs({"A": [1.0, 2.0, 3.0], "B": [1.0, 2.0, 3.0]})
        assert p5.compute_pairwise_spearman(aligned).loc["A", "B"] == pytest.approx(1.0)


# ==========================================================================
# Pairwise Jaccard (saved 1% flags)
# ==========================================================================

class TestPairwiseJaccard:
    def test_hand_case(self):
        aligned = aligned_from_runs(
            {"A": [1.0, 2.0, 3.0, 4.0], "B": [4.0, 3.0, 2.0, 1.0]},
            run_flags={
                "A": np.array([1, 1, 0, 0], dtype=np.uint8),
                "B": np.array([1, 0, 1, 0], dtype=np.uint8),
            },
        )
        jac = p5.compute_pairwise_jaccard(aligned)
        assert jac.loc["A", "B"] == pytest.approx(1.0 / 3.0)  # |{0,1}n{0,2}| / |{0,1,2}|
        assert jac.loc["A", "A"] == 1.0
        assert np.allclose(jac.values, jac.values.T)

    def test_both_empty_selections_defined_as_one(self):
        aligned = aligned_from_runs(
            {"A": [1.0, 2.0], "B": [2.0, 1.0]},
            run_flags={"A": np.zeros(2, dtype=np.uint8), "B": np.zeros(2, dtype=np.uint8)},
        )
        assert p5.compute_pairwise_jaccard(aligned).loc["A", "B"] == 1.0

    def test_matrix_properties_on_ten_runs(self):
        dataset, _ = make_synthetic_phase4_outputs(n=400, n_frauds=6, seed=2)
        aligned = p5.extract_aligned_runs(dataset, ALL_RUNS)
        jac = p5.compute_pairwise_jaccard(aligned)
        assert jac.shape == (10, 10)
        assert np.allclose(np.diag(jac), 1.0)
        assert ((jac.values >= 0.0) & (jac.values <= 1.0)).all()
        # Jaccard is computed from the saved flags, not from scores: the
        # diagonal equals 1 and the identity run pair is exact.
        flag_counts = {r: int(np.count_nonzero(aligned["runs"][r]["flag"])) for r in ALL_RUNS}
        for r in ALL_RUNS:
            self_intersect = int(np.count_nonzero(aligned["runs"][r]["flag"] == 1))
            assert flag_counts[r] == self_intersect


# ==========================================================================
# Multi-threshold agreement
# ==========================================================================

class TestDeriveTopK:
    def test_tie_breaking_is_deterministic_and_positional(self):
        scores = np.array([5.0, 5.0, 4.0, 4.0, 3.0])
        np.testing.assert_array_equal(
            p5.derive_topk_selection(scores, 1), np.array([1, 0, 0, 0, 0])
        )
        np.testing.assert_array_equal(
            p5.derive_topk_selection(scores, 2), np.array([1, 1, 0, 0, 0])
        )
        np.testing.assert_array_equal(
            p5.derive_topk_selection(scores, 4), np.array([1, 1, 1, 1, 0])
        )
        # repeated calls are identical (determinism)
        a = p5.derive_topk_selection(scores, 3)
        b = p5.derive_topk_selection(scores, 3)
        assert np.array_equal(a, b)

    def test_k_bounds_validated(self):
        scores = np.arange(5.0)
        with pytest.raises(p5.Phase5Error, match="1 <= k <= n"):
            p5.derive_topk_selection(scores, 0)
        with pytest.raises(p5.Phase5Error, match="1 <= k <= n"):
            p5.derive_topk_selection(scores, 6)


class TestMultithresholdAgreement:
    @pytest.fixture()
    def ten_run_aligned(self):
        dataset, _ = make_synthetic_phase4_outputs(n=1000, n_frauds=12, seed=3)
        return p5.extract_aligned_runs(dataset, ALL_RUNS)

    def test_grid_ks_and_partition(self, ten_run_aligned):
        table, details = p5.compute_multithreshold_agreement(ten_run_aligned)
        assert list(table.columns) == p5.MULTITHRESHOLD_AGREEMENT_COLUMNS
        assert len(table) == 6 * 11  # 6 thresholds x 11 agreement levels
        assert table.groupby("threshold_pct")["k_nominal"].first().tolist() == [1, 2, 5, 10, 20, 50]
        for pct in config.PHASE5_MULTI_THRESHOLD_PERCENTS:
            block = table[table["threshold_pct"] == pct]
            assert block["n_methods"].tolist() == list(range(11))
            assert block["observation_count"].sum() == 1000

    def test_one_percent_uses_saved_flags(self, ten_run_aligned):
        table, details = p5.compute_multithreshold_agreement(ten_run_aligned)
        canonical = table[table["threshold_pct"] == 1.0]
        assert (canonical["selection_source"] == "canonical_saved_flags").all()
        derived = table[table["threshold_pct"] != 1.0]
        assert (derived["selection_source"] == "derived_topk").all()
        # per-run selection sizes at 1% equal the SAVED flag counts (which
        # the percentile rule may make differ slightly from the nominal k)
        saved = {
            r: int(np.count_nonzero(ten_run_aligned["runs"][r]["flag"])) for r in ALL_RUNS
        }
        assert details["per_run_selection_sizes"]["1.0"] == saved
        # derived thresholds select exactly k per run
        for pct, k in ((0.1, 1), (5.0, 50)):
            assert all(
                v == k for v in details["per_run_selection_sizes"][str(float(pct))].values()
            )

    def test_flags_untouched_and_masks_separate(self, ten_run_aligned):
        before = {
            r: ten_run_aligned["runs"][r]["flag"].copy() for r in ALL_RUNS
        }
        p5.compute_multithreshold_agreement(ten_run_aligned)
        p5.compute_fraud_discovery_curve(ten_run_aligned)
        for r in ALL_RUNS:
            assert np.array_equal(ten_run_aligned["runs"][r]["flag"], before[r])

    def test_grid_must_fit_sample(self):
        aligned = aligned_from_runs({"A": np.arange(100.0), "B": np.arange(100.0)[::-1]})
        with pytest.raises(p5.Phase5Error, match="outside 1..100"):
            p5.compute_multithreshold_agreement(
                aligned, threshold_percentages=[0.1, 1.0]
            )

    def test_agreement_counts_hand_case(self):
        # 4 runs, 8 observations, derived top-k at 25% -> k = 2 per run.
        # Scores are crafted so the runs select: A={0,1}, B={0,2}, C={0,3},
        # D={0,4} -> position 0 selected by all 4 methods; positions 1-4 by
        # exactly 1; positions 5-7 by none.
        scores = {
            "A": np.array([8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]),
            "B": np.array([8.0, 6.0, 7.0, 5.0, 4.0, 3.0, 2.0, 1.0]),
            "C": np.array([8.0, 6.0, 5.0, 7.0, 4.0, 3.0, 2.0, 1.0]),
            "D": np.array([8.0, 6.0, 5.0, 4.0, 7.0, 3.0, 2.0, 1.0]),
        }
        aligned = aligned_from_runs(scores)
        table, details = p5.compute_multithreshold_agreement(
            aligned, threshold_percentages=[25.0]
        )
        block = table[table["threshold_pct"] == 25.0]
        counts = dict(zip(block["n_methods"], block["observation_count"]))
        assert counts == {0: 3, 1: 4, 2: 0, 3: 0, 4: 1}


# ==========================================================================
# Hypergeometric overlap
# ==========================================================================

class TestHypergeometric:
    def test_hand_case_exact_tail(self):
        # N=10, k_a=2, k_b=3, observed=2:
        # P(X>=2) = C(2,2)*C(8,1)/C(10,3) = 8/120 = 1/15
        flags_a = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0], dtype=np.uint8)
        flags_b = np.array([1, 1, 1, 0, 0, 0, 0, 0, 0, 0], dtype=np.uint8)
        result = p5.compute_hypergeometric_overlap(flags_a, flags_b, run_a="IF", run_b="LOF")
        assert result["run_a_flagged"] == 2 and result["run_b_flagged"] == 3
        assert result["observed_intersection"] == 2
        assert result["union_size"] == 3
        assert result["expected_intersection"] == pytest.approx(0.6)
        assert result["enrichment_observed_over_expected"] == pytest.approx(2 / 0.6)
        assert result["survival_upper_tail"] == pytest.approx(1.0 / 15.0)
        assert result["log_survival"] == pytest.approx(np.log(1.0 / 15.0))
        assert result["log10_survival"] == pytest.approx(np.log10(1.0 / 15.0))

    def test_canonical_scale_against_scipy(self):
        from scipy.stats import hypergeom

        n, k = 30000, 300
        rng = np.random.RandomState(0)
        flags_a = np.zeros(n, dtype=np.uint8)
        flags_a[rng.choice(n, size=k, replace=False)] = 1
        # exactly 107 of them also flagged by b, plus 193 others
        shared = np.flatnonzero(flags_a == 1)[:107]
        others = rng.choice(np.flatnonzero(flags_a == 0), size=193, replace=False)
        flags_b = np.zeros(n, dtype=np.uint8)
        flags_b[np.concatenate([shared, others])] = 1
        result = p5.compute_hypergeometric_overlap(flags_a, flags_b)
        assert result["observed_intersection"] == 107
        assert result["union_size"] == 493
        assert result["expected_intersection"] == pytest.approx(3.0)
        assert result["enrichment_observed_over_expected"] == pytest.approx(107.0 / 3.0)
        assert result["survival_upper_tail"] == pytest.approx(
            float(hypergeom.sf(106, 30000, 300, 300)), rel=1e-12
        )
        # log-survival handles the underflow regime: survival ~ 5e-141
        assert result["survival_upper_tail"] > 0.0
        assert result["log10_survival"] < -140
        assert result["log10_survival"] == pytest.approx(
            float(hypergeom.logsf(106, 30000, 300, 300)) / np.log(10.0), rel=1e-12
        )

    def test_zero_intersection(self):
        flags_a = np.array([1, 0, 0, 0], dtype=np.uint8)
        flags_b = np.array([0, 1, 0, 0], dtype=np.uint8)
        result = p5.compute_hypergeometric_overlap(flags_a, flags_b)
        assert result["observed_intersection"] == 0
        assert result["survival_upper_tail"] == 1.0
        assert result["log_survival"] == pytest.approx(0.0)
        assert result["enrichment_observed_over_expected"] == 0.0

    def test_empty_selection_expected_zero_enrichment_nan(self):
        flags_a = np.zeros(5, dtype=np.uint8)
        flags_b = np.array([1, 0, 0, 0, 0], dtype=np.uint8)
        result = p5.compute_hypergeometric_overlap(flags_a, flags_b)
        assert result["expected_intersection"] == 0.0
        assert np.isnan(result["enrichment_observed_over_expected"])
        assert result["survival_upper_tail"] == 1.0  # observed 0 >= 0

    def test_inconsistent_inputs_rejected(self):
        with pytest.raises(p5.Phase5Error, match="equal length"):
            p5.compute_hypergeometric_overlap(
                np.array([1, 0]), np.array([1, 0, 0])
            )
        with pytest.raises(p5.Phase5Error, match="n_observations"):
            p5.compute_hypergeometric_overlap(
                np.array([1, 0]), np.array([1, 0]), n_observations=5
            )

    def test_null_model_interpretation_recorded(self):
        result = p5.compute_hypergeometric_overlap(
            np.array([1, 0]), np.array([1, 0])
        )
        assert "independent uniform random selection" in result["null_model"]
        assert "does not establish" in result["null_model"]


# ==========================================================================
# Agreement-group composition
# ==========================================================================

class TestAgreementGroups:
    def test_hand_case(self):
        flags_a = np.array([1, 1, 0, 0], dtype=np.uint8)
        flags_b = np.array([1, 0, 1, 0], dtype=np.uint8)
        labels = np.array([1, 0, 1, 0])
        groups = p5.compute_agreement_groups(flags_a, flags_b, labels, run_a="IF_003", run_b="LOF_004")
        assert list(groups.columns) == p5.AGREEMENT_GROUPS_COLUMNS
        assert groups["group"].tolist() == ["both", "if_only", "lof_only", "neither"]
        by_group = groups.set_index("group")
        assert by_group.loc["both", "observation_count"] == 1
        assert by_group.loc["both", "fraud_count"] == 1
        assert by_group.loc["if_only", "fraud_count"] == 0
        assert by_group.loc["lof_only", "fraud_count"] == 1
        assert by_group.loc["neither", "observation_count"] == 1
        assert by_group.loc["both", "fraud_proportion"] == pytest.approx(1.0)
        assert by_group.loc["both", "recall_contribution"] == pytest.approx(0.5)
        assert by_group.loc["lof_only", "recall_contribution"] == pytest.approx(0.5)
        assert groups["recall_contribution"].sum() == pytest.approx(1.0)

    def test_exact_exhaustive_partition_on_synthetic_ten_runs(self):
        dataset, _ = make_synthetic_phase4_outputs(n=1000, n_frauds=12, seed=4)
        aligned = p5.extract_aligned_runs(dataset, ALL_RUNS)
        flags_a = aligned["runs"][config.PHASE5_OVERLAP_RUN_A]["flag"]
        flags_b = aligned["runs"][config.PHASE5_OVERLAP_RUN_B]["flag"]
        groups = p5.compute_agreement_groups(flags_a, flags_b, aligned["labels"])
        assert groups["observation_count"].sum() == 1000
        assert groups["fraud_count"].sum() == 12
        assert groups["non_fraud_count"].sum() == 1000 - 12
        assert groups["recall_contribution"].sum() == pytest.approx(1.0)
        # disjointness by construction: both + if_only == flags_a total, etc.
        assert (
            groups.loc[groups["group"].isin(["both", "if_only"]), "observation_count"].sum()
            == int(np.count_nonzero(flags_a == 1))
        )
        assert (
            groups.loc[groups["group"].isin(["both", "lof_only"]), "observation_count"].sum()
            == int(np.count_nonzero(flags_b == 1))
        )

    def test_shape_mismatch_rejected(self):
        with pytest.raises(p5.Phase5Error, match="equal length"):
            p5.compute_agreement_groups(
                np.array([1, 0]), np.array([1, 0]), np.array([1, 0, 0])
            )


# ==========================================================================
# Fraud-discovery curve
# ==========================================================================

class TestFraudDiscoveryCurve:
    def test_hand_case(self):
        aligned = aligned_from_runs(
            {"A": [9.0, 8.0, 7.0, 6.0, 5.0]}, labels=np.array([1, 0, 1, 0, 0])
        )
        curve = p5.compute_fraud_discovery_curve(aligned)
        assert list(curve.columns) == p5.FRAUD_DISCOVERY_CURVE_COLUMNS
        assert curve["budget"].tolist() == [1, 2, 3, 4, 5]
        assert curve["fraud_found"].tolist() == [1, 1, 2, 2, 2]
        assert curve["precision"].tolist() == pytest.approx([1.0, 0.5, 2 / 3, 0.5, 0.4])
        assert curve["recall"].tolist() == pytest.approx([0.5, 0.5, 1.0, 1.0, 1.0])

    def test_tie_breaking_hand_case(self):
        # ties at the top: stable order keeps position 0 before 1, and 2
        # before 3 -- independent of the labels
        aligned = aligned_from_runs(
            {"A": [5.0, 5.0, 3.0, 3.0, 1.0]}, labels=np.array([0, 1, 0, 1, 0])
        )
        curve = p5.compute_fraud_discovery_curve(aligned)
        assert curve["fraud_found"].tolist() == [0, 1, 1, 2, 2]
        assert curve["precision"].tolist() == pytest.approx([0.0, 0.5, 1 / 3, 0.5, 0.4])

    def test_all_runs_shape_and_monotonicity(self):
        dataset, _ = make_synthetic_phase4_outputs(n=400, n_frauds=8, seed=5)
        aligned = p5.extract_aligned_runs(dataset, ALL_RUNS)
        curve = p5.compute_fraud_discovery_curve(aligned)
        assert len(curve) == 10 * 400
        assert curve["run_id"].nunique() == 10
        for _, run_curve in curve.groupby("run_id", sort=False):
            assert run_curve["budget"].tolist() == list(range(1, 401))
            assert (np.diff(run_curve["recall"].to_numpy()) >= -1e-12).all()
            assert run_curve["fraud_found"].tolist() == sorted(run_curve["fraud_found"].tolist())
            assert run_curve["recall"].iloc[-1] == pytest.approx(1.0)
            assert run_curve["precision"].iloc[-1] == pytest.approx(8 / 400)

    def test_labels_used_post_hoc_only(self):
        """The ranking depends only on the scores: permuting the labels must
        not change which positions are reviewed first (fraud_found at the
        tied head is decided by position, and the full-budget totals just
        reflect the label multiset)."""
        scores = {"A": np.array([9.0, 8.0, 7.0, 6.0, 5.0])}
        labels_a = np.array([1, 0, 1, 0, 0])
        labels_b = np.array([0, 1, 0, 0, 1])
        ca = p5.compute_fraud_discovery_curve(aligned_from_runs(scores, labels=labels_a))
        cb = p5.compute_fraud_discovery_curve(aligned_from_runs(scores, labels=labels_b))
        assert ca["budget"].tolist() == cb["budget"].tolist()
        assert ca["fraud_found"].tolist() == [1, 1, 2, 2, 2]
        assert cb["fraud_found"].tolist() == [0, 1, 1, 1, 2]

    def test_no_fraud_rejected(self):
        aligned = aligned_from_runs({"A": [1.0, 2.0, 3.0]})
        with pytest.raises(p5.Phase5Error, match="no fraud"):
            p5.compute_fraud_discovery_curve(aligned)


# ==========================================================================
# No model fitting or refitting
# ==========================================================================

class TestNoFitting:
    def test_no_detector_is_fitted_or_refitted(self, tmp_path):
        """Required case: the full Phase 5A analysis runs to completion while
        every detector fitting entry point is poisoned -- nothing may fit."""
        dataset, payload = make_synthetic_phase4_outputs(n=1000, n_frauds=8, seed=6)
        ds_path, meta_path = write_phase4_outputs(tmp_path, dataset, payload)
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
            result = p5.run_phase5_analysis(
                evaluation_dataset_path=ds_path,
                phase4_run_metadata_path=meta_path,
                output_dir=tmp_path / "out",
                n_replicates=5,
                bootstrap_seed=1,
                verbose=False,
            )
        assert len(result["bootstrap"]) == 15
        assert result["provenance"]["model_fitting"]["models_fitted"] == 0

    def test_module_exposes_no_detector_constructors(self):
        assert not hasattr(p5, "IsolationForest")
        assert not hasattr(p5, "LocalOutlierFactor")
        source = Path(p5.__file__).read_text(encoding="utf-8")
        assert "sklearn.ensemble" not in source
        assert "sklearn.neighbors" not in source


# ==========================================================================
# Dry-run behaviour
# ==========================================================================

class TestDryRun:
    @pytest.fixture()
    def phase4_inputs(self, tmp_path):
        dataset, payload = make_synthetic_phase4_outputs(n=300, n_frauds=5, seed=7)
        return write_phase4_outputs(tmp_path, dataset, payload)

    def test_preflight_writes_nothing(self, phase4_inputs, tmp_path):
        ds_path, meta_path = phase4_inputs
        output_dir = tmp_path / "never_created"
        report = p5.collect_phase5_preflight(
            evaluation_dataset_path=ds_path,
            phase4_run_metadata_path=meta_path,
            output_dir=output_dir,
            n_replicates=5,
            verbose=False,
        )
        assert not output_dir.exists()
        assert report["writes_performed"] is False
        assert report["outputs"]["blocked"] is False

    def test_preflight_computes_no_analysis(self, phase4_inputs, tmp_path):
        ds_path, meta_path = phase4_inputs
        with mock.patch.object(
            p5, "run_bootstrap_diagnostics", side_effect=AssertionError("must not compute")
        ), mock.patch.object(
            p5, "compute_pairwise_spearman", side_effect=AssertionError("must not compute")
        ), mock.patch.object(
            p5, "compute_pairwise_jaccard", side_effect=AssertionError("must not compute")
        ), mock.patch.object(
            p5, "compute_multithreshold_agreement", side_effect=AssertionError("must not compute")
        ), mock.patch.object(
            p5, "compute_hypergeometric_overlap", side_effect=AssertionError("must not compute")
        ), mock.patch.object(
            p5, "compute_agreement_groups", side_effect=AssertionError("must not compute")
        ), mock.patch.object(
            p5, "compute_fraud_discovery_curve", side_effect=AssertionError("must not compute")
        ):
            report = p5.collect_phase5_preflight(
                evaluation_dataset_path=ds_path,
                phase4_run_metadata_path=meta_path,
                output_dir=tmp_path / "out",
                verbose=False,
            )
        assert report["analyses_computed"] is False
        assert report["models_fitted"] == 0
        assert len(report["analyses_planned"]) == 8

    def test_preflight_reports_blocked_outputs(self, phase4_inputs, tmp_path):
        ds_path, meta_path = phase4_inputs
        output_dir = tmp_path / "blocked_out"
        output_dir.mkdir()
        (output_dir / config.PHASE5_BOOTSTRAP_METRICS_FILENAME).write_text("existing")
        report = p5.collect_phase5_preflight(
            evaluation_dataset_path=ds_path,
            phase4_run_metadata_path=meta_path,
            output_dir=output_dir,
            verbose=False,
        )
        assert report["outputs"]["blocked"] is True
        assert (
            output_dir / config.PHASE5_BOOTSTRAP_METRICS_FILENAME
        ).read_text() == "existing"


# ==========================================================================
# Output protection
# ==========================================================================

class TestOutputProtection:
    def test_execute_refuses_existing_outputs_and_preserves_them(self, tmp_path):
        dataset, payload = make_synthetic_phase4_outputs(n=300, n_frauds=5, seed=8)
        ds_path, meta_path = write_phase4_outputs(tmp_path, dataset, payload)
        output_dir = tmp_path / "out"
        output_dir.mkdir(parents=True)
        sentinels = [output_dir / name for name in PHASE5_OUTPUT_FILES]
        for path in sentinels:
            path.write_text("EXISTING OUTPUT -- DO NOT TOUCH")
        with pytest.raises(mplad_io.OutputExistsError) as exc:
            p5.run_phase5_analysis(
                evaluation_dataset_path=ds_path,
                phase4_run_metadata_path=meta_path,
                output_dir=output_dir,
                n_replicates=3,
                verbose=False,
            )
        for path in sentinels:
            assert path.name in str(exc.value)
            assert path.read_text() == "EXISTING OUTPUT -- DO NOT TOUCH"

    def test_overwrite_opt_in_replaces_outputs(self, tmp_path):
        dataset, payload = make_synthetic_phase4_outputs(n=1000, n_frauds=8, seed=9)
        ds_path, meta_path = write_phase4_outputs(tmp_path, dataset, payload)
        output_dir = tmp_path / "out"
        output_dir.mkdir(parents=True)
        (output_dir / config.PHASE5_PAIRWISE_SPEARMAN_FILENAME).write_text("stale")
        result = p5.run_phase5_analysis(
            evaluation_dataset_path=ds_path,
            phase4_run_metadata_path=meta_path,
            output_dir=output_dir,
            n_replicates=3,
            overwrite=True,
            verbose=False,
        )
        assert result["spearman"].shape == (10, 10)
        assert (output_dir / config.PHASE5_PAIRWISE_SPEARMAN_FILENAME).read_text() != "stale"

    def test_precheck_lists_all_ten_conflicts(self, tmp_path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        for name in PHASE5_OUTPUT_FILES:
            (output_dir / name).write_text("x")
        paths = [output_dir / name for name in PHASE5_OUTPUT_FILES]
        with pytest.raises(mplad_io.OutputExistsError) as exc:
            mplad_io.assert_outputs_writable(paths, overwrite=False)
        assert all(p.name in str(exc.value) for p in paths)
        mplad_io.assert_outputs_writable(paths, overwrite=True)


# ==========================================================================
# Input manifest handling
# ==========================================================================

class TestManifestHandling:
    def test_manifest_verified_before_consuming(self, tmp_path):
        dataset, payload = make_synthetic_phase4_outputs(n=1000, n_frauds=8, seed=10)
        ds_path, meta_path = write_phase4_outputs(tmp_path, dataset, payload, with_manifest=True)
        result = p5.run_phase5_analysis(
            evaluation_dataset_path=ds_path,
            phase4_run_metadata_path=meta_path,
            output_dir=tmp_path / "out",
            n_replicates=3,
            verbose=False,
        )
        assert result["input_manifest"]["mode"] == "manifest_verified"
        assert result["input_manifest"]["verified"] is True
        assert result["provenance"]["input_manifest"]["mode"] == "manifest_verified"

    def test_tampered_input_rejected_before_consuming(self, tmp_path):
        dataset, payload = make_synthetic_phase4_outputs(n=300, n_frauds=5, seed=11)
        ds_path, meta_path = write_phase4_outputs(tmp_path, dataset, payload, with_manifest=True)
        # tamper AFTER the manifest was written
        dataset.loc[0, "anomaly_score"] = 999.0
        dataset.to_csv(ds_path, index=False)
        with pytest.raises(ManifestVerificationError, match="mismatch"):
            p5.collect_phase5_preflight(
                evaluation_dataset_path=ds_path,
                phase4_run_metadata_path=meta_path,
                verbose=False,
            )

    def test_legacy_unmanifested_pair_recorded_honestly(self, tmp_path):
        dataset, payload = make_synthetic_phase4_outputs(n=1000, n_frauds=8, seed=12)
        ds_path, meta_path = write_phase4_outputs(tmp_path, dataset, payload)
        result = p5.run_phase5_analysis(
            evaluation_dataset_path=ds_path,
            phase4_run_metadata_path=meta_path,
            output_dir=tmp_path / "out",
            n_replicates=3,
            verbose=False,
        )
        m = result["input_manifest"]
        assert m["present"] is False and m["verified"] is False
        assert m["mode"] == "legacy_unmanifested"
        assert "NOT performed" in m["note"]


# ==========================================================================
# Provenance record
# ==========================================================================

class TestProvenance:
    @pytest.fixture()
    def executed(self, tmp_path):
        dataset, payload = make_synthetic_phase4_outputs(n=1000, n_frauds=8, seed=13)
        ds_path, meta_path = write_phase4_outputs(tmp_path, dataset, payload)
        result = p5.run_phase5_analysis(
            evaluation_dataset_path=ds_path,
            phase4_run_metadata_path=meta_path,
            output_dir=tmp_path / "out",
            n_replicates=7,
            bootstrap_seed=99,
            verbose=False,
        )
        return result, ds_path, meta_path, tmp_path / "out"

    def test_input_hashes_and_parameters_recorded(self, executed):
        result, ds_path, meta_path, out_dir = executed
        provenance = json.loads(
            (out_dir / config.PHASE5_RUN_METADATA_FILENAME).read_text(encoding="utf-8")
        )
        assert provenance["phase"] == "5A"
        assert provenance["inputs"]["evaluation_dataset"]["sha256"] == (
            artifact_entry(ds_path)["sha256"]
        )
        assert provenance["inputs"]["phase4_run_metadata"]["sha256"] == (
            artifact_entry(meta_path)["sha256"]
        )
        assert provenance["bootstrap"]["n_replicates"] == 7
        assert provenance["bootstrap"]["seed"] == 99
        assert provenance["bootstrap"]["ci_method"] == "percentile"
        assert "never reselected" in provenance["bootstrap"]["threshold_policy"]
        assert provenance["model_fitting"]["models_fitted"] == 0
        for key in ("python", "numpy", "pandas", "scikit-learn", "scipy"):
            assert provenance["environment"][key]

    def test_selection_caveat_and_conventions_recorded(self, executed):
        result, ds_path, meta_path, out_dir = executed
        provenance = json.loads(
            (out_dir / config.PHASE5_RUN_METADATA_FILENAME).read_text(encoding="utf-8")
        )
        assert provenance["selection_caveat"] == p5.EXPLORATORY_SELECTION_CAVEAT
        assert "exploratory" in provenance["bootstrap"]["selection_caveat"].lower()
        conventions = provenance["analytical_conventions"]
        assert conventions["tie_breaking"] == p5.TIE_BREAK_POLICY
        assert "independent uniform random selection" in conventions["hypergeometric"]["null_model"]
        assert conventions["multithreshold"]["canonical_threshold_source"] == (
            "saved Phase 3 flags (never rederived)"
        )

    def test_output_manifest_covers_and_verifies(self, executed):
        result, ds_path, meta_path, out_dir = executed
        report = verify_manifest(
            load_manifest(out_dir / config.PHASE5_MANIFEST_FILENAME), out_dir
        )
        assert len(report) == 9  # 8 CSVs + the provenance JSON


# ==========================================================================
# End-to-end (python API + CLI)
# ==========================================================================

class TestEndToEnd:
    def test_full_analysis_output_schemas_and_cross_checks(self, tmp_path):
        dataset, payload = make_synthetic_phase4_outputs(n=1000, n_frauds=12, seed=14)
        ds_path, meta_path = write_phase4_outputs(tmp_path, dataset, payload)
        result = p5.run_phase5_analysis(
            evaluation_dataset_path=ds_path,
            phase4_run_metadata_path=meta_path,
            output_dir=tmp_path / "out",
            n_replicates=25,
            bootstrap_seed=42,
            verbose=False,
        )
        out_dir = tmp_path / "out"
        for name in PHASE5_OUTPUT_FILES:
            path = out_dir / name
            assert path.is_file() and path.stat().st_size > 0, name

        bootstrap = pd.read_csv(out_dir / config.PHASE5_BOOTSTRAP_METRICS_FILENAME)
        assert list(bootstrap.columns) == p5.BOOTSTRAP_METRICS_COLUMNS
        assert len(bootstrap) == 15
        assert set(bootstrap["run_id"]) == set(config.PHASE5_BOOTSTRAP_RUN_IDS)
        assert (bootstrap["n_replicates"] == 25).all()

        paired = pd.read_csv(
            out_dir / config.PHASE5_PAIRED_BOOTSTRAP_DIFFERENCES_FILENAME
        )
        assert list(paired.columns) == p5.PAIRED_DIFFERENCES_COLUMNS
        assert len(paired) == 5
        assert (paired["run_a"] == "IF_003").all() and (paired["run_b"] == "LOF_004").all()

        spearman = pd.read_csv(out_dir / config.PHASE5_PAIRWISE_SPEARMAN_FILENAME, index_col=0)
        assert spearman.shape == (10, 10)
        assert list(spearman.index) == ALL_RUNS
        assert np.allclose(np.diag(spearman), 1.0)

        jaccard = pd.read_csv(out_dir / config.PHASE5_PAIRWISE_JACCARD_FILENAME, index_col=0)
        assert jaccard.shape == (10, 10)
        assert np.allclose(np.diag(jaccard), 1.0)

        agreement = pd.read_csv(out_dir / config.PHASE5_MULTITHRESHOLD_AGREEMENT_FILENAME)
        assert list(agreement.columns) == p5.MULTITHRESHOLD_AGREEMENT_COLUMNS
        assert len(agreement) == 66
        for pct in config.PHASE5_MULTI_THRESHOLD_PERCENTS:
            assert agreement[agreement["threshold_pct"] == pct]["observation_count"].sum() == 1000

        hyper = pd.read_csv(out_dir / config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME)
        assert list(hyper.columns) == p5.HYPERGEOMETRIC_OVERLAP_COLUMNS
        assert len(hyper) == 1
        # cross-check against a direct computation on the aligned data
        aligned = p5.extract_aligned_runs(dataset, ALL_RUNS)
        direct = p5.compute_hypergeometric_overlap(
            aligned["runs"]["IF_003"]["flag"],
            aligned["runs"]["LOF_004"]["flag"],
            n_observations=1000,
        )
        assert hyper["observed_intersection"].iloc[0] == direct["observed_intersection"]
        assert hyper["log10_survival"].iloc[0] == pytest.approx(direct["log10_survival"])

        groups = pd.read_csv(out_dir / config.PHASE5_AGREEMENT_GROUPS_FILENAME)
        assert list(groups.columns) == p5.AGREEMENT_GROUPS_COLUMNS
        assert groups["observation_count"].sum() == 1000
        assert groups["fraud_count"].sum() == 12

        curve = pd.read_csv(out_dir / config.PHASE5_FRAUD_DISCOVERY_CURVE_FILENAME)
        assert list(curve.columns) == p5.FRAUD_DISCOVERY_CURVE_COLUMNS
        assert len(curve) == 10 * 1000
        assert curve.groupby("run_id")["recall"].last().min() == pytest.approx(1.0)

        assert verify_manifest(
            load_manifest(out_dir / config.PHASE5_MANIFEST_FILENAME), out_dir
        )

    def test_cli_preflight_then_execute_then_blocked(self, tmp_path):
        dataset, payload = make_synthetic_phase4_outputs(n=1000, n_frauds=12, seed=15)
        ds_path, meta_path = write_phase4_outputs(tmp_path, dataset, payload)
        output_dir = tmp_path / "cli_out"
        base = [
            sys.executable, "scripts/run_phase5_analysis.py",
            "--allow-noncanonical-sample-size",
            "--evaluation-dataset", str(ds_path),
            "--phase4-metadata", str(meta_path),
            "--output-dir", str(output_dir),
            "--n-replicates", "25",
        ]
        preflight = subprocess.run(base, cwd=REPO_ROOT, capture_output=True, text=True)
        assert preflight.returncode == 0, preflight.stderr
        assert "PREFLIGHT complete" in preflight.stdout
        assert not output_dir.exists()

        execute = subprocess.run(base + ["--execute"], cwd=REPO_ROOT, capture_output=True, text=True)
        assert execute.returncode == 0, execute.stderr
        for name in PHASE5_OUTPUT_FILES:
            assert (output_dir / name).is_file(), name

        blocked = subprocess.run(
            base + ["--execute"], cwd=REPO_ROOT, capture_output=True, text=True
        )
        assert blocked.returncode == 1
        assert "already exist" in blocked.stderr

# ==========================================================================
# Hardening Regression Tests
# ==========================================================================
class TestPhase5HardeningRepairs:
    def test_canonical_sample_size_enforced_when_required(self, tmp_path):
        import pandas as pd
        import json
        import pytest
        from mplad.common import config
        from mplad.stream_a import phase5_analysis
        df = pd.DataFrame({"run_id": ["IF_001"]*100, "row_id": range(100), "Class": [0]*90+[1]*10, "native_score": [0.5]*100, "anomaly_score": [-0.5]*100, "flag": [0]*90+[1]*10})
        eval_p = tmp_path / config.PHASE4_EVALUATION_DATASET_FILENAME
        meta_p = tmp_path / config.PHASE4_RUN_METADATA_FILENAME
        df.to_csv(eval_p, index=False)
        with open(meta_p, "w") as f:
            json.dump({"phase": "4", "run_ids": ["IF_001", "LOF_001"], "sample": {"sample_size": 100, "fraud_count": 10}}, f)
        
        with pytest.raises(phase5_analysis.Phase4DatasetError, match="Canonical Phase 5A execution requires"):
            phase5_analysis.collect_phase5_preflight(
                evaluation_dataset_path=eval_p,
                phase4_run_metadata_path=meta_p,
                expected_run_ids=["IF_001", "LOF_001"],
                require_canonical_sample_size=True
            )
