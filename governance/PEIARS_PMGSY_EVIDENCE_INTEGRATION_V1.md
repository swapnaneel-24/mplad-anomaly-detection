# PEIARS — PMGSY-III Evidence & Provenance Integration v1

**Status:** APPROVED DESIGN / IMPLEMENTATION PENDING  
**Workstream:** `PEIARS-PMGSY-EVIDENCE-INTEGRATION-V1`  
**Source baseline:** `pmgsy3_3state_v1`; Option B v2 and topology tracks  
**Model policy:** Isolation Forest `CLOSED_RESEARCH_NOT_ADMITTED`, no v4 or production fraud/anomaly classification.

## 1. Trigger and limits
Project owner reports `dd29405` committed register generator, manifest, summary and priority review report. The connected governance repository does **not** resolve `dd29405`, so the repository remote/full SHA and artifact paths require reconciliation. User-reported local register: 4,361 P packages, SHA-256 `4b578e6bcf8ece5f6e1f88af1bd07526e69564f6ee30a0a8162bd23d2fbda98f`. Queues: P0=6 topology, P1=25 largest absolute km discrepancies, P2=25 largest absolute relative discrepancies, union=42 cases (UP 34, MP 6, Bihar 2). These are **queue selections**, not adjudicated outcomes.

## 2. Pre-integration hard gates
**G0 — Source/commit integrity:** Verify `git remote -v`, full `git rev-parse HEAD`, `git show --stat dd29405`; review exact manifest, script and summary on canonical remote. Verify CSV hash on disk and upstream canonical-source hashes. Do not edit frozen historical output.
**G1 — Cohort correctness:** Inspect source `cohort_year_batch` and downstream join/grouping. Compute non-null, blank/whitespace, unmapped, and distinct cohort counts in whole 4,361-row register and 42-case union. Check `UP/2020_B1` from source-key lookup; do not accept reported `0/42` until checked. Preserve failure as a lineage issue if unresolved.
**G2 — Queue fidelity:** Compare P0/P1/P2 membership to source register sorted by absolute discrepancy (with stable package UID tie-break), retaining sign, original values, and every reason. Assert 6/25/25/42, 42 unique UIDs, no non-P.

## 3. Minimum PEIARS case model
Use stable `case_id = PMGSY3:<package_uid>` (namespace and escaping defined by implementation), with separate mutable `case_status` and append-only `case_event_id`. Define:
- **Entity:** `dataset_id`, `package_uid`, `source_state_key`, `MRL_ID`, `cohort_year_batch`, source feature IDs and canonical segment IDs.
- **Evidence:** `evidence_id`, source path/URI, source SHA-256, geometry CRS/units, calculation script/commit/config hash, `sum_geom_len_km`, `proposed_l_km`, signed `length_diff_km`, `length_rel_diff`, Option B tier and topology flags, exact rule/version.
- **Selection:** multiple `queue_reason` entries with `P0/P1/P2`, rank, snapshot ID and deterministic tie-break; never collapse distinct reasons into a single priority.
- **Review:** `review_id`, reviewer role, review timestamp, interpretation, specific source citation, benign alternative hypothesis, evidence domain, confidence, disposition and independent-verification status.
- **Audit event:** `event_id`, actor, event type, UTC time, previous-state hash, new-state hash, reason and source artifact reference. Corrections append an event; do not overwrite frozen annotations.

## 4. Case workflow
`QUEUED -> EVIDENCE_COLLECTING -> READY_FOR_REVIEW -> REVIEWED`, with `BLOCKED_MISSING_EVIDENCE` and `REOPENED` side states. Evidence disposition is distinct from workflow status:
- `CONFIRMED_SOURCE_DEFECT` requires independently corroborated authoritative evidence or verified source invariant.
- `SUPPORTED_REVIEW_CANDIDATE` requires specific reproducible discrepancy with plausible unresolved alternatives.
- `BENIGN_EXPLAINED` requires affirmative explanation.
- `UNRESOLVED` records conflicting or insufficient evidence.
Do not infer dispositions automatically from R, segment count, sinuosity, topology flag or queue membership. Mark `SINGLE_REVIEWER_LIMITATION` whenever applicable. Keep field infrastructure claims outside evidence scope without independent verification.

## 5. Implementation outputs
1. `validate_pmgsy_evidence_lineage.py`: G0/G1/G2 checks and failure report; no silent imputation of cohort.
2. `export_pmgsy_cases_v1.py`: deterministic 42-case export with package/segment source refs, evidence references and all queue reasons.
3. `validate_pmgsy_cases_v1.py`: referential integrity, 42 unique cases, queue counts, evidence hash/reference coverage, no secret review keys.
4. `PMGSY_COHORT_LINEAGE_CHECK_V1.md`: blanks/missingness, source-versus-derived cohort join, UP 2020_B1 finding and resolution.
5. `PMGSY_CASE_EXPORT_MANIFEST_V1.json`: hash inputs, generator revision, output hash, schema, 42-case count, queue membership and timestamp.
6. `PMGSY_CASE_REVIEW_STATUS_V1.md`: per-case workflow tally and **only evidence-supported** adjudication counts; distinguish not-yet-reviewed.

