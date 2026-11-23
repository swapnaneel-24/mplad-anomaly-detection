# PEIARS — Expanded Isolation Forest Validation Audit Protocol v1 (v3 Study)

- **Protocol Frozen At (UTC):** 2026-11-23T09:22:36.094537+00:00
- **Prerequisite Validity Freeze:** `IF_10_CASE_VALIDITY_DECISION_V1.md` (`IF_10_CASE_VALIDITY_REVIEW_V1.csv` SHA-256: `6a96423dceb5824630362bb4c793c5218c3d8b23b39e652e08b551a7644dbea1`)
- **Sample Generation Gate:** **HOLD** until protocol freeze and bipartite Tier-0 matching check are explicitly released.

## Frozen v3 Design Parameters

- **Dataset & Model:** `pmgsy3_3state_v1`; frozen 5-feature state-stratified Isolation Forest (`seed = 42`, `contamination = 0.05`, `if_strat_top5`). No model retraining or threshold changes during v3.
- **Sample Size & Exclusions:** `120` packages total (`60` unique 1:1 matched pairs: `60` `IF_TOP5_SELECTED` + `60` `MATCHED_NON_IF_CONTROL`) drawn from `4,301` eligible packages after excluding all `60` v1 audit packages.
- **Sampling Seed & Matching:** Seed `20261123`; Tier-0 exact bipartite 1:1 matching on `(source_state_key, cohort_year_batch, seg_bucket, proposed_length_band)` with random selection of `60` disjoint pairs from maximum matching (`97` Tier-0 candidate pairs identified in feasibility check).
- **Blinding & Review:** Independent, blinded evidence-based review; blinded worksheet hides IF membership/scores; unblinding key stored separately.

## Primary & Secondary Endpoints

- **Primary Endpoint:** Independently verified actionable irregularity (`CONFIRMED_SOURCE_DEFECT` or equivalent verified actionable defect), reported separately for source-data vs. infrastructure domains.
- **Secondary Endpoints:** Supported review candidates, benign source-processing artifacts, unresolved cases, and unique IF findings not already flagged by Option B v2 or topology audit.

## Statistical Analysis & Sensitivity Plan

- **Pair-Aware Inference:** Matched-pair yield comparison with paired bootstrap 95% CI, discordant-pair counts, and paired binary test.
- **Sensitivity Bounds:** Report complete-case yield alongside bounds treating unresolved cases as positive or negative (including an adverse bound for IF).

## Decision Gates (`A`–`G`)

- **Gate A (Integrity):** All 120 records accounted for; frozen sample & unblinding key; zero selection leakage.
- **Gate B (Completeness):** At least `48` adjudicable cases per arm.
- **Gate C (Actionable Yield):** IF minus control yield `>= +0.20` (`+20.0 pp`).
- **Gate D (Uncertainty):** Lower 95% confidence bound of yield difference `> 0`.
- **Gate E (Incremental Value):** At least one verified actionable IF finding not already captured by Option B v2 or topology audit.
- **Gate F (Structural Validity):** Findings not solely explained by benign segmentation conventions.
- **Gate G (Review Reliability):** Reviewer assessments preserved and disagreements resolved transparently.