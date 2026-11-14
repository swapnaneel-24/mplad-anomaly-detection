# PR-09 Delivery Report — Canonical Ten-Run IF/LOF Benchmark Integration

**PR:** PR-09 — Canonical Ten-Run IF/LOF Benchmark Integration
**Branch:** `pr-09-canonical-benchmark`
**Starting commit:** `0a23577dc52839ff2ea54cdc3fcbc32e35523fd3` (verified `main` baseline; the branch was cut from this SHA)
**Ending commit:** see `git log -1` on this branch (this document is committed as part of the PR)
**Milestone:** M2 — Verified Stream A research integration (stories M2-01, M2-02, with narrowly necessary M2-04 integrity handling)

---

## 1. Source admission decision (per capability)

Recorded in full in `PR09_SOURCE_ADMISSION.md`. Summary:

| Capability | Decision |
|---|---|
| Configuration catalog (ten runs, parameters, dataset scope) | **ADMITTED** — frozen Git-tracked sources, verified against `ci/frozen_research_manifest.json` and the Phase 4 commit manifest; run↔parameter mapping corroborated by two independent verified sources. |
| Saved Phase 4 metrics (`phase4_metrics.csv`) | **PARTIALLY ADMITTED** — schema, identity and checksums pinned by Git-tracked metadata + `.dvc` pointer; runtime serving conditional on payload presence (absent here). |
| Row-level lookup (`phase4_evaluation_dataset.csv`) | **PARTIALLY ADMITTED** — same conditions. |
| Phase 3 metrics, FULL_* companion, CORRECTED variant | **NOT ADMITTED** for this PR (different population / superseded / out of scope). |
| Pickle payloads | **BLOCKED** — pickle deserialization prohibited in the request process (arbitrary-code risk); no capability required them. |

A key evidence finding: the Phase 4 commit manifest was produced on
Windows (CRLF); the repository stores LF-normalized bytes. Verification
reconstructs the CRLF form (LF→CRLF) before hashing, which reproduces the
recorded SHA-256 and size exactly (`phase4_run_metadata.json`: recorded
`b17f40635e73cbc1…`, 3,199 bytes). Layer B MD5 checks accept the raw or
CRLF-reconstructed form, since DVC materialization ending is not assumed.

## 2. Exact run identity and field mapping

Ten canonical runs, parameters extracted verbatim from the frozen
`src/mplad/common/config.py` (AST only, never executed), mapping
corroborated by the Phase 3 run-metadata CSV (DVC pointer
`c4bcb2a86e13419ed83f9fd6af46c083`; byte-identical copy verified against
both the pointer MD5 and the input SHA-256 recorded in the Git-tracked
Phase 4 provenance):

- IF_001 `n_estimators=100, max_samples=256, random_state=42`
- IF_002 `n_estimators=200, max_samples=256, random_state=42`
- IF_003 `n_estimators=100, max_samples=0.05, random_state=42`
- IF_004 `n_estimators=100, max_samples=256, random_state=43`
- IF_005 `n_estimators=100, max_samples=256, random_state=44`
- LOF_001 `n_neighbors=5, metric=euclidean`
- LOF_002 `n_neighbors=15, metric=euclidean`
- LOF_003 `n_neighbors=30, metric=euclidean`
- LOF_004 `n_neighbors=50, metric=euclidean`
- LOF_005 `n_neighbors=30, metric=manhattan`

Field mapping: metrics CSV → frozen `METRICS_TABLE_COLUMNS` (23 columns);
evaluation CSV → frozen `EVALUATION_DATASET_COLUMNS`
(`run_id, row_id, Class, native_score, anomaly_score, flag`); native score
(lower = more anomalous) kept distinct from saved `anomaly_score`
(−native, higher = more anomalous); ground-truth `Class` kept distinct
from detector `flag`; flags are saved Phase 3 outputs, never recomputed;
labels never defaulted. No parameter was derived from scikit-learn
defaults.

## 3. Changed-file inventory

New files:

