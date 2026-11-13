# PR-07B Test Matrix

**Milestone:** PR-07B — Release Candidate Acceptance
**Baseline commit:** `351aded20d4dca1b243f6db6846dcbc22dc6ff33`
**Branch:** `pr-07b-rc-verification`
**Execution environment:** Linux sandbox (see `PR07B_ENVIRONMENT_MATRIX.md` §2)

**Counting method:** RC-07 is split into six sub-gates (A through F).
The matrix below lists 16 technical-verification sub-gates (RC-01
through RC-07-F, RC-08 through RC-11) plus RC-12 as the release
decision itself. RC-12 is NOT a technical-verification gate; it is
the decision based on the 16 sub-gates. Results reported below are
the coding AI's previously-reported Linux execution; they are NOT
independently re-executed by the reviewer.

---

## 1. Coverage summary

| Gate | Title | Status | Evidence |
|---|---|---|---|
| RC-01 | Clean-checkout reproducibility | **PARTIAL** | Prerequisite smoke checks PASS (`ci/pr07b_acceptance_smoke.py`); reused-environment regression PASS (existing `test_env_boot.py` etc.); actual clean-checkout reproduction NOT RUN |
| RC-02 | Windows 11 local acceptance | **NOT RUN** | Procedure in `PR07B_WINDOWS_RUNBOOK.md`; not executed by the Linux-only coding AI |
| RC-03 | Docker Compose release lifecycle | **NOT RUN** | Procedure in `PR07B_COMPOSE_RUNBOOK.md`; no Docker daemon in sandbox |
| RC-04 | Desktop layout (1024/1280/1366/1440) | **PASS** | E2E #16/#17/#18 |
| RC-05 | Full authenticated investigation workflow | **PASS** | E2E tests #1-#9 (individual steps) + new E2E test #19 (one continuous authenticated same-case browser workflow, added in this correction) |
| RC-06 | Concurrent reviewer | **PARTIAL** | HTTP-level concurrency PASS (`test_concurrency_http.py` C1 barrier-proven); two-browser operator workflow with visible conflict recovery NOT RUN |
| RC-07-A | Backend restart | **PASS** | `test_restart_outage_recovery.py` I1/I2 |
| RC-07-B | Database unavailable | **PASS** | `test_restart_outage_recovery.py` I3/I4/I5/I6 |
| RC-07-C | Unmigrated or outdated database | **PASS** | `test_db_readiness.py` J1-J8 |
| RC-07-D | Confirmed POST + failed follow-up GET | **PASS** | `test_persistence_equivalence.py` integrated E1 + E2E #15 |
| RC-07-E | Uncertain POST outcome | **PASS** | `mutation-reliability.test.tsx` NOTE timeout test |
| RC-07-F | Stale response race | **PASS** | `conflict-recovery-race.test.tsx` + `stale-selection-races.test.tsx` |
| RC-08 | Security integration | **PASS** | `test_rbac_boundary_sweep.py`, `test_csrf_origin_invariants.py`, `test_event_attribution_and_routes.py`, existing auth suite |
| RC-09 | Provenance and scientific honesty | **PASS** | `test_synthetic_boundary_sweep.py` K5/K6 + existing |
| RC-10 | Frozen research integrity | **PASS** | `ci/check_frozen_integrity.py` 28/28 |
| RC-11 | GitHub Actions (5 jobs) | **NOT RUN** | Branch not pushed; reference run `43395916677` for `351aded` |
| RC-12 | Release-candidate decision (NOT a technical gate) | **CONDITIONAL GO** | `PR07B_RELEASE_DECISION.md` — based on the 16 sub-gates above |

**Technical-verification sub-gate totals (16 entries):**
11 PASS, 0 FAIL, 2 PARTIAL (RC-01, RC-06), 3 NOT RUN (RC-02, RC-03, RC-11).

**Release decision (RC-12, separate from the 16 sub-gates):**
CONDITIONAL GO.

The 3 NOT RUN sub-gates and the 2 PARTIAL sub-gates are
environmental or evidence-scope limitations, not application
defects. See `PR07B_ENVIRONMENT_MATRIX.md` §4 and the per-gate
detail below.

---

## 2. Per-gate detail

### RC-01 — Clean-checkout reproducibility — **PARTIAL**

Three levels of evidence are distinguished:

