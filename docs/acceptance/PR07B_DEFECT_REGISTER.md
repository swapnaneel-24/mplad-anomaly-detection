# PR-07B Defect Register

**Milestone:** PR-07B — Release Candidate Acceptance
**Baseline commit:** `351aded20d4dca1b243f6db6846dcbc22dc6ff33`
**Branch:** `pr-07b-rc-verification`

---

## 1. Confirmed release-blocking defects — **NONE**

No release-blocking defect was found during PR-07B acceptance
execution. Of the 16 technical-verification sub-gates, 11 PASS, 2
PARTIAL (RC-01 prerequisite-only, RC-06 HTTP-level-only), and 3 NOT
RUN (RC-02 Windows, RC-03 Compose, RC-11 hosted CI). No sub-gate
FAILed. The PARTIAL and NOT RUN sub-gates are environmental or
evidence-scope limitations, not application defects — see
`PR07B_ENVIRONMENT_MATRIX.md` §4 for the documented platform
limitations.

**Production code change delta in PR-07B: zero.** No backend
application code, no frontend application code, no migrations, no API
contract changes, no frozen-research artifacts modified. The delivery
is documentation (`docs/acceptance/*.md`) plus one acceptance
automation script (`ci/pr07b_acceptance_smoke.py`) plus one new E2E
test (#19, RC-05 integrated workflow, added to the existing
`frontend/playwright/e2e.spec.ts` — a test, not application code).

---

## 1a. Bounded corrections (independent archive audit feedback)

Independent inspection of the first `PEIARS_PR07B_changed_files.zip`
identified five documentation/harness issues that required resolution
before maintainer execution. All five are corrected in this revised
delivery; no production code was changed.

1. **Compose env-file generation** (`PR07B_COMPOSE_RUNBOOK.md`): the
   single-quoted heredoc delimiter (`<<'EOF'`) prevented command
   substitution, writing literal `$(openssl rand ...)` strings into
   `.env.compose`. Corrected: separate Git Bash and PowerShell
   sections with safe, shell-specific credential generation
   (unquoted heredoc for Bash; `Set-Content` with
   `[System.Security.Cryptography.RandomNumberGenerator]` for
   PowerShell). Added `docker compose config` secret-display warning
   (redirect output to `/dev/null` / `$null`; inspect exit code only).
2. **Acceptance counting inconsistency**: the summary said "12 PASS"
   but the detailed matrix listed 13 PASS sub-gate entries (RC-07
   split into 6 sub-gates) plus 3 NOT RUN plus 1 CONDITIONAL GO.
   Corrected: explicit sub-gate counting method — 16
   technical-verification sub-gates (11 PASS, 2 PARTIAL, 3 NOT RUN)
   plus RC-12 as the release decision (separate from the 16). Totals
   updated consistently across all reports.
3. **Evidence scope for RC-01, RC-05, RC-06**: corrected to
   distinguish prerequisite checks from clean-checkout reproduction
   (RC-01: PARTIAL); individual E2E tests from one continuous
   integrated workflow (RC-05: PASS — closed by adding E2E test #19);
   HTTP-level concurrency from two-browser operator workflow (RC-06:
   PARTIAL).
4. **Compose lifecycle evidence and cleanup**: corrected the runbook
   to add bounded-poll readiness with a deadline-failure path (exits
   non-zero if the deadline is exceeded); authenticated case/history
   persistence checks after each restart; project-label-gated volume
   removal (verifies the volume's `com.docker.compose.project` label
   matches the disposable project name BEFORE removing — does NOT
   assume a hardcoded volume name); clear operator-input steps marked
   `[OPERATOR INPUT]` replacing non-executable placeholders.
5. **Verification honesty preserved**: the Linux results (backend 574,
   frontend 115, E2E 18→19, frozen 28/28, smoke 7/7) are the coding
   AI's previously-reported execution — NOT independently
   re-executed by the reviewer. The E2E suite was re-run only to
   verify the new test #19. Windows, Docker, and PR-07B hosted CI
   remain NOT RUN. Full GO is NOT claimed.

**Net production code delta in this bounded correction: zero.** The
only code change is the addition of E2E test #19 (a test, not
application code) to close the RC-05 integrated-workflow evidence gap.

### 1b. Final runbook corrections (third-round audit feedback)

Independent verification of the corrected ZIP identified five
runbook-level issues that required resolution before maintainer
execution. All five are corrected in this revision; no production
code, no E2E tests, and no security assertions were changed.

