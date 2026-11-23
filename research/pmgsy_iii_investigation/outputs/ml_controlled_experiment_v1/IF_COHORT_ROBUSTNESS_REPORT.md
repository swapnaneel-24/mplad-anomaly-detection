# PEIARS — Isolation Forest Cohort Robustness Report

- **Generated At (UTC):** 2026-11-23T05:47:55.343795+00:00
- **Sparse Cohort Merge Threshold:** `n < 30` within state merged into `OTHER_SPARSE_COHORTS`.
- **Permutations:** `500` label permutations per state.

## 1. Retired Metric vs. Merged Within-State Association

- The earlier `0.675` / `0.682` value came from cross-tabulating `cohort_year_batch` against `source_state_key` restricted to `if_strat_top5` rows (`42.9%` expected cells less than 5), mixing state identity and cohort sparsity.
- After merging cohorts with less than `30` rows per state, mean within-state Cramér's V (`if_strat_top5` vs `cohort_merged`) is **`0.1100`**.

| state          | n_packages | n_top5 | merged_cohort_cols | pct_expected_lt_5 | obs_cramers_v | perm_null_mean_v | perm_p_value |
| -------------- | ---------- | ------ | ------------------ | ----------------- | ------------- | ---------------- | ------------ |
| BIHAR          | 731        | 37     | 5                  | 30.0              | 0.1273        | 0.0687           | 0.0399       |
| MADHYA_PRADESH | 1074       | 54     | 5                  | 30.0              | 0.1112        | 0.0552           | 0.02         |
| UTTAR_PRADESH  | 2556       | 128    | 5                  | 30.0              | 0.0915        | 0.036            | 0.01         |

## 2. Reference-Population Sensitivity (Within-Cohort vs. State-Stratified)

- Scoring within `state x cohort_year_batch` (`n >= 20`, `223` flagged) vs state-stratified scoring (`219` flagged) yields `168` overlapping packages (**Jaccard = `0.6131`**).
- High seed stability (`0.8781`) does not eliminate reference-population sensitivity: ~39% of candidate membership turns over when cohort baselines replace state-wide baselines.