| Level | Description | Status | Evidence |
|---|---|---|---|
| Prerequisite checks | Python 3.12.x, Node >= 22, lockfiles present, frozen manifest present, frozen integrity 28/28, OpenAPI no drift | **PASS** | `ci/pr07b_acceptance_smoke.py` (7/7 PASS) |
| Reused-environment regression | `.env` discovery + override precedence, required env vars, fail-closed secret validation, explicit migration workflow, no implicit migration at startup, no reliance on globally-installed packages, no pre-populated cases | **PASS** | Existing `test_env_boot.py`, `test_db_config_validation.py`, `test_dependency_lock.py`, `test_migrations.py`, `test_app_factory.py` (all part of the 574 backend pytest) |
| Actual clean-checkout reproduction | Fresh `git clone` → new Python venv → `npm ci` from scratch → full suite execution on a pristine machine | **NOT RUN** | The coding AI's sandbox is NOT a fresh checkout (deps were installed in a prior session; the venv is reused). The maintainer should execute this on a clean machine (Windows 11 or Linux) and record the result. |

**Why PARTIAL:** the smoke script verifies prerequisites (Python/Node
versions, lockfile presence, frozen integrity, OpenAPI no drift) but
does NOT prove a fresh-checkout installation. The existing backend
tests verify configuration and migration behavior in a
reused-environment regression, not a clean-checkout reproduction.
A true clean-checkout reproduction (fresh clone → new venv →
`npm ci` → full suite) was NOT executed by the coding AI. The
maintainer should execute the Windows runbook
(`PR07B_WINDOWS_RUNBOOK.md`) or the POSIX equivalent on a pristine
machine to close this gap.

**Counting:** the seven-check smoke script result (7/7 PASS) is
reported as the prerequisite-checks layer, NOT as proof of RC-01
as a whole.

### RC-02 — Windows 11 local acceptance — **NOT RUN**

The coding AI executes in a Linux-only sandbox. The Windows 11
acceptance procedure is documented copy-ready in
`PR07B_WINDOWS_RUNBOOK.md`. The maintainer should execute it on
Windows 11 and record the results in `PR07B_EVIDENCE_REGISTER.md`.

Known Windows 11 platform limitation: the
`TestCredentialFailureClassification::test_wrong_password_readiness_503_sanitized`
test is expected to FAIL on Windows 11 with `pgserver` trust
authentication (see `PR07B_ENVIRONMENT_MATRIX.md` §4.1 and
`PR07B_DEFECT_REGISTER.md` §2). Expected Windows result:
**573 PASS / 1 FAIL (known harness limitation)**.

### RC-03 — Docker Compose release lifecycle — **NOT RUN**

No Docker Engine or Compose v2 plugin in the sandbox. The Compose
lifecycle procedure is documented copy-ready in
`PR07B_COMPOSE_RUNBOOK.md`. The maintainer should execute it on a
Docker-equipped environment and record the results.

The Compose design (`compose.yaml`), the container smoke test
(`ci/container_smoke_test.sh`, 11 checks), and the CI container job
are unchanged by PR-07B. The maintainer's reference CI run
`43395916677` reports 11/11 container smoke checks passing on
`351aded`.

### RC-04 — Desktop layout acceptance — **PASS**

| Width | Method | Result |
|---|---|---|
| 1024 CSS px | E2E #17 (DesktopGate at 1023 vs 1024) + E2E #18 (no overflow at 1024) | PASS |
| 1280 CSS px | E2E #18 (no overflow at 1280) | PASS |
| 1366 CSS px | E2E #18 (no overflow at 1366) + E2E #16 (screenshot at 1366×768) | PASS |
| 1440 CSS px | E2E #18 (no overflow at 1440) + E2E #16 (screenshot at 1440×900) | PASS |

