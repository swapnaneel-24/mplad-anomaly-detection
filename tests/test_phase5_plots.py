"""Lightweight software-structure tests for the Phase 5B visualization layer.

These tests run on SYNTHETIC fixtures: a structurally exact small-scale
replica of the verified repository state (a ten-run Phase 4 evaluation
dataset with saved bottom-1% flags, a genuine Phase 5A output set produced
by the frozen ``phase5_analysis`` code on that dataset, and an FS-A feature
matrix whose ``row_id`` population covers the sample). They validate the
software contract -- input/schema/manifest validation, cross-snapshot hash
consistency, score orientation, random baselines, hypergeometric support
and tail annotation, matrix rendering, top-k derivation and tie handling,
the 0.99 percentile boundaries, four-group membership, PCA row alignment
and Neither-only sampling, explained-variance reporting, no-fitting, input
immutability, preflight no-writes, output protection and staged-publication
rollback -- and never touch the real repository artifacts.

A non-interactive Matplotlib backend (Agg) is selected BEFORE the plotting
layer is imported, as the Phase 5B specification requires.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # non-interactive backend, required by the specification

import numpy as np
import pandas as pd
import pytest
from sklearn.decomposition import PCA as SklearnPCA
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score
from sklearn.neighbors import LocalOutlierFactor

from mplad.common import config
from mplad.common.manifest import (
    ManifestVerificationError,
    load_manifest,
    verify_manifest,
)
from mplad.stream_a import phase3
from mplad.stream_a import phase5_analysis as p5a
from mplad.stream_a import phase5_plots as p5b

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "run_phase5_plots.py"

ALL_RUNS = list(config.PHASE3_CANONICAL_RUN_IDS)
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

#: World geometry: n >= 600 so that every budget in the frozen grid
#: (0.1% of the sample) yields k = round(n * pct / 100) >= 1.
WORLD_N = 600
WORLD_FRAUDS = 15
WORLD_FS_ROWS = 900


# --------------------------------------------------------------------------
# Synthetic world builders (schemas identical to the real repository state)
# --------------------------------------------------------------------------

def _make_fs_matrix(fs_rows: int, rng: np.random.RandomState) -> pd.DataFrame:
    """A synthetic FS-A feature matrix: Time, V1..V28, Amount + row_id."""
    data = {"Time": rng.uniform(-1.5, 1.5, size=fs_rows)}
    for i in range(1, 29):
        data[f"V{i}"] = rng.normal(0.0, 1.0, size=fs_rows)
    data["Amount"] = rng.uniform(-1.0, 2.0, size=fs_rows)
    data[config.ID_COLUMN] = 10_000 + np.arange(fs_rows)
    return pd.DataFrame(data)


def _make_run_scores(
    n: int, n_frauds: int, labels: np.ndarray, rng: np.random.RandomState
) -> dict:
    """Correlated per-run anomaly scores with fraud bias, plus bottom-1%
    flags computed exactly like Phase 3 (native orientation, percentile rule)."""
    base_if = rng.normal(0.0, 1.0, size=n)
    base_lof = 0.5 * base_if + np.sqrt(1 - 0.25) * rng.normal(0.0, 1.0, size=n)
    run_data = {}
    for i, run_id in enumerate(ALL_RUNS):
        base = base_if if run_id.startswith("IF_") else base_lof
        anomaly = base + rng.normal(0.0, 0.55, size=n)
        anomaly[labels == 1] += 2.6  # frauds score high on anomaly_score
        native = -anomaly  # Phase 3 storage orientation (lower = anomalous)
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
    fs_rows: int = WORLD_FS_ROWS,
    manifests: bool = True,
    shuffle_fs: bool = False,
) -> dict:
    """Build a structurally exact Phase 4 + Phase 5A + FS-A input world.

    The Phase 5A outputs are produced by the REAL frozen ``phase5_analysis``
    code executed on the synthetic Phase 4 dataset, so every cross-check in
    Phase 5B operates on genuine, internally consistent artifacts.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    rng = np.random.RandomState(seed)

    fs_df = _make_fs_matrix(fs_rows, rng)
    if shuffle_fs:
        fs_df = fs_df.iloc[rng.permutation(len(fs_df))].reset_index(drop=True)
    fs_path = path / "ULB_FS_A_Baseline.csv"
    fs_df.to_csv(fs_path, index=False)

    # Sample n row_ids from the FS population (draw order preserved).
    sample_positions = np.sort(rng.choice(fs_rows, size=n, replace=False))
    row_ids = fs_df[config.ID_COLUMN].to_numpy()[sample_positions]

    labels = np.zeros(n, dtype=np.int64)
    labels[rng.choice(n, size=n_frauds, replace=False)] = 1

    run_data = _make_run_scores(n, n_frauds, labels, rng)
    dataset = _make_eval_dataset(run_data, row_ids, labels)

    phase4_dir = path / "phase4"
    phase4_dir.mkdir(parents=True, exist_ok=True)
    ds_path = phase4_dir / config.PHASE4_EVALUATION_DATASET_FILENAME
    dataset.to_csv(ds_path, index=False)
    meta_path = phase4_dir / config.PHASE4_RUN_METADATA_FILENAME
    meta_path.write_text(json.dumps(_metadata_payload(n, n_frauds)), encoding="utf-8")
    if manifests:
        from mplad.common.manifest import build_manifest

        manifest = build_manifest(
            {
                config.PHASE4_EVALUATION_DATASET_FILENAME: ds_path,
                config.PHASE4_RUN_METADATA_FILENAME: meta_path,
            }
        )
        (phase4_dir / config.PHASE5_PLOTS_PHASE4_MANIFEST_FILENAME).write_text(
            json.dumps(manifest), encoding="utf-8"
        )

    # Genuine Phase 5A outputs from the frozen analysis layer.
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
        "fs_a": fs_path,
        "n": n,
        "n_frauds": int(labels.sum()),
        "row_ids": row_ids,
        "labels": labels,
    }


def preflight(world: dict, output_dir=None, **kwargs):
    return p5b.collect_phase5_plots_preflight(
        phase5_dir=world["phase5_dir"],
        phase4_dataset_path=world["phase4_dataset"],
        fs_a_path=world["fs_a"],
        output_dir=output_dir,
        expected_sample_size=world["n"],
        verbose=False,
        **kwargs,
    )


