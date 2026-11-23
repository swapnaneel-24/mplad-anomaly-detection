# PMGSY-III Evidence Register Verification & Priority Review — Plan v1

**Status:** APPROVED FOR EXECUTION; not yet executed in this record.  
**Milestone:** `PEIARS-PMGSY-EVIDENCE-REVIEW-V1`  
**Baseline:** `pmgsy3_3state_v1`, frozen Option B v2, independent topology evidence.  
**Research boundary:** IF line closed as `CLOSED_RESEARCH_NOT_ADMITTED`; no new ML experiment authorized.

## Purpose and scope
Verify the locally generated `PMGSY_EVIDENCE_REGISTER_V2.csv` (reported 4,361 P packages), extract a bounded review queue, and produce source-traceable case assessments. The CSV has not been inspected as part of this governance-plan creation.

## Phase 1 — Integrity checks (hard stop)
1. Recompute SHA-256 for register, canonical packages and segments, frozen Option B v2 outputs, and the generator script; record paths and repository revision.
2. Assert exactly 4,361 P-package records and uniqueness of the **composite source-state/package identity**; never assume bare `MRL_ID` is globally unique.
3. Verify non-P exclusion; source feature lineage; geometry aggregation; non-null proposed lengths; zero/invalid geometry handling; units and CRS.
4. Explicitly document `length_diff_km` sign (e.g., geometry minus proposed) and `length_rel_diff` denominator (e.g., divided by proposed). Recompute and compare to stored columns with declared numeric tolerances.
5. Reconcile Option B tiers to frozen counts: topology 6, high state-R deviation 919, subthreshold shift 210, baseline within range 3,226; preserve `R<0.5` exploratory flag 135.
6. Record state/year/batch missingness, duplication, and source geometry references. Any failure blocks review-queue release until explained.

## Phase 2 — Non-exclusive queue generation
- **P0:** all 6 topology-evidence packages, with constituent segments and specific duplicate/overlap/zero-length/invalid flags.
- **P1:** top 25 by `abs(length_diff_km)`, retaining sign and both mapped/proposed lengths.
- **P2:** top 25 by `abs(length_rel_diff)`, retaining sign, denominator and both lengths.
- Use deterministic sort and tie-break by source-state/package identity. Merge duplicate package keys, preserving **all** reasons and queue ranks. Maximum 56 distinct packages; fewer if queues overlap.
- Report state, year/batch and segment-count composition; explicitly check concentration in UP 2020 Batch 1.
- No queue entry is automatically a verified defect.

## Phase 3 — Source-level case review
For each selected package record: package key, source feature IDs, geometry/CRS reference, proposed and recomputed mapped length, difference metrics, topology observations, state/year/batch, Option B tier, alternative benign explanations, reviewer, confidence, evidence reference, review date, and disposition.

Allowed dispositions:
- `CONFIRMED_SOURCE_DEFECT`: directly substantiated against independent authoritative source evidence or verified source invariant; identify precise defect and correction rationale.
- `SUPPORTED_REVIEW_CANDIDATE`: reproducible concern with unresolved alternative explanation.
- `BENIGN_EXPLAINED`: affirmative evidence supports legitimate geometry or source convention.
- `UNRESOLVED`: insufficient or conflicting evidence.

Recomputing canonical geometry alone does not establish external road alignment or fraud. Maintain original observations and subsequent adjudication changes as separate immutable records. If a second reviewer is unavailable, disclose single-reviewer limitation.

## Phase 4 — Outputs and Git policy
Track:
- deterministic generator/validator/queue scripts;
- `PMGSY_EVIDENCE_REGISTER_V2_MANIFEST.json` (SHA-256, schema, row count, source and script hashes, generation command, revision, policy version);
- `PMGSY_EVIDENCE_REGISTER_V2_SUMMARY.md` (validation results and cohort counts);
- `PMGSY_PRIORITY_REVIEW_V1.md` (queue construction, aggregate findings, limitations, no unsupported defect claims).

Keep the complete generated `PMGSY_EVIDENCE_REGISTER_V2.csv` ignored unless separately authorized for publication. Store any detailed case-level review exports with appropriate access controls; a sanitized summary may be tracked. Do not overwrite IF v1–v3 freezes or Option B v2 artifacts.

## Acceptance criteria
- 4,361 unique composite-key P packages; reconciled tier counts and verified length calculations.
- All six topology cases and both top-25 discrepancy queues included, with provenance and deduplicated reasons.
- Every reviewed case has an evidence-linked disposition, or an explicit unresolved status.
- Manifest hashes, generation command and reproducibility checks documented.
- No production anomaly, infrastructure fraud or confirmed-defect claims without independent support.

## Explicit non-goals
No IF v4, LOF replacement, weighted IF/R score, threshold retuning, model admission or production detector deployment. This milestone advances evidence review and provenance integration only.


## Status addendum — register validation versus case adjudication (2026-11-23)

**Reported partial completion:** The project owner reports commit `dd29405` containing generator, manifest, validation summary, and P0/P1/P2 priority report. The connected repository does not resolve that SHA; synchronize the authoritative remote and full commit ID before closing repository provenance checks.

- Reported integrity: 4,361 P records, unique `package_uid`, zero nulls and exact recomputed signed/relative discrepancy arithmetic; CSV SHA-256 `4b578e6bcf8ece5f6e1f88af1bd07526e69564f6ee30a0a8162bd23d2fbda98f`.
- Reported queue creation: 6 P0, 25 P1, 25 P2, 42 unique package identities, all selection reasons retained; review distributions UP 34, MP 6, Bihar 2.
- **Closed on report:** Phase 1 arithmetic and identity checks, Phase 2 queue generation (pending independent source file/manifest read).
- **OPEN:** Cohort provenance check because the summary displays blank cohort grouping; independently recompute UP `2020_B1` membership after confirming nonmissing source fields and joins.
- **OPEN:** Phase 3 source-level case adjudication. Queue inclusion is not a verified defect or a completed review.
- **OPEN:** Integration acceptance tests, case audit trail and Phase 4 outcome report. See `PEIARS_PMGSY_EVIDENCE_INTEGRATION_V1.md`.
- **Data policy:** Continue ignoring the complete generated CSV; version scripts, manifests and sanitized aggregate reports. Do not indiscriminately track old untracked annotation/research artifacts without reviewing their contents and restricted-key exposure.
