"""Lightweight software-structure tests for the Phase 3 pipeline.

These tests run on SYNTHETIC data with REDUCED configurations. They validate
the software contract (schema, sampling, flags, artifacts, protection
mechanisms) -- they never execute the canonical ten-model experiment and
never touch real data.
"""
from __future__ import annotations

import pickle
from unittest import mock

import numpy as np
import pandas as pd
import pytest
import shutil

from mplad.common import config
from mplad.common import io as mplad_io
from mplad.common.validation import FeatureMatrixError, validate_feature_matrix
from mplad.stream_a import phase3


# --------------------------------------------------------------------------
# Synthetic data helpers (schema identical to the real FS-A)
# --------------------------------------------------------------------------

def make_synthetic_fs(n_rows: int = 800, seed: int = 0) -> pd.DataFrame:
    """Build a schema-compatible FS-A stand-in: Time, V1..V28, Amount, row_id."""
    rng = np.random.RandomState(seed)
    df = pd.DataFrame({f"V{i}": rng.normal(size=n_rows) for i in range(1, 29)})
    df.insert(0, "Time", rng.uniform(0, 172792, size=n_rows))
    df["Amount"] = np.abs(rng.normal(88, 250, size=n_rows))
    df[config.ID_COLUMN] = np.arange(n_rows)  # row_id last, like the Phase 2 output
    return df


MINI_IF_CONFIGS = [{"n_estimators": 10, "max_samples": 64, "random_state": 42}]
MINI_LOF_CONFIGS = [{"n_neighbors": 5, "metric": "euclidean"}]


@pytest.fixture()
def mini_experiment(tmp_path):
    """Full pipeline on synthetic data: 800 rows -> 300 sample, 1 IF + 1 LOF run."""
    fs_path = tmp_path / "ULB_FS_A_Baseline.csv"
    make_synthetic_fs(n_rows=800, seed=0).to_csv(fs_path, index=False)
    out_dir = tmp_path / "phase3_out"
    result = phase3.run_phase3_experiment(
        fs_a_path=fs_path,
        output_dir=out_dir,
        sample_size=300,
        sample_seed=42,
        if_configs=MINI_IF_CONFIGS,
        lof_configs=MINI_LOF_CONFIGS,
        verbose=False,
    )
    result["_paths"] = {
        "fs": fs_path,
        "out": out_dir,
        "metadata": out_dir / config.METADATA_FILENAME,
        "predictions": out_dir / config.PREDICTIONS_FILENAME,
    }
    return result


# ==========================================================================
# 0. Frozen configuration guards
# ==========================================================================

class TestFrozenConfiguration:
    def test_if_grid_matches_the_original_cell(self):
        assert config.ISOLATION_FOREST_CONFIGS == [
            {"n_estimators": 100, "max_samples": 256, "random_state": 42},
            {"n_estimators": 200, "max_samples": 256, "random_state": 42},
            {"n_estimators": 100, "max_samples": 0.05, "random_state": 42},
            {"n_estimators": 100, "max_samples": 256, "random_state": 43},
            {"n_estimators": 100, "max_samples": 256, "random_state": 44},
        ]

    def test_lof_grid_matches_the_original_cell(self):
        assert config.LOF_CONFIGS == [
            {"n_neighbors": 5, "metric": "euclidean"},
            {"n_neighbors": 15, "metric": "euclidean"},
            {"n_neighbors": 30, "metric": "euclidean"},
            {"n_neighbors": 50, "metric": "euclidean"},
            {"n_neighbors": 30, "metric": "manhattan"},
        ]

    def test_fixed_params_match_the_original_cell(self):
        assert config.IF_FIXED_PARAMS == {"n_jobs": 1}
        assert config.LOF_FIXED_PARAMS == {
            "algorithm": "ball_tree", "leaf_size": 40, "n_jobs": 1,
        }

    def test_threshold_and_sampling_constants(self):
        assert config.THRESHOLD_PERCENTILE == 1.0
        assert config.THRESHOLD_RULE_LABEL == "Bottom 1.0% of scores"
        assert (config.SAMPLE_SIZE_DEFAULT, config.SAMPLE_SEED_DEFAULT) == (30000, 42)

    def test_metadata_columns_match_the_reference_csv(self):
        assert config.METADATA_COLUMNS == [
            "run_id", "model", "n_estimators", "max_samples", "random_state",
            "runtime_seconds", "threshold_rule", "flagged_count",
            "n_neighbors", "metric",
        ]


