"""Authenticated review-case API (PR-05B §6).

Endpoints (all under ``/api/v1/cases``):

* ``GET    /cases``                        — paginated accessible case list.
* ``POST   /cases``                        — create a review case.
* ``GET    /cases/{case_id}``              — retrieve one case.
* ``GET    /cases/{case_id}/history``      — ordered audit events.
* ``POST   /cases/{case_id}/notes``        — add a reviewer note.
* ``POST   /cases/{case_id}/transitions``  — change review status.
* ``POST   /cases/{case_id}/decisions``    — record a structured decision.

Security (PR-05B §7, §14):

* Every endpoint requires an authenticated principal (PR-04
  ``require_authenticated``).
* Read endpoints (GET) permit viewer, reviewer and admin.
* Write endpoints (POST) permit reviewer and admin only; viewer
  receives a sanitized 403 FORBIDDEN.
* Every state-changing endpoint enforces CSRF (PR-04 ``require_csrf``).
* Actor identity is bound from the authenticated principal via
  ``actor_ref_from_principal`` — never from the request payload. The
  ``actor_ref`` and ``created_by`` fields on request bodies are
  ignored and overwritten with the principal's user UUID.
* The case-creation endpoint validates that the referenced synthetic
  record exists before creating the case.

Optimistic concurrency (PR-05B §9):

* Every mutating endpoint takes ``expected_version``. A stale version
  raises ``ConcurrencyConflictError`` → 409 CONFLICT with the current
  case version in ``details``.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, Response, Security

from app.auth.dependencies import require_authenticated, require_csrf, require_role
from app.auth.principals import AuthenticatedPrincipal, actor_ref_from_principal
from app.auth.roles import Role
from app.contracts.common import ErrorEnvelope
from app.contracts.review_cases import (
    AddNoteRequest,
    CaseDetail,
    CaseHistoryResponse,
    CaseListResponse,
    CaseSummary,
    CreateCaseRequest,
    RecordDecisionRequest,
    TransitionStatusRequest,
)
from app.core.errors import ApiError, ErrorCode
from app.domain.statuses import IllegalTransitionError, ReviewStatus
from app.repositories.review_cases import CaseNotFoundError, ConcurrencyConflictError
from app.services.review_cases import ReviewCaseService
from app.services.synthetic_source import (
    SYNTHETIC_DATASET_ID,
    SYNTHETIC_SNAPSHOT_ID,
    SYNTHETIC_SOURCE_REGISTRY,
    SyntheticRecordNotFoundError,
)

router = APIRouter(prefix="/cases", tags=["cases"])

_ERROR_RESPONSES = {
    400: {"model": ErrorEnvelope, "description": "Bad request."},
    401: {"model": ErrorEnvelope, "description": "Authentication required."},
    403: {"model": ErrorEnvelope, "description": "Forbidden (insufficient role or CSRF failure)."},
    404: {"model": ErrorEnvelope, "description": "Case not found."},
    409: {"model": ErrorEnvelope, "description": "Optimistic concurrency conflict."},
    422: {"model": ErrorEnvelope, "description": "Validation error."},
    429: {"model": ErrorEnvelope, "description": "Too many requests."},
    503: {"model": ErrorEnvelope, "description": "Service not ready (database unavailable)."},
}


def _case_service(request: Request) -> ReviewCaseService:
    """Build the ReviewCaseService from app state; fail closed when unset."""
    db_factory = getattr(request.app.state, "db_session_factory", None)
    if db_factory is None:
        raise ApiError(
            status_code=503,
            code=ErrorCode.SERVICE_NOT_READY,
            details={"dependency": "database"},
        )
    return ReviewCaseService(db_factory.session_factory)


def _require_synthetic_enabled(request: Request) -> None:
    """Reject case creation when the demonstration source is disabled."""
    settings = request.app.state.settings
    if not getattr(settings, "demonstration_sources", False):
        raise ApiError(
            status_code=503,
            code= ErrorCode.SERVICE_NOT_READY,
            details={"dependency": "demonstration-sources"},
        )


# ---------------------------------------------------------------------------
# GET /cases — paginated list (viewer, reviewer, admin)
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=CaseListResponse,
    responses=_ERROR_RESPONSES,
    summary="List review cases",
    description="Paginated list of accessible review cases, deterministically "
    "ordered by created_at then id. Available to viewer, reviewer and admin.",
)
async def list_cases(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Security(require_authenticated)],
    status: ReviewStatus | None = Query(default=None, description="Optional status filter."),
    limit: int = Query(default=50, ge=1, le=100, description="Page size (1–100)."),
    offset: int = Query(default=0, ge=0, description="Page offset."),
) -> CaseListResponse:
    service = _case_service(request)
    return service.list_cases(status=status, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# POST /cases — create (reviewer, admin)
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=CaseDetail,
    status_code=201,
    dependencies=[Depends(require_csrf), Depends(require_role(Role.REVIEWER, Role.ADMIN))],
    responses=_ERROR_RESPONSES,
    summary="Create a review case",
    description="Creates a review case bound to a synthetic demonstration "
    "record. The actor is derived from the authenticated principal; "
    "client-supplied created_by is ignored. Requires reviewer or admin role.",
)
async def create_case(
    request: Request,
    payload: CreateCaseRequest,
    principal: Annotated[AuthenticatedPrincipal, Security(require_authenticated)],
    response: Response,
) -> CaseDetail:
    _require_synthetic_enabled(request)
    # Validate the synthetic record reference. The case must be created
    # from a known synthetic record; the record's dataset_id and
    # snapshot_id are authoritative (the client cannot supply arbitrary
    # values).
    try:
        record = SYNTHETIC_SOURCE_REGISTRY.get_record(payload.record_ref)
    except SyntheticRecordNotFoundError as exc:
        raise ApiError(
            status_code=422,
            code=ErrorCode.VALIDATION_ERROR,
            message="The referenced record does not exist in the synthetic demonstration set.",
            details={"record_ref": payload.record_ref},
        ) from exc
    # Override dataset_id / snapshot_id with the authoritative synthetic
    # values; the client cannot spoof these.
    trusted_request = CreateCaseRequest(
        dataset_id=record.dataset_id,
        snapshot_id=record.snapshot_id,
        record_ref=record.record_ref,
        title=payload.title,
        summary=payload.summary,
        created_by=actor_ref_from_principal(principal),
    )
    service = _case_service(request)
    detail = service.create_case(trusted_request)
    response.headers["Location"] = f"/api/v1/cases/{detail.id}"
    return detail


# ---------------------------------------------------------------------------
# GET /cases/{case_id} — retrieve one (viewer, reviewer, admin)
# ---------------------------------------------------------------------------


@router.get(
    "/{case_id}",
    response_model=CaseDetail,
    responses=_ERROR_RESPONSES,
    summary="Retrieve a review case",
    description="Retrieves a single review case by its server-generated UUID. "
    "Available to viewer, reviewer and admin.",
)
async def get_case(
    request: Request,
    case_id: Annotated[str, Path(description="Case UUID.")],
    principal: Annotated[AuthenticatedPrincipal, Security(require_authenticated)],
) -> CaseDetail:
    _validate_uuid(case_id)
    service = _case_service(request)
    try:
        return service.get_case(case_id)
    except CaseNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code=ErrorCode.CASE_NOT_FOUND,
            details={"case_id": case_id},
        ) from exc


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/history — ordered audit events (viewer, reviewer, admin)
# ---------------------------------------------------------------------------


@router.get(
    "/{case_id}/history",
    response_model=CaseHistoryResponse,
    responses=_ERROR_RESPONSES,
    summary="Retrieve case event history",
    description="Returns the append-only event history for a case, "
    "deterministically ordered by case_version then event_seq. Available "
    "to viewer, reviewer and admin.",
)
async def get_case_history(
    request: Request,
    case_id: Annotated[str, Path(description="Case UUID.")],
    principal: Annotated[AuthenticatedPrincipal, Security(require_authenticated)],
) -> CaseHistoryResponse:
    _validate_uuid(case_id)
    service = _case_service(request)
    try:
        return service.get_case_history(case_id)
    except CaseNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code=ErrorCode.CASE_NOT_FOUND,
            details={"case_id": case_id},
        ) from exc


# ---------------------------------------------------------------------------
# POST /cases/{case_id}/notes — add note (reviewer, admin)
# ---------------------------------------------------------------------------


@router.post(
    "/{case_id}/notes",
    response_model=CaseDetail,
    dependencies=[Depends(require_csrf), Depends(require_role(Role.REVIEWER, Role.ADMIN))],
    responses=_ERROR_RESPONSES,
    summary="Add a reviewer note",
    description="Appends a reviewer note as a note_added event and bumps the "
    "case version. The actor is derived from the authenticated principal. "
    "Requires reviewer or admin role.",
)
async def add_note(
    request: Request,
    case_id: Annotated[str, Path(description="Case UUID.")],
    payload: AddNoteRequest,
    principal: Annotated[AuthenticatedPrincipal, Security(require_authenticated)],
) -> CaseDetail:
    _validate_uuid(case_id)
    # Override actor_ref with the principal's trusted identity.
    trusted_request = AddNoteRequest(
        note_text=payload.note_text,
        actor_ref=actor_ref_from_principal(principal),
        expected_version=payload.expected_version,
    )
    service = _case_service(request)
    try:
        return service.add_note(case_id, trusted_request)
    except CaseNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code=ErrorCode.CASE_NOT_FOUND,
            details={"case_id": case_id},
        ) from exc
    except ConcurrencyConflictError as exc:
        raise ApiError(
            status_code=409,
            code=ErrorCode.CONFLICT,
            message="The case was modified by another reviewer. Reload the latest version and retry.",
            details={
                "case_id": case_id,
                "expected_version": exc.expected_version,
            },
        ) from exc


# ---------------------------------------------------------------------------
# POST /cases/{case_id}/transitions — change status (reviewer, admin)
# ---------------------------------------------------------------------------


@router.post(
    "/{case_id}/transitions",
    response_model=CaseDetail,
    dependencies=[Depends(require_csrf), Depends(require_role(Role.REVIEWER, Role.ADMIN))],
    responses=_ERROR_RESPONSES,
    summary="Change review status",
    description="Applies a legal status transition (PR-03 domain validator). "
    "The actor is derived from the authenticated principal. Requires "
    "reviewer or admin role.",
)
async def transition_status(
    request: Request,
    case_id: Annotated[str, Path(description="Case UUID.")],
    payload: TransitionStatusRequest,
    principal: Annotated[AuthenticatedPrincipal, Security(require_authenticated)],
) -> CaseDetail:
    _validate_uuid(case_id)
    trusted_request = TransitionStatusRequest(
        to_status=payload.to_status,
        reason=payload.reason,
        actor_ref=actor_ref_from_principal(principal),
        expected_version=payload.expected_version,
    )
    service = _case_service(request)
    try:
        return service.transition_status(case_id, trusted_request)
    except CaseNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code=ErrorCode.CASE_NOT_FOUND,
            details={"case_id": case_id},
        ) from exc
    except IllegalTransitionError as exc:
        raise ApiError(
            status_code=422,
            code=ErrorCode.INVALID_TRANSITION,
            message=str(exc),
            details={
                "from_status": exc.from_status.value,
                "to_status": exc.to_status.value,
            },
        ) from exc
    except ConcurrencyConflictError as exc:
        raise ApiError(
            status_code=409,
            code=ErrorCode.CONFLICT,
            message="The case was modified by another reviewer. Reload the latest version and retry.",
            details={
                "case_id": case_id,
                "expected_version": exc.expected_version,
            },
        ) from exc


# ---------------------------------------------------------------------------
# POST /cases/{case_id}/decisions — record decision (reviewer, admin)
# ---------------------------------------------------------------------------


@router.post(
    "/{case_id}/decisions",
    response_model=CaseDetail,
    dependencies=[Depends(require_csrf), Depends(require_role(Role.REVIEWER, Role.ADMIN))],
    responses=_ERROR_RESPONSES,
    summary="Record a structured decision",
    description="Records a structured decision (outcome + rationale). When "
    "the outcome changes the status, a status_changed event is also written "
    "in the same transaction. The actor is derived from the authenticated "
    "principal. Requires reviewer or admin role.",
)
async def record_decision(
    request: Request,
    case_id: Annotated[str, Path(description="Case UUID.")],
    payload: RecordDecisionRequest,
    principal: Annotated[AuthenticatedPrincipal, Security(require_authenticated)],
) -> CaseDetail:
    _validate_uuid(case_id)
    trusted_request = RecordDecisionRequest(
        outcome=payload.outcome,
        rationale=payload.rationale,
        actor_ref=actor_ref_from_principal(principal),
        expected_version=payload.expected_version,
    )
    service = _case_service(request)
    try:
        return service.record_decision(case_id, trusted_request)
    except CaseNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code=ErrorCode.CASE_NOT_FOUND,
            details={"case_id": case_id},
        ) from exc
    except IllegalTransitionError as exc:
        raise ApiError(
            status_code=422,
            code=ErrorCode.INVALID_TRANSITION,
            message=str(exc),
            details={
                "from_status": exc.from_status.value,
                "to_status": exc.to_status.value,
            },
        ) from exc
    except ConcurrencyConflictError as exc:
        raise ApiError(
            status_code=409,
            code=ErrorCode.CONFLICT,
            message="The case was modified by another reviewer. Reload the latest version and retry.",
            details={
                "case_id": case_id,
                "expected_version": exc.expected_version,
            },
        ) from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_uuid(value: str) -> None:
    """Reject non-UUID path parameters with 422 (not 404, to avoid scanning)."""
    try:
        uuid.UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ApiError(
            status_code=422,
            code=ErrorCode.VALIDATION_ERROR,
            message="case_id must be a valid UUID.",
            details={"case_id": value},
        ) from exc
