"""FastAPI application factory for the PEIARS backend.

``create_app`` builds a fully configured application:

* routes under the versioned ``/api/v1`` prefix (configurable);
* request-ID middleware (strict inbound validation, ``X-Request-ID``
  response header, structured JSON access logs);
* the shared structured error envelope for every failure path;
* explicit CORS origins (never a wildcard with credentials);
* injectable readiness probes (none configured in PR-02 — see
  :mod:`app.services.readiness` for the documented policy);
* an app-scoped static (currently empty) source registry.

The factory is deliberately free of database, authentication, model
loading and research-artifact concerns: those belong to later pull
requests. No module in this application imports the frozen research
package ``mplad``.
"""

from __future__ import annotations

from typing import Iterable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import APP_NAME, __version__
from app.api.v1.router import api_router
from app.core.config import Settings
from app.core.errors import register_exception_handlers
from app.core.middleware import REQUEST_ID_HEADER, RequestIDMiddleware, configure_logging
from app.core.openapi import build_openapi_schema
from app.services.readiness import ReadinessProbe
from app.services.source_registry import EMPTY_SOURCE_REGISTRY

_API_DESCRIPTION = (
    "Public Expenditure & Infrastructure Anomaly Review System (PEIARS) — "
    "versioned JSON API. Research evidence is served read-only and "
    "manifest-verified; an anomaly flag never implies fraud. This API "
    "never fits models, recomputes thresholds or mutates frozen research "
    "artifacts."
)


def create_app(
    settings: Settings | None = None,
    readiness_probes: Iterable[ReadinessProbe] | None = None,
) -> FastAPI:
    """Create a configured FastAPI application.

    Parameters
    ----------
    settings:
        Typed application settings; defaults to environment/``.env``
        driven settings. Tests inject explicit instances.
    readiness_probes:
        Optional injectable dependency checks (deterministic tests). The
        PR-02 default is an empty tuple: no required external dependency
        is configured yet.
    """
    settings = settings if settings is not None else Settings()

    app = FastAPI(
        title=APP_NAME,
        version=__version__,
        description=_API_DESCRIPTION,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )

    # Application-scoped state (injectable in tests).
    app.state.settings = settings
    app.state.source_registry = EMPTY_SOURCE_REGISTRY
    app.state.readiness_probes = tuple(readiness_probes or ())

    # Observability and tracing. Added last so it is the outermost user
    # middleware: every response, including error responses, passes
    # through it and receives the X-Request-ID header.
    configure_logging(settings.log_level)
    app.add_middleware(RequestIDMiddleware)

    # CORS: explicit origins only; credentials are allowed and therefore
    # wildcard origins are never used.
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=True,
            allow_methods=["GET", "OPTIONS"],
            allow_headers=["Content-Type", REQUEST_ID_HEADER],
        )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_root_path)

    # Publish the normalized OpenAPI contract. FastAPI auto-documents every
    # automatic 422 against HTTPValidationError, but the runtime returns the
    # shared ErrorEnvelope; build_openapi_schema rewrites the 422 refs and
    # drops the stale validation models so the published schema matches the
    # actual responses. The cached schema is deterministic (no timestamps).
    app.openapi_schema = None

    def _openapi() -> dict:
        if app.openapi_schema is None:
            app.openapi_schema = build_openapi_schema(app)
        return app.openapi_schema

    app.openapi = _openapi  # type: ignore[assignment]
    return app
