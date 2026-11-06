# Phase 6 Contract — Stream A: Cross-Method Consistency Analysis

**Status:** implemented 2026-11-06 (Stage 5, final analysis stage of the Colab →
repository migration).
**Scope:** the cross-method consistency and interpretation layer only — an
**evidence-synthesis stage**, not a modelling or statistical experimentation
stage. No Phase 7, no Streamlit, no full-data novelty-mode companion, no
automated audit-decision engine.

Phase 6 consumes the **verified Phase 4 evaluation dataset** and the
**verified Phase 5A quantitative tables** strictly read-only, and produces an
observation-level agreement-group assignment, a compact consistency scorecard
and a deterministic five-question Markdown report. It never fits, refits or
constructs a detector (the module imports no scikit-learn and no scipy at
all); never creates a new anomaly score or threshold; never recomputes a
bootstrap estimate, a hypergeometric probability or a correlation matrix; and
never modifies the canonical 30,000-row sample, the saved Phase 3 bottom-1%
flags or any Phase 3/4/5A/5B artifact. The 284,807-row full-data LOF
novelty-mode companion stays outside this layer entirely.

---

## 1. Inputs (exact contract)

Default locations (constants in `mplad/common/config.py`; CLI overrides below):

| Input | Default | Constant |
|---|---|---|
| Phase 4 evaluation dataset | `results/stream a/phase 4/reproduction/phase4_evaluation_dataset.csv` | `config.PHASE4_EVALUATION_DATASET_PATH` |
| Phase 5A tables (7 CSVs + 1 JSON) | `results/stream a/phase 5/reproduction/` | `config.DEFAULT_PHASE5_OUTPUT_DIR` |

### 1.1 Phase 4 evaluation dataset

Long form, one row per `(run_id, row_id)`: 300,000 rows on the canonical
experiment (10 runs × 30,000). Frozen schema (`run_id, row_id, Class,
native_score, anomaly_score, flag`), validated by the hardened Phase 5A
validators (`phase5_analysis.load_phase4_dataset` /
`validate_phase4_dataset`): exact column set; run-ID set equal to the ten
canonical runs; no missing values; identical `row_id` and `Class` sequences
across runs; binary `Class`/`flag`; finite floating scores;
`anomaly_score == -native_score`. **Canonical sample-size enforcement is
active by default**: exactly 30,000 observations are required
(`--expected-sample-size` exists only for deliberate synthetic replicas and
is recorded as a non-canonical override).

### 1.2 Phase 5A tables (all validated on load)

| Artifact | Schema (frozen) | Phase 6 validator |
|---|---|---|
| `phase5_pairwise_spearman.csv` | leading `run_id` column + 10 run columns; symmetric; diagonal 1; values in [-1, 1] | `phase6.validate_matrix_table` |
| `phase5_pairwise_jaccard_1pct.csv` | same layout; values in [0, 1] | `phase6.validate_matrix_table` |
| `phase5_hypergeometric_overlap.csv` | one row; the Phase 5A hypergeometric columns; support/union/expected/enrichment/log10 identities checked | `phase6.validate_hypergeometric_table` |
| `phase5_agreement_groups.csv` | four rows (`both, if_only, lof_only, neither`); exhaustive partition; fraud accounting | `phase6.validate_agreement_groups_table` |
| `phase5_multithreshold_agreement.csv` | 66 rows (6 thresholds × 11 levels); counts partition the sample; k rule; canonical-vs-derived source labels | `phase6.validate_multithreshold_table` |
| `phase5_bootstrap_metrics.csv` | 15 rows (3 highlighted runs × 5 metrics); bounded finite values; ordered CIs; single positive replicate count | `phase6.validate_bootstrap_metrics_table` |
| `phase5_paired_bootstrap_differences.csv` | 5 rows (IF_003 vs LOF_004 × 5 metrics); bounded finite values; ordered CIs | `phase6.validate_paired_differences_table` |
| `phase5_run_metadata.json` | `phase == "5A"`; canonical `run_ids`; `sample.sample_size`/`fraud_count`; recorded input hash | `phase6.validate_phase5_metadata` |

