"""Stream A -- Phase 6: cross-method consistency analysis (evidence synthesis).

Role and boundaries
-------------------
Phase 6 is the agreement/consistency interpretation layer of the migration.
It consumes, strictly read-only:

* the verified Phase 4 evaluation dataset
  (``results/stream a/phase 4/reproduction/phase4_evaluation_dataset.csv``);
* the verified Phase 5A quantitative tables
  (``results/stream a/phase 5/reproduction/``): the 10x10 Spearman and
  top-1% Jaccard matrices, the hypergeometric overlap summary, the
  agreement-group composition table, the multi-threshold agreement counts,
  the bootstrap metrics, the paired bootstrap differences and the Phase 5A
  run-metadata provenance record.

and produces (1) an observation-level agreement-group assignment for the
IF_003 / LOF_004 comparison pair, (2) a compact consistency scorecard in
which every entry records its source artifact and original metric field,
and (3) a deterministic five-question Markdown consistency report.

This is an **evidence-synthesis stage, not a modelling or statistical
experimentation stage**. It NEVER fits, refits or constructs a detector
(the module imports no scikit-learn and no scipy at all), NEVER creates a
new anomaly score or threshold, NEVER recomputes a bootstrap estimate, a
hypergeometric probability or a correlation matrix (every such number is
READ from the frozen Phase 5A tables), and NEVER modifies the canonical
30,000-row sample, the saved Phase 3 bottom-1% flags, or any Phase 3/4/5A/5B
artifact. The 284,807-row full-data LOF novelty-mode companion is outside
this layer entirely.

Cross-snapshot integrity
------------------------
The Phase 5A tables and the row-level Phase 4 data must come from the SAME
Phase 4 execution. This is enforced before anything is consumed: the input
SHA-256 recorded in ``phase5_run_metadata.json`` must equal the hash of the
evaluation dataset actually consumed, and the optional Phase 5A and Phase 4
commit manifests are verified first (hash-verification genuinely happens
before consumption). Input hashes are recomputed immediately before
publication as well.

Group-assignment semantics
--------------------------
IF_003 and LOF_004 are extracted by ``run_id`` and joined one-to-one on
``row_id`` (a duplicated, missing or extra row ID is a hard error; a
positional comparison is never performed). Using their SAVED canonical 1%
flags, every observation is assigned exactly one group: ``Both`` (IF=1,
LOF=1), ``IF-only`` (IF=1, LOF=0), ``LOF-only`` (IF=0, LOF=1) or
``Neither`` (IF=0, LOF=0) -- a disjoint and exhaustive partition whose
counts are cross-checked against the saved Phase 5A agreement-group table
(and, transitively, against the row-level flags).

Lightweight consistency checks
------------------------------
Flag counts, the observed intersection, the union, the four group counts
and their fraud counts, the saved top-1% Jaccard, the ten-run union /
intersection at the canonical 1% budget and the saved precision / recall /
F1-at-1% point estimates are recomputed from the Phase 4 observation-level
data and compared with the saved Phase 5A values; any disagreement is a
hard error. These checks never REPLACE a saved value: the scorecard reports
the frozen Phase 5A numbers, with the matching recomputations recorded as
explicit cross-check rows.

Reference validation
--------------------
The historical acceptance references for the canonical experiment (30,000
observations, 47 fraud labels, 300/300 flags, intersection 107, union 493,
groups 107/193/193/29,507 with frauds 30/0/8/9, Spearman 0.3666, Jaccard
0.2170, enrichment 35.67x, log10 upper tail ~ -140.30) are recorded in
``PHASE6_REFERENCE_VALUES`` **for validation only** -- they are never
written into an output as if computed. When reference validation is active
(the default production path) every source-derived value is compared with
its reference and ANY mismatch is reported as a failed validation (the run
aborts; the value is never forced). Synthetic replicas disable the check
deliberately (``validate_references=False``), which is recorded in the run
metadata.

Exploratory status of the comparison pair
-----------------------------------------
IF_003 / LOF_004 (and IF_004) were highlighted AFTER inspecting the
label-informed Phase 4 results; every comparison reported for them is
exploratory (post-hoc selection). Labels are used solely for post-hoc
evaluation and discussion.

Determinism
-----------
The consistency report is generated deterministically from validated
values and explicitly authored interpretation rules: no timestamp, no
filesystem path and no random element appears in the report text, so the
same inputs always yield a byte-identical report. The Phase 5B table
validators are re-implemented here (rather than imported) so that this
compute layer stays importable without a plotting stack.
"""
from __future__ import annotations

import json
import math
import platform
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from mplad.common import config
from mplad.common.io import assert_outputs_writable
from mplad.common.manifest import (
    ManifestError,
    build_manifest,
    load_manifest,
    save_manifest,
    verify_manifest,
)
from mplad.stream_a import phase5_analysis

__all__ = [
    "Phase6Error",
    "Phase6InputError",
    "GroupAssignmentError",
    "ReferenceValidationError",
    "assign_agreement_groups",
    "summarize_group_assignments",
    "validate_matrix_table",
    "validate_hypergeometric_table",
    "validate_agreement_groups_table",
    "validate_multithreshold_table",
    "validate_bootstrap_metrics_table",
    "validate_paired_differences_table",
    "validate_phase5_metadata",
    "load_phase6_tables",
    "build_consistency_context",
    "build_scorecard",
    "build_consistency_report",
    "validate_against_references",
    "collect_phase6_preflight",
    "run_phase6",
    "GROUP_KEYS",
    "GROUP_LABELS",
    "GROUP_ASSIGNMENT_COLUMNS",
    "SCORECARD_COLUMNS",
    "PHASE6_REFERENCE_VALUES",
    "PHASE6_REFERENCE_TOLERANCES",
    "INTERPRETATION_PRINCIPLES",
    "IF_RUN_ID",
    "LOF_RUN_ID",
]


# ---------------------------------------------------------------------------
# Errors (all ValueError subclasses, matching the Phase 3/4/5 convention)
# ---------------------------------------------------------------------------

class Phase6Error(ValueError):
    """Base class for Phase 6 contract violations."""


class Phase6InputError(Phase6Error):
    """A consumed input violates its contract (schema, provenance or
    cross-check against the Phase 4 observation-level data)."""


class GroupAssignmentError(Phase6Error):
    """The observation-level group assignment violates its contract."""


class ReferenceValidationError(Phase6Error):
    """A source-derived value disagrees with the historical acceptance
    reference for the canonical experiment (the value is never forced)."""


# ---------------------------------------------------------------------------
# Frozen conventions and documented schemas
# ---------------------------------------------------------------------------

#: The comparison pair (identical to the Phase 5A overlap runs -- Phase 6
#: analyses exactly this pair and nothing else).
IF_RUN_ID: str = config.PHASE5_OVERLAP_RUN_A
LOF_RUN_ID: str = config.PHASE5_OVERLAP_RUN_B

#: Internal group keys in the canonical Phase 5A agreement-group order.
GROUP_KEYS: Tuple[str, ...] = ("both", "if_only", "lof_only", "neither")

#: Report/assignment labels for the four groups (Phase 6 contract).
GROUP_LABELS: Dict[str, str] = {
    "both": "Both",
    "if_only": "IF-only",
    "lof_only": "LOF-only",
    "neither": "Neither",
}

#: phase6_group_assignments.csv schema (frozen).
GROUP_ASSIGNMENT_COLUMNS: list = [
    "row_id",
    "Class",
    "if_run_id",
    "lof_run_id",
    "if_anomaly_score",
    "lof_anomaly_score",
    "if_flag",
    "lof_flag",
    "agreement_group",
]

#: phase6_consistency_scorecard.csv schema (frozen).
SCORECARD_COLUMNS: list = [
    "section",
    "metric",
    "value",
    "value_type",
    "source_artifact",
    "source_field",
    "note",
]

#: Columns a run frame must carry to be joinable (subset of the frozen
#: Phase 4 evaluation-dataset schema; nothing undocumented is read).
RUN_FRAME_REQUIRED_COLUMNS: tuple = (
    "run_id",
    "row_id",
    config.LABEL_COLUMN,
    "anomaly_score",
    "flag",
)

#: Historical acceptance references for the canonical experiment
#: (VALIDATION ONLY -- never written into an output as if computed; a
#: mismatch is reported as a failed validation, never forced). The float
#: references are the published roundings of the real-data values, so they
#: are compared with the tolerances recorded in
#: ``PHASE6_REFERENCE_TOLERANCES``; integer references compare exactly.
PHASE6_REFERENCE_VALUES: Dict[str, Union[int, float]] = {
    "sample_size": 30_000,
    "fraud_label_count": 47,
    "if003_flagged_count": 300,
    "lof004_flagged_count": 300,
    "observed_intersection": 107,
    "union_size": 493,
    "both_observation_count": 107,
    "if_only_observation_count": 193,
    "lof_only_observation_count": 193,
    "neither_observation_count": 29_507,
    "both_fraud_count": 30,
    "if_only_fraud_count": 0,
    "lof_only_fraud_count": 8,
    "neither_fraud_count": 9,
    "spearman_if003_lof004": 0.3666,
    "jaccard_if003_lof004": 0.2170,
    "enrichment_observed_over_expected": 35.67,
    "log10_upper_tail_probability": -140.30,
}

#: Absolute tolerances for the rounded float references (every metric not
#: listed here -- all the counts -- is compared exactly).
PHASE6_REFERENCE_TOLERANCES: Dict[str, float] = {
    "spearman_if003_lof004": 1e-4,          # reference is a 4-dp rounding
    "jaccard_if003_lof004": 1e-4,           # reference is a 4-dp rounding
    "enrichment_observed_over_expected": 5e-3,  # 2-dp rounding
    "log10_upper_tail_probability": 0.5,    # published as approximate
}

#: The interpretation principles every Phase 6 output must obey (authored
#: once, reused verbatim in the report and the contract).
INTERPRETATION_PRINCIPLES: Tuple[str, ...] = (
    "Labels are used solely for post-hoc evaluation and discussion; no model "
    "was selected, tuned or refitted using labels in this phase.",
    "An anomaly flag is not proof of fraud; flags are detector opinions at a "
    "fixed budget, not adjudicated findings.",
    "Performance observed on the ULB credit-card fraud benchmark must not be "
    "assumed to transfer to MPLAD transactions.",
    "No universal superiority of LOF or Isolation Forest is claimed; the "
    "evidence covers one benchmark sample and post-hoc selected runs.",
    "The IF_003/LOF_004 comparison is exploratory and subject to "
    "label-informed selection bias (the pair was highlighted after inspecting "
    "the Phase 4 label-informed results).",
    "Rank agreement, flag overlap and ground-truth detection performance are "
    "distinct constructs and are reported separately (Q1, Q2, Q4).",
    "No new threshold is introduced and no new anomaly score is created; the "
    "saved canonical Phase 3 1% flags are the only selections analysed.",
)

#: Exploratory-selection caveat reused verbatim from Phase 5A.
EXPLORATORY_CAVEAT: str = phase5_analysis.EXPLORATORY_SELECTION_CAVEAT


# ---------------------------------------------------------------------------
# A. Observation-level group assignment
# ---------------------------------------------------------------------------

def _validate_run_frame(frame: object, expected_run_id: str, name: str) -> pd.DataFrame:
    """Validate one extracted run frame for the one-to-one join.

    Checks: a pandas DataFrame; every required column present (subset of
    the frozen Phase 4 schema); a constant ``run_id`` equal to
    ``expected_run_id`` (a wrong run is rejected); integer, unique, non-null
    ``row_id``; strictly binary ``Class`` and ``flag``; floating finite
    ``anomaly_score``.
    """
    if not isinstance(frame, pd.DataFrame):
        raise GroupAssignmentError(
            f"{name}: expected a pandas DataFrame, got {type(frame).__name__}"
        )
    problems: List[str] = []
    columns = list(frame.columns)
    missing = [c for c in RUN_FRAME_REQUIRED_COLUMNS if c not in columns]
    if missing:
        problems.append("missing column(s): " + ", ".join(missing))
    if problems:
        raise GroupAssignmentError(_format_problems(problems, f"{name} schema"))

    run_values = frame["run_id"].unique().tolist()
    if run_values != [expected_run_id]:
        problems.append(
            f"'run_id' must be constantly '{expected_run_id}' (the requested "
            f"run); got {run_values[:5]}"
        )

    row_ids = frame["row_id"].to_numpy()
    if row_ids.dtype.kind not in "iu":
        problems.append(f"'row_id' must have an integer dtype, got {row_ids.dtype}")
    else:
        if frame["row_id"].isna().any():
            problems.append("'row_id' contains missing values")
        if np.unique(row_ids).size != row_ids.size:
            problems.append(
                f"'row_id' contains {row_ids.size - np.unique(row_ids).size} "
                "duplicate value(s) -- a one-to-one join is impossible"
            )

    class_values = frame[config.LABEL_COLUMN].to_numpy()
    if class_values.dtype.kind not in "iuf" or not np.isin(class_values, (0, 1)).all():
        problems.append(
            f"'{config.LABEL_COLUMN}' must be strictly binary (0/1), got values "
            f"{np.unique(class_values).tolist()[:5]}"
        )
    flags = frame["flag"].to_numpy()
    if flags.dtype.kind not in "iuf" or not np.isin(flags, (0, 1)).all():
        problems.append(
            f"'flag' must be strictly binary (0/1), got values "
            f"{np.unique(flags).tolist()[:5]}"
        )
    scores = frame["anomaly_score"].to_numpy()
    if scores.dtype.kind != "f":
        problems.append(f"'anomaly_score' must have a floating dtype, got {scores.dtype}")
    elif not np.isfinite(scores).all():
        problems.append("'anomaly_score' contains non-finite value(s)")

    if problems:
        raise GroupAssignmentError(_format_problems(problems, f"{name} integrity"))
    return frame


def assign_agreement_groups(
    if_frame: pd.DataFrame,
    lof_frame: pd.DataFrame,
    if_run_id: str = IF_RUN_ID,
    lof_run_id: str = LOF_RUN_ID,
) -> pd.DataFrame:
    """Assign every observation exactly one agreement group.

    The two run frames (extracted from the validated Phase 4 evaluation
    dataset by ``run_id``) are joined **one-to-one on ``row_id``** -- never
    positionally. Duplicated, missing or extra row IDs on either side are
    hard errors, as is any label disagreement between the two frames. The
    groups follow the SAVED canonical 1% flags:

    * ``Both``    -- if_flag = 1 and lof_flag = 1
    * ``IF-only`` -- if_flag = 1 and lof_flag = 0
    * ``LOF-only``-- if_flag = 0 and lof_flag = 1
    * ``Neither`` -- if_flag = 0 and lof_flag = 0

    Returns the assignment frame (``GROUP_ASSIGNMENT_COLUMNS``) in the
    canonical order of the IF frame's rows, with the partition property
    (disjoint, exhaustive, every observation exactly once) validated before
    returning.
    """
    if_frame = _validate_run_frame(if_frame, if_run_id, f"IF frame ('{if_run_id}')")
    lof_frame = _validate_run_frame(lof_frame, lof_run_id, f"LOF frame ('{lof_run_id}')")

    n_if, n_lof = len(if_frame), len(lof_frame)
    if n_if != n_lof:
        raise GroupAssignmentError(
            f"the two run frames carry different row counts (IF {n_if:,} vs "
            f"LOF {n_lof:,}) -- every observation must appear exactly once on "
            "both sides of the join"
        )

    merged = if_frame.merge(
        lof_frame,
        on=config.ID_COLUMN,
        how="inner",
        validate="one_to_one",
        suffixes=("_if", "_lof"),
    )
    if len(merged) != n_if:
        missing_from_lof = int(n_if - len(merged))
        raise GroupAssignmentError(
            f"the row_id sets of the two run frames do not match ({n_if:,} vs "
            f"{n_lof:,} rows, {len(merged):,} joined) -- {missing_from_lof} "
            "row_id(s) are missing on one side; a one-to-one join is impossible"
        )

    label_if = merged[f"{config.LABEL_COLUMN}_if"].to_numpy()
    label_lof = merged[f"{config.LABEL_COLUMN}_lof"].to_numpy()
    if not np.array_equal(label_if, label_lof):
        n_bad = int((label_if != label_lof).sum())
        raise GroupAssignmentError(
            f"'{config.LABEL_COLUMN}' disagrees between the two frames for "
            f"{n_bad} row(s) -- labels are joined on row_id and must be "
            "identical (the Phase 4 label-alignment invariant)"
        )

    if_flag = merged["flag_if"].to_numpy()
    lof_flag = merged["flag_lof"].to_numpy()
    agreement_group = np.select(
        [
            (if_flag == 1) & (lof_flag == 1),
            (if_flag == 1) & (lof_flag == 0),
            (if_flag == 0) & (lof_flag == 1),
            (if_flag == 0) & (lof_flag == 0),
        ],
        [
            GROUP_LABELS["both"],
            GROUP_LABELS["if_only"],
            GROUP_LABELS["lof_only"],
            GROUP_LABELS["neither"],
        ],
        default="",
    )
    if (agreement_group == "").any():
        # Unreachable after the binary-flag validation; kept as a hard guard.
        raise GroupAssignmentError(
            "unassignable flag combination(s) present -- flags must be binary"
        )

    assignments = pd.DataFrame(
        {
            "row_id": merged[config.ID_COLUMN].to_numpy(),
            config.LABEL_COLUMN: label_if.astype(np.int64),
            "if_run_id": if_run_id,
            "lof_run_id": lof_run_id,
            "if_anomaly_score": merged["anomaly_score_if"].to_numpy(dtype=np.float64),
            "lof_anomaly_score": merged["anomaly_score_lof"].to_numpy(dtype=np.float64),
            "if_flag": if_flag.astype(np.int64),
            "lof_flag": lof_flag.astype(np.int64),
            "agreement_group": agreement_group,
        },
        columns=GROUP_ASSIGNMENT_COLUMNS,
    )

    _validate_partition(assignments, n_expected=n_if)
    return assignments


