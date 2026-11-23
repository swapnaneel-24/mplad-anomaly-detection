# PEIARS — Final Isolation Forest Experiment Disposition (v1)

- **Recorded At (UTC):** 2026-11-23T05:34:26.863172+00:00
- **Primary Evidence Pipeline:** Option B v2 (`scoring_option_b_v2`) + Topology Audit Track (`exact_geom_dup`, `linear_overlap`, `zero_len_segment`, `invalid_segment_geom`).
- **Isolation Forest Status:** **Research-only sandbox** (admission gate failed on cohort confounding: `strat_cohort_cramers_v_mean = 0.675` vs `<= 0.35`, despite seed stability `0.8781` and low overlap with `R` baseline `0.037`).
- **Prohibited Actions:** No Option B v3 yet, no weighted IF + R composite score, and no production ML anomaly labels without independent validation.
- **Diagnostic Artifacts:** `diagnostics/cramers_v_verification.csv`, `diagnostics/feature_ablation_summary.csv`, `diagnostics/if_enriched_audit_sample.csv`.
