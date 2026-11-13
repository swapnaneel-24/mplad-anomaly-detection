# PR-07B Delivery Report

**Milestone:** PR-07B — Release Candidate Acceptance
**Baseline commit:** `351aded20d4dca1b243f6db6846dcbc22dc6ff33` (`main`, PR #1 merge)
**Branch:** `pr-07b-rc-verification` (created from `351aded`)
**Scope:** PR-07B Stages 1-8. Release-candidate acceptance verification
and documentation. No PR-08 work. No new product features.

---

## 1. Baseline and branch

| | |
|---|---|
| Baseline | `351aded20d4dca1b243f6db6846dcbc22dc6ff33` — verified as head of `main`, PR #1 merge (`integration/pr07a-hardening`). Clean tree; `pr-06b-accepted` tag dereferences to `2176140`; PR-07A work is in via `e25f653` + `a9f8d03`. |
| Branch | `pr-07b-rc-verification`, created from `351aded` via `git checkout -b pr-07b-rc-verification`. |
| Ancestor check | `git merge-base --is-ancestor 351aded HEAD` → OK. |
| Production code changed in PR-07B | **Zero.** No backend application code, no frontend application code, no migrations, no API contract changes, no frozen research artifacts modified. One E2E test added (test #19, RC-05 integrated workflow) — a test, not application code. |

---

## 2. Stage execution summary

| Stage | Description | Status |
|---|---|---|
| 1 | Repository and baseline audit | DONE — `351aded` verified; `pr-07b-rc-verification` branch created; clean tree. |
| 2 | Acceptance matrix and environment preparation | DONE — RC-01…RC-12 plan in `PR07B_ACCEPTANCE_PLAN.md`; environment inventory in `PR07B_ENVIRONMENT_MATRIX.md`. |
| 3 | Execute available automated acceptance | DONE — backend 574/574, frontend 115/115, E2E 19/19 (18 previously reported + 1 new integrated workflow test), frozen 28/28, OpenAPI no drift, smoke 7/7. |
| 4 | Full-stack operator workflows | DONE for Linux (E2E #1-#19 + `test_concurrency_http.py` + `test_restart_outage_recovery.py`); NOT RUN for Windows/Compose. |
| 5 | Desktop compatibility and security integration | DONE — E2E #16/#17/#18 cover RC-04; existing security tests cover RC-08. |
| 6 | Correct confirmed release-blockers | NONE FOUND — zero production code changes; one E2E test added to close the RC-05 integrated-workflow evidence gap. |
| 7 | Release-candidate dossier | DONE — 9 markdown documents under `docs/acceptance/` + 1 acceptance smoke script. |
| 8 | Final delivery | DONE — `PEIARS_PR07B_changed_files.zip` + `PR07B_FILE_MANIFEST.csv`. |

---

## 3. Changed-file inventory

PR-07B adds 10 new files and modifies 1 existing file (the E2E spec,
to add test #19). No production code is modified.

| File | Change |
|---|---|
| `docs/acceptance/PR07B_ACCEPTANCE_PLAN.md` | New: complete test plan with environments, gates, owners, expected results. |
| `docs/acceptance/PR07B_TEST_MATRIX.md` | New: every RC-01…RC-12 gate, scenarios, execution status, evidence references. |
| `docs/acceptance/PR07B_ENVIRONMENT_MATRIX.md` | New: environment versions, supported combinations, actual execution results, known platform limitations (incl. Windows 11 pgserver trust auth). |
| `docs/acceptance/PR07B_WINDOWS_RUNBOOK.md` | New: copy-ready Windows 11 PowerShell + Git Bash acceptance instructions. |
| `docs/acceptance/PR07B_COMPOSE_RUNBOOK.md` | New: isolated Docker Compose deployment, restart, persistence, safe teardown instructions. Corrected in this revision: separate Git Bash / PowerShell sections; safe credential generation (no literal `$(...)` in `.env.compose`); no secret display via `docker compose config`; bounded-poll readiness with deadline-failure path; authenticated case/history persistence checks; project-label-gated volume removal. |
| `docs/acceptance/PR07B_EVIDENCE_REGISTER.md` | New: commands, results, timestamps, environment, build SHA, artifact names, sanitization verification. |
| `docs/acceptance/PR07B_DEFECT_REGISTER.md` | New: confirmed defects (none); known platform limitations; non-blocking observations. |
| `docs/acceptance/PR07B_RELEASE_DECISION.md` | New: CONDITIONAL GO assessment tied to executed evidence; conditions for full GO. |
| `docs/acceptance/PR07B_DELIVERY_REPORT.md` | New: this document. |
| `ci/pr07b_acceptance_smoke.py` | New: single-command reproducibility verifier (Python 3.12.x, Node >= 22, lockfiles, frozen 28/28, OpenAPI no drift). |
| `frontend/playwright/e2e.spec.ts` | **Modified** (+89 lines): added test #19 (`RC-05 integrated workflow: full authenticated lifecycle in one session`). One continuous authenticated same-case browser workflow: login → select record → create case → add note → transition → decision → verify history → refresh (same session) → verify persistence → logout → re-login → verify case still available. Uses the existing Playwright harness; no second E2E runner created. |

Delivery-only files (ZIP root, not committed): `PR07B_FILE_MANIFEST.csv`
(SHA-256 + byte size for every archive member).

---

## 4. Per-gate verification matrix (final statuses)

Counting method: RC-07 is split into six sub-gates (A through F).
There are 16 technical-verification sub-gates plus RC-12 as the
release decision (not a technical gate). Results are the coding AI's
previously-reported Linux execution; they are NOT independently
re-executed by the reviewer.

| Gate | Title | Final status |
|---|---|---|
| RC-01 | Clean-checkout reproducibility | **PARTIAL** (prerequisite smoke checks PASS; reused-environment regression PASS; actual clean-checkout reproduction NOT RUN) |
| RC-02 | Windows 11 local acceptance | **NOT RUN** (Linux-only coding AI; procedure in `PR07B_WINDOWS_RUNBOOK.md`) |
| RC-03 | Docker Compose release lifecycle | **NOT RUN** (no Docker in sandbox; procedure in `PR07B_COMPOSE_RUNBOOK.md`) |
| RC-04 | Desktop layout (1024/1280/1366/1440) | **PASS** |
| RC-05 | Full authenticated investigation workflow | **PASS** (individual E2E tests #1-#9 + new integrated workflow test #19) |
| RC-06 | Concurrent reviewer | **PARTIAL** (HTTP-level concurrency PASS via `test_concurrency_http.py`; two-browser operator workflow NOT RUN) |
| RC-07-A | Backend restart | **PASS** |
| RC-07-B | Database unavailable | **PASS** |
| RC-07-C | Unmigrated or outdated database | **PASS** |
| RC-07-D | Confirmed POST + failed follow-up GET | **PASS** |
| RC-07-E | Uncertain POST outcome | **PASS** |
| RC-07-F | Stale response race | **PASS** |
| RC-08 | Security integration | **PASS** |
| RC-09 | Provenance and scientific honesty | **PASS** |
| RC-10 | Frozen research integrity | **PASS** — 28/28 |
| RC-11 | GitHub Actions (5 jobs) | **NOT RUN** (branch not pushed; reference run `43395916677` for `351aded`) |
| RC-12 | Release-candidate decision (NOT a technical gate) | **CONDITIONAL GO** |

**Technical-verification sub-gate totals (16 entries):**
11 PASS, 0 FAIL, 2 PARTIAL (RC-01, RC-06), 3 NOT RUN (RC-02, RC-03, RC-11).

**Release decision (RC-12, separate from the 16 sub-gates):**
CONDITIONAL GO.

The 3 NOT RUN sub-gates are environmental limitations of the coding
AI's Linux-only sandbox. The 2 PARTIAL sub-gates reflect honest
evidence-scope distinctions (prerequisite-only vs clean-checkout for
RC-01; HTTP-level vs two-browser for RC-06). Neither PARTIAL nor
NOT RUN is an application defect. See `PR07B_ENVIRONMENT_MATRIX.md`
§4 for the documented platform limitations and
`PR07B_RELEASE_DECISION.md` for the conditional assessment and the
maintainer actions required to promote to full GO.

---

## 5. Full suite results (executed 2026-11-13, Linux sandbox)

The results below are the coding AI's previously-reported Linux
execution. They are NOT independently re-executed by the reviewer.
The bounded correction added one new E2E test (#19); the E2E suite
was re-run to verify the new test passes alongside the existing 18.

| Suite | Command | Result | Source |
|---|---|---|---|
| Backend pytest | `python -m pytest -q` (real pgserver PostgreSQL) | **574 passed**, 57.88 s | previously reported |
| Frontend typecheck | `npm run typecheck` | PASS | previously reported |
| Frontend lint | `npm run lint` (`--max-warnings=0`) | PASS | previously reported |
| Frontend Vitest | `npm run test -- --run` | **115 passed** (21 files), 21.27 s | previously reported |
| Frontend build | `npm run build` | PASS | previously reported |
| OpenAPI drift | `npm run openapi:check` | PASS (no drift) | previously reported |
| Browser E2E (previously reported) | `bash frontend/scripts/run-e2e.sh` (disposable pgserver) | **18 passed**, 31.20 s | previously reported (tests #1-#18) |
| Browser E2E (this correction) | `bash frontend/scripts/run-e2e.sh` | **19 passed**, 34.3 s | re-run after adding test #19 (RC-05 integrated workflow, 2.7s) |
| Frozen research integrity | `python ci/check_frozen_integrity.py` | **28/28 match**, exit 0 | previously reported; re-verified |
| Acceptance smoke | `python ci/pr07b_acceptance_smoke.py` | **7/7 PASS**, exit 0 | previously reported; re-verified |

**Environment:** Linux sandbox; CPython 3.12.16; Node v24.22.2;
pgserver PostgreSQL 16.x (disposable); Playwright Chromium headless
shell 158.0.8127.18 (v1254). No Docker daemon; no Windows; branch not
pushed.

**Delta vs. accepted PR-07A baseline (574/115/18/28):** backend,
frontend, frozen unchanged. E2E: 18 → 19 (+1 new integrated workflow
test). No production code change; the only code change is the
addition of E2E test #19 (a test, not application code).

A pre-existing flake in
`tests/integration/keyboard-interaction.test.tsx > Arrow Right moves
focus to the next tab and Enter activates it` was observed during
PR-07A work; the maintainer's commit `a9f8d03` (test(frontend): wait
for AppShell mount heading focus before tablist keyboard navigation)
addresses it. The test passes reliably at `351aded` (4/4 in
isolation; 115/115 in the full suite). No application defect
involved.

---

## 6. Frozen integrity verification

`ci/check_frozen_integrity.py`: **28/28 files match** at `351aded`
(exit 0). Verified twice: once during Stage 3 baseline execution,
once via `ci/pr07b_acceptance_smoke.py`. No frozen research artifact
was modified by PR-07B. The four `frontend/screenshots/*.png` files
that the E2E run regenerated were reverted to their committed bytes
before the commit (they are NOT part of the frozen manifest, but
binary churn was excluded from the delivery regardless).

---

## 7. Docker / Windows / hosted CI NOT RUN items

- **RC-02 Windows 11 acceptance:** NOT RUN by the coding AI
  (Linux-only sandbox). Procedure documented copy-ready in
  `docs/acceptance/PR07B_WINDOWS_RUNBOOK.md`. Expected maintainer
  result: 573 PASS / 1 FAIL (known harness limitation — see
  `PR07B_DEFECT_REGISTER.md` §2).
- **RC-03 Docker Compose release lifecycle:** NOT RUN (no Docker
  daemon in sandbox). Procedure documented copy-ready in
  `docs/acceptance/PR07B_COMPOSE_RUNBOOK.md`. Reference CI run
  `43395916677` reports 11/11 container smoke checks passing on
  `351aded`.
- **RC-11 GitHub-hosted CI:** NOT RUN (`pr-07b-rc-verification` not
  pushed). Reference CI run `43395916677` is for `351aded`
  (pre-PR-07B), NOT PR-07B CI evidence. The maintainer should push
  the branch and let the five jobs run (no workflow file was changed
  by PR-07B; least-privilege permissions and SHA-pinned actions
  untouched).

---

## 8. Known limitations

1. **Windows 11 pgserver trust-authentication limitation** (contract
   §20a.1): the identified
   `test_wrong_password_readiness_503_sanitized` test fails on
   Windows 11 because the local `pgserver` initializes PostgreSQL
   with `trust` authentication for loopback connections. This is a
   known harness limitation, NOT an application defect. Linux / CI
   result is 574/574; Windows 11 expected result is 573/574. Full
   attribution in `PR07B_DEFECT_REGISTER.md` §2 and
   `PR07B_ENVIRONMENT_MATRIX.md` §4.1.
2. **Three NOT RUN sub-gates** (RC-02 Windows, RC-03 Compose, RC-11
   hosted CI) — environmental, not application defects. Conditions
   for full GO in `PR07B_RELEASE_DECISION.md` §3.
3. **Two PARTIAL sub-gates** (RC-01 clean-checkout, RC-06 two-browser
   operator workflow) — evidence-scope limitations, not application
   defects. RC-01: the smoke script verifies prerequisites but a
   true clean-checkout reproduction was NOT executed. RC-06: HTTP-level
   concurrency is barrier-proven but a two-browser operator workflow
   was NOT executed. See `PR07B_TEST_MATRIX.md` §2 for the per-gate
   detail.
4. **Node 24 vs. declared Node 22** — the sandbox has Node 24; CI
   uses Node 22. All frontend checks pass on Node 24; the maintainer
   should verify on Node 22 (CI will do this automatically when the
   branch is pushed). No Node 24-specific feature is used.
5. **Compose-level nginx proxy behavior** (PR-07A carry): backend-level
   `$http_host` semantics verified in PR-06B; Compose-level proxy
   behavior is part of RC-03 (NOT RUN in this delivery).
6. **Anonymous mutation status code** (PR-07A carry): anonymous case
   mutations are rejected fail-closed with 403 `CSRF_TOKEN_INVALID`
   rather than 401 because the CSRF dependency evaluates first. No
   defect demonstrated; no change made. Recorded for a future
   API-polish PR.
7. **Verification honesty:** the Linux results (backend 574, frontend
   115, E2E 18→19, frozen 28/28, smoke 7/7) are the coding AI's
   previously-reported execution. They are NOT independently
   re-executed by the reviewer. The E2E suite was re-run only to
   verify the new test #19 passes alongside the existing 18. Windows,
   Docker, and PR-07B hosted CI remain NOT RUN until the maintainer
   executes them. Full GO is NOT claimed while required acceptance
   remains outstanding.

---

## 9. Scope compliance

- No PR-08 research integration; no CSV upload; no user-submitted
  datasets; no new scientific-data ingestion APIs; no live Isolation
  Forest/LOF execution; no PCA visualizations; no ULB/PMGSY-III
  integration; no new case types; no new scoring methods; no new
  anomaly thresholds; no new dashboards/layouts; no new auth
  providers; no new RBAC roles; no cloud/K8s; no CI platform
  changes; no dependency upgrades; no automatic non-idempotent
  mutation retries; no research-score recalculation; no frozen
  research artifact changes.
- API contracts unchanged (`openapi:check` no drift;
  `contracts.gen.ts` unchanged); architecture, authentication
  guarantees and desktop layout preserved (E2E suite — including the
  1024px desktop gate — green).
- All 28 frozen scientific artifacts preserved (28/28).
- Synthetic demonstration records remain explicitly labelled; no
  conflation with genuine research findings (K-series green).
- Zero production code changes (no defects found requiring correction).

---

## 10. Delivery manifest and integrity verification

`PEIARS_PR07B_changed_files.zip` (this bounded-correction delivery,
supersedes the previous ZIP) contains 10 new files plus 1 modified
file at their repository-relative paths, plus `PR07B_FILE_MANIFEST.csv`
at the archive root. `PR07B_FILE_MANIFEST.csv` records `path,sha256,bytes`
for every archive member. The archive was reopened after generation
and every member was verified against the manifest (byte size +
SHA-256 + UTF-8/no-BOM + LF endings); the ZIP's own SHA-256 is
recorded in the delivery message.

The bundle is built by reading each file's exact bytes from the
working tree on `pr-07b-rc-verification` (no production code is
modified; no local developer artifact is included).

**Excluded per contract §20a.4:** `.pgdata/`, `backend/.venv312/`,
`node_modules/`, `.env` files, temporary PostgreSQL directories,
browser profiles, session data, and other generated runtime artifacts.
Verified: none of these patterns appears in the archive or in
`git diff 351aded HEAD --stat`.

**Encoding per contract §20a.3:** every new text file is UTF-8
without BOM and uses LF (`\n`) line endings. The modified
`frontend/playwright/e2e.spec.ts` retains its original LF endings
(verified: no CRLF introduced). Binary files (none in this delivery)
would be preserved byte-for-byte.

---

## 11. Acceptance steps for the maintainer

1. Inspect `PEIARS_PR07B_changed_files.zip` and verify
   `PR07B_FILE_MANIFEST.csv` (byte size + SHA-256 for every member).
2. Apply the 10 new files + 1 modified file (`frontend/playwright/e2e.spec.ts`)
   at their repository-relative paths on `pr-07b-rc-verification`.
3. Run `python ci/pr07b_acceptance_smoke.py` — expect 7/7 PASS.
4. Run `bash frontend/scripts/run-e2e.sh` — expect 19 passed (18
   original + 1 new RC-05 integrated workflow test).
5. Execute `docs/acceptance/PR07B_WINDOWS_RUNBOOK.md` on Windows 11
   (RC-02); record results in `PR07B_EVIDENCE_REGISTER.md`.
6. Execute `docs/acceptance/PR07B_COMPOSE_RUNBOOK.md` on a
   Docker-equipped environment (RC-03); record results. Use the
   shell-specific (Git Bash / PowerShell) credential generation
   sections; do NOT use a single-quoted heredoc.
7. Push `pr-07b-rc-verification` to the remote; let the five GHA
   jobs run (RC-11); record the new run ID and per-job results.
8. Update `PR07B_TEST_MATRIX.md` and `PR07B_RELEASE_DECISION.md` with
   the new results. If the NOT RUN sub-gates PASS (with the documented
   Windows 11 harness-limitation exception) and the PARTIAL sub-gates
   are closed (RC-01 clean-checkout reproduction on a pristine
   machine; RC-06 two-browser operator workflow test), promote the
   decision from CONDITIONAL GO to GO.

---

**PR-07B is complete. No PR-08 work was started.**
