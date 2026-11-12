# PEIARS Configuration Inventory

**PR-06A Workstream B** — authoritative configuration reference.

Derived from `backend/app/core/config.py` (the Pydantic Settings model).
All variables use the `PEIARS_` prefix. Values are read from (in
increasing priority): field defaults → repository-root `.env` file →
environment variables.

---

## The one environment-loading procedure (PR-06A correction)

The **repository-root `.env` file is the single local-configuration
file**, and exactly one precedence rule applies everywhere:

> An explicitly exported environment variable always wins over a
> `.env` value.

Every backend process reads that same file with that same rule — no
> manual export steps are required anywhere:

| Process | Mechanism | Effect |
|---|---|---|
| API server (`python backend/scripts/serve.py`) | `load_dotenv(<repo-root>/.env, override=False)` immediately before `Settings()` is constructed | `.env` values are exported into the process environment (existing variables untouched) |
| Pydantic Settings (`app/core/config.py`) | `env_file=<repo-root>/.env` (absolute path, independent of the working directory) | values reach the typed settings model |
| Alembic (`alembic upgrade head`) | `migrations/env.py` parses the same file with `dotenv_values` when `PEIARS_DATABASE_URL` is not exported | migrations see the same URL as the API, **without mutating `os.environ`** |
| Provisioning CLIs (`create_admin.py`, `frontend/playwright/setup-reviewer.py`) | construct `Settings()` (Pydantic `env_file`) | same file, same precedence |

Two fail-loud guarantees:

* If **python-dotenv** is missing, `serve.py` exits and
  `migrations/env.py` raises with an actionable install hint — the
  `.env` file is never silently skipped.
* Importing `serve.py` does **not** load `.env` (the load happens in
  `main()`), so tooling that imports the module has no environment side
  effects.

---

## Supported interpreters

