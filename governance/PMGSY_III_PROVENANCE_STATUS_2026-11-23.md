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


## Addendum — 2026-11-23: Cohort robustness, segmentation validity, blinded audit protocol

**Evidence basis:** User-reported outputs from `step1_cohort_robustness.py`, `step2_segmentation_validity.py`, and `step3_prepare_blind_60_audit.py`. Local reports and audit rows were not independently inspected in this GitHub update.

### Cohort robustness and permutation results
- Full-population, within-state Cramer's V for IF top-5% membership vs year/batch: Bihar 0.1273 (37/731; permutation null mean 0.0687, p=0.0399); MP 0.1112 (54/1,074; null mean 0.0552, p=0.0200); UP 0.0915 (128/2,556; null mean 0.0360, p=0.0100). Mean observed V 0.1100.
- About 30% of expected contingency cells are below 5 in each state. Effect sizes are mild but permutation results indicate residual cohort association under the tested null; **do not claim cohort independence or an unconditional confounding-gate pass**.
- Reference population sensitivity remains material: within-cohort 223 vs state-stratified 219 selected, overlap 168, Jaccard 0.6131.

### Segmentation validity diagnostic
- One segment: 47/3,553 selected (1.32%); selected vs controls median sinuosity 3.254 vs 1.232, vertices/km 39.69 vs 24.39.
- Two segments: 95/302 selected (31.46%); median concentration 0.715 vs 0.892, vertices/km 27.27 vs 17.24.
- Three to five segments: 48/302 selected (15.89%); median concentration 0.847 vs 0.580.
- Six or more segments: 29/204 selected (14.22%); median concentration 0.223 vs 0.402.
- Strong dependence on segmentation is established as a **candidate-selection mechanism**, not as proof of useful anomalies. Two-segment selection rate is roughly 24 times single-segment selection rate; determine whether this represents actionable geometry/source defects or legitimate GIS segmentation.

### New blinded 60-case audit
- Reported artifacts: `IF_COHORT_ROBUSTNESS_REPORT.md`, `IF_SEGMENTATION_VALIDITY_REPORT.md`, `if_enriched_audit_blind_review.csv`, `if_enriched_audit_unblinded_key_DO_NOT_PEEK.csv`.
- Blinded identifiers `IFAUD_001`–`IFAUD_060`; 30 IF-selected and 30 matched non-IF controls; worksheet hides `audit_group`, IF score and top-5% membership.
- **Approved next action:** freeze a written rubric, review manually against source evidence, optionally use independent reviewers, freeze annotations and hashes, *then* unblind. Deterministic scripts may validate schema/completeness and calculate outcomes, but **must not assign positive labels from IF scores, R cutoffs, or topology flags**.
- Recommended exclusive outcomes: `VERIFIED_ACTIONABLE_IRREGULARITY`, `VERIFIED_BENIGN_STRUCTURE`, `SOURCE_PROCESSING_ARTIFACT`, `UNRESOLVED`, `INSUFFICIENT_EVIDENCE`. Capture evidence domain, source reference, alternative explanation, confidence and actionability. A source-processing artifact counts as actionable only when independently verified and genuinely warrants correction or investigation.
- **Proposed (not yet adopted or frozen) research-pilot admission criteria:** all 60 accounted for and blinding intact; >=24 adjudicable per arm; IF actionable yield at least 20 percentage points higher than matched controls, with positive lower confidence bound for yield difference using pair-aware analysis if matching is pairwise; independently supported incremental findings beyond Option B; segmentation validity, cohort robustness, and complete provenance. These numerical thresholds are planning proposals and must be formally frozen **before** key unblinding; small samples may yield an inconclusive result.
- A positive audit can justify **expanded research pilot only**, never production deployment or fraud inference.
- Pending artifacts: `IF_AUDIT_PROTOCOL_V1.md`, `IF_ENRICHED_AUDIT_RESULTS_V1.csv`, `IF_AUDIT_COMPARISON_REPORT.md`, `IF_ADMISSION_DECISION_V2.md`.

**Disposition unchanged:** Option B v2 and topology audit are primary descriptive evidence tracks. Isolation Forest remains research-only pending independent evidence validation; no blended scoring.