- `backend/app/services/benchmark_catalog.py` — Layer A + Layer B adapter
  (fixed allowlists, bounded parsers, digest verification, PR-08-style
  bounded cache-integrity policy).
- `backend/app/contracts/benchmark.py` — Pydantic contracts.
- `backend/app/api/v1/benchmark.py` — four GET operations under
  `/api/v1/research/benchmark` with the sanitized error matrix.
- `backend/tests/test_benchmark_adapter.py` — 48 tests covering the 18
  mandatory scenarios.
- `frontend/tests/integration/benchmark-workspace.test.tsx` — 8 Vitest
  tests.
- `docs/research-integration/PR09_SOURCE_ADMISSION.md`,
  `PR09_API_DATA_CONTRACT.md`, `PR09_TEST_MATRIX.md`, and this report.

Modified files (minimal integration changes only):

- `backend/app/api/v1/router.py` — mount the benchmark router.
- `backend/tests/test_openapi.py` — the four new paths added to the
  expected-path inventory.
- `backend/tests/test_synthetic_boundary_sweep.py` — the two sweeps
  extended with the new GET routes (required by the sweep's own
  OpenAPI-driven completeness assertion).
- `backend/contracts/openapi.json` — regenerated (24 paths).
- `frontend/src/api/contracts.gen.ts` — regenerated.
- `frontend/src/api/contracts.ts` — benchmark types (mirrors the
  generated schemas; drift check passes).
- `frontend/src/api/endpoints.ts` — four endpoint wrappers.
- `frontend/src/pages/ResearchPage.tsx` / `ResearchPage.css` — the
  benchmark section inside the existing Research workspace (no seventh
  workspace).
- `frontend/playwright/e2e.spec.ts` — test 21 (real-backend benchmark
  workspace check).

## 4. Public / restricted publication decision

All four benchmark operations are **public read-only** (FR-03 / ADR-007),
matching the PR-08 research routes: precomputed, non-sensitive scientific
values with provenance. Anonymous access is covered by tests; no case
route lost authentication, authorization or CSRF protection
(`test_authenticated_case_write_and_private_history_isolation` verifies
the case side; the full 602-test regression suite verifies the rest).

## 5. Source and payload integrity method

- Layer A: `config.py` SHA-256 vs `ci/frozen_research_manifest.json`
  (frozen-checker-compatible CRLF→LF rule); Phase 4 JSON metadata SHA-256
  + size vs the Phase 4 commit manifest (windows-commit-manifest-compatible
  LF→CRLF reconstruction); cross-check that config grids, run metadata and
  the fixed ten-run allowlist agree; digests re-verified on every request
  against the cache (PR-08 bounded cache-integrity policy).
- Layer B: `.dvc` pointers parsed by a bounded parser (single `outs`
  entry, required keys, md5-only hash, integer size); pointer output path
  must equal the expected filename; payload size must match; payload MD5
  must match raw or CRLF-reconstructed bytes; schema validated against the
  frozen Phase 4 contract (columns, ten unique runs, unique
  `(run_id, row_id)`, no missing score/flag/label); metrics population
  cross-checked against the manifest-verified sample facts; per-request
  digest re-verification with fail-closed invalidation and restart-free
  recovery.
- No pickle deserialization, no `dvc` execution, no downloads, no
  filesystem paths from user input.

## 6. Evidence actually obtained (this environment)

- Backend: **650 passed** (602 baseline + 48 new), 78.3 s.
- Frontend: typecheck PASS, lint PASS, **128 Vitest passed** (120 + 8),
  build PASS, OpenAPI drift PASS.
- E2E: **21 passed** (20 + 1) against the real pgserver + uvicorn backend.
- Frozen integrity: **28/28 match** before and after all changes.
- Clean-checkout behaviour verified live: catalog 200 with
  `artifact_missing` capabilities; metrics/record routes 503 with
  machine-readable reasons.

## 7. Missing evidence and blocked features

- **Windows trusted-payload validation: NOT RUN — DATA UNAVAILABLE.** The
  real DVC payloads are absent in this sandbox; `dvc pull` and B2
  credentials are out of scope here. The maintainer checklist is in
  `PR09_TEST_MATRIX.md` §5. Until then, the metrics and record-lookup
  features stay in their explicit unavailable state in any deployment
  without the payloads — by design, not by defect.
