"""Shared typed contracts for every ``/api/v1`` response.

Keeping the models in one module makes the OpenAPI schema (and the
generated TypeScript types) a single, reviewable contract surface.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

#: Response header used for request tracing.
REQUEST_ID_HEADER = "X-Request-ID"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthLiveResponse(BaseModel):
    """Liveness: the API process can answer requests."""

    status: Literal["alive"]
    service: str = Field(description="Application name.")
    version: str = Field(description="Backend application version.")


class ReadinessCheck(BaseModel):
    """One configured dependency check (name and status only; no details)."""

    name: str
    status: Literal["ready", "unavailable"]


class ReadinessResponse(BaseModel):
    """Readiness: all configured required dependencies are ready."""

    status: Literal["ready"]
    checks: list[ReadinessCheck] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

FeatureState = Literal["implemented", "planned"]
SubsystemState = Literal["available", "empty", "not_integrated"]


class MetaResponse(BaseModel):
    """Non-sensitive application metadata (``GET /api/v1/meta``)."""

    application: str = Field(description="Application name.")
    api_version: Literal["v1"] = Field(description="Versioned API namespace.")
    app_version: str = Field(description="Backend application version.")
    git_commit_sha: str | None = Field(
        default=None,
        description="Git commit SHA if supplied by the deployment environment; never fabricated.",
    )
    environment: Literal["development", "test", "production"]
    features: dict[str, FeatureState] = Field(
        description="Implemented versus planned application features."
    )
    subsystems: dict[str, SubsystemState] = Field(
        description="Availability of major application subsystems."
    )


# ---------------------------------------------------------------------------
# Source registry (architectural seam; static empty registry in PR-02)
# ---------------------------------------------------------------------------

DatasetKind = Literal["ulb_benchmark", "pmgsy_infrastructure", "mplads_administration"]
IntegrityStatus = Literal["verified", "unverified_legacy", "integrity_failed", "unavailable"]
AnalysisStatus = Literal["verified_benchmark", "exploratory", "restricted", "blocked", "unavailable"]


class SourceSummary(BaseModel):
    """Public description of an approved, registered data source."""

    source_id: str = Field(description="Opaque registered source identifier (not a filesystem path).")
    dataset_kind: DatasetKind
    integrity_status: IntegrityStatus
    analysis_status: AnalysisStatus


class SourceListResponse(BaseModel):
    """All registered sources (currently none are configured)."""

    sources: list[SourceSummary]
    count: int


# ---------------------------------------------------------------------------
# Synthetic demonstration records (PR-05B §5)
# ---------------------------------------------------------------------------


class SyntheticRecordSummary(BaseModel):
    """One synthetic demonstration record (list view).

    Explicitly fictional — NOT a research finding. The ``synthetic`` flag
    is always true; the ``label`` field carries the prominent
    ``SYNTHETIC DEMONSTRATION RECORD`` warning.
    """

    record_ref: str = Field(description="Stable opaque reference to the synthetic record.")
    title: str = Field(description="Synthetic record title (always carries the SYNTHETIC warning).")
    dataset_id: str = Field(description="Synthetic dataset identifier.")
    snapshot_id: str = Field(description="Synthetic snapshot identifier.")
    synthetic: bool = Field(default=True, description="Always true for demonstration records.")


class SyntheticRecordDetail(BaseModel):
    """Full detail of one synthetic demonstration record.

    Explicitly fictional. No ML anomaly score is included. The evidence
    fields are illustrative descriptions, not measured results.
    """

    record_ref: str
    title: str
    description: str = Field(description="Fictional description; NOT a research finding.")
    evidence_summary: str = Field(description="Illustrative evidence description; not a measured result.")
    administrative_context: str
    limitations: str = Field(description="Explicit scientific limitations of the synthetic data.")
    dataset_id: str
    snapshot_id: str
    synthetic: bool = Field(default=True)


class SyntheticRecordListResponse(BaseModel):
    """List of synthetic demonstration records."""

    items: list[SyntheticRecordSummary]
    total: int
    dataset_id: str = Field(description="The synthetic dataset identifier.")
    snapshot_id: str = Field(description="The synthetic snapshot identifier.")


# ---------------------------------------------------------------------------
# Structured error envelope
# ---------------------------------------------------------------------------


class ErrorBody(BaseModel):
    """Machine-readable error payload (sanitized; no tracebacks)."""

    code: str = Field(description="Stable machine-readable error code.")
    message: str = Field(description="Human-readable, sanitized error message.")
    request_id: str = Field(description="Request ID for cross-referencing server logs.")
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    """Envelope shared by every error response."""

    error: ErrorBody
