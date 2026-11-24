# PEIARS — Core Case Management v1 Engineering Specification

**Status:** AUTHORIZED FOR IMPLEMENTATION; not yet delivered  
**Milestone:** `PEIARS-CORE-CASE-MANAGEMENT-V1`  
**Recorded:** 2026-11-23  
**Research baseline:** PMGSY 42-case desk review at `c8aa5a1f7569e57c014f266f019aecb774849c31` (37 supported review candidates, 5 unresolved, 0 confirmed source defects; 162 frozen events); 12-case blocked external verification at `314b804ea5fe6a3bdaf11a3949cda44233112d3a`.

## Executive directive

Stop initiating new desk-only anomaly experiments. Build a working local-first application that can ingest the frozen 42-case PMGSY package, reconstruct the immutable event history, display evidence and limitations, accept reviewer decisions through append-only events, and export a hash-verifiable case dossier. The 12 blocked verification requests are NOT negative validation results and remain visible without changing case disposition.

## Fastest safe implementation order

### Phase A — Core backend and import
- Implement deterministic snapshot importer for existing `PEIARS_PMGSY_42_CASES.json`, evidence records, review states, decision-history JSONL, desk closure and corroboration manifests.
- Read-only baseline ingestion; materialize a local SQLite database for cases, package/source identifiers, evidence links, multiple selection reasons, review workflow, verification status, event history and artifact hashes.
- Key by immutable case ID/package UID; preserve user-provided case IDs `PEIARS_PMGSY_001`–`042`, rather than replacing them with a new synthetic ID.
- Before accepting imports, verify SHA-256 against tracked manifests, reject missing/changed required artifacts, validate unique IDs and all 42 state reconstructions. Do not pretend hashes prove independent evidence correctness.
- Represent the 12 pilot cases as verification-blocked, not as confirmed benign/defective.

### Phase B — Event replay and write path
- Create pure replay validator verifying original 162-event genesis-to-head chain, ordering, event integrity, case references and reconstructed dispositions; reproduce the frozen head hash `9caa9735fab13e88a47848a12532653bc4216548aa69cf80e4648fc5d646d5de`.
- Treat the frozen JSONL as immutable; create a **separate new application event stream** linked to the frozen head (include parent snapshot/hash). No edits, deletions or replacements of frozen historical events.
- Document canonical JSON serialization/hashing from original generator; do NOT claim replay equivalence if original chain format is unknown.
- Review/status changes must include actor, UTC time, evidence references, previous/new state, rationale, and validity constraints; reject unauthorized disposition promotion, e.g. `CONFIRMED_SOURCE_DEFECT` with no independent evidence.

### Phase C — Minimum review interface
- 42-case table with filter by state, queues P0/P1/P2, disposition, `ims_year`, verification status. Show counts 37 supported, 5 unresolved, 0 confirmed and the 12 blocked requests.
- Case detail: source package UID/MRL_ID, proposed/mapped km, signed and relative difference with undefined-zero denominator status, topology flags, source lineage, selection reasons, evidence references, independent verification state, reviewer notes, chronological immutable events.
- One explicit 'record review' action that appends an event, never silently auto-classifies cases from screening triggers.
- Explicit banners on case exports: geometry discrepancy is not a confirmed source defect, field-road condition, fraud or expenditure finding.

### Phase D — Exports and tests
- Provide sanitized single-case dossier export (JSON and/or Markdown/PDF where appropriate) with case ID, manifest/source hashes, event-chain head, evidence table, decision trail, reviewer limitation and unresolved/blocked rationale.
- End-to-end test imports 42 cases, checks 162-event replay, saves one test note into the new stream, replays both streams, verifies unchanged frozen hashes, exports and re-verifies one dossier.
- Test negative cases: corrupt hash, missing case/evidence, duplicate event, out-of-order events, invalid transition, unsupported promotion to confirmed defect, zero denominator, unavailable external source.
- Capture test output, schema/version, command and dev environment in `PEIARS_CORE_V1_VALIDATION_REPORT.md`.

## Suggested implementation (non-binding)
Use Python + SQLite + a minimal FastAPI backend and a small frontend (or Streamlit for rapid local demo). Select ONE stack and avoid architecture churn. No cloud hosting, external login, model API or geospatial heavy rendering is necessary for v1. If a map is implemented later, ground it in source geometry and label CRS accurately.

## Git / privacy policy
Track application code, tests, schema/migrations, sanitized public docs, provenance manifests and minimal non-sensitive fixtures. Keep existing full raw sources, case/evidence JSON, detailed annotation and JSONL files ignored pending publication approval. Never commit secrets, raw external records without permissions or unblinding keys. Preserve frozen IF v1–v3 and Option B v2 unchanged.

## Acceptance criteria
1. Deterministic 42-case import with exact case IDs and preserved 37/5/0 outcomes.
2. Independent genesis-to-head replay of 162 frozen events; correct frozen head; detailed fail-closed errors.
3. Correct 12/12 `VERIFICATION_BLOCKED` statuses with independent evidence = false.
4. Working case-list, case-detail and reviewer-event workflow in an actual local application.
5. Frozen stream unchanged after app writes; new append-only stream fully replays.
6. One case dossier export verifies provenance and does not overstate evidence.
7. Automated smoke/negative tests pass and resulting validation report is committed.

**Gate result required for completion:** `PEIARS_CORE_V1_ENGINEERING_PASS` only after the application and replay tests are run, not after drafting this specification.

## Later phases (not prerequisites)
- Evidence source acquisition/connectors for PMGSY/OMMAS if authorized and accessible, with explicit independence and licensing checks.
- Reviewer assignment, two-reviewer adjudication, access control and redaction.
- More data streams only after case/event/evidence abstractions pass the local PMGSY demonstration.

## Prompt D Engineering Addendum (2026-11-24)
- Added case dossier export (JSON/Markdown/manifest) and independent dossier verification.
- Gate decision: `PEIARS_CORE_V1_ENGINEERING_PASS`.
