# PEIARS Core v1 Validation Report (Prompt D)

- **Milestone:** Prompt D ? Dossier Export Verification + End-to-End Validation + Release Readiness
- **Base Commit:** `206ad6efee52b637d90bfdaf129b51a5b76ff548` (`feat/react-workbench-02-data`)
- **Date:** 2026-11-24
- **Environment:** Windows, Python 3.13.13 (`backend\.venv\Scripts\pytest.exe`), React + TypeScript + Vite (`npm run build`)

## Acceptance Criteria Evaluation

1. Deterministic 42-case import: **PASS**
2. Exact case IDs (`PEIARS_PMGSY_001` through `PEIARS_PMGSY_042`): **PASS**
3. `37 / 5 / 0` disposition preservation (`SUPPORTED_REVIEW_CANDIDATE` / `UNRESOLVED` / `CONFIRMED_SOURCE_DEFECT`): **PASS**
4. `12` `VERIFICATION_BLOCKED` preserved with explicit blocker reason: **PASS**
5. `162`-event frozen replay: **PASS**
6. Frozen head reproduced (`9caa9735fab13e88a47848a12532653bc4216548aa69cf80e4648fc5d646d5de`): **PASS**
7. Working case-list/detail (`02 Data` + `04 Investigations`): **PASS**
8. Reviewer app event append (`POST /api/v1/workbench/investigations/{case_id}/notes`): **PASS**
9. Frozen stream unchanged after writes: **PASS**
10. App stream replayable: **PASS**
11. Provenance-verifiable dossier (`JSON` + `Markdown` + sidecar manifest with SHA-256 verification): **PASS**
12. Automated smoke/e2e tests (`test_workbench_dossier.py`, `test_workbench_investigations.py`, `test_workbench_pmgsy.py`, `test_source_registry.py`, `test_frozen_isolation.py`): **PASS**
13. Automated negative tests (20 negative/tamper/integrity scenarios): **PASS**
14. Validation report committed: **PASS**

## Known Limitations & Research Boundaries

- Hash-chain integrity verifies recorded event continuity, not the correctness of underlying evidence.
- Isolation Forest (`CLOSED_RESEARCH_NOT_ADMITTED`) and Local Outlier Factor (`LOF_FEASIBILITY_COMPLETED_RESEARCH_ONLY_NOT_ADMITTED`) remain excluded from case adjudication; IF-vs-LOF comparative analysis and visualizations belong to a separate research milestone under `03 Analysis` / `06 Research`.
- Local release-readiness only; no cloud deployment performed.

## Gate Decision

**PEIARS_CORE_V1_ENGINEERING_PASS**
