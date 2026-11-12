# Stream A -- Phase 6: Cross-Method Consistency Report

Comparison pair: **IF_003** (Isolation Forest) vs **LOF_004** (LOF) on their saved canonical top-1% flags, over 30,000 observations carrying 47 labelled frauds (prevalence 0.16%).

This is an evidence-synthesis report: it was generated deterministically from validated frozen artifacts. No model was fitted, no threshold was selected, and no bootstrap estimate, hypergeometric probability or correlation matrix was recomputed in this phase (creation time, input hashes and software versions live in `phase6_run_metadata.json`).

## 1. Inputs and provenance

| Consumed artifact | Role | SHA-256 (first 12) | Manifest |
|---|---|---|---|
| `phase4_evaluation_dataset.csv` | row-level scores, saved 1% flags, labels | `affbf02c63da` | manifest_verified |
| `phase5_pairwise_spearman.csv` | 10x10 Spearman rank-correlation matrix | `673f4793cf8f` | manifest_verified |
| `phase5_pairwise_jaccard_1pct.csv` | 10x10 top-1% Jaccard matrix (saved flags) | `b8e5b7f4b5b6` | manifest_verified |
| `phase5_hypergeometric_overlap.csv` | overlap-test summary (IF_003 vs LOF_004) | `509d417f5824` | manifest_verified |
| `phase5_agreement_groups.csv` | four-group composition (IF_003 vs LOF_004) | `17822c729c10` | manifest_verified |
| `phase5_multithreshold_agreement.csv` | counts by number of selecting methods | `af6db9f91935` | manifest_verified |
| `phase5_bootstrap_metrics.csv` | bootstrap point estimates and CIs | `7bcb1f6eab5c` | manifest_verified |
| `phase5_paired_bootstrap_differences.csv` | paired LOF_004 - IF_003 differences | `237d7c952bf9` | manifest_verified |
| `phase5_run_metadata.json` | Phase 5A provenance (input hashes, conventions) | `719ec5240f6b` | manifest_verified |

Runs covered: 10 canonical configurations (IF_001..IF_005, LOF_001..LOF_005). The Phase 5A tables and the row-level dataset were verified to come from the SAME Phase 4 execution (input-hash cross-check), and the lightweight consistency checks listed in section 2 all matched.

> Exploratory analysis: the highlighted runs (IF_003, IF_004, LOF_004 and the IF_003/LOF_004 pair) were selected after inspecting the label-informed Phase 4 evaluation results; comparisons involving them are post-hoc and must not be read as confirmatory.

## 2. Method

- **Group assignment.** IF_003 and LOF_004 were extracted by `run_id` from the verified Phase 4 evaluation dataset and joined **one-to-one on `row_id`** (duplicated, missing or extra row IDs are hard errors). Using their saved canonical 1% flags, every observation is assigned exactly one group: **Both** (IF=1, LOF=1), **IF-only** (IF=1, LOF=0), **LOF-only** (IF=0, LOF=1) or **Neither** (IF=0, LOF=0) -- a disjoint and exhaustive partition of all 30,000 observations. The join-based counts were cross-checked against the saved Phase 5A agreement-group table (identical).
- **Frozen values.** The Spearman correlation, the top-1% Jaccard, the hypergeometric quantities, the family summaries and the bootstrap results are READ from the Phase 5A tables; none is recalculated here.
- **Lightweight consistency checks against the Phase 4 observation-level data** (all matching, recorded as scorecard rows in the `row_level_checks` section): per-detector flagged counts, the observed intersection and union, the four group counts and their fraud counts, the saved top-1% Jaccard, the ten-run union and intersection at the 1% budget, and the flag-based precision / recall / F1-at-1% point estimates of the three highlighted runs.
- **Determinism.** This report contains no timestamps, paths or random elements; identical inputs regenerate byte-identical text.

## 3. Q1 -- Are the anomaly rankings similar?

Spearman rank correlation between the IF_003 and LOF_004 `anomaly_score` vectors (saved `phase5_pairwise_spearman.csv`): **0.3666**.

Comparison families from the saved 10x10 matrices (off-diagonal):

| Matrix / family | Mean | Min | Max |
|---|---|---|---|
| Spearman / within Isolation Forest | 0.9440 | 0.9280 | 0.9824 |
| Spearman / within LOF | 0.7320 | 0.4388 | 0.9387 |
| Spearman / cross-method (IF x LOF) | 0.2971 | 0.1955 | 0.3773 |
| Top-1% Jaccard / within Isolation Forest | 0.7460 | 0.6901 | 0.8237 |
| Top-1% Jaccard / within LOF | 0.2652 | 0.0563 | 0.4851 |
| Top-1% Jaccard / cross-method (IF x LOF) | 0.0797 | 0.0118 | 0.2220 |

