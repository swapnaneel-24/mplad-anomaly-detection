"""Pydantic contracts for the read-only Phase 5A evidence adapter (PR-10).

These models describe the JSON contract exposed by the Phase 5A routes
under ``/api/v1/research/phase5a``. Every served value is a **precomputed,
frozen** Phase 5A artifact: Layer A values come from Git-tracked,
manifest-verified metadata; Layer B values come from DVC-backed payloads
verified against their Git-tracked ``.dvc`` pointers and the Phase 5 commit
manifest before parsing. The endpoints never fit a model, run a bootstrap,
recompute a threshold or produce a live prediction: ``is_precomputed`` is
always ``true`` and ``is_live_prediction`` is always ``false`` wherever
those fields appear.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Shared provenance
# ---------------------------------------------------------------------------


class ArtifactProvenance(BaseModel):
    """Identity of one consumed frozen artifact (Layer A)."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(description="Repository-relative path (never absolute).")
    sha256: str = Field(description="SHA-256 digest of the artifact bytes.")
    digest_algorithm: Literal["sha-256"] = Field(description="Digest algorithm.")
    canonicalization: str = Field(
        description=(
            "Byte canonicalization applied before hashing: "
            "'frozen-checker-compatible' (CRLF→LF) or "
            "'windows-commit-manifest-compatible' (LF→CRLF reconstruction)."
        )
    )


class FamilyProvenance(BaseModel):
    """Identity of one consumed DVC-backed payload (Layer B)."""

    model_config = ConfigDict(frozen=True)

    artifact_path: str = Field(description="Repository-relative payload path.")
    artifact_md5: str = Field(description="Verified DVC pointer MD5 of the payload.")
    artifact_sha256: str = Field(
        description="Commit-manifest SHA-256 of the payload."
    )
    digest_algorithm: Literal["sha-256"] = Field(default="sha-256")
    verification: str = Field(description="Verification statement.")


class CapabilityStatus(BaseModel):
    """Per-family availability of one DVC-backed evidence family."""

    model_config = ConfigDict(frozen=True)

    available: bool
    reason: Literal["artifact_missing", "integrity_failed"] | None = None
    detail: str | None = None


# ---------------------------------------------------------------------------
# Protocol / catalog (Layer A)
# ---------------------------------------------------------------------------


class Phase5AProtocolResponse(BaseModel):
    """Verified Phase 5A protocol metadata and per-family availability."""

    source_id: str
    dataset_id: str
    phase: Literal["5A"]
    stream: Literal["A"]
    layer: str
    run_mode: str
    models_fitted: Literal[0]
    created_utc: str
    environment: dict[str, Any]
    model_fitting: dict[str, Any]
    analytical_conventions: dict[str, Any]
    bootstrap_protocol: dict[str, Any]
    selection_caveat: str
    sample: dict[str, Any]
    multi_threshold_percents: list[float]
    canonical_threshold_pct: float
    evaluated_run_ids: list[str]
    paired_comparison: dict[str, Any]
    overlap_runs: dict[str, Any]
    capabilities: dict[str, CapabilityStatus]
    provenance: dict[str, Any]
    limitations: list[str]


# ---------------------------------------------------------------------------
# Bootstrap uncertainty (Layer B)
# ---------------------------------------------------------------------------


