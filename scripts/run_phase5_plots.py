#!/usr/bin/env python3
"""Command-line runner for the Stream A Phase 5B visualization layer.

Default invocation is a VALIDATION-ONLY PREFLIGHT: it verifies the optional
Phase 5A and Phase 4 commit manifests, loads and validates every consumed
artifact (Phase 5A tables, Phase 4 evaluation dataset, FS-A feature matrix),
runs the full cross-consistency battery (run completeness, cross-run row_id
alignment, table/row-level agreement, cross-snapshot hash check) and reports
the planned figures. No figure is rendered and no file is written.
Rendering and publication only happen with the explicit ``--execute`` flag.

Phase 5B NEVER fits or refits an anomaly detector, NEVER recalculates a
Phase 4 metric table or a Phase 5A bootstrap result, NEVER recomputes a
saved canonical flag and NEVER changes a feature space. Figures are written
under ``results/stream a/phase 5/figures/reproduction/`` (a new namespace:
historical Phase 5 figures are never touched); rendering happens in a
staging directory and publication is atomic with backup/rollback, the
commit manifest published LAST. Existing outputs are never replaced without
``--overwrite``.

Usage (from the repository root; Windows PowerShell or Linux):

    python scripts/run_phase5_plots.py                                 # preflight
    python scripts/run_phase5_plots.py --execute                       # render + publish
    python scripts/run_phase5_plots.py --execute --overwrite           # replace outputs
    python scripts/run_phase5_plots.py --execute \
        --output-dir "results/stream a/phase 5/figures/reproduction_v2" # redirect outputs

Optional input overrides (defaults are the canonical Phase 5A / Phase 4
outputs and the frozen FS-A feature space):

    --phase5-dir     "results/stream a/phase 5/reproduction"
    --phase4-dataset "results/stream a/phase 4/reproduction/phase4_evaluation_dataset.csv"
    --fs-a           "data/processed/stream-a/features/ULB_FS_A_Baseline.csv"

The primary dataset must contain exactly 30,000 observations and the ten
canonical runs (--expected-sample-size exists only for deliberate synthetic
replicas and is recorded as such). The 284,807-row LOF novelty-mode
companion is never a substitute input.
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

# Non-interactive rendering: select the Agg backend BEFORE the plotting
# module imports pyplot (safe on headless servers and CI).
import matplotlib  # noqa: E402

matplotlib.use("Agg")

from mplad.common import config  # noqa: E402
from mplad.common.io import OutputExistsError  # noqa: E402
from mplad.common.manifest import ManifestError  # noqa: E402
from mplad.stream_a import phase5_plots  # noqa: E402


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_phase5_plots.py",
        description=(
            "Stream A Phase 5B: render the eight authoritative diagnostic "
            "figures from the verified Phase 5A tables, the Phase 4 row-level "
            "evaluation dataset and the FS-A feature matrix (no detector is "
            "ever fitted, no saved flag is ever recomputed)."
        ),
    )
    p.add_argument(
        "--phase5-dir", type=Path, default=None, metavar="DIR",
        help=f"Phase 5A reproduction directory (default: {config.DEFAULT_PHASE5_OUTPUT_DIR})",
    )
    p.add_argument(
        "--phase4-dataset", type=Path, default=None, metavar="CSV",
        help=f"Phase 4 evaluation dataset CSV (default: {config.PHASE4_EVALUATION_DATASET_PATH})",
    )
    p.add_argument(
        "--fs-a", type=Path, default=None, metavar="CSV",
        help=f"FS-A feature matrix CSV with row_id (default: {config.DEFAULT_FS_A_PATH})",
    )
    p.add_argument(
        "--output-dir", type=Path, default=None, metavar="DIR",
        help=f"Figure output directory (default: {config.DEFAULT_PHASE5_FIGURES_DIR})",
    )
    p.add_argument(
        "--expected-sample-size", type=int, default=None, metavar="N",
        help=(
            "Override the required primary-dataset size (frozen default: "
            f"{config.SAMPLE_SIZE_DEFAULT:,}). Exists only for deliberate "
            "synthetic replicas; the override is visible in every error path."
        ),
    )
    p.add_argument(
        "--dpi", type=int, default=None, metavar="DPI",
        help=f"Figure resolution (default: {config.PHASE5_PLOT_DPI_DEFAULT})",
    )
    p.add_argument(
        "--execute", action="store_true",
        help="Render the eight figures and publish them. Without this flag "
             "the runner only validates the inputs (preflight).",
    )
    p.add_argument(
        "--overwrite", action="store_true",
        help="Allow replacing existing output files. Refused by default.",
    )
    return p


def print_preflight_report(report: dict) -> None:
    print("=== INPUTS ===")
    print(f"phase 5A tables   : {report['phase5_dir']}")
    print(f"phase 4 dataset   : {report['phase4_dataset_path']}")
    print(f"FS-A feature matrix: {report['fs_a_path']}")
    print()
    print("=== INPUT INTEGRITY MANIFESTS ===")
    for label, key in (("Phase 5A", "phase5"), ("Phase 4", "phase4")):
        m = report["input_manifests"][key]
        if m["mode"] == "manifest_verified":
            print(f"{label:<10}        : PRESENT and VERIFIED ({m['path']})")
            for name, info in m["artifacts"].items():
                print(f"  {name:<44} sha256 OK ({info['size_bytes']:,} bytes)")
        else:
            print(f"{label:<10}        : ABSENT -> legacy unmanifested input")
            print(f"looked at          : {m['path']}")
            print(
                "handling           : strict structural validation + SHA-256 "
                "recording in the plot metadata;"
            )
            print(
                "                     manifest verification is NOT claimed for "
                "legacy inputs"
            )
    print()
    print("=== PRIMARY DATASET (validated) ===")
    s = report["sample"]
    print(f"runs               : {len(report['run_ids'])} ({report['run_ids'][0]} ... {report['run_ids'][-1]})")
    print(f"sample size        : {s['sample_size']:,}")
    print(f"fraud labels       : {s['fraud_count']} (prevalence {s['fraud_prevalence']:.6f})")
    print("saved 1% flags     : " + ", ".join(
        f"{r}={c}" for r, c in s["per_run_flagged_counts"].items()
    ))
    print()
    print("=== FIGURES PLANNED (nothing is rendered in preflight mode) ===")
    for item in report["figures_planned"]:
        print(f"  {item['figure_no']}. {item['filename']}")
        print(f"     {item['title']}")
    print()
    print("=== OUTPUTS ===")
    o = report["outputs"]
    print(f"directory          : {o['directory']}")
    for key, path in o["paths"].items():
        print(f"{key:<16} : {path}  [{'EXISTS' if o['exists'][key] else 'new'}]")
    if o["blocked"]:
        print("STATUS             : BLOCKED -- output file(s) already exist. Use "
              "--overwrite to replace them, or --output-dir to redirect.")


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    expected_sample_size = (
        args.expected_sample_size
        if args.expected_sample_size is not None
        else config.SAMPLE_SIZE_DEFAULT
    )
    dpi = args.dpi if args.dpi is not None else config.PHASE5_PLOT_DPI_DEFAULT

    print("MPLAD -- Stream A -- Phase 5B runner (visualization layer)")
    print(
        f"mode               : "
        f"{'EXECUTE (figures rendered and published)' if args.execute else 'PREFLIGHT (validation only, nothing rendered or written)'}"
    )
    print(f"phase 5A tables    : {args.phase5_dir or config.DEFAULT_PHASE5_OUTPUT_DIR}")
    print(f"phase 4 dataset    : {args.phase4_dataset or config.PHASE4_EVALUATION_DATASET_PATH}")
    print(f"FS-A matrix        : {args.fs_a or config.DEFAULT_FS_A_PATH}")
    print(f"output dir         : {args.output_dir or config.DEFAULT_PHASE5_FIGURES_DIR}")
    print(f"overwrite          : {args.overwrite}")
    print(f"dpi                : {dpi}")
    if expected_sample_size != config.SAMPLE_SIZE_DEFAULT:
        print(
            "WARNING: non-canonical expected sample size "
            f"({expected_sample_size:,}; the canonical experiment uses "
            f"{config.SAMPLE_SIZE_DEFAULT:,})."
        )
    print()

    try:
        if not args.execute:
            report = phase5_plots.collect_phase5_plots_preflight(
                phase5_dir=args.phase5_dir,
                phase4_dataset_path=args.phase4_dataset,
                fs_a_path=args.fs_a,
                output_dir=args.output_dir,
                expected_sample_size=expected_sample_size,
                verbose=True,
            )
            print_preflight_report(report)
            if report["outputs"]["blocked"]:
                print("\nPreflight complete, but the run is BLOCKED by existing "
                      "outputs (see above).")
            print("\nPREFLIGHT complete: no figure was rendered, no file was "
                  "written, no model was fitted.")
            print("Re-run with --execute to render and publish the figures.")
            return 0

        result = phase5_plots.run_phase5_plots(
            phase5_dir=args.phase5_dir,
            phase4_dataset_path=args.phase4_dataset,
            fs_a_path=args.fs_a,
            output_dir=args.output_dir,
            expected_sample_size=expected_sample_size,
            dpi=dpi,
            overwrite=args.overwrite,
            verbose=True,
        )
        print("\nExecution finished. Published artifacts:")
        for figure_no, path in result["figures"].items():
            print(f"  figure {figure_no}: {path}")
        print(f"  catalog   : {result['catalog']}")
        print(f"  metadata  : {result['plot_metadata']}")
        print(f"  manifest  : {result['manifest']}  (published last)")
        print(
            "Record this run in docs/provenance_log.md. The figure catalog "
            "documentation lives in docs/phase5_figure_catalog.md."
        )
        return 0

    except (
        FileNotFoundError,
        OutputExistsError,
        ManifestError,
        phase5_plots.Phase5PlotError,
        ValueError,
    ) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
