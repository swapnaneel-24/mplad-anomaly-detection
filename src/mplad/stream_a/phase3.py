"""Stream A -- Phase 3: strict-unsupervised anomaly detection."""
from __future__ import annotations
import gc
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from mplad.common import config
from mplad.common.io import (
    assert_outputs_writable,
    load_feature_matrix,
    publish_phase3_artifacts,
)
from mplad.common.validation import validate_feature_matrix

__all__ = ["draw_sample_indices", "build_experiment_sample", "apply_percentile_flags", "run_isolation_forest", "run_lof", "run_phase3_experiment", "collect_dry_run_report"]

def draw_sample_indices(n_rows: int, sample_size: int, sample_seed: int) -> np.ndarray:
    if sample_size > n_rows: raise ValueError("sample_size exceeds available rows")
    if sample_size < 1: raise ValueError("sample_size must be >= 1")
    rng = np.random.RandomState(sample_seed)
    return rng.choice(n_rows, size=sample_size, replace=False)

def build_experiment_sample(
    fs_df: pd.DataFrame, sample_size: int = config.SAMPLE_SIZE_DEFAULT, sample_seed: int = config.SAMPLE_SEED_DEFAULT,
) -> Tuple[np.ndarray, np.ndarray]:
    feature_cols = validate_feature_matrix(fs_df)
    indices = draw_sample_indices(len(fs_df), sample_size, sample_seed)
    fs_subsampled = fs_df.iloc[indices].reset_index(drop=True)
    row_ids = fs_subsampled[config.ID_COLUMN].to_numpy()
    X = fs_subsampled[feature_cols].to_numpy()
    return row_ids, X

def apply_percentile_flags(native_scores: np.ndarray, threshold_percentile: float = config.THRESHOLD_PERCENTILE) -> Tuple[float, np.ndarray]:
    native_scores = np.asarray(native_scores)
    threshold_val = float(np.percentile(native_scores, threshold_percentile))
    flags = np.where(native_scores <= threshold_val, 1, 0).astype(np.uint8)
    return threshold_val, flags

def run_isolation_forest(X: np.ndarray, cfg: Dict, threshold_percentile: float = config.THRESHOLD_PERCENTILE) -> Dict:
    start = time.perf_counter()
    iso = IsolationForest(**{**cfg, **config.IF_FIXED_PARAMS})
    iso.fit(X)
    native_scores = iso.decision_function(X)
    runtime_seconds = time.perf_counter() - start
    threshold_val, flags = apply_percentile_flags(native_scores, threshold_percentile)
    return {"scores": native_scores.astype(np.float32), "flags": flags, "runtime_seconds": runtime_seconds, "threshold_value": threshold_val, "flagged_count": int(flags.sum())}

def run_lof(X: np.ndarray, cfg: Dict, threshold_percentile: float = config.THRESHOLD_PERCENTILE) -> Dict:
    start = time.perf_counter()
    lof = LocalOutlierFactor(**{**cfg, **config.LOF_FIXED_PARAMS})
    lof.fit_predict(X)
    native_scores = lof.negative_outlier_factor_
    runtime_seconds = time.perf_counter() - start
    threshold_val, flags = apply_percentile_flags(native_scores, threshold_percentile)
    return {"scores": native_scores.astype(np.float32), "flags": flags, "runtime_seconds": runtime_seconds, "threshold_value": threshold_val, "flagged_count": int(flags.sum())}

def _if_metadata_row(run_id: str, cfg: Dict, result: Dict) -> Dict:
    return {"run_id": run_id, "model": config.MODEL_NAME_IF, "n_estimators": cfg["n_estimators"], "max_samples": cfg["max_samples"], "random_state": cfg["random_state"], "runtime_seconds": round(result["runtime_seconds"], 2), "threshold_rule": config.THRESHOLD_RULE_LABEL, "flagged_count": result["flagged_count"]}

def _lof_metadata_row(run_id: str, cfg: Dict, result: Dict) -> Dict:
    return {"run_id": run_id, "model": config.MODEL_NAME_LOF, "n_neighbors": cfg["n_neighbors"], "metric": cfg["metric"], "random_state": "N/A", "runtime_seconds": round(result["runtime_seconds"], 2), "threshold_rule": config.THRESHOLD_RULE_LABEL, "flagged_count": result["flagged_count"]}

def _validate_run_compatibility(sample_size: int, if_configs: Sequence[Dict], lof_configs: Sequence[Dict]) -> None:
    max_k = max((c["n_neighbors"] for c in lof_configs), default=0)
    if max_k >= sample_size: raise ValueError("sample_size must exceed largest n_neighbors")
    for c in if_configs:
        ms = c.get("max_samples")
        if isinstance(ms, float) and 0 < ms < 1 and int(ms * sample_size) < 1:
            raise ValueError(f"fractional max_samples yields <1 sample")

