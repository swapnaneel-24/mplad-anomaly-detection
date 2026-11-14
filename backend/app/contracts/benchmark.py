"""Pydantic contracts for the canonical benchmark adapter (PR-09).

These models describe the JSON contract exposed by the benchmark routes
under ``/api/v1/research``. Every served value is a **precomputed, frozen**
experiment artifact: Layer A values come from Git-tracked, manifest-verified
metadata; Layer B values come from DVC-backed payloads verified against
their Git-tracked ``.dvc`` pointers before parsing. The endpoints never fit
a model, never recompute a threshold and never produce a live prediction:
``is_precomputed`` is always ``true`` and ``is_live_prediction`` is always
``false`` wherever those fields appear.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Shared provenance blocks
# ---------------------------------------------------------------------------


class ArtifactProvenance(BaseModel):
    """Identity of one consumed frozen artifact."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(
        description="Repository-relative path to the frozen artifact (never absolute)."
    )
    sha256: str = Field(description="SHA-256 digest of the artifact bytes.")
    digest_algorithm: Literal["sha-256"] = Field(
        description="Digest algorithm used for provenance."
    )
    canonicalization: str = Field(
        description=(
            "Byte canonicalization applied before hashing: "
            "'frozen-checker-compatible' (CRLF→LF, matching "
            "ci/check_frozen_integrity.py) or "
            "'windows-commit-manifest-compatible' (LF→CRLF reconstruction "
            "matching the Windows-produced Phase 4 commit manifest)."
        )
    )


class ParameterSourceProvenance(ArtifactProvenance):
    """Provenance of a run's parameter configuration."""

    note: str = Field(
        description=(
            "Statement of how the parameters were obtained (frozen source; "
            "no framework defaults inferred)."
        )
    )


# ---------------------------------------------------------------------------
# Experiment catalog (Layer A)
# ---------------------------------------------------------------------------


class BenchmarkExperimentSummary(BaseModel):
    """One canonical benchmark run in the list view."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(
        description="Canonical run identifier (IF_001..IF_005, LOF_001..LOF_005)."
    )
    algorithm: Literal["IsolationForest", "LOF"] = Field(
        description="Detector algorithm of the run."
    )
    parameters: dict[str, Any] = Field(
        description=(
            "Exact source-backed parameter configuration of the run, "
            "extracted verbatim from the frozen config module."
        )
    )
    parameter_source: ParameterSourceProvenance = Field(
        description="Provenance of the parameter configuration."
    )
    dataset_id: str = Field(description="Frozen benchmark dataset identity.")
    model_status: Literal["fitted_offline_frozen"] = Field(
        description=(
            "Run status: the detector was fitted offline by the frozen "
            "pipeline; nothing is fitted or refitted at request time."
        )
    )
    metrics_available: bool = Field(
        description=(
            "Whether the verified saved metrics for this run are currently "
            "servable (requires the admitted DVC payload to be present and "
            "checksum-verified)."
        )
    )
    row_lookup_available: bool = Field(
        description=(
            "Whether the canonical row-level lookup is currently servable "
            "(requires the admitted DVC payload to be present and "
            "checksum-verified)."
        )
    )


class BenchmarkCatalogResponse(BaseModel):
    """The verified ten-run benchmark catalog with capability availability."""

    source_id: str = Field(description="Fixed benchmark source identifier.")
    dataset_id: str = Field(description="Frozen benchmark dataset identity.")
    experiments: list[BenchmarkExperimentSummary] = Field(
        description="The ten canonical runs in frozen config order."
    )
    count: int = Field(description="Number of experiments (always 10).")
    capabilities: dict[str, Any] = Field(
        description=(
            "Per-capability availability of the DVC-backed evidence layers "
            "('metrics', 'row_level'): available / reason (artifact_missing "
            "or integrity_failed) / detail. The catalog itself is always "
            "served from Git-verified metadata."
        )
    )
    limitations: list[str] = Field(
        description="Scientific limitations that apply to every run."
    )


class DatasetScope(BaseModel):
    """Frozen dataset and experiment context of the canonical benchmark."""

    model_config = ConfigDict(frozen=True)

    sample: dict[str, Any] = Field(
        description=(
            "Canonical sample facts: sample_size, fraud_count, "
            "fraud_prevalence (30,000 rows / 47 labels on the canonical run)."
        )
    )
    registry_summary: dict[str, Any] = Field(
        description=(
            "Full-population registry context (284,807 observations, 492 "
            "positive labels) — recorded context, never mixed into sample "
            "metrics."
        )
    )
    threshold_rule: str = Field(
        description="Frozen post-hoc flagging rule (bottom 1% of native scores)."
    )
    threshold_percentile: float = Field(
        description="Frozen threshold percentile (1.0)."
    )
    sample_seed: int = Field(
        description="Frozen sampling seed of the 30k draw (42)."
    )
    score_orientation: dict[str, Any] = Field(
        description=(
            "Frozen score-orientation contract: native lower = more "
            "anomalous; anomaly_score = -native_score; ranking metrics use "
            "anomaly_score; threshold metrics use saved flags."
        )
    )
    environment: dict[str, Any] = Field(
        description=(
            "Recorded execution environment of the frozen Phase 4 "
            "evaluation (reported as recorded; never re-executed)."
        )
    )
    model_fitting: dict[str, Any] = Field(
        description=(
            "Frozen statement that Phase 4 fitted zero models (evaluation "
            "only)."
        )
    )


class BenchmarkExperimentDetail(BaseModel):
    """Full descriptor of one canonical benchmark run."""

    run_id: str
    algorithm: Literal["IsolationForest", "LOF"]
    parameters: dict[str, Any]
    fixed_pipeline_settings: dict[str, Any] = Field(
        description=(
            "Fixed detector settings recorded alongside the run grid "
            "(e.g. LOF ball_tree/leaf_size); documented, frozen."
        )
    )
    parameter_source: ParameterSourceProvenance
    dataset_id: str
    model_status: Literal["fitted_offline_frozen"]
    metrics_available: bool
    row_lookup_available: bool
    dataset_scope: DatasetScope
    provenance: dict[str, ArtifactProvenance] = Field(
        description=(
            "Provenance chain: config (parameters), run metadata "
            "(dataset scope) and commit manifest (identity)."
        )
    )
    limitations: list[str]


# ---------------------------------------------------------------------------
# Saved metrics (Layer B)
# ---------------------------------------------------------------------------


class BenchmarkMetricDefinition(BaseModel):
    """Definition and denominator semantics of one saved metric."""

    model_config = ConfigDict(frozen=True)

    metric_name: str = Field(description="Stable metric identifier.")
    definition: str = Field(
        description="How the metric was computed by the frozen pipeline."
    )
    denominator: str = Field(
        description=(
            "The population or count the metric is defined over (sample, "
            "flagged set, or label count)."
        )
    )


class BenchmarkRunMetrics(BaseModel):
    """Saved Phase 4 metrics of one canonical run, exactly as admitted."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    model: str = Field(description="Model name recorded in the saved metrics row.")
    average_precision: float
    roc_auc: float
    precision_at_1pct: float
    recall_at_1pct: float
    f1_at_1pct: float
    tn: int
    fp: int
    fn: int
    tp: int
    sample_size: int
    fraud_count: int
    fraud_prevalence: float
    flagged_count: int
    flagged_proportion: float
    runtime_seconds: float | None = Field(
        description=(
            "Recorded Phase 3 runtime of the run in seconds, when present "
            "in the admitted artifact."
        )
    )
    threshold_rule: str