* **CPython 3.12.x** — the version the backend dependency pins and the
  full test suite are validated on (the project's Linux test runner).
* **Windows:** `backend/scripts/serve.py` installs
  `asyncio.WindowsSelectorEventLoopPolicy` before uvicorn creates its
  event loop (psycopg 3 cannot use the Proactor default). Windows
  runtime verification is **pending** — the win32 tests in
  `backend/tests/test_env_boot.py` simulate the platform with mocks and
  are not runtime evidence. If a Python build does not provide the
  policy class, `serve.py` **fails at startup with an actionable
  error** — absence of the class is not treated as proof that the
  default loop is safe.
* **macOS:** POSIX startup behaviour applies (no policy is installed);
  macOS has not been exercised by the project's test runner.

> **Variable-name hazard:** the Settings model uses
> `env_prefix="PEIARS_"` with **no aliases** — a variable is read only
> if its name is exactly `PEIARS_` + the field name (e.g.
> `PEIARS_ENVIRONMENT`, `PEIARS_CORS_ORIGINS`). Unknown `PEIARS_*`
> names are silently ignored (`extra="ignore"`, required for sibling
> CLI variables such as `PEIARS_BOOTSTRAP_ADMIN_PASSWORD`), so a
> misspelled name silently falls back to defaults. The committed
> `backend/.env.example` is name-checked against the model by
> `tests/test_env_boot.py::TestDocumentedEnvironmentContract`.

---

## Variables

### Application identity

| Variable | Default | Required | Sensitive | Description |
|---|---|---|---|---|
| `PEIARS_ENVIRONMENT` | `development` | No | No | `development` \| `test` \| `production`. Production enforces `session_cookie_secure=True` (validated at construction). Note: the field is `environment`, so the variable is `PEIARS_ENVIRONMENT` — a variable named `PEIARS_ENV` is NOT read. |

### API server

| Variable | Default | Required | Sensitive | Description |
|---|---|---|---|---|
| `PEIARS_API_HOST` | `127.0.0.1` | No | No | Bind host for the development server. |
| `PEIARS_API_PORT` | `8000` | No | No | Bind port (1–65535). |
| `PEIARS_API_ROOT_PATH` | `/api/v1` | No | No | URL prefix for the versioned API. |
| `PEIARS_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | No | No | Comma-separated allowed origins — the ONE documented representation (`NoDecode` + validator; pydantic-settings' default JSON decoding would reject it before validators run). JSON-array syntax, wildcards (`*`), and origins with paths/queries fail with a clear validation error. An explicitly empty value disables cross-origin access (fail-safe). |
| `PEIARS_LOG_LEVEL` | `INFO` | No | No | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR`. |

### Database (PR-03)

| Variable | Default | Required | Sensitive | Description |
|---|---|---|---|---|
| `PEIARS_DATABASE_URL` | *(unset)* | **Yes** for the investigation workflow | **Yes** (contains credentials) | Full SQLAlchemy URL, e.g. `postgresql+psycopg://user:pass@host:5432/db`. |
| `PEIARS_DATABASE_REQUIRED` | `false` | No | No | When `true`, readiness probes PostgreSQL; startup fails if the URL is missing. **Do not set `false` to mask an unavailable database.** |
| `PEIARS_DB_POOL_SIZE` | `5` | No | No | Connection-pool size (1–50). |
| `PEIARS_DB_MAX_OVERFLOW` | `10` | No | No | Pool overflow (0–100). |
| `PEIARS_DB_POOL_PRE_PING` | `true` | No | No | Pre-ping connections before use. |
| `PEIARS_DB_POOL_RECYCLE_SECONDS` | `1800` | No | No | Recycle connections after N seconds. |

### Authentication / sessions (PR-04)

| Variable | Default | Required | Sensitive | Description |
|---|---|---|---|---|
| `PEIARS_SESSION_SECRET` | *(unset)* | **Yes** for authentication | **Yes** | HMAC-SHA256 signing secret for CSRF tokens. ≥ 32 chars; template placeholders (e.g. `CHANGE_ME`) are **rejected at startup even when long enough**. When unset, auth routes fail closed with 503. |
| `PEIARS_SESSION_TTL_MINUTES` | `480` | No | No | Absolute session lifetime (minutes, server-enforced). |
| `PEIARS_SESSION_IDLE_TIMEOUT_MINUTES` | `240` | No | No | Idle-timeout window (minutes, server-enforced). |
| `PEIARS_SESSION_COOKIE_SECURE` | `true` | No | No | Cookie Secure flag. **Set `false` for local HTTP development.** Production requires `true` (validated). |
| `PEIARS_SESSION_COOKIE_NAME` | `peiars_session` | No | No | Session cookie name. May use `__Host-` prefix in production. |
| `PEIARS_CSRF_COOKIE_NAME` | `peiars_csrf` | No | No | Readable CSRF cookie name (double-submit). |
| `PEIARS_AUTH_LOCKOUT_THRESHOLD` | `5` | No | No | Failed-login attempts before lockout. |
| `PEIARS_AUTH_LOCKOUT_MINUTES` | `15` | No | No | Lockout duration (minutes). |

### Synthetic demonstration sources (PR-05B)

| Variable | Default | Required | Sensitive | Description |
|---|---|---|---|---|
| `PEIARS_DEMONSTRATION_SOURCES` | `false` | No (opt-in) | No | When `true`, registers the synthetic demonstration source. Records are explicitly fictional — NOT research findings. **Must be `false` in production.** |

### Build provenance

| Variable | Default | Required | Sensitive | Description |
|---|---|---|---|---|
| `PEIARS_GIT_COMMIT_SHA` | *(unset)* | No | No | Supplied by the deployment environment only; never fabricated. |

### Local development conveniences

| Variable | Default | Required | Sensitive | Description |
|---|---|---|---|---|
| `PEIARS_DOCS_ENABLED` | `true` | No | No | Serve `/docs` and `/openapi.json`. Intended for non-production. |

---

## Local-development minimum set

For the full investigation workflow (login + synthetic records + case
persistence), a local `.env` must set:

```ini
PEIARS_DATABASE_URL=postgresql+psycopg://peiars_app:PASSWORD@localhost:5432/peiars_review
PEIARS_DATABASE_REQUIRED=true
PEIARS_SESSION_SECRET=<64-char random hex>
PEIARS_SESSION_COOKIE_SECURE=false
PEIARS_DEMONSTRATION_SOURCES=true
```

---

## Fail-closed behaviour

| Missing configuration | Behaviour |
|---|---|
| `PEIARS_DATABASE_URL` (with `DATABASE_REQUIRED=true`) | Startup fails with `DatabaseConfigurationError` — actionable (names the settings to fix), not a generic database error. |
| `PEIARS_SESSION_SECRET` | Auth endpoints return `503 SERVICE_NOT_READY` (fail closed; no auth bypass). |
| `PEIARS_SESSION_SECRET` containing a template placeholder | Startup fails with a Pydantic validation error naming the placeholder — the example configuration can never activate authentication with a known signing secret. |
| `PEIARS_DEMONSTRATION_SOURCES` (unset/false) | No synthetic records exposed; the investigation workflow shows honest empty states. |
| Database unreachable / credentials rejected (with `DATABASE_REQUIRED=true`) | `/health/ready` returns `503` with the failed `postgresql` check; `/health/live` remains `200` (liveness ≠ readiness). Both failure causes intentionally share this one sanitized classification — no detail about *why* the connection failed is exposed. |
| Database reachable but **not migrated** (or at an older revision) | `/health/ready` returns `503` with the failed `migrations` check while the `postgresql` connectivity check reports ready — the failure class is distinguishable from a connection failure without leaking schema detail. The check is read-only; the documented remediation is an explicit `alembic upgrade head`. |
| python-dotenv missing | `serve.py` exits and `migrations/env.py` raises with an install hint — the `.env` file is never silently skipped. |

---

## Security-sensitive variables (never log, never commit)

- `PEIARS_DATABASE_URL` — contains credentials.
- `PEIARS_SESSION_SECRET` — the CSRF signing key.

The startup diagnostics in `serve.py` print only whether these are
*configured*, never their values.
