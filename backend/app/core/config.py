"""Typed application configuration (Pydantic Settings).

All settings are injectable for tests. Values come from (in increasing
priority) field defaults, an optional repository-root ``.env`` file, and
``PEIARS_``-prefixed environment variables. Tests construct explicit
``Settings`` objects with ``_env_file=None`` so results never depend on the
machine's environment.

Security notes:

* ``git_commit_sha`` is *only* what a deployment environment supplies. The
  application never fabricates a commit SHA.
* No secret is ever logged or returned by the API; secrets live only in
  the uncommitted ``.env`` file (see the repository-root ``.env.example``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

from app import APP_NAME, __version__

#: Repository root (<repo>/backend/app/core/config.py -> parents[3]).
REPO_ROOT: Path = Path(__file__).resolve().parents[3]

#: Default local-development CORS origins (explicit; never a wildcard).
DEFAULT_CORS_ORIGINS: tuple[str, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)

EnvironmentName = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class Settings(BaseSettings):
    """Typed, injectable application settings."""

    model_config = SettingsConfigDict(
        env_prefix="PEIARS_",
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # --- Application identity -------------------------------------------------
    app_name: str = APP_NAME
    app_version: str = __version__
    environment: EnvironmentName = "development"

    # --- API server -----------------------------------------------------------
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    #: URL prefix under which the versioned API is served (router prefix).
    #: Note: this is the served URL prefix, not the ASGI ``root_path`` used
    #: when a reverse proxy strips a prefix (uvicorn ``--root-path``).
    api_root_path: str = "/api/v1"

    # --- Cross-origin resource sharing ----------------------------------------
    #: Explicit allowed origins only. Wildcard origins are never combined
    #: with credentials.
    cors_origins: list[str] = Field(default_factory=lambda: list(DEFAULT_CORS_ORIGINS))

    # --- Build provenance -----------------------------------------------------
    #: Supplied by the deployment environment only; never fabricated.
    git_commit_sha: str | None = None

    # --- Observability --------------------------------------------------------
    log_level: LogLevel = "INFO"

    # --- Local development conveniences ---------------------------------------
    #: Serve the interactive API docs (``/docs`` and ``/openapi.json``).
    #: Intended for non-production environments; the OpenAPI schema can
    #: always be exported offline via ``backend/scripts/export_openapi.py``.
    docs_enabled: bool = True

    # --- Database (PR-03) -----------------------------------------------------
    #: Full SQLAlchemy PostgreSQL URL, e.g.
    #: ``postgresql+psycopg://user:password@host:5432/dbname``. Supplied by
    #: the deployment environment; never fabricated. When unset, the
    #: database is not configured and no engine is created.
    database_url: str | None = None

    #: When true, PostgreSQL is a required dependency and readiness probes
    #: it. When false, readiness behaves as in PR-02 (no required deps).
    #: This explicit flag means "no required dependencies" can never
    #: accidentally imply PostgreSQL was verified (PR-03 §13).
    database_required: bool = False

    #: Connection-pool lifecycle (PR-03 §11). All injectable for tests.
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_pool_pre_ping: bool = True
    db_pool_recycle_seconds: int = Field(default=1800, ge=10, le=86400)

    # --- Authentication & sessions (PR-04) -------------------------------------
    #: Server-side signing secret for CSRF tokens (HMAC-SHA256). Required
    #: for any authenticated operation; when unset, the auth routes fail
    #: closed with a sanitized 503. Never logged or returned by the API.
    session_secret: str | None = None

    #: Absolute session lifetime (minutes), server-enforced.
    session_ttl_minutes: int = Field(default=480, ge=5, le=43200)

    #: Idle-timeout window (minutes) based on last_seen_at, server-enforced.
    session_idle_timeout_minutes: int = Field(default=240, ge=5, le=43200)

    #: Session cookie name. A single-host HTTPS deployment may set this to
    #: ``__Host-peiars_session`` for browser-enforced cookie guarantees.
    session_cookie_name: str = "peiars_session"

    #: Cookie Secure flag. Production default True; local HTTP development
    #: may explicitly relax it via PEIARS_SESSION_COOKIE_SECURE=false.
    session_cookie_secure: bool = True

    #: Readable (non-HttpOnly) CSRF cookie name (double-submit).
    csrf_cookie_name: str = "peiars_csrf"

    #: Failed-login lockout policy (database-backed, shared across workers).
    auth_lockout_threshold: int = Field(default=5, ge=1, le=100)
    auth_lockout_minutes: int = Field(default=15, ge=1, le=1440)

    @field_validator("session_secret", mode="before")
    @classmethod
    def _clean_session_secret(cls, value: object) -> object:
        """Treat an empty string as "not configured"."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("session_secret", mode="after")
    @classmethod
    def _validate_session_secret(cls, value: str | None) -> str | None:
        """Require at least 32 characters of secret material when set."""
        if value is not None and len(value) < 32:
            raise ValueError(
                "session_secret must be at least 32 characters when configured; "
                "generate a unique random value (e.g. `openssl rand -hex 32`)."
            )
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def _clean_database_url(cls, value: object) -> object:
        """Treat an empty string as "not configured"."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        """Accept a comma-separated string (as used in ``.env`` files)."""
        if isinstance(value, str):
            parts = [origin.strip() for origin in value.split(",")]
            return [origin for origin in parts if origin]
        return value

    @field_validator("git_commit_sha", mode="before")
    @classmethod
    def _clean_commit_sha(cls, value: object) -> object:
        """Treat an empty string as "not supplied"."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("api_root_path", mode="after")
    @classmethod
    def _validate_root_path(cls, value: str) -> str:
        if not value.startswith("/") or value.endswith("/") or ".." in value:
            raise ValueError(
                "api_root_path must be an absolute path segment without a "
                "trailing slash (for example '/api/v1')"
            )
        return value
    
    @model_validator(mode='after')
    def validate_secure_cookies(self) -> 'Settings':
        if self.environment == 'production' and not self.session_cookie_secure:
            raise ValueError('Production environment requires session_cookie_secure=True')
        return self


def canonical_settings() -> Settings:
    """Deterministic settings for offline OpenAPI export.

    Reads neither ``.env`` nor environment variables so the exported
    schema is reproducible on every machine for a given code version.
    """
    return Settings(
        _env_file=None,
        environment="development",
        git_commit_sha=None,
    )

