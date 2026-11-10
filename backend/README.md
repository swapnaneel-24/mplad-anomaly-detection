# backend/ — PEIARS API application

Intended responsibility: the **FastAPI application** — HTTP transport,
typed Pydantic API contracts under `/api/v1`, authentication boundaries and
application services. Persistent review-case data lives in its own
PostgreSQL database (PR-03); research artifacts are consumed strictly
read-only through approved server-side adapters with manifest verification
(later pull requests).

**Status (PR-04): authentication and authorization foundation
implemented** — local PostgreSQL-backed accounts with Argon2id password
hashing, opaque server-side sessions in secure HttpOnly cookies, signed
double-submit CSRF protection, role-based authorization (viewer/reviewer/
admin), database-backed login throttling, a bootstrap CLI for the first
administrator, and authenticated actor identity bound to the PR-03
append-only review history. No public case CRUD or user-management
endpoints exist yet (PR-05+).

## Implemented in PR-04

| Area | Detail |
|---|---|
| Accounts | `users` table (migration 0003): normalized unique usernames (NFKC + casefold), Argon2id hashes via `argon2-cffi` (never plaintext, never in responses), bounded display names, server-side roles, activation flag, UTC timestamps |
| Sessions | `auth_sessions` table: opaque 256-bit tokens (CSPRNG) issued in HttpOnly cookies; only the SHA-256 verifier is stored; server-enforced absolute expiry (`PEIARS_SESSION_TTL_MINUTES`), idle timeout (`PEIARS_SESSION_IDLE_TIMEOUT_MINUTES`) and irreversible revocation; fresh session per login (fixation prevention); `last_seen_at` refreshed at most every 5 minutes |
| Cookies | Session cookie: `HttpOnly; Secure; SameSite=Lax; Path=/`, no `Domain` (production defaults; `PEIARS_SESSION_COOKIE_SECURE=false` is the documented local-HTTP relaxation). CSRF cookie readable for double-submit. `__Host-` names supported via configuration |
| CSRF | Signed double-submit cookie + `X-CSRF-Token` header (HMAC-SHA256 over the server session secret) plus Origin allowlist defence in depth; applied to `POST /auth/login` and `POST /auth/logout`; no global test bypass. **Convention for PR-05+: every new state-changing route must carry the `require_csrf` dependency** |
| RBAC | `viewer` (read:public, read:analytics) ⊂ `reviewer` (+ cases:read/write) ⊂ `admin` (+ admin:users); dependencies `get_current_user`, `require_authenticated`, `require_role(...)`, `require_permission(...)`; role always read from the database, never from payloads; deactivation and role changes apply to existing sessions immediately |
| Endpoints | `POST /api/v1/auth/login` (generic failures; 429 when throttled), `POST /api/v1/auth/logout` (revoke + expire cookies; replay fails), `GET /api/v1/auth/me` (sanitized public fields + effective permissions), `GET /api/v1/auth/csrf` (bootstrap token) |
| Throttling | `login_throttles` table keyed by normalized username, atomic upsert increment (multi-worker safe); configurable threshold/lockout; locked keys fail closed with 429 `RATE_LIMITED` |
| Actor identity | `AuthenticatedPrincipal` → `actor_ref_from_principal()` → PR-03 review history records the stable user UUID; client payloads never carry actor identity; historical synthetic actor refs (non-UUID) remain distinguishable, no event rows rewritten |
| Bootstrap | `python scripts/create_admin.py --username ... --display-name ...` — interactive hidden prompt or `PEIARS_BOOTSTRAP_ADMIN_PASSWORD` env var; no defaults, no startup auto-creation, refuses duplicates |
| OpenAPI | Cookie security scheme (`APIKeyCookie`, name `peiars_session`) on `/auth/me` and `/auth/logout`; auth error responses documented as `ErrorEnvelope`; byte-reproducible snapshot |

### Error codes (PR-04 additions)

Implemented: `UNAUTHORIZED` (401), `FORBIDDEN` (403),
`RATE_LIMITED` (429, login throttling), `CSRF_TOKEN_INVALID` (403).

### Auth fail-closed behaviour

- No `PEIARS_SESSION_SECRET` → auth endpoints return a sanitized 503
  (`SERVICE_NOT_READY`); the rest of the API keeps working.
- No database configured → auth endpoints return a sanitized 503. In
  deployed authenticated mode, login/session storage never silently
  falls back to an in-memory substitute for PostgreSQL.
