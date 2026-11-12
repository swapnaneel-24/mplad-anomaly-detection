# PEIARS Local Development — POSIX (Linux / macOS) Startup Guide

**PR-06A** — Environment Normalization and Deterministic Local Reproducibility

The POSIX equivalent of the Windows guide. The Windows asyncio
selector-policy compatibility is **not** applied on POSIX systems —
it is scoped to `sys.platform == "win32"` and has no effect here.

---

## Conventions used in this guide

* **Repository root (`<repo-root>`)** — the checkout folder that
  contains `backend/`, `frontend/`, and `docs/`. Substitute your actual
  path, for example `~/dev/mplad-anomaly-detection` (`pwd` must show a
  directory listing `backend` and `frontend`).
* **One shell session** runs Stages 1–6 and 8–10. Stage 7 (the frontend
  dev server) uses a second terminal because it occupies its shell.
* **Every stage states its working directory** in the heading, and every
  code block contains the exact `cd` commands needed to reach it from
  the repository root. Stages that change directory return to
  `<repo-root>` at the end, so the stages execute in sequence by
  copy-paste.
* The backend virtual environment (created in Stage 2) stays activated
  for the rest of the session.

---

## Prerequisites

| Software | Version | Verification |
|---|---|---|
| Python | **3.12.x** — the version the backend dependency pins and test suite are validated on (Linux test runner) | `python3 --version` |
| Node.js | 22 LTS (or 24 LTS) | `node --version` |
| npm | 10.x+ | `npm --version` |
| PostgreSQL | 16.x | `psql --version` |

---

## Stage 1 — Install backend dependencies

*Working directory: `<repo-root>/backend` (returns to `<repo-root>` at the end)*

```bash
cd <repo-root>
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
```

`requirements.txt` contains the pinned direct runtime dependencies; use
`pip install -r requirements-lock.txt` for the full transitive freeze
(both files agree on every shared pin).

---

## Stage 2 — Install frontend dependencies

*Working directory: `<repo-root>/frontend` (returns to `<repo-root>` at the end)*

```bash
cd <repo-root>
cd frontend
npm ci
cd ..
```

`npm ci` works on a fresh checkout with no `node_modules` — that is its
purpose — as long as the committed `package-lock.json` is valid and in
sync with `package.json`.

---

## Stage 3 — Configure the environment

*Working directory: `<repo-root>`*

```bash
cd <repo-root>
cp backend/.env.example .env
$EDITOR .env
```

Set in `.env`:

| Variable | Value |
|---|---|
| `PEIARS_DATABASE_URL` | `postgresql+psycopg://peiars_app:YOUR_PASSWORD@localhost:5432/peiars_review` |
| `PEIARS_DATABASE_REQUIRED` | `true` |
| `PEIARS_SESSION_SECRET` | output of `openssl rand -hex 32` (do NOT keep `CHANGE_ME` — placeholders are rejected at startup) |
| `PEIARS_SESSION_COOKIE_SECURE` | `false` (local HTTP only) |
| `PEIARS_DEMONSTRATION_SOURCES` | `true` |

Generate the session secret:

```bash
openssl rand -hex 32
```

Never commit `.env`.

---

## Stage 4 — Set up the database

### 4a. Create the database and role

*Working directory: `<repo-root>`*

```bash
cd <repo-root>
psql -U postgres -c "CREATE USER peiars_app WITH PASSWORD 'YOUR_PASSWORD';"
psql -U postgres -c "CREATE DATABASE peiars_review OWNER peiars_app;"
```

### 4b. Apply and verify migrations

*Working directory: `<repo-root>/backend` (returns to `<repo-root>` at the end)*

```bash
cd <repo-root>
cd backend
alembic upgrade head          # applies 0001 → 0002 → 0003
alembic current               # expect: 0003_add_users_sessions_auth (head)
cd ..
```

`alembic` reads `PEIARS_DATABASE_URL` from the repository-root `.env`
automatically — the same file the backend loads at startup (explicitly
exported environment variables still take precedence), so no manual
export is needed. `alembic current` matters because the readiness
endpoint only verifies connectivity (`SELECT 1`), not that migrations
were applied.

### 4c. Create the first admin and a reviewer

*Working directory: `<repo-root>/backend` (returns to `<repo-root>` at the end)*