# ==========================================================================
# 1. FS-A schema validation
# ==========================================================================

class TestFeatureMatrixValidation:
    def test_valid_matrix_passes_and_returns_feature_columns(self):
        df = make_synthetic_fs(50)
        features = validate_feature_matrix(df)
        assert features == list(config.EXPECTED_FEATURE_COLUMNS)

    def test_shuffled_columns_are_reordered(self):
        df = make_synthetic_fs(50)
        shuffled_cols = list(df.columns)
        np.random.shuffle(shuffled_cols)
        df_shuffled = df[shuffled_cols]
        features = validate_feature_matrix(df_shuffled)
        assert features == list(config.EXPECTED_FEATURE_COLUMNS)

    def test_missing_feature_column_is_rejected(self):
        df = make_synthetic_fs(50).drop(columns=["V14"])
        with pytest.raises(FeatureMatrixError, match="V14"):
            validate_feature_matrix(df)

    def test_missing_id_column_is_rejected(self):
        df = make_synthetic_fs(50).drop(columns=[config.ID_COLUMN])
        with pytest.raises(FeatureMatrixError, match="row_id"):
            validate_feature_matrix(df)

    def test_unexpected_extra_column_is_rejected(self):
        df = make_synthetic_fs(50)
        df["V99"] = 0.0
        with pytest.raises(FeatureMatrixError, match="V99"):
            validate_feature_matrix(df)

    def test_non_numeric_column_is_rejected(self):
        df = make_synthetic_fs(50)
        df["Time"] = df["Time"].astype(str)
        with pytest.raises(FeatureMatrixError, match="non-numeric"):
            validate_feature_matrix(df)

    def test_missing_values_are_rejected(self):
        df = make_synthetic_fs(50)
        df.loc[3, "V7"] = np.nan
        with pytest.raises(FeatureMatrixError, match="non-finite"):
            validate_feature_matrix(df)

    def test_inf_values_are_rejected(self):
        df = make_synthetic_fs(50)
        df.loc[2, "V5"] = np.inf
        df.loc[3, "Amount"] = -np.inf
        with pytest.raises(FeatureMatrixError, match=r"non-finite.*V5.*Amount"):
            validate_feature_matrix(df)

    def test_missing_input_file_raises_clear_error(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="ULB_FS_A_Baseline"):
            mplad_io.load_feature_matrix(tmp_path / "ULB_FS_A_Baseline.csv")


# ==========================================================================
# 2. Class exclusion / rejection (label leakage guard)
# ==========================================================================

class TestClassExclusion:
    def test_class_column_is_rejected(self):
        df = make_synthetic_fs(50)
        df["Class"] = 0
        with pytest.raises(FeatureMatrixError, match="Class"):
            validate_feature_matrix(df)

    def test_class_is_registered_as_forbidden(self):
        assert "Class" in config.FORBIDDEN_COLUMNS


# ==========================================================================
# 3. Unique row_id validation
# ==========================================================================

class TestRowIdValidation:
    def test_duplicate_row_ids_are_rejected(self):
        df = make_synthetic_fs(50)
        df.loc[1, config.ID_COLUMN] = df.loc[0, config.ID_COLUMN]
        with pytest.raises(FeatureMatrixError, match="duplicate"):
            validate_feature_matrix(df)

    def test_missing_row_id_values_are_rejected(self):
        df = make_synthetic_fs(50)
        df.loc[7, config.ID_COLUMN] = np.nan
        with pytest.raises(FeatureMatrixError, match="row_id"):
            validate_feature_matrix(df)


# ==========================================================================
# 4. Reproducible 30k sample selection
# ==========================================================================

