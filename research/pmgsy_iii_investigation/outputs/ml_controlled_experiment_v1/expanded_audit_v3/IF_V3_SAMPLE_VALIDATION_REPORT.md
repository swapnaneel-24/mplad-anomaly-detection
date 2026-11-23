# PEIARS — v3 Expanded Audit Sample Validation Report

- **Validated At (UTC):** 2026-11-23T09:45:53.187587+00:00
- **All Hard-Stop Assertions:** `PASS` (120 rows, 120 unique IDs/packages, 60 exact Tier-0 1:1 pairs, 0 v1 overlap, 0 blinding leaks).
- **Tier-0 Matching Coverage:** `123 / 189` (`65.1%`) of eligible IF top-5% packages have at least one exact Tier-0 control.
- **Scope Caveat:** Conclusions generalize strictly to the Tier-0 matchable population; unmatched extreme singletons/rare strata are documented below.

## 1. Sample Balance Across Matching Dimensions (`60` Selected vs. `60` Controls)

| dimension         | stratum_value  | IF_TOP5_SELECTED | MATCHED_NON_IF_CONTROL |
| ----------------- | -------------- | ---------------- | ---------------------- |
| source_state_key  | BIHAR          | 4                | 4                      |
| source_state_key  | MADHYA_PRADESH | 24               | 24                     |
| source_state_key  | UTTAR_PRADESH  | 32               | 32                     |
| cohort_year_batch | 2019_B1        | 5                | 5                      |
| cohort_year_batch | 2020_B1        | 17               | 17                     |
| cohort_year_batch | 2021_B1        | 27               | 27                     |
| cohort_year_batch | 2021_B2        | 4                | 4                      |
| cohort_year_batch | 2022_B1        | 5                | 5                      |
| cohort_year_batch | 2022_B2        | 2                | 2                      |
| seg_bucket        | 1_seg          | 25               | 25                     |
| seg_bucket        | 2_segs         | 21               | 21                     |
| seg_bucket        | 3_to_5_segs    | 2                | 2                      |
| seg_bucket        | 6_plus_segs    | 12               | 12                     |
| len_band          | 10_to_20km     | 15               | 15                     |
| len_band          | 5_to_10km      | 40               | 40                     |
| len_band          | ge_20km        | 5                | 5                      |

## 2. Tier-0 Matchable vs. Unmatched Eligible IF Top-5% Candidates (`n = 189`)

| pool_subset             | n_packages | med_n_segments | med_seg_conc | med_sinuosity | med_vertices_km | med_proposed_km |
| ----------------------- | ---------- | -------------- | ------------ | ------------- | --------------- | --------------- |
| Unmatched_IF_Top5       | 66         | 3.0            | 0.8          | 1.142         | 26.44           | 7.28            |
| Tier0_Matchable_IF_Top5 | 123        | 2.0            | 0.794        | 1.216         | 26.6            | 8.27            |