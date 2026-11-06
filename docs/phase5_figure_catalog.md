# Phase 5B Figure Catalog — Stream A: Visualization Layer

**Status:** implemented 2026-11-05 (Stage 4 of the Colab → repository migration).
**Scope:** the Phase 5 *plotting layer* only. No Phase 6, no Streamlit, no
notebook, no additional exploratory visualizations.

Phase 5B consumes — strictly read-only — the verified Phase 5A reproduction
tables (`results/stream a/phase 5/reproduction/`), the Phase 4 row-level
evaluation dataset (`phase4_evaluation_dataset.csv`) and the FS-A feature
matrix (`data/processed/stream-a/features/ULB_FS_A_Baseline.csv`), and
renders **exactly eight authoritative figures** under
`results/stream a/phase 5/figures/reproduction/`. No detector is ever
fitted or refitted; no saved canonical flag is ever recomputed; no Phase 4
metric table and no Phase 5A bootstrap result is ever recalculated. The only
scikit-learn estimators used are `sklearn.metrics` (precision–recall
geometry) and a 2-component `sklearn.decomposition.PCA` — a lossy projection
for visualization only.

The historical Phase 5 figures are never touched: outputs go to a new
`figures/reproduction/` namespace, existing files block execution unless
`--overwrite` is passed, rendering happens in a staging directory, and
publication is atomic with backup/rollback (the commit manifest is always
published last).

---

## 1. Inputs (exact contract)

| Input | Default path | Role |
|---|---|---|
| Phase 5A Spearman matrix | `results/stream a/phase 5/reproduction/phase5_pairwise_spearman.csv` | figure 4 |
| Phase 5A top-1% Jaccard matrix | `.../phase5_pairwise_jaccard_1pct.csv` | figure 5 |
| Phase 5A hypergeometric summary | `.../phase5_hypergeometric_overlap.csv` | figure 3 |
| Phase 5A fraud-discovery curves | `.../phase5_fraud_discovery_curve.csv` | figure 2 |
| Phase 5A agreement groups | `.../phase5_agreement_groups.csv` | cross-checks + figure 7/8 labels |
| Phase 5A provenance record | `.../phase5_run_metadata.json` | conventions, sample summary, input hash |
| Phase 4 evaluation dataset | `results/stream a/phase 4/reproduction/phase4_evaluation_dataset.csv` | figures 1, 6, 7, 8 (scores, saved flags, labels) |
| FS-A feature matrix | `data/processed/stream-a/features/ULB_FS_A_Baseline.csv` | figure 8 (row_id join) |

Validation performed before anything is rendered (all of it also runs in the
default preflight mode):

- The optional `phase5_commit_manifest.json` and `phase4_commit_manifest.json`
  are verified (size + SHA-256, coverage of every consumed file) **before**
  anything is consumed; if a manifest is absent the inputs are handled as a
  **legacy unmanifested set** — strict structural validation plus SHA-256
  recording in `phase5_plot_metadata.json`, and verification is never claimed
  falsely.
- The Phase 4 dataset is validated by the hardened Phase 5A validators
  (schema, run completeness, cross-run identical `row_id`/`Class` sequences,
  finite scores, `anomaly_score == -native_score`, binary flags) and must
  contain **exactly 30,000 observations and the ten canonical runs**
  (IF_001..IF_005, LOF_001..LOF_005). The 284,807-row LOF novelty-mode
  companion is never a substitute input.
- **Cross-snapshot consistency:** the SHA-256 the Phase 5A provenance record
  stored for the Phase 4 dataset must match the file being consumed — the
  Phase 5A tables and the row-level data must come from the same Phase 4
  execution.
- Every Phase 5A table is cross-checked against the row-level data: flagged
  counts, observed intersection, agreement-group composition and the saved
  top-1% Jaccard of IF_003/LOF_004 must all agree exactly.
- The FS-A matrix passes the frozen FS-A schema validation and must cover
  every sampled `row_id` (one-to-one join).

## 2. Shared statistical and visual conventions