- Hosted CI run: to be executed on push (fixture-only suite, clean
  checkout, no DVC/B2 secrets required).

## 8. Protected-file before/after verification

- `python ci/check_frozen_integrity.py` → **28/28 match** (before:
  verified at branch creation; after: verified at delivery).
- `git status` shows no modifications under `src/mplad/`,
  `results/stream a/`, `ci/frozen_research_manifest.json`, `.dvc`
  pointers, or the frozen scientific tests (`tests/test_phase*.py`).
- No modelling, threshold recomputation or metric recalculation was run;
  no pickle was deserialized (test-enforced); no DVC pointer or manifest
  byte was altered.

## 9. Rollback steps

1. `git revert <merge-commit>` on `main` (or delete the
   `pr-09-canonical-benchmark` branch before merge).
2. The only integration points are: the router mount
   (`backend/app/api/v1/router.py`), the regenerated contracts
   (`openapi.json`, `contracts.gen.ts`) and the ResearchPage section —
   all additive; reverting the merge commit restores PR-08 behaviour
   exactly.
3. No database migration was added; no environment variable, secret or
   external service was introduced. Rollback requires no data steps.

## 10. Requirement and acceptance-test traceability

| Requirement | Status |
|---|---|
| FR-02 (source/dataset/version/integrity on records) | Catalog + detail responses carry dataset identity, scope, run status and verified digests |
| FR-03 (public read-only research; writes restricted) | All four operations anonymous-readable (tested); case writes unchanged |
| FR-04 (server-side allowlists only) | Fixed path specs and run-ID allowlists; no client-derived paths |
| FR-05 (useful unavailable states, no silent fallback) | `artifact_missing` / `integrity_failed` capabilities + 503 reasons + UI unavailable panels |
| FR-13 (ten frozen runs, correct orientation, configs, verified metrics) | Ten runs served with exact parameters; metrics served only from the admitted verified payload; score orientation explicit |
| FR-16 (row_id lookup aligned to labels/flags/scores) | Record lookup by exact saved row_id; label/flag/score distinctions explicit; shuffled-order invariance tested |
| FR-31 (SHA-256 manifest verification, fail closed) | Layer A digest chain + Layer B md5/size + commit-manifest SHA cross-check; tamper tests |
| FR-32 (source/algorithm/parameter/manifest references) | Provenance chain on every response (config, run metadata, commit manifest, payload md5) |
| NFR-01 (manifest-tied or marked unverified) | Verified digests on every served payload; unverified data is never served |
| NFR-02 (deployment records revisions/hashes) | Provenance blocks carry artifact paths + digests |
| NFR-11 (determinism; interactions never change evidence) | Read-only adapter; digest re-verification; no recomputation |
| ADR-003 (read-only evidence access) | GET-only, no writes, no blobs in review DB |
| ADR-004 (no on-request computation) | No fitting/scoring/thresholding; test-enforced import guard |
| ADR-007 (public reader, authenticated reviewer) | Publication decision §4 |
| ADR-008 (fixture-only PR checks; DVC in protected pipeline) | CI suite is fixture-only on a clean checkout; no secrets touched |
| AT-02 (assessor finds the 10 runs, parameters, limitations) | Catalog + detail + UI section |
| AT-03 (tamper manifest → integrity failure, not served) | Tamper tests (Git metadata + payload + post-cache mutation) |
| AT-04 (shuffled rows still join on row_id) | Shuffled-order invariance test |
| AT-10 (missing optional artifact → identified unavailable panel; broken manifest → clear failure) | Capability availability + sanitized 503 reasons + UI unavailable states |

## 11. Remaining M2 work (not part of PR-09)

- M2-03: Phase 5/6 interpretation surfaces (bootstrap/agreement/figures,
  workload denominators) — separate PR.
- M2-05: source-backed methodology view (preprocessing trace, historical
  284k companion handling) — separate PR.
