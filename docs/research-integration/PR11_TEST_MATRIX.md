# PR-11 Test Matrix — Phase 5B Figure Gallery and Traceability

**Branch:** `pr-11-phase5b-gallery` | **Date:** 2026-11-15

## 1. Suite Summary
- `backend/tests/test_phase5b_adapter.py`: **46 passed** across 16 classes (Windows 11, Python 3.12, materialized DVC payloads).
- Regression: `test_phase5a_adapter.py` + `test_openapi.py` (**56 passed**); Frontend Vitest (**134 passed**, 24 files); `typecheck`, `lint`, `openapi:check`, `build`, and Playwright E2E (**21 passed**) all green.

## 2. Coverage by Class
- `TestCatalogIdentity` (5), `TestThreeWayConsistency` (2), `TestManifestTrust` (3), `TestMetadataTampering` (3), `TestDvcAbsence` (2), `TestIndependentAvailability` (1), `TestDigestVerification` (2), `TestPngFormatValidation` (6), `TestPathSecurity` (4), `TestCacheMutationRecovery` (1), `TestPublicationGate` (5), `TestApiSecurity` (2), `TestTraceability` (5), `TestOpenApi` (2), `TestFrozenEvidence` (1: `28/28`), `TestTrustedLocalRealDvcPayloads` (2: verifies all 8 real PNGs + catalog CSV locally; skips cleanly in DVC-absent CI).

## 3. Isolation & Known Gaps
- Tamper/cache tests use `_isolated_figure_tree(tmp_path)` patching `REPO_ROOT` and `PHASE5_FIGURES_DIR`; real files are never mutated.
- Deferred: filesystem-level gate enforcement (container deploy scope), browser `<img>` render with gate enabled (manual trusted-lane check), and explicit negative tests for the 26 historical PNGs (excluded by integer-only `figure_no` routing).