## 6. Public Git/retention policy
Keep full 4,361-row generated CSV ignored; store its SHA-256 and deterministic generation command in tracked manifest. Track schema, validators, scripts, source lineage check and sanitized aggregate reports. Store detailed case exports or reviewer evidence attachments according to licensing/access rules; do not commit restricted unblinding keys. Review existing untracked `blinded_annotation_v1/`, `ml_experiment_protocol_v1.md`, `up_cohort_heterogeneity_report.md` before choosing archive or ignore, avoiding alteration of historical audit freezes.

## 7. Completion gates
- G0/G1/G2 pass with saved validation evidence and accurate reported state/cohort counts.
- 42 unique case IDs, 6 P0 and 25 each P1/P2 selections reconstructed with stable reason/rank; package-to-feature provenance complete.
- An append-only case-event log and reviewer outcome schema are implemented and tested, including negative and unresolved cases.
- Cohort blank issue explicitly resolved or blocked; no silent assumption that UP 2020_B1 is absent.
- Final report distinguishes **integration completed** from **source-level adjudication completed**. A reviewed case is not automatically a confirmed defect.

**No change to closed IF v1–v3 experiments, frozen Option B v2 thresholds, or the evidence standard.**


## Execution status addendum — 2026-11-23: P0 pilot completed; P1/P2 next

**Historical planning sections above are retained for provenance; this addendum supersedes their outdated pending status.** The local-to-remote reconciliation was resolved and the P0 report was verified on connected GitHub at commit `81c07d40edcaa8ec260ee0f58bbb6b479f7019ff`, `research/pmgsy_iii_investigation/outputs/peiars_evidence_integration_v1/PEIARS_PMGSY_P0_ADJUDICATION_V1.md`.

- **Integration export:** 42 unique cases, 6 P0 topology and 36 remaining unique P1/P2 candidates (P1 and P2 overlap; preserve all reason memberships). The project owner reports 42 creation events plus 12 P0 transitions, 54 total; the committed report records replay PASS. Underlying local JSONL was not independently replayed as part of this documentation update.
- **P0 reviewed:** `PEIARS_PMGSY_001`–`006`, all 6 `REVIEWED / SUPPORTED_REVIEW_CANDIDATE`, **0 confirmed source defects**. Observations: exact geometry duplication and long overlap in UP MRL 241861; overlaps and invalid segment geometry across five MP cases. Flags represent reproduced geometry concerns, not authoritative confirmation of defective source records or built roads.
- **Remaining:** `PEIARS_PMGSY_007`–`042`: `QUEUED_AWAITING_SOURCE_ADJUDICATION / UNRESOLVED` at the P0 freeze. Their 36 reviews are the next approved phase; avoid treating queue assignment as a review outcome.
- **Cohort resolution:** Previously blank `cohort_year_batch` stems from absent column in evidence register. Local join of canonical `ims_year` found UP/2020 = 25 of 42 priority packages, not the formerly reported 0 of 42. Year alone does **not** establish batch `2020_B1`; keep batch unknown without source evidence.
- **Research policy unchanged:** Option B v2 and topology evidence remain primary descriptive tracks; IF remains `CLOSED_RESEARCH_NOT_ADMITTED`.

### P1/P2 execution and admission checks
1. Freeze/verify current 54-event chain, 42-case export hashes, 6 reviewed and 36 queued states, and the case-to-package/source-feature references **before** new events.
2. Review 36 unique cases in three batches of 12 (IDs 007–018, 019–030, 031–042 for execution convenience only). Preserve original P1/P2 ranks, signs and overlapping selection reasons; neither case-ID order nor review batch is evidence priority.
3. For each package, recompute signed km and relative discrepancy using the documented denominator, inspect constituent segments, geometry completeness, CRS/units, expected source conventions and authoritative source evidence where accessible. Record both alternatives and uncertainties.
4. Only independently corroborated source defects can be marked `CONFIRMED_SOURCE_DEFECT`; reproducible but uncertain cases may be `SUPPORTED_REVIEW_CANDIDATE`; require positive explanation for `BENIGN_EXPLAINED`; otherwise `UNRESOLVED`. Review status and evidence disposition are separate fields.
5. Append transition records using the existing validated schema to the JSONL chain, preserving all previous 54 events. Replay and verify count, hash links, state transitions, no case-ID duplication and prior P0 states after each batch. Do not presume a fixed number of events per case; follow the observed workflow and document it.
6. Produce `PEIARS_PMGSY_P1P2_ADJUDICATION_V1.md`, a complete 42-case disposition summary, replay-validation summary and updated export/decision-history SHA-256 manifest after all reviews. Track sanitized reports and generator code; protect raw case-level exports and any access-restricted evidence.
7. If independent source corroboration remains absent, record that limitation plainly. **Do not classify a discrepancy as confirmed merely to finish the milestone.**

**Next authorized milestone:** `PEIARS-PMGSY-42-CASE-SOURCE-REVIEW-V1`. Implementation/execution pending; successful P0 pilot does not close the entire 42-case adjudication gate.
