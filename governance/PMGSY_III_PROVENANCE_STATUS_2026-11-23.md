# PEIARS — PMGSY-III Provenance and Experiment Decision Log

**Recorded:** 2026-11-23  
**Dataset:** `pmgsy3_3state_v1`  
**Scope:** Bihar, Madhya Pradesh, Uttar Pradesh; read-only research and descriptive evidence.  
**Evidence status:** This update records user-reported execution results. The underlying local scripts, Parquet files, manifests, and audit CSVs were not independently executed or inspected in this update.

## Source and canonicalization
- Three-state source: 8,868 geometry-backed features; 5,867 grouped packages, including 4,361 P roads and 1,506 L/non-P proposals.
- Raw-to-master normalized attribute-signature multiplicities reportedly reconcile 1:1. The 3,001 repeated attribute rows are explained by loss of geometry, not fabricated records.
- `MRL_ID` is not unique per spatial feature; preserve source-feature identity and package grouping.
- `segments.parquet` and `packages.parquet` are reported as the canonical `pmgsy3_3state_v1` baseline.
- Source usage/credit/publication terms have been reviewed and accepted by the project owner; this log does not independently adjudicate legal terms.

## Option B v2 descriptive evidence policy
- State-conditional length consistency ratio: `R = sum_geom_len_km / proposed_l_km`.
- Relative gate: `r_iqr_scaled_dev >= 3.0 OR r_abs_modified_z >= 3.5`; practical floor: `abs(R - state_median_R) >= 0.05`.
- Counts: HIGH_STATE_R_DEVIATION 919; SUBTHRESHOLD_REL_SHIFT 210; TOPOLOGY_EVIDENCE 6; BASELINE_WITHIN_RANGE 3,226. Non-P excluded 1,506.
- Exploratory `R < 0.5` cohort: 135 UP packages; **not** a confirmed anomaly threshold.
- Topology evidence is separate: exact duplicates, overlaps, zero-length or invalid geometries.
- `FREEZE_MANIFEST_OPTION_B_V2.json` reportedly hashes 20 artifacts; baseline scripts reportedly committed and pushed to `main` at `331c1d4`. This commit is user-reported, not independently verified here.

## Evidence review and pre-model freeze
- `evidence_review_register.csv`: 227 packages; POSSIBLE_COVERAGE_MISMATCH 147; UNRESOLVED 53; SOURCE_CONVENTION 23; CONFIRMED_GEOMETRY_DEFECT 4.
- UP 2020/Batch 1 accounts for 521 of UP's 748 high-deviation packages; substantial cohort heterogeneity.
- Structural feature readiness: `n_segments`, `mean_seg_len_km`, `mean_sinuosity`, `vertices_per_km`, `seg_len_concentration`. Identifiers, raw R components, and topology flags excluded from IF numeric inputs.
- 84 blinded cases frozen before fitting via `ANNOTATIONS_FREEZE_MANIFEST_V1.json`. Frozen labels are evidence classifications, **not** verified fraud ground truth.

## Controlled Isolation Forest experiment
- Seeds 42–51; contamination 0.02/0.05; state-stratified and pooled arms.
- Seed stability: state-stratified Jaccard 0.8781; pooled 0.8434.
- Non-redundancy against state-conditional R baseline: union Jaccard 0.037; consensus top-5% Jaccard 0.023.
- Initial cohort Cramer's V ~0.675 **must not be used as a valid full-population confounding statistic**: sparse subset contingency table crossed cohort with state among selected rows (verified subset V 0.682; 42.9% expected cells <5).
- Corrected full-population within-state associations of IF top-5% membership vs year/batch: Bihar 0.1273, MP 0.1112, UP 0.0915; each still has 30% sparse expected cells. Interpretation: mild descriptive association, pending sparse-cell/permutation sensitivity.
- Within-cohort vs state-stratified top-5%: 223 vs 219 selected, 168 overlap, Jaccard 0.6131.
- Feature ablations vs full five-feature top-5%: drop n_segments 0.5587; drop seg_len_concentration 0.4649; drop both 0.1526. Structural selection depends strongly on segmentation-related features.
- Frozen 84-case cross-check: 6 IF-selected (5 EXPLAINABLE, 1 UNRESOLVED); insufficient to infer verified detection yield.

## Current disposition — 2026-11-23
1. **PRIMARY DESCRIPTIVE EVIDENCE:** Option B v2 R-consistency and independent topology audit, with separate evidence reasons.
2. **RESEARCH-ONLY:** Isolation Forest as structural candidate discovery. Stable and non-redundant, but not admitted as validated anomaly detector.
3. **NO COMPOSITE SCORE:** Do not blend IF and R into an opaque weighted rank.
4. **NO PRODUCTION SCORING OR FRAUD CLAIMS:** Neither IF selection nor R/topology flags prove misuse, fraud, or incorrect expenditure.
5. **NEXT GATE:** Complete the new 60-row IF-enriched audit (30 IF-selected, 30 matched controls), blinded where feasible; assess independent actionable evidence and uncertainty.
6. **ADDITIONAL DIAGNOSTICS:** Test segmentation feature validity, sparse-cohort robustness/permutation checks, and compare the registered five-feature model against the predefined three-feature ablation without tuning to frozen labels.
7. **REVIEW ARTIFACTS:** `if_enriched_audit_sample.csv`, `PEIARS_IF_DISPOSITION_V1.md` reported created; `IF_ENRICHED_AUDIT_RESULTS_V1.csv`, `IF_SEGMENTATION_VALIDITY_REPORT.md`, `IF_COHORT_ROBUSTNESS_REPORT.md`, and `IF_ADMISSION_DECISION_V2.md` remain pending.

## Provenance limitations
This record is an audit trail of project-reported observations and decisions, not a substitute for raw artifacts, independent verification, or formal model admission. Preserve immutable snapshots, scripts, configuration, hashes, reviewer annotations, and the link from each candidate to source geometry.
