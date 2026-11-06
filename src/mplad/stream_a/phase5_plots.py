"""Stream A -- Phase 5B: visualization layer (the eight authoritative figures).

Role and boundaries
-------------------
Phase 5B consumes, strictly read-only:

* the verified Phase 5A reproduction tables under
  ``results/stream a/phase 5/reproduction/`` -- the 10x10 Spearman matrix,
  the 10x10 top-1% Jaccard matrix, the hypergeometric overlap summary, the
  fraud-discovery curve table, the agreement-group table and the Phase 5A
  provenance record (``phase5_run_metadata.json``);
* the Phase 4 row-level evaluation dataset
  (``results/stream a/phase 4/reproduction/phase4_evaluation_dataset.csv``)
  for observation-level scores, SAVED flags and labels;
* the FS-A feature matrix
  (``data/processed/stream-a/features/ULB_FS_A_Baseline.csv``, ``row_id``
  preserved) for the PCA agreement map.

and renders EXACTLY eight figures (no alternate numbered iterations, no
ninth figure):

1. ``phase5_plot1_precision_recall.png``   -- PR curves, all ten runs
2. ``phase5_plot2_fraud_discovery.png``    -- recall & precision vs review budget
3. ``phase5_plot3_hypergeometric_overlap.png`` -- hypergeometric log-PMF + observed tail
4. ``phase5_plot4_spearman_matrix.png``    -- 10x10 Spearman heat map
5. ``phase5_plot5_jaccard_matrix.png``     -- 10x10 top-1% Jaccard heat map
6. ``phase5_plot6_topk_jaccard.png``       -- top-k Jaccard vs budget curves
7. ``phase5_plot7_rank_vs_rank.png``       -- IF_003 vs LOF_004 percentile scatter
8. ``phase5_plot8_pca_agreement.png``      -- PCA agreement map (FS-A features)

This module NEVER fits, refits, retunes or constructs an anomaly detector
(its only scikit-learn imports are ``sklearn.metrics`` -- the
precision-recall geometry -- and ``sklearn.decomposition.PCA``, a lossy 2-D
projection for visualization only); NEVER recalculates a Phase 4 metric
table or a Phase 5A bootstrap result; NEVER recomputes, rewrites or
otherwise modifies a saved canonical Phase 3 flag; and NEVER changes a
feature space. Every number drawn in the figures comes from the consumed
artifacts; the only derived quantities are plotting transforms (curve
geometry, average-rank percentiles, derived top-k masks under the SAME
tie-breaking policy Phase 5A documented, pairwise Jaccard of those masks,
and PCA coordinates).

Score, threshold and percentile conventions
-------------------------------------------
* ``anomaly_score`` (higher = more anomalous) is the only ranking input;
  ``native_score`` is never used for ranking.
* Fixed-threshold quantities use the SAVED Phase 3 flags exactly as
  supplied through the Phase 4 evaluation dataset.
* Derived top-k selections (budgets other than the canonical 1%) rank by
  descending ``anomaly_score`` with the Phase 5A tie policy: ties resolved
  by ascending position in the canonical evaluation-dataset row order
  (first-stored row wins; stable sort). The implementation reuses
  ``phase5_analysis.derive_topk_selection`` verbatim so the two layers can
  never drift apart.
* Rank-versus-rank percentiles: ``percentile = 1 - descending rank / n``
  where the descending rank (1 = most anomalous) is the tie-averaged rank
  of ``-anomaly_score``. 1 maps to the most anomalous observation, 0 to
  the least, and the boundary of the top-1% region therefore sits at
  percentile 0.99 (rank = n / 100).
* Random baselines: expected recall under random review = the reviewed
  fraction (the identity line); expected precision under random review =
  the positive-class prevalence. The obsolete incorrectly scaled
  discovery baseline is NOT used anywhere.
* The hypergeometric figure is interpreted ONLY against its stated null
  (independent uniform random selections) and the upper-tail probability
  is reported through its logarithm -- an underflowed probability is never
  presented as exactly zero.

Publication safety
------------------
Outputs go to ``results/stream a/phase 5/figures/reproduction/`` (a new
namespace: no historical Phase 5 figure is deleted or overwritten).
Rendering happens in a staging directory; every staged file is verified
(non-empty, PNG magic for figures) before anything is published; existing
outputs are backed up before replacement (``--overwrite``) and restored if
any part of the publication fails; the commit manifest is always published
LAST. The default CLI mode is a validation-only preflight that writes
nothing.
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
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import sklearn
from matplotlib.lines import Line2D
from scipy.stats import hypergeom, rankdata
from sklearn.decomposition import PCA
from sklearn.metrics import average_precision_score, precision_recall_curve

from mplad.common import config
from mplad.common.io import assert_outputs_writable, save_dataframe_csv, save_json
from mplad.common.manifest import (
    artifact_entry,
    build_manifest,
    load_manifest,
    save_manifest,
    verify_manifest,
)
from mplad.common.validation import validate_feature_matrix
from mplad.stream_a import phase5_analysis
from mplad.stream_a.phase5_analysis import derive_topk_selection

__all__ = [
    "Phase5PlotError",
    "Phase5InputError",
    "load_phase5_tables",
    "validate_matrix_table",
    "validate_hypergeometric_table",
    "validate_discovery_table",
    "validate_agreement_groups_table",
    "validate_phase5_metadata_payload",
    "descending_average_rank",
    "anomaly_percentile",
    "group_masks",
    "random_expected_recall",
    "random_expected_precision",
    "compute_pr_curves",
    "compute_topk_jaccard_curves",
    "join_fs_sample",
    "project_pca",
    "apply_style",
    "run_color",
    "is_highlighted",
    "build_figure_1_precision_recall",
    "build_figure_2_fraud_discovery",
    "build_figure_3_hypergeometric_overlap",
    "build_figure_4_spearman_matrix",
    "build_figure_5_jaccard_matrix",
    "build_figure_6_topk_jaccard",
    "build_figure_7_rank_vs_rank",
    "build_figure_8_pca_agreement",
    "save_figure",
    "collect_phase5_plots_preflight",
    "run_phase5_plots",
    "FIGURE_SPECS",
    "PERCENTILE_CONVENTION",
    "PCA_DISCLAIMER",
    "FS_A_SCALING_NOTE",
    "PHASE5_PLOT_OUTPUT_FILES",
]


class Phase5PlotError(ValueError):
    """Base class for Phase 5B contract violations."""


class Phase5InputError(Phase5PlotError):
    """A Phase 5B input artifact violates its contract."""


# ---------------------------------------------------------------------------
# Documented conventions (recorded in the plot metadata and the catalog)
# ---------------------------------------------------------------------------

#: Rank-versus-rank axis convention (figure 7).
PERCENTILE_CONVENTION: str = (
    "axis percentile = 1 - descending_average_rank / n, with the descending "
    "rank computed as the tie-averaged rank of -anomaly_score (1 = most "
    "anomalous, 0 = least anomalous); the boundary of the top-1% region is "
    "therefore the percentile 0.99 (rank = n/100)"
)

#: PCA interpretation note (figure 8 and the catalog).
PCA_DISCLAIMER: str = (
    "PCA is a LOSSY 2-D projection used for visualization only: the two "
    "components capture only part of the 30-dimensional FS-A variance, so "
    "distances and overlaps in this map must not be read as detector inputs "
    "or as evidence about the feature space"
)

#: FS-A preprocessing semantics honoured by figure 8.
FS_A_SCALING_NOTE: str = (
    "the FS-A matrix already embodies the frozen Phase 2 preprocessing "
    "(V1-V28 untouched PCA outputs; Time and Amount RobustScaler-scaled); "
    "Phase 5B applies NO additional rescaling and never standardizes the "
    "full matrix -- the stored FS-A values are projected as-is"
)

#: Neither-background sampling note (figure 8; None = no sampling).
NEITHER_BACKGROUND_NOTE: str = (
    "the full Neither group is plotted as the background (no subsampling); "
    "when subsampling is explicitly requested it draws strictly from the "
    "Neither group with a fixed recorded seed -- never from the full "
    "population relabelled as Neither"
)

#: Random-review baselines (figure 2).
RANDOM_BASELINES_NOTE: str = (
    "random expected recall = reviewed fraction (identity line); random "
    "expected precision = positive-class prevalence; the obsolete "
    "incorrectly scaled discovery baseline is not used"
)

#: The eight authoritative figures and their catalog metadata.
FIGURE_SPECS: Dict[int, Dict[str, str]] = {
    1: {
        "filename": config.PHASE5_FIGURE_FILENAMES[0],
        "title": "Precision-Recall curves — ten canonical runs",
        "purpose": (
            "Label-based ranking quality of every unsupervised run on the "
            "30,000-observation sample, at every operating threshold of the "
            "continuous anomaly score"
        ),
        "inputs": (
            "Phase 4 evaluation dataset (anomaly_score, Class); saved 1% "
            "flags for the highlighted operating points"
        ),
        "conventions": (
            "precision-recall geometry from anomaly_score (higher = more "
            "anomalous); AP in the legend; positive-class prevalence line; "
            "crosses mark the saved bottom-1% flag operating points of the "
            "highlighted runs"
        ),
    },
    2: {
        "filename": config.PHASE5_FIGURE_FILENAMES[1],
        "title": "Fraud discovery and precision versus review budget",
        "purpose": (
            "Operational value of each ranking: how much fraud is found and "
            "at what precision for a fixed manual-review budget"
        ),
        "inputs": "Phase 5A fraud-discovery curve table (all ten runs)",
        "conventions": RANDOM_BASELINES_NOTE,
    },
    3: {
        "filename": config.PHASE5_FIGURE_FILENAMES[2],
        "title": "Hypergeometric overlap of the saved 1% flags",
        "purpose": (
            "Extremity of the observed IF_003/LOF_004 flag overlap under the "
            "independent uniform-selection null"
        ),
        "inputs": "Phase 5A hypergeometric overlap summary (single row)",
        "conventions": (
            "full valid support of the hypergeometric log-PMF on a log10 "
            "probability scale; observed and expected intersections marked; "
            "upper-tail probability reported via its log10 (never as zero)"
        ),
    },
    4: {
        "filename": config.PHASE5_FIGURE_FILENAMES[3],
        "title": "Pairwise Spearman rank correlation — anomaly scores",
        "purpose": (
            "Global agreement of the ten rankings over all 30,000 "
            "observations"
        ),
        "inputs": "Phase 5A 10x10 Spearman matrix",
        "conventions": (
            "full [-1, +1] range, zero-centred diverging colormap, numeric "
            "annotations in every cell (colour is never the only channel)"
        ),
    },
    5: {
        "filename": config.PHASE5_FIGURE_FILENAMES[4],
        "title": "Pairwise Jaccard similarity — saved 1% flags",
        "purpose": (
            "Agreement of the canonical bottom-1% selections, exactly as "
            "saved by Phase 3 (never rederived from scores)"
        ),
        "inputs": "Phase 5A 10x10 top-1% Jaccard matrix (built from saved flags)",
        "conventions": (
            "full [0, 1] range, sequential colormap, numeric annotations in "
            "every cell; the IF_003/LOF_004 cell is outlined"
        ),
    },
    6: {
        "filename": config.PHASE5_FIGURE_FILENAMES[5],
        "title": "Top-k Jaccard agreement versus review budget",
        "purpose": (
            "How method-family agreement scales with the review budget, and "
            "where the highlighted IF_003/LOF_004 pair sits"
        ),
        "inputs": (
            "Phase 4 evaluation dataset (continuous anomaly scores + saved "
            "1% flags); Phase 5A tie-breaking policy"
        ),
        "conventions": (
            "budgets 0.1/0.2/0.5/1/2/5% with k = round(n*pct/100); the 1% "
            "point uses the SAVED canonical flags, every other budget uses "
            "derived top-k masks under the Phase 5A tie policy; within-family "
            "means exclude the diagonal self-comparisons"
        ),
    },
    7: {
        "filename": config.PHASE5_FIGURE_FILENAMES[6],
        "title": "Rank-versus-rank agreement — IF_003 vs LOF_004",
        "purpose": (
            "Observation-level structure of the agreement between the two "
            "highlighted runs and its four flag groups"
        ),
        "inputs": (
            "Phase 4 evaluation dataset (anomaly scores + saved 1% flags of "
            "IF_003 and LOF_004)"
        ),
        "conventions": (
            PERCENTILE_CONVENTION
            + "; Neither shown as a hexbin density, the three flagged "
            "groups as marker overlays with counts; reference lines at the "
            "0.99 top-1% boundaries"
        ),
    },
    8: {
        "filename": config.PHASE5_FIGURE_FILENAMES[7],
        "title": "PCA agreement map — IF_003 vs LOF_004 flag groups",
        "purpose": (
            "Where the four agreement groups sit in the FS-A feature space "
            "(visualization only)"
        ),
        "inputs": (
            "FS-A feature matrix joined on row_id; saved 1% flags of IF_003 "
            "and LOF_004 from the Phase 4 evaluation dataset"
        ),
        "conventions": (
            FS_A_SCALING_NOTE
            + "; PCA fitted on the joined 30,000-observation sample with the "
            "exact full SVD solver; explained variance of PC1/PC2 reported; "
            + PCA_DISCLAIMER
        ),
    },
}

#: Every file Phase 5B may write (figures + catalog + metadata + manifest).
PHASE5_PLOT_OUTPUT_FILES: Tuple[str, ...] = (
    *config.PHASE5_FIGURE_FILENAMES,
    config.PHASE5_FIGURE_CATALOG_FILENAME,
    config.PHASE5_PLOT_METADATA_FILENAME,
    config.PHASE5_PLOT_MANIFEST_FILENAME,
)

PNG_MAGIC: bytes = b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------------------
# Visual consistency: shared styling (colourblind-conscious; colour is never
# the only encoding channel -- line styles, markers, counts and numeric
# annotations carry the same information)
# ---------------------------------------------------------------------------

#: Consistent IF (blue family) / LOF (orange family) run colours. The three
#: highlighted configurations use saturated, heavy weights; the remaining
#: runs stay in pale shades of their family hue.
_RUN_COLORS: Dict[str, str] = {
    "IF_001": "#9ecae1",
    "IF_002": "#6baed6",
    "IF_003": "#08519c",
    "IF_004": "#08306b",
    "IF_005": "#4292c6",
    "LOF_001": "#fdd0a2",
    "LOF_002": "#fdae6b",
    "LOF_003": "#fd8d3c",
    "LOF_004": "#a63603",
    "LOF_005": "#e6550d",
}

#: Okabe-Ito colourblind-safe palette for the four agreement groups.
GROUP_COLORS: Dict[str, str] = {
    "both": "#D55E00",
    "if_only": "#0072B2",
    "lof_only": "#009E73",
    "neither": "#999999",
}
GROUP_MARKERS: Dict[str, str] = {
    "both": "o",
    "if_only": "s",
    "lof_only": "^",
    "neither": ".",
}
GROUP_LABELS: Dict[str, str] = {
    "both": "Both",
    "if_only": "IF-only",
    "lof_only": "LOF-only",
    "neither": "Neither",
}
GROUP_ORDER: Tuple[str, ...] = ("both", "if_only", "lof_only", "neither")

#: The highlighted runs (selected after inspecting label-informed Phase 4
#: results -- every comparison involving them is exploratory).
HIGHLIGHT_RUN_IDS: Tuple[str, ...] = tuple(config.PHASE5_BOOTSTRAP_RUN_IDS)

_HIGHLIGHT_LINESTYLES: Dict[str, str] = {"IF_003": "-", "IF_004": "--", "LOF_004": "-"}


def apply_style() -> None:
    """Apply the shared publication-quality rcParams (idempotent)."""
    matplotlib.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "figure.dpi": 100,
            "savefig.dpi": config.PHASE5_PLOT_DPI_DEFAULT,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
            "axes.titlesize": 12,
            "axes.titleweight": "semibold",
            "axes.labelsize": 10.5,
            "axes.labelweight": "regular",
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "legend.frameon": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "lines.solid_capstyle": "round",
        }
    )


def is_highlighted(run_id: str) -> bool:
    """True for the three highlighted configurations."""
    return run_id in HIGHLIGHT_RUN_IDS


def run_color(run_id: str) -> str:
    """Consistent family colour: blues for IF runs, oranges for LOF runs."""
    if run_id in _RUN_COLORS:
        return _RUN_COLORS[run_id]
    if run_id.startswith("IF_"):
        return "#2171b5"
    if run_id.startswith("LOF_"):
        return "#e6550d"
    return "#7f7f7f"


def run_line_kwargs(run_id: str) -> Dict:
    """Line style for one run: highlighted runs are heavy and labelled,
    the remaining runs are thin, pale and semi-transparent."""
    if is_highlighted(run_id):
        return {
            "color": run_color(run_id),
            "linewidth": 2.4,
            "linestyle": _HIGHLIGHT_LINESTYLES.get(run_id, "-"),
            "alpha": 1.0,
            "zorder": 5,
        }
    return {
        "color": run_color(run_id),
        "linewidth": 1.1,
        "linestyle": "-",
        "alpha": 0.65,
        "zorder": 3,
    }


# ---------------------------------------------------------------------------
# Input validation: Phase 5A tables
# ---------------------------------------------------------------------------

def _require_file(path: Path, what: str) -> None:
    if not Path(path).is_file():
        raise FileNotFoundError(
            f"{what} not found: {path}\n"
            f"Phase 5B consumes the verified Phase 5A reproduction tables; "
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

    Checks: DataFrame; leading ``run_id`` index plus one column per expected
    run (exact label set on both axes, canonical order preserved); finite
    values inside ``value_range``; exact symmetry; diagonal exactly 1.0.
    Returns the matrix re-indexed in canonical run order.
    """
    expected_run_ids = list(expected_run_ids)
    if not isinstance(matrix_df, pd.DataFrame):
        raise Phase5InputError(f"{name}: expected a pandas DataFrame")
    problems: List[str] = []
    index_label = matrix_df.index.name if matrix_df.index.name is not None else "run_id"
    if list(matrix_df.index) != expected_run_ids or list(matrix_df.columns) != expected_run_ids:
        problems.append(
            f"axes must list the expected runs in canonical order "
            f"(index label '{index_label}'; got index {list(matrix_df.index)}, "
            f"columns {list(matrix_df.columns)})"
        )
    if problems:
        raise Phase5InputError(_format_problems(problems, f"{name} schema"))

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
        raise Phase5InputError(_format_problems(problems, f"{name} integrity"))
    return matrix_df.loc[expected_run_ids, expected_run_ids]


