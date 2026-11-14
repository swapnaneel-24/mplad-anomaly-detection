# PR-08 Delivery Report

**Milestone:** PR-08 — Frozen Scientific Research Results Integration
**Baseline:** `831c9b4d23349b57d48828157d68fefde5927f02` (PR-07B merge, PR #2)
**Branch:** `pr-08-research-readonly`
**Scope:** Read-only scientific results discovery, provenance-preserving
adapter and presentation. No model execution, no new data ingestion,
no frozen artifact changes.

---

## 1. Baseline and final commit

| | |
|---|---|
| Baseline | `831c9b4d23349b57d48828157d68fefde5927f02` — PR #2 merge (pr-07b-rc-verification) |
| Branch | `pr-08-research-readonly` |
| Final commit | See git log (this delivery) |
| Production code changed | Zero existing application logic modified. New read-only adapter added. |

---

## 2. Complete frozen source inventory result

28/28 frozen artifacts verified (SHA-256, frozen-checker canonicalization: LF-normalized text, raw bytes for binary). Classification:
1 ELIGIBLE (`src/mplad/stream_a/phase6.py` — `PHASE6_REFERENCE_VALUES`),
3 CONDITIONAL (documentation with reference values/caveats),
24 INELIGIBLE (narrative, infrastructure code, test code, empty files).

See `PR08_FROZEN_SOURCE_INVENTORY.md` for the full 28-artifact table.

---

## 3. Integrated result family

**`phase6-reference-values`** — 18 precomputed aggregate reference
values from the canonical ULB credit-card fraud benchmark experiment
(Stream A, Phase 6). Values include: sample size, fraud label count,
per-detector flagged counts, cross-method overlap (intersection/union),
agreement-group composition with fraud counts, Spearman correlation,
Jaccard overlap, and hypergeometric enrichment.

**Scientific justification:** aggregate-level (no record mapping),
machine-readable (Python dict parsed via AST), fully documented
(dataset, model, evaluation context, limitations), frozen (SHA-256
verified), deterministic (same artifact → same results).

---

## 4. Artifact provenance and integrity

- **Source artifact:** `src/mplad/stream_a/phase6.py`
- **SHA-256:** `2a9e7d7973c48e1305fda6f640b36d327b1a019f55419494de6a2d004f7107b3`
- **Digest algorithm:** SHA-256
- **Canonicalization:** `frozen-checker-compatible` (CRLF normalized to LF for text files without null bytes; raw bytes for binary files — matching `ci/check_frozen_integrity.py`)
- **Extraction method:** AST parsing (`ast.literal_eval`) — no module
  import, no code execution, no numpy/pandas/sklearn dependency
- **Same-snapshot guarantee:** the SHA-256 is computed from the same
  canonicalized byte snapshot that the AST parser reads

---

## 5. API endpoints implemented

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/research/sources` | List approved research sources |
| GET | `/api/v1/research/sources/{source_id}` | Source metadata + provenance |
| GET | `/api/v1/research/sources/{source_id}/results` | Precomputed results with interpretation principles, caveat, limitations |

All GET-only. All require authentication. All roles (viewer/reviewer/admin) have read access.

---

## 6. Backend and frontend file changes

### New backend files
- `backend/app/services/research_source.py` — read-only adapter (AST-based frozen constant extraction)
- `backend/app/contracts/research.py` — Pydantic response models
- `backend/app/api/v1/research.py` — 3 GET routes
- `backend/tests/test_research_adapter.py` — 18 tests

### Modified backend files
- `backend/app/api/v1/router.py` — registered research router
- `backend/contracts/openapi.json` — regenerated with 3 new routes
- `backend/tests/test_openapi.py` — added 3 new paths to expected set
- `backend/tests/test_synthetic_boundary_sweep.py` — sweep includes /research/* endpoints

### New frontend files
- `frontend/tests/integration/research-workspace.test.tsx` — 5 Vitest tests

### Modified frontend files
- `frontend/src/api/contracts.ts` — research types
- `frontend/src/api/contracts.gen.ts` — regenerated
- `frontend/src/api/endpoints.ts` — 3 endpoint functions
- `frontend/src/pages/ResearchPage.tsx` — "Precomputed Research Results" section
- `frontend/playwright/e2e.spec.ts` — test #20

### New documentation
- `docs/research-integration/PR08_FROZEN_SOURCE_INVENTORY.md`
- `docs/research-integration/PR08_SOURCE_ELIGIBILITY.md`
- `docs/research-integration/PR08_ADAPTER_CONTRACT.md`
- `docs/research-integration/PR08_SCIENTIFIC_LIMITATIONS.md`
- `docs/research-integration/PR08_TEST_MATRIX.md`
- `docs/research-integration/PR08_DELIVERY_REPORT.md` (this document)

---

## 7. Confirmed numerical and scientific semantics

- 18 reference values served exactly as stored in the frozen dict (no
  inversion, rescaling, normalization, or thresholding).
- `is_precomputed: true` and `is_live_prediction: false` in every response.
- Interpretation principles served verbatim from the frozen source.
- Exploratory caveat served verbatim from the frozen source.
- No NaN/Infinity values (all frozen values are finite int/float literals).

---

## 8. Security and read-only guarantees

- No mutation endpoints (GET only).
- No database writes (research reads create no case/event rows — asserted).
- No new RBAC role (reuses viewer/reviewer/admin).
- No frozen artifact modifications (28/28 match).
- No synthetic fallback on failure (error returned, not synthetic data).
- No path traversal (source_id is allowlisted; artifact path is fixed).
- No module execution (AST parsing only; no numpy/pandas/sklearn import).

---

## 9. Test results

| Suite | Result |
|---|---|
| Backend pytest | **602 passed** (574 + 28 research adapter) |
| Frontend typecheck/lint/build | PASS |
| Frontend Vitest | **120 passed** (115 + 5 research workspace) |
| OpenAPI drift | PASS |
| Browser E2E | **20 passed** (19 + 1 research workspace) |
| Frozen integrity | **28/28 match** |

The 28 research adapter tests include:
- 14 positive cases (correct values, provenance, interpretation principles,
  deterministic rendering, supporting-artifact verification, same-snapshot
  spy test)
- 5 negative cases (unknown source, anonymous access, mutation rejection,
  no synthetic fallback)
- 5 cache-integrity policy tests (source modified/removed/supporting altered
  → fail closed; restoration → recover; unrelated endpoints continue)
- 1 startup safety test (app creates with genuinely absent artifact;
  health works; research returns 503)
- 2 RBAC tests (viewer read, no case-state writes)
- 1 OpenAPI contract test
- 2 UI hash accuracy tests (all 28 path→prefix pairings verified;
  swap test confirms strictness)

---

## 10. Compose and hosted CI

- **Docker/Compose:** NOT RUN (no Docker daemon in sandbox). The
  research adapter requires no Docker-specific configuration — it
  reads from the repository's frozen source tree, which is present in
  every container image.
- **GitHub-hosted CI:** NOT RUN (branch not pushed). The five GHA jobs
  are unchanged; least-privilege permissions and SHA-pinned actions
  untouched.

---

## 11. Explicit scientific limitations

1. The values are from the ULB credit-card fraud benchmark, NOT MPLAD data.
2. Anomaly flags are not proof of fraud.
3. ULB benchmark performance must not be assumed to transfer to MPLAD.
4. The IF_003/LOF_004 comparison is exploratory (post-hoc selection bias).
5. No universal superiority of IF or LOF is claimed.
6. The results are precomputed, not live predictions.
7. No record-level results are served (aggregate-level only).

---

## 12. Known issues and blockers

None. The implementation is complete; no unresolved blocker remains.

---

## 13. Scope compliance

- No new data ingestion, no live inference, no model retraining, no PCA
  recomputation, no new scoring algorithms, no arbitrary thresholds,
  no automatic fraud classification, no research-to-case auto-linking,
  no new case mutation workflows, no additional workspaces, no frozen
  artifact modifications, no new public-data collection, no new
  scientific experiments.
- API contracts: 3 new GET routes added; existing contracts unchanged
  (`openapi:check` no drift for existing routes).
- All 28 frozen scientific artifacts preserved (28/28).
- Synthetic and genuine results strictly separated.
- One production change: new read-only adapter (no existing code modified).

**PR-08 is complete. STOP.**
