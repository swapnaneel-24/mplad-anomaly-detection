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


## Addendum — 2026-11-23: v3 IF closure and transition to Option B evidence review

**Basis:** Project-owner reported outcomes and Git commits; local CSV and frozen experiment files were not independently inspected in this update. Historical frozen reports remain unchanged.

### IF v3 and research closure
- v3: 120 blinded desk-review cases, 60 Tier-0 matched pairs; single reviewer, no external field survey. Outcomes: 93 BENIGN_EXPLAINED, 17 UNRESOLVED, 10 SUPPORTED_REVIEW_CANDIDATE, 0 CONFIRMED_SOURCE_DEFECT, 0 INSUFFICIENT_EVIDENCE.
- IF arm: 38 benign, 6 supported, 16 unresolved, 0 confirmed; control: 55 benign, 4 supported, 1 unresolved, 0 confirmed. Only 44 complete adjudicable pairs; gate completeness >=48 not met.
- Primary confirmed-defect difference 0.0; observed paired bootstrap CI [0,0] is **degenerate** with zero observed events and does not prove zero true effect. No demonstrated incremental confirmed defects.
- Formal IF research disposition: `CLOSED_RESEARCH_NOT_ADMITTED`, reasons `PRIMARY_ENDPOINT_ZERO_CONFIRMED_DEFECTS; COMPLETENESS_GATE_FAILED; INSUFFICIENT_INDEPENDENT_EVIDENCE`. No v4 authorized; no production detector or fraud inference.
- Project owner reports v3 commit `afdd70b` and closure commit `f72cd81`, including `IF_RESEARCH_CLOSURE_V1.md` and `PEIARS_PMGSY_FINAL_RESEARCH_REPORT.md`. These commit references are reported, not independently reconciled to local artifact contents in this addendum.

### Active PMGSY evidence track
- `PMGSY_EVIDENCE_REGISTER_V2.csv` reportedly generated locally with 4,361 P-package rows under `research/pmgsy_iii_investigation/outputs/option_b_v2_evidence_review/`; the full CSV remains ignored by `*.csv`.
- Primary tracks remain **Option B v2** (state-conditional R consistency) and **topology audit**, independent and inspectable.
- **Next authorized work is review preparation, not confirmed findings:** validate register cardinality, unique source-state/package keys, signed length difference conventions, missingness, arithmetic, topology flags, and agreement with frozen Option B counts.
- Generate three non-exclusive queues: all 6 topology-evidence packages; top 25 by absolute km difference; top 25 by absolute relative difference. Deduplicate case identities while retaining all queue-membership reasons. Include positive and negative discrepancies.
- Recompute source geometry for reviewed cases and record `CONFIRMED_SOURCE_DEFECT`, `SUPPORTED_REVIEW_CANDIDATE`, `BENIGN_EXPLAINED`, or `UNRESOLVED` only as evidence warrants. No high-R or topology flag alone proves fraud or a source defect.
- **Repository policy:** keep the full generated register CSV ignored for now; track deterministic generator, source/output SHA-256 manifest, validation summary, queue definition and a sanitized review summary. Do not alter frozen IF or Option B v2 reports.
- Planned milestone `PEIARS-PMGSY-EVIDENCE-REVIEW-V1`; execution pending. See `governance/PMGSY_EVIDENCE_REVIEW_PLAN_V1.md`.

### Evidence/availability boundary
This addendum records the project owner's reported status and an approved next-step plan. It does **not** assert that the local 4,361-row register has been inspected, that priority queues have been generated, or that any new source defects have been confirmed.


## Addendum — 2026-11-23: Evidence Register V2 validation and PEIARS integration handoff

**Source status:** Values below are project-owner-reported results, not independent inspection of the local register or the reported `dd29405` commit. **Repository reconciliation:** the connected GitHub repository (`swapnaneel-24/mplad-anomaly-detection`) does not resolve short SHA `dd29405`, and the named milestone artifacts could not be found there at the anticipated paths. Confirm actual remote and full commit SHA before asserting cross-repository provenance continuity.