| Convention | Rule |
|---|---|
| Score orientation | all ranking uses `anomaly_score` (higher = more anomalous); `native_score` is never used for ranking |
| Fixed thresholds | the SAVED Phase 3 flags are consumed exactly as supplied; the bottom-1% rule is never recomputed |
| Derived top-k | budgets other than the canonical 1% derive masks from continuous scores under the Phase 5A tie policy (descending `anomaly_score`, ties by ascending stored position — `phase5_analysis.derive_topk_selection` reused verbatim); derived masks never replace canonical flags |
| Random baselines | expected recall under random review = reviewed fraction (identity line); expected precision = positive-class prevalence; the obsolete incorrectly scaled baseline is not used |
| Percentile convention (fig. 7) | `percentile = 1 − descending tie-averaged rank / n`; 1 = most anomalous, 0 = least; the top-1% boundary sits at percentile 0.99 |
| Hypergeometric reporting | upper-tail probabilities via `log10` (sf/logsf), never presented as exactly zero; the full valid support is displayed and labelled |
| Colours | blues for IF runs, oranges for LOF runs (highlighted IF_003/IF_004/LOF_004 in saturated heavy weights); Okabe–Ito colourblind-safe palette with distinct markers for the four agreement groups; numeric annotations in every matrix cell — colour is never the only channel |
| Exploratory status | IF_003/IF_004/LOF_004 and their pairings were selected after inspecting label-informed results; every comparison involving them is exploratory (post-hoc) |
| Resolution | PNG at 200 dpi (`--dpi`), consistent typography (DejaVu Sans) and line weights across all eight figures |

## 3. The eight figures

### Figure 1 — `phase5_plot1_precision_recall.png`

- **Purpose:** label-based ranking quality of every unsupervised run at every
  operating threshold of the continuous anomaly score.
- **Inputs:** Phase 4 evaluation dataset (`anomaly_score`, `Class`); saved 1%
  flags of the highlighted runs.
- **Conventions:** `sklearn.metrics.precision_recall_curve` on `anomaly_score`
  (higher = more anomalous); AP in the legend; the sample positive-class
  prevalence drawn as the no-skill reference; crosses mark the operating
  point of the saved bottom-1% flags (TP/flagged, TP/frauds) for the three
  highlighted runs.
- **Axes:** x = recall (0–1, includes zero); y = precision (0–1).
- **Scope:** all ten runs; 30,000 observations; 47 frauds on the canonical
  experiment.
- **Limitations:** AP and the curves are label-informed *post-hoc*
  evaluations of an unsupervised ranking — they say nothing about causality;
  the flagged operating points inherit the fixed 1% threshold and any ties it
  produced; comparisons between highlighted runs are exploratory.

### Figure 2 — `phase5_plot2_fraud_discovery.png`

- **Purpose:** operational value of each ranking — fraud found and at what
  precision for a fixed manual-review budget.
- **Inputs:** the saved Phase 5A `phase5_fraud_discovery_curve.csv` (all ten
  runs; every integer budget 1..n).
- **Conventions:** two panels; random expected recall = reviewed fraction
  (identity line, y = x); random expected precision = prevalence
  (e.g. 47/30,000 ≈ 0.00157 on the canonical sample); the canonical 1%
  review budget marked on both panels. The obsolete incorrectly scaled
  discovery baseline is not used.
- **Axes:** x = review budget as a fraction of the sample (0–1); left y =
  recall; right-panel y = precision (both 0–1, zero included — no misleading
  clipping).
- **Scope:** all ten runs; the full budget range is plotted (no truncation).
- **Limitations:** the curves describe THIS sample and its 47 labels; the
  identity baseline assumes random review without replacement; precision at
  very small budgets is dominated by a handful of observations (high
  variance); run-to-run differences at small budgets are exploratory.

### Figure 3 — `phase5_plot3_hypergeometric_overlap.png`

- **Purpose:** extremity of the observed IF_003/LOF_004 flag overlap under
  the independent uniform-selection null.
- **Inputs:** the saved Phase 5A hypergeometric summary (N, flagged counts,
  observed intersection, expected intersection, enrichment, log-tail
  probability).
- **Conventions:** the theoretical hypergeometric log-PMF
  `X ~ Hypergeom(N, successes = k_a, draws = k_b)` drawn over the **full
  valid support** `[max(0, k_a + k_b − N), min(k_a, k_b)]` (e.g. [0, 300] on
  the canonical experiment) on a log10 probability scale; the observed
  intersection (solid marker line) and the null expectation (dashed) marked;
  the upper tail shaded from the observed value; the annotation reports
  `P(X ≥ observed) ≈ 10^x` via the recorded `log10_survival` — an
  underflowed probability is never shown as zero; the displayed range is
  labelled on the figure.
- **Axes:** x = k (number of observations flagged by both runs, full
  support); y = log10 P(X = k).
- **Scope:** one distribution; canonical values on the real data: observed
  107, expected 3.0, enrichment ≈ 35.67×, log10 P ≈ −140.30 (validation
  references, not hardcoded plot values).