def run_phase3_experiment(
    fs_a_path: Optional[Path] = None, output_dir: Optional[Path] = None, sample_size: int = config.SAMPLE_SIZE_DEFAULT,
    sample_seed: int = config.SAMPLE_SEED_DEFAULT, overwrite: bool = False, if_configs: Sequence[Dict] = config.ISOLATION_FOREST_CONFIGS,
    lof_configs: Sequence[Dict] = config.LOF_CONFIGS, verbose: bool = True,
) -> Dict:
    fs_a_path = Path(fs_a_path) if fs_a_path is not None else config.DEFAULT_FS_A_PATH
    output_dir = Path(output_dir) if output_dir is not None else config.DEFAULT_OUTPUT_DIR
    metadata_path = output_dir / config.METADATA_FILENAME
    predictions_path = output_dir / config.PREDICTIONS_FILENAME
    manifest_path = output_dir / config.MANIFEST_FILENAME

    if sample_size != config.SAMPLE_SIZE_DEFAULT or sample_seed != config.SAMPLE_SEED_DEFAULT:
        print("WARNING: non-canonical run parameters")

    _validate_run_compatibility(sample_size, if_configs, lof_configs)
    assert_outputs_writable([metadata_path, predictions_path, manifest_path], overwrite=overwrite)

    if verbose: print(f"Loading feature space from {fs_a_path} ...")
    fs_df = load_feature_matrix(fs_a_path)
    feature_cols = validate_feature_matrix(fs_df)

    n_full_rows = len(fs_df)
    row_ids, X = build_experiment_sample(fs_df, sample_size, sample_seed)
    del fs_df
    gc.collect()

    if verbose: print(f"Population: {n_full_rows:,} rows | sample: {X.shape[0]:,} x {X.shape[1]} features | seed={sample_seed}")

    predictions: Dict[str, Dict] = {}
    run_metadata: List[Dict] = []

    if verbose: print("\n--- ISOLATION FOREST ---")
    for i, cfg in enumerate(if_configs, start=1):
        run_id = f"IF_{i:03d}"
        if verbose: print(f"  Running {run_id} ...", end="", flush=True)
        result = run_isolation_forest(X, cfg)
        predictions[run_id] = {"scores": result["scores"], "flags": result["flags"]}
        run_metadata.append(_if_metadata_row(run_id, cfg, result))
        if verbose: print(f" done in {result['runtime_seconds']:.2f}s")
        gc.collect()

    if verbose: print("\n--- LOCAL OUTLIER FACTOR ---")
    for i, cfg in enumerate(lof_configs, start=1):
        run_id = f"LOF_{i:03d}"
        if verbose: print(f"  Running {run_id} ...", end="", flush=True)
        result = run_lof(X, cfg)
        predictions[run_id] = {"scores": result["scores"], "flags": result["flags"]}
        run_metadata.append(_lof_metadata_row(run_id, cfg, result))
        if verbose: print(f" done in {result['runtime_seconds']:.2f}s")
        gc.collect()

    metadata_df = pd.DataFrame(run_metadata, columns=config.METADATA_COLUMNS)
    bundle = {"row_ids": row_ids, "predictions": predictions}

    if verbose: print("\nSaving artifacts ...")
    publish_phase3_artifacts(metadata_df, bundle, output_dir, overwrite=overwrite)

    if verbose:
        print("\n=== PHASE 3 RUN METADATA ===")
        print(metadata_df.to_string(index=False))
        print("Phase 3 complete.")

    return {"metadata": metadata_df, "bundle": bundle, "paths": {"fs_a": fs_a_path, "metadata": metadata_path, "predictions": predictions_path}, "sample": {"population_rows": n_full_rows, "sample_size": sample_size, "sample_seed": sample_seed, "feature_columns": feature_cols}}

def collect_dry_run_report(
    fs_a_path: Optional[Path] = None, output_dir: Optional[Path] = None, sample_size: int = config.SAMPLE_SIZE_DEFAULT,
    sample_seed: int = config.SAMPLE_SEED_DEFAULT, overwrite: bool = False, if_configs: Sequence[Dict] = config.ISOLATION_FOREST_CONFIGS,
    lof_configs: Sequence[Dict] = config.LOF_CONFIGS,
) -> Dict:
    fs_a_path = Path(fs_a_path) if fs_a_path is not None else config.DEFAULT_FS_A_PATH
    output_dir = Path(output_dir) if output_dir is not None else config.DEFAULT_OUTPUT_DIR
    metadata_path = output_dir / config.METADATA_FILENAME
    predictions_path = output_dir / config.PREDICTIONS_FILENAME

    _validate_run_compatibility(sample_size, if_configs, lof_configs)

    fs_df = load_feature_matrix(fs_a_path)
    feature_cols = validate_feature_matrix(fs_df)

    row_ids_a, X_a = build_experiment_sample(fs_df, sample_size, sample_seed)
    row_ids_b, _ = build_experiment_sample(fs_df, sample_size, sample_seed)

    planned_runs = [{"run_id": f"IF_{i:03d}", "model": config.MODEL_NAME_IF, "params": dict(cfg)} for i, cfg in enumerate(if_configs, start=1)]
    planned_runs += [{"run_id": f"LOF_{i:03d}", "model": config.MODEL_NAME_LOF, "params": dict(cfg)} for i, cfg in enumerate(lof_configs, start=1)]

    return {
        "fs_a_path": fs_a_path, "population_rows": len(fs_df), "feature_columns": feature_cols,
        "sample": {"size": sample_size, "seed": sample_seed, "n_features": int(X_a.shape[1]), "row_ids_head": row_ids_a[:5].tolist(), "row_ids_tail": row_ids_a[-5:].tolist(), "unique": bool(np.unique(row_ids_a).size == sample_size)},
        "sampling_deterministic": bool(np.array_equal(row_ids_a, row_ids_b)), "planned_runs": planned_runs,
        "outputs": {"directory": output_dir, "metadata_path": metadata_path, "predictions_path": predictions_path, "metadata_exists": metadata_path.exists(), "predictions_exists": predictions_path.exists(), "overwrite": bool(overwrite), "blocked": bool((metadata_path.exists() or predictions_path.exists()) and not overwrite)},
    }