def _validate_partition(assignments: pd.DataFrame, n_expected: int) -> None:
    """The assignment must be a disjoint, exhaustive, unique-key partition."""
    problems: List[str] = []
    row_ids = assignments[config.ID_COLUMN].to_numpy()
    if len(assignments) != n_expected:
        problems.append(
            f"the assignment carries {len(assignments):,} rows, expected "
            f"{n_expected:,}"
        )
    if np.unique(row_ids).size != row_ids.size:
        problems.append("'row_id' is not unique -- an observation appears twice")
    counts = assignments["agreement_group"].value_counts().to_dict()
    unexpected = sorted(set(counts) - set(GROUP_LABELS.values()))
    if unexpected:
        problems.append(f"unexpected group label(s): {unexpected}")
    if sum(counts.values()) != len(assignments):
        problems.append("group counts do not sum to the row count")
    if problems:
        raise GroupAssignmentError(_format_problems(problems, "partition"))


def summarize_group_assignments(assignments: pd.DataFrame) -> Dict:
    """Summarise the assignment: per-group counts/frauds plus the overlap
    quantities of the two flagged sets (all derived from the assignment by
    pure arithmetic; internally consistency-checked)."""
    _validate_partition(assignments, n_expected=len(assignments))
    fraud = assignments[config.LABEL_COLUMN].to_numpy() == 1
    if_flag = assignments["if_flag"].to_numpy() == 1
    lof_flag = assignments["lof_flag"].to_numpy() == 1

    masks = {
        "both": if_flag & lof_flag,
        "if_only": if_flag & ~lof_flag,
        "lof_only": ~if_flag & lof_flag,
        "neither": ~if_flag & ~lof_flag,
    }
    groups: Dict[str, Dict[str, int]] = {}
    for key, mask in masks.items():
        groups[key] = {
            "observation_count": int(np.count_nonzero(mask)),
            "fraud_count": int(np.count_nonzero(mask & fraud)),
        }

    k_a = int(np.count_nonzero(if_flag))
    k_b = int(np.count_nonzero(lof_flag))
    intersection = groups["both"]["observation_count"]
    union = int(np.count_nonzero(if_flag | lof_flag))
    if union != k_a + k_b - intersection:
        raise GroupAssignmentError(
            "internally inconsistent assignment: union != k_if + k_lof - "
            "intersection"
        )

    total_fraud = int(np.count_nonzero(fraud))
    if sum(g["fraud_count"] for g in groups.values()) != total_fraud:
        raise GroupAssignmentError(
            "group fraud counts do not sum to the total fraud count"
        )

    return {
        "groups": groups,
        "if_flagged": k_a,
        "if_flagged_frauds": groups["both"]["fraud_count"] + groups["if_only"]["fraud_count"],
        "lof_flagged": k_b,
        "lof_flagged_frauds": groups["both"]["fraud_count"] + groups["lof_only"]["fraud_count"],
        "observed_intersection": intersection,
        "union_size": union,
        "union_frauds": (
            groups["both"]["fraud_count"]
            + groups["if_only"]["fraud_count"]
            + groups["lof_only"]["fraud_count"]
        ),
        "sample_size": int(len(assignments)),
        "fraud_label_count": total_fraud,
    }


# ---------------------------------------------------------------------------
# B. Phase 5A table validators (mirroring the Phase 5B validators so this
#    compute layer stays importable without a plotting stack)
# ---------------------------------------------------------------------------

def _require_file(path: Path, what: str) -> None:
    if not Path(path).is_file():
        raise FileNotFoundError(
            f"{what} not found: {path}\n"
            f"Phase 6 consumes the verified Phase 5A reproduction tables; "
            f"pass --phase5-dir if they live somewhere else."
        )


def _read_required_csv(path: Path, what: str) -> pd.DataFrame:
    _require_file(path, what)
    return pd.read_csv(path)


def validate_matrix_table(
    matrix_df: pd.DataFrame,
    expected_run_ids: Sequence[str],
    name: str,
    value_range: Tuple[float, float],
) -> pd.DataFrame:
    """Validate a 10x10 Phase 5A matrix table loaded with ``index_col=0``.

    Checks: DataFrame; index plus one column per expected run (exact label
    set on both axes, canonical order preserved); finite values inside
    ``value_range``; exact symmetry; diagonal exactly 1.0. Returns the
    matrix re-indexed in canonical run order.
    """
    expected_run_ids = list(expected_run_ids)
    if not isinstance(matrix_df, pd.DataFrame):
        raise Phase6InputError(f"{name}: expected a pandas DataFrame")
    problems: List[str] = []
    if list(matrix_df.index) != expected_run_ids or list(matrix_df.columns) != expected_run_ids:
        problems.append(
            "axes must list the expected runs in canonical order "
            f"(got index {list(matrix_df.index)}, columns {list(matrix_df.columns)})"
        )
    if problems:
        raise Phase6InputError(_format_problems(problems, f"{name} schema"))

    values = matrix_df.to_numpy(dtype=np.float64)
    lo, hi = value_range
    if not np.isfinite(values).all():
        problems.append("contains non-finite values")
    if values.min() < lo or values.max() > hi:
        problems.append(
            f"values outside the valid range [{lo}, {hi}] "
            f"(min {values.min():.6f}, max {values.max():.6f})"
        )
    if not np.allclose(values, values.T, rtol=0.0, atol=1e-12):
        problems.append("matrix is not symmetric")
    if not np.allclose(np.diag(values), 1.0, rtol=0.0, atol=1e-12):
        problems.append("diagonal is not exactly 1.0")
    if problems:
        raise Phase6InputError(_format_problems(problems, f"{name} integrity"))
    return matrix_df.loc[expected_run_ids, expected_run_ids]


def validate_hypergeometric_table(hyper_df: pd.DataFrame) -> Dict:
    """Validate the one-row Phase 5A hypergeometric summary; return a dict.

    Checks the frozen schema, degenerate parameters, the support of the
    observed intersection, the union identity, the expected-intersection
    and enrichment identities and the log10/log consistency. The linear
    ``survival_upper_tail`` may legitimately underflow to 0.0 for extreme
    overlaps; only the log-space value is consumed downstream and the
    underflow is never reported as a probability of exactly zero.
    """
    if not isinstance(hyper_df, pd.DataFrame) or hyper_df.shape[0] != 1:
        raise Phase6InputError(
            "phase5_hypergeometric_overlap.csv must contain exactly one row "
            f"(got {0 if not isinstance(hyper_df, pd.DataFrame) else hyper_df.shape[0]})"
        )
    required = [c for c in phase5_analysis.HYPERGEOMETRIC_OVERLAP_COLUMNS if c != "null_model"]
    missing = [c for c in required if c not in hyper_df.columns]
    if missing:
        raise Phase6InputError(
            "phase5_hypergeometric_overlap.csv is missing column(s): " + ", ".join(missing)
        )
    row = {c: hyper_df.iloc[0][c] for c in phase5_analysis.HYPERGEOMETRIC_OVERLAP_COLUMNS}
    try:
        row["threshold_pct"] = float(row["threshold_pct"])
        row["n_observations"] = int(row["n_observations"])
        row["run_a_flagged"] = int(row["run_a_flagged"])
        row["run_b_flagged"] = int(row["run_b_flagged"])
        row["observed_intersection"] = int(row["observed_intersection"])
        row["union_size"] = int(row["union_size"])
        row["expected_intersection"] = float(row["expected_intersection"])
        row["enrichment_observed_over_expected"] = float(
            row["enrichment_observed_over_expected"]
        )
        row["survival_upper_tail"] = float(row["survival_upper_tail"])
        row["log_survival"] = float(row["log_survival"])
        row["log10_survival"] = float(row["log10_survival"])
    except (TypeError, ValueError) as exc:
        raise Phase6InputError(
            f"phase5_hypergeometric_overlap.csv has non-numeric values where "
            f"numbers are required: {exc}"
        ) from exc

    problems: List[str] = []
    n, k_a, k_b = row["n_observations"], row["run_a_flagged"], row["run_b_flagged"]
    observed, union = row["observed_intersection"], row["union_size"]
    if n < 2 or k_a < 1 or k_b < 1 or k_a > n or k_b > n:
        problems.append(f"degenerate parameters (n={n}, k_a={k_a}, k_b={k_b})")
    if observed > min(k_a, k_b) or observed < max(0, k_a + k_b - n):
        problems.append(
            f"observed intersection {observed} outside the valid support "
            f"[{max(0, k_a + k_b - n)}, {min(k_a, k_b)}]"
        )
    if union != k_a + k_b - observed:
        problems.append(f"union {union} != k_a + k_b - observed ({k_a + k_b - observed})")
    if not math.isclose(row["expected_intersection"], (k_a * k_b) / n, rel_tol=1e-9, abs_tol=1e-9):
        problems.append(
            f"expected intersection {row['expected_intersection']:.6f} != "
            f"k_a*k_b/n ({(k_a * k_b) / n:.6f})"
        )
    if not math.isclose(
        row["enrichment_observed_over_expected"],
        observed / row["expected_intersection"],
        rel_tol=1e-9,
        abs_tol=1e-9,
    ):
        problems.append("enrichment != observed / expected")
    if not math.isfinite(row["log10_survival"]) or row["log10_survival"] > 0.0:
        problems.append(
            f"log10 upper-tail probability must be finite and <= 0 (got {row['log10_survival']})"
        )
    if not math.isclose(
        row["log10_survival"], row["log_survival"] / math.log(10.0), rel_tol=1e-9, abs_tol=1e-12
    ):
        problems.append("log10_survival != log_survival / ln(10)")
    if problems:
        raise Phase6InputError(_format_problems(problems, "hypergeometric summary integrity"))
    return row


def validate_agreement_groups_table(
    groups_df: pd.DataFrame,
    expected_run_ids_pair: Tuple[str, str],
    sample_size: int,
    fraud_count: int,
) -> pd.DataFrame:
    """Validate the four-row Phase 5A agreement-group table (schema, group
    set, exhaustive partition, fraud accounting)."""
    if not isinstance(groups_df, pd.DataFrame):
        raise Phase6InputError("agreement groups table: expected a pandas DataFrame")
    columns = list(groups_df.columns)
    expected_columns = list(phase5_analysis.AGREEMENT_GROUPS_COLUMNS)
    if columns != expected_columns:
        raise Phase6InputError(
            _format_problems(
                [f"columns {columns} != the frozen schema {expected_columns}"],
                "agreement groups schema",
            )
        )
    run_a, run_b = expected_run_ids_pair
    problems: List[str] = []
    if sorted(groups_df["run_a"].unique().tolist()) != [run_a]:
        problems.append(f"run_a column must be exactly ['{run_a}']")
    if sorted(groups_df["run_b"].unique().tolist()) != [run_b]:
        problems.append(f"run_b column must be exactly ['{run_b}']")
    if sorted(groups_df["group"].tolist()) != sorted(GROUP_KEYS):
        problems.append(f"group column must contain exactly {list(GROUP_KEYS)}")
    if problems:
        raise Phase6InputError(_format_problems(problems, "agreement groups schema"))

    if int(groups_df["observation_count"].sum()) != sample_size:
        problems.append(
            f"observation counts sum to {int(groups_df['observation_count'].sum()):,} "
            f"!= {sample_size:,} (not an exhaustive partition)"
        )
    if int(groups_df["fraud_count"].sum()) != fraud_count:
        problems.append(
            f"fraud counts sum to {int(groups_df['fraud_count'].sum())} != {fraud_count}"
        )
    if problems:
        raise Phase6InputError(_format_problems(problems, "agreement groups integrity"))
    return groups_df.set_index("group").loc[list(GROUP_KEYS)].reset_index()


def validate_multithreshold_table(
    mt_df: pd.DataFrame,
    sample_size: int,
) -> pd.DataFrame:
    """Validate the saved multi-threshold agreement counts table.

    Checks: exact schema; one complete block (``n_methods = 0..n_runs``)
    per threshold of the frozen grid, in grid order; counts non-negative
    integers partitioning the sample at every threshold; ``k_nominal``
    following the recorded k rule; the canonical 1% block sourced from the
    saved flags and every other block from derived top-k selections.
    """
    if not isinstance(mt_df, pd.DataFrame):
        raise Phase6InputError("multithreshold table: expected a pandas DataFrame")
    columns = list(mt_df.columns)
    expected_columns = list(phase5_analysis.MULTITHRESHOLD_AGREEMENT_COLUMNS)
    if columns != expected_columns:
        raise Phase6InputError(
            _format_problems(
                [f"columns {columns} != the frozen schema {expected_columns}"],
                "multithreshold schema",
            )
        )
    n_runs = len(config.PHASE3_CANONICAL_RUN_IDS)
    grid = [float(p) for p in config.PHASE5_MULTI_THRESHOLD_PERCENTS]
    problems: List[str] = []
    seen_thresholds = [float(t) for t in mt_df["threshold_pct"].unique().tolist()]
    if seen_thresholds != grid:
        problems.append(
            f"threshold grid {seen_thresholds} != the frozen grid {grid}"
        )
    for pct in grid:
        block = mt_df[mt_df["threshold_pct"] == pct]
        if sorted(int(m) for m in block["n_methods"].tolist()) != list(range(n_runs + 1)):
            problems.append(
                f"threshold {pct:g}%: n_methods must cover exactly 0..{n_runs}"
            )
            continue
        counts = block.set_index("n_methods")["observation_count"]
        if counts.dtype.kind not in "iu" or (counts < 0).any():
            problems.append(f"threshold {pct:g}%: observation_count must be non-negative integers")
            continue
        if int(counts.sum()) != sample_size:
            problems.append(
                f"threshold {pct:g}%: counts sum to {int(counts.sum()):,} != the "
                f"sample size {sample_size:,} (not a partition)"
            )
        k_expected = int(round(sample_size * pct / 100.0))
        if int(block["k_nominal"].iloc[0]) != k_expected:
            problems.append(
                f"threshold {pct:g}%: k_nominal {int(block['k_nominal'].iloc[0])} != "
                f"round(n * pct / 100) ({k_expected})"
            )
        sources = set(block["selection_source"].unique().tolist())
        expected_source = (
            "canonical_saved_flags"
            if pct == config.PHASE5_CANONICAL_THRESHOLD_PCT
            else "derived_topk"
        )
        if sources != {expected_source}:
            problems.append(
                f"threshold {pct:g}%: selection_source {sorted(sources)} != "
                f"['{expected_source}']"
            )
    if problems:
        raise Phase6InputError(_format_problems(problems, "multithreshold integrity"))
    return mt_df