- **Limitations:** the test is interpreted ONLY against its stated null —
  two independent uniform random selections. Rejecting that null does not
  establish that flagged observations are true anomalies, and the tiny
  p-value mostly reflects the large N; the pair IF_003/LOF_004 was selected
  post hoc.

### Figure 4 — `phase5_plot4_spearman_matrix.png`

- **Purpose:** global agreement of the ten rankings over all 30,000
  observations.
- **Inputs:** the saved 10×10 Phase 5A Spearman matrix (computed from
  `anomaly_score`; consumed as stored, never recomputed).
- **Conventions:** full [−1, +1] range, zero-centred diverging colormap
  (`RdBu_r`), every cell annotated numerically; the IF_003/LOF_004 cell
  outlined.
- **Axes:** both axes are the ten run IDs in canonical order.
- **Scope:** 10 × 10; diagonal exactly 1.0; canonical IF_003↔LOF_004 value
  ≈ 0.37 on the real data.
- **Limitations:** Spearman measures monotone rank agreement over the WHOLE
  sample — two runs can agree globally yet flag almost disjoint top-1% sets
  (compare figure 5); it is insensitive to the extreme tail that matters for
  review budgets.

### Figure 5 — `phase5_plot5_jaccard_matrix.png`

- **Purpose:** agreement of the canonical bottom-1% selections, exactly as
  saved by Phase 3.
- **Inputs:** the saved 10×10 Phase 5A top-1% Jaccard matrix (built from the
  saved flags; never rederived from scores here).
- **Conventions:** full [0, 1] range, sequential colormap (`viridis`), every
  cell annotated; the IF_003/LOF_004 cell outlined.
- **Axes:** both axes are the ten run IDs in canonical order.
- **Scope:** 10 × 10; diagonal exactly 1.0; canonical IF_003↔LOF_004 value
  ≈ 0.217 on the real data.
- **Limitations:** Jaccard here is threshold-specific (bottom-1% flags with
  their tie behaviour) and says nothing about ranking agreement elsewhere;
  flag counts can deviate slightly from the nominal 300 when the percentile
  rule produced ties.

### Figure 6 — `phase5_plot6_topk_jaccard.png`

- **Purpose:** how method-family agreement scales with the review budget and
  where the highlighted pair sits.
- **Inputs:** Phase 4 evaluation dataset (continuous anomaly scores + saved
  1% flags) — pairwise intersections and unions are constructed from the
  row-level artifact, not from the Phase 5A observation-count summary.
- **Conventions:** budgets 0.1%, 0.2%, 0.5%, 1%, 2%, 5% with
  `k = round(n × pct/100)`; the 1% point uses the SAVED canonical flags
  (open-face markers); every other budget uses derived top-k masks under the
  Phase 5A tie policy (filled markers); within-IF and within-LOF means
  average the 10 off-diagonal pairs of each family (diagonal
  self-comparisons excluded); the cross-method mean averages the 25 mixed
  pairs; IF_003 vs LOF_004 drawn separately.
- **Axes:** x = review budget in percent of the sample (log scale, ticked at
  the six budgets); y = Jaccard similarity (0–1.05).
- **Scope:** all ten runs, 45 pairs per budget.
- **Limitations:** the 1% point and the derived points are not strictly
  commensurable (saved flags vs re-derived masks; tie behaviour differs);
  Jaccard at tiny budgets is noisy; the highlighted pair is a post-hoc
  selection.

### Figure 7 — `phase5_plot7_rank_vs_rank.png`

- **Purpose:** observation-level structure of the agreement between the two
  highlighted runs.
- **Inputs:** Phase 4 evaluation dataset — anomaly scores and saved 1% flags
  of IF_003 and LOF_004, on the validated identical row sequence.
- **Conventions:** percentile = 1 − descending tie-averaged rank / n
  (1 = most anomalous, 0 = least); top-1% boundaries drawn at percentile
  0.99 on each axis; the Neither group rendered as a hexbin density; Both /
  IF-only / LOF-only as distinct marker overlays; all four groups labelled
  with observation and fraud counts (the counts are cross-checked against
  the Phase 5A agreement-group table before rendering).
- **Axes:** x = IF_003 anomaly percentile; y = LOF_004 anomaly percentile;
  both 0–1.
- **Scope:** all 30,000 observations (canonical groups on the real data:
  Both 107 / IF-only 193 / LOF-only 193 / Neither 29,507).
- **Limitations:** percentiles compress 30,000 points into [0, 1] — the
  visual top-right concentration reflects ranks, not distances; group
  membership follows the fixed 1% flags (ties may shift a boundary
  observation); hexagon counts are Neither-group-only; the pair is a
  post-hoc selection.

