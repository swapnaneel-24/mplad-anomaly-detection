# PR-12 Test Matrix — Integrated M2 Acceptance

**Branch:** `pr-12-m2-integrated-acceptance`
**Date:** 2026-11-15
**Status:** Implemented; local verification complete; hosted CI green on pre-correction head; R1+R2 corrective commit is the final merge gate

---

## 1. Integrated acceptance matrix

| # | Acceptance area | Verdict | Supporting evidence |
|---|---|---|---|
| 1 | Canonical Phase 4 benchmark (PR-09) | VERIFIED | `tests/test_benchmark_adapter.py` (1364 L); backend CI |
| 2 | Phase 5A uncertainty/agreement (PR-10) | VERIFIED | `tests/test_phase5a_adapter.py` (989 L); backend CI |
| 3 | Phase 5B figure provenance (PR-11) | VERIFIED | `tests/test_phase5b_adapter.py` (687 L); backend CI |
| 4 | Phase 6 source-backed results (PR-08) | VERIFIED | `tests/test_research_adapter.py` (658 L); frozen-source architecture documented in PR12_SOURCE_ADMISSION.md — 4.2 |
| 5 | Objective/RQ traceability | VERIFIED | `phase5b_catalog.py::_build_traceability`; `test_phase5b_adapter.py::TestTraceability` (5 tests); `ResearchPage.tsx` L1161 (rendered) |
| 6 | Research workspace rendering | VERIFIED (post-fix) | `phase5b-workspace.test.tsx` — 7 new scenarios F5B-01 through F5B-07 |
| 7 | Cross-surface failure isolation | COMPOSED EVIDENCE | Each surface fail-closed is verified in its own adapter test (PR-08: 6 — 503; PR-09: 20; PR-10: 11; PR-11: 7). No single integration test exercises all four simultaneously — described as composed evidence, not a single end-to-end scenario |
| 8 | Clean-checkout CI | VERIFIED — run 43751883842 on head bbe692b | All 5 required GitHub Actions jobs succeeded on the exact pre-correction head; re-verification on the R1+R2 corrective head is the final merge gate |
| 9 | Real-DVC Windows verification | VERIFIED (manual, repeated) | 8 PNGs + catalog CSV verified against figure manifest (SHA-256) and .dvc pointers (MD5) on Windows with materialized payloads |
| 10 | Frozen scientific integrity | VERIFIED | `python ci/check_frozen_integrity.py` returns 28/28 on every commit since PR-11 merge |

**Cross-surface framing:** Per ChatGPT Stage 1 review — 2, component-level adapter test coverage is not the same as a single integrated cross-service scenario. Row 7 is recorded as **composed evidence** — the union of individual fail-closed tests, not a scenario that spins up all four services concurrently. Making that distinction explicit is part of PR-12's acceptance-matrix obligation.

**PR-08 dependency distinction:** PR-08 verifies frozen Python source against `ci/frozen_research_manifest.json` (28 files). This is distinct from DVC-backed payloads (PR-09/10/11). Its 503 contract does not emit `details.reason` — preserving that distinction is required per ChatGPT Stage 1 review — 3.

---

## 2. New test file (AG-2 closure)

`frontend/tests/integration/phase5b-workspace.test.tsx` — 7 acceptance scenarios:

| ID | Scenario | Assertions |
|---|---|---|
| F5B-01 | Eight canonical figures render | `getAllByRole("figure")` returns 8; each "Figure N" caption present; section heading present |
| F5B-02 | Publication disabled — withheld state | 8 "Binary withheld" placeholders; notice shows "disabled"; no `<img>` in any figure |
| F5B-03 | artifact_missing / integrity_failed | Both reason strings rendered; exactly one figure per failure mode |
| F5B-04 | Publication enabled + available | 8 `<img>` elements; each `src` matches `/api/v1/research/phase5b/figures/{n}/image`; no withheld placeholders |
| F5B-05 | Objectives + RQs | 3 objective h4s ((a)/(b)/(c)); RQ table header + RQ1–RQ6 cells |
| F5B-06 | Historical companion distinction | "Historical companion" section present; "284,807" + "not comparable" + "canonical 30,000-row" all rendered |
| F5B-07 | API failure — no fabrication | ErrorPanel `role="alert"` awaited via `findByRole("alert")`; error state confirmed; no figures, objectives, RQ table, or withheld placeholders fabricated |

Test infrastructure reused from `phase5a-workspace.test.tsx`:
- `mockFetch` from `@/tests/helpers/renderApp`
- `authenticatedRoutes(REVIEWER_USER)` base
- `setCookieJar` + `CSRF_COOKIE_NAME`
- `renderApp({ initialEntries: ["/research"] })`
- `waitFor` + `screen` + `within` + `cleanup` in `afterEach`

No production code changes. No new test framework. No new workspace.

---

## 3. Per-PR test consolidation (reference)

| PR | Test file | Line count |
|---|---|---|
| PR-08 | `backend/tests/test_research_adapter.py` | 658 |
| PR-09 | `backend/tests/test_benchmark_adapter.py` | 1364 |
| PR-10 | `backend/tests/test_phase5a_adapter.py` | 989 |
| PR-11 | `backend/tests/test_phase5b_adapter.py` | 687 |
| Cross-cutting | `backend/tests/test_frozen_isolation.py` | 177 |
| Cross-cutting | `backend/tests/test_synthetic_boundary_sweep.py` | 487 |
| PR-12 (new) | `frontend/tests/integration/phase5b-workspace.test.tsx` | ~425 |
| Reference pattern | `frontend/tests/integration/phase5a-workspace.test.tsx` | 419 |

---

## 4. Verification plan (executed before pre-push checkpoint)

- Frontend: `npm run typecheck`, `npm run lint`, `npm run openapi:check`, `npm run test`, `npm run build`
- Backend: `pytest tests/test_phase5a_adapter.py tests/test_phase5b_adapter.py tests/test_openapi.py tests/test_synthetic_boundary_sweep.py -q` (targeted); full suite at pre-push
- Playwright: `./frontend/scripts/run-e2e.sh`
- Frozen integrity: `python ci/check_frozen_integrity.py` (28/28)
- Real-DVC: 8 PNGs + catalog CSV SHA-256 verification on Windows

---

## 5. Known gaps retained from prior PRs

- **Publication gate enforcement is API-level, not filesystem-level.** Deployment isolation for public delivery remains M4 scope. Route audit from PR-11 already confirmed no alternate public path.
- **Browser <img> byte-render under enabled gate** is manually verified on trusted Windows only. Not an automated Playwright test — consistent with PR-11 §7 trusted-lane clause.
- **Historical 26 scratch PNGs** are structurally excluded by the integer-only `figure_no` route (no filename parameter exists). No per-file negative test needed.

---

*End of PR-12 test matrix.*