def validate_bootstrap_metrics_table(bm_df: pd.DataFrame) -> pd.DataFrame:
    """Validate the saved Phase 5A bootstrap metrics table.

    Checks: exact schema; one row per (highlighted run, metric) for the
    frozen run/metric sets; finite bounded values; ordered CIs; a single
    positive replicate count.
    """
    if not isinstance(bm_df, pd.DataFrame):
        raise Phase6InputError("bootstrap metrics table: expected a pandas DataFrame")
    columns = list(bm_df.columns)
    expected_columns = list(phase5_analysis.BOOTSTRAP_METRICS_COLUMNS)
    if columns != expected_columns:
        raise Phase6InputError(
            _format_problems(
                [f"columns {columns} != the frozen schema {expected_columns}"],
                "bootstrap metrics schema",
            )
        )
    expected_runs = list(config.PHASE5_BOOTSTRAP_RUN_IDS)
    expected_metrics = list(phase5_analysis.BOOTSTRAP_METRIC_NAMES)
    problems: List[str] = []
    runs = sorted(bm_df["run_id"].unique().tolist())
    metrics = sorted(bm_df["metric"].unique().tolist())
    if runs != sorted(expected_runs):
        problems.append(f"run set {runs} != the highlighted runs {sorted(expected_runs)}")
    if metrics != sorted(expected_metrics):
        problems.append(f"metric set {metrics} != {sorted(expected_metrics)}")
    if len(bm_df) != len(expected_runs) * len(expected_metrics):
        problems.append(
            f"row count {len(bm_df)} != n_runs x n_metrics "
            f"({len(expected_runs)} x {len(expected_metrics)})"
        )
    if bm_df.duplicated(subset=["run_id", "metric"]).any():
        problems.append("duplicate (run_id, metric) rows")
    for column in ("point_estimate", "bootstrap_mean", "bootstrap_std", "ci_lower", "ci_upper"):
        values = pd.to_numeric(bm_df[column], errors="coerce").to_numpy(dtype=np.float64)
        if not np.isfinite(values).all():
            problems.append(f"'{column}' contains non-finite value(s)")
        elif values.min() < 0.0 or values.max() > 1.0:
            problems.append(
                f"'{column}' outside [0, 1] (min {values.min():.6f}, max {values.max():.6f})"
            )
    if (bm_df["ci_lower"] > bm_df["ci_upper"]).any():
        problems.append("ci_lower exceeds ci_upper")
    n_replicates = bm_df["n_replicates"].unique().tolist()
    if len(n_replicates) != 1 or int(n_replicates[0]) < 1:
        problems.append(f"n_replicates must be a single positive integer, got {n_replicates}")
    if problems:
        raise Phase6InputError(_format_problems(problems, "bootstrap metrics integrity"))
    return bm_df


def validate_paired_differences_table(pd_df: pd.DataFrame) -> pd.DataFrame:
    """Validate the saved Phase 5A paired-differences table (one row per
    metric for the frozen IF_003 vs LOF_004 comparison)."""
    if not isinstance(pd_df, pd.DataFrame):
        raise Phase6InputError("paired differences table: expected a pandas DataFrame")
    columns = list(pd_df.columns)
    expected_columns = list(phase5_analysis.PAIRED_DIFFERENCES_COLUMNS)
    if columns != expected_columns:
        raise Phase6InputError(
            _format_problems(
                [f"columns {columns} != the frozen schema {expected_columns}"],
                "paired differences schema",
            )
        )
    expected_metrics = list(phase5_analysis.BOOTSTRAP_METRIC_NAMES)
    problems: List[str] = []
    run_a_values = pd_df["run_a"].unique().tolist()
    run_b_values = pd_df["run_b"].unique().tolist()
    if run_a_values != [config.PHASE5_PAIRED_COMPARISON_RUNS[0]]:
        problems.append(f"run_a must be '{config.PHASE5_PAIRED_COMPARISON_RUNS[0]}', got {run_a_values}")
    if run_b_values != [config.PHASE5_PAIRED_COMPARISON_RUNS[1]]:
        problems.append(f"run_b must be '{config.PHASE5_PAIRED_COMPARISON_RUNS[1]}', got {run_b_values}")
    metrics = sorted(pd_df["metric"].unique().tolist())
    if metrics != sorted(expected_metrics):
        problems.append(f"metric set {metrics} != {sorted(expected_metrics)}")
    if len(pd_df) != len(expected_metrics):
        problems.append(f"row count {len(pd_df)} != the number of metrics ({len(expected_metrics)})")
    for column in ("point_estimate", "bootstrap_mean", "bootstrap_std", "ci_lower", "ci_upper"):
        values = pd.to_numeric(pd_df[column], errors="coerce").to_numpy(dtype=np.float64)
        if not np.isfinite(values).all():
            problems.append(f"'{column}' contains non-finite value(s)")
        elif values.min() < -1.0 or values.max() > 1.0:
            problems.append(
                f"'{column}' outside [-1, 1] (min {values.min():.6f}, max {values.max():.6f})"
            )
    if (pd_df["ci_lower"] > pd_df["ci_upper"]).any():
        problems.append("ci_lower exceeds ci_upper")
    n_replicates = pd_df["n_replicates"].unique().tolist()
    if len(n_replicates) != 1 or int(n_replicates[0]) < 1:
        problems.append(f"n_replicates must be a single positive integer, got {n_replicates}")
    if problems:
        raise Phase6InputError(_format_problems(problems, "paired differences integrity"))
    return pd_df


def validate_phase5_metadata(
    payload: object,
    expected_run_ids: Sequence[str],
    expected_sample_size: int,
    expected_fraud_count: int,
) -> Dict:
    """Validate the Phase 5A provenance record (the fields Phase 6 consumes).

    Contract: a JSON object with ``phase == "5A"``; ``run_ids``;
    ``sample.sample_size`` / ``sample.fraud_count``; and the recorded input
    hash ``inputs.evaluation_dataset.sha256`` used for the cross-snapshot
    consistency check against the Phase 4 dataset actually consumed here.
    """
    if not isinstance(payload, dict):
        raise Phase6InputError(
            f"Phase 5A run metadata must be a JSON object, got {type(payload).__name__}"
        )
    problems: List[str] = []
    if str(payload.get("phase")) != "5A":
        problems.append(f"'phase' must be '5A', got {payload.get('phase')!r}")
    run_ids = payload.get("run_ids")
    if not isinstance(run_ids, list) or list(run_ids) != list(expected_run_ids):
        problems.append("'run_ids' must list the canonical runs in order")
    sample = payload.get("sample")
    if not isinstance(sample, dict):
        problems.append("'sample' must be a JSON object")
    else:
        s_size = sample.get("sample_size")
        if s_size != expected_sample_size:
            got_str = f"{s_size:,}" if isinstance(s_size, (int, float)) else str(s_size)
            exp_str = f"{expected_sample_size:,}"
            problems.append(f"sample.sample_size {got_str} != the expected {exp_str}")
        f_count = sample.get("fraud_count")
        if f_count != expected_fraud_count:
            problems.append(f"sample.fraud_count {f_count} != the expected {expected_fraud_count}")
    inputs = payload.get("inputs")
    if not isinstance(inputs, dict) or not isinstance(inputs.get("evaluation_dataset"), dict):
        problems.append("'inputs.evaluation_dataset' must be a JSON object")
    else:
        entry = inputs["evaluation_dataset"]
        if not isinstance(entry.get("sha256"), str) or len(entry["sha256"]) != 64:
            problems.append(
                "'inputs.evaluation_dataset.sha256' must be recorded (64 hex "
                "characters) for the cross-snapshot consistency check"
            )
    if problems:
        raise Phase6InputError(_format_problems(problems, "Phase 5A run metadata"))
    return payload


# ---------------------------------------------------------------------------
# Input manifests (optional, verified when present; honest legacy fallback)
# ---------------------------------------------------------------------------

def _check_input_manifest(
    manifest_path: Path, required_artifacts: Sequence[str], what: str
) -> Dict:
    """Verify an integrity manifest covering consumed inputs, or classify
    the inputs as a legacy unmanifested set.

    Verification happens BEFORE anything is consumed; a manifest that does
    not cover every required artifact is rejected rather than silently
    accepted. When no manifest exists, the inputs are marked legacy:
    strict structural validation and SHA-256 recording are the integrity
    controls and verification is never claimed falsely.
    """
    manifest_path = Path(manifest_path)
    if not manifest_path.is_file():
        return {
            "present": False,
            "verified": False,
            "mode": "legacy_unmanifested",
            "path": str(manifest_path),
            "note": (
                f"No {what} exists next to the consumed inputs. Strict "
                "structural validation was applied and the input SHA-256 "
                "hashes are recorded in the run metadata. Manifest "
                "verification was NOT performed."
            ),
        }
    manifest = load_manifest(manifest_path)
    report = verify_manifest(
        manifest,
        base_dir=manifest_path.parent,
        required_artifacts=tuple(required_artifacts),
    )
    return {
        "present": True,
        "verified": True,
        "mode": "manifest_verified",
        "path": str(manifest_path),
        "artifacts": report,
    }


def load_phase6_tables(
    phase5_dir: Path,
    expected_run_ids: Sequence[str],
    sample_size: int,
    fraud_count: int,
) -> Dict:
    """Load and validate every consumed Phase 5A table.

    Returns ``{"spearman", "jaccard", "hypergeometric", "agreement_groups",
    "multithreshold", "bootstrap_metrics", "paired_differences"}`` -- the
    matrices as run-indexed DataFrames, the hypergeometric summary as a
    validated dict and the rest as validated DataFrames.
    """
    phase5_dir = Path(phase5_dir)
    expected_run_ids = list(expected_run_ids)

    spearman_df = validate_matrix_table(
        pd.read_csv(phase5_dir / config.PHASE5_PAIRWISE_SPEARMAN_FILENAME, index_col=0),
        expected_run_ids,
        "phase5_pairwise_spearman.csv",
        (-1.0, 1.0),
    )
    jaccard_df = validate_matrix_table(
        pd.read_csv(phase5_dir / config.PHASE5_PAIRWISE_JACCARD_FILENAME, index_col=0),
        expected_run_ids,
        "phase5_pairwise_jaccard_1pct.csv",
        (0.0, 1.0),
    )
    hypergeometric = validate_hypergeometric_table(
        _read_required_csv(
            phase5_dir / config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME,
            "Phase 5A hypergeometric overlap summary",
        )
    )
    agreement_groups = validate_agreement_groups_table(
        _read_required_csv(
            phase5_dir / config.PHASE5_AGREEMENT_GROUPS_FILENAME,
            "Phase 5A agreement-group table",
        ),
        (IF_RUN_ID, LOF_RUN_ID),
        sample_size,
        fraud_count,
    )
    multithreshold = validate_multithreshold_table(
        _read_required_csv(
            phase5_dir / config.PHASE5_MULTITHRESHOLD_AGREEMENT_FILENAME,
            "Phase 5A multi-threshold agreement table",
        ),
        sample_size,
    )
    bootstrap_metrics = validate_bootstrap_metrics_table(
        _read_required_csv(
            phase5_dir / config.PHASE5_BOOTSTRAP_METRICS_FILENAME,
            "Phase 5A bootstrap metrics table",
        )
    )
    paired_differences = validate_paired_differences_table(
        _read_required_csv(
            phase5_dir / config.PHASE5_PAIRED_BOOTSTRAP_DIFFERENCES_FILENAME,
            "Phase 5A paired bootstrap differences table",
        )
    )
    return {
        "spearman": spearman_df,
        "jaccard": jaccard_df,
        "hypergeometric": hypergeometric,
        "agreement_groups": agreement_groups,
        "multithreshold": multithreshold,
        "bootstrap_metrics": bootstrap_metrics,
        "paired_differences": paired_differences,
    }


# ---------------------------------------------------------------------------
# C. Shared loading / validation with row-level cross-checks
# ---------------------------------------------------------------------------

def _resolve_input_paths(
    phase5_dir: Optional[Path],
    phase4_dataset_path: Optional[Path],
) -> Tuple[Path, Path]:
    return (
        Path(phase5_dir) if phase5_dir is not None else config.DEFAULT_PHASE5_OUTPUT_DIR,
        Path(phase4_dataset_path)
        if phase4_dataset_path is not None
        else config.PHASE4_EVALUATION_DATASET_PATH,
    )


def _artifact_info(path: Path) -> Dict:
    """Path + SHA-256 + size for a consumed input (provenance record)."""
    from mplad.common.manifest import artifact_entry

    info = artifact_entry(path)
    return {"path": str(path), **info}