class TestSampleSelection:
    def test_same_seed_same_sample(self):
        df = make_synthetic_fs(2000, seed=3)
        ids_a, X_a = phase3.build_experiment_sample(df, 500, 42)
        ids_b, X_b = phase3.build_experiment_sample(df, 500, 42)
        assert np.array_equal(ids_a, ids_b)
        assert np.array_equal(X_a, X_b)

    def test_different_seed_different_sample(self):
        df = make_synthetic_fs(2000, seed=3)
        ids_a, _ = phase3.build_experiment_sample(df, 500, 42)
        ids_b, _ = phase3.build_experiment_sample(df, 500, 43)
        assert not np.array_equal(ids_a, ids_b)

    def test_sample_indices_match_legacy_global_api(self):
        """The explicit demonstration demanded by the migration contract:
        RandomState(seed).choice(...) is bit-for-bit identical to the original
        'np.random.seed(seed); np.random.choice(...)' mechanism."""
        n_rows, size, seed = 5000, 500, 42
        np.random.seed(seed)  # exact original mechanism (legacy global API)
        legacy = np.random.choice(n_rows, size=size, replace=False)
        modern = phase3.draw_sample_indices(n_rows, size, seed)
        assert np.array_equal(legacy, modern)
        assert np.unique(modern).size == size  # without replacement

    def test_sample_size_larger_than_population_rejected(self):
        df = make_synthetic_fs(100)
        with pytest.raises(ValueError, match="exceeds available rows"):
            phase3.build_experiment_sample(df, 200, 42)

    def test_sample_shape_and_id_handling(self):
        df = make_synthetic_fs(1000, seed=1)
        ids, X = phase3.build_experiment_sample(df, 300, 42)
        assert ids.shape == (300,)
        assert X.shape == (300, 30)  # row_id removed from the model input
        assert set(ids.tolist()) <= set(df[config.ID_COLUMN].tolist())
        assert np.unique(ids).size == 300


# ==========================================================================
# 5. Consistency of sampled IDs across all model runs
# ==========================================================================

class TestRunConsistency:
    def test_all_runs_share_the_sample_and_its_row_ids(self, mini_experiment):
        bundle = mini_experiment["bundle"]
        row_ids = bundle["row_ids"]
        assert len(row_ids) == 300
        for run_id, entry in bundle["predictions"].items():
            assert len(entry["scores"]) == 300
            assert len(entry["flags"]) == 300

    def test_repeated_experiment_is_bitwise_deterministic(self, tmp_path):
        fs_path = tmp_path / "fs.csv"
        make_synthetic_fs(800, seed=0).to_csv(fs_path, index=False)

        def run_once(tag):
            return phase3.run_phase3_experiment(
                fs_a_path=fs_path,
                output_dir=tmp_path / tag,
                sample_size=300,
                sample_seed=42,
                if_configs=MINI_IF_CONFIGS,
                lof_configs=MINI_LOF_CONFIGS,
                verbose=False,
            )

        r1, r2 = run_once("a"), run_once("b")
        assert np.array_equal(r1["bundle"]["row_ids"], r2["bundle"]["row_ids"])
        assert list(r1["bundle"]["predictions"]) == list(r2["bundle"]["predictions"])
        for run_id in r1["bundle"]["predictions"]:
            e1 = r1["bundle"]["predictions"][run_id]
            e2 = r2["bundle"]["predictions"][run_id]
            assert np.array_equal(e1["scores"], e2["scores"])
            assert np.array_equal(e1["flags"], e2["flags"])


# ==========================================================================
# 6. Native score direction (lower = more anomalous)
# ==========================================================================

class TestNativeScoreDirection:
    @pytest.mark.parametrize("run_id", ["IF_001", "LOF_001"])
    def test_flagged_scores_are_the_lowest_tail(self, mini_experiment, run_id):
        entry = mini_experiment["bundle"]["predictions"][run_id]
        scores, flags = entry["scores"], entry["flags"]
        flagged, unflagged = scores[flags == 1], scores[flags == 0]
        assert flagged.max() <= unflagged.min()   # tail separation (<= covers ties)
        assert flagged.mean() < unflagged.mean()  # orientation: lower = more anomalous

    def test_percentile_rule_flags_bottom_not_top(self):
        scores = np.arange(101, dtype=np.float64)  # 0..100
        threshold, flags = phase3.apply_percentile_flags(scores, 10.0)
        # 10th percentile of 0..100 (linear interpolation) = 10.0 -> flags 0..10
        assert threshold == pytest.approx(10.0)
        assert int(flags.sum()) == 11
        assert flags[0] == 1 and flags[50] == 0 and flags[100] == 0


# ==========================================================================
# 7. Flag dtype and expected count
# ==========================================================================

class TestFlagDtypeAndCount:
    def test_flag_dtype_is_uint8(self, mini_experiment):
        for entry in mini_experiment["bundle"]["predictions"].values():
            assert entry["flags"].dtype == np.uint8

    def test_score_dtype_is_float32(self, mini_experiment):
        for entry in mini_experiment["bundle"]["predictions"].values():
            assert entry["scores"].dtype == np.float32

    def test_expected_flag_count_for_distinct_scores(self):
        rng = np.random.RandomState(0)
        scores = rng.normal(size=10_000)  # almost surely distinct values
        _, flags = phase3.apply_percentile_flags(scores, 1.0)
        assert int(flags.sum()) == 100    # exactly 1% of 10,000

    def test_ties_at_the_threshold_are_all_flagged(self):
        scores = np.array([0.0] * 5 + list(range(1, 96)), dtype=np.float64)
        _, flags = phase3.apply_percentile_flags(scores, 1.0)
        assert flags[:5].tolist() == [1, 1, 1, 1, 1]

    def test_mini_run_flag_count_is_one_percent(self, mini_experiment):
        # 300 rows x 1% -> exactly 3 flags for distinct float scores
        for run_id, entry in mini_experiment["bundle"]["predictions"].items():
            assert int(entry["flags"].sum()) == 3, run_id


