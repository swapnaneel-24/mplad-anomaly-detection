# PR-07B Environment Matrix

**Milestone:** PR-07B — Release Candidate Acceptance
**Baseline commit:** `351aded20d4dca1b243f6db6846dcbc22dc6ff33` (`main`, PR #1 merge)
**Branch:** `pr-07b-rc-verification` (created from `351aded`)
**Document purpose:** record the environments actually used to execute
PR-07B acceptance, the supported combinations declared by the
repository, and the environment-specific limitations that gate which
RC scenarios could be executed.

---

## 1. Supported runtimes (declared by the repository)

| Component | Declared support | Source |
|---|---|---|
| Python | CPython 3.12.x (validated on 3.12.16) | `backend/requirements-lock.txt` header; `backend/pyproject.toml` |
| Node.js | 22.x (the frontend CI job is named "Frontend (Node 22)") | `.github/workflows/ci.yml`, `frontend/package.json` |
| PostgreSQL | 16.x (bundled by `pgserver==0.1.4`) | `backend/requirements-dev.txt`; `compose.yaml` (`postgres:16-alpine`) |
| Docker / Compose | Engine v2+ with `docker compose` v2 plugin | `compose.yaml` (Compose spec), `ci/container_smoke_test.sh` |
| Playwright | 1.65.x (Chromium headless shell 158.0.8127.18 / v1254) | `frontend/package.json` (`@playwright/test`), `frontend/playwright.config.ts` |
| OS | Linux (CI), Windows 11 (maintainer local), macOS not declared | `.github/workflows/ci.yml` (`runs-on: ubuntu-latest`), `docs/dev/LOCAL_STARTUP_WINDOWS.md` |

Unsupported combinations are listed in §4.

---

## 2. Executed environment — Linux sandbox (this delivery)

| Component | Version | Source / verification |
|---|---|---|
| Operating system | Linux 5.10.134-013.15.kangaroo.al8.x86_64 (Alibaba Cloud Linux kernel; glibc 2.41) | `uname -a` |
| Python | CPython 3.12.16 (implementation `cpython`) | `python3 --version`; `sys.implementation.name` |
| Node.js | v24.22.2 (npm 11.19.1) | `node --version`; `npm --version` |
| PostgreSQL | 16.x via `pgserver==0.1.4` (disposable in-process server, real PostgreSQL binaries) | `backend/requirements-dev.txt`; `pgserver.__file__` |
| Playwright | 1.65.0; Chromium headless shell 158.0.8127.18 (v1254) | `npx playwright --version`; `/home/z/.cache/ms-playwright/chromium_headless_shell-1254/` |
| Docker / Compose | **Not installed** in this sandbox | `docker --version` → `command not found` |
| Git | 2.x (current) | `git --version` |

Notes:
- Node 24 is newer than the documented supported Node 22. The frontend
  toolchain (Vite 5, Vitest 2, ESLint 9, tsc 5.6) runs unchanged on
  Node 24; all frontend checks (typecheck/lint/Vitest/build/OpenAPI)
  passed. The GitHub Actions CI job uses Node 22 (`.github/workflows/ci.yml`,
  `actions/setup-node@v5.0.0` with `node-version: "22"`); the maintainer
  should verify on Node 22 separately if exact-version parity is
  required. No Node 24-specific feature is used by the test suite or
  the production code.
- The Playwright Chromium binary was not cached in the recycled sandbox
  at first run; after `npx playwright install chromium` the E2E suite
  passed 19/19 (18 original tests + test #19 added in the bounded
  correction). This is an environment provisioning step, not an
  application defect.

---

## 3. Executed environment — maintainer-reported (PR-07A acceptance, run `43395916677`)

| Component | Version | Source |
|---|---|---|
| Operating system | Ubuntu (GitHub Actions `ubuntu-latest`) | `.github/workflows/ci.yml` |
| Python | 3.12 (GitHub Actions `actions/setup-python@v5.6.0`) | `.github/workflows/ci.yml` |
| Node.js | 22 (GitHub Actions `actions/setup-node@v5.0.0`) | `.github/workflows/ci.yml` |
| PostgreSQL | 16.x via `pgserver` (CI) | `.github/workflows/ci.yml` backend-tests job |
| Docker / Compose | Docker Engine + Compose v2 (GitHub Actions `ubuntu-latest` default) | `.github/workflows/ci.yml` container job |
| Playwright | 1.65.x; Chromium bundled by `@playwright/test` | `.github/workflows/ci.yml` e2e job |
| Reported results | Backend 574/574, frontend 115/115, E2E passed, container smoke 11/11, frozen 28/28, 5/5 jobs green | GitHub Actions run `43395916677` (referenced; not re-run for PR-07B in this sandbox) |

The maintainer also reports a Windows 11 local environment (PowerShell
+ Git Bash, Python 3.12.4, Node 22, Docker Desktop when available) in
`docs/dev/LOCAL_STARTUP_WINDOWS.md`.

---

## 4. Known unsupported combinations and platform limitations

### 4.1 Windows 11 `pgserver` trust authentication limitation

**Affected test:**
`backend/tests/test_failure_classification.py::TestCredentialFailureClassification::test_wrong_password_readiness_503_sanitized`

**Platform behavior (maintainer-reported):**
On Windows 11, the local `pgserver` test harness initializes PostgreSQL
with `trust` authentication for matching loopback connections
(`127.0.0.1/32`). Under that authentication configuration, an
incorrect password does NOT cause a server-side authentication failure
that would surface as a 503 readiness response — the connection is
accepted regardless of the supplied password.

**Observed result on Windows 11:** 573 PASS / 1 FAIL (the identified
test fails because the incorrect password is not rejected).

**Observed result on Linux / GitHub-hosted CI:** 574 PASS / 0 FAIL
(the `pgserver`-packaged PostgreSQL on Linux does not use trust
authentication for the test fixture; the incorrect password is
rejected as expected).

**Attribution:**
The Windows failure is attributable to the documented PostgreSQL
`trust` authentication configuration of the local `pgserver` test
harness on Windows 11, NOT to an application defect. The production
database-security behavior (real PostgreSQL with `scram-sha-256` or
md5 authentication) is unchanged and is covered by:

- `test_failure_classification.py` on Linux / CI (incorrect password
  → readiness 503 sanitized).
- `test_db_readiness.py` (auth-failure readiness 503 sanitized via
  disposable SCRAM fixture).
- `test_db_config_validation.py` (production config rejection).

**Requirements satisfied (per contract §20a.1):**
1. This discrepancy is recorded explicitly in this matrix and in
   `docs/acceptance/PR07B_DEFECT_REGISTER.md` §2.
2. The Windows failure is confirmed attributable to the documented
   PostgreSQL authentication configuration before classification as a
   known harness limitation.
3. The original PR-06A credential-failure test and production database
   security behavior are preserved — no assertion is weakened, no
   unconditional skip is added, no authentication logic is modified,
   and the failing test is NOT marked PASS.
4. The Linux / CI result (574/574) remains the authoritative test
   count; the Windows 11 result is reported accurately as
   **573 PASS / 1 FAIL (known harness limitation)**.
5. Optional verification using a disposable PostgreSQL instance
   configured with `scram-sha-256` is documented in the Windows
   runbook (§5 of `PR07B_WINDOWS_RUNBOOK.md`); this is the
   maintainer's responsibility on their Windows environment.

This exception applies only to the identified test and confirmed
harness configuration. It does not waive other readiness,
credential-handling or database-security requirements.

### 4.2 Docker not available in the PR-07B execution sandbox

The Linux sandbox used for this delivery does not have a Docker
Engine or Compose v2 plugin installed. All container runtime scenarios
(RC-03 Compose lifecycle, RC-07-A backend container restart, RC-07-B
database container restart, RC-07-C unmigrated-database-via-Compose)
are marked **NOT RUN** in the test matrix. The Compose design
(`compose.yaml`), the container smoke test
(`ci/container_smoke_test.sh`, 11 checks), and the CI container job
are unchanged by PR-07B and remain the maintainer's responsibility on
a Docker-equipped environment.

### 4.3 Windows 11 acceptance not executed by the coding AI

The coding AI executes in a Linux-only sandbox. The Windows acceptance
procedure is documented copy-ready in
`docs/acceptance/PR07B_WINDOWS_RUNBOOK.md` but the actual Windows
execution is **NOT RUN** by the coding AI. The maintainer should
execute the runbook on Windows 11 and record the results in the
evidence register.

### 4.4 GitHub-hosted CI not executed against the PR-07B commit

The `pr-07b-rc-verification` branch has not been pushed to the remote.
The five workflow jobs (backend-tests, frozen-integrity, frontend,
e2e, container) have therefore NOT executed against the PR-07B commit.
The reference CI run `43395916677` is for the pre-PR-07B state
(commit `351aded`) and is referenced as the accepted baseline, NOT as
PR-07B CI evidence. The maintainer should push the branch and let the
five jobs run before final merge.

### 4.5 macOS

macOS is not declared as a supported operating system by the
repository or the CI workflow. No acceptance scenario is executed on
macOS in this delivery.

---

## 5. Environment verification commands

The reproducibility of the executed environment can be verified with
`ci/pr07b_acceptance_smoke.py` (added by PR-07B), which checks
Python 3.12.x, Node >= 22, presence of the lockfiles, frozen research
integrity (28/28), and OpenAPI no-drift, in a single command:

```bash
python3.12 ci/pr07b_acceptance_smoke.py
```

The full environment inventory (per CI) is in
`.github/workflows/ci.yml` and `docs/dev/CONFIGURATION_INVENTORY.md`.
The Windows local startup guide is in
`docs/dev/LOCAL_STARTUP_WINDOWS.md`. The POSIX local startup guide is
in `docs/dev/LOCAL_STARTUP_POSIX.md`.
