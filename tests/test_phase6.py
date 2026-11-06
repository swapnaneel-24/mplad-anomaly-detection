"""Tests for the Stream A Phase 6 cross-method consistency layer.

The fixtures build a structurally exact synthetic world whose Phase 5A
outputs are produced by the REAL frozen ``phase5_analysis`` code, so every
cross-check in Phase 6 operates on genuine, internally consistent artifacts.
Unit tests of the group assignment use small hand-built run frames with
explicit flag combinations. No test touches the real repository artifacts.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mplad.common import config
from mplad.common.manifest import (
    ManifestVerificationError,
    build_manifest,
    load_manifest,
    verify_manifest,
)
from mplad.stream_a import phase3
from mplad.stream_a import phase5_analysis as p5a
from mplad.stream_a import phase6 as p6

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "run_phase6.py"

ALL_RUNS = list(config.PHASE3_CANONICAL_RUN_IDS)

#: World geometry: n >= 600 so that every budget in the frozen grid
#: (0.1% of the sample) yields k = round(n * pct / 100) >= 1.
WORLD_N = 600
WORLD_FRAUDS = 15

PHASE5_ARTIFACT_NAMES = [
    config.PHASE5_BOOTSTRAP_METRICS_FILENAME,
    config.PHASE5_PAIRED_BOOTSTRAP_DIFFERENCES_FILENAME,
    config.PHASE5_PAIRWISE_SPEARMAN_FILENAME,
    config.PHASE5_PAIRWISE_JACCARD_FILENAME,
    config.PHASE5_MULTITHRESHOLD_AGREEMENT_FILENAME,
    config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME,
    config.PHASE5_AGREEMENT_GROUPS_FILENAME,
    config.PHASE5_FRAUD_DISCOVERY_CURVE_FILENAME,
    config.PHASE5_RUN_METADATA_FILENAME,
]


# --------------------------------------------------------------------------
# Synthetic world builders (schemas identical to the real repository state)
# --------------------------------------------------------------------------

def _make_run_scores(n: int, labels: np.ndarray, rng: np.random.RandomState) -> dict:
    """Correlated per-run anomaly scores with fraud bias, plus bottom-1%
    flags computed exactly like Phase 3 (native orientation, percentile rule)."""
    base_if = rng.normal(0.0, 1.0, size=n)
    base_lof = 0.5 * base_if + np.sqrt(1 - 0.25) * rng.normal(0.0, 1.0, size=n)
    run_data = {}
    for run_id in ALL_RUNS:
        base = base_if if run_id.startswith("IF_") else base_lof
        anomaly = base + rng.normal(0.0, 0.55, size=n)
        anomaly[labels == 1] += 2.6
        native = -anomaly
        threshold = np.percentile(native, config.THRESHOLD_PERCENTILE)
        flags = np.where(native <= threshold, 1, 0).astype(np.uint8)
        run_data[run_id] = (anomaly.astype(np.float64), flags)
    return run_data


def _make_eval_dataset(run_data: dict, row_ids, labels) -> pd.DataFrame:
    frames = []
    for run_id in ALL_RUNS:
        anomaly, flags = run_data[run_id]
        frames.append(
            pd.DataFrame(
                {
                    "run_id": run_id,
                    "row_id": np.asarray(row_ids),
                    "Class": np.asarray(labels),
                    "native_score": -np.asarray(anomaly, dtype=np.float64),
                    "anomaly_score": np.asarray(anomaly, dtype=np.float64),
                    "flag": flags,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def _metadata_payload(n: int, n_frauds: int) -> dict:
    return {
        "phase": "4",
        "stream": "A",
        "layer": "label_based_evaluation",
        "run_mode": "execute",
        "run_ids": list(ALL_RUNS),
        "sample": {
            "sample_size": int(n),
            "fraud_count": int(n_frauds),
            "fraud_prevalence": n_frauds / n,
        },
    }


def build_world(
    path: Path,
    n: int = WORLD_N,
    n_frauds: int = WORLD_FRAUDS,
    seed: int = 3,
    manifests: bool = True,
) -> dict:
    """Build a structurally exact Phase 4 + Phase 5A input world.

    The Phase 5A outputs are produced by the REAL frozen ``phase5_analysis``
    code executed on the synthetic Phase 4 dataset, so every cross-check in
    Phase 6 operates on genuine, internally consistent artifacts.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    rng = np.random.RandomState(seed)

    row_ids = 10_000 + np.arange(n)
    labels = np.zeros(n, dtype=np.int64)
    labels[rng.choice(n, size=n_frauds, replace=False)] = 1

    run_data = _make_run_scores(n, labels, rng)
    dataset = _make_eval_dataset(run_data, row_ids, labels)

    phase4_dir = path / "phase4"
    phase4_dir.mkdir(parents=True, exist_ok=True)
    ds_path = phase4_dir / config.PHASE4_EVALUATION_DATASET_FILENAME
    dataset.to_csv(ds_path, index=False)
    meta_path = phase4_dir / config.PHASE4_RUN_METADATA_FILENAME
    meta_path.write_text(json.dumps(_metadata_payload(n, n_frauds)), encoding="utf-8")
    if manifests:
        (phase4_dir / config.PHASE4_MANIFEST_FILENAME).write_text(
            json.dumps(
                build_manifest(
                    {
                        config.PHASE4_EVALUATION_DATASET_FILENAME: ds_path,
                        config.PHASE4_RUN_METADATA_FILENAME: meta_path,
                    }
                )
            ),
            encoding="utf-8",
        )

    phase5_dir = path / "phase5"
    p5a.run_phase5_analysis(
        evaluation_dataset_path=ds_path,
        phase4_run_metadata_path=meta_path,
        output_dir=phase5_dir,
        n_replicates=3,
        bootstrap_seed=7,
        verbose=False,
    )
    if not manifests:
        (phase5_dir / config.PHASE5_MANIFEST_FILENAME).unlink(missing_ok=True)

    return {
        "root": path,
        "phase5_dir": phase5_dir,
        "phase4_dataset": ds_path,
        "phase4_metadata": meta_path,
        "n": n,
        "n_frauds": int(labels.sum()),
        "row_ids": row_ids,
        "labels": labels,
        "run_data": run_data,
    }