### Reported completed local milestone
- User reports `dd29405` added `run_pmgsy_evidence_register_v2.py`, `PMGSY_EVIDENCE_REGISTER_V2_MANIFEST.json`, `PMGSY_EVIDENCE_REGISTER_V2_SUMMARY.md`, and `PMGSY_PRIORITY_REVIEW_V1.md`.
- `PMGSY_EVIDENCE_REGISTER_V2.csv`: 4,361 unique P packages, 0 duplicated `package_uid`, exact UID match to scored baseline, 0 nulls, arithmetic discrepancy 0 for `length_diff_km` and `length_rel_diff = (sum_geom_len_km - proposed_l_km) / proposed_l_km`.
- Project-reported CSV SHA-256: `4b578e6bcf8ece5f6e1f88af1bd07526e69564f6ee30a0a8162bd23d2fbda98f`. Keep generated CSV ignored, preserve hash in tracked manifest.
- Queue P0 topology=6; P1 top-|km difference|=25; P2 top-|relative difference|=25; union 42 packages with 14 duplicate queue appearances. States: UP=34, MP=6, Bihar=2. Queue creation is **not equivalent** to case-level adjudication.
- Cohort grouping appears blank in reported summary. The `UP / 2020_B1 = 0/42` observation is **unverified** until cohort field completeness, join key, type, and grouping logic are checked. Do not claim absence of that cohort or compare it to prior cohort findings before resolution.

### Governance transition and explicit open gates
- Mark **register/queue generation** complete on user report; mark **source-level 42-case review** OPEN. The earlier evidence-review plan's case-disposition acceptance criterion has not yet been reported met.
- Next phase: `PEIARS-PMGSY-EVIDENCE-INTEGRATION-V1`, documented in `governance/PEIARS_PMGSY_EVIDENCE_INTEGRATION_V1.md`.
- Require stable package-to-case identity, source feature/geometry lineage, metric + rule provenance, all queue selection reasons, versioned observations, reviewer decisions and audit trail.
- Existing Option B v2/topology remain descriptive evidence tracks; IF closure unchanged (`CLOSED_RESEARCH_NOT_ADMITTED`), no IF v4, fraud claims, or production model inference.
- User reports untracked outputs `blinded_annotation_v1/`, `ml_experiment_protocol_v1.md`, `up_cohort_heterogeneity_report.md`; preserve and classify under archival/reproducibility policy, and do not add without inspecting for restricted keys or sensitive information.


## Addendum — 2026-11-23: reconciled remote and six-case P0 topology pilot

**Verified remote artifact:** `81c07d40edcaa8ec260ee0f58bbb6b479f7019ff` on `swapnaneel-24/mplad-anomaly-detection` contains `research/pmgsy_iii_investigation/outputs/peiars_evidence_integration_v1/PEIARS_PMGSY_P0_ADJUDICATION_V1.md`. User reports local Git history including `dd294052f20d9c46ace0457afe369796a8e3f3ad` was merged/pushed; this supersedes the earlier temporary 'missing remote commit' explanation. Earlier addenda remain as chronological records.

- 42-case integrated selection baseline: P0 topology 6, P1 top absolute km discrepancy 25, P2 top absolute relative discrepancy 25, 42 unique cases; 4,361 source P packages.
- Cohort lineage correction: register initially lacked `cohort_year_batch`; source-linked `ims_year` classifies UP 2020 as 25/42 priority cases (59.5%). **Do not equate year 2020 to `2020_B1` without a source-backed batch ID.**
- P0 six-case topology pilot committed and pushed: `PEIARS_PMGSY_001` UP MRL 241861 (exact geometry duplicate and 5,687.585 m maximum shared overlap); `002` MP MRL 234789 (23.333 m overlap); `003` MP MRL 252608 (1 invalid segment); `004` MP MRL 231294 (10.261 m overlap and 1 invalid segment); `005` MP MRL 234858 (17.363 m overlap); `006` MP MRL 234868 (2 invalid segments).
- All six end `REVIEWED / SUPPORTED_REVIEW_CANDIDATE`; none `CONFIRMED_SOURCE_DEFECT`. Evidence supports reproducible geometric flags, not external validation of a defect or allegations about construction quality, funds or fraud.
- P0 report records 42 original case-creation events + 12 appended transitions = 54 events and replay PASS; these outcomes were read from committed Markdown. The local JSONL and full export are not independently rerun in this governance update.
- Remaining 36 unique P1/P2 cases `PEIARS_PMGSY_007`–`042` are `QUEUED_AWAITING_SOURCE_ADJUDICATION / UNRESOLVED`; next authorized phase: `PEIARS-PMGSY-42-CASE-SOURCE-REVIEW-V1`.
- **Preservation:** closed IF v1–v3 research, Option B v2 freeze, historical audit labels, case-creation history and 12 P0 transition events must not be modified. After each 12-case batch append audit events, verify replay, and publish sanitized provenance-linked review summaries. The three pre-existing untracked files/directories remain outside this milestone until explicitly reviewed.

