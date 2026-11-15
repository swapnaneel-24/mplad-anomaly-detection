"""Read-only Phase 5B figure gallery and traceability endpoints (PR-11).

Routes (all under ``/api/v1/research/phase5b``):

* ``GET /phase5b/catalog``                        — verified figure catalog
  with per-figure integrity, availability, and publication state.
* ``GET /phase5b/figures/{figure_no}/image``      — controlled delivery of
  one verified canonical PNG (only when the publication gate is enabled).
* ``GET /phase5b/traceability``                   — source-native objectives
  (a)/(b)/(c), research questions RQ1–RQ6, historical companion, and
  reproducibility links.

All endpoints are GET-only and read-only. The binary endpoint returns
``403 PUBLICATION_NOT_APPROVED`` unless ``phase5b_public_figures_enabled``
is explicitly enabled in settings. ``figure_no`` is validated by FastAPI
to ``1 <= figure_no <= 8``; no filename or filesystem path is ever
accepted as a parameter.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Request
from fastapi.responses import Response

from app.contracts.common import ErrorEnvelope
from app.contracts.phase5b import FigureCatalogResponse, TraceabilityResponse
from app.core.errors import ApiError, ErrorCode
from app.services.phase5b_catalog import (
    PHASE5B_CATALOG_SERVICE,
    Phase5BCatalogService,
    Phase5BIntegrityError,
    Phase5BUnavailableError,
)

router = APIRouter(prefix="/research/phase5b", tags=["research"])

_ERROR_RESPONSES = {
    403: {"model": ErrorEnvelope, "description": "Publication gate is disabled."},
    503: {
        "model": ErrorEnvelope,
        "description": "Phase 5B artifact unavailable or integrity failure.",
    },
}

FigureNo = Annotated[
    int,
    Path(ge=1, le=8, description="Canonical figure number (1-8)."),
]


def _service() -> Phase5BCatalogService:
    return PHASE5B_CATALOG_SERVICE


def _publication_enabled(request: Request) -> bool:
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        return False
    return bool(getattr(settings, "phase5b_public_figures_enabled", False))


def _unavailable(reason: str) -> ApiError:
    return ApiError(
        status_code=503,
        code=ErrorCode.SERVICE_NOT_READY,
        details={"dependency": "phase5b-evidence", "reason": reason},
    )


def _publication_denied() -> ApiError:
    return ApiError(
        status_code=403,
        code=ErrorCode.PUBLICATION_NOT_APPROVED,
        details={"reason": "publication_not_approved"},
    )


@router.get(
    "/catalog",
    response_model=FigureCatalogResponse,
    responses=_ERROR_RESPONSES,
    summary="Verified Phase 5B figure catalog and availability",
    description=(
        "Returns the eight canonical Phase 5B figures with per-figure "
        "integrity (raw-byte identity), availability (payload present), "
        "and publication (binary authorised) state. Publicly readable. "
        "Binary delivery is withheld by default pending licensing "
        "verification; enabling it requires the "
        "PEIARS_PHASE5B_PUBLIC_FIGURES_ENABLED setting."
    ),
)
async def get_phase5b_catalog(request: Request) -> FigureCatalogResponse:
    service = _service()
    try:
        payload = service.get_catalog(
            publication_enabled=_publication_enabled(request)
        )
    except Phase5BUnavailableError as exc:
        raise _unavailable("artifact_missing") from exc
    except Phase5BIntegrityError as exc:
        raise _unavailable("integrity_failed") from exc
    return FigureCatalogResponse.model_validate(payload)


@router.get(
    "/figures/{figure_no}/image",
    responses={
        200: {"content": {"image/png": {}}},
        403: {"model": ErrorEnvelope},
        503: {"model": ErrorEnvelope},
    },
    summary="Controlled delivery of one verified canonical figure PNG",
    description=(
        "Returns the raw bytes of the requested canonical figure PNG "
        "(1-8), verified against both the DVC pointer and the figure "
        "manifest using raw-byte hashing. Returns 403 "
        "PUBLICATION_NOT_APPROVED when the publication gate is disabled "
        "(the default), and 503 SERVICE_NOT_READY when the payload is "
        "missing or fails verification."
    ),
)
async def get_phase5b_figure_image(
    request: Request, figure_no: FigureNo
) -> Response:
    if not _publication_enabled(request):
        raise _publication_denied()
    service = _service()
    try:
        raw = service.get_figure_bytes(figure_no)
    except Phase5BUnavailableError as exc:
        raise _unavailable("artifact_missing") from exc
    except Phase5BIntegrityError as exc:
        raise _unavailable("integrity_failed") from exc
    return Response(
        content=raw,
        media_type="image/png",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "Content-Disposition": "inline",
        },
    )


@router.get(
    "/traceability",
    response_model=TraceabilityResponse,
    responses=_ERROR_RESPONSES,
    summary="Source-native objectives (a)/(b)/(c) and RQ1–RQ6 traceability",
    description=(
        "Returns the three source-native objectives from "
        "docs/provenance_log.md §1, the six research questions from "
        "docs/Phase-0.md §0.4, the 284,807-row historical companion "
        "disclaimer, and reproducibility references. The data shape "
        "uses source-native identifiers (a)/(b)/(c) and RQ1-RQ6; no "
        "invented OBJ-* identifiers are introduced."
    ),
)
async def get_phase5b_traceability() -> TraceabilityResponse:
    service = _service()
    payload = service.get_traceability()
    return TraceabilityResponse.model_validate(payload)