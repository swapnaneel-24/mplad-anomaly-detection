"""Synthetic demonstration record endpoints (PR-05B §5).

* ``GET /api/v1/synthetic/records`` — list synthetic demonstration records.
* ``GET /api/v1/synthetic/records/{record_ref}`` — fetch one record by ref.

These routes are **only** registered when the ``demonstration_sources``
configuration flag is true (``PEIARS_DEMONSTRATION_SOURCES=true``).
When the flag is false, the routes are not mounted and return 404.

The records are explicitly fictional (see
:mod:`app.services.synthetic_source`). No ML anomaly score is exposed.
The ``synthetic`` field on every response is always ``true``.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.contracts.common import (
    ErrorEnvelope,
    SyntheticRecordDetail,
    SyntheticRecordListResponse,
    SyntheticRecordSummary,
)
from app.core.errors import ApiError, ErrorCode
from app.services.synthetic_source import (
    SYNTHETIC_DATASET_ID,
    SYNTHETIC_SNAPSHOT_ID,
    SYNTHETIC_SOURCE_REGISTRY,
    SyntheticRecordNotFoundError,
)

router = APIRouter(prefix="/synthetic", tags=["synthetic"])


def _to_summary(record) -> SyntheticRecordSummary:
    return SyntheticRecordSummary(
        record_ref=record.record_ref,
        title=record.title,
        dataset_id=record.dataset_id,
        snapshot_id=record.snapshot_id,
        synthetic=True,
    )


def _to_detail(record) -> SyntheticRecordDetail:
    return SyntheticRecordDetail(
        record_ref=record.record_ref,
        title=record.title,
        description=record.description,
        evidence_summary=record.evidence_summary,
        administrative_context=record.administrative_context,
        limitations=record.limitations,
        dataset_id=record.dataset_id,
        snapshot_id=record.snapshot_id,
        synthetic=True,
    )


@router.get(
    "/records",
    response_model=SyntheticRecordListResponse,
    responses={503: {"model": ErrorEnvelope, "description": "Synthetic source not enabled."}},
    summary="List synthetic demonstration records",
    description="Lists the deterministic synthetic demonstration records. "
    "Explicitly fictional — NOT research findings. Only available when "
    "the demonstration_sources flag is enabled.",
)
async def list_synthetic_records(request: Request) -> SyntheticRecordListResponse:
    _require_demonstration_enabled(request)
    records = SYNTHETIC_SOURCE_REGISTRY.list_records()
    return SyntheticRecordListResponse(
        items=[_to_summary(r) for r in records],
        total=len(records),
        dataset_id=SYNTHETIC_DATASET_ID,
        snapshot_id=SYNTHETIC_SNAPSHOT_ID,
    )


@router.get(
    "/records/{record_ref}",
    response_model=SyntheticRecordDetail,
    responses={
        404: {"model": ErrorEnvelope, "description": "Synthetic record not found."},
        503: {"model": ErrorEnvelope, "description": "Synthetic source not enabled."},
    },
    summary="Get one synthetic demonstration record",
    description="Fetches one synthetic demonstration record by its stable "
    "record_ref. Explicitly fictional — NOT a research finding.",
)
async def get_synthetic_record(record_ref: str, request: Request) -> SyntheticRecordDetail:
    _require_demonstration_enabled(request)
    try:
        record = SYNTHETIC_SOURCE_REGISTRY.get_record(record_ref)
    except SyntheticRecordNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            details={"record_ref": record_ref},
        ) from exc
    return _to_detail(record)


def _require_demonstration_enabled(request: Request) -> None:
    """Reject the request when the demonstration_sources flag is off."""
    settings = request.app.state.settings
    if not getattr(settings, "demonstration_sources", False):
        raise ApiError(
            status_code=503,
            code=ErrorCode.SERVICE_NOT_READY,
            details={"dependency": "demonstration-sources"},
        )