# ==========================================================================
# 8. Prediction pickle structure
# ==========================================================================

class TestPredictionBundle:
    def test_bundle_on_disk_matches_the_contract(self, mini_experiment):
        pkl_path = mini_experiment["_paths"]["predictions"]
        with open(pkl_path, "rb") as f:
            bundle = pickle.load(f)
        assert set(bundle) == {"row_ids", "predictions"}
        assert list(bundle["predictions"]) == ["IF_001", "LOF_001"]
        for run_id, entry in bundle["predictions"].items():
            assert set(entry) == {"scores", "flags"}
            assert entry["scores"].dtype == np.float32
            assert entry["flags"].dtype == np.uint8
            assert entry["scores"].shape == entry["flags"].shape == (300,)
        assert np.unique(bundle["row_ids"]).size == 300
        assert bundle["row_ids"].dtype.kind in "iu"

    def test_row_ids_are_a_subset_of_the_input_matrix(self, mini_experiment):
        original_ids = set(pd.read_csv(mini_experiment["_paths"]["fs"])[config.ID_COLUMN])
        with open(mini_experiment["_paths"]["predictions"], "rb") as f:
            bundle = pickle.load(f)
        assert set(bundle["row_ids"].tolist()) <= original_ids


# ==========================================================================
# 9. Metadata schema
# ==========================================================================

class TestMetadataSchema:
    def test_columns_match_the_existing_reference_schema(self, mini_experiment):
        assert list(mini_experiment["metadata"].columns) == list(config.METADATA_COLUMNS)

    def test_run_ids_and_model_names(self, mini_experiment):
        meta = mini_experiment["metadata"]
        assert meta["run_id"].tolist() == ["IF_001", "LOF_001"]
        assert meta["model"].tolist() == ["IsolationForest", "LOF"]

    def test_field_patterns(self, mini_experiment):
        meta = mini_experiment["metadata"].set_index("run_id")
        assert meta.loc["IF_001", "random_state"] == 42
        assert meta.loc["LOF_001", "random_state"] == "N/A"
        assert meta.loc["IF_001", "n_estimators"] == 10
        assert np.isnan(meta.loc["LOF_001", "n_estimators"])
        assert np.isnan(meta.loc["LOF_001", "max_samples"])
        assert np.isnan(meta.loc["IF_001", "n_neighbors"])
        assert np.isnan(meta.loc["IF_001", "metric"])
        assert meta.loc["LOF_001", "n_neighbors"] == 5
        assert meta.loc["LOF_001", "metric"] == "euclidean"
        assert (mini_experiment["metadata"]["threshold_rule"]
                == config.THRESHOLD_RULE_LABEL).all()
        assert (mini_experiment["metadata"]["flagged_count"] == 3).all()
        assert (mini_experiment["metadata"]["runtime_seconds"] >= 0).all()

    def test_canonical_metadata_file_if_present_has_same_schema(self):
        """Optional cross-check against the real canonical CSV when it exists
        (skipped on machines where the results directory is absent)."""
        canonical = config.DEFAULT_OUTPUT_DIR / config.METADATA_FILENAME
        if not canonical.is_file():
            pytest.skip(f"canonical metadata not found at {canonical}")
        canonical_cols = pd.read_csv(canonical, nrows=0).columns.tolist()
        assert canonical_cols == list(config.METADATA_COLUMNS)


# ==========================================================================
# 10. Output overwrite protection
# ==========================================================================