- Disabled account or wrong password → the same generic 401 message
  (no username enumeration; unknown users pay one Argon2id verification
  for timing uniformity).

### How the future React client authenticates

1. `GET /api/v1/auth/csrf` → readable `peiars_csrf` cookie + token in body.
2. `POST /api/v1/auth/login` with `X-CSRF-Token` header (value = token)
   and JSON credentials → session cookie set (HttpOnly — never readable
   by JavaScript), CSRF token rotated.
3. All subsequent requests send cookies automatically
   (`credentials: 'include'` for cross-origin dev; the Vite dev proxy in
   PR-05 will make them same-origin).
4. Every state-changing request echoes the current CSRF token in
   `X-CSRF-Token`.
5. `GET /api/v1/auth/me` returns the user's role and permissions for UI
   visibility only — authorization is always enforced server-side.

No token is ever stored in `localStorage`/`sessionStorage`.

## Implemented in PR-02

| Area | Detail |
|---|---|
| Application factory | `app.main.create_app(settings, readiness_probes)` — injectable, isolated |
| Liveness | `GET /api/v1/health/live` → 200 `{"status": "alive", ...}`; no DB/model/DVC/network access |
| Readiness | `GET /api/v1/health/ready` → 200 with the configured dependency checks; 503 `SERVICE_NOT_READY` envelope when an injected required probe fails. **PR-02 policy: zero required dependencies configured** (the checks list is honestly empty — the API does not pretend to check a database that is not integrated yet). PR-03 registers a PostgreSQL probe without changing the response contract. |
| Metadata | `GET /api/v1/meta` → application name, API version, app version, `git_commit_sha` **only if supplied by the deployment environment** (never fabricated), environment, implemented-vs-planned features, subsystem availability |
| Source registry seam | `app/services/source_registry.py` + `GET /api/v1/sources`, `GET /api/v1/sources/{source_id}` over a **static empty** registry; opaque-slug IDs strictly validated (path-like input rejected); no filesystem access, no scanning, no DVC, no file-reading endpoints |
| Error contract | Single envelope `{error: {code, message, request_id, details}}` for validation errors (422), not found (404), method not allowed (405), invalid source ID (422), source not found (404), not ready (503) and unhandled exceptions (500, sanitized — no tracebacks, no paths) |
| Request tracing | `X-Request-ID` generated per request; caller-supplied IDs accepted only after strict validation (`[A-Za-z0-9._-]{1,64}`); returned on every response including errors; structured JSON access logs carry the ID and contain **no** headers, query strings, cookies or bodies |
| CORS | Explicit origins from `PEIARS_API_CORS_ORIGINS`; credentials allowed, wildcard never used |
| OpenAPI | Deterministic export (`backend/scripts/export_openapi.py`), committed snapshot in `backend/contracts/openapi.json`, drift-guarded by tests |

### Error codes

Implemented: `VALIDATION_ERROR`, `BAD_REQUEST`, `NOT_FOUND`,
`METHOD_NOT_ALLOWED`, `INVALID_SOURCE_ID`, `SOURCE_NOT_FOUND`,
`SERVICE_NOT_READY`, `INTERNAL_SERVER_ERROR`, `REQUEST_FAILED`.

Reserved for later pull requests (documented, **not** wired up):
`UNAUTHORIZED` and `FORBIDDEN` (PR-04), `CONFLICT` and `CASE_NOT_FOUND`
(PR-03), `ARTIFACT_INTEGRITY_FAILED` and `ARTIFACT_UNAVAILABLE` (M2
research-evidence access), `RATE_LIMITED` (hardening).

## Relationship to the research package

- The existing research package `src/mplad/` is imported **without package
  installation**: the repository uses an explicit src layout where
  `tests/conftest.py` (and the research notebook bootstrap) insert
  `<repo>/src` into `sys.path`. There is no `pyproject.toml` or
  `setup.py` today, and PR-02 does not introduce any.
- **No module under `backend/app` imports `mplad` or any research
  dependency** (NumPy, pandas, scikit-learn, SciPy, matplotlib). This is
  enforced by tests (`backend/tests/test_frozen_isolation.py`), including
  a clean-venv run: the whole backend suite passes in an environment where
  the research dependencies are not installed at all.
- Research dependencies are never upgraded by application work. Backend
  dependencies are managed separately (below).
- A future move to proper packaging is a separately reviewed change.

## Python

Supported version: **3.12.x** (validated on 3.12.16; the maintainer's
research machine also uses a 3.13/pytest 9.2.0 environment — the backend
targets the same interpreter line).