The Phase 5B table validators are re-implemented in `phase6.py` (rather than
imported) so the compute layer stays importable without a plotting stack; the
validation logic mirrors the Phase 5B contracts.

### 1.3 Integrity manifests / cross-snapshot consistency

The optional Phase 5A manifest (`phase5_commit_manifest.json`, must cover the
eight consumed tables) and Phase 4 manifest (`phase4_commit_manifest.json`,
must cover the evaluation dataset) are verified BEFORE anything is consumed;
a manifest that does not cover a required artifact is rejected. When a
manifest is absent the inputs are handled as a **legacy unmanifested set**
(strict structural validation + SHA-256 recording; verification never claimed
falsely).

**Cross-snapshot guarantee:** the SHA-256 recorded in
`phase5_run_metadata.json:inputs.evaluation_dataset.sha256` must equal the
hash of the dataset actually consumed — the Phase 5A tables and the row-level
data must come from the SAME Phase 4 execution. Input hashes and manifests
are re-verified immediately before publication (`phase6._recheck_inputs`).

### 1.4 Lightweight consistency checks (required, all must match)

Recomputed from the Phase 4 observation-level data and compared with the
saved Phase 5A values (any disagreement aborts the run): per-detector flagged
counts; observed intersection and union; the four group counts and their
fraud counts; the saved top-1% Jaccard; the ten-run union and intersection at
the canonical 1% budget (vs the counts-by-methods table); the flag-based
`precision_at_1pct` / `recall_at_1pct` / `f1_at_1pct` point estimates of the
three highlighted runs; and the paired-difference identity
(`point[LOF_004] − point[IF_003]` per metric). These checks never replace a
saved value — they are recorded as `row_level_checks` scorecard rows.

---

## 2. Observation-level group assignments (output A)

`IF_003` and `LOF_004` are extracted by `run_id` and joined **one-to-one on
`row_id`** (`phase6.assign_agreement_groups`; duplicated, missing or extra row
IDs on either side are hard errors, as is any `Class` disagreement between
the frames — the Phase 4 label-alignment invariant). Using their **saved
canonical 1% flags**, every observation is assigned exactly one group:

| Group | Rule |
|---|---|
| `Both` | `if_flag == 1 and lof_flag == 1` |
| `IF-only` | `if_flag == 1 and lof_flag == 0` |
| `LOF-only` | `if_flag == 0 and lof_flag == 1` |
| `Neither` | `if_flag == 0 and lof_flag == 0` |

`phase6_group_assignments.csv` — frozen schema, one row per observation
(30,000 on the canonical experiment), in the canonical evaluation-dataset row
order of the IF frame:

```
row_id, Class, if_run_id, lof_run_id, if_anomaly_score, lof_anomaly_score,
if_flag, lof_flag, agreement_group
```

The partition is validated (disjoint, exhaustive, unique keys, every
observation exactly once), and the join-based counts are cross-checked
against the saved Phase 5A agreement-group table (which the loading layer
already matched against the row-level flags) — closing the join-vs-positional
loop (`phase6._check_assignment_against_tables`).

---

## 3. Consistency scorecard (output B)

`phase6_consistency_scorecard.csv` — one row per metric, frozen schema:

```
section, metric, value, value_type, source_artifact, source_field, note
```

Every entry records the **source artifact and the original metric field** it
was read from. Sections and contents:

