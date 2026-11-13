# PR-07B Evidence Register

**Milestone:** PR-07B — Release Candidate Acceptance
**Baseline commit:** `351aded20d4dca1b243f6db6846dcbc22dc6ff33`
**Branch:** `pr-07b-rc-verification` (clean tree at `351aded`)
**Execution environment:** Linux sandbox (see `PR07B_ENVIRONMENT_MATRIX.md` §2)
**Execution date:** 2026-11-13 (UTC+8)

**Verification honesty note:** the Linux results below are the coding
AI's previously-reported execution from the first PR-07B delivery.
They are NOT independently re-executed by the reviewer. In this
bounded correction, the only re-executed check is the E2E suite (to
verify the new test #19 passes alongside the existing 18); the
remaining results (backend 574, frontend 115, frozen 28/28, smoke
7/7) are accepted as previously reported. Windows, Docker, and
PR-07B hosted CI remain NOT RUN until the maintainer executes them.

Every row below records an actually executed command, its observed
result, the supporting artifact (file, test name, or screenshot), and
the gate it satisfies. NOT RUN rows list the documented reason and
the maintainer action that would resolve them.

---

## 1. Repository state verification

| Check | Command | Observed result | Evidence |
|---|---|---|---|
| Clean tree | `git status --short` | (empty — clean working tree) | captured 2026-11-13 |
| Branch | `git branch --show-current` | `pr-07b-rc-verification` | captured |
| HEAD SHA | `git rev-parse HEAD` | `351aded20d4dca1b243f6db6846dcbc22dc6ff33` | captured |
| Last commit | `git log -1 --oneline` | `351aded Merge pull request #1 from swapnaneel-24/integration/pr07a-hardening` | captured |
| Ancestor check | `git merge-base --is-ancestor 351aded HEAD && echo OK` | `OK: 351aded is ancestor of HEAD` | captured |
| Branch creation | `git checkout -b pr-07b-rc-verification` | `Switched to a new branch 'pr-07b-rc-verification'` | captured |

**Gate:** RC-01 (baseline verification). **Result:** PASS.

---

## 2. Environment versions

| Check | Command | Observed result | Evidence |
|---|---|---|---|
| Python | `python3 --version` | `Python 3.12.16` | captured |
| Python implementation | `python3 -c "import sys; print(sys.implementation.name)"` | `cpython` | captured |
| Node | `node --version` | `v24.22.2` | captured |
| npm | `npm --version` | `11.19.1` | captured |
| pgserver | `python3 -c "import pgserver; print(pgserver.__file__)"` | `/home/z/.venv/lib/python3.12/site-packages/pgserver/__init__.py` | captured |
| Playwright | `npx playwright --version` | `Version 1.65.0` | captured |
| Chromium headless shell | `ls /home/z/.cache/ms-playwright/chromium_headless_shell-1254/` | present (158.0.8127.18 / v1254) | captured |
| Docker | `docker --version` | `command not found` | captured — NOT RUN |
| Compose | `docker compose version` | `command not found` | captured — NOT RUN |
| Platform | `uname -a` | `Linux ... 5.10.134-013.15.kangaroo.al8.x86_64 ... x86_64 GNU/Linux` | captured |

**Gate:** RC-01 (reproducibility) + RC-02/RC-03 NOT RUN justification.
**Result:** PASS for the Linux environment; RC-02 Windows and RC-03
Compose NOT RUN (documented platform limitations, see
`PR07B_ENVIRONMENT_MATRIX.md` §4).

---

## 3. Backend pytest (real PostgreSQL)

| Item | Value |
|---|---|
| Command | `cd backend && python -m pytest -q --tb=line` |
| Working directory | `/home/z/my-project/pr07a-work/peiars-baseline/backend` |
| Python interpreter | `/home/z/.venv/bin/python3` (CPython 3.12.16) |
| Database | disposable pgserver PostgreSQL 16.x (session-scoped, data dir under `$TMPDIR/peiars_pgtest_*`) |
| Result | **574 passed**, 583 warnings, 57.88 s |
| Exit code | 0 |
| Reference baseline | 574/574 (maintainer-reported, CI run `43395916677`) |
| Delta vs. baseline | 0 (no regression; no new tests; no removed tests) |

**Gate:** RC-05/RC-06/RC-07/RC-08/RC-09 (server-side invariants).
**Result:** PASS.

---

## 4. Frontend typecheck

| Item | Value |
|---|---|
| Command | `cd frontend && npm run typecheck` |
| Tool | `tsc --noEmit` |
| Result | (no output — exit 0) |
| Exit code | 0 |

**Gate:** RC-01 (reproducibility) + RC-04 (UI compile readiness).
**Result:** PASS.

---

## 5. Frontend lint

| Item | Value |
|---|---|
| Command | `cd frontend && npm run lint` |
| Tool | `eslint . --max-warnings=0` |
| Result | (no output — exit 0) |
| Exit code | 0 |

**Gate:** RC-01 (reproducibility). **Result:** PASS.

---

## 6. Frontend Vitest

| Item | Value |
|---|---|
| Command | `cd frontend && npm run test` |
| Tool | `vitest run` |
| Result | `Test Files  21 passed (21)` / `Tests  115 passed (115)` / `Duration  21.27s` |
| Exit code | 0 |
| Reference baseline | 115/115 (maintainer-reported) |
| Delta vs. baseline | 0 |

**Gate:** RC-04/RC-05/RC-07-D/RC-07-E/RC-07-F (frontend invariants).
**Result:** PASS.

---

## 7. Frontend production build

| Item | Value |
|---|---|
| Command | `cd frontend && npm run build` |
| Tool | `tsc --noEmit && vite build` |
| Result | `✓ 78 modules transformed.` / `dist/index.html 0.68 kB` / `dist/assets/index-CtdbDZ8f.css 29.65 kB` / `dist/assets/index-jvnIiDRl.js 237.58 kB` / `map: 948.80 kB` / `✓ built in 1.34s` |
| Exit code | 0 |

**Gate:** RC-01 (reproducibility). **Result:** PASS.

---

## 8. OpenAPI drift check

| Item | Value |
|---|---|
| Command | `cd frontend && npm run openapi:check` |
| Tool | `node scripts/check-openapi.mjs` |
| Result | `OK — contracts.gen.ts is up to date and contracts.ts has no drift.` |
| Exit code | 0 |

**Gate:** RC-01 (contract stability) + RC-08 (API contract unchanged).
**Result:** PASS.

---

## 9. Browser E2E (Chromium + real backend + pgserver)

Two executions are recorded: the first PR-07B delivery (tests #1-#18,
previously reported) and this bounded correction (tests #1-#19,
re-run to verify the new test #19 passes).

### 9a. First PR-07B delivery (previously reported, not independently re-executed by the reviewer)

| Item | Value |
|---|---|
| Command | `bash frontend/scripts/run-e2e.sh` |
| Working directory | `frontend/` |
| Browser | Playwright Chromium headless shell 158.0.8127.18 (v1254) |
| Backend | disposable pgserver + uvicorn `app.main:create_app --factory` on a free port |
| Database | disposable pgserver PostgreSQL 16.x (separate from the pytest fixture) |
| Result | `18 passed (31.2s)` |
| Exit code | 0 |
| Notable tests | #1 login; #2-#4 source selection + case creation; #5-#7 note/transition/decision; #11 409 conflict + draft preserved; #13 409 reload recovery; #15 sync failure after confirmed POST (RC-07-D); #16 screenshots at 1440×900 + 1366×768 (RC-04); #17 DesktopGate at 1023 vs 1024 (RC-04); #18 no horizontal overflow at 1024/1280/1366/1440 (RC-04) |
| Pre-execution note | The Playwright Chromium binary was not cached in the recycled sandbox at first run; after `npx playwright install chromium` (158.0.8127.18 / v1254, 125.9 MiB) the suite passed 18/18. No application defect was involved. |

### 9b. Bounded correction re-run (this correction — actually executed)

| Item | Value |
|---|---|
| Command | `bash frontend/scripts/run-e2e.sh` |
| Working directory | `frontend/` |
| Browser | Playwright Chromium headless shell 158.0.8127.18 (v1254) |
| Backend | disposable pgserver + uvicorn `app.main:create_app --factory` on a free port |
| Database | disposable pgserver PostgreSQL 16.x (separate from the pytest fixture) |
| Result | `19 passed (34.3s)` |
| Exit code | 0 |
| New test | #19 `RC-05 integrated workflow: full authenticated lifecycle in one session` (2.7s) — one continuous authenticated same-case browser workflow: login → select record → create case → add note → transition → decision → verify history → refresh (same session) → verify persistence → logout → re-login → verify case still available |
| Pre-execution note | The Playwright Chromium binary was not cached in the recycled sandbox; re-installed via `npx playwright install chromium` before the re-run. |
| Post-execution cleanup | `git checkout -- frontend/screenshots/` reverted the four regenerated screenshot PNGs — they are NOT part of the frozen manifest but binary churn was excluded from the delivery regardless. |

**Gate:** RC-04 (desktop layout) + RC-05 (full workflow, now including
the integrated continuous scenario via test #19) + RC-07-D (failed
GET). **Result:** PASS.

---

## 10. Frozen research integrity

| Item | Value |
|---|---|
| Command | `python ci/check_frozen_integrity.py` |
| Tool | `ci/check_frozen_integrity.py` (reads `ci/frozen_research_manifest.json`) |
| Result | `frozen-research integrity: 28/28 files match` / `OK` |
| Exit code | 0 |
| Verification count | 2 (once during Stage 3 baseline; once via `ci/pr07b_acceptance_smoke.py`) |

**Gate:** RC-10. **Result:** PASS.

---

## 11. Acceptance smoke check

| Item | Value |
|---|---|
| Command | `python ci/pr07b_acceptance_smoke.py` |
| Tool | `ci/pr07b_acceptance_smoke.py` (added by PR-07B) |
| Commit recorded by the tool | `351aded20d4dca1b243f6db6846dcbc22dc6ff33` |
| Result | `OK: all 7 smoke checks passed` (Python 3.12.x, Node >= 22, lockfiles present, frozen 28/28, OpenAPI no drift) |
| Exit code | 0 |

**Gate:** RC-01 (reproducibility verifier). **Result:** PASS.

---

## 12. NOT RUN — Windows 11 acceptance (RC-02)

| Item | Value |
|---|---|
| Reason | The coding AI executes in a Linux-only sandbox; Windows 11 is not available. |
| Documented procedure | `docs/acceptance/PR07B_WINDOWS_RUNBOOK.md` |
| Maintainer action | Execute the runbook on Windows 11; record results here. Expected result: 573 PASS / 1 FAIL (known harness limitation — see `PR07B_DEFECT_REGISTER.md` §2). |
| Optional verification | Verify incorrect-password rejection using a disposable PostgreSQL instance configured with `scram-sha-256` (see Windows runbook §5). |

---

## 13. NOT RUN — Docker Compose release lifecycle (RC-03)

| Item | Value |
|---|---|
| Reason | No Docker Engine or Compose v2 plugin in the sandbox (`docker --version` → `command not found`). |
| Documented procedure | `docs/acceptance/PR07B_COMPOSE_RUNBOOK.md` |
| Reference CI | GitHub Actions run `43395916677` reports the container job (build + Compose smoke, 11 checks) green on `351aded`. |
| Maintainer action | Execute the runbook on a Docker-equipped environment (Linux or Windows with Docker Desktop); record results here. |

---

## 14. NOT RUN — GitHub-hosted CI (RC-11)

| Item | Value |
|---|---|
| Reason | The `pr-07b-rc-verification` branch has not been pushed to the remote. |
| Workflow file | `.github/workflows/ci.yml` (unchanged by PR-07B) |
| Reference CI run | `43395916677` — 5/5 jobs green on `351aded` (backend-tests, frozen-integrity, frontend, e2e, container) |
| Maintainer action | Push `pr-07b-rc-verification` to the remote; let the five jobs run; record the new run ID and per-job results here. |

---

## 15. Production code change delta

| Item | Value |
|---|---|
| Files changed in PR-07B | 9 markdown docs under `docs/acceptance/` + 1 Python script (`ci/pr07b_acceptance_smoke.py`) + 1 modified E2E test file (`frontend/playwright/e2e.spec.ts`, +89 lines for test #19) + `PR07B_FILE_MANIFEST.csv` (delivery-only) |
| Production source files changed | **0** |
| Backend application code changes | **0** |
| Frontend application code changes | **0** |
| Database migrations added/modified | **0** |
| Frozen research artifacts modified | **0** (28/28 match) |
| API contract changes | **0** (`openapi:check` no drift; `contracts.gen.ts` unchanged) |
| New tests added | **1** (E2E test #19, RC-05 integrated workflow — added in this bounded correction to close the gap between individual-step coverage and proof of one continuous authenticated same-case browser workflow) |

**Result:** No release-blocking defect was found; no production code
change was required. PR-07B is a documentation-and-acceptance-script
delivery plus one focused E2E test that closes the RC-05
integrated-workflow evidence gap.

---

## 16. Sanitization verification

| Property | Verified |
|---|---|
| No real session cookies in any artifact | PASS — all session cookies in tests are deterministic test-only values (e.g. `peiars_session=test-session-...`) |
| No CSRF tokens in any artifact | PASS — all CSRF tokens in tests are deterministic test-only values |
| No signing secrets in any artifact | PASS — `PEIARS_SESSION_SECRET` is always a documented test-only secret ≥ 32 chars |
| No PostgreSQL passwords in any artifact | PASS — pgserver uses trust authentication on a loopback Unix socket; no password is set or logged |
| No `.env` files included | PASS — no `.env` file is in the diff |
| No database data directories included | PASS — no `.pgdata/` or `peiars_pgtest_*` directory is in the diff |
| No runtime dumps included | PASS |
| No access tokens included | PASS |
| No personal user data included | PASS — all test users are synthetic (`reviewer`, `viewer`, `admin`, `attr-reviewer`, `boundary-reviewer`, `persist-reviewer`, `restart-reviewer`) |
| No browser profiles included | PASS |
| No virtual environments included | PASS — `.venv/`, `node_modules/` excluded from the diff |
| No Docker volumes included | PASS |
| Screenshots use synthetic content | PASS — E2E screenshots use only synthetic demonstration records |
| No invented wall-clock durations | PASS — all durations above are observed at execution time |
| Exact commit SHAs retained | PASS — `351aded`, `2176140`, `d6d4afc`, `d594d06` retained where known |