## Setup

### Windows PowerShell (from the repository root)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-lock.txt
# Run the tests:
python -m pytest tests -q
# Serve locally (reads ../.env or environment variables):
python scripts\serve.py
```

### Linux (from the repository root)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-lock.txt
python -m pytest tests -q
python scripts/serve.py
```

Equivalent direct uvicorn invocation (from `backend/`):

```bash
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Then check `http://127.0.0.1:8000/api/v1/health/live` (PowerShell:
`Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/live`).

## Dependency files

| File | Purpose |
|---|---|
| `requirements.txt` | Pinned direct runtime dependencies (fastapi, uvicorn, pydantic, pydantic-settings) |
| `requirements-dev.txt` | Runtime pins plus test dependencies (httpx for the TestClient, pytest) |
| `requirements-lock.txt` | Full transitive freeze for exact reproducibility (validated in a clean Python 3.12 venv: install + full test suite green, research environment untouched) |

## Configuration

Typed settings via Pydantic Settings, read from `PEIARS_`-prefixed
environment variables and (for local development) the repository-root
`.env` file — see `.env.example` for every supported variable (added in
PR-02: `PEIARS_GIT_COMMIT_SHA`, `PEIARS_LOG_LEVEL`,
`PEIARS_API_DOCS_ENABLED`). Tests inject explicit `Settings` objects and
never read `.env`. Real `.env` files are git-ignored; never commit
credentials.

## Local frontend-to-API proxy convention (documentation-only until PR-05)

The Vite development server (frontend, PR-05) will proxy `/api/v1` to the
API so the browser sees same-origin requests during development. The
conventional Vite configuration will be:

```ts
// frontend/vite.config.ts (planned, PR-05)
server: {
  proxy: {
    "/api/v1": {
      target: "http://127.0.0.1:8000",
      changeOrigin: false,
    },
  },
}
```

No frontend dependencies or configuration are introduced in PR-02.

## OpenAPI export and TypeScript types

Export the deterministic schema (sorted keys, no timestamps):

```bash
python backend/scripts/export_openapi.py            # writes backend/contracts/openapi.json
python backend/scripts/export_openapi.py --output somewhere/openapi.json
```

The committed snapshot `backend/contracts/openapi.json` is guarded against
drift by `backend/tests/test_openapi.py` (determinism and byte-identity)
and `backend/tests/test_openapi_contract.py` (422 contract correctness:
no `HTTPValidationError`, every 422 references `ErrorEnvelope`, runtime
422 body validates against the published schema).

### Reproducibility

The OpenAPI snapshot is only reproducible under the pinned dependency
lock. Regenerate it **only** after a clean install in a Python 3.12
environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate            # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements-lock.txt
python scripts/export_openapi.py
```

Do **not** regenerate the snapshot against arbitrary or newer dependency
versions: FastAPI and Pydantic emit slightly different schema JSON across
versions, and silently regenerating would publish a contract that does
not match the locked runtime. The installed versions are machine-checked
by `backend/tests/test_dependency_lock.py`; if that test fails, install
the locked versions rather than regenerating.

| Constraint | Value |
|---|---|
| Supported Python | 3.12.x (validated on 3.12.16) |
| Framework pin | fastapi==0.128.0, pydantic==2.12.5, pydantic-settings==2.13.1, starlette==0.50.0 |
| Test client | httpx==0.28.1 |
| Snapshot guard | `tests/test_openapi.py` (drift), `tests/test_openapi_contract.py` (422 contract), `tests/test_dependency_lock.py` (version match) |

TypeScript type generation (documented method; adopt when the frontend is
initialized in PR-05):

```bash
npx openapi-typescript@7 backend/contracts/openapi.json --output frontend/src/api/schema.d.ts
```

The frontend is intentionally not initialized in PR-02, so no generated
TypeScript file is committed; the JSON contract above is the tested,
versioned source of truth for that step.

## Testing

```bash
# From the repository root (backend venv active):
python -m pytest backend/tests -q
```

Coverage highlights: factory and settings isolation; liveness; readiness
under injected healthy/unhealthy/raising probes (no fake DB assertions);
metadata incl. missing build SHA and secret-leak scans; error envelope
stability; request-ID generation/propagation/log redaction; unhandled
exception sanitization; validation-error formatting without input echo;
CORS allowed/disallowed origins; OpenAPI determinism and drift; OpenAPI
422 contract correctness (no `HTTPValidationError`, every 422 references
`ErrorEnvelope`, runtime 422 validates against the published schema);
dependency-lock version match (Python 3.12 + pinned framework versions);
source-ID path rejection (service and HTTP level); frozen-research import
isolation (static AST scan of backend source + runtime subprocess proving
`mplad` is not loaded by the app); PR-03 review-case workflow,
transactions, append-only enforcement and event ordering; PR-04
authentication (Argon2id, generic failures, throttling), sessions
(expiry/revocation/idle/replacement), cookies (production attributes),
CSRF (missing/incorrect/correct tokens, cross-origin, no bypass), RBAC
(role gates, escalation attempts, immediate privilege changes), actor
provenance and no-leakage scans (logs + committed files).

## PR-04 local setup

### 1. Provision a disposable local PostgreSQL database

Either install PostgreSQL locally (any 13+; 16 recommended) or, for a
throwaway test instance, `pip install pgserver` (bundled PostgreSQL 16).
Create a database and a dedicated role; assemble the URL:

```
postgresql+psycopg://peiars_app:<password>@localhost:5432/peiars_review
```

### 2. Configure the environment without committing secrets

Copy `.env.example` to `.env` (uncommitted) and set:

```ini
PEIARS_DATABASE_URL=postgresql+psycopg://peiars_app:...@localhost:5432/peiars_review
PEIARS_DATABASE_REQUIRED=true
PEIARS_SESSION_SECRET=<openssl rand -hex 32>   # >= 32 chars, unique per env
PEIARS_SESSION_COOKIE_SECURE=false              # ONLY for local HTTP dev
```

### 3. Run migrations

```bash
cd backend
alembic upgrade head          # applies 0001 → 0002 → 0003
alembic history               # verify the chain
```

### 4. Create the first administrator (secure bootstrap)

```bash
# Interactive (hidden password prompt):
python scripts/create_admin.py --username admin --display-name "Administrator"