def execute(world: dict, output_dir=None, **kwargs):
    return p5b.run_phase5_plots(
        phase5_dir=world["phase5_dir"],
        phase4_dataset_path=world["phase4_dataset"],
        fs_a_path=world["fs_a"],
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


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    """The shared, manifest-verified synthetic world (never tampered with)."""
    return build_world(tmp_path_factory.mktemp("world"))


@pytest.fixture(scope="module")
def aligned(world):
    dataset = p5a.load_phase4_dataset(world["phase4_dataset"])
    return p5a.extract_aligned_runs(dataset, ALL_RUNS)


@pytest.fixture(scope="module")
def tables(world, aligned):
    return p5b.load_phase5_tables(
        world["phase5_dir"], ALL_RUNS, aligned["sample_size"], aligned["fraud_count"]
    )


# --------------------------------------------------------------------------
# Input file / schema / manifest validation
# --------------------------------------------------------------------------

class TestInputValidation:
    def test_missing_phase5_table_raises(self, tmp_path):
        world = build_world(tmp_path, manifests=False)
        (world["phase5_dir"] / config.PHASE5_PAIRWISE_SPEARMAN_FILENAME).unlink()
        with pytest.raises(FileNotFoundError, match="Spearman matrix"):
            preflight(world)

    def test_missing_phase4_dataset_raises(self, tmp_path):
        world = build_world(tmp_path, manifests=False)
        world["phase4_dataset"].unlink()
        with pytest.raises(FileNotFoundError, match="evaluation dataset"):
            preflight(world)

    def test_missing_fs_matrix_raises(self, tmp_path):
        world = build_world(tmp_path, manifests=False)
        world["fs_a"].unlink()
        with pytest.raises(FileNotFoundError, match="FS-A"):
            preflight(world)

    def test_missing_phase5_metadata_raises(self, tmp_path):
        world = build_world(tmp_path, manifests=False)
        (world["phase5_dir"] / config.PHASE5_RUN_METADATA_FILENAME).unlink()
        with pytest.raises(FileNotFoundError, match="Phase 5A run metadata"):
            preflight(world)

    def test_manifest_verified_paths(self, world):
        report = preflight(world)
        assert report["input_manifests"]["phase5"]["mode"] == "manifest_verified"
        assert report["input_manifests"]["phase4"]["mode"] == "manifest_verified"
        assert report["input_manifests"]["phase5"]["verified"] is True
        # The manifest must cover every consumed Phase 5A table.
        covered = set(report["input_manifests"]["phase5"]["artifacts"])
        assert config.PHASE5_PAIRWISE_SPEARMAN_FILENAME in covered
        assert config.PHASE5_FRAUD_DISCOVERY_CURVE_FILENAME in covered

    def test_legacy_unmanifested_inputs_recorded_honestly(self, tmp_path):
        world = build_world(tmp_path, manifests=False)
        report = preflight(world)
        for key in ("phase5", "phase4"):
            m = report["input_manifests"][key]
            assert m["mode"] == "legacy_unmanifested"
            assert m["verified"] is False
            assert "NOT performed" in m["note"]

    def test_tampered_phase5_manifest_rejected(self, tmp_path):
        world = build_world(tmp_path, manifests=True)
        spearman = world["phase5_dir"] / config.PHASE5_PAIRWISE_SPEARMAN_FILENAME
        with open(spearman, "ab") as f:
            f.write(b"tamper")
        with pytest.raises(ManifestVerificationError):
            preflight(world)

    def test_tampered_phase4_manifest_rejected(self, tmp_path):
        world = build_world(tmp_path, manifests=True)
        with open(world["phase4_dataset"], "ab") as f:
            f.write(b"\n")
        with pytest.raises(ManifestVerificationError):
            preflight(world)

    def test_matrix_table_schema_violation_rejected(self, tmp_path):
        world = build_world(tmp_path, manifests=False)
        path = world["phase5_dir"] / config.PHASE5_PAIRWISE_SPEARMAN_FILENAME
        df = pd.read_csv(path)
        df.drop(columns=["IF_002"], inplace=True)
        df.to_csv(path, index=False)
        with pytest.raises(p5b.Phase5InputError, match="IF_002"):
            preflight(world)

    def test_matrix_asymmetry_rejected(self, tmp_path):
        world = build_world(tmp_path, manifests=False)
        path = world["phase5_dir"] / config.PHASE5_PAIRWISE_JACCARD_FILENAME
        df = pd.read_csv(path, index_col=0)
        df.iloc[0, 1] = df.iloc[0, 1] + 0.3
        df.to_csv(path)
        with pytest.raises(p5b.Phase5InputError, match="symmetric"):
            preflight(world)

    def test_matrix_out_of_range_rejected(self, tmp_path):
        world = build_world(tmp_path, manifests=False)
        path = world["phase5_dir"] / config.PHASE5_PAIRWISE_SPEARMAN_FILENAME
        df = pd.read_csv(path, index_col=0)
        df.iloc[1, 2] = 1.7
        df.iloc[2, 1] = 1.7
        df.to_csv(path)
        with pytest.raises(p5b.Phase5InputError, match="range"):
            preflight(world)

    def test_hypergeometric_inconsistency_rejected(self, tmp_path):
        world = build_world(tmp_path, manifests=False)
        path = world["phase5_dir"] / config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME
        df = pd.read_csv(path)
        df.loc[0, "observed_intersection"] = int(df.loc[0, "observed_intersection"]) + 5
        df.to_csv(path, index=False)
        with pytest.raises(p5b.Phase5InputError, match="hypergeometric"):
            preflight(world)

    def test_discovery_curve_tampering_rejected(self, tmp_path):
        world = build_world(tmp_path, manifests=False)
        path = world["phase5_dir"] / config.PHASE5_FRAUD_DISCOVERY_CURVE_FILENAME
        df = pd.read_csv(path)
        df.loc[df["run_id"] == "IF_001", "precision"] *= 2.0
        df.to_csv(path, index=False)
        with pytest.raises(p5b.Phase5InputError, match="precision"):
            preflight(world)

    def test_agreement_groups_tampering_rejected(self, tmp_path):
        world = build_world(tmp_path, manifests=False)
        path = world["phase5_dir"] / config.PHASE5_AGREEMENT_GROUPS_FILENAME
        df = pd.read_csv(path)
        df.loc[df["group"] == "both", "observation_count"] += 1
        df.to_csv(path, index=False)
        with pytest.raises(p5b.Phase5InputError, match="partition"):
            preflight(world)

    def test_canonical_sample_size_enforced(self, world):
        with pytest.raises(p5b.Phase5InputError, match="30,000"):
            p5b.collect_phase5_plots_preflight(
                phase5_dir=world["phase5_dir"],
                phase4_dataset_path=world["phase4_dataset"],
                fs_a_path=world["fs_a"],
                verbose=False,
            )

    def test_ten_canonical_runs_required(self, tmp_path):
        world = build_world(tmp_path, manifests=False)
        path = world["phase4_dataset"]
        df = pd.read_csv(path)
        df = df[df["run_id"] != "LOF_005"]
        df.to_csv(path, index=False)
        with pytest.raises(ValueError, match="LOF_005"):
            preflight(world)

    def test_cross_snapshot_hash_mismatch_rejected(self, tmp_path):
        world = build_world(tmp_path, manifests=False)
        meta_path = world["phase5_dir"] / config.PHASE5_RUN_METADATA_FILENAME
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        payload["inputs"]["evaluation_dataset"]["sha256"] = "0" * 64
        meta_path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(p5b.Phase5InputError, match="cross-snapshot"):
            preflight(world)

    def test_phase5_metadata_schema_rejected(self, tmp_path):
        world = build_world(tmp_path, manifests=False)
        meta_path = world["phase5_dir"] / config.PHASE5_RUN_METADATA_FILENAME
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        payload["phase"] = "4"
        meta_path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(p5b.Phase5InputError, match="5A"):
            preflight(world)

    def test_row_level_consistency_cross_checks(self, world):
        """The preflight passes only because every Phase 5A table agrees
        with the row-level Phase 4 data (flags, groups, saved Jaccard)."""
        report = preflight(world)
        assert report["sample"]["sample_size"] == world["n"]
        assert report["sample"]["fraud_count"] == world["n_frauds"]
        assert report["writes_performed"] is False

    def test_fs_missing_sample_rows_rejected(self, tmp_path):
        world = build_world(tmp_path, manifests=False)
        fs = pd.read_csv(world["fs_a"])
        # Drop every FS row that the sample actually uses.
        sample_ids = set(pd.read_csv(world["phase4_dataset"])["row_id"].unique())
        fs = fs[~fs[config.ID_COLUMN].isin(sample_ids)]
        fs.to_csv(world["fs_a"], index=False)
        with pytest.raises(p5b.Phase5InputError, match="absent from the FS-A"):
            preflight(world)


# --------------------------------------------------------------------------
# The eight figure builders
# --------------------------------------------------------------------------

class TestFigureBuilders:
    def test_figure_1_renders_with_ap_and_prevalence(self, aligned, tmp_path):
        fig, meta = p5b.build_figure_1_precision_recall(aligned)
        out = p5b.save_figure(fig, tmp_path / "fig1.png")
        assert out.read_bytes()[:8] == PNG_MAGIC
        assert out.stat().st_size > 10_000
        assert set(meta["ap"]) == set(ALL_RUNS)
        legend = fig.axes[0].get_legend()
        labels = [t.get_text() for t in legend.get_texts()]
        assert all(r in " ".join(labels) for r in ALL_RUNS)
        assert any("prevalence" in t for t in labels)
        assert any("AP =" in t for t in labels)

    def test_figure_1_score_orientation(self, aligned):
        """AP must be computed on anomaly_score (higher = more anomalous):
        reversing the scores must change the AP, and the built figure must
        agree with a direct sklearn computation on the canonical column."""
        fig, meta = p5b.build_figure_1_precision_recall(aligned)
        run = "IF_003"
        score = aligned["runs"][run]["anomaly_score"]
        labels = aligned["labels"]
        assert math_isclose(meta["ap"][run], average_precision_score(labels, score))
        reversed_ap = average_precision_score(labels, -score)
        assert not math_isclose(meta["ap"][run], reversed_ap)

    def test_figure_1_orientation_detects_fraud(self):
        """A ranking that puts frauds on the high anomaly_score side must
        score a high AP; the mirrored ranking a low one."""
        rng = np.random.RandomState(0)
        n, n_frauds = 400, 10
        labels = np.zeros(n, dtype=np.int64)
        labels[rng.choice(n, size=n_frauds, replace=False)] = 1
        anomaly = rng.normal(0, 1, n)
        anomaly[labels == 1] += 4.0
        flags = np.zeros(n, dtype=np.uint8)
        flags[np.argsort(anomaly)[-n // 100:]] = 1
        world_aligned = make_aligned_from_arrays(labels, {"IF_003": (anomaly, flags)})
        _, meta = p5b.build_figure_1_precision_recall(world_aligned)
        assert meta["ap"]["IF_003"] > 0.9
        _, meta_rev = p5b.build_figure_1_precision_recall(
            make_aligned_from_arrays(labels, {"IF_003": (-anomaly, flags)})
        )
        assert meta_rev["ap"]["IF_003"] < 0.5

    def test_figure_1_operating_points_use_saved_flags(self, aligned):
        curves = p5b.compute_pr_curves(aligned)
        for run in ("IF_003", "IF_004", "LOF_004"):
            flags = aligned["runs"][run]["flag"] == 1
            fraud = aligned["labels"] == 1
            tp = int(np.count_nonzero(flags & fraud))
            op = curves[run]["flagged_operating_point"]
            assert op["tp"] == tp
            assert math_isclose(op["precision_at_1pct"], tp / flags.sum())
            assert math_isclose(op["recall_at_1pct"], tp / fraud.sum())

    def test_figure_2_two_panels_and_correct_baselines(self, tables, aligned):
        n = aligned["sample_size"]
        prevalence = aligned["fraud_count"] / n
        fig, meta = p5b.build_figure_2_fraud_discovery(tables["discovery"], n, prevalence)
        assert len(fig.axes) == 2
        ax_recall, ax_precision = fig.axes
        # Random recall baseline: an identity line (y == x).
        identity = [
            ln for ln in ax_recall.lines if len(ln.get_xdata()) > 2
            and np.allclose(ln.get_ydata(), ln.get_xdata())
        ]
        assert identity, "the recall panel must carry the y=x random baseline"
        # Random precision baseline: a horizontal line at the prevalence.
        flat = [
            ln for ln in ax_precision.lines
            if np.unique(np.asarray(ln.get_ydata())).size == 1
            and math_isclose(float(np.asarray(ln.get_ydata())[0]), prevalence)
        ]
        assert flat, "the precision panel must carry the prevalence baseline"
        # All ten runs are drawn on both panels (plus baselines).
        assert sum(1 for ln in ax_recall.lines) >= 10
        assert sum(1 for ln in ax_precision.lines) >= 10
        assert set(meta["runs"]) == set(ALL_RUNS)
        assert "prevalence" in meta["baselines"]["random_precision"]
        assert math_isclose(prevalence, aligned["fraud_count"] / n)

    def test_figure_2_plots_the_saved_discovery_data(self, tables, aligned):
        n = aligned["sample_size"]
        prevalence = aligned["fraud_count"] / n
        fig, _ = p5b.build_figure_2_fraud_discovery(tables["discovery"], n, prevalence)
        ax_recall = fig.axes[0]
        block = tables["discovery"][tables["discovery"]["run_id"] == "LOF_004"]
        expected_x = block["budget"].to_numpy() / float(n)
        expected_y = block["recall"].to_numpy()
        found = False
        for ln in ax_recall.lines:
            x, y = np.asarray(ln.get_xdata()), np.asarray(ln.get_ydata())
            if len(x) == len(expected_x) and np.allclose(x, expected_x) and np.allclose(y, expected_y):
                found = True
        assert found, "the plotted curve must equal the saved discovery table"

    def test_figure_3_full_support_and_tail_annotation(self, tables):
        fig, meta = p5b.build_figure_3_hypergeometric_overlap(tables["hypergeometric"])
        hyper = tables["hypergeometric"]
        support_lo = max(0, hyper["run_a_flagged"] + hyper["run_b_flagged"] - hyper["n_observations"])
        support_hi = min(hyper["run_a_flagged"], hyper["run_b_flagged"])
        assert meta["support"] == [support_lo, support_hi]
        # The plotted log-PMF spans the full valid support (no truncation).
        ax = fig.axes[0]
        pmf_lines = [ln for ln in ax.lines if len(ln.get_xdata()) == support_hi - support_lo + 1]
        assert pmf_lines, "the log-PMF must be drawn over the full support"
        assert np.array_equal(np.asarray(pmf_lines[0].get_xdata()),
                              np.arange(support_lo, support_hi + 1))
        # Observed and expected intersections are marked with vertical lines.
        def _vline_xs(linestyle):
            return [
                float(np.unique(np.asarray(ln.get_xdata()))[0])
                for ln in ax.lines
                if np.asarray(ln.get_xdata()).size == 2
                and np.unique(np.asarray(ln.get_xdata())).size == 1
                and ln.get_linestyle() == linestyle
            ]

        assert any(math_isclose(v, hyper["observed_intersection"]) for v in _vline_xs("-"))
        assert any(math_isclose(v, hyper["expected_intersection"]) for v in _vline_xs("--"))
        legend_texts = " ".join(t.get_text() for t in ax.get_legend().get_texts())
        assert f"observed intersection = {hyper['observed_intersection']}" in legend_texts
        assert f"expected under null = {hyper['expected_intersection']:.2f}" in legend_texts
        text_blob = " ".join(t.get_text() for t in ax.texts)
        # The tail annotation reports the log10 probability, never zero.
        assert "10^" in text_blob
        assert f"{hyper['log10_survival']:.2f}" in text_blob
        assert "not zero" in text_blob
        # The displayed range is labelled.
        assert "full support" in text_blob

    def test_figure_3_rejects_out_of_support_observation(self):
        with pytest.raises(p5b.Phase5PlotError, match="support"):
            p5b.build_figure_3_hypergeometric_overlap(
                {
                    "run_a": "A", "run_b": "B",
                    "n_observations": 100, "run_a_flagged": 10, "run_b_flagged": 10,
                    "observed_intersection": 11, "expected_intersection": 1.0,
                    "enrichment_observed_over_expected": 11.0,
                    "log10_survival": -20.0, "log_survival": -20.0 * np.log(10),
                    "threshold_pct": 1.0, "union_size": 9,
                    "survival_upper_tail": 1e-20,
                }
            )

    def test_figure_4_spearman_render(self, tables):
        fig, meta = p5b.build_figure_4_spearman_matrix(tables["spearman"])
        ax = fig.axes[0]
        image = ax.images[0]
        assert image.get_clim() == (-1.0, 1.0)
        assert np.allclose(np.asarray(image.get_array()), tables["spearman"].to_numpy())
        assert [t.get_text() for t in ax.get_xticklabels()] == ALL_RUNS
        assert [t.get_text() for t in ax.get_yticklabels()] == ALL_RUNS
        # Numeric annotation in every cell (100 cells).
        assert len(ax.texts) == len(ALL_RUNS) ** 2
        assert math_isclose(
            meta["pair_value"],
            float(tables["spearman"].loc["IF_003", "LOF_004"]),
        )

    def test_figure_5_jaccard_render(self, tables):
        fig, meta = p5b.build_figure_5_jaccard_matrix(tables["jaccard"])
        ax = fig.axes[0]
        image = ax.images[0]
        assert image.get_clim() == (0.0, 1.0)
        assert np.allclose(np.asarray(image.get_array()), tables["jaccard"].to_numpy())
        assert [t.get_text() for t in ax.get_xticklabels()] == ALL_RUNS
        assert math_isclose(
            meta["pair_value"],
            float(tables["jaccard"].loc["IF_003", "LOF_004"]),
        )

    def test_figure_6_topk_derivation_matches_phase5a(self, aligned):
        """Derived masks must equal phase5_analysis.derive_topk_selection
        verbatim, and ties must resolve by ascending stored position."""
        score = aligned["runs"]["IF_001"]["anomaly_score"]
        n = aligned["sample_size"]
        for pct in (0.2, 2.0):
            k = int(round(n * pct / 100))
            mask = p5b.derive_topk_selection(score, k) == 1
            assert mask.sum() == k
            assert np.array_equal(
                mask, p5a.derive_topk_selection(score, k) == 1
            )

    def test_figure_6_tie_break_first_stored_row_wins(self):
        scores = np.array([5.0, 5.0, 5.0, 1.0, 2.0])
        mask = p5a.derive_topk_selection(scores, 2)
        assert mask.tolist() == [1, 1, 0, 0, 0]  # positions 0 and 1 win ties

    def test_figure_6_canonical_1pct_uses_saved_flags(self, aligned, tables):
        curves, details = p5b.compute_topk_jaccard_curves(aligned)
        row = curves[curves["threshold_pct"] == config.PHASE5_CANONICAL_THRESHOLD_PCT].iloc[0]
        assert row["selection_source"] == "canonical_saved_flags"
        assert math_isclose(
            row["pair_jaccard"],
            float(tables["jaccard"].loc["IF_003", "LOF_004"]),
        )
        assert details["canonical_threshold_source"] == "saved Phase 3 flags (never rederived)"

    def test_figure_6_within_family_means_exclude_diagonal(self, aligned):
        curves, _ = p5b.compute_topk_jaccard_curves(aligned)
        pct = 2.0
        k = int(round(aligned["sample_size"] * pct / 100))
        masks = {
            r: p5b.derive_topk_selection(aligned["runs"][r]["anomaly_score"], k) == 1
            for r in ALL_RUNS
        }

        def jac(a, b):
            union = int(np.count_nonzero(masks[a] | masks[b]))
            return 1.0 if union == 0 else int(np.count_nonzero(masks[a] & masks[b])) / union

        if_runs = [r for r in ALL_RUNS if r.startswith("IF_")]
        lof_runs = [r for r in ALL_RUNS if r.startswith("LOF_")]
        expected_if = float(np.mean([jac(a, b) for a in if_runs for b in if_runs if a < b]))
        expected_lof = float(np.mean([jac(a, b) for a in lof_runs for b in lof_runs if a < b]))
        expected_cross = float(np.mean([jac(a, b) for a in if_runs for b in lof_runs]))
        row = curves[curves["threshold_pct"] == pct].iloc[0]
        assert math_isclose(row["within_if_mean_jaccard"], expected_if)
        assert math_isclose(row["within_lof_mean_jaccard"], expected_lof)
        assert math_isclose(row["cross_method_mean_jaccard"], expected_cross)
        # A diagonal-inclusive mean would differ (self-Jaccard = 1.0).
        naive_if = float(np.mean(
            [jac(a, b) if a != b else 1.0 for a in if_runs for b in if_runs]
        ))
        assert not math_isclose(row["within_if_mean_jaccard"], naive_if)

    def test_figure_6_renders_four_series(self, aligned):
        curves, _ = p5b.compute_topk_jaccard_curves(aligned)
        fig, meta = p5b.build_figure_6_topk_jaccard(curves)
        ax = fig.axes[0]
        # Four series curves (multi-point lines); the canonical-1% markers are
        # separate single-point overlays drawn with open faces.
        series = [ln for ln in ax.lines if np.asarray(ln.get_xdata()).size > 1]
        assert len(series) == 4  # within-IF, within-LOF, cross, highlighted pair
        canonical_markers = [ln for ln in ax.lines if np.asarray(ln.get_xdata()).size == 1]
        assert len(canonical_markers) == 4
        assert len(ax.get_legend().get_texts()) == 4
        xticks = [t.get_text() for t in ax.get_xticklabels()]
        assert any("0.1%" in t for t in xticks) and any("5%" in t for t in xticks)
        assert meta["canonical_threshold_pct"] == 1.0

    def test_percentile_convention_boundaries(self):
        """Percentile = 1 - descending rank / n: the top-1% boundary sits at
        exactly 0.99 (checked at n = 10,000 as in the specification)."""
        n = 10_000
        rng = np.random.RandomState(1)
        scores = rng.normal(0, 1, n)
        pct = p5b.anomaly_percentile(scores)
        assert pct.max() <= 1.0 and pct.min() >= 0.0
        # The 100th most anomalous observation has percentile 0.99.
        top_100 = np.sort(pct)[-100:]
        assert math_isclose(float(top_100.min()), 0.99, abs_tol=1e-12)
        # Most anomalous maps towards 1, least anomalous to 0.
        assert pct.max() > 0.999
        assert math_isclose(float(pct.min()), 0.0, abs_tol=1e-12)

    def test_figure_7_groups_counts_and_labels(self, aligned, tables):
        fig, meta = p5b.build_figure_7_rank_vs_rank(aligned)
        groups_table = tables["agreement_groups"].set_index("group")
        for group, label in p5b.GROUP_LABELS.items():
            assert meta["group_counts"][group] == int(
                groups_table.loc[group, "observation_count"]
            )
        legend_texts = " ".join(
            t.get_text() for t in fig.axes[0].get_legend().get_texts()
        )
        for group, label in p5b.GROUP_LABELS.items():
            assert label in legend_texts
            assert f"{meta['group_counts'][group]:,}" in legend_texts
        # The Neither group is rendered as a hexbin density.
        assert any(type(c).__name__ == "PolyCollection" for c in fig.axes[0].collections)

    def test_figure_7_overlay_membership(self):
        """Points in the Both overlay must sit at the percentile coordinates
        of exactly the observations flagged by both runs (row alignment)."""
        rng = np.random.RandomState(5)
        n = 120
        labels = np.zeros(n, dtype=np.int64)
        labels[[3, 17, 80]] = 1
        score_a = rng.normal(0, 1, n)
        score_b = rng.normal(0, 1, n)
        flags_a = np.zeros(n, dtype=np.uint8)
        flags_b = np.zeros(n, dtype=np.uint8)
        both_idx = [3, 40, 90]
        if_only = [10, 11]
        lof_only = [55, 56]
        flags_a[both_idx + if_only] = 1
        flags_b[both_idx + lof_only] = 1
        aligned = make_aligned_from_arrays(
            labels,
            {"IF_003": (score_a, flags_a), "LOF_004": (score_b, flags_b)},
        )
        fig, meta = p5b.build_figure_7_rank_vs_rank(aligned, "IF_003", "LOF_004")
        assert meta["group_counts"] == {
            "both": 3, "if_only": 2, "lof_only": 2, "neither": n - 7,
        }
        ax = fig.axes[0]
        pct_a = p5b.anomaly_percentile(score_a)
        pct_b = p5b.anomaly_percentile(score_b)
        marker_lines = {ln.get_marker(): ln for ln in ax.lines if ln.get_marker() != "None"}
        for idx in both_idx:
            point = (pct_a[idx], pct_b[idx])
            pts = np.column_stack(marker_lines["o"].get_data())
            assert np.any(np.isclose(pts, point).all(axis=1))
        for idx in if_only:
            point = (pct_a[idx], pct_b[idx])
            pts = np.column_stack(marker_lines["s"].get_data())
            assert np.any(np.isclose(pts, point).all(axis=1))
        for idx in lof_only:
            point = (pct_a[idx], pct_b[idx])
            pts = np.column_stack(marker_lines["^"].get_data())
            assert np.any(np.isclose(pts, point).all(axis=1))

    def test_figure_7_reference_lines_at_099(self, aligned):
        fig, _ = p5b.build_figure_7_rank_vs_rank(aligned)
        ax = fig.axes[0]
        vlines = [
            float(np.unique(np.asarray(ln.get_xdata()))[0])
            for ln in ax.lines
            if np.asarray(ln.get_xdata()).size == 2
            and np.unique(np.asarray(ln.get_xdata())).size == 1
        ]
        hlines = [
            float(np.unique(np.asarray(ln.get_ydata()))[0])
            for ln in ax.lines
            if np.asarray(ln.get_ydata()).size == 2
            and np.unique(np.asarray(ln.get_ydata())).size == 1
        ]
        assert any(math_isclose(v, 0.99) for v in vlines)
        assert any(math_isclose(h, 0.99) for h in hlines)

    def test_figure_8_row_alignment_with_shuffled_fs(self, tmp_path):
        """A shuffled FS-A row order must not misalign the join: coordinates
        must equal a manual PCA of the row_id-matched features."""
        world = build_world(tmp_path, manifests=False, shuffle_fs=True, seed=11)
        fs_df = pd.read_csv(world["fs_a"])
        dataset = p5a.load_phase4_dataset(world["phase4_dataset"])
        aligned = p5a.extract_aligned_runs(dataset, ALL_RUNS)
        X, cols = p5b.join_fs_sample(fs_df, aligned["row_ids"])
        assert cols == list(config.EXPECTED_FEATURE_COLUMNS)
        # The joined matrix equals the FS rows looked up by row_id.
        fs_indexed = fs_df.set_index(config.ID_COLUMN)[cols]
        expected = fs_indexed.reindex(aligned["row_ids"]).to_numpy()
        assert np.array_equal(X, expected)
        coords, explained = p5b.project_pca(X)
        manual = SklearnPCA(n_components=2, svd_solver="full").fit_transform(expected)
        assert np.allclose(coords, manual)

    def test_figure_8_neither_only_sampling(self, world, aligned):
        fs_df = pd.read_csv(world["fs_a"])
        fig, meta = p5b.build_figure_8_pca_agreement(
            fs_df, aligned, neither_max_points=40, neither_sample_seed=42
        )
        ax = fig.axes[0]
        background = [ln for ln in ax.lines if ln.get_marker() == "."][0]
        pts = np.column_stack(background.get_data())
        assert pts.shape[0] == 40
        # Every background point must belong to the Neither group.
        X, _ = p5b.join_fs_sample(fs_df, aligned["row_ids"])
        coords, _ = p5b.project_pca(X)
        masks = p5b.group_masks(
            aligned["runs"]["IF_003"]["flag"], aligned["runs"]["LOF_004"]["flag"]
        )
        neither_coords = coords[masks["neither"]]
        for point in pts:
            match = np.isclose(neither_coords, point).all(axis=1)
            assert match.any(), f"background point {point} is not a Neither point"
        # Determinism: the same seed reproduces the same background.
        fig2, _ = p5b.build_figure_8_pca_agreement(
            fs_df, aligned, neither_max_points=40, neither_sample_seed=42
        )
        background2 = [ln for ln in fig2.axes[0].lines if ln.get_marker() == "."][0]
        assert np.array_equal(pts, np.column_stack(background2.get_data()))
        assert "strictly from the Neither group" in meta["neither_background"]

    def test_figure_8_full_neither_by_default(self, world, aligned):
        fs_df = pd.read_csv(world["fs_a"])
        fig, meta = p5b.build_figure_8_pca_agreement(fs_df, aligned)
        background = [ln for ln in fig.axes[0].lines if ln.get_marker() == "."][0]
        masks = p5b.group_masks(
            aligned["runs"]["IF_003"]["flag"], aligned["runs"]["LOF_004"]["flag"]
        )
        assert background.get_xdata().shape[0] == int(masks["neither"].sum())
        assert "no subsampling" in meta["neither_background"]

    def test_figure_8_explained_variance_reporting(self, world, aligned):
        fs_df = pd.read_csv(world["fs_a"])
        fig, meta = p5b.build_figure_8_pca_agreement(fs_df, aligned)
        X, _ = p5b.join_fs_sample(fs_df, aligned["row_ids"])
        manual = SklearnPCA(n_components=2, svd_solver="full").fit(X)
        assert math_isclose(
            meta["explained_variance_pct"]["pc1"],
            float(manual.explained_variance_ratio_[0]) * 100.0,
        )
        assert math_isclose(
            meta["explained_variance_pct"]["pc2"],
            float(manual.explained_variance_ratio_[1]) * 100.0,
        )
        total = meta["explained_variance_pct"]["pc1"] + meta["explained_variance_pct"]["pc2"]
        assert 0.0 < total < 100.0  # a lossy projection, stated as such
        ax = fig.axes[0]
        assert "PC1" in ax.get_xlabel() and "variance explained" in ax.get_xlabel()
        assert "lossy projection" in ax.get_title()

    def test_figure_8_no_additional_rescaling(self, world, aligned):
        """The projected values must be the stored FS-A values, unrescaled."""
        fs_df = pd.read_csv(world["fs_a"])
        X, _ = p5b.join_fs_sample(fs_df, aligned["row_ids"])
        fs_indexed = fs_df.set_index(config.ID_COLUMN)[
            list(config.EXPECTED_FEATURE_COLUMNS)
        ]
        assert np.array_equal(
            X, fs_indexed.reindex(aligned["row_ids"]).to_numpy()
        )

    def test_all_eight_figures_via_execute(self, world, tmp_path):
        out_dir = tmp_path / "figures"
        result = execute(world, output_dir=out_dir)
        for i, filename in enumerate(config.PHASE5_FIGURE_FILENAMES, start=1):
            path = out_dir / filename
            assert path.is_file(), f"figure {i} missing: {filename}"
            assert path.read_bytes()[:8] == PNG_MAGIC
            assert path.stat().st_size > 5_000
        assert set(result["figures"]) == {1, 2, 3, 4, 5, 6, 7, 8}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def math_isclose(a, b, rel_tol=1e-9, abs_tol=1e-12):
    import math

    return math.isclose(float(a), float(b), rel_tol=rel_tol, abs_tol=abs_tol)


def make_aligned_from_arrays(labels, run_data, row_ids=None):
    """A minimal aligned dict (labels + per-run anomaly scores and flags)."""
    labels = np.asarray(labels)
    n = labels.shape[0]
    runs = {}
    for run_id, (anomaly, flags) in run_data.items():
        anomaly = np.asarray(anomaly, dtype=np.float64)
        flags = np.asarray(flags)
        assert anomaly.shape == (n,) and flags.shape == (n,)
        runs[run_id] = {"anomaly_score": anomaly, "flag": flags}
    return {
        "row_ids": np.asarray(row_ids if row_ids is not None else np.arange(n)),
        "labels": labels.astype(np.int64),
        "runs": runs,
        "run_ids": list(run_data),
        "sample_size": n,
        "fraud_count": int(np.count_nonzero(labels == 1)),
    }


# --------------------------------------------------------------------------
# Random baselines
# --------------------------------------------------------------------------

class TestRandomBaselines:
    def test_random_recall_is_identity(self):
        fractions = np.array([0.0, 0.01, 0.25, 0.5, 1.0])
        assert np.array_equal(p5b.random_expected_recall(fractions), fractions)

    def test_random_precision_is_prevalence(self):
        assert math_isclose(p5b.random_expected_precision(47 / 30_000), 47 / 30_000)
        with pytest.raises(p5b.Phase5PlotError):
            p5b.random_expected_precision(0.0)
        with pytest.raises(p5b.Phase5PlotError):
            p5b.random_expected_precision(1.0)

    def test_baselines_match_canonical_reference_shape(self, aligned):
        prevalence = aligned["fraud_count"] / aligned["sample_size"]
        assert math_isclose(p5b.random_expected_precision(prevalence), prevalence)
        assert math_isclose(float(p5b.random_expected_recall(np.array([0.01]))[0]), 0.01)


# --------------------------------------------------------------------------
# No model fit or refit; no input modification
# --------------------------------------------------------------------------

class TestNoFittingNoModification:
    def test_no_detector_is_fitted_or_refitted(self, tmp_path):
        world = build_world(tmp_path, manifests=False)
        with mock_patch_object(IsolationForest, "fit", side_effect=AssertionError("must not fit")), \
             mock_patch_object(IsolationForest, "fit_predict", side_effect=AssertionError("must not fit")), \
             mock_patch_object(LocalOutlierFactor, "fit", side_effect=AssertionError("must not fit")), \
             mock_patch_object(LocalOutlierFactor, "fit_predict", side_effect=AssertionError("must not fit")), \
             mock_patch_object(phase3, "run_isolation_forest", side_effect=AssertionError("must not fit")), \
             mock_patch_object(phase3, "run_lof", side_effect=AssertionError("must not fit")):
            result = execute(world, output_dir=tmp_path / "figures")
        assert len(result["figures"]) == 8

    def test_module_exposes_no_detector_constructors(self):
        assert not hasattr(p5b, "IsolationForest")
        assert not hasattr(p5b, "LocalOutlierFactor")
        source = Path(p5b.__file__).read_text(encoding="utf-8")
        assert "IsolationForest" not in source
        assert "LocalOutlierFactor" not in source

    def test_inputs_unmodified_by_execute(self, tmp_path):
        world = build_world(tmp_path, manifests=True)
        before = {
            **tree_state(world["phase5_dir"]),
            **tree_state(world["phase4_dataset"].parent),
            str(world["fs_a"]): (
                world["fs_a"].stat().st_size,
                hashlib.sha256(world["fs_a"].read_bytes()).hexdigest(),
            ),
        }
        execute(world, output_dir=tmp_path / "figures")
        after = {
            **tree_state(world["phase5_dir"]),
            **tree_state(world["phase4_dataset"].parent),
            str(world["fs_a"]): (
                world["fs_a"].stat().st_size,
                hashlib.sha256(world["fs_a"].read_bytes()).hexdigest(),
            ),
        }
        assert before == after

    def test_execute_writes_only_into_output_dir(self, tmp_path):
        world = build_world(tmp_path / "world", manifests=False)
        before = set(tree_state(world["root"]))
        execute(world, output_dir=tmp_path / "figures")
        after = set(tree_state(world["root"]))
        new_files = after - before
        assert new_files == set(), "no file may be created outside the output dir"


# --------------------------------------------------------------------------
# Preflight no-writes, output protection, staged publication rollback
# --------------------------------------------------------------------------

class TestSafetyAndPublication:
    def test_preflight_performs_no_writes(self, world, tmp_path):
        out_dir = tmp_path / "figures"
        before = tree_state(tmp_path)
        preflight(world, output_dir=out_dir)
        assert tree_state(tmp_path) == before
        assert not out_dir.exists(), "preflight must not even create the output dir"

    def test_execute_blocked_by_existing_outputs(self, world, tmp_path):
        out_dir = tmp_path / "figures"
        out_dir.mkdir(parents=True)
        sentinel = out_dir / config.PHASE5_FIGURE_FILENAMES[0]
        sentinel.write_bytes(b"existing figure bytes")
        with pytest.raises(Exception, match="[Aa]lready exist"):
            execute(world, output_dir=out_dir)
        assert sentinel.read_bytes() == b"existing figure bytes"
        assert list(out_dir.iterdir()) == [sentinel]

    def test_execute_replaces_outputs_only_with_overwrite(self, world, tmp_path):
        out_dir = tmp_path / "figures"
        execute(world, output_dir=out_dir)
        first = tree_state(out_dir)
        with pytest.raises(Exception, match="[Aa]lready exist"):
            execute(world, output_dir=out_dir)
        execute(world, output_dir=out_dir, overwrite=True)
        assert set(tree_state(out_dir)) == set(first)

    def test_render_failure_publishes_nothing(self, world, tmp_path):
        out_dir = tmp_path / "figures"
        with mock_patch_object(
            p5b, "build_figure_5_jaccard_matrix",
            side_effect=RuntimeError("render exploded"),
        ):
            with pytest.raises(RuntimeError, match="render exploded"):
                execute(world, output_dir=out_dir)
        assert not out_dir.exists(), "a render failure must publish nothing"
        # No staging leftovers next to the output directory.
        leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".")]
        assert leftovers == []

    def test_publication_rollback_restores_originals(self, world, tmp_path):
        out_dir = tmp_path / "figures"
        out_dir.mkdir(parents=True)
        sentinels = {}
        for name in (
            *config.PHASE5_FIGURE_FILENAMES,
            config.PHASE5_FIGURE_CATALOG_FILENAME,
            config.PHASE5_PLOT_METADATA_FILENAME,
            config.PHASE5_PLOT_MANIFEST_FILENAME,
        ):
            content = f"sentinel:{name}".encode()
            (out_dir / name).write_bytes(content)
            sentinels[name] = content
        with mock_patch_object(
            p5b, "save_manifest", side_effect=RuntimeError("manifest write failed")
        ):
            with pytest.raises(RuntimeError, match="manifest write failed"):
                execute(world, output_dir=out_dir, overwrite=True)
        # Every original file is restored byte-identical; nothing new remains.
        assert {p.name for p in out_dir.iterdir()} == set(sentinels)
        for name, content in sentinels.items():
            assert (out_dir / name).read_bytes() == content
        leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".")]
        assert leftovers == []

    def test_manifest_published_last_and_covers_everything(self, world, tmp_path):
        out_dir = tmp_path / "figures"
        execute(world, output_dir=out_dir)
        manifest_path = out_dir / config.PHASE5_PLOT_MANIFEST_FILENAME
        assert manifest_path.is_file()
        report = verify_manifest(
            load_manifest(manifest_path), out_dir,
            required_artifacts=(
                *config.PHASE5_FIGURE_FILENAMES,
                config.PHASE5_FIGURE_CATALOG_FILENAME,
                config.PHASE5_PLOT_METADATA_FILENAME,
            ),
        )
        assert len(report) == 10  # 8 figures + catalog + metadata
        # The manifest is the newest file in the directory.
        newest = max(p.stat().st_mtime for p in out_dir.iterdir())
        assert manifest_path.stat().st_mtime == pytest.approx(newest, abs=2.0)

    def test_catalog_and_metadata_contents(self, world, tmp_path):
        out_dir = tmp_path / "figures"
        execute(world, output_dir=out_dir)
        catalog = pd.read_csv(out_dir / config.PHASE5_FIGURE_CATALOG_FILENAME)
        assert list(catalog["filename"]) == list(config.PHASE5_FIGURE_FILENAMES)
        assert list(catalog["figure_no"]) == list(range(1, 9))
        assert (catalog["size_bytes"] > 0).all()

        with open(out_dir / config.PHASE5_PLOT_METADATA_FILENAME, encoding="utf-8") as f:
            metadata = json.load(f)
        assert metadata["phase"] == "5B"
        assert metadata["model_fitting"]["models_fitted"] == 0
        assert len(metadata["inputs"]) == 8
        for entry in metadata["inputs"].values():
            assert len(entry["sha256"]) == 64
        assert metadata["input_manifests"]["phase5_commit_manifest"]["verified"] is True
        assert metadata["figures_rendered"] == 8
        assert set(metadata["figure_inventory"]) == {str(i) for i in range(1, 9)}
        conventions = metadata["plotting_conventions"]
        assert conventions["percentile_convention"] == p5b.PERCENTILE_CONVENTION
        assert conventions["tie_breaking"] == p5a.TIE_BREAK_POLICY
        assert "matplotlib" in metadata["environment"]
        assert "lossy" in metadata["plotting_conventions"]["pca"]["disclaimer"].lower()