**Disposition:** P0 pilot complete; full 42-case source review open; no confirmed source defects introduced. No IF v4 or production anomaly/fraud scoring.


## Addendum — 2026-11-23: completed 42-case desk review, blocked external corroboration, engineering transition

**Verified connected-repository commits:** `c8aa5a1f7569e57c014f266f019aecb774849c31` (desk review summaries, gate reconciliation, manifest) and `314b804ea5fe6a3bdaf11a3949cda44233112d3a` (desk closure plus 12-case corroboration pilot artifacts). Preserve previous entries as chronological evidence, not the latest status.

- **Desk-review final:** 42 cases; 37 supported candidates, 5 unresolved (all UP: `030`, `034`, `037`, `040`, `042`), 0 confirmed source defects. The corrected screening-versus-disposition boundary is retained; zero proposed length means `UNDEFINED_ZERO_DENOMINATOR`, never an artificial relative-discrepancy trigger.
- **Event history:** user-generated 42 initial + 12 P0 + 72 P1/P2 + 36 corrective gate events = 162. Committed replay report records PASS and manifest hashes the gitignored local JSONL. Frozen desk baseline event head: `9caa9735fab13e88a47848a12532653bc4216548aa69cf80e4648fc5d646d5de` (as recorded in corroboration report); neither raw JSONL nor source data independently rerun in this update.
- **Independent corroboration:** 12/12 cases `VERIFICATION_BLOCKED` and `independent_of_canonical_gis=False`, due to absent independent PMGSY/OMMAS sanction/alignment documentation within local snapshot. Dispositions remain seven supported (six P0 plus case 007) and five unresolved; zero confirmed defects. These are unverified cases, **not** 12 disproved irregularities.
- **Source-quality boundary:** mapped-versus-proposed km and observed topology flags are reproducible GIS observations; no claim of field road quality, fraud, expenditure irregularity or source defect is established without appropriate independent evidence.
- **Project decision:** PMGSY desk-review research cycle closed with documented evidence limitation; IF remains `CLOSED_RESEARCH_NOT_ADMITTED`. External source verification may be reopened later if independent evidence is obtained. **Engineering track now active:** `PEIARS-CORE-CASE-MANAGEMENT-V1`, see `governance/PEIARS_CORE_CASE_MANAGEMENT_V1.md`. Implement local-first case management, independent provenance replay and verifiable case exports using frozen data; no new unsupervised model experiment.

**Retention policy:** keep full source/register/case/evidence/JSONL raw exports ignored as appropriate, but retain manifest and reproducible scripts in repository. Do not modify frozen desk baseline or reassign prior dispositions in place.


## Addendum — 2026-11-24: LOF feasibility v1 closed as research-only

**Verified research branch:** `research/pmgsy-lof-feasibility-v1` at `fc03519af02309732943ad238562c7c485d8a820` contains the seven frozen `PEIARS-PMGSY-LOF-FEASIBILITY-V1` artifacts under `research/pmgsy_iii_investigation/outputs/lof_feasibility_v1/`. This addendum records the experiment without modifying the frozen PMGSY desk-review baseline, Option B v2, IF v1–v3, or case dispositions.

- **Population/configuration:** 4,361 scored P packages (UP 2,556; MP 1,074; Bihar 731), state-stratified RobustScaler + LocalOutlierFactor, `novelty=False`, Euclidean `p=2`, `k={10,20,35,50}`. Arms: five structural features and a three-feature ablation dropping `n_segments` and `seg_len_concentration`. The committed report states no label tuning.
- **Data criticality:** `n_segments==1` for 3,553/4,361 (81.47%), IQR=0 and skew≈9.05. This makes RobustScaler's zero-IQR treatment and discrete segment-count jumps an explicit methodological limitation, not a resolved preprocessing detail.
- **Stability:** full five-feature top-5% Jaccard = 0.7951 for k20↔k35 and 0.7805 for k35↔k50; three-feature ablation k35↔k50 = 0.8798. k10 is materially less stable (full k10↔k50 = 0.4361; ablation = 0.4129).
- **Segmentation sensitivity:** full-vs-ablation top-5% Jaccard is 0.5643–0.5927. At k35, full-feature selection rate is 13.91% for two-segment packages vs 4.19% for one-segment packages; the ablation removes that spike. Therefore LOF is **not** treated as segmentation-independent.
- **Option B comparison:** top-5% LOF overlap with 1,135 Option B v2 non-baseline flags has Jaccard 0.0529–0.0603. This is evidence of low selection overlap only; it does not establish useful orthogonality or defect-detection validity.
- **42-case cross-check:** all 42 historical review cases matched the P population. Full-feature LOF top-5% contains 11–13 of them depending on k; the committed report correctly treats this as descriptive alignment because the register is queue-selected and non-random, not an unbiased validation sample.
- **Evidence boundary:** independent source-defect corroboration remains unavailable; LOF has no verified precision/recall or operational defect yield. It must not change the 37 supported / 5 unresolved / 0 confirmed desk-review dispositions.

