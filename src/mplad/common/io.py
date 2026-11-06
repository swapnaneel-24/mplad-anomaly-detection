"""Artifact I/O with explicit overwrite protection and transactional staging."""
from __future__ import annotations

import hashlib
import json
import pickle
import shutil
from pathlib import Path
from typing import Dict, Iterable, Union

import pandas as pd

from mplad.common import config as _config

PathLike = Union[str, Path]


class OutputExistsError(FileExistsError):
    """An output file already exists and overwrite was not requested."""


def load_feature_matrix(path: PathLike) -> pd.DataFrame:
    """Load a feature-matrix CSV, failing clearly when it is absent."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f"Feature matrix not found: {path}\n"
            "Expected the frozen Phase 2 output (FS-A). Pass --fs-a / fs_a_path "
            "if it lives somewhere else."
        )
    return pd.read_csv(path)


def assert_outputs_writable(output_paths: Iterable[PathLike], overwrite: bool = False) -> None:
    """Raise OutputExistsError (listing every conflict) if any output exists."""
    conflicts = [Path(p) for p in output_paths if Path(p).exists()]
    if conflicts and not overwrite:
        listing = "\n  ".join(str(c) for c in conflicts)
        raise OutputExistsError(
            "Output file(s) already exist:\n  " + listing
            + "\nRefusing to overwrite. Pass --overwrite (overwrite=True) to "
            "replace them, or choose another output directory."
        )


def _write_guard(path: PathLike, overwrite: bool) -> Path:
    path = Path(path)
    if path.exists() and not overwrite:
        raise OutputExistsError(
            f"Output file already exists: {path}\nRefusing to overwrite "
            "(pass overwrite=True / --overwrite to replace it)."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_predictions_pickle(path: PathLike) -> dict:
    """Load a canonical prediction bundle (used by verification tooling)."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Prediction bundle not found: {path}")
    with open(path, "rb") as f:
        return pickle.load(f)


def save_dataframe_csv(df: pd.DataFrame, path: PathLike, overwrite: bool = False) -> None:
    """Save any DataFrame to CSV (index=False) with overwrite protection."""
    path = _write_guard(path, overwrite)
    df.to_csv(path, index=False)


