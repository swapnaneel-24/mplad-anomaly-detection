#!/usr/bin/env python3
"""Command-line runner for the Stream A Phase 4 evaluation layer.

Default invocation is a VALIDATION-ONLY PREFLIGHT: it verifies the optional
Phase 3 manifest, loads and validates the ground-truth registry, the Phase 3
run metadata and the prediction bundle, and performs the row_id alignment.
No metric is calculated and no file is written. Evaluation and output
writing only happen with the explicit ``--execute`` flag.

Phase 4 NEVER fits a model: it evaluates the saved Phase 3 scores and flags
against the ground truth. The historical Phase 4 outputs are never touched;
by default results go to ``results/stream a/phase 4/reproduction/``.

Usage (from the repository root; Windows PowerShell or Linux):

    python scripts/run_phase4.py                                  # preflight
    python scripts/run_phase4.py --execute                        # evaluate + write
    python scripts/run_phase4.py --execute --overwrite            # replace outputs
    python scripts/run_phase4.py --execute \
        --output-dir "results/stream a/phase 4/reproduction_v2"   # redirect outputs
    python scripts/run_phase4.py --execute \
        --reference-metrics "results/stream a/phase 4/phase4_metrics_corrected.csv"

Optional input overrides (defaults are the frozen canonical artifacts):

    --predictions    "results/stream a/phase 3/phase3_canonical_predictions.pkl"
    --run-metadata   "results/stream a/phase 3/phase3_run_metadata.csv"
    --ground-truth   "data/processed/stream-a/labels/ground_truth_registry.csv"
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
from mplad.common.manifest import ManifestError                   # noqa: E402
from mplad.stream_a import phase4                                 # noqa: E402


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_phase4.py",
        description=(
            "Stream A Phase 4: label-based evaluation of the frozen Phase 3 "
            "predictions (no model is ever fitted or refitted)."
        ),
    )
    p.add_argument(
        "--predictions", type=Path, default=None, metavar="PKL",
        help=f"Phase 3 canonical prediction bundle (default: {config.PHASE3_PREDICTIONS_PATH})",
    )
    p.add_argument(
        "--run-metadata", type=Path, default=None, metavar="CSV",
        help=f"Phase 3 run metadata CSV (default: {config.PHASE3_RUN_METADATA_PATH})",
    )
    p.add_argument(
        "--ground-truth", type=Path, default=None, metavar="CSV",
        help=f"Ground-truth registry CSV, schema 'row_id, Class' "
             f"(default: {config.DEFAULT_GROUND_TRUTH_PATH})",
    )
    p.add_argument(
        "--output-dir", type=Path, default=None, metavar="DIR",
        help=f"Output directory (default: {config.DEFAULT_PHASE4_OUTPUT_DIR})",
    )
    p.add_argument(
        "--execute", action="store_true",
        help="Calculate the metrics and write the outputs. Without this flag "
             "the runner only validates the inputs (preflight).",
    )
    p.add_argument(
        "--overwrite", action="store_true",
        help="Allow replacing existing output files. Refused by default.",
    )
    p.add_argument(
        "--allow-noncanonical-sample-size", action="store_true",
        help="Allow non-30,000 sample sizes (for synthetic testing).",
    )
    p.add_argument(
        "--reference-metrics", type=Path, default=None, metavar="CSV",
        help="Optional reference metrics CSV (needs a 'run_id' column) used "
             "ONLY for a post-hoc acceptance comparison after independent "
             "recalculation. It never influences the calculation.",
    )
    return p


def print_preflight_report(report: dict) -> None:
    print("=== INPUTS ===")
    print(f"predictions        : {report['predictions_path']}")
    print(f"run metadata       : {report['run_metadata_path']}")
    print(f"ground truth       : {report['ground_truth_path']}")
    print()
    print("=== PHASE 3 INTEGRITY MANIFEST ===")
    m = report["input_manifest"]
    if m["mode"] == "manifest_verified":
        print(f"status             : PRESENT and VERIFIED ({m['path']})")
        for name, info in m["artifacts"].items():
            print(f"  {name:<40} sha256 OK ({info['size_bytes']:,} bytes)")
    else:
        print(f"status             : ABSENT -> legacy unmanifested pair")
        print(f"looked at          : {m['path']}")
        print(
            "handling           : strict structural validation + SHA-256 "
            "recording in the provenance record;"
        )
        print(
            "                     manifest verification is NOT claimed for "
            "legacy inputs"
        )
    print()
    print("=== GROUND TRUTH REGISTRY ===")
    r = report["registry_summary"]
    print(f"total observations : {r['total_observations']:,}")
    print(f"positive labels    : {r['positive_labels']:,}")
    print()
    print("=== PHASE 3 EXPERIMENT (validated) ===")
    print(f"runs               : {len(report['run_ids'])} ({report['run_ids'][0]} ... {report['run_ids'][-1]})")
    s = report["sample"]
    print(f"sample size        : {s['sample_size']:,}")
    print(f"fraud labels       : {s['fraud_count']} (prevalence {s['fraud_prevalence']:.6f})")
    a = report["alignment"]
    print(f"alignment          : row_id join, {a['join_validation']}, "
          f"prediction order preserved, unmatched IDs rejected")
    print()
    print("=== PLANNED METRICS (nothing is calculated in preflight mode) ===")
    print("ranking            : " + ", ".join(report["metrics_planned"][:2])
          + "  (on anomaly_score = -native_score)")
    print("fixed-threshold    : " + ", ".join(report["metrics_planned"][2:9])
          + "  (on the SAVED Phase 3 flags)")
    print("bookkeeping        : " + ", ".join(report["metrics_planned"][9:]))
    print()
    print("=== OUTPUTS ===")
    o = report["outputs"]
    print(f"directory          : {o['directory']}")
    for key, path in o["paths"].items():
        print(f"{key:<18} : {path}  [{'EXISTS' if o['exists'][key] else 'new'}]")
    if o["blocked"]:
        print("STATUS             : BLOCKED -- output file(s) already exist. Use "
              "--overwrite to replace them, or --output-dir to redirect.")


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    print("MPLAD -- Stream A -- Phase 4 runner (evaluation layer)")
    print(f"mode        : "
          f"{'EXECUTE (metrics calculated, outputs written)' if args.execute else 'PREFLIGHT (validation only, nothing calculated or written)'}")
    print(f"predictions : {args.predictions or config.PHASE3_PREDICTIONS_PATH}")
    print(f"ground truth: {args.ground_truth or config.DEFAULT_GROUND_TRUTH_PATH}")
    print(f"output dir  : {args.output_dir or config.DEFAULT_PHASE4_OUTPUT_DIR}")
    print(f"overwrite   : {args.overwrite}")
    if args.reference_metrics:
        print(f"reference   : {args.reference_metrics} (post-hoc comparison only)")
    print()

    try:
        if not args.execute:
            report = phase4.collect_phase4_preflight(
                predictions_path=args.predictions,
                run_metadata_path=args.run_metadata,
                ground_truth_path=args.ground_truth,
                output_dir=args.output_dir,
                overwrite=args.overwrite,
                require_canonical_sample_size=not args.allow_noncanonical_sample_size,
            )
            print_preflight_report(report)
            if report["outputs"]["blocked"]:
                print("\nPreflight complete, but the run is BLOCKED by existing "
                      "outputs (see above).")
            print("\nPREFLIGHT complete: no metric was calculated, no file was "
                  "written, no model was fitted.")
            print("Re-run with --execute to perform the evaluation.")
            return 0

        result = phase4.run_phase4_evaluation(
            predictions_path=args.predictions,
            run_metadata_path=args.run_metadata,
            ground_truth_path=args.ground_truth,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
            reference_metrics_path=args.reference_metrics,
            verbose=True,
            require_canonical_sample_size=not args.allow_noncanonical_sample_size,
        )
        if result["reference_comparison"] is not None:
            print("\n=== REFERENCE COMPARISON (post-hoc acceptance check) ===")
            print(result["reference_comparison"].to_string(index=False))
        print("\nExecution finished. Artifacts:")
        for key in ("evaluation_dataset", "metrics", "run_metadata", "manifest"):
            print(f"  {key:<18}: {result['paths'][key]}")
        print("Record this run in docs/provenance_log.md. Phase 5 consumes the "
              "evaluation dataset and metrics table.")
        return 0

    except (
        FileNotFoundError,
        OutputExistsError,
        ManifestError,
        phase4.Phase4Error,
        ValueError,
    ) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
