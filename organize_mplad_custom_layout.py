#!/usr/bin/env python3
"""Safely organize known MPLAD/Stream A artifacts into the user's chosen layout.

Run from the repository root (or place this script in the repository root):
    python organize_mplad_custom_layout.py          # dry run; makes no changes
    python organize_mplad_custom_layout.py --apply  # perform unambiguous moves

The script only handles the explicitly listed Stream A / project files below.
It deliberately ignores PMGSY datasets, DVC internals, Git internals, and unknown files.
It never overwrites or automatically deletes a file.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple


# The destinations intentionally preserve the user's directory names, including spaces.
DESTINATIONS: Dict[str, str] = {
    # Raw and processed Stream A data
    "creditcard.csv": "data/raw/creditcard.csv",
    "creditcard_preprocessed.csv": "data/processed/stream-a/creditcard_preprocessed.csv",
    "ULB_FS_A_Baseline.csv": "data/processed/stream-a/features/ULB_FS_A_Baseline.csv",
    "ULB_FS_B_LogAmount.csv": "data/processed/stream-a/features/ULB_FS_B_LogAmount.csv",
    "ground_truth_registry.csv": "data/processed/stream-a/labels/ground_truth_registry.csv",

    # Documentation
    "feature_space_manifest.md": "docs/feature_space_manifest.md",
    "MPLAD_framework_pipeline.md": "docs/MPLAD_framework_pipeline.md",
    "MPLAD_Project_Inference_and_decision.docx": "docs/MPLAD_Project_Inference_and_decision.docx",
    "Phase-0.md": "docs/Phase-0.md",
    "provenance_log.md": "docs/provenance_log.md",

    # Notebooks
    "phase1_verification.ipynb": "notebooks/phase1_verification.ipynb",
    "phase1_verification_PMGSY.ipynb": "notebooks/phase1_verification_PMGSY.ipynb",
    "phase2_trackA.ipynb": "notebooks/phase2_trackA.ipynb",
    "phase2_trackA(revised).ipynb": "notebooks/phase2_trackA(revised).ipynb",
    "phase3_trackA.ipynb": "notebooks/phase3_trackA.ipynb",

    # Phase 3 outputs
    "iforest_execution_summary.csv": "results/stream a/phase 3/iforest_execution_summary.csv",
    "iforest_raw_predictions.pkl": "results/stream a/phase 3/iforest_raw_predictions.pkl",
    "lof_execution_summary.csv": "results/stream a/phase 3/lof_execution_summary.csv",
    "lof_raw_predictions.pkl": "results/stream a/phase 3/lof_raw_predictions.pkl",
    "phase3_canonical_predictions.pkl": "results/stream a/phase 3/phase3_canonical_predictions.pkl",
    "phase3_evaluation_metrics.csv": "results/stream a/phase 3/phase3_evaluation_metrics.csv",
    "phase3_run_metadata.csv": "results/stream a/phase 3/phase3_run_metadata.csv",

    # Phase 4 outputs
    "FULL_phase4_evaluation_dataset.csv": "results/stream a/phase 4/FULL_phase4_evaluation_dataset.csv",
    "FULL_phase4_metrics.csv": "results/stream a/phase 4/FULL_phase4_metrics.csv",
    "phase4_validation_metrics.csv": "results/stream a/phase 4/phase4_validation_metrics.csv",
    "phase4_validation_metrics_CORRECTED.csv": "results/stream a/phase 4/phase4_validation_metrics_CORRECTED.csv",

    # Phase 5 figures: full-data companion
    "FULL_plot1_PR_curves.png": "results/stream a/phase 5/FULL_plot1_PR_curves.png",
    "FULL_plot2_fraud_discovery.png": "results/stream a/phase 5/FULL_plot2_fraud_discovery.png",
    "FULL_plot3_hypergeom.png": "results/stream a/phase 5/FULL_plot3_hypergeom.png",
    "FULL_plot4_spearman_matrix.png": "results/stream a/phase 5/FULL_plot4_spearman_matrix.png",
    "FULL_plot5_jaccard_matrix.png": "results/stream a/phase 5/FULL_plot5_jaccard_matrix.png",
    "FULL_plot6_rank_vs_rank.png": "results/stream a/phase 5/FULL_plot6_rank_vs_rank.png",
    "FULL_plot7_pca_agreement.png": "results/stream a/phase 5/FULL_plot7_pca_agreement.png",

    # Phase 5 figures: primary 30k experiment
    "phase5_plot1_PR_curves.png": "results/stream a/phase 5/phase5_plot1_PR_curves.png",
    "phase5_plot1_rank_vs_rank.png": "results/stream a/phase 5/phase5_plot1_rank_vs_rank.png",
    "phase5_plot2_fraud_discovery.png": "results/stream a/phase 5/phase5_plot2_fraud_discovery.png",
    "phase5_plot2_fraud_discovery_precision.png": "results/stream a/phase 5/phase5_plot2_fraud_discovery_precision.png",
    "phase5_plot2_pca_agreement.png": "results/stream a/phase 5/phase5_plot2_pca_agreement.png",
    "phase5_plot3_ECDF.png": "results/stream a/phase 5/phase5_plot3_ECDF.png",
    "phase5_plot3_hypergeom.png": "results/stream a/phase 5/phase5_plot3_hypergeom.png",
    "phase5_plot3_jaccard_curve.png": "results/stream a/phase 5/phase5_plot3_jaccard_curve.png",
    "phase5_plot4_pca_fraud_overlay.png": "results/stream a/phase 5/phase5_plot4_pca_fraud_overlay.png",
    "phase5_plot4_rank_vs_rank.png": "results/stream a/phase 5/phase5_plot4_rank_vs_rank.png",
    "phase5_plot4_spearman_matrix.png": "results/stream a/phase 5/phase5_plot4_spearman_matrix.png",
    "phase5_plot5_enrichment_lift.png": "results/stream a/phase 5/phase5_plot5_enrichment_lift.png",
    "phase5_plot5_jaccard_matrix.png": "results/stream a/phase 5/phase5_plot5_jaccard_matrix.png",
    "phase5_plot6_corr_matrix.png": "results/stream a/phase 5/phase5_plot6_corr_matrix.png",
    "phase5_plot6_topk_jaccard.png": "results/stream a/phase 5/phase5_plot6_topk_jaccard.png",
    "phase5_plot7_lof_sensitivity.png": "results/stream a/phase 5/phase5_plot7_lof_sensitivity.png",
    "phase5_plot7_pca_agreement.png": "results/stream a/phase 5/phase5_plot7_pca_agreement.png",
    "phase5_plot8_pca_agreement.png": "results/stream a/phase 5/phase5_plot8_pca_agreement.png",
    "phase5_plot8_rank_vs_rank.png": "results/stream a/phase 5/phase5_plot8_rank_vs_rank.png",

    # Phase 6 outputs
    "phase6_group_assignments.csv": "results/stream a/phase 6/phase6_group_assignments.csv",
}

# Avoid scanning generated/cache areas and unrelated PMGSY data.
EXCLUDED_DIRS = {
    ".git", ".dvc", ".venv", "venv", "env", "__pycache__",
    "node_modules", ".pytest_cache", ".mypy_cache", ".tox",
}
EXCLUDED_TOP_LEVEL = {"data/raw"}  # raw source data is already in its intended location


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def walk_project(root: Path):
    """Yield files without traversing caches, Git/DVC internals, or symlink dirs."""
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        rel_current = current_path.relative_to(root).as_posix()

        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not (current_path / d).is_symlink()]
        if rel_current in EXCLUDED_TOP_LEVEL:
            dirs[:] = []
            continue

        for filename in files:
            candidate = current_path / filename
            if candidate.is_file() and not candidate.is_symlink():
                yield candidate


def classify(root: Path):
    by_name: Dict[str, List[Path]] = {name: [] for name in DESTINATIONS}
    for path in walk_project(root):
        if path.name in by_name:
            by_name[path.name].append(path)
    return by_name


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely organize known project files into the user's custom MPLAD layout."
    )
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent,
        help="Repository root (default: directory containing this script)."
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Perform unambiguous moves. Without this option, only show a dry run."
    )
    args = parser.parse_args()
    root = args.root.expanduser().resolve()

    if not root.is_dir():
        print(f"ERROR: repository root does not exist: {root}", file=sys.stderr)
        return 2

    # Basic sanity check: do not accidentally run against a parent directory.
    if not (root / ".git").exists() and not (root / "README.md").exists():
        print("ERROR: this does not look like the project root (.git or README.md not found).", file=sys.stderr)
        print("Use --root PATH to specify the correct repository directory.", file=sys.stderr)
        return 2

    inventory = classify(root)
    moved = 0
    already_correct = 0
    missing = 0
    duplicates = 0
    conflicts = 0

    mode = "APPLY MODE" if args.apply else "DRY RUN (no files will be changed)"
    print(f"\n{mode}\nRepository: {root}\n")

    for filename, relative_destination in DESTINATIONS.items():
        destination = root / Path(relative_destination)
        candidates = sorted(inventory[filename], key=lambda p: p.as_posix().lower())

        # If the canonical path already exists, it is authoritative for placement.
        if destination.exists():
            already_correct += 1
            print(f"[OK]      {relative_destination}")
            extras = [p for p in candidates if p.resolve() != destination.resolve()]
            for extra in extras:
                duplicates += 1
                try:
                    identical = sha256(extra) == sha256(destination)
                except OSError:
                    identical = False
                status = "identical content" if identical else "DIFFERENT CONTENT"
                print(f"[REVIEW]  duplicate elsewhere ({status}); left untouched: {extra.relative_to(root)}")
            continue

        if not candidates:
            missing += 1
            print(f"[MISSING] {relative_destination}")
            continue

        if len(candidates) > 1:
            duplicates += 1
            print(f"[AMBIGUOUS] Multiple possible sources for {relative_destination}; no move made:")
            for candidate in candidates:
                print(f"           - {candidate.relative_to(root)}")
            continue

        source = candidates[0]
        if source.resolve() == destination.resolve():
            already_correct += 1
            print(f"[OK]      {relative_destination}")
            continue

        if destination.exists():  # defensive; destination check above should catch this
            conflicts += 1
            print(f"[CONFLICT] Destination already exists; left untouched: {relative_destination}")
            continue

        print(f"[MOVE]    {source.relative_to(root)}  ->  {relative_destination}")
        if args.apply:
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                # Re-check immediately before moving; never overwrite.
                if destination.exists():
                    conflicts += 1
                    print("          SKIPPED: destination appeared during execution.")
                    continue
                shutil.move(str(source), str(destination))
                moved += 1
            except OSError as exc:
                conflicts += 1
                print(f"          ERROR: {exc}")

    print("\n--- Summary ---")
    print(f"Already in target location: {already_correct}")
    print(f"Moved:                     {moved}")
    print(f"Missing from inventory:    {missing}")
    print(f"Duplicates/ambiguities:    {duplicates}")
    print(f"Move conflicts/errors:     {conflicts}")

    # Specific warning from the supplied tree: the DVC pointer is at the parent
    # processed directory while its working CSV is nested under stream-a.
    dvc_pointer = root / "data/processed/creditcard_preprocessed.csv.dvc"
    processed_root_csv = root / "data/processed/creditcard_preprocessed.csv"
    processed_stream_csv = root / "data/processed/stream-a/creditcard_preprocessed.csv"
    if dvc_pointer.exists() and processed_stream_csv.exists() and not processed_root_csv.exists():
        print("\n[IMPORTANT DVC CHECK]")
        print("Found data/processed/creditcard_preprocessed.csv.dvc but the CSV is nested at")
        print("data/processed/stream-a/creditcard_preprocessed.csv.")
        print("This may be a DVC path mismatch. The script has NOT moved or edited the .dvc file.")
        print("Inspect the .dvc file's 'path' entry and run `dvc status` from the repository root.")

    stray_notebook_summary = root / "notebooks/iforest_execution_summary.csv"
    canonical_summary = root / "results/stream a/phase 3/iforest_execution_summary.csv"
    if stray_notebook_summary.exists() and canonical_summary.exists():
        try:
            identical = sha256(stray_notebook_summary) == sha256(canonical_summary)
        except OSError:
            identical = False
        print("\n[NOTEBOOK DUPLICATE CHECK]")
        print("Both notebooks/iforest_execution_summary.csv and the Phase 3 result file exist.")
        print("Content is " + ("identical." if identical else "DIFFERENT; investigate before choosing one."))
        print("Neither copy was deleted or overwritten by this script.")

    if not args.apply:
        print("\nNo changes made. Review the plan, then rerun with --apply to move unambiguous files.")
    else:
        print("\nMove pass complete. Review the summary and run `git status --short` and `dvc status`.")
    return 0 if conflicts == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
