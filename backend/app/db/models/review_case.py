"""``review_cases`` ORM model.

The stable application-facing fields (PR-03 §5, ADR-003 §4.3):

    id            UUID primary key
    dataset_id    approved dataset identifier (opaque slug)
    snapshot_id   exact source/experimental snapshot identifier (opaque)
    record_ref    stable opaque reference to the reviewed record
    status        current workflow status (controlled enum)
    title         concise case description (bounded length)
    summary       optional human-written investigation context (bounded)
    created_at    UTC creation timestamp
    updated_at    UTC last modification timestamp
    version       optimistic-lock counter (monotonically increasing)
    created_by    provenance of case creation (actor reference)

Identity rules (PR-03 §5):

* ``record_ref`` is an opaque reference, never a filesystem path. It is
  resolved by a future server-side source-registry adapter (PR-03 does
  not implement that adapter and does not create a foreign key to a
  nonexistent source table).
* ``dataset_id`` and ``snapshot_id`` are validated opaque slugs. Their
  referential integrity will be enforced once the source registry admits
  real sources; for PR-03 they are stored as validated strings.
* No full raw datasets or feature vectors are stored in this table.

Optimistic concurrency (PR-03 §10, ADR-003 §4.3):

* ``version`` is incremented atomically on every update.
* A stale client (wrong expected version) receives a typed concurrency
  conflict; no silent overwrite, no duplicate event.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Index, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.statuses import ReviewStatus

#: Bounded lengths (PR-03 §9: "Enforce bounded text lengths and validation").
_DATASET_ID_MAX = 64
_SNAPSHOT_ID_MAX = 128
_RECORD_REF_MAX = 256
_TITLE_MAX = 240
_SUMMARY_MAX = 4000
_ACTOR_REF_MAX = 128

#: The CHECK constraint expression that enforces the controlled status
#: vocabulary at the database level (defence in depth: the service layer
#: validates first, the DB constraint catches anything that slips through).
_STATUS_CHECK = "status IN ('not_reviewed','under_review','explained_deviation','needs_source_verification','escalated_for_examination')"


class ReviewCase(Base):
    """A review case for a single record in an approved dataset snapshot."""

    __tablename__ = "review_cases"

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        doc="UUID primary key, server-generated.",
    )

    # --- Record identity (opaque, immutable after creation) --------------
    dataset_id: Mapped[str] = mapped_column(
        String(_DATASET_ID_MAX),
        nullable=False,
        index=True,
        doc="Opaque approved dataset identifier (not a filesystem path).",
    )
    snapshot_id: Mapped[str] = mapped_column(
        String(_SNAPSHOT_ID_MAX),
        nullable=False,
        index=True,
        doc="Opaque exact source/experimental snapshot identifier.",
    )
    record_ref: Mapped[str] = mapped_column(
        String(_RECORD_REF_MAX),
        nullable=False,
        index=True,
        doc="Opaque stable reference to the reviewed record (never a path).",
    )

    # --- Workflow state ---------------------------------------------------
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="Current review status (controlled vocabulary; see CHECK constraint).",
    )
    title: Mapped[str] = mapped_column(
        String(_TITLE_MAX),
        nullable=False,
        doc="Concise case description.",
    )
    summary: Mapped[str | None] = mapped_column(
        String(_SUMMARY_MAX),
        nullable=True,
        doc="Optional human-written investigation context.",
    )

    # --- Timestamps (UTC) -------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("clock_timestamp()"),
        doc="UTC creation timestamp (server-generated).",
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("clock_timestamp()"),
        onupdate=text("clock_timestamp()"),
        doc="UTC last modification timestamp (server-generated).",
    )

    # --- Concurrency ------------------------------------------------------
    version: Mapped[int] = mapped_column(
        nullable=False,
        server_default=text("1"),
        doc="Optimistic-lock counter; incremented atomically on every update.",
    )

    # --- Provenance -------------------------------------------------------
    created_by: Mapped[str] = mapped_column(
        String(_ACTOR_REF_MAX),
        nullable=False,
        index=True,
        doc="Provenance of case creation (actor reference; PR-04 binds authenticated principal).",
    )

    __table_args__ = (
        CheckConstraint(_STATUS_CHECK, name="review_cases_status_enum"),
        # Common query path: list cases for a dataset+snapshot, ordered.
        Index(
            "ix_review_cases_dataset_snapshot",
            "dataset_id",
            "snapshot_id",
            "created_at",
        ),
        # Common query path: list cases by status.
        Index(
            "ix_review_cases_status_created",
            "status",
            "created_at",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"ReviewCase(id={self.id!r}, dataset_id={self.dataset_id!r}, "
            f"status={self.status!r}, version={self.version!r})"
        )

    @property
    def status_enum(self) -> ReviewStatus:
        """The status column coerced to the typed enum."""
        return ReviewStatus(self.status)