| Section | Contents (all read from the named frozen artifact) |
|---|---|
| `experiment` | sample size, fraud count, prevalence, run count (Phase 4 dataset) |
| `rank_agreement` | Spearman IF_003–LOF_004; within-IF / within-LOF / cross-method mean-min-max (Spearman matrix) |
| `flag_overlap` | flagged counts, intersection, union, Jaccard, per-detector overlap fractions (hypergeometric summary + Jaccard matrix) |
| `hypergeometric_null` | expected intersection, enrichment, log10 upper tail, null description (hypergeometric summary; the linear tail may underflow — only the log-space value is consumed) |
| `agreement_groups` | per-group observation counts, fraud counts, fraud proportions, recall contributions (agreement-groups table) |
| `review_workload` | Both-only / each detector's flags / union: reviews, sample share, frauds, precision, recall (derived from the agreement-groups rows) |
| `family_consistency` | within-IF / within-LOF / cross-method mean-min-max (Jaccard matrix) |
| `threshold_sensitivity` | per frozen budget: k, selection source, selected-by-≥1 / by-all-10 / by-exactly-1 counts (multithreshold table — counts by number of methods only; no per-pair results exist and none are invented) |
| `bootstrap_context` | precision@1% point estimates and CIs for the three highlighted runs; paired difference and CI; replicate count (bootstrap tables — read, never recomputed) |
| `row_level_checks` | the §1.4 recomputed values with the artifact field each one matched |

Values are formatted deterministically (ints exact, floats 6 decimals,
strings verbatim; non-finite floats rejected) and metric names are unique.

---

## 4. Five-question consistency report (output C)

`phase6_consistency_report.md` — deterministic Markdown answering the five
established research questions from validated values plus **explicitly
authored interpretation rules** (`phase6.build_consistency_report`). No
timestamp, filesystem path or random element appears in the text; identical
inputs regenerate a byte-identical report (creation time lives in the run
metadata).

* **Q1 — rankings similar?** The saved Spearman correlation plus the
  within-family and cross-method families of both matrices. Fixed rule: a
  positive rank correlation measures monotonic association over the full
  sample and **does not imply identical rankings** (contrast with the
  top-1% Jaccard).
