# PEIARS — v3 Expanded Audit Sampling Feasibility Report

- **Generated At (UTC):** 2026-11-23T09:16:54.398673+00:00
- **Total Canonical `P` Packages:** `4361`
- **Excluded v1 Audit Packages:** `60`
- **Eligible Remaining Pool:** `4301` (`189` IF top-5%, `4112` non-IF controls)
- **Target v3 Sample Size:** `120` packages (`60` IF top-5% + `60` matched controls).

## Matching Capacity Across Predefined Relaxation Tiers

- **Tier 0 (Exact: `state × cohort_year_batch × seg_bucket × len_band`):** `97` max 1:1 pairs available across `189` eligible IF top-5% packages.
- **Tier 1 (Drop `len_band`: `state × cohort_year_batch × seg_bucket`):** `105` max 1:1 pairs available.
- **Tier 2 (Drop `cohort_year_batch`: `state × seg_bucket`):** `117` max 1:1 pairs available.

## Feasibility Verdict

- With `97` exact Tier-0 pairs and `105` Tier-1 pairs available for a `60`-pair target, 1:1 matched sampling is **FEASIBLE** using deterministic fallback (`Tier 0 -> Tier 1 -> Tier 2`).
- Sample generation remains **HOLD** until `IF_10_CASE_VALIDITY_REVIEW_V1.csv` is adjudicated and frozen.