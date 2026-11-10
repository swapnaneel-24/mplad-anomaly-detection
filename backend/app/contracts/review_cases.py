"""Application-facing Pydantic contracts for review-case operations.

These models are the typed boundary between the service layer and its
callers (tests today; authenticated API handlers in PR-04). They enforce
bounded text lengths, opaque-identifier validation and a controlled
status vocabulary, so arbitrary unvalidated dictionaries cannot pass
through the service boundary (PR-03 §9).

No model here carries a database credential, an absolute path, or a raw
binary payload.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.events import EventType
from app.domain.statuses import ReviewStatus

# Re-export the opaque-slug validator shape so contracts stay consistent
# with the source-registry seam (PR-02).
_DATASET_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{0,63}$"
_SNAPSHOT_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{0,127}$"
_RECORD_REF_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$"
_ACTOR_REF_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"


class CreateCaseRequest(BaseModel):
    """Input contract for creating a review case."""

    model_config = ConfigDict(frozen=True)

    dataset_id: str = Field(
        description="Opaque approved dataset identifier (lowercase kebab slug, ≤64 chars)."
    )
    snapshot_id: str = Field(
        description="Opaque exact snapshot identifier (lowercase kebab slug, ≤128 chars)."
    )
    record_ref: str = Field(
        description="Opaque stable reference to the reviewed record (≤256 chars; never a path)."
    )
    title: str = Field(
        min_length=1,
        max_length=240,
        description="Concise case description.",
    )
    summary: str | None = Field(
        default=None,
        max_length=4000,
        description="Optional human-written investigation context.",
    )
    created_by: str = Field(
        description="Actor reference for the case creator (≤128 chars). Internal trusted context only.",
    )

    @field_validator("dataset_id")
    @classmethod
    def _validate_dataset_id(cls, v: str) -> str:
        import re

        if not re.fullmatch(_DATASET_ID_PATTERN, v):
            raise ValueError("dataset_id must be an opaque lowercase kebab slug (≤64 chars).")
        return v

    @field_validator("snapshot_id")
    @classmethod
    def _validate_snapshot_id(cls, v: str) -> str:
        import re

        if not re.fullmatch(_SNAPSHOT_ID_PATTERN, v):
            raise ValueError("snapshot_id must be an opaque lowercase kebab slug (≤128 chars).")
        return v

    @field_validator("record_ref")
    @classmethod
    def _validate_record_ref(cls, v: str) -> str:
        import re

        if not re.fullmatch(_RECORD_REF_PATTERN, v):
            raise ValueError(
                "record_ref must be an opaque reference (letters, digits, . _ : -; ≤256 chars)."
            )
        # Reject anything that looks path-like.
        lowered = v.lower()
        for bad in ("/", "\\", "..", "://"):
            if bad in lowered:
                raise ValueError("record_ref must not contain path-like substrings.")
        return v

    @field_validator("created_by")
    @classmethod
    def _validate_created_by(cls, v: str) -> str:
        import re

        if not re.fullmatch(_ACTOR_REF_PATTERN, v):
            raise ValueError("created_by must be an opaque actor reference (≤128 chars).")
        return v


class CaseSummary(BaseModel):
    """Summary of a review case (list view)."""

    model_config = ConfigDict(frozen=True)

    id: str
    dataset_id: str
    snapshot_id: str
    record_ref: str
    status: ReviewStatus
    title: str
    summary: str | None
    created_at: datetime
    updated_at: datetime
    version: int
    created_by: str


class CaseDetail(CaseSummary):
    """Full detail of a review case (single-case view)."""


class CaseListResponse(BaseModel):
    """Paginated list of review cases with a deterministic total order."""

    model_config = ConfigDict(frozen=True)

    items: list[CaseSummary]
    total: int = Field(description="Total number of matching cases (before pagination).")
    limit: int
    offset: int


class AddNoteRequest(BaseModel):
    """Input contract for adding a reviewer note to a case."""

    model_config = ConfigDict(frozen=True)

    note_text: str = Field(
        min_length=1,
        max_length=4000,
        description="The note body (Unicode-safe; bounded length).",
    )
    actor_ref: str = Field(description="Actor reference for the note author (≤128 chars).")
    expected_version: int = Field(
        ge=1,
        description="The case version the caller read; used for optimistic concurrency.",
    )

    @field_validator("actor_ref")
    @classmethod
    def _validate_actor_ref(cls, v: str) -> str:
        import re

        if not re.fullmatch(_ACTOR_REF_PATTERN, v):
            raise ValueError("actor_ref must be an opaque actor reference (≤128 chars).")
        return v


class TransitionStatusRequest(BaseModel):
    """Input contract for a status transition."""

    model_config = ConfigDict(frozen=True)

    to_status: ReviewStatus = Field(description="Target status (must be a legal transition).")
    reason: str = Field(
        min_length=1,
        max_length=1000,
        description="Human-readable reason for the transition (required).",
    )
    actor_ref: str = Field(description="Actor reference for the transition author (≤128 chars).")
    expected_version: int = Field(
        ge=1,
        description="The case version the caller read; used for optimistic concurrency.",
    )

    @field_validator("actor_ref")
    @classmethod
    def _validate_actor_ref(cls, v: str) -> str:
        import re

        if not re.fullmatch(_ACTOR_REF_PATTERN, v):
            raise ValueError("actor_ref must be an opaque actor reference (≤128 chars).")
        return v


class RecordDecisionRequest(BaseModel):
    """Input contract for recording a structured decision.

    A decision is a status transition with an explicit outcome and a
    review rationale. It is persisted as a ``decision_recorded`` event
    (and, when the outcome changes the status, a ``status_changed``
    event in the same transaction).
    """

    model_config = ConfigDict(frozen=True)

    outcome: ReviewStatus = Field(
        description="Decision outcome status (must be a legal transition from the current status)."
    )
    rationale: str = Field(
        min_length=1,
        max_length=4000,
        description="Structured review rationale for the decision.",
    )
    actor_ref: str = Field(description="Actor reference for the decision author (≤128 chars).")
    expected_version: int = Field(
        ge=1,
        description="The case version the caller read; used for optimistic concurrency.",
    )

    @field_validator("actor_ref")
    @classmethod
    def _validate_actor_ref(cls, v: str) -> str:
        import re

        if not re.fullmatch(_ACTOR_REF_PATTERN, v):
            raise ValueError("actor_ref must be an opaque actor reference (≤128 chars).")
        return v


class CaseEventRecord(BaseModel):
    """One event in a case's append-only history."""

    model_config = ConfigDict(frozen=True)

    id: str
    case_id: str
    event_type: EventType
    event_at: datetime
    actor_ref: str
    previous_status: ReviewStatus | None
    new_status: ReviewStatus | None
    reason: str | None
    event_payload: dict[str, Any] | None
    case_version: int
    event_seq: int = Field(
        description="Database-generated monotonic sequence for deterministic ordering."
    )


class CaseHistoryResponse(BaseModel):
    """The append-only event history for a case, deterministically ordered."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    items: list[CaseEventRecord]
    total: int
