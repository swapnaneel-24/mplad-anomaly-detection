"""Central configuration: repository paths and the frozen Phase 3 experiment.

Every constant in this module is either

* a path default that can be overridden on the command line
  (``scripts/run_phase3.py``), or
* a **frozen experimental parameter** extracted verbatim from the recovered
  Colab notebook ``phase3_trackA`` (14-cell historical artifact), cell index
  4 -- "PHASE 3: Methodological Execution", the revised primary 30k
  experiment.

Do not edit the frozen parameters without recording the change in
``docs/provenance_log.md`` -- they define the established experiment.
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Repository layout
# ---------------------------------------------------------------------------

#: Repository root, derived from this file's location
#: (<repo>/src/mplad/common/config.py -> parents[3] == <repo>).
REPO_ROOT: Path = Path(__file__).resolve().parents[3]

#: Frozen Phase 2 feature space, FS-A (RobustScaler baseline).
#: NOTE: the historical layout mixes 'stream-a' (hyphen, under data/) with
#: 'stream a' (literal space, under results/). Both are preserved verbatim
#: for compatibility with existing artifacts -- do not "normalise" them.
DEFAULT_FS_A_PATH: Path = (
    REPO_ROOT / "data" / "processed" / "stream-a" / "features" / "ULB_FS_A_Baseline.csv"
)

#: Default Phase 3 output directory (the literal spaces are intentional).
DEFAULT_OUTPUT_DIR: Path = REPO_ROOT / "results" / "stream a" / "phase 3"

#: Canonical Phase 3 artifact filenames (existing output contract).
METADATA_FILENAME: str = "phase3_run_metadata.csv"
PREDICTIONS_FILENAME: str = "phase3_canonical_predictions.pkl"
MANIFEST_FILENAME: str = "phase3_commit_manifest.json"

#: Historical Colab storage root. Context only -- never used as a path by
#: this package; the local runner has no Google Drive dependency.
HISTORICAL_COLAB_STORAGE_DIR: str = "/content/drive/MyDrive/mplad-dvc-storage"

# ---------------------------------------------------------------------------
# Feature-space schema (Phase 2 manifest: FS-A)
# ---------------------------------------------------------------------------

#: Stable row identifier: retained for every observation, never a model input.
ID_COLUMN: str = "row_id"

#: Columns that must never appear in a feature matrix (label-leakage guard).
FORBIDDEN_COLUMNS: tuple = ("Class",)

#: Frozen FS-A features: Time, V1..V28 (PCA outputs, untouched), Amount.
EXPECTED_FEATURE_COLUMNS: tuple = ("Time",) + tuple(f"V{i}" for i in range(1, 29)) + ("Amount",)

# ---------------------------------------------------------------------------
# Sampling (recovered notebook, cell index 4 -- verbatim)
# ---------------------------------------------------------------------------

SAMPLE_SIZE_DEFAULT: int = 30_000
SAMPLE_SEED_DEFAULT: int = 42  # the `np.random.seed(42)` of cell index 4

# ---------------------------------------------------------------------------
# Post-hoc flagging rule (verbatim)
# ---------------------------------------------------------------------------

THRESHOLD_PERCENTILE: float = 1.0
THRESHOLD_RULE_LABEL: str = f"Bottom {THRESHOLD_PERCENTILE}% of scores"

# ---------------------------------------------------------------------------
# Detector grids (verbatim from cell index 4) -- FROZEN, do not edit
# ---------------------------------------------------------------------------

ISOLATION_FOREST_CONFIGS: list = [
    {"n_estimators": 100, "max_samples": 256, "random_state": 42},
    {"n_estimators": 200, "max_samples": 256, "random_state": 42},  # parameter sensitivity
    {"n_estimators": 100, "max_samples": 0.05, "random_state": 42},  # parameter sensitivity (5% sub-sample)
    {"n_estimators": 100, "max_samples": 256, "random_state": 43},  # seed stability
    {"n_estimators": 100, "max_samples": 256, "random_state": 44},  # seed stability
]

#: Fixed Isolation Forest settings (cell index 4, 30k run).
IF_FIXED_PARAMS: dict = {"n_jobs": 1}

LOF_CONFIGS: list = [
    {"n_neighbors": 5, "metric": "euclidean"},
    {"n_neighbors": 15, "metric": "euclidean"},
    {"n_neighbors": 30, "metric": "euclidean"},
    {"n_neighbors": 50, "metric": "euclidean"},
    {"n_neighbors": 30, "metric": "manhattan"},
]

#: Fixed LOF settings (cell index 4, 30k run).
LOF_FIXED_PARAMS: dict = {"algorithm": "ball_tree", "leaf_size": 40, "n_jobs": 1}

# ---------------------------------------------------------------------------
# Run-metadata CSV schema (identical to the existing phase3_run_metadata.csv)
# ---------------------------------------------------------------------------

METADATA_COLUMNS: list = [
    "run_id",
    "model",
    "n_estimators",
    "max_samples",
    "random_state",
    "runtime_seconds",
    "threshold_rule",
    "flagged_count",
    "n_neighbors",
    "metric",
]

#: Display names recorded in the metadata 'model' column.
MODEL_NAME_IF: str = "IsolationForest"
MODEL_NAME_LOF: str = "LOF"

# ---------------------------------------------------------------------------
# Phase 4 (label-based evaluation layer) -- paths and constants
#
# Added for the Phase 4 migration. Everything above this section is frozen
# Phase 3 material and is NOT modified: Phase 4 consumes the Phase 3 outputs
# read-only and never refits a detector.
# ---------------------------------------------------------------------------

#: Ground-truth registry (full ULB population: 284,807 unique row_ids,
#: 492 positive labels on the real file). Stored separately from the feature
#: spaces so the unsupervised phases can never see it by accident.
DEFAULT_GROUND_TRUTH_PATH: Path = (
    REPO_ROOT / "data" / "processed" / "stream-a" / "labels" / "ground_truth_registry.csv"
)

#: Label column of the ground-truth registry. Same name as the feature-matrix
#: forbidden column -- there it is the leakage guard, here it is the target.
LABEL_COLUMN: str = "Class"

#: The only valid label values (strict binary ground truth).
VALID_LABEL_VALUES: tuple = (0, 1)

#: Canonical Phase 3 inputs consumed by Phase 4 (the frozen source of truth).
#: These default to the canonical artifacts in ``results/stream a/phase 3/``
#: and are NEVER written to by Phase 4.
PHASE3_PREDICTIONS_PATH: Path = DEFAULT_OUTPUT_DIR / PREDICTIONS_FILENAME
PHASE3_RUN_METADATA_PATH: Path = DEFAULT_OUTPUT_DIR / METADATA_FILENAME

#: Where Phase 4 looks for an optional Phase 3 integrity manifest (same
#: directory as the Phase 3 artifacts). The hardened Stage 1 Phase 3 does not
#: generate manifests, so on the current repository this file is expected to
#: be absent and the inputs are handled as a legacy unmanifested pair.
PHASE3_MANIFEST_FILENAME: str = "phase3_commit_manifest.json"

#: Run IDs of the established Phase 3 experiment, derived from the frozen
#: grids (5 Isolation Forest + 5 LOF configurations).
PHASE3_CANONICAL_RUN_IDS: tuple = tuple(
    [f"IF_{i:03d}" for i in range(1, len(ISOLATION_FOREST_CONFIGS) + 1)]
    + [f"LOF_{i:03d}" for i in range(1, len(LOF_CONFIGS) + 1)]
)

#: Default Phase 4 output directory. Deliberately a ``reproduction``
#: sub-directory so that any historical Phase 4 outputs directly under
#: ``results/stream a/phase 4/`` are never touched by default (the literal
#: spaces in the path are intentional, as everywhere else).
DEFAULT_PHASE4_OUTPUT_DIR: Path = (
    REPO_ROOT / "results" / "stream a" / "phase 4" / "reproduction"
)

#: Canonical Phase 4 artifact filenames.
PHASE4_EVALUATION_DATASET_FILENAME: str = "phase4_evaluation_dataset.csv"
PHASE4_METRICS_FILENAME: str = "phase4_metrics.csv"
PHASE4_RUN_METADATA_FILENAME: str = "phase4_run_metadata.json"
PHASE4_MANIFEST_FILENAME: str = "phase4_commit_manifest.json"

# ---------------------------------------------------------------------------
# Phase 5A (quantitative diagnostic analysis) -- paths and constants
#
# Added for the Phase 5A migration. Everything above is frozen Phase 3 /
# Phase 4 material and is NOT modified: Phase 5A consumes the Phase 4
# reproduction outputs read-only, never refits a detector and never
# recomputes the saved 1% flags.
# ---------------------------------------------------------------------------

#: Canonical Phase 4 outputs consumed by Phase 5A (read-only, never written
#: to by this phase).
PHASE4_EVALUATION_DATASET_PATH: Path = (
    DEFAULT_PHASE4_OUTPUT_DIR / PHASE4_EVALUATION_DATASET_FILENAME
)
PHASE4_RUN_METADATA_JSON_PATH: Path = (
    DEFAULT_PHASE4_OUTPUT_DIR / PHASE4_RUN_METADATA_FILENAME
)

#: Where Phase 5A looks for the optional Phase 4 integrity manifest (same
#: directory as the Phase 4 outputs). The hardened Phase 4 publishes one, so
#: on a healthy repository this file EXISTS and its hashes are verified
#: before anything is consumed; if it is missing the inputs are handled as a
#: legacy unmanifested pair (strict structural validation + SHA-256
#: recording, verification never claimed falsely).
PHASE5_INPUT_MANIFEST_FILENAME: str = PHASE4_MANIFEST_FILENAME

#: Default Phase 5 output directory. Like Phase 4, deliberately a
#: ``reproduction`` sub-directory so historical Phase 5 outputs directly
#: under ``results/stream a/phase 5/`` are never touched by default (the
#: literal spaces in the path are intentional, as everywhere else).
DEFAULT_PHASE5_OUTPUT_DIR: Path = (
    REPO_ROOT / "results" / "stream a" / "phase 5" / "reproduction"
)

#: Canonical Phase 5A artifact filenames.
PHASE5_BOOTSTRAP_METRICS_FILENAME: str = "phase5_bootstrap_metrics.csv"
PHASE5_PAIRED_BOOTSTRAP_DIFFERENCES_FILENAME: str = "phase5_paired_bootstrap_differences.csv"
PHASE5_PAIRWISE_SPEARMAN_FILENAME: str = "phase5_pairwise_spearman.csv"
PHASE5_PAIRWISE_JACCARD_FILENAME: str = "phase5_pairwise_jaccard_1pct.csv"
PHASE5_MULTITHRESHOLD_AGREEMENT_FILENAME: str = "phase5_multithreshold_agreement.csv"
PHASE5_HYPERGEOMETRIC_OVERLAP_FILENAME: str = "phase5_hypergeometric_overlap.csv"
PHASE5_AGREEMENT_GROUPS_FILENAME: str = "phase5_agreement_groups.csv"
PHASE5_FRAUD_DISCOVERY_CURVE_FILENAME: str = "phase5_fraud_discovery_curve.csv"
PHASE5_RUN_METADATA_FILENAME: str = "phase5_run_metadata.json"
PHASE5_MANIFEST_FILENAME: str = "phase5_commit_manifest.json"

#: Frozen bootstrap protocol (historical Phase 5 methodology): 2,000
#: class-stratified bootstrap replicates, metrics for the three highlighted
#: runs, and the paired LOF_004-minus-IF_003 comparison on shared replicate
#: indices. The highlighted runs were chosen AFTER inspecting the Phase 4
#: label-informed results -- every comparison on them is exploratory and is
#: labelled as such in the outputs.
PHASE5_BOOTSTRAP_REPLICATES_DEFAULT: int = 2_000
#: Bootstrap seed. A NEW generator (numpy.random.default_rng, PCG64), fully
#: independent of the Phase 3 legacy RandomState(42) sampling stream.
PHASE5_BOOTSTRAP_SEED_DEFAULT: int = 42
PHASE5_BOOTSTRAP_RUN_IDS: tuple = ("IF_003", "IF_004", "LOF_004")
#: Paired comparison definition: difference is run_b minus run_a.
PHASE5_PAIRED_COMPARISON_RUNS: tuple = ("IF_003", "LOF_004")
PHASE5_CI_LEVEL: float = 0.95

#: Multi-threshold agreement grid (percent of the sample; k = round(n*pct/100)).
PHASE5_MULTI_THRESHOLD_PERCENTS: tuple = (0.1, 0.2, 0.5, 1.0, 2.0, 5.0)
#: The canonical saved-flag threshold: at this percentage the SAVED Phase 3
#: flags are used; every other percentage derives top-k selections from the
#: continuous anomaly scores under the documented tie-breaking policy.
PHASE5_CANONICAL_THRESHOLD_PCT: float = 1.0

#: The highlighted pair for the hypergeometric overlap and agreement-group
#: analyses (canonical saved 1% flags).
PHASE5_OVERLAP_RUN_A: str = "IF_003"
PHASE5_OVERLAP_RUN_B: str = "LOF_004"

# ---------------------------------------------------------------------------
# Phase 5B (visualization layer) -- paths and constants
#
# Added for the Phase 5B migration. Everything above is frozen Phase 3 /
# Phase 4 / Phase 5A material and is NOT modified: Phase 5B consumes the
# Phase 5A reproduction tables, the Phase 4 row-level evaluation dataset and
# the FS-A feature matrix strictly read-only, never refits a detector, never
# recomputes a saved flag and never recalculates a bootstrap result.
# ---------------------------------------------------------------------------

#: Default Phase 5B output directory (figures). Deliberately a
#: ``figures/reproduction`` sub-directory so that any historical Phase 5
#: figures elsewhere under ``results/stream a/phase 5/`` are never touched
#: (the literal spaces in the path are intentional, as everywhere else).
DEFAULT_PHASE5_FIGURES_DIR: Path = (
    REPO_ROOT / "results" / "stream a" / "phase 5" / "figures" / "reproduction"
)

#: The eight authoritative figure filenames, in canonical order. No alternate
#: numbered iterations and no ninth figure exist in this layer.
PHASE5_FIGURE_FILENAMES: tuple = (
    "phase5_plot1_precision_recall.png",
    "phase5_plot2_fraud_discovery.png",
    "phase5_plot3_hypergeometric_overlap.png",
    "phase5_plot4_spearman_matrix.png",
    "phase5_plot5_jaccard_matrix.png",
    "phase5_plot6_topk_jaccard.png",
    "phase5_plot7_rank_vs_rank.png",
    "phase5_plot8_pca_agreement.png",
)

#: Companion publication artifacts of the figure layer.
PHASE5_FIGURE_CATALOG_FILENAME: str = "phase5_figure_catalog.csv"
PHASE5_PLOT_METADATA_FILENAME: str = "phase5_plot_metadata.json"
PHASE5_PLOT_MANIFEST_FILENAME: str = "phase5_plot_commit_manifest.json"

#: Where Phase 5B looks for the optional Phase 5A integrity manifest (same
#: directory as the Phase 5A tables). The hardened Phase 5A publishes one, so
#: on a healthy repository this file EXISTS and its hashes are verified
#: before anything is consumed; if it is missing the inputs are handled as a
#: legacy unmanifested set (strict structural validation + SHA-256 recording,
#: verification never claimed falsely).
PHASE5_PLOTS_INPUT_MANIFEST_FILENAME: str = PHASE5_MANIFEST_FILENAME

#: Where Phase 5B looks for the optional Phase 4 integrity manifest (same
#: directory as the Phase 4 evaluation dataset).
PHASE5_PLOTS_PHASE4_MANIFEST_FILENAME: str = PHASE4_MANIFEST_FILENAME

#: Publication rendering defaults (recorded in the plot metadata).
PHASE5_PLOT_DPI_DEFAULT: int = 200

# ---------------------------------------------------------------------------
# Phase 6 (cross-method consistency layer) -- paths and constants
#
# Added for the Phase 6 migration. Everything above is frozen Phase 3 /
# Phase 4 / Phase 5A / Phase 5B material and is NOT modified: Phase 6 is an
# evidence-synthesis stage that consumes the verified Phase 4 evaluation
# dataset and the verified Phase 5A quantitative tables strictly read-only.
# It never fits a detector, never recomputes a bootstrap estimate, a
# hypergeometric probability or a correlation matrix, never introduces a new
# threshold and never produces a plot.
# ---------------------------------------------------------------------------

#: Default Phase 6 output directory. Deliberately a ``reproduction``
#: sub-directory so that any historical Phase 6 outputs directly under
#: ``results/stream a/phase 6/`` are never touched by default (the literal
#: spaces in the path are intentional, as everywhere else).
DEFAULT_PHASE6_OUTPUT_DIR: Path = (
    REPO_ROOT / "results" / "stream a" / "phase 6" / "reproduction"
)

#: Canonical Phase 6 artifact filenames.
PHASE6_GROUP_ASSIGNMENTS_FILENAME: str = "phase6_group_assignments.csv"
PHASE6_CONSISTENCY_SCORECARD_FILENAME: str = "phase6_consistency_scorecard.csv"
PHASE6_CONSISTENCY_REPORT_FILENAME: str = "phase6_consistency_report.md"
PHASE6_RUN_METADATA_FILENAME: str = "phase6_run_metadata.json"
PHASE6_MANIFEST_FILENAME: str = "phase6_commit_manifest.json"

#: Where Phase 6 looks for the optional Phase 5A integrity manifest (same
#: directory as the Phase 5A tables). The hardened Phase 5A publishes one, so
#: on a healthy repository this file EXISTS and its hashes are verified
#: before anything is consumed; if it is missing the inputs are handled as a
#: legacy unmanifested set (strict structural validation + SHA-256 recording,
#: verification never claimed falsely).
PHASE6_INPUT_MANIFEST_FILENAME: str = PHASE5_MANIFEST_FILENAME

#: Where Phase 6 looks for the optional Phase 4 integrity manifest (same
#: directory as the Phase 4 evaluation dataset).
PHASE6_PHASE4_MANIFEST_FILENAME: str = PHASE4_MANIFEST_FILENAME
