# PEIARS PMGSY-III Local Outlier Factor (LOF) Feasibility Report (`PEIARS-PMGSY-LOF-FEASIBILITY-V1`)

## 1. Scope and Baseline
- **Dataset:** Canonical `pmgsy3_3state_v1` baseline (`packages.parquet`), filtered to the **4,361** scored `P` road packages (`proposal_type == "P"`, positive `proposed_l_km`, non-null `length_ratio_r`) across `UTTAR_PRADESH` (2,556), `MADHYA_PRADESH` (1,074), and `BIHAR` (731).
- **Structural features:** `n_segments`, `mean_seg_len_km`, `mean_sinuosity`, `vertices_per_km` (`total_vertices / sum_geom_len_km` when `sum_geom_len_km > 0`, else `0.0`), and `seg_len_concentration` (`max_seg_len_km / sum_geom_len_km` when `sum_geom_len_km > 0`, else `0.0`), with state-median imputation on `mean_sinuosity` prior to numeric fill.
- **Configuration:** State-stratified `RobustScaler` + `LocalOutlierFactor` (`novelty=False`, Euclidean/`p=2`) across `n_neighbors` in `[10, 20, 35, 50]`, comparing `full_5feat` against `ablation_no_seg_conc` (`mean_seg_len_km`, `mean_sinuosity`, `vertices_per_km`). No label tuning was performed.

## 2. Phase 1?4 Findings
- **Data readiness & skew:** Zero missingness across present columns, but heavy skew and zero-IQR concentration (`n_segments == 1` in 3,553 / 4,361 = 81.47% of packages, `IQR = 0.0`). Within-state fitting avoids small-cohort truncation across `k` in `[10, 20, 35, 50]`.
- **Neighborhood stability:** Stronger for `k >= 20` (`k20` vs `k35` top-5% Jaccard `0.7951` in `full_5feat`; `k35` vs `k50` `0.7805` in `full_5feat` and `0.8798` in `ablation_no_seg_conc`), while `k = 10` diverges noticeably (`0.4361` vs `k50` in `full_5feat`).
- **Segmentation ablation & Option B v2 overlap:** Removing `n_segments` and `seg_len_concentration` yields `0.5643?0.5927` top-5% Jaccard overlap with `full_5feat`. In `full_5feat`, `2_seg` packages show an elevated selection rate (`13.58%` at `k=20`, `13.91%` at `k=35` vs. `4.22%` / `4.19%` in `1_seg`), dropping to `3.64%` under `ablation_no_seg_conc__k35`. Overlap with Option B v2 non-baseline flags (1,135 packages) is low (`0.0529?0.0603` Jaccard).
- **Descriptive cross-check on the 42-case register:** All **42/42** rows in `PEIARS_PMGSY_42_CASES.csv` (37 `SUPPORTED_REVIEW_CANDIDATE`, 5 `UNRESOLVED`) matched to the 4,361-package baseline. Between **11** (`k=10`) and **13** (`k=20, 35, 50`) fall in `full_5feat` state-stratified top-5% (**10** to **15** in `ablation_no_seg_conc`), with median within-state rank percentiles ~`0.84?0.89`. **Caveat:** Because the 42-case register is a historical review queue rather than an unbiased random sample, this alignment is strictly descriptive and does not establish ground-truth accuracy or confirmed defects.

## 3. Two-Gate Decision
- **Gate 1 ? Structural Feasibility:** **Retain as research result (with caveats).** `k >= 20` (`k=20` or `k=35`) offers reasonable neighborhood stability, low redundancy with Option B v2 (`~0.06` Jaccard), and partial resilience to dropping `n_segments` and `seg_len_concentration` (`~0.57?0.59` Jaccard), subject to `k=10` drift and `2_seg` concentration.
- **Gate 2 ? Evidence Validity:** **Ineligible for operational admission.** Independent defect corroboration remains unestablished, and no composite score or fraud inference is permitted.

## 4. Stop Rule & Next Status
- Treat `PEIARS-PMGSY-LOF-FEASIBILITY-V1` as complete without further parameter tuning or label fitting.
- Keep UI/UX work on `feat/react-workbench-02-data` paused until you choose to resume workbench or evidence-validation tasks.