# Or non-interactive (secret from the process environment):
PEIARS_BOOTSTRAP_ADMIN_PASSWORD='...' python scripts/create_admin.py \
    --username admin --display-name "Administrator"
```

The command refuses duplicate usernames and never displays the password.
Later user provisioning (viewer/reviewer accounts) is deferred to a
separately approved administrator workflow.

### 5. Start the API

```bash
python scripts/serve.py
# or: uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

### 6. Exercise login / logout / CSRF / me (curl examples)

```bash
BASE=http://127.0.0.1:8000/api/v1

# CSRF bootstrap (sets the readable peiars_csrf cookie):
CSRF=$(curl -s -c cookies.txt $BASE/auth/csrf | sed -E 's/.*"csrf_token":"([^"]+)".*/\1/')

# Login (echo the CSRF token; -b/-c persist cookies):
curl -s -b cookies.txt -c cookies.txt -H "X-CSRF-Token: $CSRF" \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"..."}' $BASE/auth/login

# Current user (session cookie only):
curl -s -b cookies.txt $BASE/auth/me

# Logout (fresh CSRF token after rotation, then revoke):
CSRF=$(curl -s -b cookies.txt -c cookies.txt $BASE/auth/csrf | sed -E 's/.*"csrf_token":"([^"]+)".*/\1/')
curl -s -b cookies.txt -c cookies.txt -H "X-CSRF-Token: $CSRF" -X POST $BASE/auth/logout
```

### 7. Run the authentication tests

```bash
python -m pytest tests/test_auth_*.py -q     # real PostgreSQL via pgserver
```

### 8. Inspect session revocation

```sql
-- After logout, the row shows revoked_at set; replaying the old cookie
-- returns 401:
SELECT s.id, u.username, s.created_at, s.expires_at, s.revoked_at
FROM auth_sessions s JOIN users u ON u.id = s.user_id
ORDER BY s.created_at DESC;
```

### 9. Reset a disposable development database

```sql
-- From an admin connection (destroys all application data):
DROP DATABASE peiars_review;
CREATE DATABASE peiars_review OWNER peiars_app;
```
then re-run `alembic upgrade head` and the bootstrap CLI. Never run
destructive steps against a database containing real review history.

## What deliberately does not exist yet

Public case CRUD endpoints and any review-case mutation routes (PR-05+),
user-management/administration endpoints, password-reset and email
services, MFA/SSO/OAuth, the React application (PR-05), Docker Compose
and CI (PR-06), research-artifact serving (M2) and any PMGSY/MPLADS
ingestion. The only write endpoints that exist are
`POST /api/v1/auth/login` and `POST /api/v1/auth/logout`, both
CSRF-protected.
