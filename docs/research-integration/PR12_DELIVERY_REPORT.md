# PR-12 Delivery Report — Integrated M2 Acceptance

**Branch:** `pr-12-m2-integrated-acceptance`
**Date:** 2026-11-15
**Status:** Implementation complete; local verification complete; hosted CI green on pre-correction head; corrective commit (R1 + R2) re-verification in progress on this branch tip
**Milestone:** M2 — Verified Stream A Research Integration
**Baseline:** `10d8613558e4056f3d831698adccaec3c79a60cc` (PR #7 merge on `main`)

---

## 1. Summary

PR-12 is the final M2 acceptance gate. It does not introduce new research capability — it consolidates the accepted PR-08 through PR-11 evidence into an explicit integrated acceptance matrix, closes one coverage gap (AG-2), and documents the resolved review findings from the source-admission preflight.

**Deliverables:**
1. `frontend/tests/integration/phase5b-workspace.test.tsx` — 7 scenarios (F5B-01 through F5B-07), models the `phase5a-workspace.test.tsx` pattern
2. `docs/research-integration/PR12_SOURCE_ADMISSION.md` — committed at `f3b9912`; documents admission decisions, provenance, failure-state matrix, objective traceability, and the 10-row acceptance matrix
3. `docs/research-integration/PR12_TEST_MATRIX.md` — consolidated per-PR test map + new frontend coverage
4. `docs/research-integration/PR12_DELIVERY_REPORT.md` — this document

**No production backend changes. No scientific artifact changes. No DVC migration.**

---

## 2. Commit chain since `main`
bbe692b feat(test): add phase5b-workspace frontend integration tests + PR-12 acceptance docs
f3b9912 docs(research): admit integrated M2 evidence for PR-12
ba8c29c docs(planning): start PR-12 source admission and update active baseline
10d8613 Merge pull request #7 (PR-11 acceptance ledger) — main


(The current branch tip adds one corrective commit on top of `bbe692b` for R1 + R2; its SHA is recorded in the CI re-verification message.)

**Note on the SHA reference correction:** `PR12_SOURCE_ADMISSION.md` §2 records `ba8c29c` as the branch HEAD at the time of drafting. That was accurate then; the source-admission commit `f3b9912` and the implementation commit `bbe692b` were made after. The pre-push checkpoint head was `bbe692b`.

---

## 3. AG dispositions (final)

| ID | Status | Evidence |
|---|---|---|
| AG-1 (PR-08 error-specificity) | **CLOSED — N/A** | PR-08 contract emits `{"dependency": "research-source"}` without `details.reason`; preserved as-is. |
| AG-2 (Phase 5B frontend coverage) | **CLOSED — implemented** | `phase5b-workspace.test.tsx` with 7 scenarios; see §4 |
| AG-3 (Integrated M2 acceptance) | **CLOSED — consolidated** | `PR12_TEST_MATRIX.md` §1 (10-row matrix, composed-evidence framing for cross-surface row) |

---

## 4. New test coverage (AG-2 closure)

`frontend/tests/integration/phase5b-workspace.test.tsx` — 7 scenarios, all pass:

| ID | Scenario | Result |
|---|---|---|
| F5B-01 | Eight canonical figures render | PASS |
| F5B-02 | Publication disabled — withheld state | PASS |
| F5B-03 | artifact_missing / integrity_failed states | PASS |
| F5B-04 | Publication enabled — controlled image URLs | PASS |
| F5B-05 | Objectives (a)/(b)/(c) + RQ1–RQ6 | PASS |
| F5B-06 | Historical 284,807-row companion distinction | PASS |
| F5B-07 | API failure — no fabricated content | PASS |

**F5B-07 strengthened per R2 review:** the test now waits for the `role="alert"` ErrorPanel to become visible (via `findByRole("alert")`) before asserting the absence of fabricated scientific content. This eliminates a race condition where the unconditionally-rendered section heading could allow the "no fabrication" assertions to run before the async 503 fetch had settled. Production code unchanged.

Fixtures are synthetic; no real research payloads embedded. Publication gate is disabled by default in the fixture and only enabled per-test for F5B-04.

---

## 5. Integrated acceptance matrix (10 rows)

See `PR12_TEST_MATRIX.md` §1 for the full table. Summary of verdicts:

| # | Acceptance area | Verdict |
|---|---|---|
| 1 | Canonical Phase 4 benchmark (PR-09) | VERIFIED |
| 2 | Phase 5A uncertainty/agreement (PR-10) | VERIFIED |
| 3 | Phase 5B figure provenance (PR-11) | VERIFIED |
| 4 | Phase 6 source-backed results (PR-08) | VERIFIED |
| 5 | Objective/RQ traceability | VERIFIED |
| 6 | Research workspace rendering | VERIFIED (post AG-2) |
| 7 | Cross-surface failure isolation | COMPOSED EVIDENCE |
| 8 | Clean-checkout CI | VERIFIED — run 43751883842, head bbe692b |
| 9 | Real-DVC Windows verification | VERIFIED — 9/9 |
| 10 | Frozen scientific integrity | VERIFIED — 28/28 |

**Row 7 framing:** No single integration test exercises all four services concurrently with mixed availability states. The evidence is composed from individual fail-closed tests in each adapter. Recorded as composed evidence, not a single end-to-end scenario.

**Row 8 note:** Hosted CI run `43751883842` on head `bbe692b` completed all five required jobs successfully (Backend 2m4s, Browser E2E 1m3s, Container 1m17s, Frontend 40s, Frozen 5s). Re-verification on the R1+R2 corrective head is the final merge gate.

**Row 9 note:** Real-DVC verification is manually executed on the trusted Windows workstation with materialized payloads; not automated in CI. Consistent with PR-09 through PR-11 practice.

---

## 6. Verification results

### Frontend (Windows, materialized DVC payloads)

Verified locally on the corrective head (post-R2):
- `npm run typecheck` — PASS (0 errors)
- `npm run lint --max-warnings=0` — PASS (0 warnings)
- `npm run openapi:check` — PASS (clean checkout; runs without `--write` because `.gitattributes` pins `contracts.gen.ts` to eol=lf)
- `npm run test` — **141/141 PASS** (25 files; baseline 134 + 7 new = 141)
- `npm run build` — PASS

### Playwright (chromium E2E)

- **Windows workstation: NOT RUN.** `npx playwright test` fails because `playwright.config.ts` `webServer` uses a POSIX env-var prefix (`PEIARS_DATABASE_URL=... command`) unsupported by Windows cmd; `bash.exe` on this machine is the WSL launcher stub, not full POSIX bash.
- **Hosted CI (Ubuntu): PASS.** Executed in the Browser E2E job of run `43751883842` on head `bbe692b` (1m3s). Hosted Ubuntu is the authoritative Playwright evidence, consistent with PR-08 through PR-11 practice.

### Backend (Windows, materialized DVC payloads)

- `pytest -q` — **754/754 PASS**, 886 warnings (7m46s)
- Hosted CI (Ubuntu, DVC absent) collects the same 754 tests; **12 payload-dependent skips** occur via `@requires_payloads` / `@requires_catalog_csv` markers on the Phase 5B payload-tamper cases. This is the expected skip behavior, not a failure.
- Warning count (886) and classes (Starlette testclient alias, FastAPI `on_event`, Alembic `path_separator`) are unchanged from PR-08 through PR-11. No new warning class introduced by PR-12.
- The 754 count is the actual observed collection on the Windows workstation with DVC payloads present. PR-12 adds zero backend tests. Prior PR references to `750` reflect a different environment state.

### Real-DVC (Windows, materialized)

- 8 canonical PNGs — SHA-256 matches figure manifest (8/8)
- Catalog CSV — SHA-256 matches figure manifest (1/1)
- Result: **9/9 verified**, 0 failed

### Frozen research integrity

- `python ci/check_frozen_integrity.py` — **28/28 PASS** (verified on both `bbe692b` and the corrective head)

### Hosted CI (Ubuntu, run 43751883842, head bbe692b)

| Job | Result | Duration |
|---|---|---|
| Backend tests (Python 3.12, real PostgreSQL) | PASS | 2m4s |
| Browser E2E (Chromium + real backend + pgserver) | PASS | 1m3s |
| Container build + Compose smoke | PASS | 1m17s |
| Frontend (Node 22 — typecheck, lint, vitest, build, OpenAPI) | PASS | 40s |
| Frozen research integrity (SHA-256) | PASS | 5s |

0 cancelled, 0 failing, 5 successful, 0 skipped, 0 pending. Re-verification on the R1+R2 corrective head is the final merge gate.

---

## 7. Retained boundaries

- **Phase 5B public binary delivery** remains disabled by default (`PEIARS_PHASE5B_PUBLIC_FIGURES_ENABLED=false`). Enabling is a deployment-time decision, subject to licensing review.
- **Historical 284,807-row LOF Novelty Mode companion** is not comparable to the canonical 30,000-row benchmark. The distinction is enforced in the API (`historical_companion` block), rendered in `ResearchPage.tsx`, and asserted in F5B-06.
- **PR-08 failure envelope** does not emit `details.reason`. Preserved as-is; do not normalize for PR-09/10/11 symmetry.
- **DVC migration** deferred to M4. The DVC storage inventory (604.7 MB available payload, missing 151 MB deprecated artifact) is recorded separately and is not part of PR-12.

---

## 8. M2 recommendation

**M2 is READY FOR MERGE pending final authorization on the corrective head's CI result.**

Evidence:
- All 10 acceptance-matrix rows are VERIFIED or COMPOSED EVIDENCE with documented backing
- AG-1 closed (N/A), AG-2 implemented, AG-3 consolidated into the acceptance matrix
- Frozen scientific integrity maintained (28/28)
- No new research computation, no regressions in PR-08 through PR-11 surfaces
- Hosted CI 5/5 green on pre-correction head `bbe692b`; re-verification on the R1+R2 corrective head is the merge gate

**Post-merge follow-up:** Open a small docs-only branch (`docs/pr12-acceptance-ledger`) to update `docs/planning/R1_IMPLEMENTATION_STATUS.md` with the PR-12 merge SHA and mark M2 COMPLETED, following the PR-11 acceptance-ledger pattern.

---

## 9. Deferred to M4

- DVC remote selection (GitHub Releases vs. S3-compatible DVC remote vs. private GitHub distribution)
- Public Phase 5B PNG binary delivery authorization
- Deployment reproducibility procedures
- Recovery of the deprecated 151 MB `creditcard_preprocessed.csv` object or documented omission

These are all M4 scope; none block M2 acceptance.

---

*End of PR-12 delivery report.*