def _safe_div(numerator: float, denominator: float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def _load_and_validate_inputs(
    phase5_dir: Path,
    phase4_dataset_path: Path,
    expected_run_ids: Optional[Sequence[str]],
    expected_sample_size: int,
    verbose: bool = True,
) -> Dict:
    """Load and validate every Phase 6 input; compute no analysis.

    Order of operations: the optional Phase 5A and Phase 4 output manifests
    are verified FIRST (hash-verification genuinely happens before the
    artifacts are consumed), then the Phase 4 evaluation dataset is loaded
    and validated (reusing the hardened Phase 5A validators, with the
    canonical sample-size requirement enforced), then the Phase 5A
    provenance record is validated and cross-checked against the dataset
    hash (the cross-snapshot consistency guarantee), then the Phase 5A
    tables are loaded, validated and cross-checked against the row-level
    data. Every cross-check result is recorded for the scorecard.
    """
    if expected_run_ids is None:
        expected_run_ids = list(config.PHASE3_CANONICAL_RUN_IDS)
    expected_run_ids = list(expected_run_ids)

    # --- input manifests -------------------------------------------------
    consumed_phase5_names = (
        config.PHASE5_PAIRWISE_SPEARMAN_FILENAME,
        config.PHASE5_PAIRWISE_JACCARD_FILENAME,
        config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME,
        config.PHASE5_AGREEMENT_GROUPS_FILENAME,
        config.PHASE5_MULTITHRESHOLD_AGREEMENT_FILENAME,
        config.PHASE5_BOOTSTRAP_METRICS_FILENAME,
        config.PHASE5_PAIRED_BOOTSTRAP_DIFFERENCES_FILENAME,
        config.PHASE5_RUN_METADATA_FILENAME,
    )
    if verbose:
        print("Checking for the Phase 5A integrity manifest ...")
    phase5_manifest = _check_input_manifest(
        phase5_dir / config.PHASE6_INPUT_MANIFEST_FILENAME,
        consumed_phase5_names,
        "Phase 5A commit manifest",
    )
    if verbose:
        print(
            f"  manifest FOUND and VERIFIED: {phase5_manifest['path']} "
            f"({len(phase5_manifest['artifacts'])} artifact(s) hash-checked)"
            if phase5_manifest["mode"] == "manifest_verified"
            else f"  no manifest at {phase5_manifest['path']} -> LEGACY "
            "UNMANIFESTED set: strict structural validation + SHA-256 "
            "recording (verification NOT claimed)"
        )
    if verbose:
        print("Checking for the Phase 4 integrity manifest ...")
    phase4_manifest = _check_input_manifest(
        Path(phase4_dataset_path).parent / config.PHASE6_PHASE4_MANIFEST_FILENAME,
        (Path(phase4_dataset_path).name,),
        "Phase 4 commit manifest",
    )
    if verbose:
        print(
            f"  manifest FOUND and VERIFIED: {phase4_manifest['path']}"
            if phase4_manifest["mode"] == "manifest_verified"
            else f"  no manifest at {phase4_manifest['path']} -> LEGACY "
            "UNMANIFESTED input: strict structural validation + SHA-256 "
            "recording (verification NOT claimed)"
        )

    # --- Phase 4 evaluation dataset (hardened Phase 5A validators) --------
    if verbose:
        print(f"Loading Phase 4 evaluation dataset from {phase4_dataset_path} ...")
    dataset_df = phase5_analysis.load_phase4_dataset(
        phase4_dataset_path, expected_run_ids=expected_run_ids
    )
    dataset_summary = phase5_analysis.validate_phase4_dataset(
        dataset_df, expected_run_ids=expected_run_ids
    )
    sample_size = dataset_summary["sample_size"]
    fraud_count = dataset_summary["fraud_count"]
    if sample_size != expected_sample_size:
        raise Phase6InputError(
            f"the primary dataset must contain exactly {expected_sample_size:,} "
            f"observations (the canonical experiment size); it carries "
            f"{sample_size:,}. Pass --expected-sample-size deliberately if a "
            "non-canonical replica is being analysed."
        )
    if verbose:
        print(
            f"  dataset: {dataset_summary['total_rows']:,} rows = "
            f"{len(expected_run_ids)} runs x {sample_size:,} observations "
            f"(identical row_id sequence across runs, verified); "
            f"{fraud_count} fraud labels "
            f"(prevalence {dataset_summary['fraud_prevalence']:.6f})"
        )
    aligned = phase5_analysis.extract_aligned_runs(dataset_df, expected_run_ids)

    # --- Phase 5A provenance record + cross-snapshot hash check -----------
    metadata_path = phase5_dir / config.PHASE5_RUN_METADATA_FILENAME
    if verbose:
        print(f"Loading Phase 5A run metadata from {metadata_path} ...")
    _require_file(metadata_path, "Phase 5A run metadata")
    with open(metadata_path, "r", encoding="utf-8") as f:
        phase5_metadata = json.load(f)
    phase5_metadata = validate_phase5_metadata(
        phase5_metadata, expected_run_ids, sample_size, fraud_count
    )
    from mplad.common.manifest import artifact_entry

    recorded_hash = phase5_metadata["inputs"]["evaluation_dataset"]["sha256"].lower()
    actual_hash = artifact_entry(phase4_dataset_path)["sha256"].lower()
    if recorded_hash != actual_hash:
        raise Phase6InputError(
            "cross-snapshot inconsistency: the Phase 5A provenance record was "
            "computed against a Phase 4 evaluation dataset with SHA-256 "
            f"{recorded_hash}, but the dataset being consumed now hashes to "
            f"{actual_hash}. The Phase 5A tables and the row-level data must "
            "come from the SAME Phase 4 execution -- re-run Phase 5A against "
            "the current Phase 4 outputs before running Phase 6."
        )
    if verbose:
        print("  cross-snapshot check: Phase 5A input hash matches the consumed dataset")

    # --- Phase 5A tables ---------------------------------------------------
    if verbose:
        print(f"Loading Phase 5A tables from {phase5_dir} ...")
    tables = load_phase6_tables(phase5_dir, expected_run_ids, sample_size, fraud_count)

    # --- lightweight cross-checks against the row-level data ---------------
    row_level_checks: List[Dict] = []
    problems: List[str] = []

    def _record_check(metric: str, value, source_field: str, note: str) -> None:
        row_level_checks.append(
            {
                "metric": metric,
                "value": value,
                "source_artifact": config.PHASE4_EVALUATION_DATASET_FILENAME,
                "source_field": source_field,
                "note": note,
            }
        )

    flags_if = aligned["runs"][IF_RUN_ID]["flag"] == 1
    flags_lof = aligned["runs"][LOF_RUN_ID]["flag"] == 1
    labels = aligned["labels"] == 1
    masks = {
        "both": flags_if & flags_lof,
        "if_only": flags_if & ~flags_lof,
        "lof_only": ~flags_if & flags_lof,
        "neither": ~flags_if & ~flags_lof,
    }
    hyper = tables["hypergeometric"]
    groups_table = tables["agreement_groups"].set_index("group")

    if hyper["run_a"] != IF_RUN_ID or hyper["run_b"] != LOF_RUN_ID:
        problems.append(
            f"hypergeometric summary covers ({hyper['run_a']}, {hyper['run_b']}), "
            f"expected ({IF_RUN_ID}, {LOF_RUN_ID})"
        )
    if hyper["n_observations"] != sample_size:
        problems.append(
            f"hypergeometric n {hyper['n_observations']:,} != sample size {sample_size:,}"
        )

    row_if_flagged = int(np.count_nonzero(flags_if))
    row_lof_flagged = int(np.count_nonzero(flags_lof))
    if hyper["run_a_flagged"] != row_if_flagged or hyper["run_b_flagged"] != row_lof_flagged:
        problems.append(
            "hypergeometric flagged counts disagree with the saved flags in the "
            f"Phase 4 evaluation dataset ({hyper['run_a_flagged']}/"
            f"{hyper['run_b_flagged']} vs {row_if_flagged}/{row_lof_flagged})"
        )
    _record_check(
        "recompute_if003_flagged_count", row_if_flagged,
        "count(flag == 1) for run_id == 'IF_003'",
        f"matches {config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME}:run_a_flagged",
    )
    _record_check(
        "recompute_lof004_flagged_count", row_lof_flagged,
        "count(flag == 1) for run_id == 'LOF_004'",
        f"matches {config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME}:run_b_flagged",
    )

    row_intersection = int(np.count_nonzero(masks["both"]))
    row_union = int(np.count_nonzero(flags_if | flags_lof))
    if hyper["observed_intersection"] != row_intersection:
        problems.append(
            f"hypergeometric observed intersection {hyper['observed_intersection']} "
            f"!= row-level both-flagged count {row_intersection}"
        )
    if hyper["union_size"] != row_union:
        problems.append(
            f"hypergeometric union {hyper['union_size']} != row-level union {row_union}"
        )
    _record_check(
        "recompute_observed_intersection", row_intersection,
        "count(if_flag == 1 and lof_flag == 1)",
        f"matches {config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME}:observed_intersection",
    )
    _record_check(
        "recompute_union_size", row_union,
        "count(if_flag == 1 or lof_flag == 1)",
        f"matches {config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME}:union_size",
    )

    saved_jaccard = float(tables["jaccard"].loc[IF_RUN_ID, LOF_RUN_ID])
    row_jaccard = _safe_div(row_intersection, row_union)
    if not math.isclose(saved_jaccard, row_jaccard, rel_tol=0.0, abs_tol=1e-12):
        problems.append(
            f"saved top-1% Jaccard [{IF_RUN_ID}, {LOF_RUN_ID}] = {saved_jaccard:.6f} != "
            f"row-level flag Jaccard {row_jaccard:.6f}"
        )
    _record_check(
        "recompute_jaccard_if003_lof004", row_jaccard,
        "|if_flags AND lof_flags| / |if_flags OR lof_flags|",
        f"matches {config.PHASE5_PAIRWISE_JACCARD_FILENAME}:[{IF_RUN_ID}, {LOF_RUN_ID}]",
    )

    for group_key, mask in masks.items():
        table_count = int(groups_table.loc[group_key, "observation_count"])
        row_count = int(np.count_nonzero(mask))
        if table_count != row_count:
            problems.append(
                f"agreement group '{group_key}': table count {table_count} != "
                f"row-level count {row_count}"
            )
        table_frauds = int(groups_table.loc[group_key, "fraud_count"])
        row_frauds = int(np.count_nonzero(mask & labels))
        if table_frauds != row_frauds:
            problems.append(
                f"agreement group '{group_key}': table frauds {table_frauds} != "
                f"row-level frauds {row_frauds}"
            )
        _record_check(
            f"recompute_{group_key}_count", row_count,
            f"count of the '{group_key}' flag combination",
            f"matches {config.PHASE5_AGREEMENT_GROUPS_FILENAME}:observation_count "
            f"[group={group_key}]",
        )
        _record_check(
            f"recompute_{group_key}_fraud_count", row_frauds,
            f"count of the '{group_key}' flag combination with Class == 1",
            f"matches {config.PHASE5_AGREEMENT_GROUPS_FILENAME}:fraud_count "
            f"[group={group_key}]",
        )

    # Ten-run union / intersection at the canonical 1% budget vs the saved
    # counts-by-number-of-methods table.
    any_flag = np.zeros(sample_size, dtype=bool)
    all_flag = np.ones(sample_size, dtype=bool)
    for run_id in expected_run_ids:
        run_flags = aligned["runs"][run_id]["flag"] == 1
        any_flag |= run_flags
        all_flag &= run_flags
    canonical_block = tables["multithreshold"][
        tables["multithreshold"]["threshold_pct"] == config.PHASE5_CANONICAL_THRESHOLD_PCT
    ].set_index("n_methods")["observation_count"]
    saved_any = int(canonical_block.loc[[m for m in canonical_block.index if m >= 1]].sum())
    saved_all = int(canonical_block.loc[10])
    row_any = int(np.count_nonzero(any_flag))
    row_all = int(np.count_nonzero(all_flag))
    if saved_any != row_any:
        problems.append(
            f"multithreshold table: observations selected by >= 1 method at 1% "
            f"({saved_any:,}) != row-level ten-run union ({row_any:,})"
        )
    if saved_all != row_all:
        problems.append(
            f"multithreshold table: observations selected by all 10 methods at "
            f"1% ({saved_all}) != row-level ten-run intersection ({row_all})"
        )
    _record_check(
        "recompute_ten_run_union_at_1pct", row_any,
        "count(flag == 1 for at least one of the ten runs)",
        f"matches {config.PHASE5_MULTITHRESHOLD_AGREEMENT_FILENAME}: "
        "observation_count summed over n_methods >= 1 at threshold_pct = 1.0",
    )
    _record_check(
        "recompute_ten_run_intersection_at_1pct", row_all,
        "count(flag == 1 for all ten runs)",
        f"matches {config.PHASE5_MULTITHRESHOLD_AGREEMENT_FILENAME}: "
        "observation_count at n_methods = 10 at threshold_pct = 1.0",
    )

    # Saved bootstrap point estimates vs row-level flag arithmetic (the
    # score/curve metrics are Phase 4 quantities and are never recomputed).
    bm = tables["bootstrap_metrics"].set_index(["run_id", "metric"])["point_estimate"]
    for run_id in config.PHASE5_BOOTSTRAP_RUN_IDS:
        run_flags = aligned["runs"][run_id]["flag"] == 1
        tp = int(np.count_nonzero(run_flags & labels))
        k = int(np.count_nonzero(run_flags))
        precision = _safe_div(tp, k)
        recall = _safe_div(tp, fraud_count)
        f1 = _safe_div(2.0 * precision * recall, precision + recall)
        for metric_name, row_value in (
            ("precision_at_1pct", precision),
            ("recall_at_1pct", recall),
            ("f1_at_1pct", f1),
        ):
            saved_value = float(bm.loc[(run_id, metric_name)])
            if not math.isclose(saved_value, row_value, rel_tol=0.0, abs_tol=1e-9):
                problems.append(
                    f"bootstrap point estimate {run_id}/{metric_name} "
                    f"({saved_value:.6f}) != row-level value ({row_value:.6f})"
                )
            _record_check(
                f"recompute_{run_id.lower()}_{metric_name}", row_value,
                f"flag-based {metric_name} for run_id == '{run_id}'",
                f"matches {config.PHASE5_BOOTSTRAP_METRICS_FILENAME}:point_estimate "
                f"[run_id={run_id}, metric={metric_name}]",
            )

    # Paired-difference identity (saved-vs-saved arithmetic consistency).
    pd_table = tables["paired_differences"].set_index("metric")
    for metric_name in phase5_analysis.BOOTSTRAP_METRIC_NAMES:
        paired_point = float(pd_table.loc[metric_name, "point_estimate"])
        difference = float(bm.loc[(LOF_RUN_ID, metric_name)]) - float(
            bm.loc[(IF_RUN_ID, metric_name)]
        )
        if not math.isclose(paired_point, difference, rel_tol=0.0, abs_tol=1e-9):
            problems.append(
                f"paired difference for {metric_name} ({paired_point:.6f}) != "
                f"{LOF_RUN_ID} - {IF_RUN_ID} point estimates ({difference:.6f})"
            )
    _record_check(
        "check_paired_difference_identity", "consistent",
        "point_estimate[pd] == point_estimate[LOF_004] - point_estimate[IF_003] for all 5 metrics",
        f"matches {config.PHASE5_PAIRED_BOOTSTRAP_DIFFERENCES_FILENAME} against "
        f"{config.PHASE5_BOOTSTRAP_METRICS_FILENAME}",
    )
    _record_check(
        "check_cross_snapshot_dataset_hash", "match",
        "SHA-256 of the consumed Phase 4 evaluation dataset",
        "matches the hash recorded in "
        f"{config.PHASE5_RUN_METADATA_FILENAME}:inputs.evaluation_dataset.sha256",
    )
    _record_check(
        "check_phase5a_sample_consistency", "match",
        "sample size and fraud count of the consumed dataset",
        f"matches {config.PHASE5_RUN_METADATA_FILENAME}:sample.sample_size and "
        "sample.fraud_count",
    )

    if problems:
        raise Phase6InputError(
            _format_problems(problems, "Phase 5A table / row-level consistency")
        )
    if verbose:
        print(
            "  cross-checks: flagged counts, intersection, union, group "
            "composition, ten-run union/intersection, saved Jaccard and the "
            "flag-based bootstrap point estimates all match the row-level data"
        )

    inputs_info = {
        "phase5_spearman": _artifact_info(phase5_dir / config.PHASE5_PAIRWISE_SPEARMAN_FILENAME),
        "phase5_jaccard_1pct": _artifact_info(phase5_dir / config.PHASE5_PAIRWISE_JACCARD_FILENAME),
        "phase5_hypergeometric_overlap": _artifact_info(
            phase5_dir / config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME
        ),
        "phase5_agreement_groups": _artifact_info(
            phase5_dir / config.PHASE5_AGREEMENT_GROUPS_FILENAME
        ),
        "phase5_multithreshold_agreement": _artifact_info(
            phase5_dir / config.PHASE5_MULTITHRESHOLD_AGREEMENT_FILENAME
        ),
        "phase5_bootstrap_metrics": _artifact_info(
            phase5_dir / config.PHASE5_BOOTSTRAP_METRICS_FILENAME
        ),
        "phase5_paired_bootstrap_differences": _artifact_info(
            phase5_dir / config.PHASE5_PAIRED_BOOTSTRAP_DIFFERENCES_FILENAME
        ),
        "phase5_run_metadata": _artifact_info(metadata_path),
        "phase4_evaluation_dataset": _artifact_info(phase4_dataset_path),
    }

    return {
        "phase5_manifest": phase5_manifest,
        "phase4_manifest": phase4_manifest,
        "dataset_df": dataset_df,
        "dataset_summary": dataset_summary,
        "aligned": aligned,
        "phase5_metadata": phase5_metadata,
        "tables": tables,
        "inputs_info": inputs_info,
        "row_level_checks": row_level_checks,
        "sample": {
            "sample_size": sample_size,
            "fraud_count": fraud_count,
            "fraud_prevalence": dataset_summary["fraud_prevalence"],
            "per_run_flagged_counts": dataset_summary["per_run_flagged_counts"],
        },
    }


def _reference_check_context(validated: Dict) -> Dict:
    """The reference-checkable values, all derived from source artifacts
    (and already cross-checked against the row-level data)."""
    tables = validated["tables"]
    hyper = tables["hypergeometric"]
    groups = tables["agreement_groups"].set_index("group")
    context: Dict = {
        "sample_size": validated["sample"]["sample_size"],
        "fraud_label_count": validated["sample"]["fraud_count"],
        "if003_flagged_count": int(hyper["run_a_flagged"]),
        "lof004_flagged_count": int(hyper["run_b_flagged"]),
        "observed_intersection": int(hyper["observed_intersection"]),
        "union_size": int(hyper["union_size"]),
        "spearman_if003_lof004": float(tables["spearman"].loc[IF_RUN_ID, LOF_RUN_ID]),
        "jaccard_if003_lof004": float(tables["jaccard"].loc[IF_RUN_ID, LOF_RUN_ID]),
        "enrichment_observed_over_expected": float(
            hyper["enrichment_observed_over_expected"]
        ),
        "log10_upper_tail_probability": float(hyper["log10_survival"]),
    }
    for group_key in GROUP_KEYS:
        context[f"{group_key}_observation_count"] = int(
            groups.loc[group_key, "observation_count"]
        )
        context[f"{group_key}_fraud_count"] = int(groups.loc[group_key, "fraud_count"])
    return context


def validate_against_references(context: Dict) -> List[str]:
    """Compare every reference-checkable value with its historical
    acceptance reference; return the list of mismatch problems (empty =
    pass). Integer references compare exactly; float references compare
    within the recorded absolute tolerance (they are published roundings).
    A missing or non-numeric value is a mismatch, never a pass."""
    problems: List[str] = []
    for metric, reference in PHASE6_REFERENCE_VALUES.items():
        if metric not in context:
            problems.append(f"'{metric}' is missing from the derived values")
            continue
        derived = context[metric]
        if isinstance(reference, int) and not isinstance(reference, bool):
            if not isinstance(derived, (int, np.integer)) or int(derived) != reference:
                problems.append(
                    f"'{metric}': derived {derived!r} != the canonical reference "
                    f"{reference} (exact comparison)"
                )
        else:
            try:
                derived_float = float(derived)
            except (TypeError, ValueError):
                problems.append(f"'{metric}': derived value {derived!r} is not numeric")
                continue
            tolerance = PHASE6_REFERENCE_TOLERANCES.get(metric, 0.0)
            if not math.isclose(derived_float, float(reference), rel_tol=0.0, abs_tol=tolerance):
                problems.append(
                    f"'{metric}': derived {derived_float:.6f} differs from the "
                    f"canonical reference {reference} by more than the allowed "
                    f"tolerance {tolerance:g}"
                )
    return problems


# ---------------------------------------------------------------------------
# D. Consistency context (single derived-value store for scorecard + report)
# ---------------------------------------------------------------------------

def _family_block_stats(matrix_df: pd.DataFrame, run_ids: Sequence[str]) -> Dict:
    """Within-IF / within-LOF / cross-method summary statistics of a saved
    10x10 matrix (off-diagonal entries only inside each family block; the
    cross block needs no diagonal exclusion)."""
    if_runs = [r for r in run_ids if r.startswith("IF_")]
    lof_runs = [r for r in run_ids if r.startswith("LOF_")]

    def _stats(values: np.ndarray) -> Dict:
        return {
            "mean": float(np.mean(values)),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
        }

    within_if = matrix_df.loc[if_runs, if_runs].to_numpy(dtype=np.float64)
    within_lof = matrix_df.loc[lof_runs, lof_runs].to_numpy(dtype=np.float64)
    cross = matrix_df.loc[if_runs, lof_runs].to_numpy(dtype=np.float64).ravel()
    return {
        "within_if": _stats(within_if[~np.eye(len(if_runs), dtype=bool)]),
        "within_lof": _stats(within_lof[~np.eye(len(lof_runs), dtype=bool)]),
        "cross_method": _stats(cross),
    }


def build_consistency_context(validated: Dict, assignments_summary: Dict) -> Dict:
    """Assemble every value the scorecard and the report consume.

    Every saved quantity is READ from a Phase 5A table (never recomputed);
    the workload rows are pure arithmetic over the saved group counts; the
    assignment summary (join-based) has already been cross-checked against
    the same tables.
    """
    tables = validated["tables"]
    hyper = tables["hypergeometric"]
    groups_table = tables["agreement_groups"].set_index("group")
    run_ids = list(validated["aligned"]["run_ids"])
    sample_size = validated["sample"]["sample_size"]
    fraud_count = validated["sample"]["fraud_count"]

    # --- reference-checkable values (shared with _reference_check_context) -
    context = _reference_check_context(validated)
    context.update(
        {
            "if_run_id": IF_RUN_ID,
            "lof_run_id": LOF_RUN_ID,
            "threshold_pct": config.PHASE5_CANONICAL_THRESHOLD_PCT,
            "fraud_prevalence": validated["sample"]["fraud_prevalence"],
            "canonical_run_count": len(run_ids),
            "expected_intersection_under_null": float(hyper["expected_intersection"]),
            "null_model_description": str(hyper["null_model"]),
            "survival_underflow_note": _tail_reporting_note(float(hyper["log10_survival"])),
        }
    )

    # --- per-group detail from the saved table -----------------------------
    groups: Dict[str, Dict] = {}
    for group_key in GROUP_KEYS:
        groups[group_key] = {
            "observation_count": int(groups_table.loc[group_key, "observation_count"]),
            "fraud_count": int(groups_table.loc[group_key, "fraud_count"]),
            "fraud_proportion": float(groups_table.loc[group_key, "fraud_proportion"]),
            "recall_contribution": float(groups_table.loc[group_key, "recall_contribution"]),
        }
    context["groups"] = groups

    # --- per-detector overlap fractions (deliberately distinct from Jaccard)
    context["if003_flagged_share_overlapping"] = _safe_div(
        context["observed_intersection"], context["if003_flagged_count"]
    )
    context["lof004_flagged_share_overlapping"] = _safe_div(
        context["observed_intersection"], context["lof004_flagged_count"]
    )

    # --- review-workload policies (pure arithmetic over saved group rows) ---
    both, if_only = groups["both"], groups["if_only"]
    lof_only, neither = groups["lof_only"], groups["neither"]
    if_frauds = both["fraud_count"] + if_only["fraud_count"]
    lof_frauds = both["fraud_count"] + lof_only["fraud_count"]
    union_frauds = if_frauds + lof_frauds - both["fraud_count"]

    def _policy(reviews: int, frauds: int) -> Dict:
        return {
            "reviews": int(reviews),
            "sample_share": _safe_div(reviews, sample_size),
            "frauds": int(frauds),
            "precision": _safe_div(frauds, reviews),
            "recall": _safe_div(frauds, fraud_count),
        }

    context["workload"] = {
        "both_only": _policy(both["observation_count"], both["fraud_count"]),
        "if003_flags": _policy(context["if003_flagged_count"], if_frauds),
        "lof004_flags": _policy(context["lof004_flagged_count"], lof_frauds),
        "union": _policy(context["union_size"], union_frauds),
    }
    context["neither_fraud_count"] = neither["fraud_count"]

    # --- family consistency from the saved matrices ------------------------
    context["within_if_spearman"] = _family_block_stats(tables["spearman"], run_ids)["within_if"]
    context["within_lof_spearman"] = _family_block_stats(tables["spearman"], run_ids)["within_lof"]
    context["cross_method_spearman"] = _family_block_stats(tables["spearman"], run_ids)["cross_method"]
    context["within_if_jaccard"] = _family_block_stats(tables["jaccard"], run_ids)["within_if"]
    context["within_lof_jaccard"] = _family_block_stats(tables["jaccard"], run_ids)["within_lof"]
    context["cross_method_jaccard"] = _family_block_stats(tables["jaccard"], run_ids)["cross_method"]

    # --- threshold sensitivity from the saved counts-by-methods table ------
    thresholds: List[Dict] = []
    mt = tables["multithreshold"]
    for pct in config.PHASE5_MULTI_THRESHOLD_PERCENTS:
        block = mt[mt["threshold_pct"] == pct].set_index("n_methods")["observation_count"]
        thresholds.append(
            {
                "pct": float(pct),
                "k": int(mt[mt["threshold_pct"] == pct]["k_nominal"].iloc[0]),
                "source": str(mt[mt["threshold_pct"] == pct]["selection_source"].iloc[0]),
                "any_method_count": int(block.loc[[m for m in block.index if m >= 1]].sum()),
                "all_methods_count": int(block.loc[len(run_ids)]),
                "single_method_count": int(block.loc[1]),
            }
        )
    context["thresholds"] = thresholds

    # --- bootstrap context (read, never recomputed) -------------------------
    bm = tables["bootstrap_metrics"].set_index(["run_id", "metric"])
    precision_context: Dict[str, Dict] = {}
    for run_id in config.PHASE5_BOOTSTRAP_RUN_IDS:
        precision_context[run_id] = {
            "point": float(bm.loc[(run_id, "precision_at_1pct"), "point_estimate"]),
            "ci_lower": float(bm.loc[(run_id, "precision_at_1pct"), "ci_lower"]),
            "ci_upper": float(bm.loc[(run_id, "precision_at_1pct"), "ci_upper"]),
        }
    pd_row = tables["paired_differences"].set_index("metric").loc["precision_at_1pct"]
    context["bootstrap"] = {
        "n_replicates": int(tables["bootstrap_metrics"]["n_replicates"].iloc[0]),
        "ci_level": config.PHASE5_CI_LEVEL,
        "precision_at_1pct": precision_context,
        "paired_difference": {
            "comparison": str(pd_row["comparison"]),
            "point": float(pd_row["point_estimate"]),
            "ci_lower": float(pd_row["ci_lower"]),
            "ci_upper": float(pd_row["ci_upper"]),
        },
    }

    # --- provenance summary (deterministic: names + hash prefixes) ----------
    inputs_info = validated["inputs_info"]
    roles = {
        "phase4_evaluation_dataset": "row-level scores, saved 1% flags, labels",
        "phase5_spearman": "10x10 Spearman rank-correlation matrix",
        "phase5_jaccard_1pct": "10x10 top-1% Jaccard matrix (saved flags)",
        "phase5_hypergeometric_overlap": "overlap-test summary (IF_003 vs LOF_004)",
        "phase5_agreement_groups": "four-group composition (IF_003 vs LOF_004)",
        "phase5_multithreshold_agreement": "counts by number of selecting methods",
        "phase5_bootstrap_metrics": "bootstrap point estimates and CIs",
        "phase5_paired_bootstrap_differences": "paired LOF_004 - IF_003 differences",
        "phase5_run_metadata": "Phase 5A provenance (input hashes, conventions)",
    }
    artifact_names = {
        "phase4_evaluation_dataset": config.PHASE4_EVALUATION_DATASET_FILENAME,
        "phase5_spearman": config.PHASE5_PAIRWISE_SPEARMAN_FILENAME,
        "phase5_jaccard_1pct": config.PHASE5_PAIRWISE_JACCARD_FILENAME,
        "phase5_hypergeometric_overlap": config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME,
        "phase5_agreement_groups": config.PHASE5_AGREEMENT_GROUPS_FILENAME,
        "phase5_multithreshold_agreement": config.PHASE5_MULTITHRESHOLD_AGREEMENT_FILENAME,
        "phase5_bootstrap_metrics": config.PHASE5_BOOTSTRAP_METRICS_FILENAME,
        "phase5_paired_bootstrap_differences": config.PHASE5_PAIRED_BOOTSTRAP_DIFFERENCES_FILENAME,
        "phase5_run_metadata": config.PHASE5_RUN_METADATA_FILENAME,
    }
    manifest_status = {
        "phase4_evaluation_dataset": validated["phase4_manifest"]["mode"],
    }
    context["inputs"] = [
        {
            "artifact": artifact_names[key],
            "role": roles[key],
            "sha256_12": inputs_info[key]["sha256"][:12],
            "manifest": manifest_status.get(key, validated["phase5_manifest"]["mode"]),
        }
        for key in roles
    ]
    context["exploratory_caveat"] = EXPLORATORY_CAVEAT
    context["assignment_summary"] = assignments_summary
    return context


# ---------------------------------------------------------------------------
# E. Consistency scorecard
# ---------------------------------------------------------------------------

def _format_scorecard_value(value) -> Tuple[str, str]:
    """Deterministic value formatting: ints exactly, floats at 6 decimals,
    strings verbatim (with a hard non-finite guard)."""
    if isinstance(value, bool):
        raise Phase6Error(f"boolean scorecard values are not supported: {value!r}")
    if isinstance(value, (int, np.integer)):
        return str(int(value)), "int"
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(float(value)):
            raise Phase6Error(f"non-finite scorecard value for metric: {value!r}")
        return f"{float(value):.6f}", "float"
    return str(value), "string"


def build_scorecard(context: Dict, row_level_checks: Sequence[Dict]) -> pd.DataFrame:
    """Build the compact consistency scorecard.

    One row per metric with its section, formatted value, value type, the
    SOURCE ARTIFACT and the ORIGINAL METRIC FIELD it was read from, and a
    short note. Saved Phase 5A quantities are reported as stored; derived
    entries (overlap fractions, workload rows, family summaries, threshold
    counts) record the source fields they combine. The row-level check
    entries record the recomputed values that matched the saved ones.
    """
    rows: List[Dict] = []

    def add(section: str, metric: str, value, source_artifact: str, source_field: str, note: str = "") -> None:
        formatted, value_type = _format_scorecard_value(value)
        rows.append(
            {
                "section": section,
                "metric": metric,
                "value": formatted,
                "value_type": value_type,
                "source_artifact": source_artifact,
                "source_field": source_field,
                "note": note,
            }
        )

    ds = config.PHASE4_EVALUATION_DATASET_FILENAME
    sp = config.PHASE5_PAIRWISE_SPEARMAN_FILENAME
    jc = config.PHASE5_PAIRWISE_JACCARD_FILENAME
    hy = config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME
    ag = config.PHASE5_AGREEMENT_GROUPS_FILENAME
    mt = config.PHASE5_MULTITHRESHOLD_AGREEMENT_FILENAME
    bm = config.PHASE5_BOOTSTRAP_METRICS_FILENAME
    pdc = config.PHASE5_PAIRED_BOOTSTRAP_DIFFERENCES_FILENAME

    # --- experiment ---------------------------------------------------------
    add("experiment", "sample_size", context["sample_size"], ds,
        "rows per run block (ten validated run blocks)",
        "the canonical Phase 4 evaluation dataset")
    add("experiment", "fraud_label_count", context["fraud_label_count"], ds,
        "count(Class == 1) per run block")
    add("experiment", "fraud_prevalence", context["fraud_prevalence"], ds,
        "fraud_label_count / sample_size")
    add("experiment", "canonical_run_count", context["canonical_run_count"], ds,
        "count(distinct run_id)",
        "IF_001..IF_005 and LOF_001..LOF_005")

    # --- rank agreement -----------------------------------------------------
    add("rank_agreement", "spearman_if003_lof004", context["spearman_if003_lof004"], sp,
        f"value at [{IF_RUN_ID}, {LOF_RUN_ID}]",
        "Spearman rank correlation of the anomaly_score vectors")
    for family, key in (
        ("within_if", "within_if_spearman"),
        ("within_lof", "within_lof_spearman"),
        ("cross_method", "cross_method_spearman"),
    ):
        stats = context[key]
        add("rank_agreement", f"{family}_spearman_mean", stats["mean"], sp,
            f"mean of the {family} block (off-diagonal)")
        add("rank_agreement", f"{family}_spearman_min", stats["min"], sp,
            f"min of the {family} block (off-diagonal)")
        add("rank_agreement", f"{family}_spearman_max", stats["max"], sp,
            f"max of the {family} block (off-diagonal)")

    # --- flag overlap -------------------------------------------------------
    add("flag_overlap", "if003_flagged_count", context["if003_flagged_count"], hy,
        "run_a_flagged", "saved canonical 1% flags of IF_003")
    add("flag_overlap", "lof004_flagged_count", context["lof004_flagged_count"], hy,
        "run_b_flagged", "saved canonical 1% flags of LOF_004")
    add("flag_overlap", "observed_intersection", context["observed_intersection"], hy,
        "observed_intersection")
    add("flag_overlap", "union_size", context["union_size"], hy, "union_size")
    add("flag_overlap", "jaccard_if003_lof004", context["jaccard_if003_lof004"], jc,
        f"value at [{IF_RUN_ID}, {LOF_RUN_ID}]",
        "Jaccard = |intersection| / |union| of the two flagged sets")
    add("flag_overlap", "if003_flagged_share_overlapping",
        context["if003_flagged_share_overlapping"], hy,
        "observed_intersection / run_a_flagged",
        "share of IF_003's own flagged set that LOF_004 also flags")
    add("flag_overlap", "lof004_flagged_share_overlapping",
        context["lof004_flagged_share_overlapping"], hy,
        "observed_intersection / run_b_flagged",
        "share of LOF_004's own flagged set that IF_003 also flags")

    # --- hypergeometric null -------------------------------------------------
    add("hypergeometric_null", "expected_intersection_under_null",
        context["expected_intersection_under_null"], hy, "expected_intersection",
        "k_a * k_b / n under independent uniform selection")
    add("hypergeometric_null", "enrichment_observed_over_expected",
        context["enrichment_observed_over_expected"], hy,
        "enrichment_observed_over_expected", "observed / expected")
    add("hypergeometric_null", "log10_upper_tail_probability",
        context["log10_upper_tail_probability"], hy, "log10_survival",
        context["survival_underflow_note"])
    add("hypergeometric_null", "null_model_description",
        context["null_model_description"], hy, "null_model",
        "the ONLY null this test is interpreted against")

    # --- agreement groups ----------------------------------------------------
    for group_key in GROUP_KEYS:
        group = context["groups"][group_key]
        add("agreement_groups", f"{group_key}_observation_count",
            group["observation_count"], ag, f"observation_count [group={group_key}]")
        add("agreement_groups", f"{group_key}_fraud_count",
            group["fraud_count"], ag, f"fraud_count [group={group_key}]")
        add("agreement_groups", f"{group_key}_fraud_proportion",
            group["fraud_proportion"], ag, f"fraud_proportion [group={group_key}]",
            "labelled-fraud share within the group")
        add("agreement_groups", f"{group_key}_recall_contribution",
            group["recall_contribution"], ag, f"recall_contribution [group={group_key}]",
            "group frauds / total labelled frauds")

    # --- review workload ------------------------------------------------------
    workload_fields = {
        "both_only": ("observation_count [group=both]", "both"),
        "if003_flags": ("run_a_flagged (= both + if_only)", "if003"),
        "lof004_flags": ("run_b_flagged (= both + lof_only)", "lof004"),
        "union": ("union_size", "union"),
    }
    for policy, (field, _tag) in workload_fields.items():
        entry = context["workload"][policy]
        add("review_workload", f"{policy}_review_count", entry["reviews"], ag,
            f"derived from {field}")
        add("review_workload", f"{policy}_sample_share", entry["sample_share"], ag,
            f"derived from {field}", "reviews / sample_size")
        add("review_workload", f"{policy}_fraud_count", entry["frauds"], ag,
            f"derived from fraud_count rows ({field})")
        add("review_workload", f"{policy}_precision", entry["precision"], ag,
            f"derived from fraud_count / observation count ({field})")
        add("review_workload", f"{policy}_recall", entry["recall"], ag,
            "derived from fraud counts / total labelled frauds")

    # --- family consistency ----------------------------------------------------
    for family, key in (
        ("within_if", "within_if_jaccard"),
        ("within_lof", "within_lof_jaccard"),
        ("cross_method", "cross_method_jaccard"),
    ):
        stats = context[key]
        add("family_consistency", f"{family}_jaccard_mean", stats["mean"], jc,
            f"mean of the {family} block (off-diagonal)")
        add("family_consistency", f"{family}_jaccard_min", stats["min"], jc,
            f"min of the {family} block (off-diagonal)")
        add("family_consistency", f"{family}_jaccard_max", stats["max"], jc,
            f"max of the {family} block (off-diagonal)")

    # --- threshold sensitivity ---------------------------------------------------
    for entry in context["thresholds"]:
        label = f"{entry['pct']:g}".replace(".", "_")
        add("threshold_sensitivity", f"multithreshold_{label}_k_nominal", entry["k"], mt,
            f"k_nominal at threshold_pct = {entry['pct']:g}",
            f"selection source: {entry['source']}")
        add("threshold_sensitivity", f"multithreshold_{label}_any_method_count",
            entry["any_method_count"], mt,
            f"observation_count summed over n_methods >= 1 at threshold_pct = {entry['pct']:g}")
        add("threshold_sensitivity", f"multithreshold_{label}_all_methods_count",
            entry["all_methods_count"], mt,
            f"observation_count at n_methods = 10 at threshold_pct = {entry['pct']:g}")
        add("threshold_sensitivity", f"multithreshold_{label}_single_method_count",
            entry["single_method_count"], mt,
            f"observation_count at n_methods = 1 at threshold_pct = {entry['pct']:g}")

    # --- bootstrap context ----------------------------------------------------------
    for run_id, entry in context["bootstrap"]["precision_at_1pct"].items():
        tag = run_id.lower()
        add("bootstrap_context", f"{tag}_precision_at_1pct_point_estimate",
            entry["point"], bm, f"point_estimate [run_id={run_id}, metric=precision_at_1pct]")
        add("bootstrap_context", f"{tag}_precision_at_1pct_ci_lower",
            entry["ci_lower"], bm, f"ci_lower [run_id={run_id}, metric=precision_at_1pct]")
        add("bootstrap_context", f"{tag}_precision_at_1pct_ci_upper",
            entry["ci_upper"], bm, f"ci_upper [run_id={run_id}, metric=precision_at_1pct]")
    paired = context["bootstrap"]["paired_difference"]
    add("bootstrap_context", "paired_precision_at_1pct_difference",
        paired["point"], pdc, "point_estimate [metric=precision_at_1pct]",
        f"comparison: {paired['comparison']} (run_b minus run_a)")
    add("bootstrap_context", "paired_precision_at_1pct_difference_ci_lower",
        paired["ci_lower"], pdc, "ci_lower [metric=precision_at_1pct]")
    add("bootstrap_context", "paired_precision_at_1pct_difference_ci_upper",
        paired["ci_upper"], pdc, "ci_upper [metric=precision_at_1pct]")
    add("bootstrap_context", "bootstrap_replicates",
        context["bootstrap"]["n_replicates"], bm, "n_replicates")

    # --- row-level consistency checks ---------------------------------------------------
    for check in row_level_checks:
        add("row_level_checks", check["metric"], check["value"],
            check["source_artifact"], check["source_field"], check["note"])

    scorecard = pd.DataFrame(rows, columns=SCORECARD_COLUMNS)
    if scorecard.duplicated(subset=["metric"]).any():
        duplicates = scorecard[scorecard.duplicated(subset=["metric"], keep=False)]["metric"].tolist()
        raise Phase6Error(f"duplicate scorecard metric name(s): {sorted(set(duplicates))}")
    return scorecard


# ---------------------------------------------------------------------------
# F. Five-question consistency report (deterministic)
# ---------------------------------------------------------------------------

def _fmt_int(value: int) -> str:
    return f"{int(value):,}"


def _fmt_f(value: float, decimals: int = 4) -> str:
    return f"{float(value):.{decimals}f}"


def _fmt_pct(value: float, decimals: int = 2) -> str:
    return f"{100.0 * float(value):.{decimals}f}%"


def _is_are(count: int) -> str:
    return "is" if int(count) == 1 else "are"


def _tail_reporting_note(log10_upper_tail: float) -> str:
    """How the upper tail is reported: in log space when the linear value
    underflows double precision (never as exactly zero), otherwise with its
    linear-scale order of magnitude."""
    if float(log10_upper_tail) < -300.0:
        return (
            "the linear-space upper-tail probability underflows double "
            "precision at this overlap; the log-space value is the reported "
            "quantity and the tail is never stated as exactly zero"
        )
    return (
        f"the linear-space upper-tail probability is approximately "
        f"1e{float(log10_upper_tail):.0f} at this overlap; the log-space value "
        "is reported for precision"
    )


def _comparison_word(a: float, b: float) -> str:
    if a > b:
        return "higher than"
    if a < b:
        return "lower than"
    return "equal to"


def _config_axes_description() -> Tuple[str, str]:
    """The frozen Phase 3 configuration axes, derived from config (frozen
    facts of the experiment, stated without causal claims)."""
    if_n_estimators = "/".join(str(v) for v in sorted({c["n_estimators"] for c in config.ISOLATION_FOREST_CONFIGS}))
    if_max_samples = "/".join(str(v) for v in sorted({str(c["max_samples"]) for c in config.ISOLATION_FOREST_CONFIGS}))
    if_seeds = "/".join(str(v) for v in sorted({c["random_state"] for c in config.ISOLATION_FOREST_CONFIGS}))
    lof_neighbors = "/".join(str(v) for v in sorted({c["n_neighbors"] for c in config.LOF_CONFIGS}))
    lof_metrics = "/".join(sorted({c["metric"] for c in config.LOF_CONFIGS}))
    if_axes = (
        f"the Isolation Forest configurations vary n_estimators ({if_n_estimators}), "
        f"max_samples ({if_max_samples}) and random_state ({if_seeds})"
    )
    lof_axes = (
        f"the LOF configurations vary n_neighbors ({lof_neighbors}) and the "
        f"distance metric ({lof_metrics}; LOF_005 is the manhattan variant)"
    )
    return if_axes, lof_axes


def build_consistency_report(context: Dict) -> str:
    """Render the five-question consistency report as Markdown.

    Deterministic by construction: every number is injected from the
    validated context, no timestamp, path or random element appears, and
    every interpretive statement is one of the explicitly authored rules
    below (factual number statements plus fixed caveats). The same inputs
    always regenerate a byte-identical report.
    """
    n = context["sample_size"]
    frauds = context["fraud_label_count"]
    g = context["groups"]
    w = context["workload"]
    boot = context["bootstrap"]
    if_axes, lof_axes = _config_axes_description()

    L: List[str] = []
    L.append("# Stream A -- Phase 6: Cross-Method Consistency Report")
    L.append("")
    L.append(
        f"Comparison pair: **{IF_RUN_ID}** (Isolation Forest) vs **{LOF_RUN_ID}** "
        f"(LOF) on their saved canonical top-1% flags, over {_fmt_int(n)} "
        f"observations carrying {_fmt_int(frauds)} labelled frauds "
        f"(prevalence {_fmt_pct(context['fraud_prevalence'])})."
    )
    L.append("")
    L.append(
        "This is an evidence-synthesis report: it was generated deterministically "
        "from validated frozen artifacts. No model was fitted, no threshold was "
        "selected, and no bootstrap estimate, hypergeometric probability or "
        "correlation matrix was recomputed in this phase (creation time, input "
        "hashes and software versions live in `phase6_run_metadata.json`)."
    )
    L.append("")

    # --- 1. inputs and provenance -------------------------------------------
    L.append("## 1. Inputs and provenance")
    L.append("")
    L.append("| Consumed artifact | Role | SHA-256 (first 12) | Manifest |")
    L.append("|---|---|---|---|")
    for entry in context["inputs"]:
        L.append(
            f"| `{entry['artifact']}` | {entry['role']} | `{entry['sha256_12']}` | "
            f"{entry['manifest']} |"
        )
    L.append("")
    L.append(
        f"Runs covered: {context['canonical_run_count']} canonical configurations "
        "(IF_001..IF_005, LOF_001..LOF_005). The Phase 5A tables and the "
        "row-level dataset were verified to come from the SAME Phase 4 "
        "execution (input-hash cross-check), and the lightweight consistency "
        "checks listed in section 2 all matched."
    )
    L.append("")
    L.append(f"> {context['exploratory_caveat']}")
    L.append("")

    # --- 2. method -----------------------------------------------------------
    L.append("## 2. Method")
    L.append("")
    L.append(
        f"- **Group assignment.** {IF_RUN_ID} and {LOF_RUN_ID} were extracted by "
        "`run_id` from the verified Phase 4 evaluation dataset and joined "
        "**one-to-one on `row_id`** (duplicated, missing or extra row IDs are "
        "hard errors). Using their saved canonical 1% flags, every observation "
        "is assigned exactly one group: **Both** (IF=1, LOF=1), **IF-only** "
        "(IF=1, LOF=0), **LOF-only** (IF=0, LOF=1) or **Neither** (IF=0, "
        "LOF=0) -- a disjoint and exhaustive partition of all "
        f"{_fmt_int(n)} observations. The join-based counts were cross-checked "
        "against the saved Phase 5A agreement-group table (identical)."
    )
    L.append(
        "- **Frozen values.** The Spearman correlation, the top-1% Jaccard, the "
        "hypergeometric quantities, the family summaries and the bootstrap "
        "results are READ from the Phase 5A tables; none is recalculated here."
    )
    L.append(
        "- **Lightweight consistency checks against the Phase 4 "
        "observation-level data** (all matching, recorded as scorecard rows in "
        "the `row_level_checks` section): per-detector flagged counts, the "
        "observed intersection and union, the four group counts and their "
        "fraud counts, the saved top-1% Jaccard, the ten-run union and "
        "intersection at the 1% budget, and the flag-based precision / recall "
        "/ F1-at-1% point estimates of the three highlighted runs."
    )
    L.append(
        "- **Determinism.** This report contains no timestamps, paths or random "
        "elements; identical inputs regenerate byte-identical text."
    )
    L.append("")

    # --- 3. Q1 ---------------------------------------------------------------
    L.append("## 3. Q1 -- Are the anomaly rankings similar?")
    L.append("")
    L.append(
        f"Spearman rank correlation between the {IF_RUN_ID} and {LOF_RUN_ID} "
        f"`anomaly_score` vectors (saved `phase5_pairwise_spearman.csv`): "
        f"**{_fmt_f(context['spearman_if003_lof004'])}**."
    )
    L.append("")
    L.append("Comparison families from the saved 10x10 matrices (off-diagonal):")
    L.append("")
    L.append("| Matrix / family | Mean | Min | Max |")
    L.append("|---|---|---|---|")
    for label, key in (
        ("Spearman / within Isolation Forest", "within_if_spearman"),
        ("Spearman / within LOF", "within_lof_spearman"),
        ("Spearman / cross-method (IF x LOF)", "cross_method_spearman"),
        ("Top-1% Jaccard / within Isolation Forest", "within_if_jaccard"),
        ("Top-1% Jaccard / within LOF", "within_lof_jaccard"),
        ("Top-1% Jaccard / cross-method (IF x LOF)", "cross_method_jaccard"),
    ):
        s = context[key]
        L.append(f"| {label} | {_fmt_f(s['mean'])} | {_fmt_f(s['min'])} | {_fmt_f(s['max'])} |")
    L.append("")
    L.append("Interpretation (fixed rules):")
    L.append("")
    L.append(
        f"- The two detectors' full-sample rankings are positively correlated "
        f"(Spearman {_fmt_f(context['spearman_if003_lof004'])}). A positive rank "
        "correlation measures monotonic association across all "
        f"{_fmt_int(n)} observations; it **does not imply identical anomaly "
        "rankings**, and it is compatible with very different top-1% selections "
        "-- the observed top-1% Jaccard between the two detectors is "
        f"{_fmt_f(context['jaccard_if003_lof004'])} (Q2), whereas identical "
        "selections would give 1.0."
    )
    L.append(
        f"- Within the saved matrices, the within-IF mean Spearman "
        f"({_fmt_f(context['within_if_spearman']['mean'])}) is "
        f"{_comparison_word(context['within_if_spearman']['mean'], context['cross_method_spearman']['mean'])} "
        f"the cross-method mean ({_fmt_f(context['cross_method_spearman']['mean'])}), and the "
        f"within-LOF mean ({_fmt_f(context['within_lof_spearman']['mean'])}) is "
        f"{_comparison_word(context['within_lof_spearman']['mean'], context['cross_method_spearman']['mean'])} "
        "the cross-method mean; the analogous Jaccard comparisons are "
        f"{_comparison_word(context['within_if_jaccard']['mean'], context['cross_method_jaccard']['mean'])} "
        f"(within-IF {_fmt_f(context['within_if_jaccard']['mean'])} vs "
        f"{_fmt_f(context['cross_method_jaccard']['mean'])}) and "
        f"{_comparison_word(context['within_lof_jaccard']['mean'], context['cross_method_jaccard']['mean'])} "
        f"(within-LOF {_fmt_f(context['within_lof_jaccard']['mean'])} vs "
        f"{_fmt_f(context['cross_method_jaccard']['mean'])})."
    )
    L.append(
        "- Rank agreement (this question), flag overlap (Q2) and ground-truth "
        "detection performance (Q4) are distinct constructs; a change in one "
        "does not determine the others."
    )
    L.append("")

    # --- 4. Q2 ---------------------------------------------------------------
    L.append("## 4. Q2 -- How much do the flagged observations overlap?")
    L.append("")
    L.append("| Quantity | Value | Source |")
    L.append("|---|---|---|")
    L.append(
        f"| {IF_RUN_ID} flagged (saved 1% flags) | {_fmt_int(context['if003_flagged_count'])} | "
        "`phase5_hypergeometric_overlap.csv` : `run_a_flagged` |"
    )
    L.append(
        f"| {LOF_RUN_ID} flagged (saved 1% flags) | {_fmt_int(context['lof004_flagged_count'])} | "
        "`run_b_flagged` |"
    )
    L.append(
        f"| Observed intersection (Both) | {_fmt_int(context['observed_intersection'])} | "
        "`observed_intersection` |"
    )
    L.append(
        f"| Union | {_fmt_int(context['union_size'])} | `union_size` |"
    )
    L.append(
        f"| **Jaccard** = intersection / union | **{_fmt_f(context['jaccard_if003_lof004'])}** "
        f"({_fmt_pct(context['jaccard_if003_lof004'])}) | "
        f"`phase5_pairwise_jaccard_1pct.csv` : `[{IF_RUN_ID}, {LOF_RUN_ID}]` |"
    )
    L.append(
        f"| Share of {IF_RUN_ID}'s flagged set also flagged by {LOF_RUN_ID} | "
        f"{_fmt_f(context['if003_flagged_share_overlapping'])} "
        f"({_fmt_pct(context['if003_flagged_share_overlapping'])}) | derived: "
        "`observed_intersection / run_a_flagged` |"
    )
    L.append(
        f"| Share of {LOF_RUN_ID}'s flagged set also flagged by {IF_RUN_ID} | "
        f"{_fmt_f(context['lof004_flagged_share_overlapping'])} "
        f"({_fmt_pct(context['lof004_flagged_share_overlapping'])}) | derived: "
        "`observed_intersection / run_b_flagged` |"
    )
    L.append("")
    L.append(
        "Group counts (disjoint, exhaustive partition of all observations): "
        f"**Both** {_fmt_int(g['both']['observation_count'])} / **IF-only** "
        f"{_fmt_int(g['if_only']['observation_count'])} / **LOF-only** "
        f"{_fmt_int(g['lof_only']['observation_count'])} / **Neither** "
        f"{_fmt_int(g['neither']['observation_count'])}."
    )
    L.append("")
    L.append("Interpretation (fixed rules):")
    L.append("")
    L.append(
        f"- The **Jaccard coefficient** ({_fmt_f(context['jaccard_if003_lof004'])}) "
        "expresses the overlap **relative to the union** of the two flagged "
        "sets; the **per-detector overlap fractions** "
        f"({_fmt_pct(context['if003_flagged_share_overlapping'])} of "
        f"{IF_RUN_ID}'s flags and {_fmt_pct(context['lof004_flagged_share_overlapping'])} "
        f"of {LOF_RUN_ID}'s flags) express the overlap **relative to each "
        "detector's own flagged set. These quantities answer different "
        "questions and are deliberately reported side by side; they coincide "
        "only in special cases."
    )
    L.append(
        f"- Of {IF_RUN_ID}'s {_fmt_int(context['if003_flagged_count'])} flagged "
        f"observations, {_fmt_int(g['if_only']['observation_count'])} {_is_are(g['if_only']['observation_count'])} flagged "
        f"only by {IF_RUN_ID} and {_fmt_int(context['observed_intersection'])} {_is_are(context['observed_intersection'])} "
        f"shared with {LOF_RUN_ID}; of {LOF_RUN_ID}'s "
        f"{_fmt_int(context['lof004_flagged_count'])} flagged observations, "
        f"{_fmt_int(g['lof_only']['observation_count'])} {_is_are(g['lof_only']['observation_count'])} flagged only by "
        f"{LOF_RUN_ID}."
    )
    L.append("")

    # --- 5. Q3 ---------------------------------------------------------------
    L.append("## 5. Q3 -- Is the overlap greater than expected under the specified random-selection null?")
    L.append("")
    L.append(
        "The null this test is interpreted against (verbatim from the Phase 5A "
        f"artifact): *\"{context['null_model_description']}\"*."
    )
    L.append("")
    L.append(
        f"- Expected intersection under the null: `k_a * k_b / n` = "
        f"{_fmt_int(context['if003_flagged_count'])} x "
        f"{_fmt_int(context['lof004_flagged_count'])} / {_fmt_int(n)} = "
        f"**{_fmt_f(context['expected_intersection_under_null'], 2)}**."
    )
    L.append(
        f"- Observed intersection: **{_fmt_int(context['observed_intersection'])}** "
        f"(enrichment observed / expected: **{_fmt_f(context['enrichment_observed_over_expected'], 2)}x**)."
    )
    L.append(
        f"- log10 P(X >= observed) = **{_fmt_f(context['log10_upper_tail_probability'], 2)}** "
        "(upper-tail probability of the hypergeometric null; "
        + context["survival_underflow_note"] + ")."
    )
    L.append("")
    L.append("Interpretation (fixed rules):")
    L.append("")
    L.append(
        f"- The observed overlap ({_fmt_int(context['observed_intersection'])}) "
        "is compared with independent uniform random selection of two subsets "
        "of the observed sizes; the upper-tail probability above quantifies "
        "how surprising the overlap is **under this null and nothing else**."
    )
    L.append(
        "- Rejecting this null establishes neither that the flagged "
        "observations are true anomalies, nor any operational validity for "
        "fraud detection on MPLAD transactions or any other deployment."
    )
    L.append("")

    # --- 6. Q4 ---------------------------------------------------------------
    L.append("## 6. Q4 -- How are known fraud labels distributed across agreement groups?")
    L.append("")
    L.append(
        "Labels enter here solely post hoc, to describe the composition of the "
        "four agreement groups of the saved 1% flags:"
    )
    L.append("")
    L.append("| Group | Observations | Labelled frauds | Fraud share in group | Recall contribution |")
    L.append("|---|---|---|---|---|")
    for group_key in GROUP_KEYS:
        group = g[group_key]
        L.append(
            f"| {GROUP_LABELS[group_key]} | {_fmt_int(group['observation_count'])} | "
            f"{_fmt_int(group['fraud_count'])} | {_fmt_pct(group['fraud_proportion'])} | "
            f"{_fmt_pct(group['recall_contribution'])} |"
        )
    L.append("")
    L.append("Review-workload policies at the canonical 1% flags:")
    L.append("")
    L.append("| Review policy | Reviews | Share of sample | Labelled frauds found | Precision | Recall |")
    L.append("|---|---|---|---|---|---|")
    policies = (
        ("Both-only (agreement gate)", "both_only"),
        (f"{IF_RUN_ID}'s flagged set", "if003_flags"),
        (f"{LOF_RUN_ID}'s flagged set", "lof004_flags"),
        ("Union of both flagged sets", "union"),
    )
    for label, key in policies:
        entry = w[key]
        L.append(
            f"| {label} | {_fmt_int(entry['reviews'])} | {_fmt_pct(entry['sample_share'])} | "
            f"{_fmt_int(entry['frauds'])} | {_fmt_pct(entry['precision'])} | "
            f"{_fmt_pct(entry['recall'])} |"
        )
    L.append("")
    L.append(
        f"- Reviewing only the **Both** group examines "
        f"{_fmt_int(w['both_only']['reviews'])} observations "
        f"({_fmt_pct(w['both_only']['sample_share'])} of the sample) and "
        f"recovers {_fmt_int(w['both_only']['frauds'])} of the "
        f"{_fmt_int(frauds)} labelled frauds; the **union** policy examines "
        f"{_fmt_int(w['union']['reviews'])} observations "
        f"({_fmt_pct(w['union']['sample_share'])}) and recovers "
        f"{_fmt_int(w['union']['frauds'])}. Each individual detector's "
        f"{_fmt_int(context['if003_flagged_count'])}-observation flagged set sits "
        "between these two operating points."
    )
    L.append(
        f"- **{_fmt_int(context['neither_fraud_count'])} labelled fraud(s) "
        f"{_is_are(context['neither_fraud_count'])} in the Neither group** and "
        f"{_is_are(context['neither_fraud_count'])} missed by both detectors at "
        "the 1% budget."
    )
    L.append(
        f"- Saved bootstrap context (Phase 5A, "
        f"{_fmt_int(boot['n_replicates'])} class-stratified replicates): "
        f"precision@1% point estimates {_fmt_f(boot['precision_at_1pct'][IF_RUN_ID]['point'])} "
        f"[{IF_RUN_ID}] and {_fmt_f(boot['precision_at_1pct'][LOF_RUN_ID]['point'])} "
        f"[{LOF_RUN_ID}]; paired difference "
        f"({boot['paired_difference']['comparison']}) "
        f"{boot['paired_difference']['point']:+.4f} with a "
        f"{int(boot['ci_level'] * 100)}% percentile CI of "
        f"[{boot['paired_difference']['ci_lower']:.4f}, "
        f"{boot['paired_difference']['ci_upper']:.4f}] (read from the frozen "
        "Phase 5A tables; not recomputed)."
    )
    L.append(
        "- These rows describe alternative review policies on ONE benchmark "
        "sample; they do not establish a universally optimal audit policy. The "
        "comparison pair was selected after label-informed inspection, so the "
        "precision contrast is exploratory; cost structures, investigation "
        "capacity and fraud-base rates on MPLAD transactions would have to "
        "dominate any real policy choice."
    )
    L.append("")

    # --- 7. Q5 ---------------------------------------------------------------
    L.append("## 7. Q5 -- Is disagreement sensitive to neighbourhood size, detector configuration or review threshold?")
    L.append("")
    L.append(
        f"Frozen Phase 3 configuration axes: {if_axes}; {lof_axes}. The "
        "canonical run order maps IF_001..IF_005 and LOF_001..LOF_005 onto "
        "these grids in order."
    )
    L.append("")
    L.append("Agreement levels from the saved 10x10 matrices (see Q1 table):")
    L.append("")
    L.append(
        f"- Spearman -- within IF: mean {_fmt_f(context['within_if_spearman']['mean'])} "
        f"(range {_fmt_f(context['within_if_spearman']['min'])} to "
        f"{_fmt_f(context['within_if_spearman']['max'])}); within LOF: mean "
        f"{_fmt_f(context['within_lof_spearman']['mean'])} (range "
        f"{_fmt_f(context['within_lof_spearman']['min'])} to "
        f"{_fmt_f(context['within_lof_spearman']['max'])}); cross-method: mean "
        f"{_fmt_f(context['cross_method_spearman']['mean'])} (range "
        f"{_fmt_f(context['cross_method_spearman']['min'])} to "
        f"{_fmt_f(context['cross_method_spearman']['max'])})."
    )
    L.append(
        f"- Top-1% Jaccard -- within IF: mean {_fmt_f(context['within_if_jaccard']['mean'])} "
        f"(range {_fmt_f(context['within_if_jaccard']['min'])} to "
        f"{_fmt_f(context['within_if_jaccard']['max'])}); within LOF: mean "
        f"{_fmt_f(context['within_lof_jaccard']['mean'])} (range "
        f"{_fmt_f(context['within_lof_jaccard']['min'])} to "
        f"{_fmt_f(context['within_lof_jaccard']['max'])}); cross-method: mean "
        f"{_fmt_f(context['cross_method_jaccard']['mean'])} (range "
        f"{_fmt_f(context['cross_method_jaccard']['min'])} to "
        f"{_fmt_f(context['cross_method_jaccard']['max'])})."
    )
    L.append("")
    L.append(
        "Multi-threshold agreement from the saved counts-by-number-of-methods "
        "table (observations selected by at least one / all ten / exactly one "
        "of the ten configurations):"
    )
    L.append("")
    L.append("| Review budget | k per method | Selection source | Selected by >= 1 method | By all 10 | By exactly 1 |")
    L.append("|---|---|---|---|---|---|")
    for entry in context["thresholds"]:
        L.append(
            f"| {entry['pct']:g}% | {_fmt_int(entry['k'])} | `{entry['source']}` | "
            f"{_fmt_int(entry['any_method_count'])} | {_fmt_int(entry['all_methods_count'])} | "
            f"{_fmt_int(entry['single_method_count'])} |"
        )
    L.append("")
    L.append("Interpretation (fixed rules):")
    L.append("")
    L.append(
        "- The saved statistics show the within-family and cross-method "
        "agreement levels and their ranges, and how the counts change with the "
        "review budget. They do **not** isolate which configuration choice "
        "causes which part of the disagreement: attributing disagreement to a "
        "specific seed, parameter, neighbourhood size or distance metric would "
        "require controlled single-factor experiments, which were not run in "
        "this experiment."
    )
    L.append(
        "- The multi-threshold artifact contains only counts by number of "
        "selecting methods; it carries no per-pair results at the "
        "non-canonical thresholds, and none are invented here."
    )
    L.append(
        "- No detector family or configuration is claimed to be uniquely "
        "responsible for the disagreement, and no configuration is claimed "
        "superior."
    )
    L.append("")

    # --- 8. interpretation principles ----------------------------------------
    L.append("## 8. Interpretation principles")
    L.append("")
    for i, principle in enumerate(INTERPRETATION_PRINCIPLES, start=1):
        L.append(f"{i}. {principle}")
    L.append("")

    # --- 9. reproducibility ----------------------------------------------------
    L.append("## 9. Reproducibility")
    L.append("")
    L.append(
        "This report is byte-deterministic: it contains no timestamps, no "
        "filesystem paths and no random elements, and every number is read "
        "from a validated frozen artifact (the scorecard records the source "
        "artifact and original metric field of every value). Regenerate with:"
    )
    L.append("")
    L.append("    python scripts/run_phase6.py --execute")
    L.append("")
    L.append(
        "Creation time, full input hashes, manifest statuses, software "
        "versions, the reference-validation status and the zero-model-fitting "
        "declaration are recorded in `phase6_run_metadata.json`; integrity is "
        "vouched by `phase6_commit_manifest.json` (published last)."
    )
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# G. Provenance record and orchestration
# ---------------------------------------------------------------------------

def _output_paths(output_dir: Path) -> Dict[str, Path]:
    return {
        "group_assignments": output_dir / config.PHASE6_GROUP_ASSIGNMENTS_FILENAME,
        "consistency_scorecard": output_dir / config.PHASE6_CONSISTENCY_SCORECARD_FILENAME,
        "consistency_report": output_dir / config.PHASE6_CONSISTENCY_REPORT_FILENAME,
        "run_metadata": output_dir / config.PHASE6_RUN_METADATA_FILENAME,
        "manifest": output_dir / config.PHASE6_MANIFEST_FILENAME,
    }


def _build_provenance_record(
    validated: Dict,
    output_paths: Dict,
    run_mode: str,
    reference_status: Dict,
    non_canonical_overrides: Dict,
) -> Dict:
    """Assemble the phase6_run_metadata.json payload (JSON-safe types)."""
    return {
        "phase": "6",
        "stream": "A",
        "layer": "cross_method_consistency",
        "run_mode": run_mode,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": validated["inputs_info"],
        "input_manifests": {
            "phase5": validated["phase5_manifest"],
            "phase4": validated["phase4_manifest"],
        },
        "sample": validated["sample"],
        "run_ids": list(validated["aligned"]["run_ids"]),
        "comparison_pair": {
            "if_run_id": IF_RUN_ID,
            "lof_run_id": LOF_RUN_ID,
            "threshold_pct": config.PHASE5_CANONICAL_THRESHOLD_PCT,
            "flag_source": "saved canonical Phase 3 top-1% flags (never recomputed)",
        },
        "reference_validation": reference_status,
        "non_canonical_overrides": non_canonical_overrides,
        "analytical_conventions": {
            "group_assignment": (
                "Both (IF=1, LOF=1) / IF-only (IF=1, LOF=0) / LOF-only (IF=0, "
                "LOF=1) / Neither (IF=0, LOF=0) on the saved canonical 1% "
                "flags; disjoint and exhaustive partition, every observation "
                "exactly once"
            ),
            "join": (
                "one-to-one merge on row_id between the IF_003 and LOF_004 run "
                "blocks extracted by run_id; duplicated, missing or extra row "
                "IDs are hard errors; canonical row-ID alignment preserved"
            ),
            "saved_value_policy": (
                "bootstrap estimates, hypergeometric probabilities and "
                "correlation matrices are READ from the frozen Phase 5A "
                "outputs, never recomputed"
            ),
            "lightweight_checks": (
                "flag counts, intersection, union, group counts and frauds, "
                "saved Jaccard, ten-run union/intersection at 1%, and the "
                "flag-based precision/recall/F1-at-1% point estimates "
                "recomputed from the Phase 4 observation-level data and "
                "matched against the saved Phase 5A values (all matched)"
            ),
            "report_determinism": (
                "the Markdown report contains no timestamps, paths or random "
                "elements; identical inputs regenerate byte-identical text"
            ),
            "references": (
                "PHASE6_REFERENCE_VALUES are historical acceptance references "
                "used for validation only; they are never written into an "
                "output as if computed, and a mismatch is reported as a "
                "failed validation rather than forced"
            ),
        },
        "selection_caveat": EXPLORATORY_CAVEAT,
        "outputs": {k: str(v) for k, v in output_paths.items()},
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "executable": sys.executable,
        },
        "model_fitting": {
            "models_fitted": 0,
            "note": (
                "Phase 6 is an evidence-synthesis layer: no detector was "
                "constructed, fitted or refitted; no anomaly score or "
                "threshold was created; no bootstrap estimate, hypergeometric "
                "probability or correlation matrix was recomputed; no plot "
                "was produced."
            ),
        },
    }