**Two-gate closure:** Gate 1 `PASS_WITH_LIMITATIONS` (structural feasibility retained as a research result); Gate 2 `NOT_MET` (evidence validity / operational admission). Formal disposition: `LOF_FEASIBILITY_COMPLETED_RESEARCH_ONLY_NOT_ADMITTED`.

**Stop rule:** no further v1 neighborhood tuning, feature search, fitting to the 42-case labels, production anomaly ranking, fraud inference, or LOF+IF+Option-B composite score is authorized. Freeze `full_5feat__k35` and `ablation_no_seg_conc__k35` only as possible future research comparators. Any future human-in-the-loop comparison requires a new prospectively frozen protocol and genuinely independent evidence. IF remains `CLOSED_RESEARCH_NOT_ADMITTED`.

**Engineering direction:** return to the PEIARS workbench/core product track. LOF may be displayed in `06 Research` as a frozen exploratory result, clearly separated from evidence-backed case disposition and verification status.


## Addendum — 2026-11-24: React/FastAPI Prompt B data-workbench completion

**Verified workbench commit:** `09d16df35e7f6ea9ea6623ea88f9f668dd8a4013` on `feat/react-workbench-02-data`.

- The `02 Data` workbench now exposes the frozen local PMGSY snapshot and all 42 case-linked package records through explicit read-only workbench routes, while preserving the separate admitted-source semantics of `/api/v1/sources`.
- The previous React-only illustrative PMGSY package/snapshot constants were removed; the selected-record inspector now reads typed backend data and loads package detail on selection.
- Current displayed evidence state remains exactly 37 supported review candidates, 5 unresolved, 0 confirmed source defects, with 12 verification-blocked cases.
- Relative length remains undefined when proposed length is zero; `UNDEFINED_ZERO_DENOMINATOR` is preserved.
- Screening, disposition, verification and provenance remain distinct concepts. No review decision is mutated from `02 Data`.
- IF and LOF remain research-only closures and are not exposed as operational PMGSY case scores. No composite scoring was introduced.
- Targeted backend tests report 55 passing tests and the frontend TypeScript/Vite build passes.
- Frozen PMGSY source/research artifacts were not modified by this implementation.

**Engineering interpretation:** this is a presentation/data-access milestone, not a new evidentiary finding. The authoritative 42-case evidence outcomes and external-corroboration limitation are unchanged.


## Addendum — 2026-11-24: Prompt C investigation/provenance workflow completion

**Verified workbench commit:** `206ad6efee52b637d90bfdaf129b51a5b76ff548` on `feat/react-workbench-02-data`.

- `04 Investigations` now exposes all 42 PMGSY cases through typed React/FastAPI contracts and keeps screening reasons, disposition, verification status and provenance as separate concepts.
- The history API presents the global frozen 162-event baseline and separate case-scoped application stream explicitly; frozen head remains `9caa9735fab13e88a47848a12532653bc4216548aa69cf80e4648fc5d646d5de`.
- Reviewer notes append only to the application event stream. Frozen history is not rewritten.
- Writes fail closed for stale app-stream state, chain-integrity failure, unknown cases and invalid note/disposition requests.
- Promotion to `CONFIRMED_SOURCE_DEFECT` is rejected because independently verified corroboration is not present.
- The evidence state remains unchanged: 37 supported review candidates, 5 unresolved, 0 confirmed source defects, 12 verification-blocked.
- Targeted backend tests report 59 passing tests; frontend TypeScript/Vite build passes.
- IF and LOF remain research-only and are excluded from investigation filtering, scoring and adjudication.

**Engineering interpretation:** Prompt C advances auditable case-management capability but introduces no new source-level finding. Hash-chain continuity validates recorded history integrity under the implemented scheme; it does not establish factual correctness of the underlying evidence.