def validate_hypergeometric_table(hyper_df: pd.DataFrame) -> Dict:
    """Validate the one-row Phase 5A hypergeometric summary; return a dict."""
    if not isinstance(hyper_df, pd.DataFrame) or hyper_df.shape[0] != 1:
        raise Phase5InputError(
            "phase5_hypergeometric_overlap.csv must contain exactly one row "
            f"(got {0 if not isinstance(hyper_df, pd.DataFrame) else hyper_df.shape[0]})"
        )
    required = [
        c
        for c in phase5_analysis.HYPERGEOMETRIC_OVERLAP_COLUMNS
        if c != "null_model"
    ]
    missing = [c for c in required if c not in hyper_df.columns]
    if missing:
        raise Phase5InputError(
            "phase5_hypergeometric_overlap.csv is missing column(s): " + ", ".join(missing)
        )
    row = {
        c: hyper_df.iloc[0][c] for c in phase5_analysis.HYPERGEOMETRIC_OVERLAP_COLUMNS
    }
    try:
        row["n_observations"] = int(row["n_observations"])
        row["run_a_flagged"] = int(row["run_a_flagged"])
        row["run_b_flagged"] = int(row["run_b_flagged"])
        row["observed_intersection"] = int(row["observed_intersection"])
        row["union_size"] = int(row["union_size"])
        row["threshold_pct"] = float(row["threshold_pct"])
        row["expected_intersection"] = float(row["expected_intersection"])
        row["enrichment_observed_over_expected"] = float(
            row["enrichment_observed_over_expected"]
        )
        row["survival_upper_tail"] = float(row["survival_upper_tail"])
        row["log_survival"] = float(row["log_survival"])
        row["log10_survival"] = float(row["log10_survival"])
    except (TypeError, ValueError) as exc:
        raise Phase5InputError(
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
        problems.append(
            f"union {union} != k_a + k_b - observed ({k_a + k_b - observed})"
        )
    if not math.isclose(
        row["expected_intersection"], (k_a * k_b) / n, rel_tol=1e-9, abs_tol=1e-9
    ):
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
            f"log10 upper-tail probability must be finite and <= 0 "
            f"(got {row['log10_survival']})"
        )
    if not math.isclose(
        row["log10_survival"], row["log_survival"] / math.log(10.0),
        rel_tol=1e-9, abs_tol=1e-12,
    ):
        problems.append("log10_survival != log_survival / ln(10)")
    if problems:
        raise Phase5InputError(_format_problems(problems, "hypergeometric summary integrity"))
    return row


def validate_discovery_table(
    discovery_df: pd.DataFrame,
    expected_run_ids: Sequence[str],
    sample_size: int,
    fraud_count: int,
) -> pd.DataFrame:
    """Validate the Phase 5A fraud-discovery curve table.

    Checks: exact schema; one complete block per expected run with budgets
    exactly ``1..sample_size``; ``fraud_found`` integral, non-decreasing and
    bounded by the total fraud count; ``precision == fraud_found / budget``
    and ``recall == fraud_found / total frauds`` (both in [0, 1]); the
    per-run maximum frauds equal the total fraud count (every ranking
    eventually reviews every observation).
    """
    expected_run_ids = list(expected_run_ids)
    if not isinstance(discovery_df, pd.DataFrame):
        raise Phase5InputError("discovery curve table: expected a pandas DataFrame")
    columns = list(discovery_df.columns)
    expected_columns = list(phase5_analysis.FRAUD_DISCOVERY_CURVE_COLUMNS)
    if columns != expected_columns:
        raise Phase5InputError(
            _format_problems(
                [f"columns {columns} != the frozen schema {expected_columns}"],
                "discovery curve schema",
            )
        )
    if len(discovery_df) != sample_size * len(expected_run_ids):
        raise Phase5InputError(
            _format_problems(
                [
                    f"row count {len(discovery_df):,} != sample_size x n_runs "
                    f"({sample_size:,} x {len(expected_run_ids)})"
                ],
                "discovery curve schema",
            )
        )
    if fraud_count < 1:
        raise Phase5InputError("recall is undefined when the sample has no fraud")

    problems: List[str] = []
    for run_id in expected_run_ids:
        block = discovery_df[discovery_df["run_id"] == run_id]
        if len(block) != sample_size:
            problems.append(f"run '{run_id}' contributes {len(block):,} rows")
            continue
        budgets = block["budget"].to_numpy()
        if not np.array_equal(budgets, np.arange(1, sample_size + 1)):
            problems.append(f"run '{run_id}': budgets are not exactly 1..{sample_size:,}")
            continue
        found = block["fraud_found"].to_numpy()
        precision = block["precision"].to_numpy(dtype=np.float64)
        recall = block["recall"].to_numpy(dtype=np.float64)
        if found.dtype.kind not in "iu" or found.min() < 0 or found.max() > fraud_count:
            problems.append(
                f"run '{run_id}': fraud_found outside [0, {fraud_count}]"
            )
            continue
        if np.any(np.diff(found) < 0):
            problems.append(f"run '{run_id}': fraud_found decreases with budget")
        if not np.allclose(precision, found / budgets, rtol=1e-9, atol=1e-12):
            problems.append(f"run '{run_id}': precision != fraud_found / budget")
        if not np.allclose(recall, found / fraud_count, rtol=1e-9, atol=1e-12):
            problems.append(f"run '{run_id}': recall != fraud_found / total frauds")
        if int(found[-1]) != fraud_count:
            problems.append(
                f"run '{run_id}': final frauds found {int(found[-1])} != total "
                f"fraud count {fraud_count}"
            )
    if problems:
        raise Phase5InputError(_format_problems(problems, "discovery curve integrity"))
    return discovery_df


