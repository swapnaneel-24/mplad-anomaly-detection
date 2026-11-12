# PEIARS Local Development — Windows 11 Startup Guide

**PR-06A** — Environment Normalization and Deterministic Local Reproducibility

This guide takes a developer with a **fresh checkout** on Windows 11 from
zero to a running PEIARS investigation workbench, **without editing any
application source code**.

---

## Conventions used in this guide

* **Repository root (`<repo-root>`)** — the checkout folder that contains
  `backend/`, `frontend/`, and `docs/`. Wherever `<repo-root>` appears,
  substitute your actual path, for example
  `C:\dev\mplad-anomaly-detection`. You can check you are in the right
  place with `dir` — it must list `backend` and `frontend`.
* **One PowerShell session** runs Stages 1–6 and 8–10. Stage 7 (the
  frontend dev server) uses a second window because it occupies its
  terminal.
* **Every stage states its working directory** in the heading, and every
  code block contains the exact `cd` commands needed to get there from
  the repository root. Each stage that changes directory ends by
  returning to `<repo-root>`, so the stages can be executed in sequence
  by copy-paste with no ambiguity about the current location.
* The backend virtual environment (created in Stage 2) stays activated
  for the rest of the session; `cd` does not deactivate it.

---

## Prerequisites

| Software | Version | Verification |
|---|---|---|
| Python | **3.12.x** — the version the backend dependency pins and test suite are validated on (Linux test runner; Windows runtime verification is pending) | `python --version` |
| Node.js | 22 LTS (or 24 LTS) | `node --version` |
| npm | 10.x+ | `npm --version` |
| PostgreSQL | 16.x (running locally) | `psql --version` |

> **PostgreSQL note:** any reachable PostgreSQL 16+ instance works — a
> local Windows service, a Docker container, or a remote host. The
> application supports a fully configurable endpoint via
> `PEIARS_DATABASE_URL`; nothing is hardcoded.

---

## Stage 1 — Verify prerequisites

*Working directory: `<repo-root>`*

```powershell
python --version     # expect: Python 3.12.x
node --version       # expect: v22.x or v24.x
npm --version        # expect: 10.x or higher
psql --version       # expect: psql (PostgreSQL) 16.x or higher
```

If `python` is not found, install from https://python.org (check "Add to
PATH"). **Use Python 3.12.x** — the backend dependencies are pinned and
validated on 3.12 (Linux test runner), and `serve.py` requires the
Windows selector event-loop policy that psycopg 3 needs (see the
troubleshooting table below for what happens on an interpreter that does
not provide it).

If `psql` is not found, install PostgreSQL from https://postgresql.org or
use a Docker container:

```powershell
docker run --name peiars-pg -e POSTGRES_PASSWORD=peiars -p 5432:5432 -d postgres:16
```

---

## Stage 2 — Install backend dependencies

*Working directory: `<repo-root>\backend` (returns to `<repo-root>` at the end)*

```powershell
cd <repo-root>
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..
```

Notes:

* `requirements.txt` contains the pinned direct runtime dependencies.
  For the full transitive freeze use `pip install -r requirements-lock.txt`
  (both files agree on every shared pin).
* If script execution is blocked:
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

---

## Stage 3 — Install frontend dependencies

*Working directory: `<repo-root>\frontend` (returns to `<repo-root>` at the end)*

```powershell
cd <repo-root>
cd frontend
npm ci
cd ..
```

> **`npm ci` on a fresh checkout:** `npm ci` is exactly the right command
> when `node_modules` does not exist yet — that is its purpose. It works
> from a clean checkout as long as the committed `package-lock.json` is
> valid and in sync with `package.json`; it then installs precisely the
> lockfile contents. (`npm ci` also deletes any pre-existing
> `node_modules` first, which is expected.) If npm reports that the
> lockfile is out of sync, run `npm install` once and commit the updated
> `package-lock.json`.

---

## Stage 4 — Configure the environment

*Working directory: `<repo-root>`*

```powershell
cd <repo-root>
Copy-Item backend\.env.example .env
notepad .env
```

Edit `.env` and set:

