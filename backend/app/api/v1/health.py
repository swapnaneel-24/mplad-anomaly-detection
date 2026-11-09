"""Health endpoints: liveness and readiness.

* ``GET /api/v1/health/live`` — the process can answer requests. No
  database access, no model loading, no DVC or network access.
* ``GET /api/v1/health/ready`` — all **configured, required** application
  dependencies are ready. PR-02 configures none (see
  :mod:`app.services.readiness` for the documented policy), so the
  default response is ``200`` with an empty checks list. When an injected
  probe fails, the endpoint answers ``503`` with the structured
  ``SERVICE_NOT_READY`` error envelope; response details contain only
  dependency names and statuses — never connection strings or exception
  text.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app import __version__
from app.contracts.common import (
    ErrorEnvelope,
    HealthLiveResponse,
    ReadinessCheck,
    ReadinessResponse,
)
from app.services.readiness import evaluate_probes

router = APIRouter(tags=["health"])


@router.get(
    "/health/live",
    response_model=HealthLiveResponse,
    summary="Liveness probe",
    description="Proves the API process is answering requests. Performs no "
    "database, model, DVC or network access.",
)
async def health_live() -> HealthLiveResponse:
    return HealthLiveResponse(status="alive", service="PEIARS API", version=__version__)


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    response_class=JSONResponse,
    responses={503: {"model": ErrorEnvelope, "description": "A required dependency is unavailable."}},
    summary="Readiness probe",
    description="Reports whether all configured, required application "
    "dependencies are ready. PR-02 configures no required external "
    "dependencies, so the default response is ready with an empty checks "
    "list. Optional research artifacts are not readiness dependencies.",
)
async def health_ready(request: Request) -> ReadinessResponse | JSONResponse:
    probes = getattr(request.app.state, "readiness_probes", ())
    ready_names, unavailable_names = evaluate_probes(probes)
    if unavailable_names:
        # Only dependency names and statuses are exposed — no connection
        # details, no exception messages. Rendered with the shared error
        # envelope so the 503 contract matches every other error.
        from app.core.errors import _error_response

        return _error_response(
            request,
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "SERVICE_NOT_READY",
            "A required application dependency is unavailable.",
            {
                "failed_checks": [
                    {"name": name, "status": "unavailable"} for name in unavailable_names
                ],
                "ready_checks": sorted(ready_names),
            },
        )
    checks = [ReadinessCheck(name=name, status="ready") for name in ready_names]
    return ReadinessResponse(status="ready", checks=checks)
