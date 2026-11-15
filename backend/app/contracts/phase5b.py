"""Pydantic contracts for the Phase 5B figure gallery (PR-11).

These models describe the JSON contract exposed by the Phase 5B routes
under ``/api/v1/research/phase5b``. Every served value is either a
manifest-verified Phase 5B artifact (catalog CSV, plot metadata JSON,
eight canonical PNGs) or an explicitly labelled PR-11 application
mapping (objective traceability links).

Per-figure integrity, availability, and publication state are kept
separate: a figure can be ``integrity=verified`` and ``available=true``
while ``publication.enabled=false`` (the default, pending licensing
review). The three states must not be conflated.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Per-figure state
# ---------------------------------------------------------------------------


class IntegrityStatus(BaseModel):
    """Raw-byte integrity of one figure artifact against its declared identities."""

    model_config = ConfigDict(frozen=True)

    state: Literal[
        "verified", "artifact_missing", "integrity_failed", "source_not_admitted"
    ]
    size_bytes: int | None = Field(
        default=None,
        description="Verified raw size in bytes (only set when state=verified).",
    )
    sha256: str | None = Field(
        default=None,
        description="Verified manifest SHA-256 (only set when state=verified).",
    )


class Availability(BaseModel):
    """Whether the figure payload can be served right now."""

    model_config = ConfigDict(frozen=True)

    available: bool
    reason: Literal["artifact_missing", "integrity_failed", "source_not_admitted"] | None = None
    detail: str | None = None


class Publication(BaseModel):
    """Whether the figure binary is authorised for public delivery."""

    model_config = ConfigDict(frozen=True)

    enabled: bool
    reason: Literal["publication_not_approved", "licensing_unresolved"] | None = None
    detail: str | None = None


class FigureEntry(BaseModel):
    """One canonical Phase 5B figure, with all state dimensions separated."""

    model_config = ConfigDict(frozen=True)

    figure_no: int = Field(ge=1, le=8)
    filename: str
    title: str | None = Field(
        default=None,
        description="Source-backed title from the catalog CSV; null if the CSV is unavailable.",
    )
    purpose: str | None = None
    input_artifacts: str | None = None
    conventions: str | None = Field(
        default=None,
        description="Full conventions text; used as the visible caption, not raw alt.",
    )
    alt_text: str = Field(
        description="Concise source-backed accessibility description (derived from title)."
    )
    integrity: IntegrityStatus
    availability: Availability
    publication: Publication


class FigureCatalogResponse(BaseModel):
    """The verified Phase 5B figure catalog."""

    source_id: str
    dataset_id: str
    phase: Literal["5B"]
    stream: Literal["A"]
    models_fitted: Literal[0]
    manifest_status: Literal["verified", "integrity_failed", "source_not_admitted"]
    catalog_metadata_available: bool = Field(
        description="True when the DVC-backed catalog CSV is present and verified; false on a clean checkout."
    )
    publication_gate: Publication
    figures: list[FigureEntry]
    limitations: list[str]


# ---------------------------------------------------------------------------
# Objective traceability (source-native (a)/(b)/(c) + RQ1..RQ6)
# ---------------------------------------------------------------------------


class EvidenceLink(BaseModel):
    """One link from an objective/RQ to existing capability evidence."""

    model_config = ConfigDict(frozen=True)

    type: str
    source_id: str | None = None
    reference: str
    verification_status: Literal["verified", "unverified", "unavailable"] = "verified"


class ObjectiveEntry(BaseModel):
    """One source-native objective from docs/provenance_log.md §1."""

    model_config = ConfigDict(frozen=True)

    objective_id: Literal["(a)", "(b)", "(c)"]
    statement: str
    research_questions: list[str] = Field(default_factory=list)
    methodology_sources: list[str] = Field(default_factory=list)
    evidence: list[EvidenceLink] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ResearchQuestionEntry(BaseModel):
    """One research question from docs/Phase-0.md §0.4."""

    model_config = ConfigDict(frozen=True)

    rq_id: Literal["RQ1", "RQ2", "RQ3", "RQ4", "RQ5", "RQ6"]
    statement: str
    source_reference: str
    linked_objective: Literal["(a)", "(b)", "(c)"]


class HistoricalCompanion(BaseModel):
    """The 284,807-row LOF Novelty Mode companion, kept distinct from the canonical sample."""

    model_config = ConfigDict(frozen=True)

    population: int
    canonical_comparable: Literal[False] = False
    limitations: list[str] = Field(default_factory=list)


class Reproducibility(BaseModel):
    """Source and artifact references for reproducibility."""

    model_config = ConfigDict(frozen=True)

    source_references: list[dict] = Field(default_factory=list)
    artifact_references: list[dict] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class TraceabilityResponse(BaseModel):
    """Objectives, research questions, historical companion, and reproducibility links."""

    source_identity: dict
    objectives: list[ObjectiveEntry]
    research_questions: list[ResearchQuestionEntry]
    historical_companion: HistoricalCompanion
    reproducibility: Reproducibility
    limitations: list[str]