Interpretation (fixed rules):

- The two detectors' full-sample rankings are positively correlated (Spearman 0.3666). A positive rank correlation measures monotonic association across all 30,000 observations; it **does not imply identical anomaly rankings**, and it is compatible with very different top-1% selections -- the observed top-1% Jaccard between the two detectors is 0.2170 (Q2), whereas identical selections would give 1.0.
- Within the saved matrices, the within-IF mean Spearman (0.9440) is higher than the cross-method mean (0.2971), and the within-LOF mean (0.7320) is higher than the cross-method mean; the analogous Jaccard comparisons are higher than (within-IF 0.7460 vs 0.0797) and higher than (within-LOF 0.2652 vs 0.0797).
- Rank agreement (this question), flag overlap (Q2) and ground-truth detection performance (Q4) are distinct constructs; a change in one does not determine the others.

## 4. Q2 -- How much do the flagged observations overlap?

| Quantity | Value | Source |
|---|---|---|
| IF_003 flagged (saved 1% flags) | 300 | `phase5_hypergeometric_overlap.csv` : `run_a_flagged` |
| LOF_004 flagged (saved 1% flags) | 300 | `run_b_flagged` |
| Observed intersection (Both) | 107 | `observed_intersection` |
| Union | 493 | `union_size` |
| **Jaccard** = intersection / union | **0.2170** (21.70%) | `phase5_pairwise_jaccard_1pct.csv` : `[IF_003, LOF_004]` |
| Share of IF_003's flagged set also flagged by LOF_004 | 0.3567 (35.67%) | derived: `observed_intersection / run_a_flagged` |
| Share of LOF_004's flagged set also flagged by IF_003 | 0.3567 (35.67%) | derived: `observed_intersection / run_b_flagged` |

Group counts (disjoint, exhaustive partition of all observations): **Both** 107 / **IF-only** 193 / **LOF-only** 193 / **Neither** 29,507.

Interpretation (fixed rules):

- The **Jaccard coefficient** (0.2170) expresses the overlap **relative to the union** of the two flagged sets; the **per-detector overlap fractions** (35.67% of IF_003's flags and 35.67% of LOF_004's flags) express the overlap **relative to each detector's own flagged set. These quantities answer different questions and are deliberately reported side by side; they coincide only in special cases.
- Of IF_003's 300 flagged observations, 193 are flagged only by IF_003 and 107 are shared with LOF_004; of LOF_004's 300 flagged observations, 193 are flagged only by LOF_004.

## 5. Q3 -- Is the overlap greater than expected under the specified random-selection null?

The null this test is interpreted against (verbatim from the Phase 5A artifact): *"independent uniform random selection: run_a's flags and run_b's flags are two independent uniform random subsets of the n observations; the upper-tail probability is the extremity of the observed overlap under THIS null only and does not establish that flagged observations are true anomalies"*.

- Expected intersection under the null: `k_a * k_b / n` = 300 x 300 / 30,000 = **3.00**.
- Observed intersection: **107** (enrichment observed / expected: **35.67x**).
- log10 P(X >= observed) = **-140.30** (upper-tail probability of the hypergeometric null; the linear-space upper-tail probability is approximately 1e-140 at this overlap; the log-space value is reported for precision).

Interpretation (fixed rules):

- The observed overlap (107) is compared with independent uniform random selection of two subsets of the observed sizes; the upper-tail probability above quantifies how surprising the overlap is **under this null and nothing else**.
- Rejecting this null establishes neither that the flagged observations are true anomalies, nor any operational validity for fraud detection on MPLAD transactions or any other deployment.

## 6. Q4 -- How are known fraud labels distributed across agreement groups?

Labels enter here solely post hoc, to describe the composition of the four agreement groups of the saved 1% flags:

| Group | Observations | Labelled frauds | Fraud share in group | Recall contribution |
|---|---|---|---|---|
| Both | 107 | 30 | 28.04% | 63.83% |
| IF-only | 193 | 0 | 0.00% | 0.00% |
| LOF-only | 193 | 8 | 4.15% | 17.02% |
| Neither | 29,507 | 9 | 0.03% | 19.15% |

Review-workload policies at the canonical 1% flags:

| Review policy | Reviews | Share of sample | Labelled frauds found | Precision | Recall |
|---|---|---|---|---|---|
| Both-only (agreement gate) | 107 | 0.36% | 30 | 28.04% | 63.83% |
| IF_003's flagged set | 300 | 1.00% | 30 | 10.00% | 63.83% |
| LOF_004's flagged set | 300 | 1.00% | 38 | 12.67% | 80.85% |
| Union of both flagged sets | 493 | 1.64% | 38 | 7.71% | 80.85% |

