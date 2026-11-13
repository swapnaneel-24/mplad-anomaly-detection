# PR-07B Windows 11 Acceptance Runbook

**Milestone:** PR-07B — Release Candidate Acceptance
**Baseline commit:** `351aded20d4dca1b243f6db6846dcbc22dc6ff33`
**Target environment:** Windows 11 + PowerShell + Git Bash + Python 3.12.4 + Node 22 + Docker Desktop (optional)
**Execution owner:** maintainer (the coding AI is Linux-only and does NOT execute this runbook; actual Windows execution is **NOT RUN** by the coding AI).

This runbook is copy-ready: every command can be pasted directly into
a PowerShell or Git Bash session on a fresh Windows 11 machine with
the documented supported tools installed. It complements (does not
duplicate) the existing `docs/dev/LOCAL_STARTUP_WINDOWS.md`, which
covers environment setup from a fresh checkout.

---

## 1. Pre-flight checks (PowerShell)

Open PowerShell at the repository root.

```powershell
git status --short
git rev-parse HEAD
git branch --show-current
py -3.12 --version
node --version
npm --version
docker version
docker compose version
```

**Expected:**
- `git status --short` → empty (clean tree).
- `git rev-parse HEAD` → `351aded20d4dca1b243f6db6846dcbc22dc6ff33` (or the PR-07B verification commit on top of it).
- `git branch --show-current` → `pr-07b-rc-verification` (or the maintainer's chosen branch name).
- `py -3.12 --version` → `Python 3.12.4` (or any 3.12.x).
- `node --version` → `v22.x.x` (or any Node 22+).
- `docker version` → Docker Desktop running (if Compose acceptance is planned; otherwise optional).

If `py -3.12` is not available, install Python 3.12 from
https://www.python.org/downloads/windows/ (the "Add Python 3.12 to
PATH" checkbox must be checked). If `node` is not available, install
Node 22 LTS from https://nodejs.org/.

---

## 2. Backend acceptance (PowerShell)

### 2.1 Backend dependency installation

```powershell
cd backend
py -3.12 -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install --upgrade pip
.\.venv312\Scripts\python.exe -m pip install -r requirements-lock.txt
cd ..
```

If `.venv312` already exists from a prior session, skip the `venv`
creation step and just upgrade pip + reinstall the lockfile.

### 2.2 Backend pytest (real PostgreSQL via pgserver)

```powershell
cd backend
.\.venv312\Scripts\python.exe -m pytest -q
cd ..
```

**Expected result:** `574 passed` (or `573 passed, 1 failed` if the
Windows 11 `pgserver` trust-authentication limitation applies — see
§5 below and `PR07B_DEFECT_REGISTER.md` §2).

The `pgserver` package (`pgserver==0.1.4`, declared in
`backend/requirements-dev.txt` and pinned in
`backend/requirements-lock.txt`) bundles a real PostgreSQL 16.x server
that starts in-process on a disposable loopback Unix-domain socket
(on Windows, a loopback TCP port) with its own temporary data
directory. No external PostgreSQL service is required.

### 2.3 Backend imports + application factory smoke

```powershell
cd backend
.\.venv312\Scripts\python.exe -c "from app.main import create_app; app = create_app(); print(type(app).__name__)"
cd ..
```

**Expected:** `<class 'fastapi.applications.FastAPI'>` (or equivalent).

---

## 3. Frontend acceptance (PowerShell)

### 3.1 Frontend dependency installation

```powershell
cd frontend
npm ci
cd ..
```

`npm ci` requires `frontend/package-lock.json` (present in the
repository). It performs a clean install that matches the lockfile
exactly — no semver drift.

### 3.2 Frontend typecheck, lint, Vitest, build, OpenAPI

```powershell
cd frontend
npm run typecheck
npm run lint
npm run test -- --run
npm run build
npm run openapi:check
cd ..
```

**Expected:** all five commands exit 0. Vitest should report
`115 passed` (21 test files). The build should produce
`dist/index.html`, `dist/assets/index-*.css`, and
`dist/assets/index-*.js`. The OpenAPI check should print
`OK — contracts.gen.ts is up to date and contracts.ts has no drift.`

---

## 4. Browser E2E acceptance (Git Bash)

The E2E runner script (`frontend/scripts/run-e2e.sh`) is a Bash
script. On Windows, execute it via Git Bash (installed with Git for
Windows, or standalone from https://git-scm.com/download/win).

```bash
# In Git Bash, at the repository root:
cd frontend
npx playwright install chromium
bash scripts/run-e2e.sh
cd ..
```

**Expected:** `19 passed` (Playwright Chromium headless). The runner
starts a disposable pgserver PostgreSQL, a uvicorn backend on a free
port, and the Vite dev server, then exercises the full authenticated
investigation workflow (login → source selection → case creation →
note/transition/decision → reload → logout → re-login → persistence
verified) plus the desktop-layout assertions at 1024/1280/1366/1440
CSS pixels. Test #19 (added in the PR-07B bounded correction) runs
the full lifecycle as one continuous authenticated same-case browser
session.

If `npx playwright install chromium` fails on Windows, ensure the
Playwright system dependencies are installed
(`npx playwright install-deps chromium` on Linux; on Windows the
bundled installer handles dependencies automatically).

---

## 5. Windows 11 `pgserver` trust-authentication limitation (known)

**Affected test:**
`backend/tests/test_failure_classification.py::TestCredentialFailureClassification::test_wrong_password_readiness_503_sanitized`

**Observed Windows 11 result (maintainer-reported):**
`573 passed, 1 failed`. The identified test fails because the local
`pgserver` initializes PostgreSQL with `trust` authentication for
matching loopback connections (`127.0.0.1/32`), so an incorrect
password is accepted rather than rejected, and no 503 readiness
response is produced.

This is a **known harness limitation**, NOT an application defect.
Full attribution analysis in `PR07B_DEFECT_REGISTER.md` §2 and
`PR07B_ENVIRONMENT_MATRIX.md` §4.1. The production database-security
behavior (real PostgreSQL with `scram-sha-256` or md5 authentication)
is unchanged and is covered by the test on Linux / CI.

### 5.1 Optional verification via `scram-sha-256` (disposable)

If the maintainer wishes to verify incorrect-password rejection on
Windows 11 outside the `trust`-auth `pgserver` fixture, the procedure
is:

1. Start a disposable PostgreSQL 16 instance with `scram-sha-256`
   authentication (NOT via `pgserver`; use a manual `initdb` +
   `pg_ctl start` against a temporary `PGDATA` directory, with
   `password_encryption = scram-sha-256` in `postgresql.conf` and a
   `pg_hba.conf` entry requiring `scram-sha-256` for the test role).
2. Set `PEIARS_DATABASE_URL` to point at the disposable instance with
   the correct password.
3. Run the `test_wrong_password_readiness_503_sanitized` test against
   that instance (a small driver script or a `pytest -k
   test_wrong_password_readiness_503_sanitized --override-ini='addopts='`
   invocation with `PEIARS_DATABASE_URL` exported).
4. Assert the test passes (incorrect password → readiness 503
   sanitized).
5. Tear down the disposable instance and remove the temporary `PGDATA`
   directory.

This procedure is OPTIONAL and is the maintainer's responsibility on
their Windows environment. It is NOT required for PR-07B acceptance
(the Linux / CI result of 574/574 is the authoritative test count;
the Windows 573/574 is documented as a known harness limitation).

---

## 6. Frozen research integrity

```powershell
py -3.12 ci/check_frozen_integrity.py
```

**Expected:** `frozen-research integrity: 28/28 files match` / `OK`
(exit 0). The frozen manifest is `ci/frozen_research_manifest.json`.
No frozen research artifact may be modified to make the check pass.

---

## 7. Acceptance smoke check (single-command verifier)

```powershell
py -3.12 ci/pr07b_acceptance_smoke.py
```

**Expected:** `OK: all 7 smoke checks passed` (exit 0). This runs the
fast reproducibility preconditions (Python 3.12.x, Node >= 22,
lockfiles present, frozen 28/28, OpenAPI no drift). It does NOT run
the full backend pytest, frontend Vitest, or Playwright E2E suites —
those are the separate commands above.

---

## 8. Compose acceptance (if Docker Desktop is available)

See `docs/acceptance/PR07B_COMPOSE_RUNBOOK.md` for the full Compose
lifecycle procedure. If Docker Desktop is NOT available on this
Windows machine, mark RC-03 NOT RUN and proceed with the other gates.

---

## 9. Recording results

For each executed command, record in `PR07B_EVIDENCE_REGISTER.md`:

- The exact command (including the working directory).
- The observed stdout / exit code.
- The wall-clock duration (use `Measure-Command` in PowerShell or
  `time` in Git Bash).
- The execution timestamp (Windows local time + UTC offset).
- The Windows 11 build number (`winver` or
  `[System.Environment]::OSVersion.Version`).

Mark each gate as PASS / FAIL / PARTIAL / NOT RUN in
`PR07B_TEST_MATRIX.md` based on the observed results. If the Windows
11 result for `test_wrong_password_readiness_503_sanitized` is FAIL,
record it as `573 PASS / 1 FAIL (known harness limitation)` per
`PR07B_DEFECT_REGISTER.md` §2 — do NOT mark it as PASS.

---

## 10. Cleanup

- The `pgserver` test fixture creates a temporary data directory
  (under `$TMPDIR/peiars_pgtest_*` on Linux, or the Windows equivalent
  under `%TEMP%\peiars_pgtest_*`). It is removed automatically by the
  fixture teardown.
- The E2E runner creates a disposable pgserver instance and a uvicorn
  subprocess; both are torn down by the runner's cleanup trap.
- The `.venv312` directory and `node_modules/` are NOT cleaned up
  automatically — they are local developer artifacts that should NOT
  be committed or included in the delivery archive (per contract
  §20a.4).
- If you started a disposable `scram-sha-256` PostgreSQL instance for
  §5.1, tear it down with `pg_ctl stop -m fast -w` and remove the
  temporary `PGDATA` directory.