class BenchmarkMetricsResponse(BaseModel):
    """Verified saved metrics for the canonical ten-run benchmark."""

    source_id: str
    dataset_id: str
    sample: dict[str, Any]
    metrics: list[BenchmarkRunMetrics] = Field(
        description="One row per canonical run, in frozen metadata order."
    )
    metric_definitions: list[BenchmarkMetricDefinition] = Field(
        description=(
            "Definitions and denominator semantics that must be shown "
            "alongside the values."
        )
    )
    provenance: dict[str, Any] = Field(
        description=(
            "Payload identity: repository-relative path, verified md5 and "
            "the verification statement."
        )
    )
    limitations: list[str]
    is_precomputed: Literal[True] = Field(
        default=True,
        description="Always true: values are precomputed and frozen.",
    )
    is_live_prediction: Literal[False] = Field(
        default=False,
        description="Always false: this endpoint never produces a live prediction.",
    )


# ---------------------------------------------------------------------------
# Canonical record lookup (Layer B)
# ---------------------------------------------------------------------------


class RecordLabelBlock(BaseModel):
    """Ground-truth label of a canonical record."""

    model_config = ConfigDict(frozen=True)

    Class: int = Field(description="Ground-truth evaluation label (0/1).")
    provenance: str = Field(
        description=(
            "Provenance of the label: ground-truth ULB evaluation label "
            "joined on row_id; distinct from the detector flag."
        )
    )


class RecordScoreBlock(BaseModel):
    """Saved scores of a canonical record."""

    model_config = ConfigDict(frozen=True)

    native_score: float = Field(
        description="Phase 3 native estimator score (lower = more anomalous)."
    )
    anomaly_score: float = Field(
        description="Saved oriented score -native_score (higher = more anomalous)."
    )
    native_definition: str
    anomaly_definition: str


class RecordFlagBlock(BaseModel):
    """Saved detector flag of a canonical record."""

    model_config = ConfigDict(frozen=True)

    value: int = Field(description="Saved Phase 3 bottom-1% flag (0/1).")
    provenance: str = Field(
        description="Provenance of the flag: saved Phase 3 output; never recomputed."
    )


class BenchmarkRecordResponse(BaseModel):
    """One canonical record, resolved by exact saved row_id."""

    run_id: str
    row_id: int = Field(description="Canonical ULB row identifier (join key).")
    label: RecordLabelBlock
    scores: RecordScoreBlock
    flag: RecordFlagBlock
    dataset_id: str
    sample: dict[str, Any]
    score_orientation: dict[str, Any]
    provenance: dict[str, Any]
    limitations: list[str]
    is_precomputed: Literal[True] = Field(default=True)
    is_live_prediction: Literal[False] = Field(default=False)