| Variable | Value | Notes |
|---|---|---|
| `PEIARS_DATABASE_URL` | `postgresql+psycopg://peiars_app:YOUR_PASSWORD@localhost:5432/peiars_review` | Full SQLAlchemy URL |
| `PEIARS_DATABASE_REQUIRED` | `true` | Fail-closed if the database is unreachable |
| `PEIARS_SESSION_SECRET` | (generate below — do NOT keep `CHANGE_ME`) | Template placeholders are rejected at startup |
| `PEIARS_SESSION_COOKIE_SECURE` | `false` | Required for local HTTP |
| `PEIARS_DEMONSTRATION_SOURCES` | `true` | Enables synthetic records |

Generate a session secret (cryptographically secure, .NET CSPRNG). The
command below uses the **instance-based** API —
`RandomNumberGenerator.Create()` plus the instance `GetBytes(byte[])`
method — because those exist on every .NET version from .NET Framework
2.0 (Windows PowerShell 5.1) through modern .NET (PowerShell 7+); the
STATIC `RandomNumberGenerator.GetBytes` overloads are .NET Core / .NET 5+
only and do not exist on .NET Framework:

```powershell
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$bytes = New-Object byte[] 32
$rng.GetBytes($bytes)
$secret = -join ($bytes | ForEach-Object { $_.ToString('x2') })

# Shape check: 32 cryptographically random bytes hex-encoded must be
# exactly 64 lowercase hexadecimal characters.
$secret.Length                     # expect: 64
$secret -cmatch '^[0-9a-f]{64}$'   # expect: True
```

Paste the resulting 64-character hex string as the
`PEIARS_SESSION_SECRET` value in `.env`.

Then verify the real application validator accepts it (run from
`backend` with the venv still active; the secret travels via an
environment variable and is never printed or stored in shell history):

```powershell
cd <repo-root>
cd backend
$env:PEIARS_SESSION_SECRET = $secret
python -c "from app.core.config import Settings; Settings(_env_file=None); print('Settings validator: accepted')"
Remove-Item Env:\PEIARS_SESSION_SECRET
cd ..
```

