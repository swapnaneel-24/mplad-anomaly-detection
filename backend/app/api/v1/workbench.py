"""Read-only workbench endpoints for local PMGSY snapshot and case-linked packages."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.contracts.common import ErrorEnvelope
from app.core.errors import ApiError, ErrorCode
from app.services.workbench_pmgsy import (
    WorkbenchLookupError,
    WorkbenchPackageDetail,
    WorkbenchPackageSummary,
    WorkbenchSnapshotDetail,
    get_workbench_pmgsy_package,
    get_workbench_snapshot,
    list_workbench_pmgsy_packages,
    list_workbench_snapshots,
)

router = APIRouter(prefix="/workbench", tags=["workbench"])


class WorkbenchSnapshotListResponse(BaseModel):
    snapshots: list[WorkbenchSnapshotDetail]
    count: int


class WorkbenchPackageListResponse(BaseModel):
    packages: list[WorkbenchPackageSummary]
    count: int


def _resolve_repo_root(request: Request) -> Path:
    configured = getattr(request.app.state, "repo_root", None)
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[4]


@router.get(
    "/snapshots",
    response_model=WorkbenchSnapshotListResponse,
    summary="List local read-only workbench snapshots",
)
async def get_snapshots(request: Request) -> WorkbenchSnapshotListResponse:
    repo_root = _resolve_repo_root(request)
    snaps = list_workbench_snapshots(repo_root)
    return WorkbenchSnapshotListResponse(snapshots=snaps, count=len(snaps))


@router.get(
    "/snapshots/{snapshot_id}",
    response_model=WorkbenchSnapshotDetail,
    responses={
        404: {"model": ErrorEnvelope, "description": "Snapshot not found."},
    },
    summary="Get one local read-only workbench snapshot",
)
async def get_snapshot(snapshot_id: str, request: Request) -> WorkbenchSnapshotDetail:
    repo_root = _resolve_repo_root(request)
    try:
        return get_workbench_snapshot(repo_root, snapshot_id)
    except WorkbenchLookupError as exc:
        raise ApiError(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            details={"snapshot_id": snapshot_id},
        ) from exc


@router.get(
    "/pmgsy/packages",
    response_model=WorkbenchPackageListResponse,
    summary="List case-linked PMGSY package summaries (read-only)",
)
async def get_pmgsy_packages(request: Request) -> WorkbenchPackageListResponse:
    repo_root = _resolve_repo_root(request)
    pkgs = list_workbench_pmgsy_packages(repo_root)
    return WorkbenchPackageListResponse(packages=pkgs, count=len(pkgs))


@router.get(
    "/pmgsy/packages/{case_id}",
    response_model=WorkbenchPackageDetail,
    responses={
        404: {"model": ErrorEnvelope, "description": "Case-linked package not found."},
    },
    summary="Get grouped metadata and provenance for one PMGSY case-linked package",
)
async def get_pmgsy_package(case_id: str, request: Request) -> WorkbenchPackageDetail:
    repo_root = _resolve_repo_root(request)
    try:
        return get_workbench_pmgsy_package(repo_root, case_id)
    except WorkbenchLookupError as exc:
        raise ApiError(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            details={"case_id": case_id},
        ) from exc

from app.services.workbench_investigations import (
    AppendReviewerNoteRequest,
    AppendReviewerNoteResponse,
    InvestigationConflictError,
    InvestigationDetail,
    InvestigationHistoryResponse,
    InvestigationIntegrityError,
    InvestigationSummary,
    InvestigationValidationError,
    append_workbench_reviewer_note,
    get_workbench_investigation_detail,
    get_workbench_investigation_history,
    list_workbench_investigations,
)


class WorkbenchInvestigationListResponse(BaseModel):
    investigations: list[InvestigationSummary]
    count: int


def _extract_optional_actor(request: Request) -> str | None:
    principal = getattr(request.state, "principal", None)
    if principal is not None:
        for attr in ("user_id", "subject", "actor_ref", "email"):
            val = getattr(principal, attr, None)
            if isinstance(val, str) and val.strip():
                return val.strip()
    header_actor = request.headers.get("X-Reviewer-Id")
    if header_actor and header_actor.strip():
        return header_actor.strip()
    return None


@router.get(
    "/investigations",
    response_model=WorkbenchInvestigationListResponse,
    summary="List all 42 PMGSY investigation summaries (read-only)",
)
async def get_investigations(request: Request) -> WorkbenchInvestigationListResponse:
    repo_root = _resolve_repo_root(request)
    items = list_workbench_investigations(repo_root)
    return WorkbenchInvestigationListResponse(investigations=items, count=len(items))


@router.get(
    "/investigations/{case_id}",
    response_model=InvestigationDetail,
    responses={
        404: {"model": ErrorEnvelope, "description": "Investigation case not found."},
    },
    summary="Get grouped investigation evidence, verification, and provenance for one case",
)
async def get_investigation_detail(case_id: str, request: Request) -> InvestigationDetail:
    repo_root = _resolve_repo_root(request)
    try:
        return get_workbench_investigation_detail(repo_root, case_id)
    except WorkbenchLookupError as exc:
        raise ApiError(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            details={"case_id": case_id},
        ) from exc


@router.get(
    "/investigations/{case_id}/history",
    response_model=InvestigationHistoryResponse,
    responses={
        404: {"model": ErrorEnvelope, "description": "Investigation case not found."},
    },
    summary="Get immutable frozen baseline and separate append-only app event stream for a case",
)
async def get_investigation_history(case_id: str, request: Request) -> InvestigationHistoryResponse:
    repo_root = _resolve_repo_root(request)
    try:
        return get_workbench_investigation_history(repo_root, case_id)
    except WorkbenchLookupError as exc:
        raise ApiError(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            details={"case_id": case_id},
        ) from exc


@router.post(
    "/investigations/{case_id}/notes",
    response_model=AppendReviewerNoteResponse,
    responses={
        404: {"model": ErrorEnvelope, "description": "Investigation case not found."},
        409: {"model": ErrorEnvelope, "description": "Event chain head conflict."},
        422: {"model": ErrorEnvelope, "description": "Invalid note or disallowed transition."},
        503: {"model": ErrorEnvelope, "description": "Provenance or event chain integrity failure."},
    },
    summary="Append a reviewer note to the separate application event stream",
)
async def post_investigation_note(
    case_id: str,
    payload: AppendReviewerNoteRequest,
    request: Request,
) -> AppendReviewerNoteResponse:
    repo_root = _resolve_repo_root(request)
    actor = _extract_optional_actor(request)
    try:
        return append_workbench_reviewer_note(
            repo_root,
            case_id,
            payload,
            authenticated_actor=actor,
        )
    except WorkbenchLookupError as exc:
        raise ApiError(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            details={"case_id": case_id},
        ) from exc
    except InvestigationValidationError as exc:
        raise ApiError(
            status_code=422,
            code=ErrorCode.VALIDATION_ERROR,
            details={"reason": str(exc)},
        ) from exc
    except InvestigationConflictError as exc:
        raise ApiError(
            status_code=409,
            code=ErrorCode.CONFLICT,
            details=exc.details,
        ) from exc
    except InvestigationIntegrityError as exc:
        raise ApiError(
            status_code=503,
            code=ErrorCode.SERVICE_NOT_READY,
            details={"integrity_code": exc.code, "reason": str(exc), **exc.details},
        ) from exc
