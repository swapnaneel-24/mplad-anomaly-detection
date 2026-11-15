# PR-12 Source Admission — Integrated M2 Evidence

**Branch:** `pr-12-m2-integrated-acceptance`
**Date:** 2026-11-15
**Status:** Mandatory pre-implementation gate
**Baseline:** `10d8613558e4056f3d831698adccaec3c79a60cc` (PR #7 merge commit on `main`; includes PR-11 acceptance ledger)

---

## 1. Decision

**Integrated M2 evidence ADMITTED. Final M2 acceptance PENDING a bounded PR-12 closure.**

| Evidence group | Verdict | Basis |
|---|---|---|
| A — Scientific evidence (PR-08 through PR-11) | **VERIFIED** | Four research surfaces present, distinct, coherent; population boundaries explicit and unviolated |
| B — Provenance | **VERIFIED** | Three independently pinned manifest chains (PR-09/10/11) plus PR-08's separate frozen-source chain; each pin defined once and verified once |
| C — Failure behavior | **VERIFIED at individual-service level** | Each service fails closed; cross-surface integration not yet demonstrated as a consolidated acceptance |
| D — Objective traceability | **VERIFIED** | Source-native objectives (a)/(b)/(c), RQ1–RQ6, Phase 6 synthesis and Phase 7 limitations all traceable to authentic evidence |
| E — Integrated application | **PARTIALLY VERIFIED** | All four research surfaces render in the Research workspace; dedicated frontend Phase 5B integration test absent (AG-2) |

**Boundary observations that are NOT defects:**

- PR-08 uses a distinct provenance architecture (frozen Python source + `ci/frozen_research_manifest.json`) vs. PR-09/10/11 (per-family commit manifest + `.dvc` pointers). The `phase6_commit_manifest.json` on disk is not consumed by any service — intentional, because PR-08 serves AST-extracted constants from frozen source, not the Phase 6 CSV artifacts.
- PR-08 uses a simpler public failure envelope (`{"dependency": "research-source"}`) without `details.reason` distinction. This is the existing contract and remains correct as-is.

**Corrections authorized in PR-12:** AG-2 (frontend Phase 5B integration test) only. AG-1 (PR-08 reason-code specificity) is closed as **NOT APPLICABLE** — the PR-08 contract does not emit those codes.

**Scope exclusions (unchanged from PR-11):** No refitting IF/LOF models, no recomputation of Phase 4–6 statistics, no regeneration of Phase 5B figures, no modification of the 28 protected scientific files, no new production research APIs, no normalization of historical novelty-mode results, no default-enabled public PNG delivery, no refactor of PR-08's error taxonomy, no expansion into M3/M4 work.

---

## 2. Baseline

| Item | SHA |
|---|---|
| PR-08 merge commit | `0a23577dc52839ff2ea54cdc3fcbc32e35523fd3` (per PR-10 ledger) |
| PR-09 merge commit | `89615e5b6a0c89bb6c06401f2d5e87a4e6478556` (per PR-10 ledger) |
| PR-10 merge commit | `e57cc15239e2f590d9aa3ca6bc2bab7ca1310dd3` |
| PR-11 merge commit | `8ed0669af2b07a2c8aa45d3d5aa174104b017335` |
| PR-11 acceptance ledger merge (PR #7) | `10d8613558e4056f3d831698adccaec3c79a60cc` |
| Current `main` HEAD | `10d8613` (unchanged) |
| PR-12 branch HEAD | `ba8c29ce0e2c203fd36375f5fe8072d3e8d7113d` (one doc commit ahead) |
| Frozen integrity at branch point | 28/28 files match (OK) |

---

## 3. Evidence inventory

### 3.1 Research service modules

| Service | Line count | Serves | Manifest anchor |
|---|---|---|---|
| `backend/app/services/research_source.py` | 747 | PR-08 Phase 6 aggregate reference values | `ci/frozen_research_manifest.json` (28 files) |
| `backend/app/services/benchmark_catalog.py` | 1397 | PR-09 canonical ten-run catalog + Phase 4 metrics | `phase4_commit_manifest.json` pinned by `TRUSTED_COMMIT_MANIFEST_SHA256` (L66), verified L371 |
| `backend/app/services/phase5a_catalog.py` | 1259 | PR-10 Phase 5A uncertainty/agreement/policy evidence | `phase5_commit_manifest.json` pinned by `TRUSTED_PHASE5_COMMIT_MANIFEST_SHA256` (L209), verified L341 |
| `backend/app/services/phase5b_catalog.py` | 635 | PR-11 eight canonical figures + objective traceability | `phase5_plot_commit_manifest.json` pinned by `TRUSTED_PHASE5_PLOT_COMMIT_MANIFEST_SHA256` (L55), verified L124 |

### 3.2 Route modules

| Route module | Line count | Prefix |
|---|---|---|
| `backend/app/api/v1/research.py` | 172 | `/research/sources` |
| `backend/app/api/v1/benchmark.py` | 239 | `/research/benchmark` |
| `backend/app/api/v1/phase5a.py` | 385 | `/research/phase5a` |
| `backend/app/api/v1/phase5b.py` | 164 | `/research/phase5b` |

All routes GET-only, all under `/api/v1/research`, all mounted via `router.py`.

### 3.3 Test families

| Test file | Line count | Service covered |
|---|---|---|
| `backend/tests/test_research_adapter.py` | 658 | PR-08 |
| `backend/tests/test_benchmark_adapter.py` | 1364 | PR-09 |
| `backend/tests/test_phase5a_adapter.py` | 989 | PR-10 |
| `backend/tests/test_phase5b_adapter.py` | 687 | PR-11 |
| `backend/tests/test_frozen_isolation.py` | 177 | Cross-cutting (28-file manifest) |
| `backend/tests/test_synthetic_boundary_sweep.py` | 487 | Cross-cutting (demo-source boundary) |

### 3.4 Frontend research surface

`frontend/src/pages/ResearchPage.tsx` renders all four research surfaces in a single workspace. Section headings (from L409):

- L409 Methodology
- L426 Reproducibility
- L443 Precomputed Research Results (PR-08)
- L526 Canonical Benchmark — Ten IF/LOF Runs (PR-09)
- L783 Phase 5A Evidence — Uncertainty, Agreement, Review Policies (PR-10)
- L1092 Phase 5B — Figure Gallery and Methodology (PR-11)
- L1272 Limitations / L1283 Scientific cautions

Frontend integration tests:
- `research-workspace.test.tsx` (220 L) — PR-08 surface
- `benchmark-workspace.test.tsx` (518 L) — PR-09 surface
- `phase5a-workspace.test.tsx` (419 L) — PR-10 surface
- **No `phase5b-workspace.test.tsx`** — closes with PR-12 (AG-2)

---

## 4. Provenance

### 4.1 Manifest-pin chains (PR-09, PR-10, PR-11)

Symmetric structure — each pin constant:

1. Defined once in its service module with an LF-normalized SHA-256 value.
2. Verified at exactly one call site before artifact trust is granted.
3. Verification uses `trust.canonicalize_frozen_checker` (CRLF–LF) so the pin is stable across checkouts and CI platforms.
4. A pin mismatch raises the service-specific integrity error — mapped by the API to `503 SERVICE_NOT_READY` with `reason="integrity_failed"`.

| Family | Pin constant | Definition | Verification |
|---|---|---|---|
| PR-09 | `TRUSTED_COMMIT_MANIFEST_SHA256` | `benchmark_catalog.py:66` | `benchmark_catalog.py:371` |
| PR-10 | `TRUSTED_PHASE5_COMMIT_MANIFEST_SHA256` | `phase5a_catalog.py:209` | `phase5a_catalog.py:341` |
| PR-11 | `TRUSTED_PHASE5_PLOT_COMMIT_MANIFEST_SHA256` | `phase5b_catalog.py:55` | `phase5b_catalog.py:124` |

### 4.2 PR-08 frozen-source chain (architectural distinction)

`research_source.py` uses a **different but equally defensible** provenance model:

1. Reads approved SHA-256 digests from `ci/frozen_research_manifest.json` (the same 28-file manifest used by `ci/check_frozen_integrity.py`).
2. For each consumed file, computes `_sha256_canonicalized` (CRLF—LF) and compares to the approved digest **before parsing**.
3. Only after verification, extracts constants from `src/mplad/stream_a/phase6.py` via `ast.literal_eval` (no import, no code execution, no AST evaluation of expressions).
4. Serves 18 precomputed reference values + `INTERPRETATION_PRINCIPLES` + `EXPLORATORY_SELECTION_CAVEAT` **verbatim**.

**Why `phase6_commit_manifest.json` is not consumed by any service:** PR-08 does not serve the Phase 6 CSV artifacts (which the Phase 6 commit manifest would cover). It serves aggregate constants extracted from the frozen Python source. That source is anchored by `ci/frozen_research_manifest.json`, which is the correct anchor for this design. The Phase 6 commit manifest governs Phase 6 CSV outputs and remains on disk for any future consumer but is not part of the PR-08 trust chain.

**This asymmetry is intentional, documented, and NOT a defect.** PR-12 will record it as an architectural note in the acceptance matrix, not correct it.

---

## 5. Failure-state matrix (individual-service contract)

| Mode | PR-08 | PR-09 | PR-10 | PR-11 | Test coverage |
|---|---|---|---|---|---|
| Payload present + valid | 200 | 200 | 200 | 200 | Each adapter test file asserts success paths |
| Payload absent (Layer B) | 503, no `reason` field | 503 `artifact_missing` | 503 `artifact_missing` | 503 `artifact_missing` | Asserted in each test file (`status_code == 503`) |
| Manifest tamper / digest mismatch | 503, no `reason` field | 503 `integrity_failed` | 503 `integrity_failed` | 503 `integrity_failed` | Asserted in each test file |
| Publication gate disabled | N/A | N/A | N/A | 403 `PUBLICATION_NOT_APPROVED` | `test_phase5b_adapter.py` (`TestPublicationGate`, 4 assertions) |
| Unknown source_id/run_id | 404 `SOURCE_NOT_FOUND` | 404 `SOURCE_NOT_FOUND` | 404 `SOURCE_NOT_FOUND` | N/A | Asserted per service |
| Cache mutation recovery | Module-level cache; `_invalidate_cache()` | Grep confirms analogous coverage | Grep confirms analogous coverage | `TestCacheMutationRecovery` explicit | Per-service |

**PR-08 taxonomy distinction:** The PR-08 API deliberately does not distinguish `artifact_missing` from `integrity_failed` in the public response — both map to `{"dependency": "research-source"}` without a `reason` field. This is the established public contract. AG-1 is closed as NOT APPLICABLE: asserting nonexistent reason codes would violate the contract, and normalizing PR-08's error envelope solely for symmetry would expand PR-12's scope.

**Cross-surface failure isolation:** Each service's fail-closed behavior is verified at the unit-test level. Integrated cross-surface acceptance (all four services operating concurrently with mixed availability states and preserving unrelated endpoint behavior) is not currently a single asserted scenario and is listed as a PR-12 obligation (see §7).

---

## 6. Objective traceability

| Source-native objective | Evidence chain |
|---|---|
| `(a)` Data preparation and preprocessing | `docs/Phase-0.md` §0.3.1 (in-scope pipeline design); `docs/provenance_log.md` §5 (Phase 2 Track A decisions); `docs/phase5_figure_catalog.md` §3 Figure 8 conventions (FS-A frozen preprocessing) |
| `(b)` IF/LOF application and comparative evaluation | PR-09 benchmark catalog (`benchmark_catalog.py`); PR-10 Phase 5A agreement evidence (`phase5a_catalog.py`); PR-11 eight canonical figures (`phase5b_catalog.py`) |
| `(c)` Consistency, false positives, and ethics | PR-10 agreement groups + review policies; Phase 6 five-question synthesis (`docs/phase6_contract.md` §4); Phase 7 limitations (`docs/phase7_synthesis.md`) |

Research questions RQ1–RQ6 are sourced from `docs/Phase-0.md` §0.4, mapped to objectives in the PR-11 traceability endpoint (`phase5b_catalog.py::_build_traceability`). The mapping is served via `GET /api/v1/research/phase5b/traceability` and rendered on `ResearchPage.tsx` at L1161 (h3 "Methodology and Original Objectives").

Phase 6 synthesis and Phase 7 limitations are:

- **Documented**: `docs/phase6_contract.md`, `docs/phase7_synthesis.md`
- **Served**: `research_source.py` exposes the Phase 6 reference constants + interpretation principles
- **Cross-referenced**: `phase5b_catalog.py:519-537` links objective `(c)` to `{"type": "phase6_synthesis", "source_id": "phase6"}` and `{"type": "phase7_limitations", "source_id": "phase7"}`

No OBJ-* identifiers are invented. All research provenance is source-native.

---

## 7. Acceptance-gap register

| ID | Finding | Classification | Corrective scope |
|---|---|---|---|
| AG-1 | PR-08 reason-code specificity | **NOT APPLICABLE** — existing PR-08 contract does not emit `reason` field; behavior is fail-closed and tested | None. Preserve intentional error-granularity distinction as an architectural note. |
| AG-2 | Missing `frontend/tests/integration/phase5b-workspace.test.tsx` | **PARTIALLY VERIFIED** — required corrective | Add Vitest/React integration test covering PR-11 gallery + traceability render, publication-withheld state, artifact_missing state, and objective/RQ display |
| AG-3 | Integrated M2 cross-surface acceptance | **PARTIALLY VERIFIED** — acceptance evidence pending | Establish a documented acceptance matrix (this PR-12 deliverable) that cites existing tests per surface; only add code where an actual uncovered condition remains |

**AG-3 in context.** PR-12's purpose is to consolidate the accepted M2 evidence into a coherent acceptance matrix, not to build new backend services. Where a cross-surface condition is already covered by an existing test, cite that test. Where a cross-surface condition is not asserted as an integration scenario (e.g., "all four services simultaneously operable with mixed availability"), document it as `existing evidence available — integrated acceptance result recorded in §8`. Do not add implementation code unless a genuine gap exists.

---

## 8. Proposed PR-12 scope

### 8.1 Integrated acceptance matrix (PR-12 deliverable)

| Acceptance area | Status | PR-12 obligation |
|---|---|---|
| Canonical Phase 4 benchmark (PR-09) | **VERIFIED** | Reference `test_benchmark_adapter.py` |
| Phase 5A uncertainty/agreement (PR-10) | **VERIFIED** | Reference `test_phase5a_adapter.py` |
| Phase 5B figure provenance (PR-11) | **VERIFIED** | Reference `test_phase5b_adapter.py` |
| Phase 6 source-backed results (PR-08) | **VERIFIED** | Document distinct provenance architecture (§4.2) |
| Objective/RQ traceability | **VERIFIED** | Reference `phase5b_catalog.py::_build_traceability` + `ResearchPage.tsx` L1161 |
| Research workspace rendering | **PARTIALLY VERIFIED** | Close AG-2 (new `phase5b-workspace.test.tsx`) |
| Cross-surface failure isolation | Existing evidence available | Establish integrated acceptance result (documented) |
| Clean-checkout CI | Existing evidence available | Confirm on PR-12 final head |
| Real-DVC Windows verification | Existing evidence available | Confirm on PR-12 final head |
| Frozen scientific integrity | **VERIFIED at baseline** | Reverify before acceptance |

### 8.2 Implementation scope (bounded)

**Single new file:** `frontend/tests/integration/phase5b-workspace.test.tsx`

Modeled on `phase5a-workspace.test.tsx` (419 L). Minimum assertions per ChatGPT Stage 1 review §1:

1. Eight canonical figure entries render from supplied API responses.
2. Publication disabled produces visible withheld state without image delivery.
3. Missing or corrupt figures produce the appropriate unavailable state.
4. Authorized, available images use the controlled image URL (`/api/v1/research/phase5b/figures/{n}/image`).
5. Objectives (a)/(b)/(c) and RQ1–RQ6 render correctly.
6. Historical 284,807-record companion remains visibly distinct from the canonical 30,000-record benchmark.
7. API failure produces an appropriate error state without fabricated research content.

Vitest/React integration test only. No new browser E2E framework, no new workspace, no additional backend code.

### 8.3 Documentation deliverables

- `docs/research-integration/PR12_SOURCE_ADMISSION.md` (this document)
- `docs/research-integration/PR12_TEST_MATRIX.md` (per-PR-08/09/10/11 test consolidation + new phase5b frontend coverage)
- `docs/research-integration/PR12_DELIVERY_REPORT.md` (integrated acceptance matrix, implementation summary, verification results)

### 8.4 Explicitly NOT in PR-12 scope

Per ChatGPT Stage 1 review §4 scope exclusions:

- No refitting IF/LOF models.
- No recomputation of Phase 4–6 statistics.
- No modification of the 28 protected scientific files.
- No regeneration of Phase 5B figures.
- No new production research APIs.
- No normalization of historical novelty-mode results into the canonical benchmark.
- No default-enabled Phase 5B public PNG delivery.
- No refactor of PR-08's public error taxonomy.
- No expansion into M3 (PMGSY) or M4 (deployment) work.

---

## 9. Frozen integrity baseline

`python ci/check_frozen_integrity.py` returns `28/28 files match (OK)` on the PR-12 branch at the time of this admission. No frozen scientific file, DVC pointer, or manifest was touched by the Stage 1 inventory.

---

*End of PR-12 source admission.*