def _check_assignment_against_tables(assignment_summary: Dict, tables: Dict) -> None:
    """The join-based assignment must agree with the saved Phase 5A group
    table (which the loading layer already matched against the row-level
    flags) -- closing the join-vs-positional loop."""
    groups_table = tables["agreement_groups"].set_index("group")
    hyper = tables["hypergeometric"]
    problems: List[str] = []
    for group_key in GROUP_KEYS:
        if assignment_summary["groups"][group_key]["observation_count"] != int(
            groups_table.loc[group_key, "observation_count"]
        ):
            problems.append(
                f"group '{group_key}': join-based count "
                f"{assignment_summary['groups'][group_key]['observation_count']} != "
                f"saved table count {int(groups_table.loc[group_key, 'observation_count'])}"
            )
        if assignment_summary["groups"][group_key]["fraud_count"] != int(
            groups_table.loc[group_key, "fraud_count"]
        ):
            problems.append(
                f"group '{group_key}': join-based frauds "
                f"{assignment_summary['groups'][group_key]['fraud_count']} != "
                f"saved table frauds {int(groups_table.loc[group_key, 'fraud_count'])}"
            )
    if assignment_summary["observed_intersection"] != int(hyper["observed_intersection"]):
        problems.append("join-based intersection disagrees with the saved summary")
    if assignment_summary["union_size"] != int(hyper["union_size"]):
        problems.append("join-based union disagrees with the saved summary")
    if assignment_summary["if_flagged"] != int(hyper["run_a_flagged"]) or (
        assignment_summary["lof_flagged"] != int(hyper["run_b_flagged"])
    ):
        problems.append("join-based flagged counts disagree with the saved summary")
    if problems:
        raise GroupAssignmentError(
            _format_problems(problems, "assignment / Phase 5A table consistency")
        )