> **PowerShell versions:** the instance-based command above is the one
> form compatible with BOTH Windows PowerShell 5.1 (.NET Framework) and
> PowerShell 7+ (.NET 6+) by API availability. This project's test
> runner executes on Linux and CANNOT run PowerShell — run the shape
> check and the validator check above on your machine (no Windows
> PowerShell execution is claimed by this repository's tests).

> **Why not `Get-Random`?** `Get-Random` is not a cryptographic RNG.
> The signing secret must come from `RandomNumberGenerator` (or
> `openssl rand -hex 32` on POSIX). Do not keep the `CHANGE_ME`
> placeholder: the application validates the secret at startup and
> refuses placeholder values **even when they are long enough** to pass
> the minimum-length check.

> **Never commit `.env`.** It contains your local credentials.

---

## Stage 5 — Set up the database

### 5a. Create the database and role

*Working directory: `<repo-root>`*

```powershell
cd <repo-root>
psql -U postgres -c "CREATE USER peiars_app WITH PASSWORD 'YOUR_PASSWORD';"
psql -U postgres -c "CREATE DATABASE peiars_review OWNER peiars_app;"
```

### 5b. Apply Alembic migrations

*Working directory: `<repo-root>\backend` (returns to `<repo-root>` at the end)*

```powershell
cd <repo-root>
cd backend
alembic upgrade head
cd ..
```

`alembic` reads `PEIARS_DATABASE_URL` from the repository-root `.env`
automatically — the same file the backend loads at startup (explicitly
exported environment variables still take precedence over the file), so
no manual export is needed. If PostgreSQL is not reachable you will get
a connection error from `alembic` itself; check the URL in `.env` and
that the server is running.

### 5c. Verify migrations

*Working directory: `<repo-root>\backend` (returns to `<repo-root>` at the end)*

```powershell
cd <repo-root>
cd backend
alembic current    # expect: 0003_add_users_sessions_auth (head)
cd ..
```

This step matters: it shows WHICH revision is applied. The readiness
endpoint (Stage 6) now also verifies migration state and fails with the
`migrations` check when the schema is absent or outdated — but
`alembic current` is the canonical, explicit verification immediately
after upgrading.

### 5d. Create the first admin user

*Working directory: `<repo-root>\backend` (returns to `<repo-root>` at the end)*

```powershell
cd <repo-root>
cd backend
$env:PEIARS_BOOTSTRAP_ADMIN_PASSWORD = "YourAdminPassword123!"
python scripts\create_admin.py --username admin --display-name "Administrator"
Remove-Item Env:\PEIARS_BOOTSTRAP_ADMIN_PASSWORD
cd ..
```

`create_admin.py` is the repository's offline administrator bootstrap
CLI. It refuses duplicate usernames, never displays the password, and
reads the database URL from the same `.env` file.

### 5e. Create a reviewer (for testing the investigation workflow)

*Working directory: `<repo-root>\backend` (returns to `<repo-root>` at the end)*

The repository ships one idempotent user-provisioning script —
`frontend\playwright\setup-reviewer.py` — used by the E2E suite to
create a reviewer account. It reads the database URL from the same
`.env` file and leaves an existing user untouched.

```powershell
cd <repo-root>
cd backend
$env:PEIARS_E2E_USERNAME = "reviewer1"
$env:PEIARS_E2E_PASSWORD = "ReviewerPass123!"
python ..\frontend\playwright\setup-reviewer.py
Remove-Item Env:\PEIARS_E2E_USERNAME, Env:\PEIARS_E2E_PASSWORD
cd ..
```

---

## Stage 6 — Start the backend

*Working directory: `<repo-root>\backend` (this terminal stays busy while the server runs)*

```powershell
cd <repo-root>
cd backend
.\.venv\Scripts\Activate.ps1
python scripts\serve.py
```

**Expected output** (captured on the validated Linux environment; on
Windows the event-loop line reads `WindowsSelectorEventLoopPolicy` —
that is the selector policy `serve.py` installed before uvicorn
started):

```
Serving PEIARS API v0.4.0 on http://127.0.0.1:8000
[peiars] environment: development
[peiars] event loop: WindowsSelectorEventLoopPolicy
[peiars] database required: True
[peiars] database configured: yes
[peiars] demonstration sources: enabled
[peiars] session secret: configured
[peiars] api prefix: /api/v1
[peiars] docs: enabled
API prefix: /api/v1 (docs: /docs)
INFO:     Uvicorn running on http://127.0.0.1:8000
```

> **Windows asyncio:** `serve.py` installs the
> `WindowsSelectorEventLoopPolicy` on Windows before uvicorn creates its
> event loop. This is required because psycopg 3 cannot use the Proactor
> loop (Python's Windows default). Supported interpreters: **CPython
> 3.12.x** — the version the backend dependency pins and test suite are
> validated on (Linux test runner); Windows runtime verification is
> pending and must be done on a real machine (the win32 tests in this
> repository simulate the platform with mocks — they are not runtime
> evidence). If a future Python no longer provides the policy class,
> `serve.py` fails at startup with an actionable error instead of
> silently starting on the incompatible default.

Verify the backend is healthy (in a second prompt or after Ctrl+C is
NOT pressed — the server must keep running):

```powershell
curl http://127.0.0.1:8000/api/v1/health/live
# {"status":"alive","service":"PEIARS API","version":"0.4.0"}

curl http://127.0.0.1:8000/api/v1/health/ready
# {"status":"ready","checks":[{"name":"postgresql","status":"ready"},{"name":"migrations","status":"ready"}]}
```

> **What readiness verifies:** the `postgresql` check proves
> connectivity (`SELECT 1`); the `migrations` check proves — read-only —
> that the database's `alembic_version` equals the committed migrations'
> head. A reachable but unmigrated (or outdated) database fails with
> HTTP 503 and the failed `migrations` check while `postgresql` stays
> ready, so the two failure classes are distinguishable. Migrations are
> never applied automatically at startup; the remediation is always an
> explicit `alembic upgrade head` (Stage 5b).

---

## Stage 7 — Start the frontend

Open a **new** PowerShell window (the Stage 6 terminal is busy serving
the API):

```powershell
cd <repo-root>\frontend
npm run dev
```

**Expected output:**

```
VITE v5.x  ready in xxx ms
➜  Local:  http://127.0.0.1:5173/
```

Open http://127.0.0.1:5173/ in a browser (window width ≥ 1024 CSS pixels).

---

## Stage 8 — Authenticate and smoke-test

1. The browser redirects to `/login`.
2. Sign in with the reviewer credentials (e.g. `reviewer1` / `ReviewerPass123!`).
3. Navigate to **Investigations** (tab 04).
4. The left panel lists **synthetic demonstration records** (`synth-001` … `synth-010`).
5. Click a record → the evidence panel shows its metadata with the
   `SYNTHETIC DEMONSTRATION RECORD` banner.
6. Fill the **Create review case** form → **Create case**.
7. Add a note, apply a status transition, record a decision.
8. The append-only event history appears in the right panel.

---

## Stage 9 — Verify persistence across restart

1. Create a case with a distinctive title.
2. Press `Ctrl+C` in both the backend and frontend terminals.
3. Restart the backend (`cd <repo-root>\backend; .\.venv\Scripts\Activate.ps1; python scripts\serve.py`)
   and the frontend (`cd <repo-root>\frontend; npm run dev`).
4. Log in again and open Investigations.
5. The previously created case is still listed — data is persisted in
   PostgreSQL.

---

## Stage 10 — Graceful shutdown

Press `Ctrl+C` in the backend and frontend terminals. The backend's
shutdown event disposes the database connection pool cleanly.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `psycopg.InterfaceError` on backend start | Proactor event loop on Windows | Use `python scripts\serve.py` (it installs the selector policy). Do NOT use `uvicorn app.main:create_app --factory` directly on Windows — that path does not install the policy. |
| `RuntimeError: asyncio.WindowsSelectorEventLoopPolicy is not available...` at startup | The interpreter does not provide the selector policy psycopg 3 requires (PEIARS refuses to start on unknown defaults) | Install **Python 3.12.x**, recreate `backend\.venv`, and rerun. See `SUPPORTED_PYTHON_VERSIONS` in `backend/scripts/serve.py`. |
| Readiness `503` with failed check `migrations` | The database is reachable but its schema is not at the committed head (never migrated, or an older revision) | Run `alembic upgrade head` from `backend/` (Stage 5b), then re-check `/api/v1/health/ready`. The check is read-only; migrations are never applied automatically at startup. |
| Pydantic `ValidationError` mentioning `cors_origins ... comma-separated` | `PEIARS_CORS_ORIGINS` is not a plain comma-separated origin list (e.g. JSON-array syntax, a wildcard `*`, or an origin with a path) | Use the documented form: `PEIARS_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173`. Wildcards are prohibited because credentials are enabled. |
| Pydantic `ValidationError` mentioning `session_secret ... placeholder` | The `CHANGE_ME` template value (or another placeholder) is still in `.env` | Generate a real secret with the `RandomNumberGenerator` command in Stage 4 and restart. |
| `503 SERVICE_NOT_READY` on all auth endpoints | `PEIARS_SESSION_SECRET` not set (or removed) | Generate a 64-char hex string; set it in `.env`; restart. |
| `DatabaseConfigurationError` at startup | `PEIARS_DATABASE_REQUIRED=true` but `PEIARS_DATABASE_URL` is empty | Set a valid database URL in `.env`. |
| No synthetic records in Investigations | `PEIARS_DEMONSTRATION_SOURCES` is false | Set `PEIARS_DEMONSTRATION_SOURCES=true` in `.env` and restart. |
| Browser shows "Desktop window required" | Viewport < 1024 CSS pixels | Widen the browser window to ≥ 1024px. |
| `alembic upgrade head` fails | Database unreachable or credentials wrong | Verify `PEIARS_DATABASE_URL` in `.env` and that PostgreSQL is running. |
| Login fails with generic 401 | Wrong application credentials or user not created | Run `create_admin.py` and/or the reviewer setup in Stage 5e. (A 401 here is an application-login outcome — it says nothing about PostgreSQL connectivity; check `/api/v1/health/ready` for that.) |
| `.env` values not loaded | Running uvicorn directly instead of `serve.py` | Use `python scripts\serve.py`, which loads `.env` via python-dotenv. If python-dotenv itself is missing, `serve.py` exits with an install hint instead of silently skipping the file. |

---

## Verification performed on this guide

The commands above were verified against the authoritative checkout on
the project's Linux test environment (backend, migrations, reviewer/admin
provisioning, E2E suite, and the configuration-contract tests). The
Windows-specific behaviours — selector event-loop installation,
PowerShell secret generation, `Copy-Item`, `Remove-Item Env:\...` — are
covered by platform-scoped code and platform-mocked tests but still
require a run on a **real Windows 11 machine**; see the final correction
delivery report for the explicit list.