def save_json(payload: dict, path: PathLike, overwrite: bool = False) -> None:
    """Save a JSON-serialisable payload with overwrite protection."""
    path = _write_guard(path, overwrite)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def compute_sha256(path: PathLike) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def publish_phase3_artifacts(
    metadata_df: pd.DataFrame, bundle: dict, output_dir: PathLike, overwrite: bool = False
) -> None:
    """Write Phase 3 artifacts atomically using a staging & rollback strategy."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    meta_path = output_dir / _config.METADATA_FILENAME
    pred_path = output_dir / _config.PREDICTIONS_FILENAME
    manifest_path = output_dir / _config.MANIFEST_FILENAME

    assert_outputs_writable([meta_path, pred_path, manifest_path], overwrite=overwrite)

    stage_meta = meta_path.with_suffix(".csv.stage")
    stage_pred = pred_path.with_suffix(".pkl.stage")

    try:
        metadata_df.to_csv(stage_meta, index=False)
        with open(stage_pred, "wb") as f:
            pickle.dump(bundle, f, protocol=pickle.HIGHEST_PROTOCOL)

        pd.read_csv(stage_meta)
        with open(stage_pred, "rb") as f:
            pickle.load(f)

        meta_hash = compute_sha256(stage_meta)
        pred_hash = compute_sha256(stage_pred)

        bak_meta = meta_path.with_suffix(".csv.bak") if meta_path.exists() else None
        bak_pred = pred_path.with_suffix(".pkl.bak") if pred_path.exists() else None
        bak_man = manifest_path.with_suffix(".json.bak") if manifest_path.exists() else None

        if bak_meta:
            shutil.copy2(meta_path, bak_meta)
        if bak_pred:
            shutil.copy2(pred_path, bak_pred)
        if bak_man:
            shutil.copy2(manifest_path, bak_man)

        try:
            shutil.move(str(stage_meta), str(meta_path))
            shutil.move(str(stage_pred), str(pred_path))

            manifest = {
                "purpose": "Provides checksums for downstream verification of the artifact pair.",
                "artifacts": {
                    _config.METADATA_FILENAME: meta_hash,
                    _config.PREDICTIONS_FILENAME: pred_hash,
                },
            }
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)

        except Exception as commit_err:
            if bak_meta and bak_meta.exists():
                shutil.move(str(bak_meta), str(meta_path))
            elif meta_path.exists():
                meta_path.unlink()

            if bak_pred and bak_pred.exists():
                shutil.move(str(bak_pred), str(pred_path))
            elif pred_path.exists():
                pred_path.unlink()

            if bak_man and bak_man.exists():
                shutil.move(str(bak_man), str(manifest_path))
            elif manifest_path.exists():
                manifest_path.unlink()

            raise RuntimeError(
                f"Artifact publication failed and was rolled back: {commit_err}"
            ) from commit_err

        finally:
            if bak_meta and bak_meta.exists():
                bak_meta.unlink()
            if bak_pred and bak_pred.exists():
                bak_pred.unlink()
            if bak_man and bak_man.exists():
                bak_man.unlink()

    finally:
        if stage_meta.exists():
            stage_meta.unlink()
        if stage_pred.exists():
            stage_pred.unlink()


def publish_phase4_artifacts(
    evaluation_dataset: pd.DataFrame,
    metrics_df: pd.DataFrame,
    provenance: Dict,
    output_dir: PathLike,
    overwrite: bool = False,
) -> Dict:
    """Stage, validate, hash, and transactionally publish all 4 Phase 4 outputs.

    The commit manifest is published LAST after the staged evaluation dataset,
    metrics table, and run-metadata JSON have been reopened, validated, and
    moved into place. If any step fails, any partially written files are
    removed and any previous valid output set is restored from .bak backups.
    """
    from mplad.common.manifest import build_manifest, load_manifest, verify_manifest

    output_dir = Path(output_dir)
    eval_path = output_dir / _config.PHASE4_EVALUATION_DATASET_FILENAME
    metrics_path = output_dir / _config.PHASE4_METRICS_FILENAME
    meta_path = output_dir / _config.PHASE4_RUN_METADATA_FILENAME
    manifest_path = output_dir / _config.PHASE4_MANIFEST_FILENAME

    targets = [eval_path, metrics_path, meta_path, manifest_path]
    assert_outputs_writable(targets, overwrite=overwrite)
    output_dir.mkdir(parents=True, exist_ok=True)

    stage_eval = eval_path.with_suffix(".csv.stage")
    stage_metrics = metrics_path.with_suffix(".csv.stage")
    stage_meta = meta_path.with_suffix(".json.stage")
    stage_manifest = manifest_path.with_suffix(".json.stage")
    stages = [stage_eval, stage_metrics, stage_meta, stage_manifest]

    try:
        # 1. Write data and metadata to staging files
        evaluation_dataset.to_csv(stage_eval, index=False)
        metrics_df.to_csv(stage_metrics, index=False)
        with open(stage_meta, "w", encoding="utf-8") as f:
            json.dump(provenance, f, indent=2, sort_keys=True)
            f.write("\n")

        # 2. Reopen and validate staged data files
        check_eval = pd.read_csv(stage_eval)
        if len(check_eval) != len(evaluation_dataset) or list(check_eval.columns) != list(evaluation_dataset.columns):
            raise RuntimeError("Staged evaluation dataset failed read-back validation.")
        check_metrics = pd.read_csv(stage_metrics)
        if len(check_metrics) != len(metrics_df) or list(check_metrics.columns) != list(metrics_df.columns):
            raise RuntimeError("Staged metrics CSV failed read-back validation.")
        with open(stage_meta, "r", encoding="utf-8") as f:
            json.load(f)

        # 3. Build and validate staged manifest from the staged artifacts
        manifest_payload = build_manifest(
            {
                _config.PHASE4_EVALUATION_DATASET_FILENAME: stage_eval,
                _config.PHASE4_METRICS_FILENAME: stage_metrics,
                _config.PHASE4_RUN_METADATA_FILENAME: stage_meta,
            }
        )
        with open(stage_manifest, "w", encoding="utf-8") as f:
            json.dump(manifest_payload, f, indent=2, sort_keys=True)
            f.write("\n")
        load_manifest(stage_manifest)

        # 4. Back up existing files if overwriting
        backups = {}
        for t in targets:
            if t.exists():
                bak = t.with_name(t.name + ".bak")
                shutil.copy2(t, bak)
                backups[t] = bak

        # 5. Commit staged files (manifest written/moved LAST)
        try:
            shutil.move(str(stage_eval), str(eval_path))
            shutil.move(str(stage_metrics), str(metrics_path))
            shutil.move(str(stage_meta), str(meta_path))
            shutil.move(str(stage_manifest), str(manifest_path))

            verify_manifest(
                load_manifest(manifest_path),
                base_dir=output_dir,
                required_artifacts=(
                    _config.PHASE4_EVALUATION_DATASET_FILENAME,
                    _config.PHASE4_METRICS_FILENAME,
                    _config.PHASE4_RUN_METADATA_FILENAME,
                ),
            )
        except Exception as commit_err:
            for t in targets:
                if t in backups and backups[t].exists():
                    shutil.move(str(backups[t]), str(t))
                elif t.exists():
                    t.unlink()
            raise RuntimeError(
                f"Phase 4 artifact publication failed and was rolled back: {commit_err}"
            ) from commit_err
        finally:
            for bak in backups.values():
                if bak.exists():
                    bak.unlink()

        return manifest_payload

    finally:
        for s in stages:
            if s.exists():
                s.unlink()

def publish_phase5_artifacts(
    bootstrap_metrics: pd.DataFrame,
    paired_differences: pd.DataFrame,
    spearman_df: pd.DataFrame,
    jaccard_df: pd.DataFrame,
    agreement_table: pd.DataFrame,
    hypergeometric_df: pd.DataFrame,
    agreement_groups_df: pd.DataFrame,
    discovery_curve_df: pd.DataFrame,
    provenance: dict,
    output_dir: PathLike,
    overwrite: bool = False,
) -> dict:
    """Stage, validate, hash, and transactionally publish all 10 Phase 5A outputs."""
    from mplad.common.manifest import build_manifest, load_manifest, verify_manifest
    import shutil

    output_dir = Path(output_dir)
    targets = {
        _config.PHASE5_BOOTSTRAP_METRICS_FILENAME: bootstrap_metrics,
        _config.PHASE5_PAIRED_BOOTSTRAP_DIFFERENCES_FILENAME: paired_differences,
        _config.PHASE5_PAIRWISE_SPEARMAN_FILENAME: spearman_df,
        _config.PHASE5_PAIRWISE_JACCARD_FILENAME: jaccard_df,
        _config.PHASE5_MULTITHRESHOLD_AGREEMENT_FILENAME: agreement_table,
        _config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME: hypergeometric_df,
        _config.PHASE5_AGREEMENT_GROUPS_FILENAME: agreement_groups_df,
        _config.PHASE5_FRAUD_DISCOVERY_CURVE_FILENAME: discovery_curve_df,
    }
    
    meta_path = output_dir / _config.PHASE5_RUN_METADATA_FILENAME
    manifest_path = output_dir / _config.PHASE5_MANIFEST_FILENAME
    target_paths = [output_dir / name for name in targets]
    all_paths = target_paths + [meta_path, manifest_path]

    assert_outputs_writable(all_paths, overwrite=overwrite)
    output_dir.mkdir(parents=True, exist_ok=True)

    stage_dict = {p.name: p.with_suffix(p.suffix + ".stage") for p in all_paths}
    stages = list(stage_dict.values())

    try:
        # 1. Write data and metadata to staging files
        for name, df in targets.items():
            df.to_csv(stage_dict[name], index=False)
        with open(stage_dict[_config.PHASE5_RUN_METADATA_FILENAME], "w", encoding="utf-8") as f:
            json.dump(provenance, f, indent=2, sort_keys=True)
            f.write("\n")

        # 2. Reopen and validate staged data files
        for name, df in targets.items():
            check = pd.read_csv(stage_dict[name])
            if len(check) != len(df) or list(check.columns) != list(df.columns):
                raise RuntimeError(f"Staged {name} failed read-back validation.")
        with open(stage_dict[_config.PHASE5_RUN_METADATA_FILENAME], "r", encoding="utf-8") as f:
            json.load(f)

        # 3. Build and validate staged manifest from the staged artifacts
        manifest_targets = {
            name: stage_dict[name] for name in targets
        }
        manifest_targets[_config.PHASE5_RUN_METADATA_FILENAME] = stage_dict[_config.PHASE5_RUN_METADATA_FILENAME]
        
        manifest_payload = build_manifest(manifest_targets)
        with open(stage_dict[_config.PHASE5_MANIFEST_FILENAME], "w", encoding="utf-8") as f:
            json.dump(manifest_payload, f, indent=2, sort_keys=True)
            f.write("\n")
        load_manifest(stage_dict[_config.PHASE5_MANIFEST_FILENAME])

        # 4. Back up existing files if overwriting
        backups = {}
        for t in all_paths:
            if t.exists():
                bak = t.with_name(t.name + ".bak")
                shutil.copy2(t, bak)
                backups[t] = bak

        # 5. Commit staged files (manifest written/moved LAST)
        try:
            for t in all_paths:
                shutil.move(str(stage_dict[t.name]), str(t))

            verify_manifest(
                load_manifest(manifest_path),
                base_dir=output_dir,
                required_artifacts=tuple(targets.keys()) + (_config.PHASE5_RUN_METADATA_FILENAME,),
            )
        except Exception as commit_err:
            for t in all_paths:
                if t in backups and backups[t].exists():
                    shutil.move(str(backups[t]), str(t))
                elif t.exists():
                    t.unlink()
            raise RuntimeError(
                f"Phase 5A artifact publication failed and was rolled back: {commit_err}"
            ) from commit_err
        finally:
            for bak in backups.values():
                if bak.exists():
                    bak.unlink()
        return manifest_payload

    finally:
        for s in stages:
            if s.exists():
                s.unlink()