* **Q2 — flagged overlap?** Flagged counts, intersection, union, Jaccard,
  group counts. Fixed rule: the **Jaccard** (overlap relative to the union)
  is deliberately distinguished from the **per-detector overlap fractions**
  (overlap relative to each detector's own flagged set) — they answer
  different questions.
* **Q3 — overlap greater than the random null?** The saved hypergeometric
  outputs. The **uniform-independent-selection null is described verbatim**;
  the tail is reported in log space (never as exactly zero on underflow).
  Fixed rules: rejecting this null establishes neither true-anomaly status
  nor operational validity.
* **Q4 — fraud labels across groups?** Group table (counts, fraud shares,
  recall contributions) and the review-workload table distinguishing the
  **Both-only policy, either detector's flagged set, and the union**. Saved
  bootstrap context (point estimates, paired difference, CI) is cited, not
  recomputed. Fixed rules: no universally optimal audit policy is claimed;
  the exploratory (post-hoc) status of the pair is stated; ULB benchmark
  behaviour must not be assumed to transfer to MPLAD transactions.
* **Q5 — disagreement sensitivity?** Within-family vs cross-method ranges
  from the saved 10×10 matrices; the multi-threshold counts-by-methods table;
  the frozen Phase 3 configuration axes (stated as facts, derived from
  `config`). Fixed rules: no causal attribution without controlled
  experiments; the counts table carries no per-pair threshold results and
  none are invented; no configuration or family is claimed superior.

Section 8 lists the interpretation principles verbatim
(`phase6.INTERPRETATION_PRINCIPLES`): labels are post-hoc only; a flag is not
proof of fraud; no ULB → MPLAD transfer; no universal LOF/IF superiority; the
IF_003/LOF_004 comparison is exploratory (label-informed selection bias);
rank agreement, flag overlap and ground-truth detection performance are
distinct constructs; no new threshold or score is introduced.

---

## 5. Reference validation (canonical production path)

`phase6.PHASE6_REFERENCE_VALUES` records the historical acceptance references
of the canonical experiment **for validation only** — they are never written
into an output as if computed: 30,000 observations; 47 fraud labels; 300/300
flags; intersection 107; union 493; groups 107/193/193/29,507 with frauds
30/0/8/9; Spearman 0.3666; Jaccard 0.2170; enrichment 35.67×; log10 upper
tail ≈ −140.30. Integer references compare exactly; the four float references
are published roundings and compare within the tolerances in
`PHASE6_REFERENCE_TOLERANCES` (1e-4 / 1e-4 / 5e-3 / 0.5).

With validation active (default in both preflight and execute) every
source-derived value is compared with its reference; **any mismatch raises
`ReferenceValidationError` listing every difference, nothing is written, and
no value is forced**. `--skip-reference-validation` (library:
`validate_references=False`) exists only for deliberate synthetic replicas
and is recorded in the run metadata as a non-canonical override.

---

## 6. Outputs, provenance and publication safety

Output directory: `results/stream a/phase 6/reproduction/`
(`config.DEFAULT_PHASE6_OUTPUT_DIR`; historical Phase 6 outputs elsewhere
under `results/stream a/phase 6/` are never touched).

| File | Content |
|---|---|
| `phase6_group_assignments.csv` | §2 |
| `phase6_consistency_scorecard.csv` | §3 |
| `phase6_consistency_report.md` | §4 |
| `phase6_run_metadata.json` | phase/stream/layer, run mode, created UTC, the nine input artifacts with paths + SHA-256 + sizes, both manifest statuses, sample summary, run IDs, comparison pair, reference-validation status, non-canonical overrides, analytical conventions, exploratory caveat, output paths, environment versions, `model_fitting.models_fitted: 0` |
| `phase6_commit_manifest.json` | SHA-256 manifest over the four artifacts, **published last** |

Publication uses the established staged approach: fail-fast output precheck →
staging directory → staged-artifact verification (existence, non-empty,
UTF-8 text) → backup of pre-existing outputs (only with `--overwrite`) →
atomic moves → manifest written last over the final bytes. Any failure rolls
back completely (new files removed, backups restored byte-identical).

---

## 7. CLI

```
python scripts/run_phase6.py                 # read-only preflight (default)
python scripts/run_phase6.py --execute       # generate the five outputs
python scripts/run_phase6.py --execute --overwrite
python scripts/run_phase6.py --execute --output-dir <DIR>
    --phase5-dir <DIR>                       # input override
    --evaluation-dataset <CSV>               # input override
    --expected-sample-size <N>               # deliberate, recorded override
    --skip-reference-validation              # deliberate, recorded override
```

Canonical sample-size enforcement and manifest verification are active by
default; reference validation is active by default on the canonical path.

---

## 8. Tests

`tests/test_phase6.py` — 68 tests on synthetic fixtures (a structurally
exact world whose Phase 5A outputs are produced by the REAL frozen
`phase5_analysis` code; unit fixtures with explicit flag combinations):

group assignment for all four combinations; disjoint and exhaustive
partition; duplicate / missing / disjoint row IDs; incorrect run IDs;
shuffled row ordering (join by `row_id` still aligns); non-binary flags and
classes; cross-label mismatch; cross-snapshot hash mismatch; conflicting
Phase 4 vs Phase 5A counts; tampered matrices / hypergeometric summaries /
manifests; wrong sample size; legacy unmanifested inputs; scorecard
consistency with the saved Phase 5A values; per-row source recording;
deterministic value formatting; reference-checked metric coverage;
row-level check rows; union and intersection arithmetic; Both-only /
per-detector / union workload rows; Jaccard vs per-detector overlap
fractions; the five questions, source-value consistency, null statement and
required caveats in the report; interpretation principles; byte-determinism;
no timestamps or paths; reference validation pass / mismatch / tolerance /
missing-value behaviour and its enforcement in preflight and execute; no
model fitting (poisoned detector entry points + source scan); input
immutability (SHA-256 tree snapshots); preflight no-writes; output
protection; overwrite semantics; staging-failure publishes nothing;
publication-failure rollback restores originals byte-identical; manifest
coverage, self-exclusion and verification; run-metadata provenance; and five
CLI subprocess tests.

---

## 9. Scope restrictions (enforced)

Phase 6 does not modify Phases 3/4/5A/5B; does not refit models or create new
anomaly scores; does not recalculate bootstrap experiments; introduces no new
thresholds; generates no plots; modifies no feature spaces or datasets;
touches no DVC configuration; overwrites no historical results; implements
no Streamlit; implements no full-data novelty-mode companion; and is not an
automated audit-decision engine.
