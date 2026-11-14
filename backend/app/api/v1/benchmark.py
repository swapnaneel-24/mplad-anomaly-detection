"""Read-only canonical benchmark endpoints (PR-09).

Routes (all under ``/api/v1/research``, extending the PR-08 research API):

* ``GET /research/benchmark/experiments``     -- the verified ten-run
  catalog with per-capability availability (Layer A; works on a clean
  checkout without DVC payloads).
* ``GET /research/benchmark/experiments/{run_id}`` -- one run's full
  descriptor with configuration provenance and dataset scope (Layer A).
* ``GET /research/benchmark/metrics``         -- the verified saved Phase 4
  metrics for all ten runs (Layer B; requires the admitted DVC payload).
* ``GET /research/benchmark/experiments/{run_id}/records/{row_id}`` -- one
  canonical record resolved by exact saved ``row_id`` (Layer B).

Why the existing PR-08 routes cannot cover these operations: they are keyed
by the single Phase 6 aggregate ``source_id`` and serve one frozen results
payload; the benchmark needs a per-run catalog keyed by ``run_id``, a
metrics table with per-metric denominator semantics, and a record lookup
keyed by ``(run_id, row_id)`` — different resources, so separate operations
on the same research router (no overlapping registry, same error envelope).

Security and scope:

* All four endpoints are GET-only, read-only and publicly readable
  (FR-03 / ADR-007: approved research views are public read-only).
* ``run_id`` and ``row_id`` are validated against fixed allowlists /
  value rules; they are never used to construct filesystem paths.
* Unknown run IDs return a structured 404 ``SOURCE_NOT_FOUND``.
* DVC-dependent routes return a sanitized 503 ``SERVICE_NOT_READY`` with a
  machine-readable ``reason`` (``artifact_missing`` or
  ``integrity_failed``) when the payload is absent or fails verification.
* No endpoint fits a model, deserializes a pickle, or downloads anything.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path

from app.contracts.benchmark import (
    BenchmarkCatalogResponse,
    BenchmarkExperimentDetail,
    BenchmarkExperimentSummary,
    BenchmarkMetricsResponse,
    BenchmarkRecordResponse,
    BenchmarkRunMetrics,
)
from app.contracts.common import ErrorEnvelope
from app.core.errors import ApiError, ErrorCode
from app.services.benchmark_catalog import (
    BENCHMARK_CATALOG_SERVICE,
    BenchmarkCatalogService,
    BenchmarkIntegrityError,
    BenchmarkUnavailableError,
)
from app.services.source_registry import SourceNotFoundError

router = APIRouter(prefix="/research/benchmark", tags=["research"])

_ERROR_RESPONSES = {
    404: {"model": ErrorEnvelope, "description": "Unknown benchmark run or record."},
    503: {
        "model": ErrorEnvelope,
        "description": "Benchmark payload unavailable or integrity failure.",
    },
}

RunId = Annotated[
    str,
    Path(
        description=(
            "Canonical run identifier (IF_001..IF_005, LOF_001..LOF_005)."
        )
    ),
]

RowId = Annotated[
    int,
    Path(
        description=(
            "Canonical ULB row identifier; the record is resolved by the "
            "exact saved row_id, never by physical row order."
        ),
        ge=0,
        le=2_147_483_647,
    ),
]


def _service() -> BenchmarkCatalogService:
    """Build the read-only benchmark catalog service.

    The service is stateless beyond the module-level verified caches, which
    are populated lazily and re-verified on every request.
    """
    return BENCHMARK_CATALOG_SERVICE


def _unavailable(exc: Exception, reason: str) -> ApiError:
    return ApiError(
        status_code=503,
        code=ErrorCode.SERVICE_NOT_READY,
        details={"dependency": "benchmark-evidence", "reason": reason},
    )


@router.get(
    "/experiments",
    response_model=BenchmarkCatalogResponse,
    responses=_ERROR_RESPONSES,
    summary="List the canonical benchmark experiments",
    description=(
        "Lists the ten canonical Stream A Isolation Forest / Local Outlier "
        "Factor runs (IF_001..IF_005, LOF_001..LOF_005) with their exact "
        "source-backed parameter configurations and per-capability "
        "availability of the DVC-backed evidence layers. The catalog itself "
        "is served entirely from Git-tracked, manifest-verified metadata "
        "and works on a clean checkout without DVC payloads. Publicly "
        "readable (GET-only, read-only per FR-03 / ADR-007)."
    ),
)
async def list_benchmark_experiments() -> BenchmarkCatalogResponse:
    service = _service()
    try:
        experiments = service.list_experiments()
        availability = service.availability()
    except BenchmarkUnavailableError as exc:
        raise _unavailable(exc, "source_not_admitted") from exc
    except BenchmarkIntegrityError as exc:
        raise _unavailable(exc, "integrity_failed") from exc
    items = [BenchmarkExperimentSummary.model_validate(e) for e in experiments]
    return BenchmarkCatalogResponse(
        source_id=service.source_id,
        dataset_id=service.dataset_id,
        experiments=items,
        count=len(items),
        capabilities=availability,
        limitations=service.limitations,
    )


@router.get(
    "/experiments/{run_id}",
    response_model=BenchmarkExperimentDetail,
    responses=_ERROR_RESPONSES,
    summary="Get one benchmark experiment's full descriptor",
    description=(
        "Fetches one canonical run's exact parameter configuration with its "
        "verified provenance, the fixed pipeline settings, the frozen "
        "dataset scope (30,000-row sample, 47 fraud labels, bottom-1% "
        "threshold, score orientation) and the full provenance chain "
        "(config module, Phase 4 run metadata, commit manifest). Unknown "
        "run identifiers return SOURCE_NOT_FOUND. Publicly readable."
    ),
)
async def get_benchmark_experiment(run_id: RunId) -> BenchmarkExperimentDetail:
    service = _service()
    try:
        descriptor = service.get_experiment(run_id)
    except SourceNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code=ErrorCode.SOURCE_NOT_FOUND,
            details={"run_id": run_id},
        ) from exc
    except BenchmarkUnavailableError as exc:
        raise _unavailable(exc, "source_not_admitted") from exc
    except BenchmarkIntegrityError as exc:
        raise _unavailable(exc, "integrity_failed") from exc
    return BenchmarkExperimentDetail.model_validate(descriptor)


@router.get(
    "/metrics",
    response_model=BenchmarkMetricsResponse,
    responses=_ERROR_RESPONSES,
    summary="Get the verified saved benchmark metrics",
    description=(
        "Fetches the saved Phase 4 evaluation metrics for all ten canonical "
        "runs, exactly as stored in the admitted DVC-backed artifact and "
        "only after its md5/size verification against the Git-tracked DVC "
        "pointer. Every metric travels with its definition and denominator "
        "semantics. Requires the DVC payload to be present; when it is "
        "absent the route returns 503 SERVICE_NOT_READY with reason "
        "artifact_missing (the configuration catalog remains available). "
        "Publicly readable."
    ),
)
async def get_benchmark_metrics() -> BenchmarkMetricsResponse:
    service = _service()
    try:
        payload = service.get_metrics()
    except BenchmarkUnavailableError as exc:
        raise _unavailable(exc, "artifact_missing") from exc
    except BenchmarkIntegrityError as exc:
        raise _unavailable(exc, "integrity_failed") from exc
    payload = {
        **payload,
        "metrics": [
            BenchmarkRunMetrics.model_validate(m).model_dump()
            for m in payload["metrics"]
        ],
    }
    return BenchmarkMetricsResponse.model_validate(payload)


@router.get(
    "/experiments/{run_id}/records/{row_id}",
    response_model=BenchmarkRecordResponse,
    responses=_ERROR_RESPONSES,
    summary="Look up one canonical record by row_id",
    description=(
        "Returns one saved record of the selected canonical run, resolved "
        "by the exact saved ULB row_id (never by physical row order). The "
        "response distinguishes the ground-truth Class label from the "
        "detector flag, and the native estimator score from the oriented "
        "anomaly_score. No rank, top-k threshold or prediction is computed. "
        "Requires the DVC-backed evaluation dataset; when absent the route "
        "returns 503 SERVICE_NOT_READY with reason artifact_missing. "
        "Unknown run or row identifiers return SOURCE_NOT_FOUND. Publicly "
        "readable."
    ),
)
async def get_benchmark_record(run_id: RunId, row_id: RowId) -> BenchmarkRecordResponse:
    service = _service()
    try:
        payload = service.get_record(run_id, row_id)
    except SourceNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code=ErrorCode.SOURCE_NOT_FOUND,
            details={"run_id": run_id, "row_id": row_id},
        ) from exc
    except BenchmarkUnavailableError as exc:
        raise _unavailable(exc, "artifact_missing") from exc
    except BenchmarkIntegrityError as exc:
        raise _unavailable(exc, "integrity_failed") from exc
    return BenchmarkRecordResponse.model_validate(payload)
