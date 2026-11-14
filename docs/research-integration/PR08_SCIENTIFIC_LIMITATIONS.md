# PR-08 Scientific Limitations

**Baseline:** `831c9b4d23349b57d48828157d68fefde5927f02`
**Branch:** `pr-08-research-readonly`

---

## 1. Dataset population

The precomputed reference values originate from the **ULB Credit Card
Fraud Detection 2013** dataset:

- **Rows:** 284,807 transactions
- **Features:** 31 columns (V1–V28 PCA-derived, Time, Amount, Class)
- **Class distribution:** 492 positive (fraud), 284,315 negative
- **Sample:** 30,000-row random subsample with 47 fraud labels
- **License:** ODbL v1.0 and DbCL v1.0

This is a **proxy benchmark** — it is NOT MPLAD data. The dataset
contains anonymized PCA features (V1–V28) that cannot be interpreted
in domain terms. The benchmark measures methodological performance on
credit-card fraud detection, not public-expenditure anomaly detection.

---

## 2. Experimental scope

- **Models:** Isolation Forest (IF_003: 100 estimators, 5% max_samples,
  seed 42) and Local Outlier Factor (LOF_004: 50 neighbors, euclidean
  metric).
- **Threshold:** Bottom 1% of anomaly scores flagged (300 flags per
  detector on the 30k sample).
- **Evaluation:** Post-hoc, label-informed (Phase 4 metrics, Phase 5A
  bootstrap, Phase 6 cross-method consistency). Labels were NOT used
  for model fitting, tuning, or threshold selection.
- **Comparison pair:** IF_003 vs LOF_004 — selected AFTER inspecting
  the Phase 4 label-informed results (exploratory, post-hoc selection
  bias).

---

## 3. Model interpretation

- **Isolation Forest:** An ensemble tree method that flags anomalies
  based on path length. Lower `decision_function` scores = more
  anomalous. The adapter serves the `anomaly_score` orientation
  (higher = more anomalous) as documented in the Phase 4 contract.
- **LOF:** A density-based method that flags anomalies based on local
  deviation. Lower `negative_outlier_factor` = more anomalous.
- **Distinction:** IF and LOF are different analytical methods with
  different sensitivity profiles (global vs local). No universal
  superiority of either is claimed.

---

## 4. Metrics

The reference values are aggregate-level experiment facts and
cross-method consistency metrics:
- Flagged counts, intersection, union, agreement-group composition.
- Spearman rank correlation (monotonic association over the full
  sample — does NOT imply identical rankings).
- Jaccard overlap (overlap relative to the union — distinct from
  per-detector overlap fractions).
- Hypergeometric enrichment (observed intersection / expected under
  uniform-independent-selection null — rejecting the null establishes
  neither true-anomaly status nor operational validity).

---

## 5. Uncertainty

- The reference values are point estimates from a single 30k sample.
- Bootstrap confidence intervals are documented in the Phase 5A
  contract but are NOT served by the adapter (they are not in the
  `PHASE6_REFERENCE_VALUES` dict).
- No p-values, confidence intervals, or uncertainty estimates are
  fabricated by the adapter.

---

## 6. Prohibited claims

The adapter and frontend presentation MUST NOT claim:

1. That anomaly flags are proof of fraud, corruption, or misconduct.
2. That ULB benchmark performance transfers to MPLAD transactions.
3. That Isolation Forest or LOF is universally superior.
4. That the IF_003/LOF_004 comparison is confirmatory (it is
   exploratory, post-hoc selected).
5. That the reference values are live predictions.
6. That the reference values apply to any specific public-expenditure
   record, project, or constituency.
7. That the hypergeometric test establishes true-anomaly status.
8. That the results are field-validated fraud-detection performance.

---

## 7. Synthetic separation

The research results are strictly separated from synthetic
demonstration data:
- The research adapter (`/api/v1/research/*`) serves frozen scientific
  constants from `src/mplad/stream_a/phase6.py`.
- The synthetic source adapter (`/api/v1/synthetic/*`,
  `/api/v1/cases/*`) serves synthetic demonstration records from
  `app/services/synthetic_source.py`.
- The two adapters share NO code, NO data, and NO endpoints.
- The frontend Research workspace displays research results with the
  label "Precomputed Research Results" and the caution "These are not
  live predictions."
- The frontend Investigation workspace displays synthetic demonstration
  records with the label "SYNTHETIC DEMONSTRATION RECORD — NOT A
  RESEARCH FINDING."
- No automatic linking between research results and review cases exists.

---

## 8. Interpretation principles (served verbatim by the adapter)

1. Labels are used solely for post-hoc evaluation and discussion; no
   model was selected, tuned or refitted using labels in this phase.
2. An anomaly flag is not proof of fraud; flags are detector opinions
   at a fixed budget, not adjudicated findings.
3. Performance observed on the ULB credit-card fraud benchmark must
   not be assumed to transfer to MPLAD transactions.
4. No universal superiority of LOF or Isolation Forest is claimed; the
   evidence covers one benchmark sample and post-hoc selected runs.
5. The IF_003/LOF_004 comparison is exploratory and subject to
   label-informed selection bias.
6. Rank agreement, flag overlap and ground-truth detection performance
   are distinct constructs and are reported separately.
7. No new threshold is introduced and no new anomaly score is created;
   the saved canonical Phase 3 1% flags are the only selections analysed.