def validate_agreement_groups_table(
    groups_df: pd.DataFrame,
    expected_run_ids_pair: Tuple[str, str],
    sample_size: int,
    fraud_count: int,
) -> pd.DataFrame:
    """Validate the four-row Phase 5A agreement-group table (schema, group
    set, exhaustive partition, fraud accounting)."""
    if not isinstance(groups_df, pd.DataFrame):
        raise Phase5InputError("agreement groups table: expected a pandas DataFrame")
    columns = list(groups_df.columns)
    expected_columns = list(phase5_analysis.AGREEMENT_GROUPS_COLUMNS)
    if columns != expected_columns:
        raise Phase5InputError(
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
    if sorted(groups_df["group"].tolist()) != sorted(GROUP_ORDER):
        problems.append(f"group column must contain exactly {list(GROUP_ORDER)}")
    if problems:
        raise Phase5InputError(_format_problems(problems, "agreement groups schema"))

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
        raise Phase5InputError(_format_problems(problems, "agreement groups integrity"))
    return groups_df.set_index("group").loc[list(GROUP_ORDER)].reset_index()


def validate_phase5_metadata_payload(
    payload: object,
    expected_run_ids: Sequence[str],
    expected_sample_size: int,
    expected_fraud_count: int,
) -> Dict:
    """Validate the Phase 5A provenance record (the fields Phase 5B consumes).

    Contract (Phase 5A contract section 5.9): a JSON object with
    ``phase == "5A"``; ``run_ids``; ``sample.sample_size`` and
    ``sample.fraud_count``; ``analytical_conventions.tie_breaking`` equal to
    the Phase 5A tie policy this layer must reuse verbatim; and the recorded
    input hash ``inputs.evaluation_dataset.sha256`` (used for the
    cross-snapshot consistency check against the Phase 4 dataset actually
    consumed here).
    """
    if not isinstance(payload, dict):
        raise Phase5InputError(
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
        if sample.get("sample_size") != expected_sample_size:
            problems.append(
                f"sample.sample_size {sample.get('sample_size'):,} != the "
                f"expected {expected_sample_size:,}"
            )
        if sample.get("fraud_count") != expected_fraud_count:
            problems.append(
                f"sample.fraud_count {sample.get('fraud_count')} != the "
                f"expected {expected_fraud_count}"
            )
    conventions = payload.get("analytical_conventions")
    if not isinstance(conventions, dict):
        problems.append("'analytical_conventions' must be a JSON object")
    elif conventions.get("tie_breaking") != phase5_analysis.TIE_BREAK_POLICY:
        problems.append(
            "'analytical_conventions.tie_breaking' does not match the Phase 5A "
            "tie policy implemented in this repository -- derived top-k masks "
            "would silently disagree with the published Phase 5A tables"
        )
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
        raise Phase5InputError(_format_problems(problems, "Phase 5A run metadata"))
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
                "hashes are recorded in the plot metadata. Manifest "
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


def load_phase5_tables(
    phase5_dir: Path,
    expected_run_ids: Sequence[str],
    sample_size: int,
    fraud_count: int,
) -> Dict:
    """Load and validate every consumed Phase 5A table.

    Returns ``{"spearman", "jaccard", "hypergeometric", "discovery",
    "agreement_groups"}`` where the matrices are DataFrames indexed by run
    ID, the hypergeometric summary is a validated dict and the other two
    are validated DataFrames.
    """
    phase5_dir = Path(phase5_dir)
    expected_run_ids = list(expected_run_ids)

    spearman_path = phase5_dir / config.PHASE5_PAIRWISE_SPEARMAN_FILENAME
    _require_file(spearman_path, "Phase 5A Spearman matrix")
    spearman_df = validate_matrix_table(
        pd.read_csv(spearman_path, index_col=0),
        expected_run_ids,
        "phase5_pairwise_spearman.csv",
        (-1.0, 1.0),
    )

    jaccard_df = validate_matrix_table(
        pd.read_csv(
            phase5_dir / config.PHASE5_PAIRWISE_JACCARD_FILENAME, index_col=0
        ),
        expected_run_ids,
        "phase5_pairwise_jaccard_1pct.csv",
        (0.0, 1.0),
    )

    hyper_df = _read_required_csv(
        phase5_dir / config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME,
        "Phase 5A hypergeometric overlap summary",
    )
    hypergeometric = validate_hypergeometric_table(hyper_df)

    discovery_df = _read_required_csv(
        phase5_dir / config.PHASE5_FRAUD_DISCOVERY_CURVE_FILENAME,
        "Phase 5A fraud-discovery curve table",
    )
    discovery_df = validate_discovery_table(
        discovery_df, expected_run_ids, sample_size, fraud_count
    )

    groups_df = _read_required_csv(
        phase5_dir / config.PHASE5_AGREEMENT_GROUPS_FILENAME,
        "Phase 5A agreement-group table",
    )
    agreement_groups = validate_agreement_groups_table(
        groups_df,
        (config.PHASE5_OVERLAP_RUN_A, config.PHASE5_OVERLAP_RUN_B),
        sample_size,
        fraud_count,
    )

    return {
        "spearman": spearman_df,
        "jaccard": jaccard_df,
        "hypergeometric": hypergeometric,
        "discovery": discovery_df,
        "agreement_groups": agreement_groups,
    }


# ---------------------------------------------------------------------------
# Derived plotting quantities (never written back to any artifact)
# ---------------------------------------------------------------------------

def descending_average_rank(scores: np.ndarray) -> np.ndarray:
    """Tie-averaged descending rank: 1 = most anomalous (highest score)."""
    scores = np.asarray(scores)
    if scores.ndim != 1 or scores.size == 0:
        raise Phase5PlotError("'scores' must be a non-empty 1-D array")
    return rankdata(-scores.astype(np.float64), method="average")


def anomaly_percentile(scores: np.ndarray) -> np.ndarray:
    """Percentile with 1 = most anomalous and 0 = least anomalous.

    ``percentile = 1 - descending_average_rank / n``; the boundary of the
    top-1% region (rank = n / 100) therefore sits at percentile 0.99.
    """
    ranks = descending_average_rank(scores)
    n = ranks.shape[0]
    return 1.0 - ranks / float(n)


def group_masks(flags_a: np.ndarray, flags_b: np.ndarray) -> Dict[str, np.ndarray]:
    """The four agreement groups as boolean masks (disjoint and exhaustive).

    ``both`` (flagged by both runs), ``if_only`` (flagged by run_a only),
    ``lof_only`` (flagged by run_b only), ``neither``.
    """
    flags_a = np.asarray(flags_a)
    flags_b = np.asarray(flags_b)
    if flags_a.shape != flags_b.shape or flags_a.ndim != 1:
        raise Phase5PlotError("flags_a and flags_b must be 1-D arrays of equal length")
    a = flags_a == 1
    b = flags_b == 1
    return {
        "both": a & b,
        "if_only": a & ~b,
        "lof_only": ~a & b,
        "neither": ~a & ~b,
    }


def random_expected_recall(review_fraction: np.ndarray) -> np.ndarray:
    """Expected recall when a ``review_fraction`` of the sample is reviewed
    in random order: exactly the reviewed fraction (the identity line)."""
    return np.asarray(review_fraction, dtype=np.float64).copy()


def random_expected_precision(prevalence: float) -> float:
    """Expected precision under random review: the positive-class prevalence."""
    prevalence = float(prevalence)
    if not 0.0 < prevalence < 1.0:
        raise Phase5PlotError(
            f"prevalence must lie in (0, 1) for the random-precision baseline, "
            f"got {prevalence}"
        )
    return prevalence


def compute_pr_curves(aligned: Dict, run_ids: Optional[Sequence[str]] = None) -> Dict:
    """Precision-recall geometry per run from the canonical anomaly scores.

    Uses ``anomaly_score`` (higher = more anomalous) with binary ``Class``;
    returns per run the precision/recall arrays, the AP, and the operating
    point of the SAVED bottom-1% flags (TP / flagged, TP / frauds).
    """
    run_ids = list(aligned["run_ids"]) if run_ids is None else list(run_ids)
    labels = aligned["labels"]
    curves: Dict[str, Dict] = {}
    for run_id in run_ids:
        run_data = aligned["runs"][run_id]
        score = np.asarray(run_data["anomaly_score"], dtype=np.float64)
        precision, recall, _ = precision_recall_curve(labels, score)
        ap = float(average_precision_score(labels, score))
        flags = np.asarray(run_data["flag"]) == 1
        tp = int(np.count_nonzero(flags & (labels == 1)))
        flagged = int(np.count_nonzero(flags))
        frauds = int(np.count_nonzero(labels == 1))
        curves[run_id] = {
            "precision": precision,
            "recall": recall,
            "ap": ap,
            "flagged_operating_point": {
                "tp": tp,
                "precision_at_1pct": (tp / flagged) if flagged else 0.0,
                "recall_at_1pct": (tp / frauds) if frauds else 0.0,
            },
        }
    return curves


def compute_topk_jaccard_curves(
    aligned: Dict,
    threshold_percentages: Optional[Sequence[float]] = None,
    run_ids: Optional[Sequence[str]] = None,
) -> Tuple[pd.DataFrame, Dict]:
    """Mean pairwise Jaccard versus review budget, from the row-level data.

    For each budget percentage with ``k = round(n * pct / 100)``: at the
    canonical 1% the SAVED Phase 3 flags are used as supplied; every other
    budget derives top-k masks from the continuous ``anomaly_score`` under
    the Phase 5A tie-breaking policy (``phase5_analysis.derive_topk_selection``
    verbatim). Reports the mean within-IF, within-LOF and cross-method
    Jaccard (diagonal self-comparisons excluded by construction: only
    i < j pairs enter the means) plus the IF_003/LOF_004 pair separately.
    """
    if threshold_percentages is None:
        threshold_percentages = list(config.PHASE5_MULTI_THRESHOLD_PERCENTS)
    threshold_percentages = [float(p) for p in threshold_percentages]
    run_ids = list(aligned["run_ids"]) if run_ids is None else list(run_ids)
    phase5_analysis._require_runs(aligned, run_ids)  # noqa: SLF001 -- same-package reuse

    n = int(aligned["sample_size"])
    if_runs = [r for r in run_ids if r.startswith("IF_")]
    lof_runs = [r for r in run_ids if r.startswith("LOF_")]
    if not if_runs or not lof_runs:
        raise Phase5PlotError(
            "top-k Jaccard curves require at least one IF run and one LOF run"
        )
    pair = (config.PHASE5_OVERLAP_RUN_A, config.PHASE5_OVERLAP_RUN_B)
    pair_present = pair[0] in run_ids and pair[1] in run_ids

    rows = []
    per_budget_selection_sizes: Dict[str, Dict[str, int]] = {}
    for pct in threshold_percentages:
        k = int(round(n * pct / 100.0))
        if k < 1 or k > n:
            raise Phase5PlotError(
                f"budget {pct:g}% yields k={k} outside 1..{n} on a sample of "
                f"{n} observations"
            )
        if pct == config.PHASE5_CANONICAL_THRESHOLD_PCT:
            masks = {
                r: np.asarray(aligned["runs"][r]["flag"]) == 1 for r in run_ids
            }
            source = "canonical_saved_flags"
        else:
            masks = {
                r: derive_topk_selection(aligned["runs"][r]["anomaly_score"], k) == 1
                for r in run_ids
            }
            source = "derived_topk"
        per_budget_selection_sizes[f"{pct:g}%"] = {
            r: int(masks[r].sum()) for r in run_ids
        }

        pair_values: Dict[Tuple[str, str], float] = {}
        for i, ri in enumerate(run_ids):
            for rj in run_ids[i + 1:]:
                intersection = int(np.count_nonzero(masks[ri] & masks[rj]))
                union = int(np.count_nonzero(masks[ri] | masks[rj]))
                pair_values[(ri, rj)] = 1.0 if union == 0 else intersection / union

        def _mean(pairs: List[Tuple[str, str]]) -> float:
            return float(np.mean([pair_values[p] for p in pairs])) if pairs else float("nan")

        within_if = _mean([(a, b) for a in if_runs for b in if_runs if a < b])
        within_lof = _mean([(a, b) for a in lof_runs for b in lof_runs if a < b])
        cross = _mean([(a, b) for a in if_runs for b in lof_runs])
        pair_value = pair_values[pair] if pair_present else float("nan")
        rows.append(
            {
                "threshold_pct": pct,
                "k": k,
                "selection_source": source,
                "within_if_mean_jaccard": within_if,
                "within_lof_mean_jaccard": within_lof,
                "cross_method_mean_jaccard": cross,
                "pair_jaccard": pair_value,
                "pair": f"{pair[0]} vs {pair[1]}" if pair_present else "",
            }
        )

    curves = pd.DataFrame(rows)
    details = {
        "k_rule": "k = round(n * pct / 100), required to satisfy 1 <= k <= n",
        "tie_breaking": phase5_analysis.TIE_BREAK_POLICY,
        "canonical_threshold_pct": config.PHASE5_CANONICAL_THRESHOLD_PCT,
        "canonical_threshold_source": "saved Phase 3 flags (never rederived)",
        "diagonal_excluded": "within-method means average the i<j pairs only",
        "per_budget_selection_sizes": per_budget_selection_sizes,
    }
    return curves, details


def join_fs_sample(fs_df: pd.DataFrame, sample_row_ids: np.ndarray) -> Tuple[np.ndarray, List[str]]:
    """Join the FS-A feature matrix onto the sample ``row_id`` sequence.

    Returns ``(X, feature_columns)`` with the rows aligned EXACTLY to
    ``sample_row_ids`` (a one-to-one join on ``row_id``; any missing or
    duplicated identifier is a hard error) and the columns in the frozen
    FS-A order (``Time, V1..V28, Amount``). The stored FS-A values are
    returned as-is: no rescaling, no standardization (see
    ``FS_A_SCALING_NOTE``).
    """
    feature_cols = validate_feature_matrix(fs_df)
    ordered_cols = [c for c in config.EXPECTED_FEATURE_COLUMNS]
    if set(feature_cols) != set(ordered_cols):
        raise Phase5InputError(
            "FS-A feature columns do not match the frozen feature space"
        )
    sample_row_ids = np.asarray(sample_row_ids)
    fs_indexed = fs_df.set_index(config.ID_COLUMN)[ordered_cols]
    missing = np.setdiff1d(sample_row_ids, fs_indexed.index.to_numpy())
    if missing.size:
        raise Phase5InputError(
            f"{missing.size} sample row_id(s) are absent from the FS-A feature "
            f"matrix (e.g. {missing[:5].tolist()}) -- the PCA agreement map "
            "requires every sampled observation to carry FS-A features"
        )
    X = fs_indexed.reindex(sample_row_ids).to_numpy(dtype=np.float64)
    if not np.isfinite(X).all():
        raise Phase5InputError(
            "the joined FS-A feature matrix contains non-finite values"
        )
    return X, ordered_cols


def project_pca(X: np.ndarray, n_components: int = 2) -> Tuple[np.ndarray, np.ndarray]:
    """Lossy 2-D PCA projection for visualization only (exact full SVD,
    fitted on the joined sample; deterministic -- no randomized solver).

    Returns ``(coords, explained_variance_ratio)``.
    """
    X = np.asarray(X, dtype=np.float64)
    if X.ndim != 2 or X.shape[0] < 2:
        raise Phase5PlotError("'X' must be a 2-D array with at least two rows")
    pca = PCA(n_components=n_components, svd_solver="full")
    coords = pca.fit_transform(X)
    return coords, pca.explained_variance_ratio_


# ---------------------------------------------------------------------------
# Shared loading / validation of every input (no writes, no plots)
# ---------------------------------------------------------------------------

def _resolve_input_paths(
    phase5_dir: Optional[Path],
    phase4_dataset_path: Optional[Path],
    fs_a_path: Optional[Path],
) -> Tuple[Path, Path, Path]:
    return (
        Path(phase5_dir) if phase5_dir is not None else config.DEFAULT_PHASE5_OUTPUT_DIR,
        Path(phase4_dataset_path)
        if phase4_dataset_path is not None
        else config.PHASE4_EVALUATION_DATASET_PATH,
        Path(fs_a_path) if fs_a_path is not None else config.DEFAULT_FS_A_PATH,
    )


def _artifact_info(path: Path) -> Dict:
    info = artifact_entry(path)
    return {"path": str(path), **info}


def _load_and_validate_inputs(
    phase5_dir: Path,
    phase4_dataset_path: Path,
    fs_a_path: Path,
    expected_run_ids: Optional[Sequence[str]],
    expected_sample_size: int,
    verbose: bool = True,
) -> Dict:
    """Load and validate every Phase 5B input; render and write nothing.

    Order of operations: the optional Phase 5A and Phase 4 output manifests
    are verified FIRST (hash-verification genuinely happens before the
    artifacts are consumed), then the Phase 4 evaluation dataset is loaded
    and validated (reusing the hardened Phase 5A validators), then the
    Phase 5A tables are loaded, validated and cross-checked against the
    row-level data, then the FS-A matrix is validated and joined.
    """
    if expected_run_ids is None:
        expected_run_ids = list(config.PHASE3_CANONICAL_RUN_IDS)
    expected_run_ids = list(expected_run_ids)

    # --- input manifests -------------------------------------------------
    consumed_phase5_names = (
        config.PHASE5_PAIRWISE_SPEARMAN_FILENAME,
        config.PHASE5_PAIRWISE_JACCARD_FILENAME,
        config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME,
        config.PHASE5_FRAUD_DISCOVERY_CURVE_FILENAME,
        config.PHASE5_AGREEMENT_GROUPS_FILENAME,
        config.PHASE5_RUN_METADATA_FILENAME,
    )
    pre_input_hashes = {}
    for key, p in (
        ("phase5_run_metadata", phase5_dir / config.PHASE5_RUN_METADATA_FILENAME),
        ("phase4_evaluation_dataset", phase4_dataset_path),
        ("fs_a_feature_matrix", fs_a_path),
    ):
        if Path(p).is_file():
            pre_input_hashes[key] = _artifact_info(Path(p))

    if verbose:
        print("Checking for the Phase 5A integrity manifest ...")
    phase5_manifest = _check_input_manifest(
        phase5_dir / config.PHASE5_PLOTS_INPUT_MANIFEST_FILENAME,
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
        phase4_dataset_path.parent / config.PHASE5_PLOTS_PHASE4_MANIFEST_FILENAME,
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
        raise Phase5InputError(
            f"the primary dataset must contain exactly {expected_sample_size:,} "
            f"observations (the canonical experiment size); it carries "
            f"{sample_size:,}. Pass --expected-sample-size deliberately if a "
            "non-canonical replica is being visualized."
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

    # --- Phase 5A provenance record ---------------------------------------
    if verbose:
        print(f"Loading Phase 5A run metadata from {phase5_dir / config.PHASE5_RUN_METADATA_FILENAME} ...")
    _require_file(
        phase5_dir / config.PHASE5_RUN_METADATA_FILENAME,
        "Phase 5A run metadata",
    )
    with open(phase5_dir / config.PHASE5_RUN_METADATA_FILENAME, "r", encoding="utf-8") as f:
        phase5_metadata = json.load(f)
    phase5_metadata = validate_phase5_metadata_payload(
        phase5_metadata, expected_run_ids, sample_size, fraud_count
    )
    recorded_hash = phase5_metadata["inputs"]["evaluation_dataset"]["sha256"].lower()
    actual_hash = artifact_entry(phase4_dataset_path)["sha256"].lower()
    if recorded_hash != actual_hash:
        raise Phase5InputError(
            "cross-snapshot inconsistency: the Phase 5A provenance record was "
            "computed against a Phase 4 evaluation dataset with SHA-256 "
            f"{recorded_hash}, but the dataset being consumed now hashes to "
            f"{actual_hash}. The Phase 5A tables and the row-level data must "
            "come from the SAME Phase 4 execution -- re-run Phase 5A against "
            "the current Phase 4 outputs before plotting."
        )
    if verbose:
        print("  cross-snapshot check: Phase 5A input hash matches the consumed dataset")

    # --- Phase 5A tables ---------------------------------------------------
    if verbose:
        print(f"Loading Phase 5A tables from {phase5_dir} ...")
    tables = load_phase5_tables(phase5_dir, expected_run_ids, sample_size, fraud_count)

    # --- cross-checks against the row-level data ---------------------------
    run_a, run_b = config.PHASE5_OVERLAP_RUN_A, config.PHASE5_OVERLAP_RUN_B
    flags_a = aligned["runs"][run_a]["flag"] == 1
    flags_b = aligned["runs"][run_b]["flag"] == 1
    masks = group_masks(aligned["runs"][run_a]["flag"], aligned["runs"][run_b]["flag"])
    hyper = tables["hypergeometric"]
    problems: List[str] = []
    if hyper["run_a"] != run_a or hyper["run_b"] != run_b:
        problems.append(
            f"hypergeometric summary covers ({hyper['run_a']}, {hyper['run_b']}), "
            f"expected ({run_a}, {run_b})"
        )
    if hyper["n_observations"] != sample_size:
        problems.append(
            f"hypergeometric n {hyper['n_observations']:,} != sample size {sample_size:,}"
        )
    if hyper["run_a_flagged"] != int(flags_a.sum()) or hyper["run_b_flagged"] != int(
        flags_b.sum()
    ):
        problems.append(
            "hypergeometric flagged counts disagree with the saved flags in the "
            "Phase 4 evaluation dataset "
            f"({hyper['run_a_flagged']}/{hyper['run_b_flagged']} vs "
            f"{int(flags_a.sum())}/{int(flags_b.sum())})"
        )
    if hyper["observed_intersection"] != int(masks["both"].sum()):
        problems.append(
            f"hypergeometric observed intersection {hyper['observed_intersection']} "
            f"!= row-level both-flagged count {int(masks['both'].sum())}"
        )
    saved_jaccard = tables["jaccard"].loc[run_a, run_b]
    row_level_jaccard = float(
        np.count_nonzero(flags_a & flags_b) / np.count_nonzero(flags_a | flags_b)
    )
    if not math.isclose(float(saved_jaccard), row_level_jaccard, rel_tol=0, abs_tol=1e-12):
        problems.append(
            f"saved top-1% Jaccard [{run_a}, {run_b}] = {saved_jaccard:.6f} != "
            f"row-level flag Jaccard {row_level_jaccard:.6f}"
        )
    groups_table = tables["agreement_groups"].set_index("group")
    for group_name, mask in masks.items():
        table_count = int(groups_table.loc[group_name, "observation_count"])
        row_count = int(mask.sum())
        if table_count != row_count:
            problems.append(
                f"agreement group '{group_name}': table count {table_count} != "
                f"row-level count {row_count}"
            )
        table_frauds = int(groups_table.loc[group_name, "fraud_count"])
        row_frauds = int(np.count_nonzero(mask & (aligned["labels"] == 1)))
        if table_frauds != row_frauds:
            problems.append(
                f"agreement group '{group_name}': table frauds {table_frauds} != "
                f"row-level frauds {row_frauds}"
            )
    if problems:
        raise Phase5InputError(
            _format_problems(problems, "Phase 5A table / row-level consistency")
        )
    if verbose:
        print(
            "  cross-checks: flagged counts, observed intersection, group "
            "composition and the saved Jaccard all match the row-level data"
        )

    # --- FS-A feature matrix ----------------------------------------------
    if verbose:
        print(f"Loading FS-A feature matrix from {fs_a_path} ...")
    _require_file(fs_a_path, "FS-A feature matrix")
    fs_df = pd.read_csv(fs_a_path)
    X_joined, feature_cols = join_fs_sample(fs_df, aligned["row_ids"])
    if verbose:
        print(
            f"  joined {X_joined.shape[0]:,} observations x {X_joined.shape[1]} "
            f"FS-A features on row_id (no additional rescaling applied)"
        )

    inputs_info = {
        "phase5_spearman": _artifact_info(
            phase5_dir / config.PHASE5_PAIRWISE_SPEARMAN_FILENAME
        ),
        "phase5_jaccard_1pct": _artifact_info(
            phase5_dir / config.PHASE5_PAIRWISE_JACCARD_FILENAME
        ),
        "phase5_hypergeometric_overlap": _artifact_info(
            phase5_dir / config.PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME
        ),
        "phase5_fraud_discovery_curve": _artifact_info(
            phase5_dir / config.PHASE5_FRAUD_DISCOVERY_CURVE_FILENAME
        ),
        "phase5_agreement_groups": _artifact_info(
            phase5_dir / config.PHASE5_AGREEMENT_GROUPS_FILENAME
        ),
        "phase5_run_metadata": _artifact_info(
            phase5_dir / config.PHASE5_RUN_METADATA_FILENAME
        ),
        "phase4_evaluation_dataset": _artifact_info(phase4_dataset_path),
        "fs_a_feature_matrix": _artifact_info(fs_a_path),
    }

    for key, post_info in inputs_info.items():
        pre_info = pre_input_hashes.get(key)
        if pre_info is not None and (
            pre_info["sha256"] != post_info["sha256"]
            or pre_info["size_bytes"] != post_info["size_bytes"]
        ):
            raise Phase5InputError(
                f"Input artifact '{key}' changed on disk during Phase 5B execution."
            )

    return {
        "phase5_manifest": phase5_manifest,
        "phase4_manifest": phase4_manifest,
        "aligned": aligned,
        "dataset_summary": dataset_summary,
        "tables": tables,
        "phase5_metadata": phase5_metadata,
        "fs_df": fs_df,
        "X_joined": X_joined,
        "fs_feature_cols": feature_cols,
        "inputs_info": inputs_info,
        "sample": {
            "sample_size": sample_size,
            "fraud_count": fraud_count,
            "fraud_prevalence": dataset_summary["fraud_prevalence"],
            "per_run_flagged_counts": dataset_summary["per_run_flagged_counts"],
        },
    }


def _format_problems(problems: List[str], category: str) -> str:
    lines = [f"Validation failed ({category}):"]
    lines.extend(f"  {i}. {p}" for i, p in enumerate(problems, start=1))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Figure builders. Each returns (figure, metadata); none of them writes a
# file -- saving happens through save_figure into the staging directory.
# ---------------------------------------------------------------------------

def build_figure_1_precision_recall(aligned: Dict) -> Tuple[matplotlib.figure.Figure, Dict]:
    """Figure 1: precision-recall curves of all ten runs.

    Continuous ``anomaly_score`` (higher = more anomalous) against binary
    ``Class``; AP values in the legend; the sample positive-class prevalence
    as the no-skill reference; the saved bottom-1% flag operating points of
    the three highlighted runs marked with crosses.
    """
    apply_style()
    curves = compute_pr_curves(aligned)
    run_ids = list(aligned["run_ids"])
    n = int(aligned["sample_size"])
    fraud_count = int(aligned["fraud_count"])
    prevalence = fraud_count / n

    fig, ax = plt.subplots(figsize=(8.5, 6.5), layout="constrained")
    for run_id in run_ids:
        style = run_line_kwargs(run_id)
        label = f"{run_id} (AP = {curves[run_id]['ap']:.3f})"
        ax.plot(
            curves[run_id]["recall"],
            curves[run_id]["precision"],
            label=label,
            **style,
        )
    for run_id in run_ids:
        if is_highlighted(run_id):
            op = curves[run_id]["flagged_operating_point"]
            ax.plot(
                [op["recall_at_1pct"]],
                [op["precision_at_1pct"]],
                marker="x",
                markersize=9,
                markeredgewidth=2.2,
                color=run_color(run_id),
                linestyle="none",
                zorder=6,
            )
    ax.axhline(
        prevalence,
        color="#666666",
        linestyle=":",
        linewidth=1.4,
        zorder=2,
        label=(
            f"positive-class prevalence = {prevalence:.5f} "
            f"({fraud_count}/{n:,})"
        ),
    )
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.02)
    ax.set_title(
        "Precision-Recall curves — ten canonical runs\n"
        f"{n:,}-observation sample, continuous anomaly scores"
    )
    handles, labels = ax.get_legend_handles_labels()
    proxy = Line2D(
        [],
        [],
        marker="x",
        linestyle="none",
        color="#444444",
        label="saved 1% flags (fixed threshold)",
    )
    ax.legend(handles=[*handles, proxy], loc="upper right", ncol=1, fontsize=8.5)
    meta = {
        "figure_no": 1,
        "ap": {r: curves[r]["ap"] for r in run_ids},
        "prevalence": prevalence,
        "runs": run_ids,
        "highlighted": [r for r in run_ids if is_highlighted(r)],
    }
    return fig, meta


def build_figure_2_fraud_discovery(
    discovery_df: pd.DataFrame,
    sample_size: int,
    prevalence: float,
) -> Tuple[matplotlib.figure.Figure, Dict]:
    """Figure 2: recall and precision versus review budget (two panels).

    Data: the saved Phase 5A fraud-discovery curve table (all ten runs).
    Baselines: random expected recall = reviewed fraction (identity line);
    random expected precision = positive-class prevalence. The canonical 1%
    review budget is marked on both panels.
    """
    apply_style()
    run_ids = list(discovery_df["run_id"].unique())
    fig, (ax_r, ax_p) = plt.subplots(
        1, 2, figsize=(12.5, 5.6), sharex=True, layout="constrained"
    )

    for run_id in run_ids:
        block = discovery_df[discovery_df["run_id"] == run_id]
        fraction = block["budget"].to_numpy(dtype=np.float64) / float(sample_size)
        style = run_line_kwargs(run_id)
        ax_r.plot(fraction, block["recall"].to_numpy(dtype=np.float64), **style)
        ax_p.plot(fraction, block["precision"].to_numpy(dtype=np.float64), **style)

    # Random baselines (correctly scaled).
    grid = np.linspace(0.0, 1.0, 200)
    ax_r.plot(
        grid,
        random_expected_recall(grid),
        color="#555555",
        linestyle="--",
        linewidth=1.6,
        zorder=4,
        label="random review: expected recall = reviewed fraction",
    )
    ax_p.axhline(
        random_expected_precision(prevalence),
        color="#555555",
        linestyle="--",
        linewidth=1.6,
        zorder=4,
        label=f"random review: expected precision = prevalence ({prevalence:.5f})",
    )
    # Canonical 1% review budget reference.
    for ax in (ax_r, ax_p):
        ax.axvline(
            config.PHASE5_CANONICAL_THRESHOLD_PCT / 100.0,
            color="#999999",
            linestyle=":",
            linewidth=1.2,
            zorder=1,
        )
    ax_r.text(
        config.PHASE5_CANONICAL_THRESHOLD_PCT / 100.0 + 0.012,
        0.04,
        "canonical 1% budget",
        fontsize=8,
        color="#777777",
        rotation=90,
        va="bottom",
    )

    ax_r.set_xlabel("Review budget (fraction of the sample)")
    ax_r.set_ylabel("Recall (frauds found / total frauds)")
    ax_r.set_xlim(0.0, 1.0)
    ax_r.set_ylim(0.0, 1.02)
    ax_r.set_title("Recall versus review budget")
    ax_r.legend(loc="lower right", fontsize=8.5)

    ax_p.set_xlabel("Review budget (fraction of the sample)")
    ax_p.set_ylabel("Precision (frauds found / reviewed)")
    ax_p.set_xlim(0.0, 1.0)
    ax_p.set_ylim(0.0, 1.02)
    ax_p.set_title("Precision versus review budget")
    ax_p.legend(loc="upper right", fontsize=8.5)
    ax_p.text(
        0.02,
        -0.13,
        "run colours as in the left panel",
        transform=ax_p.transAxes,
        fontsize=8,
        color="#777777",
    )

    fig.suptitle(
        "Fraud discovery and precision versus review budget — ten canonical runs",
        fontsize=12,
    )
    meta = {
        "figure_no": 2,
        "runs": run_ids,
        "baselines": {
            "random_recall": "expected recall = reviewed fraction (identity)",
            "random_precision": f"expected precision = prevalence ({prevalence:.6f})",
        },
        "sample_size": sample_size,
    }
    return fig, meta


def build_figure_3_hypergeometric_overlap(
    hypergeometric: Dict,
) -> Tuple[matplotlib.figure.Figure, Dict]:
    """Figure 3: theoretical hypergeometric log-PMF over the FULL valid
    support, with the observed and expected intersections marked and the
    observed upper-tail result annotated.

    Probabilities are drawn on a log10 scale; the upper-tail probability is
    reported through its logarithm and never presented as exactly zero.
    """
    apply_style()
    n = int(hypergeometric["n_observations"])
    k_a = int(hypergeometric["run_a_flagged"])
    k_b = int(hypergeometric["run_b_flagged"])
    observed = int(hypergeometric["observed_intersection"])
    expected = float(hypergeometric["expected_intersection"])
    enrichment = float(hypergeometric["enrichment_observed_over_expected"])
    log10_survival = float(hypergeometric["log10_survival"])
    run_a = str(hypergeometric["run_a"])
    run_b = str(hypergeometric["run_b"])

    support_lo = max(0, k_a + k_b - n)
    support_hi = min(k_a, k_b)
    if observed < support_lo or observed > support_hi:
        raise Phase5PlotError(
            f"observed intersection {observed} outside the valid support "
            f"[{support_lo}, {support_hi}]"
        )
    support = np.arange(support_lo, support_hi + 1)
    logpmf = hypergeom.logpmf(support, n, k_a, k_b)
    if not np.isfinite(logpmf).all():
        # Guard: clip the display floor and LABEL it (never hide the clip).
        floor = float(np.nanmin(logpmf[np.isfinite(logpmf)])) - 50.0
        display = np.where(np.isfinite(logpmf), logpmf, floor) / math.log(10.0)
        floor_note = (
            f"log-PMF values below 10^{floor / math.log(10.0):.0f} are floored "
            "for display only"
        )
    else:
        display = logpmf / math.log(10.0)
        floor_note = ""
    log10_at_observed = float(
        hypergeom.logpmf(observed, n, k_a, k_b) / math.log(10.0)
    )

    fig, ax = plt.subplots(figsize=(9.0, 5.8), layout="constrained")
    ax.plot(
        support,
        display,
        color="#4292c6",
        linewidth=1.6,
        zorder=3,
        label="hypergeometric log-PMF (full valid support)",
    )
    # Upper-tail shading from the observed intersection to the support end.
    tail_mask = support >= observed
    if tail_mask.any():
        ax.fill_between(
            support[tail_mask],
            display[tail_mask],
            float(display.min()) - 5.0,
            color="#D55E00",
            alpha=0.12,
            zorder=1,
        )
    ax.axvline(
        observed,
        color="#D55E00",
        linewidth=1.8,
        zorder=4,
        label=f"observed intersection = {observed}",
    )
    ax.axvline(
        expected,
        color="#0072B2",
        linewidth=1.6,
        linestyle="--",
        zorder=4,
        label=f"expected under null = {expected:.2f}",
    )
    ax.plot(
        [observed],
        [log10_at_observed],
        marker="o",
        markersize=7,
        color="#D55E00",
        zorder=5,
    )

    annotation = (
        f"observed overlap = {observed} of {n:,} observations\n"
        f"enrichment = {enrichment:.2f}x the null expectation\n"
        rf"$P(X \geq {observed}) \approx 10^{{{log10_survival:.2f}}}$"
        "  (log-space; not zero)"
    )
    ax.text(
        0.985,
        0.975,
        annotation,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=9.5,
        bbox={"boxstyle": "round,pad=0.45", "facecolor": "white",
              "edgecolor": "#cccccc", "alpha": 0.92},
    )
    ax.text(
        0.985,
        0.035,
        f"displayed range: full support k = [{support_lo}, {support_hi}]"
        + (f" — {floor_note}" if floor_note else ""),
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color="#666666",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "white",
              "edgecolor": "none", "alpha": 0.85},
    )

    ax.set_xlabel(
        f"k = number of observations flagged by both {run_a} and {run_b}"
    )
    ax.set_ylabel("log10 probability mass  log10 P(X = k)")
    ax.set_title(
        f"Hypergeometric overlap of the saved 1% flags — {run_a} vs {run_b}\n"
        f"null: independent uniform random selections "
        f"(N = {n:,}, {k_a} vs {k_b} flagged)"
    )
    ax.legend(loc="center right", fontsize=8.5)
    meta = {
        "figure_no": 3,
        "support": [int(support_lo), int(support_hi)],
        "observed_intersection": observed,
        "expected_intersection": expected,
        "enrichment": enrichment,
        "log10_survival": log10_survival,
        "null_model": phase5_analysis.NULL_MODEL_DESCRIPTION,
    }
    return fig, meta


def _draw_matrix_figure(
    values: np.ndarray,
    run_ids: Sequence[str],
    *,
    cmap: str,
    vmin: float,
    vmax: float,
    title: str,
    colorbar_label: str,
    highlight_cells: Sequence[Tuple[int, int]],
    center_zero: bool,
) -> Tuple[matplotlib.figure.Figure, Dict]:
    """Shared renderer for the two 10x10 matrix figures."""
    apply_style()
    values = np.asarray(values, dtype=np.float64)
    n_runs = len(run_ids)
    fig, ax = plt.subplots(figsize=(8.6, 7.3), layout="constrained")
    image = ax.imshow(
        values,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        origin="upper",
        aspect="equal",
    )
    ax.set_xticks(range(n_runs))
    ax.set_yticks(range(n_runs))
    ax.set_xticklabels(run_ids, rotation=45, ha="right")
    ax.set_yticklabels(run_ids)
    ax.set_xlabel("run_id")
    ax.set_ylabel("run_id")

    # Numeric annotations in every cell: colour is never the only channel.
    for i in range(n_runs):
        for j in range(n_runs):
            v = values[i, j]
            if center_zero:
                # Diverging map: dark at the extremes, light near zero.
                text_color = "white" if abs(v) > 0.6 else "black"
            else:
                # Sequential viridis: dark purple at 0, bright yellow at 1 --
                # dark text on the bright end, white text on the dark end.
                text_color = "black" if v > 0.42 else "white"
            ax.text(
                j,
                i,
                f"{v:.2f}",
                ha="center",
                va="center",
                fontsize=7.6,
                color=text_color,
            )
    for i, j in highlight_cells:
        ax.add_patch(
            plt.Rectangle(
                (j - 0.5, i - 0.5),
                1.0,
                1.0,
                fill=False,
                edgecolor="black",
                linewidth=2.0,
            )
        )
    cbar = fig.colorbar(image, ax=ax, shrink=0.85)
    cbar.set_label(colorbar_label)
    cbar.ax.tick_params(labelsize=8.5)
    ax.set_title(title)
    meta = {
        "value_range": [float(vmin), float(vmax)],
        "run_ids": list(run_ids),
        "highlight_cells": [list(c) for c in highlight_cells] or None,
    }
    return fig, meta


def build_figure_4_spearman_matrix(
    spearman_df: pd.DataFrame,
) -> Tuple[matplotlib.figure.Figure, Dict]:
    """Figure 4: the saved 10x10 Spearman matrix, full [-1, +1] range,
    zero-centred diverging colormap, all ten runs labelled."""
    run_ids = list(spearman_df.index)
    i_a = run_ids.index(config.PHASE5_OVERLAP_RUN_A)
    i_b = run_ids.index(config.PHASE5_OVERLAP_RUN_B)
    fig, meta = _draw_matrix_figure(
        spearman_df.to_numpy(dtype=np.float64),
        run_ids,
        cmap="RdBu_r",
        vmin=-1.0,
        vmax=1.0,
        title=(
            "Pairwise Spearman rank correlation of anomaly scores\n"
            "(full [-1, +1] range, zero-centred; outlined cells: IF_003 vs LOF_004)"
        ),
        colorbar_label="Spearman correlation (tie-averaged ranks)",
        highlight_cells=[(i_b, i_a), (i_a, i_b)],
        center_zero=True,
    )
    meta["figure_no"] = 4
    meta["pair_value"] = float(
        spearman_df.loc[config.PHASE5_OVERLAP_RUN_A, config.PHASE5_OVERLAP_RUN_B]
    )
    return fig, meta


def build_figure_5_jaccard_matrix(
    jaccard_df: pd.DataFrame,
) -> Tuple[matplotlib.figure.Figure, Dict]:
    """Figure 5: the saved 10x10 top-1% Jaccard matrix (canonical saved
    flags, never rederived), full [0, 1] range."""
    run_ids = list(jaccard_df.index)
    i_a = run_ids.index(config.PHASE5_OVERLAP_RUN_A)
    i_b = run_ids.index(config.PHASE5_OVERLAP_RUN_B)
    fig, meta = _draw_matrix_figure(
        jaccard_df.to_numpy(dtype=np.float64),
        run_ids,
        cmap="viridis",
        vmin=0.0,
        vmax=1.0,
        title=(
            "Pairwise Jaccard similarity of the saved 1% flags\n"
            "(full [0, 1] range; outlined cells: IF_003 vs LOF_004)"
        ),
        colorbar_label="Jaccard similarity (intersection over union)",
        highlight_cells=[(i_b, i_a), (i_a, i_b)],
        center_zero=False,
    )
    meta["figure_no"] = 5
    meta["pair_value"] = float(
        jaccard_df.loc[config.PHASE5_OVERLAP_RUN_A, config.PHASE5_OVERLAP_RUN_B]
    )
    return fig, meta


def build_figure_6_topk_jaccard(
    curves: pd.DataFrame,
) -> Tuple[matplotlib.figure.Figure, Dict]:
    """Figure 6: mean within-IF / within-LOF / cross-method Jaccard versus
    review budget, plus the IF_003 vs LOF_004 pair."""
    apply_style()
    x = curves["threshold_pct"].to_numpy(dtype=np.float64)
    fig, ax = plt.subplots(figsize=(8.5, 6.0), layout="constrained")
    series = [
        ("within_if_mean_jaccard", "within-IF mean (5 runs, 10 pairs)", "#08519c", "-", "o"),
        ("within_lof_mean_jaccard", "within-LOF mean (5 runs, 10 pairs)", "#e6550d", "-", "s"),
        (
            "cross_method_mean_jaccard",
            "cross-method mean (25 pairs)",
            "#009E73",
            "-",
            "^",
        ),
        ("pair_jaccard", "IF_003 vs LOF_004 (highlighted pair)", "#222222", "--", "D"),
    ]
    for column, label, color, linestyle, marker in series:
        y = curves[column].to_numpy(dtype=np.float64)
        ax.plot(
            x,
            y,
            label=label,
            color=color,
            linestyle=linestyle,
            marker=marker,
            markersize=6,
            linewidth=1.9,
        )
    # Mark the canonical 1% point (saved flags) with an open-face marker.
    canonical_rows = curves[curves["threshold_pct"] == config.PHASE5_CANONICAL_THRESHOLD_PCT]
    if len(canonical_rows) == 1:
        for column, _, color, _, marker in series:
            ax.plot(
                [config.PHASE5_CANONICAL_THRESHOLD_PCT],
                [float(canonical_rows.iloc[0][column])],
                marker=marker,
                markersize=11,
                markerfacecolor="white",
                markeredgecolor=color,
                markeredgewidth=1.8,
                linestyle="none",
                zorder=6,
            )
    ax.set_xscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{v:g}%" for v in x])
    ax.set_xlabel("Review budget (top-k% of the sample, log scale)")
    ax.set_ylabel("Jaccard similarity")
    ax.set_ylim(0.0, 1.05)
    ax.set_title(
        "Top-k Jaccard agreement versus review budget\n"
        "open markers: canonical 1% (saved flags); filled: derived top-k "
        "(Phase 5A tie policy)"
    )
    ax.legend(loc="upper left", fontsize=8.5)
    meta = {
        "figure_no": 6,
        "curves": curves.to_dict(orient="records"),
        "canonical_threshold_pct": config.PHASE5_CANONICAL_THRESHOLD_PCT,
    }
    return fig, meta


def build_figure_7_rank_vs_rank(
    aligned: Dict,
    run_a: Optional[str] = None,
    run_b: Optional[str] = None,
) -> Tuple[matplotlib.figure.Figure, Dict]:
    """Figure 7: rank-versus-rank percentile scatter of the highlighted pair.

    Percentile convention: 1 = most anomalous, 0 = least anomalous, so the
    top-1% boundaries sit at 0.99 on each axis. The Neither group is drawn
    as a hexbin density; Both / IF-only / LOF-only are marker overlays with
    counts and fraud counts labelled. Row alignment is inherited from the
    validated identical ``row_id`` sequence.
    """
    apply_style()
    run_a = run_a or config.PHASE5_OVERLAP_RUN_A
    run_b = run_b or config.PHASE5_OVERLAP_RUN_B
    pct_a = anomaly_percentile(aligned["runs"][run_a]["anomaly_score"])
    pct_b = anomaly_percentile(aligned["runs"][run_b]["anomaly_score"])
    masks = group_masks(
        aligned["runs"][run_a]["flag"], aligned["runs"][run_b]["flag"]
    )
    fraud = aligned["labels"] == 1

    fig, ax = plt.subplots(figsize=(8.6, 7.2), layout="constrained")
    neither_mask = masks["neither"]
    hexbin = ax.hexbin(
        pct_a[neither_mask],
        pct_b[neither_mask],
        gridsize=45,
        cmap="Greys",
        mincnt=1,
        linewidths=0.15,
        zorder=1,
    )
    cbar = fig.colorbar(hexbin, ax=ax, shrink=0.85)
    cbar.set_label("Neither-group observations per hexagon")

    counts = {}
    legend_handles: List[Line2D] = []
    legend_labels: List[str] = []
    overlay_groups = ("both", "if_only", "lof_only")
    for zorder, group in enumerate(overlay_groups, start=3):
        mask = masks[group]
        counts[group] = int(mask.sum())
        group_frauds = int(np.count_nonzero(mask & fraud))
        ax.plot(
            pct_a[mask],
            pct_b[mask],
            marker=GROUP_MARKERS[group],
            linestyle="none",
            markersize=7 if group != "both" else 8,
            markerfacecolor=GROUP_COLORS[group],
            markeredgecolor="white",
            markeredgewidth=0.6,
            alpha=0.9,
            zorder=zorder,
        )
        legend_handles.append(
            Line2D(
                [],
                [],
                marker=GROUP_MARKERS[group],
                linestyle="none",
                markersize=7,
                markerfacecolor=GROUP_COLORS[group],
                markeredgecolor="#333333",
                markeredgewidth=0.6,
            )
        )
        legend_labels.append(
            f"{GROUP_LABELS[group]} — {counts[group]:,} obs ({group_frauds} fraud)"
        )
    counts["neither"] = int(neither_mask.sum())
    legend_handles.insert(
        0,
        Line2D(
            [],
            [],
            marker="h",
            linestyle="none",
            markersize=9,
            color="#777777",
        ),
    )
    legend_labels.insert(
        0,
        f"Neither — {counts['neither']:,} obs "
        f"({int(np.count_nonzero(neither_mask & fraud))} fraud, hexbin density)",
    )
    # The top-1% boundary lines are identified through the legend (never
    # through a free-floating text that could collide with axis labels).
    legend_handles.append(
        Line2D([], [], linestyle="--", color="#999999", linewidth=1.2)
    )
    legend_labels.append("top-1% boundary (percentile 0.99)")

    for value in (0.99,):
        ax.axvline(value, color="#999999", linestyle="--", linewidth=1.1, zorder=2)
        ax.axhline(value, color="#999999", linestyle="--", linewidth=1.1, zorder=2)

    # Corner zoom: the flagged groups live in the thin [0.99, 1] bands and
    # would otherwise be overplotted at the axes edges. The inset replots the
    # SAME three overlay groups on the corner range (no new data, no jitter).
    axins = ax.inset_axes([0.585, 0.075, 0.375, 0.375])
    axins.set_facecolor("white")
    for zorder, group in enumerate(overlay_groups, start=3):
        mask = masks[group]
        axins.plot(
            pct_a[mask],
            pct_b[mask],
            marker=GROUP_MARKERS[group],
            linestyle="none",
            markersize=4.2 if group != "both" else 5.0,
            markerfacecolor=GROUP_COLORS[group],
            markeredgecolor="white",
            markeredgewidth=0.4,
            alpha=0.9,
            zorder=zorder,
        )
    axins.set_xlim(0.985, 1.0)
    axins.set_ylim(0.985, 1.0)
    axins.tick_params(labelsize=7)
    axins.set_title("top-1% corner zoom", fontsize=8, pad=3)
    ax.indicate_inset_zoom(axins, edgecolor="#888888")

    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.set_xlabel(f"{run_a} anomaly percentile (1 = most anomalous)")
    ax.set_ylabel(f"{run_b} anomaly percentile (1 = most anomalous)")
    ax.set_title(
        f"Rank-versus-rank agreement — {run_a} vs {run_b}\n"
        "saved 1% flags define the groups; percentile = 1 - descending rank / n"
    )
    ax.legend(legend_handles, legend_labels, loc="lower left", fontsize=8.5)
    meta = {
        "figure_no": 7,
        "run_a": run_a,
        "run_b": run_b,
        "group_counts": counts,
        "percentile_convention": PERCENTILE_CONVENTION,
    }
    return fig, meta


def build_figure_8_pca_agreement(
    fs_df: pd.DataFrame,
    aligned: Dict,
    run_a: Optional[str] = None,
    run_b: Optional[str] = None,
    neither_max_points: Optional[int] = None,
    neither_sample_seed: int = 42,
) -> Tuple[matplotlib.figure.Figure, Dict]:
    """Figure 8: PCA agreement map of the four flag groups in FS-A space.

    The FS-A matrix is joined on ``row_id`` (one-to-one; stored values used
    as-is -- no additional rescaling) and projected with an exact full-SVD
    PCA fitted on the joined sample. Explained variance of PC1/PC2 is
    reported in the title. The Neither background is either drawn in full
    (default) or subsampled STRICTLY from the Neither group with a fixed
    seed -- never from the full population relabelled as Neither.
    """
    apply_style()
    run_a = run_a or config.PHASE5_OVERLAP_RUN_A
    run_b = run_b or config.PHASE5_OVERLAP_RUN_B
    X, feature_cols = join_fs_sample(fs_df, aligned["row_ids"])
    coords, explained = project_pca(X, n_components=2)
    masks = group_masks(
        aligned["runs"][run_a]["flag"], aligned["runs"][run_b]["flag"]
    )
    fraud = aligned["labels"] == 1

    fig, ax = plt.subplots(figsize=(9.4, 7.0), layout="constrained")
    neither_mask = masks["neither"]
    background_note = NEITHER_BACKGROUND_NOTE
    if neither_max_points is not None and int(neither_max_points) < int(
        neither_mask.sum()
    ):
        rng = np.random.default_rng(int(neither_sample_seed))
        background_idx = np.flatnonzero(neither_mask)
        chosen = rng.choice(
            background_idx, size=int(neither_max_points), replace=False
        )
        background_mask = np.zeros_like(neither_mask)
        background_mask[chosen] = True
        background_note = (
            f"Neither background subsampled to {int(neither_max_points):,} of "
            f"{int(neither_mask.sum()):,} points, drawn strictly from the "
            f"Neither group with seed {int(neither_sample_seed)} "
            "(numpy.random.default_rng, PCG64)"
        )
    else:
        background_mask = neither_mask

    ax.plot(
        coords[background_mask, 0],
        coords[background_mask, 1],
        marker=".",
        linestyle="none",
        markersize=2.6,
        color=GROUP_COLORS["neither"],
        alpha=0.45,
        rasterized=True,
        zorder=1,
    )
    legend_handles = [
        Line2D(
            [],
            [],
            marker=".",
            linestyle="none",
            markersize=7,
            color=GROUP_COLORS["neither"],
            label=(
                f"Neither — {int(neither_mask.sum()):,} obs "
                f"({int(np.count_nonzero(neither_mask & fraud))} fraud)"
            ),
        )
    ]
    for zorder, group in enumerate(("if_only", "lof_only", "both"), start=3):
        mask = masks[group]
        ax.plot(
            coords[mask, 0],
            coords[mask, 1],
            marker=GROUP_MARKERS[group],
            linestyle="none",
            markersize=6.5 if group != "both" else 7.5,
            markerfacecolor=GROUP_COLORS[group],
            markeredgecolor="white",
            markeredgewidth=0.5,
            alpha=0.9,
            rasterized=True,
            zorder=zorder,
        )
        legend_handles.append(
            Line2D(
                [],
                [],
                marker=GROUP_MARKERS[group],
                linestyle="none",
                markersize=7,
                markerfacecolor=GROUP_COLORS[group],
                markeredgecolor="#333333",
                markeredgewidth=0.5,
                label=(
                    f"{GROUP_LABELS[group]} — {int(mask.sum()):,} obs "
                    f"({int(np.count_nonzero(mask & fraud))} fraud)"
                ),
            )
        )

    pc1_var = float(explained[0]) * 100.0
    pc2_var = float(explained[1]) * 100.0
    # Display at two decimals and sum the ROUNDED values so the title and the
    # axis labels are exactly consistent (no 3.6 + 3.6 = 7.1 artefact).
    pc1_label = round(pc1_var, 2)
    pc2_label = round(pc2_var, 2)
    ax.set_xlabel(f"PC1 ({pc1_label:.2f}% variance explained)")
    ax.set_ylabel(f"PC2 ({pc2_label:.2f}% variance explained)")
    ax.set_title(
        f"PCA agreement map — {run_a} vs {run_b} saved 1% flag groups\n"
        f"FS-A features ({len(feature_cols)} dimensions, stored scaling)\n"
        f"PC1+PC2 = {pc1_label + pc2_label:.2f}% of variance — lossy projection"
    )
    ax.legend(handles=legend_handles, loc="upper right", fontsize=8.5)
    meta = {
        "figure_no": 8,
        "run_a": run_a,
        "run_b": run_b,
        "explained_variance_pct": {"pc1": pc1_var, "pc2": pc2_var},
        "feature_columns": feature_cols,
        "pca_solver": "full",
        "fitted_on": "the joined sample (row_id-aligned FS-A rows)",
        "neither_background": background_note,
        "pca_disclaimer": PCA_DISCLAIMER,
        "fs_scaling": FS_A_SCALING_NOTE,
    }
    return fig, meta


def save_figure(
    fig: matplotlib.figure.Figure,
    path: Path,
    dpi: Optional[int] = None,
    close: bool = True,
) -> Path:
    """Save one figure as PNG (white background, fixed DPI) and close it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi or config.PHASE5_PLOT_DPI_DEFAULT, facecolor="white")
    if close:
        plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Output paths, catalog and plot metadata
# ---------------------------------------------------------------------------

def _output_paths(output_dir: Path) -> Dict[str, Path]:
    """The eleven files Phase 5B may write, keyed by artifact name."""
    paths = {
        f"figure_{i}": Path(output_dir) / spec["filename"]
        for i, spec in FIGURE_SPECS.items()
    }
    paths["figure_catalog"] = Path(output_dir) / config.PHASE5_FIGURE_CATALOG_FILENAME
    paths["plot_metadata"] = Path(output_dir) / config.PHASE5_PLOT_METADATA_FILENAME
    paths["manifest"] = Path(output_dir) / config.PHASE5_PLOT_MANIFEST_FILENAME
    return paths


def _build_catalog_dataframe(staged_paths: Dict[int, Path]) -> pd.DataFrame:
    """The figure catalog CSV: one row per authoritative figure."""
    rows = []
    for figure_no, spec in FIGURE_SPECS.items():
        staged = staged_paths[figure_no]
        rows.append(
            {
                "figure_no": figure_no,
                "filename": spec["filename"],
                "title": spec["title"],
                "purpose": spec["purpose"],
                "input_artifacts": spec["inputs"],
                "conventions": spec["conventions"],
                "size_bytes": int(staged.stat().st_size),
            }
        )
    return pd.DataFrame(rows)


def _build_plot_metadata(
    validated: Dict,
    output_paths: Dict[str, Path],
    figure_metas: Dict[int, Dict],
    staged_paths: Dict[int, Path],
    topk_details: Dict,
    run_mode: str,
    dpi: int,
) -> Dict:
    """Assemble the phase5_plot_metadata.json payload (JSON-safe types)."""
    sample = validated["sample"]
    inventory = {}
    for figure_no, spec in FIGURE_SPECS.items():
        staged = staged_paths[figure_no]
        entry = {
            "filename": spec["filename"],
            "title": spec["title"],
            "size_bytes": int(staged.stat().st_size),
            "output_path": str(output_paths[f"figure_{figure_no}"]),
        }
        entry.update(
            {k: v for k, v in figure_metas[figure_no].items() if k != "curves"}
        )
        inventory[str(figure_no)] = entry
    return {
        "phase": "5B",
        "stream": "A",
        "layer": "visualization",
        "run_mode": run_mode,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": validated["inputs_info"],
        "input_manifests": {
            "phase5_commit_manifest": validated["phase5_manifest"],
            "phase4_commit_manifest": validated["phase4_manifest"],
        },
        "sample": sample,
        "run_ids": list(validated["aligned"]["run_ids"]),
        "plotting_conventions": {
            "score_orientation": (
                "anomaly_score from the Phase 4 evaluation dataset "
                "(higher = more anomalous); native_score never used for ranking"
            ),
            "fixed_threshold_policy": (
                "saved Phase 3 flags consumed exactly as supplied; the 1% rule "
                "is never recomputed, re-optimised or re-thresholded"
            ),
            "percentile_convention": PERCENTILE_CONVENTION,
            "rank_vs_rank_boundaries": "top-1% boundaries drawn at percentile 0.99",
            "random_baselines": RANDOM_BASELINES_NOTE,
            "hypergeometric_reporting": (
                "upper-tail probabilities reported via log10 (sf/logsf); an "
                "underflowed probability is never presented as exactly zero; "
                "the full valid support is displayed and labelled"
            ),
            "tie_breaking": phase5_analysis.TIE_BREAK_POLICY,
            "topk_derivation": topk_details,
            "colours": {
                "if_family": "shades of blue (#08519c / #08306b for the highlighted IF runs)",
                "lof_family": "shades of orange (#a63603 for the highlighted LOF run)",
                "agreement_groups": "Okabe-Ito colourblind-safe palette with "
                                    "distinct markers per group",
                "matrices": "numeric annotation in every cell; colour is never "
                            "the only channel",
            },
            "pca": {
                "preprocessing": FS_A_SCALING_NOTE,
                "solver": "exact full SVD (deterministic; no randomized solver)",
                "fitted_on": "the joined 30,000-observation sample (row_id-aligned FS-A rows)",
                "explained_variance_pct": figure_metas[8]["explained_variance_pct"],
                "disclaimer": PCA_DISCLAIMER,
                "neither_background": figure_metas[8]["neither_background"],
            },
            "dpi": int(dpi),
            "exploratory_selection_caveat": phase5_analysis.EXPLORATORY_SELECTION_CAVEAT,
        },
        "figure_inventory": inventory,
        "figures_rendered": len(FIGURE_SPECS),
        "outputs": {k: str(v) for k, v in output_paths.items()},
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
            "scikit-learn": sklearn.__version__,
            "matplotlib": matplotlib.__version__,
            "executable": sys.executable,
        },
        "model_fitting": {
            "models_fitted": 0,
            "note": (
                "Phase 5B is a visualization-only layer: no anomaly detector "
                "was constructed, fitted or refitted; the only scikit-learn "
                "estimator used is a 2-component PCA (a lossy projection for "
                "visualization); Phase 4 scores and saved flags were consumed "
                "exactly as stored; no Phase 5A quantity was recalculated."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Staged publication with backup / rollback (the manifest is published LAST)
# ---------------------------------------------------------------------------

def _verify_staged_artifacts(
    staging_dir: Path, artifact_names: Sequence[str]
) -> None:
    """Every staged file must exist, be non-empty and (for PNGs) carry the
    PNG magic bytes -- a partially written figure is never published."""
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
        if name.endswith(".png"):
            with open(staged, "rb") as f:
                if f.read(8) != PNG_MAGIC:
                    problems.append(f"'{name}' does not carry the PNG magic bytes")
    if problems:
        raise Phase5PlotError(
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
            raise Phase5PlotError(
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
                print(
                    f"  backed up {len(existing)} existing output(s) to {backup_dir}"
                )

        for name in artifact_names:
            (staging_dir / name).rename(output_dir / name)
            published.append(name)
        if verbose:
            print(f"  published {len(published)} artifact(s) to {output_dir}")

        # The manifest is built inside the staging logic but published LAST.
        manifest = build_manifest(
            {name: output_dir / name for name in artifact_names}
        )
        save_manifest(manifest, output_dir / manifest_name, overwrite=True)
        published.append(manifest_name)
        if verbose:
            print(f"  published the commit manifest last: {output_dir / manifest_name}")
    except BaseException:
        for name in published:
            target = output_dir / name
            if target.exists():
                target.unlink()
        for name, backup in backed_up.items():
            if not (output_dir / name).exists():
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

def collect_phase5_plots_preflight(
    phase5_dir: Optional[Path] = None,
    phase4_dataset_path: Optional[Path] = None,
    fs_a_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    expected_run_ids: Optional[Sequence[str]] = None,
    expected_sample_size: int = config.SAMPLE_SIZE_DEFAULT,
    verbose: bool = True,
) -> Dict:
    """Validate everything Phase 5B needs WITHOUT rendering or writing.

    Verifies the optional Phase 5A and Phase 4 output manifests, loads and
    validates every consumed artifact (schemas, run completeness, cross-run
    row_id consistency, Phase 5A table cross-checks, FS-A join coverage,
    cross-snapshot hash consistency) and reports the planned figures and
    the output status. No figure is rendered and no file is written (the
    output directory is not even created).
    """
    phase5_dir, phase4_dataset_path, fs_a_path = _resolve_input_paths(
        phase5_dir, phase4_dataset_path, fs_a_path
    )
    output_dir = Path(output_dir) if output_dir is not None else config.DEFAULT_PHASE5_FIGURES_DIR
    paths = _output_paths(output_dir)

    validated = _load_and_validate_inputs(
        phase5_dir, phase4_dataset_path, fs_a_path,
        expected_run_ids, expected_sample_size, verbose=verbose,
    )
    sample = validated["sample"]

    return {
        "phase5_dir": phase5_dir,
        "phase4_dataset_path": phase4_dataset_path,
        "fs_a_path": fs_a_path,
        "input_manifests": {
            "phase5": validated["phase5_manifest"],
            "phase4": validated["phase4_manifest"],
        },
        "sample": sample,
        "run_ids": list(validated["aligned"]["run_ids"]),
        "figures_planned": [
            {"figure_no": i, "filename": s["filename"], "title": s["title"]}
            for i, s in FIGURE_SPECS.items()
        ],
        "outputs": {
            "directory": output_dir,
            "paths": paths,
            "exists": {k: Path(v).exists() for k, v in paths.items()},
            "overwrite": False,
            "blocked": bool(any(Path(v).exists() for v in paths.values())),
        },
        "writes_performed": False,
        "figures_rendered": 0,
        "models_fitted": 0,
    }


def run_phase5_plots(
    phase5_dir: Optional[Path] = None,
    phase4_dataset_path: Optional[Path] = None,
    fs_a_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    expected_run_ids: Optional[Sequence[str]] = None,
    expected_sample_size: int = config.SAMPLE_SIZE_DEFAULT,
    dpi: int = config.PHASE5_PLOT_DPI_DEFAULT,
    overwrite: bool = False,
    verbose: bool = True,
) -> Dict:
    """Execute the Phase 5B visualization layer end to end.

    Steps: fail-fast output precheck -> verify the optional Phase 5A and
    Phase 4 manifests -> load and validate every input (including the
    cross-snapshot hash check and the Phase 5A table cross-checks) -> render
    the eight figures into a staging directory -> verify every staged file
    -> publish with backup/rollback, the commit manifest LAST -> write the
    figure catalog and the plot metadata.

    No detector is ever fitted, no threshold is ever reselected, no Phase 4
    metric and no Phase 5A bootstrap result is ever recalculated, and
    existing outputs are never replaced unless ``overwrite=True``.
    """
    phase5_dir, phase4_dataset_path, fs_a_path = _resolve_input_paths(
        phase5_dir, phase4_dataset_path, fs_a_path
    )
    output_dir = Path(output_dir) if output_dir is not None else config.DEFAULT_PHASE5_FIGURES_DIR
    paths = _output_paths(output_dir)

    # Fail fast: refuse to render if outputs exist and cannot be replaced.
    assert_outputs_writable(list(paths.values()), overwrite=overwrite)

    validated = _load_and_validate_inputs(
        phase5_dir, phase4_dataset_path, fs_a_path,
        expected_run_ids, expected_sample_size, verbose=verbose,
    )
    aligned = validated["aligned"]
    tables = validated["tables"]
    sample = validated["sample"]
    prevalence = sample["fraud_prevalence"]

    # --- derived plotting quantities -------------------------------------
    if verbose:
        print("Deriving top-k Jaccard curves from the row-level artifact ...")
    topk_curves, topk_details = compute_topk_jaccard_curves(aligned)

    # --- render every figure into the staging directory -------------------
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent)
    )
    if verbose:
        print(f"Rendering the eight figures into {staging_dir} ...")
    try:
        figure_metas: Dict[int, Dict] = {}
        staged_paths: Dict[int, Path] = {}

        fig, meta = build_figure_1_precision_recall(aligned)
        staged_paths[1] = save_figure(fig, staging_dir / FIGURE_SPECS[1]["filename"], dpi=dpi)
        figure_metas[1] = meta

        fig, meta = build_figure_2_fraud_discovery(
            tables["discovery"], sample["sample_size"], prevalence
        )
        staged_paths[2] = save_figure(fig, staging_dir / FIGURE_SPECS[2]["filename"], dpi=dpi)
        figure_metas[2] = meta

        fig, meta = build_figure_3_hypergeometric_overlap(tables["hypergeometric"])
        staged_paths[3] = save_figure(fig, staging_dir / FIGURE_SPECS[3]["filename"], dpi=dpi)
        figure_metas[3] = meta

        fig, meta = build_figure_4_spearman_matrix(tables["spearman"])
        staged_paths[4] = save_figure(fig, staging_dir / FIGURE_SPECS[4]["filename"], dpi=dpi)
        figure_metas[4] = meta

        fig, meta = build_figure_5_jaccard_matrix(tables["jaccard"])
        staged_paths[5] = save_figure(fig, staging_dir / FIGURE_SPECS[5]["filename"], dpi=dpi)
        figure_metas[5] = meta

        fig, meta = build_figure_6_topk_jaccard(topk_curves)
        staged_paths[6] = save_figure(fig, staging_dir / FIGURE_SPECS[6]["filename"], dpi=dpi)
        figure_metas[6] = meta

        fig, meta = build_figure_7_rank_vs_rank(aligned)
        staged_paths[7] = save_figure(fig, staging_dir / FIGURE_SPECS[7]["filename"], dpi=dpi)
        figure_metas[7] = meta

        fig, meta = build_figure_8_pca_agreement(validated["fs_df"], aligned)
        staged_paths[8] = save_figure(fig, staging_dir / FIGURE_SPECS[8]["filename"], dpi=dpi)
        figure_metas[8] = meta

        # --- catalog + plot metadata into staging --------------------------
        catalog_df = _build_catalog_dataframe(staged_paths)
        catalog_path = staging_dir / config.PHASE5_FIGURE_CATALOG_FILENAME
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_df.to_csv(catalog_path, index=False)

        plot_metadata = _build_plot_metadata(
            validated, paths, figure_metas, staged_paths, topk_details,
            run_mode="execute", dpi=dpi,
        )
        metadata_path = staging_dir / config.PHASE5_PLOT_METADATA_FILENAME
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(plot_metadata, f, indent=2, sort_keys=True)
            f.write("\n")

        # --- staged publication (manifest LAST) ----------------------------
        artifact_names = [
            *[FIGURE_SPECS[i]["filename"] for i in sorted(FIGURE_SPECS)],
            config.PHASE5_FIGURE_CATALOG_FILENAME,
            config.PHASE5_PLOT_METADATA_FILENAME,
        ]
        if verbose:
            print("Publishing staged artifacts (backup/rollback armed) ...")
        publication = _publish_with_rollback(
            staging_dir,
            output_dir,
            artifact_names,
            config.PHASE5_PLOT_MANIFEST_FILENAME,
            overwrite=overwrite,
            verbose=verbose,
        )
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)

    if verbose:
        _print_execution_summary(validated, figure_metas, output_dir)

    return {
        "figures": {i: str(paths[f"figure_{i}"]) for i in FIGURE_SPECS},
        "figure_metas": figure_metas,
        "topk_curves": topk_curves,
        "catalog": str(paths["figure_catalog"]),
        "plot_metadata": str(paths["plot_metadata"]),
        "manifest": str(paths["manifest"]),
        "publication": publication,
        "sample": sample,
        "paths": {k: Path(v) for k, v in paths.items()},
    }


def _print_execution_summary(validated: Dict, figure_metas: Dict, output_dir: Path) -> None:
    """Print the headline values for independent comparison."""
    sample = validated["sample"]
    hyper = validated["tables"]["hypergeometric"]
    print("\n=== PHASE 5B FIGURE LAYER (published) ===")
    print(
        f"sample: {sample['sample_size']:,} observations, "
        f"{sample['fraud_count']} fraud labels "
        f"(prevalence {sample['fraud_prevalence']:.6f})"
    )
    print(
        f"hypergeometric reference: observed {hyper['observed_intersection']}, "
        f"expected {hyper['expected_intersection']:.2f}, enrichment "
        f"{hyper['enrichment_observed_over_expected']:.2f}x, log10 upper tail "
        f"{hyper['log10_survival']:.2f}"
    )
    m8 = figure_metas[8]
    print(
        "PCA explained variance: PC1 "
        f"{m8['explained_variance_pct']['pc1']:.1f}%, PC2 "
        f"{m8['explained_variance_pct']['pc2']:.1f}% (lossy projection)"
    )
    print(f"figures + catalog + metadata + manifest published to {output_dir}")
    print(f"NOTE: {phase5_analysis.EXPLORATORY_SELECTION_CAVEAT}")