1. **Compose outage sequence** (`PR07B_COMPOSE_RUNBOOK.md` §3.8):
   replaced the conflicting §3.8 / §3.8.1 / §3.8.2 structure (which
   interleaved `restart db` with `stop db` in a confusing order) with
   a single linear, safe sequence: stop DB → assert readiness 503 and
   liveness 200 → start DB → bounded-poll to readiness 200 → verify
   authenticated case/history persistence. Every failure path has an
   explicit recovery/cleanup instruction; the script auto-starts the
   DB before exiting on assertion failure so the stack is left
   recoverable.
2. **PowerShell HTTP 503 handling**: added a `Get-HttpStatus` helper
   function that catches `Invoke-WebRequest`'s terminating error on
   4xx/5xx responses and returns the status code (e.g. 503) without
   an uncaught error. Connection failures (no HTTP response) return
   `0` and fail the assertion. Unexpected responses still fail
   clearly.
3. **PowerShell elapsed time**: replaced the incorrect
   `(Get-Date) - (Get-Date).AddSeconds(-60)` calculation (which always
   evaluated to ~60) with `System.Diagnostics.Stopwatch` —
   `$Stopwatch.Elapsed.TotalSeconds` gives the actual elapsed time.
   The Git Bash version uses `SECONDS - $START` (correct).
