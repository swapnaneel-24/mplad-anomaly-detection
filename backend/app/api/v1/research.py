"""Read-only research-results endpoints (PR-08).

Routes (all under ``/api/v1/research``):

* ``GET /research/sources``                        -- list approved read-only
  research sources (public read-only per FR-03 / ADR-007).
* ``GET /research/sources/{source_id}``            -- fetch one source's
  metadata, including frozen-artifact provenance and experimental context
  (public read-only per FR-03 / ADR-007).
* ``GET /research/sources/{source_id}/results``    -- fetch the precomputed
  aggregate reference values with full provenance (any authenticated
  role).

Security and scope (PR-08):

* Every endpoint requires an authenticated principal via
  public read-only access (viewer, reviewer and admin are all
  permitted -- the data is read-only and non-sensitive aggregate
  reference values).
* Every endpoint is GET-only: this router performs no writes, creates no
  database rows and never mutates a frozen artifact.
* Unknown ``source_id`` values raise ``SOURCE_NOT_FOUND`` (404). The
  ``source_id`` is never used to construct a filesystem path.
* The served values are precomputed and frozen; ``is_precomputed`` is
  always ``true`` and ``is_live_prediction`` is always ``false`` on the
  results response.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path

from app.contracts.common import ErrorEnvelope
from app.contracts.research import (
    ResearchResultItem,
    ResearchResultsResponse,
    ResearchSourceDetail,
    ResearchSourceListResponse,
    ResearchSourceSummary,
)
from app.core.errors import ApiError, ErrorCode
from app.services.research_source import (
    ResearchIntegrityError,
    ResearchSourceService,
    ResearchUnavailableError,
)
from app.services.source_registry import SourceNotFoundError

router = APIRouter(prefix="/research", tags=["research"])

_ERROR_RESPONSES = {
    404: {"model": ErrorEnvelope, "description": "Research source not found."},
    503: {"model": ErrorEnvelope, "description": "Research source unavailable or integrity failure."},
}


def _service() -> ResearchSourceService:
    """Build the read-only research-source service.

    The service is stateless and holds no database or request-scoped
    resources, so a fresh instance per request is cheap. The frozen
    research constants are loaded lazily (and cached at module level)
    on the first call that actually needs them.
    """
    return ResearchSourceService()


def _summary(descriptor: dict) -> ResearchSourceSummary:
    return ResearchSourceSummary.model_validate(descriptor)


def _detail(descriptor: dict) -> ResearchSourceDetail:
    return ResearchSourceDetail.model_validate(descriptor)


@router.get(
    "/sources",
    response_model=ResearchSourceListResponse,
    responses=_ERROR_RESPONSES,
    summary="List approved research sources",
    description=(
        "Lists the approved, read-only research sources. Every served value "
        "is a precomputed, frozen, manifest-verified aggregate reference "
        "value; this endpoint never fits a model, recomputes a threshold or "
        "produces a live prediction. Publicly readable (GET-only, non-sensitive precomputed reference values per FR-03 / ADR-007)."
    ),
)
async def list_research_sources() -> ResearchSourceListResponse:
    service = _service()
    items = [_summary(descriptor) for descriptor in service.list_sources()]
    return ResearchSourceListResponse(items=items, count=len(items))


@router.get(
    "/sources/{source_id}",
    response_model=ResearchSourceDetail,
    responses=_ERROR_RESPONSES,
    summary="Get one research source's metadata",
    description=(
        "Fetches the full metadata for one approved read-only research "
        "source, including the frozen-artifact provenance (path, SHA-256, "
        "digest algorithm, canonicalization) and the frozen experimental "
        "context. Unknown identifiers return SOURCE_NOT_FOUND. Available to "
        "viewer, reviewer and admin."
    ),
)
async def get_research_source(
    source_id: Annotated[str, Path(description="Opaque research-source identifier.")],
) -> ResearchSourceDetail:
    service = _service()
    try:
        descriptor = service.get_source(source_id)
    except SourceNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code=ErrorCode.SOURCE_NOT_FOUND,
            details={"source_id": source_id},
        ) from exc
    except (ResearchUnavailableError, ResearchIntegrityError) as exc:
        raise ApiError(
            status_code=503,
            code=ErrorCode.SERVICE_NOT_READY,
            details={"dependency": "research-source"},
        ) from exc
    return _detail(descriptor)


@router.get(
    "/sources/{source_id}/results",
    response_model=ResearchResultsResponse,
    responses=_ERROR_RESPONSES,
    summary="Get precomputed research results",
    description=(
        "Fetches the precomputed aggregate reference values for one "
        "approved read-only research source, with full provenance, the "
        "frozen interpretation principles, the exploratory-selection caveat "
        "and the scientific limitations. The response always carries "
        "is_precomputed=true and is_live_prediction=false. Unknown "
        "identifiers return SOURCE_NOT_FOUND. Available to viewer, reviewer "
        "and admin."
    ),
)
async def get_research_results(
    source_id: Annotated[str, Path(description="Opaque research-source identifier.")],
) -> ResearchResultsResponse:
    service = _service()
    try:
        payload = service.get_results(source_id)
    except SourceNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code=ErrorCode.SOURCE_NOT_FOUND,
            details={"source_id": source_id},
        ) from exc
    except (ResearchUnavailableError, ResearchIntegrityError) as exc:
        raise ApiError(
            status_code=503,
            code=ErrorCode.SERVICE_NOT_READY,
            details={"dependency": "research-source"},
        ) from exc
    # Validate the results list through the item model so the value_type tag
    # and the int/float/str shape are enforced on the way out.
    payload = {
        **payload,
        "results": [
            ResearchResultItem.model_validate(item).model_dump()
            for item in payload["results"]
        ],
    }
    return ResearchResultsResponse.model_validate(payload)
