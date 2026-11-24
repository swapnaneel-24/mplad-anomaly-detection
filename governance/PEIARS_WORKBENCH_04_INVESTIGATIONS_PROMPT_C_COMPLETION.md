# PEIARS — Workbench 04 Investigations Prompt C Completion

**Recorded:** 2026-11-24  
**Branch:** `feat/react-workbench-02-data`  
**Implementation commit:** `206ad6efee52b637d90bfdaf129b51a5b76ff548`  
**Status:** COMPLETE; stop before Prompt D

## Scope

Prompt C implemented the evidence-backed `04 Investigations` workflow and provenance/event-history presentation over the frozen PMGSY 42-case baseline.

## Delivered

- `GET /api/v1/workbench/investigations`
- `GET /api/v1/workbench/investigations/{case_id}`
- `GET /api/v1/workbench/investigations/{case_id}/history`
- `POST /api/v1/workbench/investigations/{case_id}/notes`
- React investigation workbench and case-detail presentation.
- Explicit separation of frozen baseline events and append-only application events.
- Stale-head/count conflict protection and fail-closed integrity handling.
- Server-side rejection of unsupported `CONFIRMED_SOURCE_DEFECT` promotion.
- Preservation of zero-denominator semantics and explicit verification blockers.

## Frozen evidence state

- 42 cases.
- 37 `SUPPORTED_REVIEW_CANDIDATE`.
- 5 `UNRESOLVED`.
- 0 `CONFIRMED_SOURCE_DEFECT`.
- 12 `VERIFICATION_BLOCKED`.
- 162 frozen baseline events.
- Frozen head: `9caa9735fab13e88a47848a12532653bc4216548aa69cf80e4648fc5d646d5de`.

No case disposition or independent-verification result changed as a consequence of Prompt C.

## Event-stream semantics

`FROZEN_BASELINE` is immutable.

`APPENDED_APP_EVENT` is a separate append-only stream linked to the frozen baseline/current app head.

A successful hash-chain replay demonstrates continuity and integrity of the recorded stream under the implemented hashing scheme. It does not prove the factual truth of the underlying road/evidence observations.

## Validation

Reported Prompt C validation:

- Targeted backend tests: 59 passed.
- Frontend `npm run build`: passed.
- Reviewer-note append demonstrated.
- Frozen baseline remained byte/hash unchanged after app writes.
- Empty note rejected.
- Unknown case write rejected.
- Stale app state rejected with conflict.
- Unsupported confirmed-defect promotion rejected.
- Corrupted provenance/event chain rejects or disables writes.
- No frozen research artifact modified.

## Research boundary

Isolation Forest remains `CLOSED_RESEARCH_NOT_ADMITTED`.

LOF remains `LOF_FEASIBILITY_COMPLETED_RESEARCH_ONLY_NOT_ADMITTED`.

Neither model participates in `04 Investigations` scoring, filtering, disposition or automatic case transitions.

A future dedicated analytical/research milestone must still compare PMGSY Isolation Forest and LOF implementations with appropriate visualizations and methodological caveats under `03 Analysis` and/or `06 Research`. That work is separate from evidence-backed investigation state.

## Handoff

Prompt C is closed.

The next engineering milestone is Prompt D, focused on:

- dossier/export verification;
- end-to-end workflow validation;
- negative-path and integrity testing;
- reproducibility/validation report;
- local release-readiness checks.

Do not begin Prompt E or deployment automatically. Do not reopen anomaly-model tuning as part of Prompt D.
