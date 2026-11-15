"""Read-only Phase 5A evidence endpoints (PR-10).

Routes (all under ``/api/v1/research/phase5a``, extending the research API):

* ``GET /phase5a``                                   -- verified protocol
  metadata + per-family availability (Layer A; clean-checkout safe).
* ``GET /phase5a/bootstrap``                         -- saved bootstrap
  uncertainty intervals (Layer B).
* ``GET /phase5a/paired-differences``                -- saved paired bootstrap
  differences (Layer B).
* ``GET /phase5a/agreement/{kind}``                  -- saved 10×10 Spearman
  or Jaccard matrix (Layer B).
* ``GET /phase5a/overlap-null``                      -- saved hypergeometric
  overlap result (Layer B).
* ``GET /phase5a/groups``                            -- saved four-way
  agreement groups (Layer B).
* ``GET /phase5a/policies``                          -- four review policies
  with actual (unequal) review costs (Layer B).
* ``GET /phase5a/thresholds``                        -- saved multi-threshold
  sensitivity (Layer B).
* ``GET /phase5a/discovery-curve``                  -- bounded page of the
  saved fraud-discovery curve (Layer B).

All endpoints are GET-only, read-only, and publicly readable (FR-03 /
ADR-007). ``run_id`` / ``kind`` are validated against fixed allowlists and
never used to construct filesystem paths. DVC-dependent routes return a
sanitized 503 ``SERVICE_NOT_READY`` with a machine-readable ``reason``
(``artifact_missing`` or ``integrity_failed``) when the payload is absent or
fails verification. No endpoint fits a model, runs a bootstrap, recomputes a
threshold, deserializes a pickle or downloads anything.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.contracts.common import ErrorEnvelope
from app.contracts.phase5a import (
    AgreementGroupsResponse,
    AgreementMatrixResponse,
    BootstrapMetricsResponse,
    DiscoveryCurveResponse,
    HypergeometricResponse,
    MultithresholdResponse,
    PairedDifferencesResponse,
    Phase5AProtocolResponse,
    ReviewPoliciesResponse,
    UncertaintyResponse,
    AgreementResponse,
)
from app.core.errors import ApiError, ErrorCode
from app.services.phase5a_catalog import (
    PHASE5A_EVIDENCE_SERVICE,
    Phase5AEvidenceService,
    Phase5AIntegrityError,
    Phase5AUnavailableError,
)
from app.services.source_registry import SourceNotFoundError

router = APIRouter(prefix="/research/phase5a", tags=["research"])

_ERROR_RESPONSES = {
    404: {"model": ErrorEnvelope, "description": "Unknown Phase 5A resource."},
    503: {
        "model": ErrorEnvelope,
        "description": "Phase 5A payload unavailable or integrity failure.",
    },
}

Kind = Annotated[
    str,
    Path(
        description="Agreement matrix kind: 'spearman' or 'jaccard'.",
    ),
]

RunId = Annotated[
    str,
    Query(
        description=(
            "Canonical run identifier (IF_001..IF_005, LOF_001..LOF_005)."
        )
    ),
]


def _service() -> Phase5AEvidenceService:
    return PHASE5A_EVIDENCE_SERVICE


def _unavailable(exc: Exception, reason: str) -> ApiError:
    return ApiError(
        status_code=503,
        code=ErrorCode.SERVICE_NOT_READY,
        details={"dependency": "phase5a-evidence", "reason": reason},
    )


@router.get(
    "",
    response_model=Phase5AProtocolResponse,
    responses=_ERROR_RESPONSES,
    summary="Get the verified Phase 5A protocol metadata",
    description=(
        "Returns the frozen Phase 5A protocol metadata (phase 5A, stream A, "
        "models_fitted=0, bootstrap protocol, sample facts, analytical "
        "conventions, selection caveat) and the per-family availability of "
        "the eight DVC-backed evidence families. Served entirely from "
        "Git-tracked, manifest-verified metadata and works on a clean "
        "checkout without DVC payloads. Publicly readable (FR-03 / ADR-007)."
    ),
)
async def get_phase5a_protocol() -> Phase5AProtocolResponse:
    service = _service()
    try:
        payload = service.get_protocol()
    except Phase5AUnavailableError as exc:
        raise _unavailable(exc, "source_not_admitted") from exc
    except Phase5AIntegrityError as exc:
        raise _unavailable(exc, "integrity_failed") from exc
    return Phase5AProtocolResponse.model_validate(payload)


@router.get(
    "/bootstrap",
    response_model=BootstrapMetricsResponse,
    responses=_ERROR_RESPONSES,
    summary="Get the saved Phase 5A bootstrap uncertainty intervals",
    description=(
        "Returns the saved bootstrap intervals for the three evaluated runs "
        "(IF_003, IF_004, LOF_004) and the five saved metrics, with the "
        "frozen protocol (2,000 replicates, 0.95 percentile CI, "
        "class-stratified resampling, seed 42). Intervals are NOT calibrated "
        "fraud probabilities. Requires the DVC-backed payload; when absent "
        "returns 503 SERVICE_NOT_READY with reason artifact_missing. "
        "Publicly readable."
    ),
)
async def get_phase5a_bootstrap() -> BootstrapMetricsResponse:
    service = _service()
    try:
        payload = service.get_bootstrap()
    except Phase5AUnavailableError as exc:
        raise _unavailable(exc, "artifact_missing") from exc
    except Phase5AIntegrityError as exc:
        raise _unavailable(exc, "integrity_failed") from exc
    return BootstrapMetricsResponse.model_validate(payload)


@router.get(
    "/paired-differences",
    response_model=PairedDifferencesResponse,
    responses=_ERROR_RESPONSES,
    summary="Get the saved Phase 5A paired bootstrap differences",
    description=(
        "Returns the saved paired bootstrap differences for the comparison "
        "LOF_004 − IF_003 (direction frozen; never inverted). Labelled "
        "exploratory/post-hoc. Requires the DVC-backed payload; when absent "
        "returns 503 SERVICE_NOT_READY with reason artifact_missing. "
        "Publicly readable."
    ),
)
async def get_phase5a_paired_differences() -> PairedDifferencesResponse:
    service = _service()
    try:
        payload = service.get_paired_differences()
    except Phase5AUnavailableError as exc:
        raise _unavailable(exc, "artifact_missing") from exc
    except Phase5AIntegrityError as exc:
        raise _unavailable(exc, "integrity_failed") from exc
    return PairedDifferencesResponse.model_validate(payload)


@router.get(
    "/agreement/{kind}",
    response_model=AgreementMatrixResponse,
    responses=_ERROR_RESPONSES,
    summary="Get a saved 10×10 agreement matrix",
    description=(
        "Returns the saved pairwise Spearman rank-correlation matrix or the "
        "pairwise Jaccard 1% overlap matrix (kind = 'spearman' or "
        "'jaccard'), with the IF_003/LOF_004 pair highlighted as an existing "
        "post-hoc comparison. Requires the DVC-backed payload; when absent "
        "returns 503 SERVICE_NOT_READY with reason artifact_missing. "
        "Publicly readable."
    ),
)
async def get_phase5a_agreement_matrix(kind: Kind) -> AgreementMatrixResponse:
    service = _service()
    try:
        payload = service.get_agreement_matrix(kind)
    except SourceNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code=ErrorCode.SOURCE_NOT_FOUND,
            details={"kind": kind},
        ) from exc
    except Phase5AUnavailableError as exc:
        raise _unavailable(exc, "artifact_missing") from exc
    except Phase5AIntegrityError as exc:
        raise _unavailable(exc, "integrity_failed") from exc
    return AgreementMatrixResponse.model_validate(payload)


@router.get(
    "/overlap-null",
    response_model=HypergeometricResponse,
    responses=_ERROR_RESPONSES,
    summary="Get the saved hypergeometric overlap result",
    description=(
        "Returns the saved hypergeometric overlap for IF_003 vs LOF_004 at "
        "the canonical 1% threshold, with the explicit null model and the "
        "preserved log-probabilities (never exponentiated to a misleading "
        "zero). The p-value describes the stated overlap null only — not the "
        "probability that flagged records are fraudulent. Requires the "
        "DVC-backed payload; when absent returns 503 SERVICE_NOT_READY with "
        "reason artifact_missing. Publicly readable."
    ),
)
async def get_phase5a_overlap_null() -> HypergeometricResponse:
    service = _service()
    try:
        payload = service.get_hypergeometric()
    except Phase5AUnavailableError as exc:
        raise _unavailable(exc, "artifact_missing") from exc
    except Phase5AIntegrityError as exc:
        raise _unavailable(exc, "integrity_failed") from exc
    return HypergeometricResponse.model_validate(payload)


@router.get(
    "/groups",
    response_model=AgreementGroupsResponse,
    responses=_ERROR_RESPONSES,
    summary="Get the saved four-way agreement groups",
    description=(
        "Returns the saved disjoint exhaustive partition (both / if_only / "
        "lof_only / neither) of the saved 1% flag pair for IF_003 vs "
        "LOF_004, with conservation of the 30,000-row sample and the 47 "
        "labelled positives. Requires the DVC-backed payload; when absent "
        "returns 503 SERVICE_NOT_READY with reason artifact_missing. "
        "Publicly readable."
    ),
)
async def get_phase5a_groups() -> AgreementGroupsResponse:
    service = _service()
    try:
        payload = service.get_groups()
    except Phase5AUnavailableError as exc:
        raise _unavailable(exc, "artifact_missing") from exc
    except Phase5AIntegrityError as exc:
        raise _unavailable(exc, "integrity_failed") from exc
    return AgreementGroupsResponse.model_validate(payload)


@router.get(
    "/policies",
    response_model=ReviewPoliciesResponse,
    responses=_ERROR_RESPONSES,
    summary="Get the four saved review policies",
    description=(
        "Returns the four saved review policies (both-only, IF_003 flags, "
        "LOF_004 flags, union) with their actual (unequal) review costs, "
        "labelled-positives found, precision and recall contribution "
        "(denominator = 47). The four policies are NOT an equal-budget "
        "comparison and are distinct from the future R2 rank-consensus "
        "strategy. Requires the DVC-backed payload; when absent returns 503 "
        "SERVICE_NOT_READY with reason artifact_missing. Publicly readable."
    ),
)
async def get_phase5a_policies() -> ReviewPoliciesResponse:
    # Legacy route deliberately refuses to generate derived policy statistics.
    # The /review-policies route presents the saved disjoint group rows instead.
    raise _unavailable(
        Phase5AUnavailableError("No separately published policy metrics."),
        "source_not_admitted",
    )


@router.get(
    "/thresholds",
    response_model=MultithresholdResponse,
    responses=_ERROR_RESPONSES,
    summary="Get the saved multi-threshold sensitivity",
    description=(
        "Returns the saved cross-method agreement across the approved "
        "thresholds (0.1, 0.2, 0.5, 1.0, 2.0, 5.0%), distinguishing the saved "
        "canonical 1% flags from the derived offline top-k selections. "
        "Requires the DVC-backed payload; when absent returns 503 "
        "SERVICE_NOT_READY with reason artifact_missing. Publicly readable."
    ),
)
async def get_phase5a_thresholds() -> MultithresholdResponse:
    service = _service()
    try:
        payload = service.get_thresholds()
    except Phase5AUnavailableError as exc:
        raise _unavailable(exc, "artifact_missing") from exc
    except Phase5AIntegrityError as exc:
        raise _unavailable(exc, "integrity_failed") from exc
    return MultithresholdResponse.model_validate(payload)


@router.get(
    "/discovery-curve",
    response_model=DiscoveryCurveResponse,
    responses=_ERROR_RESPONSES,
    summary="Get a bounded page of the saved fraud-discovery curve",
    description=(
        "Returns a bounded page of the saved fraud-discovery curve for one "
        "canonical run, sorted by (run_id, budget). limit is clamped to "
        "[1, 200] (default 100); offset >= 0. The full 15 MB curve is never "
        "serialized into one response and is never regenerated. Requires the "
        "DVC-backed payload; when absent returns 503 SERVICE_NOT_READY with "
        "reason artifact_missing. Publicly readable."
    ),
)
async def get_phase5a_discovery_curve(
    run_id: RunId,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> DiscoveryCurveResponse:
    service = _service()
    try:
        payload = service.get_discovery_curve(run_id, limit=limit, offset=offset)
    except SourceNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code=ErrorCode.SOURCE_NOT_FOUND,
            details={"run_id": run_id},
        ) from exc
    except Phase5AUnavailableError as exc:
        raise _unavailable(exc, "artifact_missing") from exc
    except Phase5AIntegrityError as exc:
        raise _unavailable(exc, "integrity_failed") from exc
    return DiscoveryCurveResponse.model_validate(payload)


# PR-10 focused resource paths (approved public read-only evidence).
@router.get(
    "/catalog",
    response_model=Phase5AProtocolResponse,
    responses=_ERROR_RESPONSES,
    summary="Verified Phase 5A source catalog and availability",
)
async def get_phase5a_catalog() -> Phase5AProtocolResponse:
    return await get_phase5a_protocol()


@router.get(
    "/uncertainty",
    response_model=UncertaintyResponse,
    responses=_ERROR_RESPONSES,
    summary="Saved bootstrap and paired uncertainty evidence",
)
async def get_phase5a_uncertainty() -> UncertaintyResponse:
    # Separate underlying loaders: a missing required subartifact yields a
    # clear 503, while other capabilities and their endpoints remain intact.
    bootstrap = await get_phase5a_bootstrap()
    paired = await get_phase5a_paired_differences()
    return UncertaintyResponse(bootstrap=bootstrap, paired_differences=paired)


@router.get(
    "/agreement",
    response_model=AgreementResponse,
    responses=_ERROR_RESPONSES,
    summary="Saved Spearman and Jaccard pairwise agreement",
)
async def get_phase5a_agreement() -> AgreementResponse:
    spearman = await get_phase5a_agreement_matrix("spearman")
    jaccard = await get_phase5a_agreement_matrix("jaccard")
    return AgreementResponse(spearman=spearman, jaccard=jaccard)


@router.get(
    "/review-policies",
    response_model=AgreementGroupsResponse,
    responses=_ERROR_RESPONSES,
    summary="Saved disjoint detector-agreement groups (no runtime derivation)",
)
async def get_phase5a_review_policies() -> AgreementGroupsResponse:
    return await get_phase5a_groups()