```bash
cd <repo-root>
cd backend
source .venv/bin/activate

# First administrator (interactive hidden-password prompt):
python scripts/create_admin.py --username admin --display-name "Administrator"

# Reviewer for the investigation workflow (idempotent, reads .env):
PEIARS_E2E_USERNAME=reviewer1 PEIARS_E2E_PASSWORD='ReviewerPass123!' \
  python ../frontend/playwright/setup-reviewer.py
cd ..
```

`create_admin.py` is the offline administrator bootstrap CLI;
`setup-reviewer.py` is the repository's idempotent reviewer-provisioning
script (also used by the E2E suite). Both read the database URL from
the same `.env` file.

---

## Stage 5 — Start the backend

*Working directory: `<repo-root>/backend` (this terminal stays busy while the server runs)*

```bash
cd <repo-root>
cd backend
source .venv/bin/activate
python scripts/serve.py
```

`serve.py` loads the repository-root `.env` via python-dotenv before the
application settings are read (explicitly exported environment variables
take precedence), prints safe startup diagnostics (never secrets), and
installs the Windows selector event-loop policy only on `win32` — a
no-op on POSIX.

**Expected output:**

```
Serving PEIARS API v0.4.0 on http://127.0.0.1:8000
[peiars] environment: development
[peiars] event loop: default (POSIX)
[peiars] database required: True
[peiars] database configured: yes
[peiars] demonstration sources: enabled
[peiars] session secret: configured
[peiars] api prefix: /api/v1
[peiars] docs: enabled
API prefix: /api/v1 (docs: /docs)
INFO:     Uvicorn running on http://127.0.0.1:8000
```

---

## Stage 6 — Start the frontend

Open a **new terminal** (the Stage 5 terminal is busy serving the API):

```bash
cd <repo-root>/frontend
npm run dev
```

Open http://127.0.0.1:5173/ (browser window ≥ 1024 CSS pixels).

---

## Verify the backend

```bash
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
> ready. Migrations are never applied automatically at startup; the
> remediation is always an explicit `alembic upgrade head`.

---

## Verify persistence

1. Log in, create a review case from a synthetic record.
2. `Ctrl+C` the backend, restart it
   (`cd <repo-root>/backend && source .venv/bin/activate && python scripts/serve.py`).
3. Log in again — the case is still listed (PostgreSQL persistence).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Pydantic `ValidationError` mentioning `session_secret ... placeholder` | Replace the `CHANGE_ME` template value in `.env` with `openssl rand -hex 32` output. |
| `503 SERVICE_NOT_READY` on auth | Set `PEIARS_SESSION_SECRET` (≥ 32 chars, real random) in `.env`. |
| `DatabaseConfigurationError` | Set `PEIARS_DATABASE_URL` in `.env`. |
| Readiness `503` with failed check `postgresql` | PostgreSQL is unreachable or rejected the connection — verify the server and the URL. (Credential failures and network failures intentionally share this one sanitized classification; no detail is exposed.) |
| Readiness `503` with failed check `migrations` | The database is reachable but its schema is not at the committed head (never migrated, or an older revision). Run `alembic upgrade head`, then re-check `/api/v1/health/ready`. The check is read-only; migrations are never applied automatically at startup. |
| Pydantic `ValidationError` mentioning `cors_origins ... comma-separated` | `PEIARS_CORS_ORIGINS` is not a plain comma-separated origin list (e.g. JSON-array syntax, a wildcard `*`, or an origin with a path). Use the documented form: `PEIARS_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173`. Wildcards are prohibited because credentials are enabled. |
| No synthetic records | Set `PEIARS_DEMONSTRATION_SOURCES=true` in `.env`. |
| "Desktop window required" | Widen the browser to ≥ 1024 CSS pixels. |
| Migrations fail | Verify PostgreSQL is running and the URL in `.env` is correct. |
| `.env` not loaded | Use `python scripts/serve.py` (not bare `uvicorn`). If python-dotenv is missing, `serve.py` exits with an install hint instead of silently skipping the file. |

---

## Event-loop note (POSIX)

`backend/scripts/serve.py` installs the
`WindowsSelectorEventLoopPolicy` only when `sys.platform == "win32"`.
On Linux and macOS the default `asyncio` policy is used — no
compatibility shim is needed or applied. Supported interpreters:
**CPython 3.12.x** — the version the backend dependency pins and the
full test suite are validated on (Linux test runner). Windows runtime
verification is pending (its behaviour is covered by platform-mocked
tests, which are not runtime evidence); macOS has not been exercised by
the project's test runner either.
