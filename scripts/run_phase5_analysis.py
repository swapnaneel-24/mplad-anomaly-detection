#!/usr/bin/env python3
"""Command-line runner for the Stream A Phase 5A quantitative diagnostics.

Default invocation is a VALIDATION-ONLY PREFLIGHT: it verifies the optional
Phase 4 output manifest, loads and validates the Phase 4 provenance record
and the evaluation dataset (schema, run completeness, cross-run row_id
consistency, finite scores, binary flags, orientation identity). No
analysis is computed and no file is written. Computation and output writing
only happen with the explicit ``--execute`` flag.

Phase 5A NEVER fits a model, NEVER recomputes the saved 1% flags and NEVER
produces a plot: it analyses the verified Phase 4 evaluation dataset. The
historical Phase 5 outputs are never touched; by default results go to
``results/stream a/phase 5/reproduction/``.

Usage (from the repository root; Windows PowerShell or Linux):

    python scripts/run_phase5_analysis.py                                # preflight
    python scripts/run_phase5_analysis.py --execute                      # analyse + write
    python scripts/run_phase5_analysis.py --execute --overwrite          # replace outputs
    python scripts/run_phase5_analysis.py --execute \
        --output-dir "results/stream a/phase 5/reproduction_v2"          # redirect outputs
    python scripts/run_phase5_analysis.py --execute --n-replicates 200   # quick smoke run

Optional input overrides (defaults are the canonical Phase 4 outputs):

    --evaluation-dataset "results/stream a/phase 4/reproduction/phase4_evaluation_dataset.csv"
    --phase4-metadata    "results/stream a/phase 4/reproduction/phase4_run_metadata.json"

The frozen bootstrap protocol uses 2,000 replicates and seed 42 (recorded
in every output); --n-replicates / --bootstrap-seed overrides are allowed
for smoke runs but are reported and recorded as non-canonical.
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
from mplad.stream_a import phase5_analysis                        # noqa: E402


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_phase5_analysis.py",
        description=(
            "Stream A Phase 5A: quantitative diagnostic analysis of the "
            "verified Phase 4 evaluation dataset (no detector is ever "
            "fitted, no threshold is ever reselected, no plots)."
        ),
    )
    p.add_argument(
        "--evaluation-dataset", type=Path, default=None, metavar="CSV",
        help=f"Phase 4 evaluation dataset CSV (default: {config.PHASE4_EVALUATION_DATASET_PATH})",
    )
    p.add_argument(
        "--phase4-metadata", type=Path, default=None, metavar="JSON",
        help=f"Phase 4 run-metadata JSON (default: {config.PHASE4_RUN_METADATA_JSON_PATH})",
    )
    p.add_argument(
        "--output-dir", type=Path, default=None, metavar="DIR",
        help=f"Output directory (default: {config.DEFAULT_PHASE5_OUTPUT_DIR})",
    )
    p.add_argument(
        "--execute", action="store_true",
        help="Compute the analyses and write the outputs. Without this flag "
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
        "--n-replicates", type=int, default=None, metavar="N",
        help=f"Bootstrap replicates (frozen default: {config.PHASE5_BOOTSTRAP_REPLICATES_DEFAULT:,}). "
             "Overrides are recorded as non-canonical parameters.",
    )
    p.add_argument(
        "--bootstrap-seed", type=int, default=None, metavar="SEED",
        help=f"Bootstrap seed (frozen default: {config.PHASE5_BOOTSTRAP_SEED_DEFAULT}). "
             "Overrides are recorded as non-canonical parameters.",
    )
    return p


def print_preflight_report(report: dict) -> None:
    print("=== INPUTS ===")
    print(f"evaluation dataset : {report['evaluation_dataset_path']}")
    print(f"phase 4 metadata   : {report['phase4_run_metadata_path']}")
    print()
    print("=== PHASE 4 INTEGRITY MANIFEST ===")
    m = report["input_manifest"]
    if m["mode"] == "manifest_verified":
        print(f"status             : PRESENT and VERIFIED ({m['path']})")
        for name, info in m["artifacts"].items():
            print(f"  {name:<44} sha256 OK ({info['size_bytes']:,} bytes)")
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
    print("=== PHASE 4 EVALUATION DATASET (validated) ===")
    s = report["sample"]
    print(f"runs               : {len(report['run_ids'])} ({report['run_ids'][0]} ... {report['run_ids'][-1]})")
    print(f"sample size        : {s['sample_size']:,}")
    print(f"fraud labels       : {s['fraud_count']} (prevalence {s['fraud_prevalence']:.6f})")
    print("saved 1% flags     : " + ", ".join(
        f"{r}={c}" for r, c in s["per_run_flagged_counts"].items()
    ))
    a = report["cross_run_alignment"]
    print(
        "cross-run check    : identical row_id and Class sequences across all "
        f"runs ({'verified' if a['positional_comparison_validated'] else 'FAILED'})"
    )
    print()
    print("=== PLANNED ANALYSES (nothing is computed in preflight mode) ===")
    for item in report["analyses_planned"]:
        print(f"  - {item}")
    b = report["bootstrap_parameters"]
    print(
        f"bootstrap protocol : {b['n_replicates']:,} replicates, seed {b['seed']}, "
        "class-stratified, paired on shared replicate indices"
    )
    print()
    print("=== OUTPUTS ===")
    o = report["outputs"]
    print(f"directory          : {o['directory']}")
    for key, path in o["paths"].items():
        print(f"{key:<28} : {path}  [{'EXISTS' if o['exists'][key] else 'new'}]")
    if o["blocked"]:
        print("STATUS             : BLOCKED -- output file(s) already exist. Use "
              "--overwrite to replace them, or --output-dir to redirect.")


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    n_replicates = (
        args.n_replicates
        if args.n_replicates is not None
        else config.PHASE5_BOOTSTRAP_REPLICATES_DEFAULT
    )
    bootstrap_seed = (
        args.bootstrap_seed
        if args.bootstrap_seed is not None
        else config.PHASE5_BOOTSTRAP_SEED_DEFAULT
    )

    print("MPLAD -- Stream A -- Phase 5A runner (quantitative diagnostics)")
    print(
        f"mode               : "
        f"{'EXECUTE (analyses computed, outputs written)' if args.execute else 'PREFLIGHT (validation only, nothing computed or written)'}"
    )
    print(f"evaluation dataset : {args.evaluation_dataset or config.PHASE4_EVALUATION_DATASET_PATH}")
    print(f"phase 4 metadata   : {args.phase4_metadata or config.PHASE4_RUN_METADATA_JSON_PATH}")
    print(f"output dir         : {args.output_dir or config.DEFAULT_PHASE5_OUTPUT_DIR}")
    print(f"overwrite          : {args.overwrite}")
    print(f"bootstrap          : {n_replicates:,} replicates, seed {bootstrap_seed}")
    if n_replicates != config.PHASE5_BOOTSTRAP_REPLICATES_DEFAULT or bootstrap_seed != config.PHASE5_BOOTSTRAP_SEED_DEFAULT:
        print(
            "WARNING: non-canonical bootstrap parameters (frozen protocol: "
            f"{config.PHASE5_BOOTSTRAP_REPLICATES_DEFAULT:,} replicates, seed "
            f"{config.PHASE5_BOOTSTRAP_SEED_DEFAULT}); the override is recorded "
            "in the provenance JSON."
        )
    print()

    try:
        if not args.execute:
            report = phase5_analysis.collect_phase5_preflight(
                evaluation_dataset_path=args.evaluation_dataset,
                phase4_run_metadata_path=args.phase4_metadata,
                output_dir=args.output_dir,
                n_replicates=n_replicates,
                bootstrap_seed=bootstrap_seed,
                overwrite=args.overwrite,
                require_canonical_sample_size=not args.allow_noncanonical_sample_size,
            )
            print_preflight_report(report)
            if report["outputs"]["blocked"]:
                print("\nPreflight complete, but the run is BLOCKED by existing "
                      "outputs (see above).")
            print("\nPREFLIGHT complete: no analysis was computed, no file was "
                  "written, no model was fitted.")
            print("Re-run with --execute to perform the analysis.")
            return 0

        result = phase5_analysis.run_phase5_analysis(
            evaluation_dataset_path=args.evaluation_dataset,
            phase4_run_metadata_path=args.phase4_metadata,
            output_dir=args.output_dir,
            n_replicates=n_replicates,
            bootstrap_seed=bootstrap_seed,
            overwrite=args.overwrite,
            verbose=True,
            require_canonical_sample_size=not args.allow_noncanonical_sample_size,
        )
        print("\nExecution finished. Artifacts:")
        for key in (
            "bootstrap_metrics",
            "paired_bootstrap_differences",
            "pairwise_spearman",
            "pairwise_jaccard_1pct",
            "multithreshold_agreement",
            "hypergeometric_overlap",
            "agreement_groups",
            "fraud_discovery_curve",
            "run_metadata",
            "manifest",
        ):
            print(f"  {key:<28}: {result['paths'][key]}")
        print(
            "Record this run in docs/provenance_log.md. Phase 5B (plotting) "
            "consumes these tables; no plot was produced here."
        )
        return 0

    except (
        FileNotFoundError,
        OutputExistsError,
        ManifestError,
        phase5_analysis.Phase5Error,
        ValueError,
    ) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