def preflight(world: dict, output_dir=None, **kwargs):
    kwargs.setdefault("validate_references", False)
    return p6.collect_phase6_preflight(
        phase5_dir=world["phase5_dir"],
        phase4_dataset_path=world["phase4_dataset"],
        output_dir=output_dir,
        expected_sample_size=world["n"],
        verbose=False,
        **kwargs,
    )


def execute(world: dict, output_dir=None, **kwargs):
    kwargs.setdefault("validate_references", False)
    return p6.run_phase6(
        phase5_dir=world["phase5_dir"],
        phase4_dataset_path=world["phase4_dataset"],
        output_dir=output_dir,
        expected_sample_size=world["n"],
        verbose=False,
        **kwargs,
    )


def tree_state(root: Path) -> dict:
    """Path -> (size, sha256) for every file under root (snapshots)."""
    state = {}
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            state[str(p)] = (p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
    return state


def rebuild_phase5_manifest(phase5_dir: Path) -> None:
    """Rebuild the Phase 5A manifest over the (possibly tampered) tables, so
    tests can exercise the SEMANTIC cross-checks rather than hash rejection."""
    phase5_dir = Path(phase5_dir)
    (phase5_dir / config.PHASE5_MANIFEST_FILENAME).write_text(
        json.dumps(
            build_manifest({name: phase5_dir / name for name in PHASE5_ARTIFACT_NAMES})
        ),
        encoding="utf-8",
    )


def _run_frame(run_id, row_ids, labels, scores, flags):
    """A minimal run frame with the frozen Phase 4 schema."""
    return pd.DataFrame(
        {
            "run_id": run_id,
            "row_id": np.asarray(row_ids),
            "Class": np.asarray(labels),
            "native_score": -np.asarray(scores, dtype=np.float64),
            "anomaly_score": np.asarray(scores, dtype=np.float64),
            "flag": np.asarray(flags),
        }
    )


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    """The shared, manifest-verified synthetic world (never tampered with)."""
    return build_world(tmp_path_factory.mktemp("world"))


@pytest.fixture(scope="module")
def executed(world, tmp_path_factory):
    """One execute run over the shared world, reused by many assertions."""
    out_dir = tmp_path_factory.mktemp("phase6_out")
    result = execute(world, output_dir=out_dir)
    result["output_dir"] = out_dir
    return result


# --------------------------------------------------------------------------
# A. Observation-level group assignment (unit tests on hand-built frames)
# --------------------------------------------------------------------------

class TestGroupAssignment:
    def _tiny_frames(self):
        row_ids = [1, 2, 3, 4]
        labels = [0, 1, 0, 1]
        if_scores = [0.1, 0.2, 0.3, 0.4]
        lof_scores = [0.4, 0.3, 0.2, 0.1]
        if_flags = [1, 1, 0, 0]
        lof_flags = [1, 0, 1, 0]
        return (
            _run_frame("IF_003", row_ids, labels, if_scores, if_flags),
            _run_frame("LOF_004", row_ids, labels, lof_scores, lof_flags),
        )

    def test_all_four_flag_combinations_map_to_expected_groups(self):
        if_frame, lof_frame = self._tiny_frames()
        assignments = p6.assign_agreement_groups(if_frame, lof_frame)
        assert list(assignments["agreement_group"]) == ["Both", "IF-only", "LOF-only", "Neither"]
        assert list(assignments["if_flag"]) == [1, 1, 0, 0]
        assert list(assignments["lof_flag"]) == [1, 0, 1, 0]

    def test_partition_is_disjoint_and_exhaustive(self):
        rng = np.random.RandomState(5)
        n = 200
        row_ids = np.arange(1000, 1000 + n)
        labels = (rng.random(n) < 0.1).astype(int)
        if_flags = (rng.random(n) < 0.2).astype(int)
        lof_flags = (rng.random(n) < 0.2).astype(int)
        if_frame = _run_frame("IF_003", row_ids, labels, rng.normal(size=n), if_flags)
        lof_frame = _run_frame("LOF_004", row_ids, labels, rng.normal(size=n), lof_flags)
        assignments = p6.assign_agreement_groups(if_frame, lof_frame)

        assert len(assignments) == n
        assert assignments["row_id"].is_unique
        assert set(assignments["agreement_group"]) == set(p6.GROUP_LABELS.values())
        counts = assignments["agreement_group"].value_counts().to_dict()
        assert sum(counts.values()) == n
        # every observation exactly once, group consistent with its own flags
        for _, row in assignments.iterrows():
            expected = {
                (1, 1): "Both", (1, 0): "IF-only", (0, 1): "LOF-only", (0, 0): "Neither",
            }[(int(row["if_flag"]), int(row["lof_flag"]))]
            assert row["agreement_group"] == expected

    def test_duplicate_row_id_in_if_frame_is_rejected(self):
        if_frame, lof_frame = self._tiny_frames()
        broken = pd.concat([if_frame, if_frame.iloc[[0]]], ignore_index=True)
        with pytest.raises(p6.GroupAssignmentError, match="duplicate"):
            p6.assign_agreement_groups(broken, lof_frame)

    def test_duplicate_row_id_in_lof_frame_is_rejected(self):
        if_frame, lof_frame = self._tiny_frames()
        broken = pd.concat([lof_frame, lof_frame.iloc[[1]]], ignore_index=True)
        with pytest.raises(p6.GroupAssignmentError, match="duplicate"):
            p6.assign_agreement_groups(if_frame, broken)

    def test_missing_row_in_lof_frame_is_rejected(self):
        if_frame, lof_frame = self._tiny_frames()
        with pytest.raises(p6.GroupAssignmentError, match="row counts"):
            p6.assign_agreement_groups(if_frame, lof_frame.iloc[1:])

    def test_disjoint_row_id_sets_are_rejected(self):
        if_frame, lof_frame = self._tiny_frames()
        shifted = lof_frame.copy()
        shifted.loc[shifted.index[-1], "row_id"] = 999  # same length, one ID differs
        with pytest.raises(p6.GroupAssignmentError, match="do not match"):
            p6.assign_agreement_groups(if_frame, shifted)

    def test_incorrect_if_run_id_is_rejected(self):
        if_frame, lof_frame = self._tiny_frames()
        wrong = if_frame.copy()
        wrong["run_id"] = "IF_002"
        with pytest.raises(p6.GroupAssignmentError, match="IF_003"):
            p6.assign_agreement_groups(wrong, lof_frame)

    def test_incorrect_lof_run_id_is_rejected(self):
        if_frame, lof_frame = self._tiny_frames()
        wrong = lof_frame.copy()
        wrong["run_id"] = "LOF_003"
        with pytest.raises(p6.GroupAssignmentError, match="LOF_004"):
            p6.assign_agreement_groups(if_frame, wrong)

    def test_shuffled_lof_row_ordering_still_aligns_by_row_id(self):
        if_frame, lof_frame = self._tiny_frames()
        reference = p6.assign_agreement_groups(if_frame, lof_frame)
        shuffled = lof_frame.iloc[[3, 0, 2, 1]].reset_index(drop=True)
        shuffled_result = p6.assign_agreement_groups(if_frame, shuffled)
        # identical groups AND identical per-row LOF scores: the join is by
        # row_id, never positional
        assert list(shuffled_result["row_id"]) == list(reference["row_id"])
        assert list(shuffled_result["agreement_group"]) == list(reference["agreement_group"])
        assert np.allclose(shuffled_result["lof_anomaly_score"], reference["lof_anomaly_score"])

    def test_non_binary_flag_is_rejected(self):
        if_frame, lof_frame = self._tiny_frames()
        bad = lof_frame.copy()
        bad.loc[0, "flag"] = 2
        with pytest.raises(p6.GroupAssignmentError, match="binary"):
            p6.assign_agreement_groups(if_frame, bad)

    def test_non_binary_class_is_rejected(self):
        if_frame, lof_frame = self._tiny_frames()
        bad = lof_frame.copy()
        bad.loc[0, "Class"] = 7
        with pytest.raises(p6.GroupAssignmentError, match="binary"):
            p6.assign_agreement_groups(if_frame, bad)

    def test_class_mismatch_across_frames_is_rejected(self):
        if_frame, lof_frame = self._tiny_frames()
        bad = lof_frame.copy()
        bad.loc[0, "Class"] = 1 - int(bad.loc[0, "Class"])
        with pytest.raises(p6.GroupAssignmentError, match="label-alignment"):
            p6.assign_agreement_groups(if_frame, bad)

    def test_missing_score_values_are_rejected(self):
        if_frame, lof_frame = self._tiny_frames()
        bad = lof_frame.copy()
        bad.loc[0, "anomaly_score"] = np.nan
        with pytest.raises(p6.GroupAssignmentError, match="non-finite"):
            p6.assign_agreement_groups(if_frame, bad)

    def test_output_schema_column_order_and_dtypes(self):
        if_frame, lof_frame = self._tiny_frames()
        assignments = p6.assign_agreement_groups(if_frame, lof_frame)
        assert list(assignments.columns) == p6.GROUP_ASSIGNMENT_COLUMNS
        assert str(assignments["row_id"].dtype).startswith("int")
        assert str(assignments["if_flag"].dtype).startswith("int")
        assert assignments["if_anomaly_score"].dtype.kind == "f"
        assert set(assignments["if_run_id"]) == {"IF_003"}
        assert set(assignments["lof_run_id"]) == {"LOF_004"}

    def test_summary_counts_and_overlap_identities(self):
        rng = np.random.RandomState(9)
        n = 500
        row_ids = np.arange(n)
        labels = (rng.random(n) < 0.1).astype(int)
        if_flags = (rng.random(n) < 0.15).astype(int)
        lof_flags = (rng.random(n) < 0.25).astype(int)
        if_frame = _run_frame("IF_003", row_ids, labels, rng.normal(size=n), if_flags)
        lof_frame = _run_frame("LOF_004", row_ids, labels, rng.normal(size=n), lof_flags)
        summary = p6.summarize_group_assignments(
            p6.assign_agreement_groups(if_frame, lof_frame)
        )
        a, b = if_flags == 1, lof_flags == 1
        assert summary["observed_intersection"] == int((a & b).sum())
        assert summary["union_size"] == int((a | b).sum())
        assert summary["union_size"] == summary["if_flagged"] + summary["lof_flagged"] - summary["observed_intersection"]
        assert summary["if_flagged_frauds"] == int((a & (labels == 1)).sum())
        assert summary["lof_flagged_frauds"] == int((b & (labels == 1)).sum())
        assert summary["union_frauds"] == int(((a | b) & (labels == 1)).sum())


# --------------------------------------------------------------------------
# Input loading: cross-snapshot, tamper and conflict rejection
# --------------------------------------------------------------------------

class TestWorldLoading:
    def test_cross_snapshot_hash_mismatch_is_rejected(self, tmp_path):
        world = build_world(tmp_path, manifests=True)
        meta_path = world["phase5_dir"] / config.PHASE5_RUN_METADATA_FILENAME
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        payload["inputs"]["evaluation_dataset"]["sha256"] = "0" * 64
        meta_path.write_text(json.dumps(payload), encoding="utf-8")
        rebuild_phase5_manifest(world["phase5_dir"])
        with pytest.raises(p6.Phase6InputError, match="cross-snapshot"):
            preflight(world)

    def test_conflicting_group_counts_between_phase4_and_phase5a(self, tmp_path):
        world = build_world(tmp_path, manifests=True)
        groups_path = world["phase5_dir"] / config.PHASE5_AGREEMENT_GROUPS_FILENAME
        groups = pd.read_csv(groups_path)
        groups.loc[groups["group"] == "both", "observation_count"] += 1
        groups.loc[groups["group"] == "neither", "observation_count"] -= 1
        groups.to_csv(groups_path, index=False)
        rebuild_phase5_manifest(world["phase5_dir"])
        with pytest.raises(p6.Phase6InputError, match="agreement group 'both'"):
            preflight(world)

    def test_tampered_table_without_manifest_rebuild_is_rejected(self, tmp_path):
        world = build_world(tmp_path, manifests=True)
        groups_path = world["phase5_dir"] / config.PHASE5_AGREEMENT_GROUPS_FILENAME
        groups = pd.read_csv(groups_path)
        groups.loc[groups["group"] == "both", "fraud_count"] += 1
        groups.to_csv(groups_path, index=False)
        with pytest.raises(ManifestVerificationError):
            preflight(world)

    def test_tampered_jaccard_matrix_is_rejected(self, tmp_path):
        world = build_world(tmp_path, manifests=True)
        path = world["phase5_dir"] / config.PHASE5_PAIRWISE_JACCARD_FILENAME
        matrix = pd.read_csv(path, index_col=0)
        matrix.iloc[0, 1] = 5.0  # out of range AND asymmetric
        matrix.to_csv(path)
        rebuild_phase5_manifest(world["phase5_dir"])
        with pytest.raises(p6.Phase6InputError, match="jaccard"):
            preflight(world)

    def test_inconsistent_hypergeometric_summary_is_rejected(self, tmp_path):
        world = build_world(tmp_path, manifests=True)
        path = world["phase5_dir"] / config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME
        row = pd.read_csv(path)
        row.loc[0, "enrichment_observed_over_expected"] = 99.0
        row.to_csv(path, index=False)
        rebuild_phase5_manifest(world["phase5_dir"])
        with pytest.raises(p6.Phase6InputError, match="enrichment"):
            preflight(world)

    def test_wrong_sample_size_is_rejected(self, world):
        with pytest.raises(p6.Phase6InputError, match="exactly"):
            p6.collect_phase6_preflight(
                phase5_dir=world["phase5_dir"],
                phase4_dataset_path=world["phase4_dataset"],
                expected_sample_size=world["n"] + 1,
                validate_references=False,
                verbose=False,
            )

    def test_legacy_unmanifested_world_still_loads(self, tmp_path):
        world = build_world(tmp_path, manifests=False)
        report = preflight(world)
        assert report["input_manifests"]["phase5"]["mode"] == "legacy_unmanifested"
        assert report["input_manifests"]["phase4"]["mode"] == "legacy_unmanifested"
        assert report["sample"]["sample_size"] == world["n"]

# --------------------------------------------------------------------------
# B. Consistency scorecard
# --------------------------------------------------------------------------

class TestScorecard:
    def _value(self, executed_result, metric):
        sc = executed_result["scorecard"].set_index("metric")
        assert metric in sc.index, f"metric '{metric}' missing from the scorecard"
        row = sc.loc[metric]
        if row["value_type"] == "int":
            return int(row["value"])
        if row["value_type"] == "float":
            return float(row["value"])
        return str(row["value"])

    def test_scorecard_values_match_saved_phase5a_values(self, world, executed):
        tables = p6.load_phase6_tables(
            world["phase5_dir"], ALL_RUNS, world["n"], world["n_frauds"]
        )
        hyper = tables["hypergeometric"]
        assert self._value(executed, "sample_size") == world["n"]
        assert self._value(executed, "fraud_label_count") == world["n_frauds"]
        assert self._value(executed, "if003_flagged_count") == hyper["run_a_flagged"]
        assert self._value(executed, "lof004_flagged_count") == hyper["run_b_flagged"]
        assert self._value(executed, "observed_intersection") == hyper["observed_intersection"]
        assert self._value(executed, "union_size") == hyper["union_size"]
        assert math.isclose(
            self._value(executed, "spearman_if003_lof004"),
            float(tables["spearman"].loc["IF_003", "LOF_004"]),
            abs_tol=1e-6,
        )
        assert math.isclose(
            self._value(executed, "jaccard_if003_lof004"),
            float(tables["jaccard"].loc["IF_003", "LOF_004"]),
            abs_tol=1e-6,
        )
        assert math.isclose(
            self._value(executed, "log10_upper_tail_probability"),
            float(hyper["log10_survival"]),
            abs_tol=1e-6,
        )
        groups = tables["agreement_groups"].set_index("group")
        for key in p6.GROUP_KEYS:
            assert self._value(executed, f"{key}_observation_count") == int(
                groups.loc[key, "observation_count"]
            )
            assert self._value(executed, f"{key}_fraud_count") == int(
                groups.loc[key, "fraud_count"]
            )

    def test_every_row_records_source_artifact_and_field(self, executed):
        sc = executed["scorecard"]
        assert (sc["source_artifact"].str.len() > 0).all()
        assert (sc["source_field"].str.len() > 0).all()
        known_sources = {
            config.PHASE4_EVALUATION_DATASET_FILENAME,
            config.PHASE5_PAIRWISE_SPEARMAN_FILENAME,
            config.PHASE5_PAIRWISE_JACCARD_FILENAME,
            config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME,
            config.PHASE5_AGREEMENT_GROUPS_FILENAME,
            config.PHASE5_MULTITHRESHOLD_AGREEMENT_FILENAME,
            config.PHASE5_BOOTSTRAP_METRICS_FILENAME,
            config.PHASE5_PAIRED_BOOTSTRAP_DIFFERENCES_FILENAME,
        }
        assert set(sc["source_artifact"].unique()) <= known_sources

    def test_expected_sections_present(self, executed):
        sections = set(executed["scorecard"]["section"])
        assert sections == {
            "experiment", "rank_agreement", "flag_overlap", "hypergeometric_null",
            "agreement_groups", "review_workload", "family_consistency",
            "threshold_sensitivity", "bootstrap_context", "row_level_checks",
        }

    def test_value_types_and_formatting_are_deterministic(self, executed):
        sc = executed["scorecard"]
        assert set(sc["value_type"]) <= {"int", "float", "string"}
        floats = sc[sc["value_type"] == "float"]["value"]
        assert floats.str.fullmatch(r"-?\d+\.\d{6}").all()
        ints = sc[sc["value_type"] == "int"]["value"]
        assert ints.str.fullmatch(r"\d+").all()
        assert not sc.duplicated(subset=["metric"]).any()

    def test_reference_metric_names_exist_as_scorecard_rows(self, executed):
        metrics = set(executed["scorecard"]["metric"])
        for name in p6.PHASE6_REFERENCE_VALUES:
            assert name in metrics, f"reference-checked metric '{name}' not in the scorecard"

    def test_row_level_check_rows_all_match_saved_values(self, world, executed):
        sc = executed["scorecard"]
        checks = sc[sc["section"] == "row_level_checks"]
        assert len(checks) >= 20
        assert checks["note"].str.contains("matches").all()
        # the recomputed flagged counts equal the raw world flags
        if_flags = world["run_data"]["IF_003"][1]
        lof_flags = world["run_data"]["LOF_004"][1]
        assert self._value(executed, "recompute_if003_flagged_count") == int(if_flags.sum())
        assert self._value(executed, "recompute_lof004_flagged_count") == int(lof_flags.sum())


# --------------------------------------------------------------------------
# Overlap / workload arithmetic and Jaccard interpretation
# --------------------------------------------------------------------------

class TestWorkloadAndOverlap:
    def test_union_and_intersection_match_raw_world_flags(self, world, executed):
        a = world["run_data"]["IF_003"][1] == 1
        b = world["run_data"]["LOF_004"][1] == 1
        context = executed["context"]
        assert context["observed_intersection"] == int((a & b).sum())
        assert context["union_size"] == int((a | b).sum())

    def test_workload_rows_for_all_four_policies(self, world, executed):
        context = executed["context"]
        w = context["workload"]
        g = context["groups"]
        total_frauds = context["fraud_label_count"]

        both_count = g["both"]["observation_count"]
        if_k = context["if003_flagged_count"]
        lof_k = context["lof004_flagged_count"]
        union = context["union_size"]

        assert w["both_only"]["reviews"] == both_count
        assert w["if003_flags"]["reviews"] == if_k
        assert w["lof004_flags"]["reviews"] == lof_k
        assert w["union"]["reviews"] == union == if_k + lof_k - context["observed_intersection"]
        for policy, reviews in (
            ("both_only", both_count), ("if003_flags", if_k),
            ("lof004_flags", lof_k), ("union", union),
        ):
            assert w[policy]["sample_share"] == reviews / world["n"]
            assert w[policy]["precision"] == w[policy]["frauds"] / reviews
            assert w[policy]["recall"] == w[policy]["frauds"] / total_frauds
        # fraud accounting across the policies
        assert w["if003_flags"]["frauds"] == g["both"]["fraud_count"] + g["if_only"]["fraud_count"]
        assert w["lof004_flags"]["frauds"] == g["both"]["fraud_count"] + g["lof_only"]["fraud_count"]
        assert w["union"]["frauds"] == w["lof004_flags"]["frauds"] + w["if003_flags"]["frauds"] - g["both"]["fraud_count"]
        assert w["both_only"]["frauds"] + context["neither_fraud_count"] + (
            w["if003_flags"]["frauds"] - w["both_only"]["frauds"]
        ) + (w["lof004_flags"]["frauds"] - w["both_only"]["frauds"]) == total_frauds

    def test_jaccard_is_distinct_from_per_detector_overlap_fractions(self, executed):
        context = executed["context"]
        intersection = context["observed_intersection"]
        union = context["union_size"]
        assert math.isclose(
            context["jaccard_if003_lof004"], intersection / union, abs_tol=1e-12
        )
        assert math.isclose(
            context["if003_flagged_share_overlapping"],
            intersection / context["if003_flagged_count"],
            abs_tol=1e-12,
        )
        assert math.isclose(
            context["lof004_flagged_share_overlapping"],
            intersection / context["lof004_flagged_count"],
            abs_tol=1e-12,
        )
        # Jaccard (over the union) and the per-detector overlap fractions
        # (over each flagged set) are distinct constructs; they can coincide
        # only when the union equals the flagged set (one set nested in the
        # other with no unique observations on the other side).
        if union != context["if003_flagged_count"]:
            assert (
                context["jaccard_if003_lof004"]
                != context["if003_flagged_share_overlapping"]
            )


# --------------------------------------------------------------------------
# C. Five-question report
# --------------------------------------------------------------------------

class TestReport:
    def test_report_contains_the_five_questions(self, executed):
        report = executed["report_markdown"]
        for needle in (
            "Q1 -- Are the anomaly rankings similar?",
            "Q2 -- How much do the flagged observations overlap?",
            "Q3 -- Is the overlap greater than expected under the specified random-selection null?",
            "Q4 -- How are known fraud labels distributed across agreement groups?",
            "Q5 -- Is disagreement sensitive to neighbourhood size, detector configuration or review threshold?",
        ):
            assert needle in report

    def test_report_numbers_match_source_values(self, world, executed):
        report = executed["report_markdown"]
        context = executed["context"]
        assert f"**{context['spearman_if003_lof004']:.4f}**" in report
        assert f"**{context['jaccard_if003_lof004']:.4f}**" in report
        assert f"{context['observed_intersection']:,}" in report
        assert f"{context['union_size']:,}" in report
        for key in p6.GROUP_KEYS:
            assert f"{context['groups'][key]['observation_count']:,}" in report
        assert f"{context['fraud_label_count']:,}" in report
        assert f"{world['n']:,}" in report

    def test_report_distinguishes_jaccard_from_detector_overlap(self, executed):
        report = executed["report_markdown"]
        context = executed["context"]
        assert "relative to the union" in report
        assert "relative to each detector's own flagged set" in report
        assert f"({100 * context['if003_flagged_share_overlapping']:.2f}%)" in report
        assert f"({100 * context['jaccard_if003_lof004']:.2f}%)" in report

    def test_report_states_null_and_required_caveats(self, executed):
        report = executed["report_markdown"]
        assert "independent uniform random selection" in report
        assert "true anomalies" in report
        assert "operational validity" in report
        assert "do not establish a universally optimal audit policy" in report
        assert "does not imply identical anomaly rankings" in report
        assert "controlled single-factor experiments" in report
        assert "none are invented here" in report
        assert "exploratory" in report

    def test_report_contains_interpretation_principles(self, executed):
        report = executed["report_markdown"]
        for principle in p6.INTERPRETATION_PRINCIPLES:
            assert principle in report

    def test_report_is_deterministic_across_runs(self, world, tmp_path):
        first = execute(world, output_dir=tmp_path / "a")
        second = execute(world, output_dir=tmp_path / "b")
        assert first["report_markdown"] == second["report_markdown"]
        assert first["scorecard"].equals(second["scorecard"])
        a = (tmp_path / "a" / config.PHASE6_CONSISTENCY_REPORT_FILENAME).read_bytes()
        b = (tmp_path / "b" / config.PHASE6_CONSISTENCY_REPORT_FILENAME).read_bytes()
        assert a == b

    def test_report_contains_no_timestamps_or_paths(self, world, executed):
        report = executed["report_markdown"]
        assert "created_utc" not in report
        assert str(world["root"]) not in report
        assert str(Path("/tmp")) not in report
        assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", report)

    def test_report_review_policy_table_has_the_four_policies(self, executed):
        report = executed["report_markdown"]
        for label in (
            "Both-only (agreement gate)",
            "IF_003's flagged set",
            "LOF_004's flagged set",
            "Union of both flagged sets",
        ):
            assert label in report


# --------------------------------------------------------------------------
# Reference validation (historical acceptance references)
# --------------------------------------------------------------------------

class TestReferenceValidation:
    def test_context_matching_all_references_passes(self):
        context = {k: v for k, v in p6.PHASE6_REFERENCE_VALUES.items()}
        assert p6.validate_against_references(context) == []

    def test_mismatch_is_reported_with_metric_and_values(self):
        context = {k: v for k, v in p6.PHASE6_REFERENCE_VALUES.items()}
        context["observed_intersection"] = 108
        problems = p6.validate_against_references(context)
        assert len(problems) == 1
        assert "observed_intersection" in problems[0]
        assert "108" in problems[0]

    def test_rounded_float_references_compare_within_tolerance(self):
        context = {k: v for k, v in p6.PHASE6_REFERENCE_VALUES.items()}
        context["spearman_if003_lof004"] = 0.36655  # within 1e-4 of 0.3666
        context["enrichment_observed_over_expected"] = 35.667  # within 5e-3 of 35.67
        assert p6.validate_against_references(context) == []

    def test_out_of_tolerance_values_fail(self):
        context = {k: v for k, v in p6.PHASE6_REFERENCE_VALUES.items()}
        context["spearman_if003_lof004"] = 0.3600
        problems = p6.validate_against_references(context)
        assert any("spearman_if003_lof004" in p for p in problems)

    def test_missing_or_non_numeric_values_fail(self):
        context = {k: v for k, v in p6.PHASE6_REFERENCE_VALUES.items()}
        del context["union_size"]
        context["jaccard_if003_lof004"] = "not-a-number"
        problems = p6.validate_against_references(context)
        assert any("union_size" in p for p in problems)
        assert any("jaccard_if003_lof004" in p for p in problems)

    def test_execute_fails_on_synthetic_world_when_references_active(self, world, tmp_path):
        out_dir = tmp_path / "out"
        with pytest.raises(p6.ReferenceValidationError, match="sample_size"):
            execute(world, output_dir=out_dir, validate_references=True)
        assert not out_dir.exists()  # nothing was written, nothing forced

    def test_preflight_also_fails_when_references_active(self, world):
        with pytest.raises(p6.ReferenceValidationError, match="reference validation FAILED"):
            preflight(world, validate_references=True)


# --------------------------------------------------------------------------
# No model fitting, no input mutation
# --------------------------------------------------------------------------

class TestNoFittingNoModification:
    def test_no_detector_is_fitted_or_refitted(self, tmp_path):
        from sklearn.ensemble import IsolationForest
        from sklearn.neighbors import LocalOutlierFactor

        world = build_world(tmp_path, manifests=False)
        with mock_patch_object(IsolationForest, "fit", side_effect=AssertionError("must not fit")), \
             mock_patch_object(IsolationForest, "fit_predict", side_effect=AssertionError("must not fit")), \
             mock_patch_object(LocalOutlierFactor, "fit", side_effect=AssertionError("must not fit")), \
             mock_patch_object(LocalOutlierFactor, "fit_predict", side_effect=AssertionError("must not fit")), \
             mock_patch_object(phase3, "run_isolation_forest", side_effect=AssertionError("must not fit")), \
             mock_patch_object(phase3, "run_lof", side_effect=AssertionError("must not fit")):
            result = execute(world, output_dir=tmp_path / "out")
        assert len(result["scorecard"]) > 100

    def test_module_is_free_of_detector_machinery(self):
        assert not hasattr(p6, "IsolationForest")
        assert not hasattr(p6, "LocalOutlierFactor")
        source = Path(p6.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "import sklearn", "from sklearn", "import scipy", "from scipy",
            "IsolationForest", "LocalOutlierFactor", "hypergeom(", "spearmanr(",
        ):
            assert forbidden not in source, f"forbidden pattern in phase6.py: {forbidden}"

    def test_inputs_unmodified_by_execute(self, tmp_path):
        world = build_world(tmp_path / "world", manifests=True)
        before = tree_state(world["root"])
        execute(world, output_dir=tmp_path / "out")
        assert tree_state(world["root"]) == before

    def test_execute_writes_only_into_output_dir(self, tmp_path):
        world = build_world(tmp_path / "world", manifests=False)
        before = set(tree_state(world["root"]))
        execute(world, output_dir=tmp_path / "out")
        after = set(tree_state(world["root"]))
        assert after - before == set()


# --------------------------------------------------------------------------
# Preflight no-writes, output protection, staged publication rollback
# --------------------------------------------------------------------------

class TestSafetyAndPublication:
    def test_preflight_writes_nothing(self, world, tmp_path):
        out_dir = tmp_path / "phase6"
        before = tree_state(world["root"])
        report = preflight(world, output_dir=out_dir)
        assert not out_dir.exists()
        assert report["writes_performed"] is False
        assert tree_state(world["root"]) == before

    def test_preflight_reports_blocked_when_outputs_exist(self, world, tmp_path):
        out_dir = tmp_path / "phase6"
        execute(world, output_dir=out_dir)
        report = preflight(world, output_dir=out_dir)
        assert report["outputs"]["blocked"] is True

    def test_second_execute_is_blocked(self, world, tmp_path):
        out_dir = tmp_path / "phase6"
        execute(world, output_dir=out_dir)
        with pytest.raises(FileExistsError):
            execute(world, output_dir=out_dir)
        # the original outputs are untouched
        assert (out_dir / config.PHASE6_CONSISTENCY_REPORT_FILENAME).is_file()

    def test_overwrite_replaces_outputs(self, world, tmp_path):
        out_dir = tmp_path / "phase6"
        execute(world, output_dir=out_dir)
        marker_before = (out_dir / config.PHASE6_CONSISTENCY_REPORT_FILENAME).read_bytes()
        result = execute(world, output_dir=out_dir, overwrite=True)
        assert result["publication"]["backed_up"] == sorted(
            [
                config.PHASE6_GROUP_ASSIGNMENTS_FILENAME,
                config.PHASE6_CONSISTENCY_REPORT_FILENAME,
                config.PHASE6_CONSISTENCY_SCORECARD_FILENAME,
                config.PHASE6_MANIFEST_FILENAME,
                config.PHASE6_RUN_METADATA_FILENAME,
            ]
        )
        assert (out_dir / config.PHASE6_CONSISTENCY_REPORT_FILENAME).read_bytes() == marker_before
        # no leftover backup directories
        assert [d.name for d in tmp_path.iterdir() if d.name.startswith(".")] == []

    def test_staging_failure_publishes_nothing(self, world, tmp_path):
        from unittest import mock

        out_dir = tmp_path / "phase6"
        with mock.patch.object(
            p6, "_verify_staged_artifacts", side_effect=RuntimeError("staging boom")
        ):
            with pytest.raises(RuntimeError, match="staging boom"):
                execute(world, output_dir=out_dir)
        # the output directory exists but is empty; no staging leftovers
        assert list(out_dir.glob("*")) == []
        assert [d.name for d in tmp_path.iterdir() if "staging" in d.name] == []

    def test_publication_failure_restores_originals(self, world, tmp_path):
        from unittest import mock

        out_dir = tmp_path / "phase6"
        execute(world, output_dir=out_dir)
        original_state = tree_state(out_dir)
        with mock.patch.object(
            p6, "save_manifest", side_effect=RuntimeError("manifest boom")
        ):
            with pytest.raises(RuntimeError, match="manifest boom"):
                execute(world, output_dir=out_dir, overwrite=True)
        # every original file restored byte-identical, nothing extra left
        assert tree_state(out_dir) == original_state
        assert [d.name for d in tmp_path.iterdir() if "backup" in d.name] == []


# --------------------------------------------------------------------------
# Manifest and run metadata
# --------------------------------------------------------------------------

class TestManifestAndMetadata:
    def test_manifest_covers_all_artifacts_and_verifies(self, executed):
        out_dir = executed["output_dir"]
        manifest = load_manifest(out_dir / config.PHASE6_MANIFEST_FILENAME)
        report = verify_manifest(
            manifest,
            base_dir=out_dir,
            required_artifacts=(
                config.PHASE6_GROUP_ASSIGNMENTS_FILENAME,
                config.PHASE6_CONSISTENCY_SCORECARD_FILENAME,
                config.PHASE6_CONSISTENCY_REPORT_FILENAME,
                config.PHASE6_RUN_METADATA_FILENAME,
            ),
        )
        assert len(report) == 4

    def test_manifest_does_not_list_itself(self, executed):
        manifest = load_manifest(executed["output_dir"] / config.PHASE6_MANIFEST_FILENAME)
        assert config.PHASE6_MANIFEST_FILENAME not in manifest["artifacts"]

    def test_run_metadata_records_provenance_and_guards(self, world, executed):
        out_dir = executed["output_dir"]
        metadata = json.loads(
            (out_dir / config.PHASE6_RUN_METADATA_FILENAME).read_text(encoding="utf-8")
        )
        assert metadata["phase"] == "6"
        assert metadata["model_fitting"]["models_fitted"] == 0
        assert len(metadata["inputs"]) == 9
        for info in metadata["inputs"].values():
            assert len(info["sha256"]) == 64
        assert metadata["reference_validation"]["enabled"] is False
        assert metadata["non_canonical_overrides"] == {
            "expected_sample_size": world["n"],
            "validate_references": False,
        }
        assert metadata["input_manifests"]["phase5"]["mode"] == "manifest_verified"
        assert metadata["comparison_pair"]["if_run_id"] == "IF_003"
        assert metadata["comparison_pair"]["lof_run_id"] == "LOF_004"
        assert metadata["selection_caveat"] == p6.EXPLORATORY_CAVEAT

    def test_group_assignments_match_phase5a_group_table(self, world, executed):
        out_dir = executed["output_dir"]
        assignments = pd.read_csv(out_dir / config.PHASE6_GROUP_ASSIGNMENTS_FILENAME)
        tables = p6.load_phase6_tables(
            world["phase5_dir"], ALL_RUNS, world["n"], world["n_frauds"]
        )
        groups = tables["agreement_groups"].set_index("group")
        counts = assignments["agreement_group"].value_counts().to_dict()
        for key in p6.GROUP_KEYS:
            assert counts[p6.GROUP_LABELS[key]] == int(groups.loc[key, "observation_count"])
            frauds = int(assignments.loc[
                assignments["agreement_group"] == p6.GROUP_LABELS[key], "Class"
            ].sum())
            assert frauds == int(groups.loc[key, "fraud_count"])


# --------------------------------------------------------------------------
# End-to-end (library level)
# --------------------------------------------------------------------------

class TestEndToEnd:
    def test_execute_produces_the_five_outputs(self, executed):
        out_dir = executed["output_dir"]
        for name in (
            config.PHASE6_GROUP_ASSIGNMENTS_FILENAME,
            config.PHASE6_CONSISTENCY_SCORECARD_FILENAME,
            config.PHASE6_CONSISTENCY_REPORT_FILENAME,
            config.PHASE6_RUN_METADATA_FILENAME,
            config.PHASE6_MANIFEST_FILENAME,
        ):
            path = out_dir / name
            assert path.is_file() and path.stat().st_size > 0

    def test_group_assignments_rows_and_schema(self, world, executed):
        out_dir = executed["output_dir"]
        assignments = pd.read_csv(out_dir / config.PHASE6_GROUP_ASSIGNMENTS_FILENAME)
        assert list(assignments.columns) == p6.GROUP_ASSIGNMENT_COLUMNS
        assert len(assignments) == world["n"]
        assert assignments["row_id"].is_unique
        assert set(assignments["row_id"]) == set(world["row_ids"])
        assert set(assignments["agreement_group"]) <= set(p6.GROUP_LABELS.values())
        assert set(assignments["if_run_id"]) == {"IF_003"}
        assert set(assignments["lof_run_id"]) == {"LOF_004"}
        assert set(assignments["if_flag"]) <= {0, 1}
        assert set(assignments["lof_flag"]) <= {0, 1}

    def test_scorecard_file_round_trips(self, executed):
        out_dir = executed["output_dir"]
        on_disk = pd.read_csv(out_dir / config.PHASE6_CONSISTENCY_SCORECARD_FILENAME)
        assert list(on_disk.columns) == p6.SCORECARD_COLUMNS
        assert len(on_disk) == len(executed["scorecard"])


# --------------------------------------------------------------------------
# CLI behaviour (subprocess, exactly as a user invokes it)
# --------------------------------------------------------------------------

class TestCommandLineInterface:
    def _run(self, world, out_dir, *extra):
        return subprocess.run(
            [
                sys.executable, str(RUNNER),
                "--phase5-dir", str(world["phase5_dir"]),
                "--evaluation-dataset", str(world["phase4_dataset"]),
                "--output-dir", str(out_dir),
                "--expected-sample-size", str(world["n"]),
                *extra,
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )

    def test_default_is_preflight_and_writes_nothing(self, world, tmp_path):
        out_dir = tmp_path / "phase6"
        result = self._run(world, out_dir, "--skip-reference-validation")
        assert result.returncode == 0, result.stderr
        assert "PREFLIGHT" in result.stdout
        assert "row-level checks" in result.stdout
        assert not out_dir.exists()

    def test_execute_produces_outputs(self, world, tmp_path):
        out_dir = tmp_path / "phase6"
        result = self._run(world, out_dir, "--execute", "--skip-reference-validation")
        assert result.returncode == 0, result.stderr
        for name in (
            config.PHASE6_GROUP_ASSIGNMENTS_FILENAME,
            config.PHASE6_CONSISTENCY_SCORECARD_FILENAME,
            config.PHASE6_CONSISTENCY_REPORT_FILENAME,
            config.PHASE6_RUN_METADATA_FILENAME,
            config.PHASE6_MANIFEST_FILENAME,
        ):
            assert (out_dir / name).is_file()

    def test_second_execute_is_blocked(self, world, tmp_path):
        out_dir = tmp_path / "phase6"
        assert self._run(world, out_dir, "--execute", "--skip-reference-validation").returncode == 0
        blocked = self._run(world, out_dir, "--execute", "--skip-reference-validation")
        assert blocked.returncode == 1
        assert "overwrite" in blocked.stderr.lower()

    def test_reference_guard_fails_without_skip_flag(self, world, tmp_path):
        out_dir = tmp_path / "phase6"
        result = self._run(world, out_dir, "--execute")
        assert result.returncode == 1
        assert "reference" in result.stderr.lower()
        assert not out_dir.exists()

    def test_overwrite_flag_replaces_outputs(self, world, tmp_path):
        out_dir = tmp_path / "phase6"
        assert self._run(world, out_dir, "--execute", "--skip-reference-validation").returncode == 0
        replaced = self._run(
            world, out_dir, "--execute", "--skip-reference-validation", "--overwrite"
        )
        assert replaced.returncode == 0, replaced.stderr
        assert len(list(out_dir.glob("phase6_*"))) == 5


def mock_patch_object(target, attribute, side_effect):
    from unittest import mock

    return mock.patch.object(target, attribute, side_effect=side_effect)

# ==========================================================================
# Hardening Regression Tests (Manifest Rollback & Malformed Metadata)
# ==========================================================================
class TestPhase6HardeningRepairs:
    def test_publication_rollback_on_manifest_failure(self, tmp_path):
        import shutil
        from unittest import mock
        from mplad.stream_a import phase6
        from mplad.common.io import save_json

        out_dir = tmp_path / "results"
        out_dir.mkdir()
        
        # Create dummy pre-existing files
        dummy_csv = out_dir / "assignments.csv"
        dummy_csv.write_text("old_assignments", encoding="utf-8")
        
        stage_dir = tmp_path / "staging"
        stage_dir.mkdir()
        stage_csv = stage_dir / "assignments.csv"
        stage_csv.write_text("new_assignments", encoding="utf-8")
        
        orig_save = save_json
        def fake_save_json(payload, path, overwrite=False):
            if "manifest" in str(path):
                # Write partial file then crash
                with open(path, "w", encoding="utf-8") as f:
                    f.write('{"partial": ')
                raise OSError("Simulated manifest write failure")
            orig_save(payload, path, overwrite)
            
        with mock.patch("mplad.common.manifest.save_json", side_effect=fake_save_json):
            # Bypass staging verification for the dummy files
            with mock.patch("mplad.stream_a.phase6._verify_staged_artifacts"):
                with pytest.raises(OSError, match="Simulated manifest write failure"):
                    phase6._publish_with_rollback(
                        stage_dir, out_dir, ["assignments.csv"], "manifest.json", overwrite=True, verbose=False
                    )
                    
        # Verify rollback succeeded
        assert dummy_csv.read_text(encoding="utf-8") == "old_assignments", "Backup was not restored"
        assert not (out_dir / "manifest.json").exists(), "Partial manifest was not deleted"
        
    def test_validate_metadata_handles_missing_sample_size_without_type_error(self):
        from mplad.stream_a import phase6
        payload = {"phase": "5A", "run_ids": ["IF_001"], "sample": {}, "analytical_conventions": {"tie_breaking": phase6.phase5_analysis.TIE_BREAK_POLICY}, "inputs": {"evaluation_dataset": {"sha256": "A" * 64}}}
        with pytest.raises(phase6.Phase6InputError, match="sample_size None != the expected 1,000"):
            phase6.validate_phase5_metadata(payload, ["IF_001"], 1000, 10)