4. **E2E count 18→19**: updated all stale expected totals across the
   nine reports. The Windows runbook, acceptance plan, release
   decision, defect register, and environment matrix now consistently
   reference 19 E2E tests (18 original + test #19). Historical
   references in the evidence register §9a (the first-delivery result
   of 18 tests) are preserved as factually accurate historical
   context, clearly labeled as "previously reported."
5. **Admin password security** (`PR07B_COMPOSE_RUNBOOK.md` §3.6):
   added clipboard-based password delivery — the generated password
   is copied to the clipboard (`xclip`/`clip` for Git Bash;
   `Set-Clipboard` for PowerShell) so the operator can paste it into
   the browser login form without it appearing on screen. After
   login, both the shell variable and the clipboard are cleared
   explicitly. The `create_admin` CLI does NOT print the password
   (verified by `ci/container_smoke_test.sh`).

**Net production code delta in this final correction: zero.** Only
markdown documentation files were modified.

---

## 2. Known platform limitation — Windows 11 pgserver trust authentication

**Classification:** known harness limitation (NOT an application
defect). Documented per contract §20a.1.

**Affected test:**
`backend/tests/test_failure_classification.py::TestCredentialFailureClassification::test_wrong_password_readiness_503_sanitized`

**Platform behavior (maintainer-reported, contract §20a.1):**
On Windows 11, the local `pgserver` test harness initializes PostgreSQL
with `trust` authentication for matching loopback connections
(`127.0.0.1/32`). Under that authentication configuration, an
incorrect password does NOT cause a server-side authentication failure
that would surface as a 503 readiness response — the connection is
accepted regardless of the supplied password.

**Observed results:**

| Environment | Result | Source |
|---|---|---|
| Linux sandbox (this delivery) | **574 PASS / 0 FAIL** — the test passes | `python -m pytest -q` executed 2026-11-13 |
| GitHub-hosted CI (Ubuntu) | **574 PASS / 0 FAIL** — the test passes | reference run `43395916677` |
| Windows 11 (maintainer local) | **573 PASS / 1 FAIL** — the identified test fails because the incorrect password is not rejected under `trust` authentication | maintainer-reported; contract §20a.1 |

**Attribution analysis (per contract §20a.1 requirement 2):**

The Windows failure is attributable to the documented PostgreSQL
`trust` authentication configuration of the local `pgserver` test
harness on Windows 11, NOT to an application defect, on the following
grounds:

1. The test asserts that an incorrect password produces a 503
   readiness response. Under `trust` authentication, PostgreSQL
   accepts any password (including an incorrect one) for matching
   loopback connections, so no authentication failure occurs and the
   readiness probe stays 200.
2. The test passes on Linux and GitHub-hosted CI (Ubuntu), where
   `pgserver`'s bundled PostgreSQL does not use `trust`
   authentication for the test fixture — the incorrect password is
   rejected as expected, producing the 503 readiness response the
   test asserts.
3. The production database-security behavior (real PostgreSQL with
   `scram-sha-256` or md5 authentication) is unchanged and is covered
   by:
   - `test_failure_classification.py` on Linux / CI.
   - `test_db_readiness.py` (auth-failure readiness 503 sanitized via
     disposable SCRAM fixture).
   - `test_db_config_validation.py` (production config rejection).

**Requirements satisfied (per contract §20a.1):**

| Requirement (§20a.1) | Satisfied | Evidence |
|---|---|---|
| 1. Record the discrepancy explicitly | YES | this section; `PR07B_ENVIRONMENT_MATRIX.md` §4.1 |
| 2. Confirm Windows failure attributable to documented auth config | YES | attribution analysis above |
| 3. Preserve original PR-06A credential-failure test and production DB security behavior | YES | no test modified; no auth logic modified |
| 4. No weakened assertions, no unconditional skips, no marked-as-PASS failures | YES | the test is unchanged; on Linux/CI it passes; on Windows it fails honestly |
| 5. Optional verification via disposable `scram-sha-256` PostgreSQL | DOCUMENTED | `PR07B_WINDOWS_RUNBOOK.md` §5 |
| 6. Report Windows outcome accurately as 573 PASS / 1 FAIL (known harness limitation) | YES | this section; `PR07B_ENVIRONMENT_MATRIX.md` §4.1; `PR07B_TEST_MATRIX.md` RC-02 |

**Scope of the exception:** This exception applies ONLY to the
identified test and confirmed harness configuration. It does not waive
other readiness, credential-handling or database-security requirements.

**Resolution path:** The maintainer may either (a) accept the Linux
574/574 result as the authoritative test count and document the
Windows 573/574 as a known harness limitation (the path taken by this
register), or (b) verify incorrect-password rejection on Windows
using a disposable PostgreSQL instance configured with `scram-sha-256`
(see `PR07B_WINDOWS_RUNBOOK.md` §5 for the procedure). Option (b) is
optional and is the maintainer's responsibility on their Windows
environment.

---

## 3. Non-blocking observations

### 3.1 Node 24 vs. declared Node 22

The Linux sandbox used for this delivery has Node v24.22.2 installed;
the documented supported Node version is 22.x (`.github/workflows/ci.yml`,
`actions/setup-node@v5.0.0` with `node-version: "22"`). The frontend
toolchain (Vite 5, Vitest 2, ESLint 9, tsc 5.6) runs unchanged on
Node 24; all frontend checks (typecheck/lint/Vitest/build/OpenAPI)
passed. No Node 24-specific feature is used by the test suite or the
production code. The maintainer should verify on Node 22 separately
if exact-version parity is required (the GitHub Actions CI job uses
Node 22, so pushing the branch will provide that verification
automatically).

**Classification:** non-blocking observation; no action required for
PR-07B acceptance.

### 3.2 Playwright Chromium binary not cached in the recycled sandbox

The first E2E attempt failed with
`browserType.launch: Executable doesn't exist at .../chromium_headless_shell-1254/...`
because the Playwright browser binary was not cached in the recycled
sandbox. After `npx playwright install chromium` (158.0.8127.18 / v1254,
125.9 MiB) the suite passed 19/19 (18 original tests + test #19 added
in the bounded correction). This is an environment provisioning
step, not an application defect.

**Classification:** environmental; no action required for PR-07B
acceptance (the CI workflow installs Playwright browsers as part of
its setup).

### 3.3 Anonymous mutation status code (carried from PR-07A)

PR-07A defect log §3 noted that anonymous case mutations are rejected
fail-closed with 403 `CSRF_TOKEN_INVALID` rather than 401 because the
CSRF dependency evaluates first. This is fail-closed (no mutation, no
event, no row) and is asserted in `test_rbac_boundary_sweep.py::G9`.
No defect is demonstrated; no change was made. Recorded for a future
API-polish PR if the maintainer wants 401 to surface first.

**Classification:** non-blocking observation; carried from PR-07A;
no action required for PR-07B acceptance.

---

## 4. Severity classification summary

| Defect / observation | Severity | Status | Action |
|---|---|---|---|
| Release-blocking defects | n/a | NONE FOUND | none |
| Windows 11 pgserver trust auth limitation | known harness limitation | DOCUMENTED | maintainer may verify via `scram-sha-256` (optional) |
| Node 24 vs. declared Node 22 | non-blocking observation | DOCUMENTED | CI will verify on Node 22 when branch is pushed |
| Playwright Chromium cache miss | environmental | RESOLVED | `npx playwright install chromium` |
| Anonymous mutation 403 vs. 401 (PR-07A carry) | non-blocking observation | DOCUMENTED | future API-polish PR if desired |

No defect in this register requires a production code change for
PR-07B acceptance.
