#!/usr/bin/env python3
"""Command-line runner for the Stream A Phase 3 primary experiment.

Default invocation is a VALIDATION-ONLY DRY RUN: it loads and validates the
FS-A matrix, draws the reproducible 30k sample (twice, to prove determinism)
and prints the planned model runs. Nothing is fitted and nothing is written.
Model fitting only happens with the explicit ``--execute`` flag.

The larger "novelty mode" experiment is intentionally NOT implemented here;
it will get its own explicitly named runner after its artifacts and exact
dataset size have been inspected and confirmed.

Usage (from the repository root; Windows PowerShell or Linux):

    python scripts/run_phase3.py                                  # dry run
    python scripts/run_phase3.py --execute                        # canonical run
    python scripts/run_phase3.py --execute --overwrite            # replace outputs
    python scripts/run_phase3.py --execute \
        --output-dir "results/stream a/phase 3/reproduction"      # redirect outputs

Historical context: the Colab original wrote to
/content/drive/MyDrive/mplad-dvc-storage ; Google Drive is NOT a dependency
of this runner.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make src/ importable without installing the package (works from any CWD,
# Windows and Linux alike).
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from mplad.common import config                                   # noqa: E402
from mplad.common.io import OutputExistsError                     # noqa: E402
from mplad.common.validation import FeatureMatrixError            # noqa: E402
from mplad.stream_a import phase3                                 # noqa: E402


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_phase3.py",
        description=(
            "Stream A Phase 3: strict-unsupervised IF/LOF on the reproducible "
            "30k FS-A sample."
        ),
    )
    p.add_argument(
        "--fs-a", type=Path, default=None, metavar="CSV",
        help=f"FS-A feature matrix CSV (default: {config.DEFAULT_FS_A_PATH})",
    )
    p.add_argument(
        "--output-dir", type=Path, default=None, metavar="DIR",
        help=f"Output directory (default: {config.DEFAULT_OUTPUT_DIR})",
    )
    p.add_argument(
        "--sample-size", type=int, default=config.SAMPLE_SIZE_DEFAULT, metavar="N",
        help="Rows in the experiment sample (default: %(default)s). "
             "Changing this deviates from the established experiment.",
    )
    p.add_argument(
        "--sample-seed", type=int, default=config.SAMPLE_SEED_DEFAULT, metavar="SEED",
        help="Seed of the subsample draw ONLY -- the 'np.random.seed(42)' line of "
             "the original cell. IsolationForest random_state values (42/43/44) are "
             "frozen in the config grid and are NOT affected. (default: %(default)s)",
    )
    p.add_argument(
        "--execute", action="store_true",
        help="Actually fit the ten models and write artifacts. Without this flag "
             "the runner only validates inputs (dry run).",
    )
    p.add_argument(
        "--overwrite", action="store_true",
        help="Allow replacing existing output files. Refused by default.",
    )
    return p


def print_dry_run_report(report: dict) -> None:
    print("=== INPUT ===")
    print(f"FS-A path          : {report['fs_a_path']}")
    print(f"population rows    : {report['population_rows']:,}")
    feats = report["feature_columns"]
    print(f"feature columns    : {len(feats)} ({feats[0]} ... {feats[-1]})")
    print("label leakage      : none ('Class' is hard-rejected by validation)")
    print()
    print("=== SAMPLE ===")
    s = report["sample"]
    print(f"size / seed        : {s['size']:,} / {s['seed']}")
    print(f"unique row_ids     : {s['unique']}")
    det = "PASSED (two independent draws identical)" if report["sampling_deterministic"] else "FAILED"
    print(f"determinism        : {det}")
    print(f"row_ids head       : {s['row_ids_head']}")
    print(f"row_ids tail       : {s['row_ids_tail']}")
    print()
    print("=== PLANNED RUNS (nothing is fitted in dry-run mode) ===")
    for r in report["planned_runs"]:
        print(f"  {r['run_id']}  {r['model']:<16} {r['params']}")
    print(f"flagging rule      : {config.THRESHOLD_RULE_LABEL} "
          f"(native scores; lower = more anomalous)")
    print(f"expected flags     : ~{int(s['size'] * config.THRESHOLD_PERCENTILE / 100)} per run")
    print()
    print("=== OUTPUTS ===")
    o = report["outputs"]
    print(f"directory          : {o['directory']}")
    print(f"metadata CSV       : {o['metadata_path']}  "
          f"[{'EXISTS' if o['metadata_exists'] else 'new'}]")
    print(f"predictions pickle : {o['predictions_path']}  "
          f"[{'EXISTS' if o['predictions_exists'] else 'new'}]")
    if o["blocked"]:
        print("STATUS             : BLOCKED -- output file(s) already exist. Use "
              "--overwrite to replace them, or --output-dir to redirect.")


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    print("MPLAD -- Stream A -- Phase 3 runner")
    print(f"mode        : "
          f"{'EXECUTE (models will be fitted)' if args.execute else 'DRY RUN (validation only, nothing is fitted)'}")
    print(f"fs-a        : {args.fs_a or config.DEFAULT_FS_A_PATH}")
    print(f"output dir  : {args.output_dir or config.DEFAULT_OUTPUT_DIR}")
    print(f"sample      : size={args.sample_size}, seed={args.sample_seed}")
    print(f"overwrite   : {args.overwrite}")
    print()

    try:
        if not args.execute:
            report = phase3.collect_dry_run_report(
                fs_a_path=args.fs_a,
                output_dir=args.output_dir,
                sample_size=args.sample_size,
                sample_seed=args.sample_seed,
                overwrite=args.overwrite,
            )
            print_dry_run_report(report)
            if not report["sampling_deterministic"]:
                print("\nERROR: sampling determinism check FAILED -- aborting.",
                      file=sys.stderr)
                return 1
            print("\nDRY RUN complete: no model was fitted, no file was written.")
            print("Re-run with --execute to perform the experiment.")
            return 0

        result = phase3.run_phase3_experiment(
            fs_a_path=args.fs_a,
            output_dir=args.output_dir,
            sample_size=args.sample_size,
            sample_seed=args.sample_seed,
            overwrite=args.overwrite,
            verbose=True,
        )
        print("\nExecution finished. Artifacts:")
        print(f"  metadata   : {result['paths']['metadata']}")
        print(f"  predictions: {result['paths']['predictions']}")
        print("The Phase 4 consumer reads these files; record this run in "
              "docs/provenance_log.md.")
        return 0

    except (FileNotFoundError, OutputExistsError, FeatureMatrixError, ValueError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