class TestOverwriteProtection:
    def test_saving_over_existing_file_requires_overwrite(self, tmp_path):
        df = pd.DataFrame({"a": [1]})
        bundle = {"row_ids": np.array([1]), "predictions": {}}
        mplad_io.publish_phase3_artifacts(df, bundle, tmp_path, overwrite=False)
        with pytest.raises(mplad_io.OutputExistsError):
            mplad_io.publish_phase3_artifacts(df, bundle, tmp_path, overwrite=False)
        mplad_io.publish_phase3_artifacts(df, bundle, tmp_path, overwrite=True)

    def test_precheck_lists_all_conflicting_files(self, tmp_path):
        d = tmp_path / "out"
        d.mkdir()
        (d / config.METADATA_FILENAME).write_text("x")
        (d / config.PREDICTIONS_FILENAME).write_bytes(b"x")
        paths = [d / config.METADATA_FILENAME, d / config.PREDICTIONS_FILENAME]
        with pytest.raises(mplad_io.OutputExistsError) as exc:
            mplad_io.assert_outputs_writable(paths, overwrite=False)
        assert config.METADATA_FILENAME in str(exc.value)
        assert config.PREDICTIONS_FILENAME in str(exc.value)
        mplad_io.assert_outputs_writable(paths, overwrite=True)  # passes

    def test_experiment_refuses_existing_outputs_before_fitting(self, tmp_path):
        fs_path = tmp_path / "fs.csv"
        make_synthetic_fs(800, seed=0).to_csv(fs_path, index=False)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / config.METADATA_FILENAME).write_text("existing")
        (out_dir / config.PREDICTIONS_FILENAME).write_bytes(b"existing")

        with mock.patch.object(
            phase3, "run_isolation_forest", side_effect=AssertionError("must not fit")
        ):
            with pytest.raises(mplad_io.OutputExistsError):
                phase3.run_phase3_experiment(
                    fs_a_path=fs_path,
                    output_dir=out_dir,
                    sample_size=300,
                    sample_seed=42,
                    if_configs=MINI_IF_CONFIGS,
                    lof_configs=MINI_LOF_CONFIGS,
                    verbose=False,
                )

    def test_dry_run_never_fits(self, tmp_path):
        fs_path = tmp_path / "fs.csv"
        make_synthetic_fs(800, seed=0).to_csv(fs_path, index=False)
        with mock.patch.object(
            phase3, "run_isolation_forest", side_effect=AssertionError("must not fit")
        ), mock.patch.object(
            phase3, "run_lof", side_effect=AssertionError("must not fit")
        ):
            report = phase3.collect_dry_run_report(
                fs_a_path=fs_path, sample_size=300, sample_seed=42, output_dir=tmp_path
            )
        assert report["sampling_deterministic"] is True
        assert report["outputs"]["blocked"] is False

    def test_dry_run_blocked_with_existing_outputs(self, tmp_path):
        fs_path = tmp_path / "fs.csv"
        make_synthetic_fs(100).to_csv(fs_path, index=False)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / config.METADATA_FILENAME).write_text("x")
        report = phase3.collect_dry_run_report(fs_a_path=fs_path, sample_size=50, output_dir=out_dir, if_configs=MINI_IF_CONFIGS, lof_configs=MINI_LOF_CONFIGS)
        assert report["outputs"]["blocked"] is True

# ==========================================================================
# 11. Artifact Publication
# ==========================================================================

class TestArtifactPublication:
    def test_successful_publication_writes_manifest(self, tmp_path):
        df = pd.DataFrame({"a": [1]})
        bundle = {"row_ids": np.array([1]), "predictions": {}}
        mplad_io.publish_phase3_artifacts(df, bundle, tmp_path)
        assert (tmp_path / config.METADATA_FILENAME).exists()
        assert (tmp_path / config.PREDICTIONS_FILENAME).exists()
        assert (tmp_path / config.MANIFEST_FILENAME).exists()

    def test_publication_rollback_on_failure(self, tmp_path):
        meta_path = tmp_path / config.METADATA_FILENAME
        pred_path = tmp_path / config.PREDICTIONS_FILENAME
        meta_path.write_text("old_meta")
        pred_path.write_bytes(b"old_pred")
        
        df = pd.DataFrame({"a": [2]})
        bundle = {"row_ids": np.array([2]), "predictions": {}}
        
        import shutil
        original_move = shutil.move
        def fake_move(src, dst):
            if str(src).endswith(".stage") and str(dst).endswith(config.PREDICTIONS_FILENAME): raise OSError("Simulated disk failure")
            return original_move(src, dst)
        
        with mock.patch("mplad.common.io.shutil.move", side_effect=fake_move):
            with pytest.raises(RuntimeError, match="Simulated disk failure"):
                mplad_io.publish_phase3_artifacts(df, bundle, tmp_path, overwrite=True)
        
        assert meta_path.read_text() == "old_meta"
        assert pred_path.read_bytes() == b"old_pred"
