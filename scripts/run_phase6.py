#!/usr/bin/env python3
"""Command-line runner for the Stream A Phase 6 cross-method consistency layer.

Default invocation is a VALIDATION-ONLY PREFLIGHT: it verifies the optional
Phase 5A and Phase 4 output manifests, loads and validates every consumed
artifact (schemas, run completeness, cross-run row_id consistency,
cross-snapshot hash consistency, row-level cross-checks) and -- on the
canonical production path -- validates the reference-checkable values
against the historical acceptance references. No output is computed and no
file is written. Computation and output writing only happen with the
explicit ``--execute`` flag.

Phase 6 NEVER fits a model, NEVER creates a new score or threshold, and
NEVER recomputes a bootstrap estimate, a hypergeometric probability or a
correlation matrix: it synthesises the verified Phase 4 evaluation dataset
and the verified Phase 5A quantitative tables. Historical Phase 6 outputs
are never touched; by default results go to
``results/stream a/phase 6/reproduction/``.

Usage (from the repository root; Windows PowerShell or Linux):

    python scripts/run_phase6.py                                # preflight
    python scripts/run_phase6.py --execute                      # generate outputs
    python scripts/run_phase6.py --execute --overwrite          # replace outputs
    python scripts/run_phase6.py --execute \
        --output-dir "results/stream a/phase 6/reproduction_v2" # redirect outputs

Optional input overrides (defaults are the canonical Phase 4 / Phase 5A
outputs):

    --phase5-dir         "results/stream a/phase 5/reproduction"
    --evaluation-dataset "results/stream a/phase 4/reproduction/phase4_evaluation_dataset.csv"

Canonical-path guards (both ACTIVE BY DEFAULT):

* the primary dataset must carry exactly 30,000 observations and the ten
  canonical runs (``--expected-sample-size`` exists only for deliberate
  synthetic-replica runs and is recorded as a non-canonical override);
* the consumed values are validated against the historical acceptance
  references (30,000 / 47 / 300+300 flags / intersection 107 / union 493 /
  groups 107-193-193-29,507 with frauds 30-0-8-9 / Spearman 0.3666 /
  Jaccard 0.2170 / enrichment 35.67x / log10 upper tail ~ -140.30). A
  mismatch is reported as a FAILED VALIDATION and nothing is written;
  ``--skip-reference-validation`` exists only for deliberate synthetic
  replicas and is recorded as a non-canonical override.
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
from mplad.stream_a import phase6                                 # noqa: E402


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_phase6.py",
        description=(
            "Stream A Phase 6: cross-method consistency analysis of the "
            "verified Phase 4 evaluation dataset and the verified Phase 5A "
            "quantitative tables (evidence synthesis: no detector is ever "
            "fitted, no threshold is ever created, no bootstrap estimate, "
            "hypergeometric probability or correlation matrix is ever "
            "recomputed)."
        ),
    )
    p.add_argument(
        "--phase5-dir", type=Path, default=None, metavar="DIR",
        help=f"Directory holding the Phase 5A reproduction tables "
             f"(default: {config.DEFAULT_PHASE5_OUTPUT_DIR})",
    )
    p.add_argument(
        "--evaluation-dataset", type=Path, default=None, metavar="CSV",
        help=f"Phase 4 evaluation dataset CSV (default: {config.PHASE4_EVALUATION_DATASET_PATH})",
    )
    p.add_argument(
        "--output-dir", type=Path, default=None, metavar="DIR",
        help=f"Output directory (default: {config.DEFAULT_PHASE6_OUTPUT_DIR})",
    )
    p.add_argument(
        "--execute", action="store_true",
        help="Generate the outputs. Without this flag the runner only "
             "validates the inputs (read-only preflight).",
    )
    p.add_argument(
        "--overwrite", action="store_true",
        help="Allow replacing existing output files. Refused by default.",
    )
    p.add_argument(
        "--expected-sample-size", type=int, default=None, metavar="N",
        help=f"Deliberate override of the canonical sample-size requirement "
             f"(frozen default: {config.SAMPLE_SIZE_DEFAULT:,}). Recorded as "
             f"a non-canonical parameter in the run metadata.",
    )
    p.add_argument(
        "--skip-reference-validation", action="store_true",
        help="Deliberately skip the historical-acceptance-reference "
             "validation (canonical path: ACTIVE). Recorded as a "
             "non-canonical parameter in the run metadata.",
    )
    return p


def print_preflight_report(report: dict) -> None:
    print("=== INPUTS ===")
    print(f"phase 5A tables   : {report['phase5_dir']}")
    print(f"evaluation dataset: {report['phase4_dataset_path']}")
    print()
    print("=== INPUT INTEGRITY MANIFESTS ===")
    for layer in ("phase5", "phase4"):
        m = report["input_manifests"][layer]
        if m["mode"] == "manifest_verified":
            print(f"{layer:<17}: PRESENT and VERIFIED ({m['path']})")
            for name, info in m["artifacts"].items():
                print(f"  {name:<44} sha256 OK ({info['size_bytes']:,} bytes)")
        else:
            print(f"{layer:<17}: ABSENT -> legacy unmanifested inputs")
            print(f"looked at         : {m['path']}")
            print(
                "handling          : strict structural validation + SHA-256 "
                "recording in the run metadata;"
            )
            print(
                "                    manifest verification is NOT claimed for "
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
    print(
        "row-level checks   : "
        f"{len(report['row_level_checks_performed'])} recomputed quantities "
        "matched the saved Phase 5A values"
    )
    pair = report["comparison_pair"]
    print(
        f"comparison pair    : {pair['if_run_id']} vs {pair['lof_run_id']} "
        f"({pair['flag_source']})"
    )
    print()
    print("=== REFERENCE VALIDATION (canonical production path) ===")
    rv = report["reference_validation"]
    if rv["enabled"]:
        print(
            f"status             : {'PASSED' if rv['passed'] else 'FAILED'} "
            f"({rv['n_references_checked']} historical acceptance references checked)"
        )
    else:
        print(
            "status             : deliberately SKIPPED (non-canonical replica; "
            "recorded in the run metadata)"
        )
    print()
    print("=== PLANNED ANALYSES (nothing is computed in preflight mode) ===")
    for item in report["analyses_planned"]:
        print(f"  - {item}")
    print()
    print("=== OUTPUTS ===")
    o = report["outputs"]
    print(f"directory          : {o['directory']}")
    for key, path in o["paths"].items():
        print(f"{key:<22} : {path}  [{'EXISTS' if o['exists'][key] else 'new'}]")
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
    validate_references = not args.skip_reference_validation

    print("MPLAD -- Stream A -- Phase 6 runner (cross-method consistency)")
    print(
        f"mode               : "
        f"{'EXECUTE (outputs generated)' if args.execute else 'PREFLIGHT (read-only validation, nothing computed or written)'}"
    )
    print(f"phase 5A tables    : {args.phase5_dir or config.DEFAULT_PHASE5_OUTPUT_DIR}")
    print(f"evaluation dataset : {args.evaluation_dataset or config.PHASE4_EVALUATION_DATASET_PATH}")
    print(f"output dir         : {args.output_dir or config.DEFAULT_PHASE6_OUTPUT_DIR}")
    print(f"overwrite          : {args.overwrite}")
    print(
        f"sample size guard  : {expected_sample_size:,} observations, ten canonical runs "
        f"(default {'ACTIVE' if expected_sample_size == config.SAMPLE_SIZE_DEFAULT else 'OVERRIDDEN (non-canonical)'})"
    )
    print(
        f"reference guard    : {'ACTIVE' if validate_references else 'SKIPPED (non-canonical)'}"
    )
    if expected_sample_size != config.SAMPLE_SIZE_DEFAULT or not validate_references:
        print(
            "WARNING: non-canonical guards active; the override is recorded in "
            "the run metadata."
        )
    print()

    try:
        if not args.execute:
            report = phase6.collect_phase6_preflight(
                phase5_dir=args.phase5_dir,
                phase4_dataset_path=args.evaluation_dataset,
                output_dir=args.output_dir,
                expected_sample_size=expected_sample_size,
                validate_references=validate_references,
            )
            print_preflight_report(report)
            if report["outputs"]["blocked"]:
                print("\nPreflight complete, but the run is BLOCKED by existing "
                      "outputs (see above).")
            print("\nPREFLIGHT complete: no output was computed, no file was "
                  "written, no model was fitted.")
            print("Re-run with --execute to generate the Phase 6 outputs.")
            return 0

        result = phase6.run_phase6(
            phase5_dir=args.phase5_dir,
            phase4_dataset_path=args.evaluation_dataset,
            output_dir=args.output_dir,
            expected_sample_size=expected_sample_size,
            validate_references=validate_references,
            overwrite=args.overwrite,
            verbose=True,
        )
        print("\nExecution finished. Artifacts:")
        for key in (
            "group_assignments",
            "consistency_scorecard",
            "consistency_report",
            "run_metadata",
            "manifest",
        ):
            print(f"  {key:<22}: {result['paths'][key]}")
        print(
            "Record this run in docs/provenance_log.md. Phase 6 is the final "
            "stage of this migration; no further stage is implemented."
        )
        return 0

    except (
        FileNotFoundError,
        OutputExistsError,
        ManifestError,
        phase6.Phase6Error,
        ValueError,
    ) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