- Trusted Windows payload validation (§7) and hosted CI green run.
- PR-10, PR-11, PR-12 and all M3/R2 work remain out of scope.

**PR-09 stops at its boundary.** M2 is not complete; R1 is not claimed
complete.


---

## Maintainer Local Hardening & Windows 11 Verification Addendum (2026-11-14)

Prior to opening the GitHub PR, four targeted integrity and availability hardening corrections were applied locally on `pr-09-canonical-benchmark`:

1. **Trust-Anchor Re-verification on Catalog Cache Hits (`backend/app/services/benchmark_catalog.py`):** `_verify_layer_a_trust_chain()` now re-verifies `src/mplad/common/config.py` against `ci/frozen_research_manifest.json`, `phase4_commit_manifest.json` against the code-pinned `TRUSTED_COMMIT_MANIFEST_SHA256` (`e6d8d9306310af578b90011b407fd953312aeb67c61b5c5f90c41c8faa6d358d`), and `phase4_run_metadata.json` against the commit manifest on every request before accepting `_LAYER_A_CACHE`.
2. **DVC Payload SHA-256 Provenance & Representation-Compatible Size Checks:** `_verify_payload_bytes()` verifies both the `.dvc` pointer (`md5` + `size`) and `phase4_commit_manifest.json` (`sha256` + `size_bytes`) against the same matched byte representation (raw bytes or CRLF-reconstructed text bytes), and surfaces `metrics_sha256` / `evaluation_dataset_sha256` in API provenance blocks.
3. **Independent Layer B Capability Loading (`_LAYER_B_METRICS_CACHE` vs. `_LAYER_B_ROWS_CACHE`):** `get_metrics()` and `get_record()` load and cache their respective DVC payloads independently so one absent optional payload returns `503 artifact_missing` only for its own route without disabling the other capability.
4. **Canonical Row-Level Population & Score/Label/Flag Invariants:** `_validate_evaluation_rows()` enforces exact per-run sample counts (`30,000` per run across all 10 canonical runs = `300,000` rows), identical canonical `row_id` membership across runs, cross-run `Class` label consistency (`47` positive labels per run), valid binary `flag` cardinality (`300` flags per run under the bottom-1% policy), and `math.isclose(anomaly_score, -native_score)` consistency, building an $O(1)$ `(run_id, row_id)` lookup index.

### Verified Local Execution Summary (Windows 11)

- **Frozen research integrity (`python ci/check_frozen_integrity.py`):** `28/28 files match (OK)`.
- **Trusted local real-DVC verification (`TestTrustedLocalRealDvcPayloads`):** Executed and passed against materialized `phase4_metrics.csv` (MD5 `2fb961b52603643dab21850bf6d950f9`, SHA-256 `6535001ce38766d7e52fef84253a7d95e6335b6183fd34f6ead12210eec99acd`, 10 runs) and `phase4_evaluation_dataset.csv` (MD5 `0ba7aece01f588daca3034587e4cbcf7`, SHA-256 `affbf02c63da594d1fdb2c66d07121f39221f7e24082eed4770b59d4598bb048`, 300,000 rows).
- **Targeted backend benchmark, OpenAPI & synthetic boundary tests:** `71/71 passed` (`81.57s`).
- **Full backend pytest suite (`backend/tests`):** `658/659 passed` (`368.30s`); the sole failure is the documented Windows `pgserver --auth=trust` harness limitation in `TestCredentialFailureClassification.test_wrong_password_readiness_503_sanitized`.
- **Frontend verification:** `npm run typecheck` (`0` errors), `npm run lint` (`0` warnings), `npm run test -- --run` (`23/23` test files, `128/128` Vitest tests passed), `npm run openapi:check` (`OK`), and `npm run build` (`dist/assets/index-BAW5YFkS.js`, `2.61s`).
- **Playwright Chromium E2E (`./frontend/scripts/run-e2e.sh`):** `21/21 passed` (`1.0m`, exit `0`), including Test 21 exercising the canonical 10-run benchmark catalog, live Phase 4 metrics table, and canonical `row_id` lookup UI.
