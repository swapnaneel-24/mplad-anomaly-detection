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

import re
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
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

#: A browser origin as it appears in the ``Origin`` header: an http/https
#: scheme, a host (DNS name, IPv4, or a bracketed IPv6 literal) and an
#: optional port. No path, query, wildcard or embedded JSON syntax —
#: CORS origins are compared by exact string match, so anything else
#: could never match a real browser origin anyway.
_CORS_ORIGIN_PATTERN = re.compile(
    r"^https?://"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"
    r"|\[[0-9A-Fa-f:.]+\])"
    r"(?::[0-9]{1,5})?$"
)

#: Placeholder markers that must never be accepted as a real signing
#: secret (PR-06A correction). A value containing one of these markers is
#: a template placeholder copied from an example file — possibly padded
#: past the minimum length — not a generated secret. Activating
#: authentication with it would let anyone who can read the repository
#: forge CSRF tokens. The check is case-insensitive.
_FORBIDDEN_SECRET_MARKERS: tuple[str, ...] = (
    "change_me",
    "changeme",
    "replace_me",
    "placeholder",
    "generate_a_random",
    "generate_a_unique",
    "generate_your_own",
    "your_secret",
    "your_own_secret",
    "example_secret",
    "sample_secret",
    "dummy_secret",
    "secret_here",
    "not_a_real_secret",
    "do_not_use",
    "todo_generate",
)


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
    #: with credentials. The single documented representation is a
    #: comma-separated string (see ``backend/.env.example``); ``NoDecode``
    #: keeps pydantic-settings from JSON-decoding the raw environment /
    #: ``.env`` value before the validator below can parse it (with the
    #: library's default complex-field decoding, a comma-separated value
    #: raises an opaque ``SettingsError`` before any field validator
    #: runs, and a JSON array never reaches the validator as a string).
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_CORS_ORIGINS)
    )

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

    # --- Synthetic demonstration sources (PR-05B §5) -------------------------
    #: When true, the synthetic demonstration source adapter is registered
    #: and its records are retrievable through /api/v1/sources and the case
    #: API. When false (the default), the source registry remains empty as
    #: in PR-02 and no synthetic data is exposed. This flag MUST be false
    #: in production deployments — synthetic records are explicitly
    #: fictional and must never be presented as research findings.
    demonstration_sources: bool = False

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
        """Require real secret material when a signing secret is configured.

        Two independent checks (PR-06A correction — neither may be weakened):

        1. At least 32 characters, so short guesses are rejected.
        2. No template-placeholder markers. This catches values copied
           unchanged from ``.env.example`` even when they are long enough
           to satisfy the length check (e.g. the former 46-character
           ``CHANGE_ME_GENERATE_A_RANDOM_64_CHAR_HEX_STRING`` placeholder,
           which passed the length check and would have activated
           authentication with a publicly known signing secret).
        """
        if value is None:
            return None
        if len(value) < 32:
            raise ValueError(
                "session_secret must be at least 32 characters when configured; "
                "generate a unique random value (e.g. `openssl rand -hex 32`)."
            )
        lowered = value.lower()
        matched = next(
            (marker for marker in _FORBIDDEN_SECRET_MARKERS if marker in lowered),
            None,
        )
        if matched is not None:
            raise ValueError(
                "session_secret contains the placeholder marker "
                f"{matched!r}; it cannot be used to sign CSRF tokens. "
                "Generate a unique random value instead — see the commands in "
                "backend/.env.example or docs/dev/LOCAL_STARTUP_WINDOWS.md "
                "(Stage 4)."
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
        """Parse the documented comma-separated allowed-origin list.

        The one documented representation (``backend/.env.example`` and
        ``docs/dev/CONFIGURATION_INVENTORY.md``) is a comma-separated
        string of origins. ``NoDecode`` on the field guarantees the raw
        string reaches this validator from both the environment-variable
        source and the ``.env``-file source. Anything that is not a valid
        origin fails with an actionable message instead of silently
        producing unusable allow-list entries — in particular:

        * the wildcard ``*`` is prohibited (credentials are always
          enabled, so the allow-list must stay explicit);
        * JSON-array syntax (``["http://a.example", ...]``) is rejected —
          it is NOT the documented representation;
        * values with a path, query, or embedded quotes/brackets are
          rejected as never-matchable origins.

        An explicitly empty value is accepted and produces an empty
        allow-list: no CORS middleware is installed and the API allows no
        cross-origin browser access (fail-safe, never fail-open).
        """
        if isinstance(value, str):
            parts = [origin.strip() for origin in value.split(",")]
            parsed = [origin for origin in parts if origin]
        elif isinstance(value, (list, tuple)):
            parsed = [origin.strip() if isinstance(origin, str) else str(origin) for origin in value]
        else:
            raise ValueError(
                "cors_origins must be a comma-separated string of allowed "
                f"origins (received {type(value).__name__}); e.g. "
                "PEIARS_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173"
            )
        for origin in parsed:
            if origin == "*":
                raise ValueError(
                    "cors_origins must not contain the wildcard '*' — "
                    "credentials are enabled, so the allow-list must be "
                    "explicit."
                )
            if not _CORS_ORIGIN_PATTERN.match(origin):
                raise ValueError(
                    f"cors_origins entry {origin!r} is not a valid browser "
                    "origin (expected scheme://host[:port], e.g. "
                    "http://localhost:5173). The documented representation "
                    "is a plain comma-separated list — JSON-array syntax is "
                    "not supported."
                )
        return parsed

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