class BootstrapMetricRow(BaseModel):
    """One saved bootstrap interval for one (run, metric)."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    metric: str
    point_estimate: float
    bootstrap_mean: float
    bootstrap_std: float
    ci_lower: float
    ci_upper: float
    n_replicates: int


class BootstrapMetricsResponse(BaseModel):
    source_id: str
    dataset_id: str
    bootstrap_protocol: dict[str, Any]
    selection_caveat: str
    metrics: list[BootstrapMetricRow]
    provenance: FamilyProvenance
    limitations: list[str]
    is_precomputed: Literal[True] = True
    is_live_prediction: Literal[False] = False


# ---------------------------------------------------------------------------
# Paired bootstrap differences (Layer B)
# ---------------------------------------------------------------------------


class PairedDifferenceRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    comparison: str
    run_a: str
    run_b: str
    metric: str
    point_estimate: float
    bootstrap_mean: float
    bootstrap_std: float
    ci_lower: float
    ci_upper: float
    n_replicates: int


class PairedDifferencesResponse(BaseModel):
    source_id: str
    dataset_id: str
    direction: str = Field(description="Frozen subtraction direction (LOF_004 - IF_003).")
    run_a: str
    run_b: str
    selection_caveat: str
    differences: list[PairedDifferenceRow]
    provenance: FamilyProvenance
    limitations: list[str]
    is_precomputed: Literal[True] = True
    is_live_prediction: Literal[False] = False


# ---------------------------------------------------------------------------
# Agreement matrices (Layer B)
# ---------------------------------------------------------------------------


class MatrixRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    values: dict[str, float]


class AgreementMatrixResponse(BaseModel):
    source_id: str
    dataset_id: str
    kind: Literal["spearman", "jaccard"]
    run_labels: list[str]
    matrix: list[MatrixRow]
    bounds: dict[str, float]
    highlighted_pair: dict[str, str]
    selection_caveat: str
    definition: str
    provenance: FamilyProvenance
    limitations: list[str]
    is_precomputed: Literal[True] = True
    is_live_prediction: Literal[False] = False


# ---------------------------------------------------------------------------
# Hypergeometric overlap (Layer B)
# ---------------------------------------------------------------------------


class HypergeometricResponse(BaseModel):
    source_id: str
    dataset_id: str
    run_a: str
    run_b: str
    threshold_pct: float
    n_observations: int
    run_a_flagged: int
    run_b_flagged: int
    observed_intersection: int
    union_size: int
    expected_intersection: float
    enrichment_observed_over_expected: float
    survival_upper_tail: float = Field(
        description="Upper-tail probability under the stated null; preserved as recorded."
    )
    log_survival: float = Field(
        description="Natural-log survival; preserved as recorded (never exponentiated to a misleading zero)."
    )
    log10_survival: float = Field(
        description="Base-10 log survival; preserved as recorded."
    )
    null_model: str
    selection_caveat: str
    provenance: FamilyProvenance
    limitations: list[str]
    is_precomputed: Literal[True] = True
    is_live_prediction: Literal[False] = False


# ---------------------------------------------------------------------------
# Agreement groups + review policies (Layer B)
# ---------------------------------------------------------------------------


class AgreementGroupRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    group: Literal["both", "if_only", "lof_only", "neither"]
    observation_count: int
    fraud_count: int
    non_fraud_count: int
    fraud_proportion: float
    recall_contribution: float


class AgreementGroupsResponse(BaseModel):
    source_id: str
    dataset_id: str
    run_a: str
    run_b: str
    threshold_pct: float
    groups: list[AgreementGroupRow]
    conservation: dict[str, Any]
    selection_caveat: str
    provenance: FamilyProvenance
    limitations: list[str]
    is_precomputed: Literal[True] = True
    is_live_prediction: Literal[False] = False


class ReviewPolicyRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy: Literal["both_only", "if_003_flags", "lof_004_flags", "union"]
    label: str
    review_count: int = Field(description="Actual review workload (records).")
    sample_share: float
    labelled_positives_found: int
    precision: float
    recall_contribution: float = Field(
        description="Recall contribution; denominator = 47 labelled positives."
    )
    selection_basis: str
    unequal_budget_note: str = Field(
        description="Warning that the four policies have unequal review costs."
    )


class ReviewPoliciesResponse(BaseModel):
    source_id: str
    dataset_id: str
    run_a: str
    run_b: str
    threshold_pct: float
    labelled_positive_denominator: int
    sample_size: int
    policies: list[ReviewPolicyRow]
    selection_caveat: str
    provenance: FamilyProvenance
    limitations: list[str]
    is_precomputed: Literal[True] = True
    is_live_prediction: Literal[False] = False


# ---------------------------------------------------------------------------
# Multi-threshold sensitivity (Layer B)
# ---------------------------------------------------------------------------


class ThresholdRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    threshold_pct: float
    k_nominal: int
    selection_source: str = Field(
        description="'saved_canonical' (the frozen 1% flags) or 'derived_topk'."
    )
    is_canonical: bool
    n_methods: int
    observation_count: int


class MultithresholdResponse(BaseModel):
    source_id: str
    dataset_id: str
    canonical_threshold_pct: float
    approved_thresholds: list[float]
    thresholds: list[ThresholdRow]
    selection_caveat: str
    provenance: FamilyProvenance
    limitations: list[str]
    is_precomputed: Literal[True] = True
    is_live_prediction: Literal[False] = False


# ---------------------------------------------------------------------------
# Discovery curve (Layer B, bounded)
# ---------------------------------------------------------------------------


class DiscoveryCurveRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    budget: int | str = Field(description="Saved budget (int when parseable).")
    fraud_found: int
    precision: float
    recall: float


class DiscoveryCurveResponse(BaseModel):
    source_id: str
    dataset_id: str
    run_id: str
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
    total: int = Field(ge=0)
    has_more: bool
    rows: list[DiscoveryCurveRow]
    selection_caveat: str
    provenance: FamilyProvenance
    limitations: list[str]
    is_precomputed: Literal[True] = True
    is_live_prediction: Literal[False] = False


# PR-10 focused public API: composite data are pre-existing saved results.
class UncertaintyResponse(BaseModel):
    bootstrap: BootstrapMetricsResponse
    paired_differences: PairedDifferencesResponse


class AgreementResponse(BaseModel):
    spearman: AgreementMatrixResponse
    jaccard: AgreementMatrixResponse