def _recheck_inputs(validated: Dict) -> None:
    """Re-verify the input manifests and re-hash every consumed input
    immediately before publication (inputs must not have drifted while the
    analysis ran)."""
    problems: List[str] = []
    for manifest_key in ("phase5_manifest", "phase4_manifest"):
        record = validated[manifest_key]
        if record["mode"] != "manifest_verified":
            continue
        manifest_path = Path(record["path"])
        try:
            manifest = load_manifest(manifest_path)
            verify_manifest(manifest, base_dir=manifest_path.parent)
        except ManifestError as exc:
            problems.append(f"{manifest_key}: re-verification failed: {exc}")
    from mplad.common.manifest import artifact_entry

    for key, info in validated["inputs_info"].items():
        try:
            current = artifact_entry(Path(info["path"]))
        except FileNotFoundError:
            problems.append(f"input '{key}' disappeared: {info['path']}")
            continue
        if current["sha256"] != info["sha256"] or current["size_bytes"] != info["size_bytes"]:
            problems.append(
                f"input '{key}' changed while Phase 6 was running "
                f"(recorded {info['sha256'][:12]}..., now {current['sha256'][:12]}...)"
            )
    if problems:
        raise Phase6InputError(_format_problems(problems, "pre-publication input recheck"))


# ---------------------------------------------------------------------------
# Staged publication with backup / rollback (the manifest is published LAST)
# ---------------------------------------------------------------------------