### Figure 8 — `phase5_plot8_pca_agreement.png`

- **Purpose:** where the four agreement groups sit in the FS-A feature
  space (visualization only).
- **Inputs:** FS-A feature matrix joined on `row_id` (one-to-one; every
  sampled observation must carry FS-A features); saved 1% flags of IF_003
  and LOF_004 from the Phase 4 evaluation dataset.
- **Preprocessing and scaling (documented semantics):** the FS-A matrix
  already embodies the frozen Phase 2 preprocessing — V1–V28 are untouched
  PCA outputs and Time/Amount were RobustScaler-scaled when FS-A was built.
  Phase 5B applies **no additional rescaling** and never standardizes the
  full matrix; the stored FS-A values are projected as-is, in the frozen
  column order (Time, V1..V28, Amount).
- **Projection:** PCA with the exact full-SVD solver (`svd_solver="full"` —
  deterministic, no randomized solver), **fitted on the joined
  30,000-observation sample**. Explained variance of PC1 and PC2 is reported
  on both axis labels and in the title (their sum states how much variance
  the two components carry).
- **Background:** by default the FULL Neither group is plotted (no
  subsampling). When subsampling is explicitly requested, points are drawn
  strictly from the Neither group with a fixed recorded seed
  (`numpy.random.default_rng`, PCG64) — never from the full population
  relabelled as Neither.
- **Axes:** x = PC1 (with % variance explained); y = PC2 (with % variance
  explained).
- **Scope:** all 30,000 observations; the four groups with observation and
  fraud counts in the legend.
- **Limitations:** **PCA is a lossy 2-D projection** — PC1+PC2 capture only
  part of the 30-dimensional FS-A variance, so apparent distances, overlaps
  and group separation in this map must not be read as detector inputs, as
  feature-space evidence, or as an explanation of the detectors' decisions;
  FS-A components are themselves PCA outputs of the original features, so
  the map is a projection of a projection; the flagged groups are tiny
  (hundreds) against ~29.5k background points, and their visibility is a
  rendering choice, not a density estimate.

## 4. Companion artifacts

| File | Content |
|---|---|
| `phase5_figure_catalog.csv` | one row per figure: number, filename, title, purpose, inputs, conventions, rendered size |
| `phase5_plot_metadata.json` | input paths + SHA-256 hashes, manifest statuses (verified / legacy, honestly recorded), software versions, sample summary, all plotting conventions, the figure inventory, `models_fitted: 0` |
| `phase5_plot_commit_manifest.json` | standard manifest (version 1) over the eight PNGs + catalog + metadata; always published LAST |

Verify with:

```python
from mplad.common.manifest import load_manifest, verify_manifest
verify_manifest(load_manifest(<figures dir>/phase5_plot_commit_manifest.json), <figures dir>)
```

## 5. CLI

```
python scripts/run_phase5_plots.py                 # preflight (default): validate only, write nothing
python scripts/run_phase5_plots.py --execute       # render + staged publication
python scripts/run_phase5_plots.py --execute --overwrite
python scripts/run_phase5_plots.py --execute --output-dir "results/stream a/phase 5/figures/reproduction_v2"
```

Input overrides: `--phase5-dir`, `--phase4-dataset`, `--fs-a`; rendering:
`--dpi`. `--expected-sample-size` exists only for deliberate synthetic
replicas (the canonical requirement of exactly 30,000 observations and the
ten canonical runs is enforced by default and any override is warned about).

## 6. Publication safety

Outputs go to `results/stream a/phase 5/figures/reproduction/` — a new
namespace, so **no historical Phase 5 figure is deleted or overwritten**.
Rendering happens in a hidden staging directory beside the output; every
staged file is verified (non-empty; PNG magic bytes for figures) before
anything is published; pre-existing outputs are backed up before replacement
(`--overwrite`) and restored if any step fails; the commit manifest is
published last. A render or publication failure leaves the output directory
exactly as it was.

## 7. Scope restrictions honoured

Phase 3, Phase 4 and Phase 5A source files are untouched (`config.py` gained
an appended Phase 5B section only — the frozen constants above it are
byte-identical); no detector is fitted or refitted; no Phase 4 metric and no
Phase 5A bootstrap result is recalculated; saved canonical flags are never
changed; feature spaces are never changed; no full-data novelty-mode
companion plots are generated; Phase 6 and Streamlit are out of scope; DVC
files, datasets and historical notebooks are not modified.