# --------------------------------------------------------------------------
# CLI behaviour (subprocess, exactly as a user invokes it)
# --------------------------------------------------------------------------

class TestCommandLineInterface:
    def _run(self, world, out_dir, *extra):
        return subprocess.run(
            [
                sys.executable, str(RUNNER),
                "--phase5-dir", str(world["phase5_dir"]),
                "--phase4-dataset", str(world["phase4_dataset"]),
                "--fs-a", str(world["fs_a"]),
                "--output-dir", str(out_dir),
                "--expected-sample-size", str(world["n"]),
                *extra,
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )

    def test_default_is_preflight_and_writes_nothing(self, world, tmp_path):
        out_dir = tmp_path / "figures"
        result = self._run(world, out_dir)
        assert result.returncode == 0, result.stderr
        assert "PREFLIGHT" in result.stdout
        assert not out_dir.exists()

    def test_execute_renders_the_eight_figures(self, world, tmp_path):
        out_dir = tmp_path / "figures"
        result = self._run(world, out_dir, "--execute")
        assert result.returncode == 0, result.stderr
        for filename in config.PHASE5_FIGURE_FILENAMES:
            assert (out_dir / filename).is_file()
        assert (out_dir / config.PHASE5_FIGURE_CATALOG_FILENAME).is_file()
        assert (out_dir / config.PHASE5_PLOT_METADATA_FILENAME).is_file()
        assert (out_dir / config.PHASE5_PLOT_MANIFEST_FILENAME).is_file()

    def test_second_execute_is_blocked(self, world, tmp_path):
        out_dir = tmp_path / "figures"
        assert self._run(world, out_dir, "--execute").returncode == 0
        blocked = self._run(world, out_dir, "--execute")
        assert blocked.returncode == 1
        assert "overwrite" in blocked.stderr.lower()

    def test_overwrite_flag_replaces_outputs(self, world, tmp_path):
        out_dir = tmp_path / "figures"
        assert self._run(world, out_dir, "--execute").returncode == 0
        replaced = self._run(world, out_dir, "--execute", "--overwrite")
        assert replaced.returncode == 0, replaced.stderr
        assert len(list(out_dir.glob("*.png"))) == 8


def mock_patch_object(target, attribute, side_effect):
    from unittest import mock

    return mock.patch.object(target, attribute, side_effect=side_effect)

# ==========================================================================
# Hardening Regression Tests (Manifest Rollback)
# ==========================================================================
class TestPhase5BHardeningRepairs:
    def test_publication_rollback_on_manifest_failure(self, tmp_path):
        import shutil
        from unittest import mock
        from mplad.stream_a import phase5_plots
        from mplad.common.io import save_json

        out_dir = tmp_path / "figures"
        out_dir.mkdir()
        
        # Create dummy pre-existing files
        dummy_png = out_dir / "figure_1.png"
        dummy_png.write_text("old_image", encoding="utf-8")
        
        stage_dir = tmp_path / "staging"
        stage_dir.mkdir()
        stage_png = stage_dir / "figure_1.png"
        stage_png.write_text("new_image", encoding="utf-8")
        
        orig_save = save_json
        def fake_save_json(payload, path, overwrite=False):
            if "manifest" in str(path):
                # Write partial file then crash
                with open(path, "w", encoding="utf-8") as f:
                    f.write('{"partial": ')
                raise OSError("Simulated manifest write failure")
            orig_save(payload, path, overwrite)
            
        with mock.patch("mplad.stream_a.phase5_plots.save_json", side_effect=fake_save_json):
            # Bypass staging verification for the dummy files
            with mock.patch("mplad.stream_a.phase5_plots._verify_staged_artifacts"):
                with pytest.raises(OSError, match="Simulated manifest write failure"):
                    phase5_plots._publish_with_rollback(
                        stage_dir, out_dir, ["figure_1.png"], "manifest.json", overwrite=True, verbose=False
                    )
                    
        # Verify rollback succeeded
        assert dummy_png.read_text(encoding="utf-8") == "old_image", "Backup was not restored"
        assert not (out_dir / "manifest.json").exists(), "Partial manifest was not deleted"
