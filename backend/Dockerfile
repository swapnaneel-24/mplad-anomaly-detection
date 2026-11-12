# PEIARS backend runtime image (PR-06B).
#
# Builds the FastAPI application into a reproducible, non-root Linux image
# that runs ONLY the application runtime dependencies (no test tooling, no
# pgserver — PostgreSQL is a dedicated `postgres:16` Compose service, and
# pgserver is a host-level pytest-only dependency kept in requirements-dev.txt
# / requirements-lock.txt for local and CI test execution).
#
# Build context: `backend/` (see compose.yaml / .dockerignore). Only the
# application runtime files are copied; no .env, no test databases, no
# research datasets, no node_modules.
#
# Supported interpreter: CPython 3.12.x (the version the backend dependency
# pins and full test suite are validated on). Do not silently upgrade the
# runtime — the committed OpenAPI snapshot is reproducible only under these
# exact versions (see backend/requirements-lock.txt).

# --- Stage 1: runtime image ------------------------------------------------
FROM python:3.12-slim-bookworm

# Metadata. OCI labels are informational; no secrets are ever embedded.
LABEL org.opencontainers.image.title="PEIARS backend" \
      org.opencontainers.image.description="FastAPI application runtime for the Public Expenditure & Infrastructure Anomaly Review System." \
      org.opencontainers.image.source="https://github.com/swapnaneel-24/mplad-anomaly-detection" \
      org.opencontainers.image.licenses="UNLICENSED"

# Operating-system packages required only to run psycopg 3 (binary wheel has
# no system libpq dependency) and to manage a SIGTERM-friendly process. curl
# is NOT installed; the healthcheck uses the Python interpreter directly.
# tzdata keeps timestamp logs sane; ca-certificates lets outbound HTTPS (none
# by default, but present for future use) validate.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

# Application directory. The backend package is laid out so that the
# Alembic config (alembic.ini, migrations/) and the app package (app/) live
# under /app, matching the documented `cd backend && alembic upgrade head`
# workflow. PYTHONPATH=/app makes `app.*` importable for uvicorn and Alembic.
ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# --- Dependency layer (cached independently of source changes) -------------
# Install ONLY the runtime requirements. requirements.txt is the runtime
# dependency set (FastAPI, uvicorn, SQLAlchemy, Alembic, psycopg 3, argon2,
# pydantic-settings, python-dotenv). It deliberately excludes pgserver,
# pytest and httpx — those are test-only (requirements-dev.txt /
# requirements-lock.txt) and are never present in the runtime image.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# --- Application source ----------------------------------------------------
# Only the files the running application needs. No tests/, no __pycache__,
# no .env, no contracts/openapi.json regeneration tooling beyond the
# committed snapshot (the app publishes the committed schema; it never
# regenerates it at runtime).
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY contracts/ ./contracts/
COPY scripts/ ./scripts/

# --- Non-root user ---------------------------------------------------------
# The application must not run as root. A fixed UID makes volume permissions
# predictable. /app is owned by the app user; no host filesystem is mounted
# except the (optional) readonly research-data mount in a future deployment.
RUN groupadd --system --gid 10001 peiars \
    && useradd --system --uid 10001 --gid peiars --home-dir /app --shell /usr/sbin/nologin peiars \
    && chown -R peiars:peiars /app
USER peiars

# --- Network + health ------------------------------------------------------
EXPOSE 8000

# Liveness healthcheck: the process can answer HTTP. Uses the Python
# interpreter (always present) — no curl dependency. /api/v1/health/live
# performs no database access. Readiness (/api/v1/health/ready) is NOT used
# as the container healthcheck because a healthy-but-unmigrated database must
# keep the container alive (so `docker compose` can run the migrate step and
# recover) while readiness correctly stays 503 — see
# docs/dev/CONTAINER_TROUBLESHOOTING.md.
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=10 \
  CMD python -c "import urllib.request,sys; \
r=urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live',timeout=3); \
sys.exit(0 if r.status==200 else 1)" || exit 1

# --- Entrypoint ------------------------------------------------------------
# The documented ASGI startup entrypoint (see backend/scripts/serve.py
# docstring): `uvicorn app.main:create_app --factory`. --host 0.0.0.0 binds
# inside the container (the Compose network restricts which peers can reach
# it; the backend port is NOT published to the host by default).
#
# --proxy-headers is intentionally NOT set: the local Compose stack is HTTP
# on a private bridge network with a single browser-visible origin (the
# frontend nginx). The backend reads its cookie-secure policy from
# PEIARS_SESSION_COOKIE_SECURE (config-driven, not request-driven), and CSRF
# validates the Origin header (a request header nginx forwards unchanged).
# For a future HTTPS-terminated production deployment, enable --proxy-headers
# together with an explicit --forwarded-allow-ips list of trusted proxy IPs.
#
# The Windows selector-event-loop workaround in scripts/serve.py is a no-op
# on Linux (`sys.platform != "win32"`) and is not used here because uvicorn
# is invoked directly. On Linux the default epoll loop is correct for
# psycopg 3.
CMD ["uvicorn", "app.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--access-log", "--no-server-header"]
