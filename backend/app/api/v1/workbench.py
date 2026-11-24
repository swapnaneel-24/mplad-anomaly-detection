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
