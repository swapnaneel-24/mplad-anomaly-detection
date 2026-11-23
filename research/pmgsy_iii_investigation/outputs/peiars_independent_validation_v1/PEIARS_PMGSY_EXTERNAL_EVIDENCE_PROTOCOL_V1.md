# PEIARS ? External Evidence Corroboration Protocol v1

- **Effective At (UTC):** 2026-11-23T10:58:24.339250+00:00
- **Source Hierarchy (Most to Least Authoritative for Package/Alignment Verification):**
  1. Authoritative PMGSY / OMMAS sanction records, approved alignment drawings, or official survey deliverables.
  2. Independently sourced authoritative road geometry / gazetteer / engineering drawings outside `pmgsy3_3state_v1`.
  3. High-resolution satellite/imagery plausibility checks (useful for plausibility context only; cannot establish approved package length or defect status on their own).
- **Independence Test:** Evidence is `INDEPENDENT_OF_CANONICAL_GIS` only when derived outside `pmgsy3_3state_v1/segments.parquet` and `packages_p_scored_option_b_v2.csv`; otherwise it is `DERIVED_FROM_CANONICAL_SNAPSHOT`.
- **Orthogonal Verification Status (Process State ? Not a Defect Label):**
  - `NOT_ATTEMPTED` | `SOURCE_REQUESTED` | `INDEPENDENT_EVIDENCE_OBTAINED` | `VERIFICATION_BLOCKED`
- **Existing Four Dispositions (Unchanged):**
  - `CONFIRMED_SOURCE_DEFECT` | `SUPPORTED_REVIEW_CANDIDATE` | `BENIGN_EXPLAINED` | `UNRESOLVED`
- **Event Rule:** All new corroboration evidence or disposition changes must append a new hash-chained event to `PEIARS_PMGSY_DECISION_HISTORY.jsonl` without altering prior events.