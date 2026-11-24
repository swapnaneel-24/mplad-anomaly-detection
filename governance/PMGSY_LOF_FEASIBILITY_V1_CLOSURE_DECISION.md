# PEIARS Formal Closure Decision: `PEIARS-LOF-FEASIBILITY-V1-CLOSURE`

- **Decision ID:** `PEIARS-LOF-FEASIBILITY-V1-CLOSURE`
- **Date:** 2026-11-24
- **Disposition:** `LOF_FEASIBILITY_COMPLETED_RESEARCH_ONLY_NOT_ADMITTED`
- **Gate 1 (Structural Feasibility):** `PASS_WITH_LIMITATIONS`
- **Gate 2 (Evidence Validity):** `NOT_MET`
- **Research Branch:** `research/pmgsy-lof-feasibility-v1` (prior commit `fc03519`)
- **Dataset Scope:** `pmgsy3_3state_v1` ? `4,361` scored `P` road packages (`UTTAR_PRADESH`, `MADHYA_PRADESH`, `BIHAR`), with `PEIARS_PMGSY_42_CASES.csv` (42 rows: 37 `SUPPORTED_REVIEW_CANDIDATE`, 5 `UNRESOLVED`) used strictly as a descriptive non-random cross-check.

## Summary of Findings & Limitations
1. Neighborhood ranking stability is moderate for `k=20?50`, while `k=10` is comparatively unstable.
2. State-stratified LOF shows low selection overlap with Option B v2 descriptive flags (not proof of independent investigative value).
3. A significant two-segment selection spike occurs in `full_5feat` (no segmentation independence or defect detection is claimed).
4. Dropping segmentation features (`ablation_no_seg_conc`) reduces the two-segment spike but materially changes selected cases.
5. Zero-IQR `RobustScaler` behavior on `n_segments` (81.47% equal to `1`) is a known methodological limitation.
6. The 42-case historical register is non-random and cannot establish unbiased precision, recall, verified detection yield, or external validity.
7. No independent confirmed source defects exist to support operational admission; baseline counts (37 supported / 5 unresolved / 0 confirmed) remain unchanged.

## Preserved Comparison Candidates & Guardrails
- **Preserved research comparison candidates only:** `full_5feat__k35` and `ablation_no_seg_conc__k35`. Existing IF outputs remain a historical benchmark only.
- **Strict prohibitions:** `IF` remains `CLOSED_RESEARCH_NOT_ADMITTED`; LOF is not an admitted anomaly detector; no LOF score may automatically alter case dispositions; no `LOF + IF + Option B` composite score is authorized; no further LOF v1 tuning is authorized; further evidence-validity work requires a new protocol and independent source evidence.