- Reviewing only the **Both** group examines 107 observations (0.36% of the sample) and recovers 30 of the 47 labelled frauds; the **union** policy examines 493 observations (1.64%) and recovers 38. Each individual detector's 300-observation flagged set sits between these two operating points.
- **9 labelled fraud(s) are in the Neither group** and are missed by both detectors at the 1% budget.
- Saved bootstrap context (Phase 5A, 2,000 class-stratified replicates): precision@1% point estimates 0.1000 [IF_003] and 0.1267 [LOF_004]; paired difference (LOF_004 - IF_003) +0.0267 with a 95% percentile CI of [0.0066, 0.0489] (read from the frozen Phase 5A tables; not recomputed).
- These rows describe alternative review policies on ONE benchmark sample; they do not establish a universally optimal audit policy. The comparison pair was selected after label-informed inspection, so the precision contrast is exploratory; cost structures, investigation capacity and fraud-base rates on MPLAD transactions would have to dominate any real policy choice.

## 7. Q5 -- Is disagreement sensitive to neighbourhood size, detector configuration or review threshold?

Frozen Phase 3 configuration axes: the Isolation Forest configurations vary n_estimators (100/200), max_samples (0.05/256) and random_state (42/43/44); the LOF configurations vary n_neighbors (5/15/30/50) and the distance metric (euclidean/manhattan; LOF_005 is the manhattan variant). The canonical run order maps IF_001..IF_005 and LOF_001..LOF_005 onto these grids in order.

Agreement levels from the saved 10x10 matrices (see Q1 table):

- Spearman -- within IF: mean 0.9440 (range 0.9280 to 0.9824); within LOF: mean 0.7320 (range 0.4388 to 0.9387); cross-method: mean 0.2971 (range 0.1955 to 0.3773).
- Top-1% Jaccard -- within IF: mean 0.7460 (range 0.6901 to 0.8237); within LOF: mean 0.2652 (range 0.0563 to 0.4851); cross-method: mean 0.0797 (range 0.0118 to 0.2220).

Multi-threshold agreement from the saved counts-by-number-of-methods table (observations selected by at least one / all ten / exactly one of the ten configurations):

| Review budget | k per method | Selection source | Selected by >= 1 method | By all 10 | By exactly 1 |
|---|---|---|---|---|---|
| 0.1% | 30 | `derived_topk` | 136 | 0 | 72 |
| 0.2% | 60 | `derived_topk` | 241 | 1 | 119 |
| 0.5% | 150 | `derived_topk` | 552 | 5 | 233 |
| 1% | 300 | `canonical_saved_flags` | 1,090 | 7 | 459 |
| 2% | 600 | `derived_topk` | 2,051 | 16 | 728 |
| 5% | 1,500 | `derived_topk` | 4,740 | 62 | 1,589 |

Interpretation (fixed rules):

- The saved statistics show the within-family and cross-method agreement levels and their ranges, and how the counts change with the review budget. They do **not** isolate which configuration choice causes which part of the disagreement: attributing disagreement to a specific seed, parameter, neighbourhood size or distance metric would require controlled single-factor experiments, which were not run in this experiment.
- The multi-threshold artifact contains only counts by number of selecting methods; it carries no per-pair results at the non-canonical thresholds, and none are invented here.
- No detector family or configuration is claimed to be uniquely responsible for the disagreement, and no configuration is claimed superior.

## 8. Interpretation principles

1. Labels are used solely for post-hoc evaluation and discussion; no model was selected, tuned or refitted using labels in this phase.
2. An anomaly flag is not proof of fraud; flags are detector opinions at a fixed budget, not adjudicated findings.
3. Performance observed on the ULB credit-card fraud benchmark must not be assumed to transfer to MPLAD transactions.
4. No universal superiority of LOF or Isolation Forest is claimed; the evidence covers one benchmark sample and post-hoc selected runs.
5. The IF_003/LOF_004 comparison is exploratory and subject to label-informed selection bias (the pair was highlighted after inspecting the Phase 4 label-informed results).
6. Rank agreement, flag overlap and ground-truth detection performance are distinct constructs and are reported separately (Q1, Q2, Q4).
7. No new threshold is introduced and no new anomaly score is created; the saved canonical Phase 3 1% flags are the only selections analysed.

## 9. Reproducibility

This report is byte-deterministic: it contains no timestamps, no filesystem paths and no random elements, and every number is read from a validated frozen artifact (the scorecard records the source artifact and original metric field of every value). Regenerate with:

    python scripts/run_phase6.py --execute

Creation time, full input hashes, manifest statuses, software versions, the reference-validation status and the zero-model-fitting declaration are recorded in `phase6_run_metadata.json`; integrity is vouched by `phase6_commit_manifest.json` (published last).