def _verify_staged_artifacts(staging_dir: Path, artifact_names: Sequence[str]) -> None:
    """Every staged file must exist, be non-empty and start with decodable
    UTF-8 text -- a partially written artifact is never published."""
    problems: List[str] = []
    for name in artifact_names:
        staged = staging_dir / name
        if not staged.is_file():
            problems.append(f"'{name}' is missing from the staging directory")
            continue
        size = staged.stat().st_size
        if size <= 0:
            problems.append(f"'{name}' is empty ({size} bytes)")
            continue
        with open(staged, "rb") as f:
            head = f.read(256)
        try:
            head.decode("utf-8")
        except UnicodeDecodeError:
            problems.append(f"'{name}' does not start with UTF-8 text")
    if problems:
        raise Phase6Error(
            "staged artifact verification failed:\n  " + "\n  ".join(problems)
        )


def _publish_with_rollback(
    staging_dir: Path,
    output_dir: Path,
    artifact_names: Sequence[str],
    manifest_name: str,
    overwrite: bool,
    verbose: bool = True,
) -> Dict:
    """Publish the staged artifacts; roll back completely on any failure.

    Steps: verify every staged file -> back up any pre-existing outputs
    (only reachable with ``overwrite=True``) -> move the staged artifacts
    into place -> write the commit manifest LAST (hashing the final files).
    If anything fails, every newly published file is removed and every
    backup is restored, leaving the output directory exactly as it was.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    all_names = list(artifact_names) + [manifest_name]

    backed_up: Dict[str, Path] = {}
    published: List[str] = []
    backup_dir: Optional[Path] = None
    try:
        _verify_staged_artifacts(staging_dir, artifact_names)

        existing = [n for n in all_names if (output_dir / n).exists()]
        if existing and not overwrite:
            raise Phase6Error(
                "output file(s) already exist: " + ", ".join(existing)
            )
        if existing:
            backup_dir = Path(
                tempfile.mkdtemp(prefix=f".{output_dir.name}.backup-", dir=output_dir.parent)
            )
            for name in existing:
                (output_dir / name).rename(backup_dir / name)
                backed_up[name] = backup_dir / name
            if verbose:
                print(f"  backed up {len(existing)} existing output(s) to {backup_dir}")

        for name in artifact_names:
            (staging_dir / name).rename(output_dir / name)
            published.append(name)
        if verbose:
            print(f"  published {len(published)} artifact(s) to {output_dir}")

        # Build and validate manifest in staging first, then publish LAST
        manifest = build_manifest({name: output_dir / name for name in artifact_names})
        staged_manifest = staging_dir / manifest_name
        save_manifest(manifest, staged_manifest, overwrite=True)
        load_manifest(staged_manifest)
        if (output_dir / manifest_name).exists():
            (output_dir / manifest_name).unlink()
        staged_manifest.rename(output_dir / manifest_name)
        published.append(manifest_name)
        if verbose:
            print(f"  published the commit manifest last: {output_dir / manifest_name}")
    except BaseException:
        for name in all_names:
            target = output_dir / name
            if target.exists():
                target.unlink()
        for name, backup in backed_up.items():
            if backup.exists() and not (output_dir / name).exists():
                backup.rename(output_dir / name)
        if backup_dir is not None and backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)
        raise
    else:
        if backup_dir is not None and backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)
    return {"published": published, "backed_up": sorted(backed_up)}


# ---------------------------------------------------------------------------
# Orchestration: preflight (default) and staged execution
# ---------------------------------------------------------------------------

def collect_phase6_preflight(
    phase5_dir: Optional[Path] = None,
    phase4_dataset_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    expected_run_ids: Optional[Sequence[str]] = None,
    expected_sample_size: int = config.SAMPLE_SIZE_DEFAULT,
    validate_references: bool = True,
    verbose: bool = True,
) -> Dict:
    """Validate everything Phase 6 needs WITHOUT computing or writing.

    Verifies the optional Phase 5A and Phase 4 output manifests, loads and
    validates every consumed artifact (schemas, run completeness, cross-run
    row_id consistency, cross-snapshot hash consistency, row-level
    cross-checks) and, when reference validation is active, compares the
    reference-checkable values with the historical acceptance references.
    No output is computed and no file is written (the output directory is
    not even created).
    """
    phase5_dir, phase4_dataset_path = _resolve_input_paths(phase5_dir, phase4_dataset_path)
    output_dir = Path(output_dir) if output_dir is not None else config.DEFAULT_PHASE6_OUTPUT_DIR
    paths = _output_paths(output_dir)

    validated = _load_and_validate_inputs(
        phase5_dir, phase4_dataset_path, expected_run_ids, expected_sample_size,
        verbose=verbose,
    )

    reference_status = {"enabled": bool(validate_references), "n_references_checked": len(PHASE6_REFERENCE_VALUES)}
    if validate_references:
        mismatches = validate_against_references(_reference_check_context(validated))
        if mismatches:
            raise ReferenceValidationError(
                "reference validation FAILED -- the consumed artifacts do not "
                "reproduce the canonical experiment; nothing is computed or "
                "written and no value is forced:\n  "
                + "\n  ".join(mismatches)
            )
        reference_status.update({"passed": True, "mismatches": []})
    else:
        reference_status.update({
            "passed": None,
            "mismatches": None,
            "note": "reference validation deliberately skipped (non-canonical replica)",
        })

    return {
        "phase5_dir": phase5_dir,
        "phase4_dataset_path": phase4_dataset_path,
        "input_manifests": {
            "phase5": validated["phase5_manifest"],
            "phase4": validated["phase4_manifest"],
        },
        "sample": validated["sample"],
        "run_ids": list(validated["aligned"]["run_ids"]),
        "comparison_pair": {
            "if_run_id": IF_RUN_ID,
            "lof_run_id": LOF_RUN_ID,
            "threshold_pct": config.PHASE5_CANONICAL_THRESHOLD_PCT,
            "flag_source": "saved canonical Phase 3 top-1% flags",
        },
        "reference_validation": reference_status,
        "row_level_checks_performed": [c["metric"] for c in validated["row_level_checks"]],
        "analyses_planned": [
            "observation-level group assignment (one-to-one row_id join, saved 1% flags)",
            "consistency scorecard (frozen Phase 5A values + row-level checks)",
            "five-question consistency report (deterministic Markdown)",
        ],
        "outputs": {
            "directory": output_dir,
            "paths": paths,
            "exists": {k: Path(v).exists() for k, v in paths.items()},
            "overwrite": False,
            "blocked": bool(any(Path(v).exists() for v in paths.values())),
        },
        "writes_performed": False,
        "models_fitted": 0,
    }


def run_phase6(
    phase5_dir: Optional[Path] = None,
    phase4_dataset_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    expected_run_ids: Optional[Sequence[str]] = None,
    expected_sample_size: int = config.SAMPLE_SIZE_DEFAULT,
    validate_references: bool = True,
    overwrite: bool = False,
    verbose: bool = True,
) -> Dict:
    """Execute the Phase 6 cross-method consistency layer end to end.

    Steps: fail-fast output precheck -> verify the optional Phase 5A and
    Phase 4 manifests -> load and validate every input (cross-snapshot hash
    consistency + row-level cross-checks) -> validate the reference-checkable
    values against the historical acceptance references (abort on mismatch,
    never force) -> assign the observation-level agreement groups by a
    one-to-one ``row_id`` join and cross-check them against the saved group
    table -> build the consistency scorecard and the deterministic
    five-question report -> re-verify the inputs -> stage all artifacts,
    verify them and publish with backup/rollback, the commit manifest LAST.

    No detector is ever fitted, no score or threshold is ever created, and
    no bootstrap estimate, hypergeometric probability or correlation matrix
    is ever recomputed. Existing outputs are never replaced unless
    ``overwrite=True``.
    """
    phase5_dir, phase4_dataset_path = _resolve_input_paths(phase5_dir, phase4_dataset_path)
    output_dir = Path(output_dir) if output_dir is not None else config.DEFAULT_PHASE6_OUTPUT_DIR
    paths = _output_paths(output_dir)

    # Fail fast: refuse to compute if outputs exist and cannot be replaced.
    assert_outputs_writable(list(paths.values()), overwrite=overwrite)

    validated = _load_and_validate_inputs(
        phase5_dir, phase4_dataset_path, expected_run_ids, expected_sample_size,
        verbose=verbose,
    )

    # --- reference validation (before anything is computed or written) ------
    reference_status = {"enabled": bool(validate_references), "n_references_checked": len(PHASE6_REFERENCE_VALUES)}
    if validate_references:
        mismatches = validate_against_references(_reference_check_context(validated))
        if mismatches:
            raise ReferenceValidationError(
                "reference validation FAILED -- the consumed artifacts do not "
                "reproduce the canonical experiment (30,000 observations, 47 "
                "fraud labels, the documented overlap/group counts, Spearman "
                "0.3666, Jaccard 0.2170, enrichment 35.67x, log10 upper tail "
                "~ -140.30). Nothing is written and no value is forced:\n  "
                + "\n  ".join(mismatches)
            )
        reference_status.update({"passed": True, "mismatches": []})
    else:
        reference_status.update({
            "passed": None,
            "mismatches": None,
            "note": "reference validation deliberately skipped (non-canonical replica)",
        })

    # --- A. observation-level group assignment -------------------------------
    if verbose:
        print(
            f"Assigning agreement groups ({IF_RUN_ID} vs {LOF_RUN_ID}, "
            "one-to-one row_id join on the saved 1% flags) ..."
        )
    dataset_df = validated["dataset_df"]
    if_frame = dataset_df[dataset_df["run_id"] == IF_RUN_ID]
    lof_frame = dataset_df[dataset_df["run_id"] == LOF_RUN_ID]
    assignments = assign_agreement_groups(if_frame, lof_frame)
    assignment_summary = summarize_group_assignments(assignments)
    _check_assignment_against_tables(assignment_summary, validated["tables"])
    if verbose:
        counts = {k: v["observation_count"] for k, v in assignment_summary["groups"].items()}
        print(f"  partition: {counts} (matches the saved Phase 5A group table)")

    # --- B. consistency scorecard ---------------------------------------------
    if verbose:
        print("Building the consistency scorecard from the frozen Phase 5A values ...")
    context = build_consistency_context(validated, assignment_summary)
    scorecard = build_scorecard(context, validated["row_level_checks"])
    if verbose:
        print(f"  {len(scorecard)} scorecard entries, every row sourced")

    # --- C. five-question report -----------------------------------------------
    if verbose:
        print("Rendering the five-question consistency report (deterministic) ...")
    report_markdown = build_consistency_report(context)

    non_canonical_overrides = {}
    if expected_sample_size != config.SAMPLE_SIZE_DEFAULT:
        non_canonical_overrides["expected_sample_size"] = expected_sample_size
    if not validate_references:
        non_canonical_overrides["validate_references"] = False
    provenance = _build_provenance_record(
        validated, paths, run_mode="execute",
        reference_status=reference_status,
        non_canonical_overrides=non_canonical_overrides,
    )

    # --- re-verify inputs immediately before publication ------------------------
    if verbose:
        print("Re-checking input hashes and manifests before publication ...")
    _recheck_inputs(validated)

    # --- staged publication (manifest LAST) --------------------------------------
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent)
    )
    if verbose:
        print(f"Staging the four artifacts in {staging_dir} ...")
    artifact_names = [
        config.PHASE6_GROUP_ASSIGNMENTS_FILENAME,
        config.PHASE6_CONSISTENCY_SCORECARD_FILENAME,
        config.PHASE6_CONSISTENCY_REPORT_FILENAME,
        config.PHASE6_RUN_METADATA_FILENAME,
    ]
    try:
        assignments.to_csv(staging_dir / config.PHASE6_GROUP_ASSIGNMENTS_FILENAME, index=False)
        scorecard.to_csv(staging_dir / config.PHASE6_CONSISTENCY_SCORECARD_FILENAME, index=False)
        with open(staging_dir / config.PHASE6_CONSISTENCY_REPORT_FILENAME, "w", encoding="utf-8") as f:
            f.write(report_markdown)
        with open(staging_dir / config.PHASE6_RUN_METADATA_FILENAME, "w", encoding="utf-8") as f:
            json.dump(provenance, f, indent=2, sort_keys=True)
            f.write("\n")

        if verbose:
            print("Publishing staged artifacts (backup/rollback armed) ...")
        publication = _publish_with_rollback(
            staging_dir,
            output_dir,
            artifact_names,
            config.PHASE6_MANIFEST_FILENAME,
            overwrite=overwrite,
            verbose=verbose,
        )
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)

    if verbose:
        _print_execution_summary(context, output_dir)

    return {
        "group_assignments": assignments,
        "assignment_summary": assignment_summary,
        "scorecard": scorecard,
        "report_markdown": report_markdown,
        "context": context,
        "reference_validation": reference_status,
        "provenance": provenance,
        "publication": publication,
        "sample": validated["sample"],
        "paths": {k: Path(v) for k, v in paths.items()},
    }


def _print_execution_summary(context: Dict, output_dir: Path) -> None:
    """Print the headline values for independent comparison."""
    w = context["workload"]
    g = context["groups"]
    print("\n=== PHASE 6 CROSS-METHOD CONSISTENCY (published) ===")
    print(
        f"sample: {context['sample_size']:,} observations, "
        f"{context['fraud_label_count']} labelled frauds "
        f"(prevalence {context['fraud_prevalence']:.6f})"
    )
    print(
        f"overlap ({IF_RUN_ID} vs {LOF_RUN_ID}, saved 1% flags): "
        f"intersection {context['observed_intersection']}, union "
        f"{context['union_size']}, Jaccard {context['jaccard_if003_lof004']:.4f}"
    )
    print(
        f"hypergeometric null: expected "
        f"{context['expected_intersection_under_null']:.2f}, enrichment "
        f"{context['enrichment_observed_over_expected']:.2f}x, log10 upper tail "
        f"{context['log10_upper_tail_probability']:.2f}"
    )
    print(
        "groups: "
        + ", ".join(
            f"{GROUP_LABELS[key]}={g[key]['observation_count']}"
            f"({g[key]['fraud_count']} frauds)"
            for key in GROUP_KEYS
        )
    )
    print(
        f"review policies: Both-only {w['both_only']['reviews']} obs / "
        f"{w['both_only']['frauds']} frauds; each detector "
        f"{context['if003_flagged_count']}; union {w['union']['reviews']} / "
        f"{w['union']['frauds']}; Neither misses "
        f"{context['neither_fraud_count']} frauds"
    )
    print(f"outputs published to {output_dir}")
    print(f"NOTE: {EXPLORATORY_CAVEAT}")


def _format_problems(problems: List[str], category: str) -> str:
    lines = [f"Validation failed ({category}):"]
    lines.extend(f"  {i}. {p}" for i, p in enumerate(problems, start=1))
    return "\n".join(lines)


