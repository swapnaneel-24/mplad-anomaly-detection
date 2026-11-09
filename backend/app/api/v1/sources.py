"""Approved source registry endpoints (architectural seam).

* ``GET /api/v1/sources`` — list registered (approved) sources. PR-02
  returns an empty list: no sources have been admitted yet.
* ``GET /api/v1/sources/{source_id}`` — fetch one registered source by its
  opaque slug; currently always ``SOURCE_NOT_FOUND``.

The registry is a server-side abstraction only. Identifiers are strictly
validated opaque slugs: path-like values are rejected with
``INVALID_SOURCE_ID``. There is no directory scanning, no frozen-artifact
reading, no DVC access and no generic file-reading capability behind
these routes.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, Request

from app.contracts.common import (
    DatasetKind,
    ErrorEnvelope,
    SourceListResponse,
    SourceSummary,
)
from app.core.errors import ApiError, ErrorCode
from app.services.source_registry import (
    SourceDescriptor,
    SourceIdValidationError,
    SourceNotFoundError,
    validate_source_id,
)

router = APIRouter(prefix="/sources", tags=["sources"])


def _descriptor_to_summary(descriptor: SourceDescriptor) -> SourceSummary:
    return SourceSummary(
        source_id=descriptor.source_id,
        dataset_kind=descriptor.dataset_kind,
        integrity_status=descriptor.integrity_status,
        analysis_status=descriptor.analysis_status,
    )


@router.get(
    "",
    response_model=SourceListResponse,
    responses={
        422: {
            "model": ErrorEnvelope,
            "description": "Validation error (invalid dataset_kind filter).",
        },
    },
    summary="List approved sources",
    description="Lists the approved, registered data sources. No sources are "
    "admitted in PR-02, so this returns an empty list. Sources are never "
    "discovered by scanning the filesystem.",
)
async def list_sources(
    request: Request,
    dataset_kind: DatasetKind | None = Query(
        default=None,
        description="Optional dataset-kind filter.",
    ),
) -> SourceListResponse:
    registry = request.app.state.source_registry
    sources = [
        _descriptor_to_summary(descriptor)
        for descriptor in registry.list_sources()
        if dataset_kind is None or descriptor.dataset_kind == dataset_kind
    ]
    return SourceListResponse(sources=sources, count=len(sources))


@router.get(
    "/{source_id}",
    response_model=SourceSummary,
    responses={
        404: {"model": ErrorEnvelope, "description": "Source not registered."},
        422: {"model": ErrorEnvelope, "description": "Invalid source identifier."},
    },
    summary="Get one approved source",
    description="Fetches a single approved source by its opaque registered "
    "identifier. Path-like identifiers are rejected.",
)
async def get_source(source_id: str, request: Request) -> SourceSummary:
    try:
        validated = validate_source_id(source_id)
    except SourceIdValidationError as exc:
        raise ApiError(
            status_code=422,
            code=ErrorCode.INVALID_SOURCE_ID,
            details={"reason": "not_an_opaque_slug"},
        ) from exc
    try:
        descriptor = registry_get(request, validated)
    except SourceNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code=ErrorCode.SOURCE_NOT_FOUND,
            details={"source_id": validated},
        ) from exc
    return _descriptor_to_summary(descriptor)


def registry_get(request: Request, source_id: str) -> SourceDescriptor:
    """Resolve a validated source ID through the app-scoped registry."""
    return request.app.state.source_registry.get_source(source_id)