The E2E suite captures Chromium screenshots at 1440×900 and 1366×768
(test #16) and asserts no page-wide horizontal overflow at every
supported width (test #18). The DesktopGate component renders the
mobile/desktop breakpoint at 1024 CSS px (test #17). The investigation
workspace three-column layout (record/case index + case detail/evidence
+ history/review controls) is exercised by tests #1-#15.

### RC-05 — Full authenticated investigation workflow — **PASS**

Two levels of evidence:

| Level | Description | Status | Evidence |
|---|---|---|---|
| Individual workflow steps | Each step of the workflow (login, source selection, case creation, note, transition, decision, history, refresh, logout, re-login) covered by separate E2E tests, each starting with a fresh login | **PASS** | E2E tests #1-#9 (each step verified independently against real PostgreSQL + Chromium) |
| One continuous authenticated same-case browser workflow | A single test that runs the full lifecycle in one browser page with one authenticated session: login → select record → create case → add note → transition → decision → verify history → refresh (same session) → verify persistence → logout → re-login → verify case still available | **PASS** | New E2E test #19 (`RC-05 integrated workflow: full authenticated lifecycle in one session`, added in this correction) |

E2E test #19 was added in this bounded correction to close the gap
between individual-step coverage and proof of one continuous
workflow. It uses the existing Playwright harness (no second E2E
runner), creates its own case with a unique title
(`RC-05 integrated ${Date.now()}`) to avoid collision with the case
created by test #3, and verifies the full lifecycle in one
authenticated session.

**Expected result:** the real authenticated review lifecycle
completes without duplicate events, lost changes, incorrect source
identity or authorization bypass. Verified: E2E test #19 passed
(2.7s) alongside the existing 18 tests (19 total, 34.3s).

### RC-06 — Concurrent reviewer acceptance — **PARTIAL**

Two levels of evidence are distinguished (per contract §11:
"Do not falsely claim simultaneity if the scenario only verifies a
sequential stale-version conflict. Report those as separate levels
of evidence."):

| Level | Description | Status | Evidence |
|---|---|---|
| Database atomicity (HTTP-level concurrency) | Two separately authenticated reviewer TestClients over the pgserver-backed app; both read version N; both POST notes with `expected_version=N`, released simultaneously by a dispatch barrier; a second in-flight barrier inside `before_cursor_execute` fires only when both transactions are about to execute `UPDATE review_cases` | **PASS** | `test_concurrency_http.py::test_genuine_independent_sessions_conflict` (C1) — exactly one 200 + one 409; final version N+1; exactly one new event; winner's UUID attributed; `test_repeated_stale_mutation_stays_409` (C3) — stays 409 until fresh version supplied |
| Two-browser operator workflow with visible conflict recovery | Two real browser sessions (two reviewer identities); both load the same case; reviewer A submits; reviewer B submits with stale version; reviewer B sees a 409 conflict in the UI; reviewer B reloads and retries successfully | **NOT RUN** | A two-browser Playwright test (two browser contexts, two sessions, timing coordination) was NOT added in this correction. The existing E2E tests #11 and #13 cover single-browser conflict recovery with a mocked 409, but NOT a two-browser concurrent workflow. |

**Why PARTIAL:** the HTTP-level concurrency is proven with a
genuine in-flight UPDATE barrier (the barrier firing at all is the
overlap proof). However, the integrated two-browser operator
workflow — where a second reviewer sees the conflict in the UI and
recovers in real time — was NOT executed. The contract §11
explicitly permits reporting these as separate levels of evidence
rather than claiming the HTTP-level test proves the full
operator-visible scenario.

### RC-07 — Failure injection and recovery — **PASS (A-F)**

| Sub-scenario | Test | Result |
|---|---|---|
| RC-07-A Backend restart | `test_restart_outage_recovery.py::test_full_scenario` I1/I2 | PASS — case/events byte-identical after SIGTERM/restart; DB-backed session survives; logout still revokes |
| RC-07-B Database unavailable | `test_restart_outage_recovery.py` I3/I4/I5/I6 | PASS — readiness 503 with all probes non-ready; liveness 200; no stale healthy state; recovery to 200; write succeeds (pool recovery) |
| RC-07-C Unmigrated or outdated | `test_db_readiness.py` J1-J8 | PASS — unmigrated → readiness detects; explicit migration → readiness recovers; liveness ≠ DB readiness proxy |
| RC-07-D Confirmed POST + failed GET | `test_persistence_equivalence.py::test_confirmed_post_then_failed_get_then_recovery_leaves_exactly_one_event` + E2E #15 | PASS — POST 200 → armed 503 → GET /history 503 SERVICE_NOT_READY → recovery GET 200 → exactly one event; UI no duplicate POST |
| RC-07-E Uncertain POST outcome | `mutation-reliability.test.tsx` NOTE: POST timeout test | PASS — no auto-retry; distinct "Write outcome unknown" copy; draft preserved; POST count stays 1 |
| RC-07-F Stale response race | `conflict-recovery-race.test.tsx` B3-1/2/3 + `stale-selection-races.test.tsx` B1/B2/B4 | PASS — generation guards at :163/:202/:207/:214/:217 and `handleReloadAfterConflict` prevent stale detail/history/evidence/conflict-recovery from overwriting the current selection |

All failure injection is isolated to test-owned resources (disposable
pgserver, test-owned uvicorn subprocess, ephemeral ports). Bounded
deadline polling throughout — no arbitrary sleeps.

### RC-08 — Security integration acceptance — **PASS**

| Property | Test | Result |
|---|---|---|
| Valid login | `test_auth_login.py` | PASS |
| Logout invalidation | `test_auth_sessions.py::test_logout_replay_fails` | PASS |
| Former cookie replay rejected | `test_auth_sessions.py` | PASS |
| Session expiry (absolute + idle) | `test_auth_sessions.py` + `test_csrf_origin_invariants.py` F1 (`expires_at = now()` boundary) | PASS |
| Session rotation | `test_auth_csrf.py` (login rotates CSRF token) + `test_csrf_origin_invariants.py` H4 (pre-login token replay after rotation rejected) | PASS |
| Protected endpoint access rejected after invalidation | `test_auth_sessions.py` | PASS |
| Session cookie HttpOnly | `test_auth_cookies.py::TestProductionCookiePolicy` | PASS |
| SameSite policy | `test_auth_cookies.py` | PASS |
| Production Secure requirement | `test_env_boot.py` + `test_auth_cookies.py` | PASS |
| Dev loopback relaxation | `test_auth_cookies.py` | PASS |
| CSRF cookie readability | `test_auth_cookies.py` | PASS |
| Viewer allowed reads | `test_auth_rbac.py` + `test_rbac_boundary_sweep.py` G1 | PASS |
| Viewer direct API mutation rejected (4 routes) | `test_rbac_boundary_sweep.py` G2-G6 | PASS — 403 + zero rows + zero events |
| Reviewer permitted writes | `test_case_api.py` | PASS |
| Admin-only ops inaccessible to unauthorized roles | `test_rbac_boundary_sweep.py` G8 (executable N/A — no admin-only HTTP route exists) | PASS |
| Rejected writes produce no case/event change | `test_rbac_boundary_sweep.py` G2-G6 + `test_event_attribution_and_routes.py` D2 | PASS |
| Valid same-origin request succeeds | `test_auth_csrf.py` | PASS |
| Missing CSRF rejected | `test_auth_csrf.py` | PASS |
| Invalid CSRF rejected | `test_auth_csrf.py` | PASS |
| Pre-login token replay after rotation rejected | `test_csrf_origin_invariants.py` H4 | PASS |
| Authenticated cross-origin write rejected | `test_csrf_origin_invariants.py` H5/H7 | PASS — 403 with valid session + valid CSRF + disallowed Origin; no mutation |
| nginx proxy behavior preserved | Compose-level NOT RUN; backend `$http_host` semantics verified in PR-06B | PARTIAL (backend-level only) |
| Production missing/placeholder secrets rejected | `test_env_boot.py` | PASS |
| Production insecure cookies rejected | `test_env_boot.py` + `test_auth_cookies.py` | PASS |
| No sensitive values in startup logs | `test_auth_no_leakage.py` | PASS |

### RC-09 — Provenance and scientific honesty — **PASS**

| Assertion | Test | Result |
|---|---|---|
| Synthetic records visibly synthetic | `test_synthetic_boundary_sweep.py` + existing `test_case_api.py::TestSyntheticSource` | PASS — `SYNTHETIC DEMONSTRATION RECORD — NOT A RESEARCH FINDING` label + `synthetic: true` flag |
| Demonstration-source access explicitly configured | `test_source_registry.py` + `test_synthetic_boundary_sweep.py` | PASS — empty registry when `demonstration_sources=false` |
| Case refs retain dataset/snapshot/record | `test_case_api.py` round-trip | PASS |
| Synthetic payloads not exposed when disabled | `test_synthetic_boundary_sweep.py::test_no_get_endpoint_exposes_synthetic_content` (non-parameterized) + `test_parameterized_gets_do_not_leak_synthetic_payload_with_persisted_case` (parameterized with persisted case) | PASS |
| No synthetic-as-validated ULB/MPLADS/PMGSY | `test_synthetic_boundary_sweep.py` + `test_no_confirmed_fraud_status` | PASS |
| Interface does not assert anomaly = fraud | E2E #10 ("does not display fabricated anomaly scores") + UI banner assertions | PASS |
| No new scientific models/scores by acceptance scripts | Inspection — no new model code in PR-07B diff | PASS |
| No actual public-data ingestion | Inspection — no new ingestion code in PR-07B diff | PASS |

### RC-10 — Frozen research integrity — **PASS**

`ci/check_frozen_integrity.py`: **28/28 files match** at `351aded`
(exit 0). Verified twice: once during Stage 3 baseline execution, once
via `ci/pr07b_acceptance_smoke.py`. No frozen research artifact was
modified by PR-07B.

### RC-11 — GitHub Actions and reproducibility — **NOT RUN**

The `pr-07b-rc-verification` branch has not been pushed to the remote.
The five workflow jobs have NOT executed against the PR-07B commit.
The reference CI run `43395916677` is for commit `351aded` (the
accepted baseline) and is referenced as the pre-PR-07B state, NOT as
PR-07B CI evidence.

The maintainer should push `pr-07b-rc-verification` and let the five
jobs run:
1. backend-tests (Python 3.12 + real PostgreSQL)
2. frozen-integrity (SHA-256)
3. frontend (Node 22 — typecheck, lint, Vitest, build, OpenAPI)
4. e2e (Chromium + real backend + pgserver)
5. container (build + Compose smoke, 11 checks)

No workflow file was changed by PR-07B; least-privilege permissions
and SHA-pinned actions are untouched.

### RC-12 — Release-candidate decision — **CONDITIONAL GO**

See `PR07B_RELEASE_DECISION.md` for the full assessment. Summary:
of the 16 technical-verification sub-gates, 11 PASS, 2 PARTIAL
(RC-01 prerequisite-only, RC-06 HTTP-level-only), and 3 NOT RUN
(RC-02 Windows, RC-03 Compose, RC-11 hosted CI). No sub-gate FAILed.
The release candidate is suitable for a clearly bounded next use
(controlled synthetic demonstration, read-only scientific adapter
development) pending maintainer execution of the NOT RUN gates and
closure of the PARTIAL evidence gaps.

---

## 3. Test totals at `351aded` + bounded correction (Linux sandbox)

The results below are the coding AI's previously-reported Linux
execution. They are NOT independently re-executed by the reviewer.
The bounded correction added one new E2E test (#19, RC-05 integrated
workflow); the E2E suite was re-run to verify the new test passes
alongside the existing 18.

| Suite | Command | Result | Source |
|---|---|---|---|
| Backend pytest | `python -m pytest -q` (real pgserver PostgreSQL) | **574 passed**, 57.9 s | previously reported |
| Frontend typecheck | `npm run typecheck` | PASS | previously reported |
| Frontend lint | `npm run lint` (`--max-warnings=0`) | PASS | previously reported |
| Frontend Vitest | `npm run test -- --run` | **115 passed** (21 files), 21.3 s | previously reported |
| Frontend build | `npm run build` | PASS | previously reported |
| OpenAPI drift | `npm run openapi:check` | PASS (no drift) | previously reported |
| Browser E2E (previously reported) | `bash frontend/scripts/run-e2e.sh` | **18 passed**, 31.2 s | previously reported (tests #1-#18) |
| Browser E2E (this correction) | `bash frontend/scripts/run-e2e.sh` | **19 passed**, 34.3 s | re-run after adding test #19 (RC-05 integrated workflow) |
| Frozen research integrity | `python ci/check_frozen_integrity.py` | **28/28 match**, exit 0 | previously reported; re-verified |
| Acceptance smoke | `python ci/pr07b_acceptance_smoke.py` | **7/7 PASS**, exit 0 | previously reported; re-verified |

No regression vs. the accepted PR-07A baseline (which also reported
574/115/18/28). No production code change in this PR-07B delivery;
the only code change is the addition of E2E test #19 (a test, not
application code).
