"""Pydantic contracts for the read-only research-results adapter (PR-08).

These models describe the JSON contract exposed by ``/api/v1/research/*``.
Every value served through these contracts is a **precomputed, frozen**
constant sourced from ``src/mplad/stream_a/phase6.py`` (SHA-256 verified by
``ci/frozen_research_manifest.json``). The endpoints never fit a model,
never recompute a threshold and never produce a live prediction:
``is_precomputed`` is always ``true`` and ``is_live_prediction`` is always
``false`` on every response.

The contracts intentionally carry provenance (artifact path, SHA-256 digest,
digest algorithm and canonicalization) on both the source detail and the
results responses so a consumer can audit exactly which frozen bytes a
served number came from.
"""

from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Source summaries
# ---------------------------------------------------------------------------


class ResearchSourceSummary(BaseModel):
    """Public summary of one approved read-only research source.

    Carries no provenance or experimental detail: it is the list-view
    descriptor. Use the detail endpoint for artifact provenance and the
    frozen experimental context.
    """

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(
        description="Opaque research-source identifier (never a filesystem path)."
    )
    dataset_id: str = Field(
        description="Frozen dataset the reported results pertain to."
    )
    research_family: str = Field(
        description="Research stream or family the source belongs to."
    )
    model_methods: list[str] = Field(
        description="Detector methods whose aggregate results are reported."
    )
    result_type: str = Field(
        description="Kind of result exposed by this source."
    )
    result_granularity: str = Field(
        description="Aggregation level of the reported results."
    )
    availability: Literal["available", "unavailable", "registered"] = Field(
        description="Whether the source is currently servable. "
        "'registered' means the source is approved but not yet verified at runtime; "
        "'available' means verified and servable; 'unavailable' means the artifact "
        "is missing or failed integrity verification."
    )


class ResearchSourceListResponse(BaseModel):
    """List of approved read-only research sources."""

    items: list[ResearchSourceSummary] = Field(
        description="Approved research sources in deterministic order."
    )
    count: int = Field(description="Number of items in ``items``.")


# ---------------------------------------------------------------------------
# Source detail
# ---------------------------------------------------------------------------


class ResearchSourceDetail(ResearchSourceSummary):
    """Full metadata for one read-only research source, with provenance.

    Extends :class:`ResearchSourceSummary` with the frozen-artifact
    provenance and the experimental context the results were produced
    under (frozen, never recomputed).
    """

    artifact_path: str = Field(
        description="Repository-relative path to the frozen artifact (never absolute)."
    )
    artifact_sha256: str = Field(
        description="SHA-256 digest of the frozen artifact bytes."
    )
    digest_algorithm: Literal["sha-256"] = Field(
        description="Digest algorithm used for provenance."
    )
    canonicalization: Literal["raw-bytes", "frozen-checker-compatible"] = Field(
        description="How the artifact bytes were canonicalized before hashing. "
        "'frozen-checker-compatible' matches ci/check_frozen_integrity.py "
        "(CRLF→LF for text files, raw for binary)."
    )
    experimental_context: dict[str, Any] = Field(
        description=(
            "Frozen experimental parameters the results were produced under "
            "(sample size, label count, threshold rule, run ids, detector grids)."
        )
    )
    limitations: list[str] = Field(
        description="Scientific limitations that apply to every result from this source."
    )
    supporting_artifacts: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Supporting frozen artifacts consumed by the adapter (path, SHA-256, "
            "role). Each artifact's digest is verified against the trusted frozen "
            "manifest before its bytes are parsed."
        ),
    )


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


#: Primitive type tag recorded alongside every result value.
ResultValueType = Literal["int", "float", "str"]


class ResearchResultItem(BaseModel):
    """One precomputed aggregate reference value with its description.

    ``value_type`` records the primitive type of ``value`` so a consumer
    can parse the value without guessing; it is one of ``"int"``,
    ``"float"`` or ``"str"``.
    """

    model_config = ConfigDict(frozen=True)

    metric_name: str = Field(description="Stable metric identifier.")
    value: Union[int, float, str] = Field(
        description="The precomputed value (an int, a float or a str)."
    )
    value_type: ResultValueType = Field(
        description="Primitive type of ``value``: int, float or str."
    )
    description: str = Field(description="Human-readable description of the metric.")


class ResearchProvenance(BaseModel):
    """Provenance of a precomputed research result (artifact + digest)."""

    model_config = ConfigDict(frozen=True)

    artifact_path: str = Field(description="Repository-relative path to the frozen artifact.")
    artifact_sha256: str = Field(description="SHA-256 digest of the frozen artifact bytes.")
    digest_algorithm: Literal["sha-256"] = Field(description="Digest algorithm.")
    canonicalization: Literal["raw-bytes", "frozen-checker-compatible"] = Field(
        description="Byte canonicalization applied before hashing. "
        "'frozen-checker-compatible' matches ci/check_frozen_integrity.py."
    )


class ResearchResultsResponse(BaseModel):
    """Precomputed research results with full provenance.

    Every field except ``results`` is metadata / provenance. The
    ``results`` list carries the 18 frozen aggregate reference values from
    the ULB credit-card fraud benchmark experiment (Stream A, Phase 6).
    """

    source_id: str
    dataset_id: str
    model_methods: list[str]
    results: list[ResearchResultItem] = Field(
        description="The precomputed aggregate reference values."
    )
    interpretation_principles: list[str] = Field(
        description="Frozen interpretation principles every consumer must respect."
    )
    exploratory_caveat: str = Field(
        description="Post-hoc selection caveat reused verbatim from Phase 5A."
    )
    provenance: ResearchProvenance
    limitations: list[str]
    is_precomputed: Literal[True] = Field(
        default=True,
        description="Always true: results are precomputed and frozen, never recomputed on request.",
    )
    is_live_prediction: Literal[False] = Field(
        default=False,
        description="Always false: this endpoint never produces a live prediction.",
    )
