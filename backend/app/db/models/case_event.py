"""``case_events`` ORM model — append-only audit trail.

Every mutation of a review case (creation, note addition, status change,
decision) commits a corresponding event row in the same database
transaction (PR-03 §7, ADR-003 §4.3 write invariant).

Append-only enforcement is **database-level**, not merely an ORM
convention (PR-03 §7): a PostgreSQL trigger rejects ``UPDATE`` and
``DELETE`` on this table. The trigger is installed by the Alembic
migration. Application-level privileges should additionally restrict the
role used by the application so that even a bug in the ORM cannot
silently mutate history.

The trigger does not make the history tamper-proof against a database
superuser (PR-03 §7); it is an application-level append-only audit trail.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_EVENT_TYPE_CHECK = (
    "event_type IN ('created','note_added','status_changed','decision_recorded','reopened')"
)

#: Bounded lengths for text columns (PR-03 §9: bounded text; Unicode-safe).
_ACTOR_REF_MAX = 128
_REASON_MAX = 1000


class CaseEvent(Base):
    """An immutable event in a review case's audit trail."""

    __tablename__ = "case_events"

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        doc="UUID event identifier, server-generated.",
    )

    case_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("review_cases.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key to review_cases.id.",
    )

    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="Event type (controlled vocabulary; see CHECK constraint).",
    )

    event_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("clock_timestamp()"),
        index=True,
        doc="UTC event timestamp (server-generated, not client clock).",
    )

    actor_ref: Mapped[str] = mapped_column(
        String(_ACTOR_REF_MAX),
        nullable=False,
        index=True,
        doc="Identity/provenance reference for the actor that produced the event.",
    )

    previous_status: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        doc="Previous review status when applicable (status-changed/reopened events).",
    )
    new_status: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        doc="New review status when applicable (status-changed/reopened events).",
    )

    reason: Mapped[str | None] = mapped_column(
        String(_REASON_MAX),
        nullable=True,
        doc="Human-readable explanation where applicable.",
    )

    event_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Validated JSON payload for event-specific details (bounded; no binary).",
    )

    #: The case version produced by this event. This is the value of
    #: ``review_cases.version`` after the transaction that created the
    #: event commits. Together with ``event_seq`` it gives a deterministic
    #: chronological and version ordering of the history (PR-03 §7.7,
    #: hardened in PR-03 §2).
    case_version: Mapped[int] = mapped_column(
        nullable=False,
        doc="Case version produced by this event (monotonic per case).",
    )

    #: Database-generated monotonic sequence for deterministic intra-version
    #: ordering (PR-03 hardening §2). When a single operation writes
    #: multiple events at the same ``case_version`` (e.g. ``record_decision``
    #: writes a ``status_changed`` event then a ``decision_recorded``
    #: event), ``event_seq`` guarantees the insertion order is preserved.
    #: The column is a PostgreSQL ``BIGINT GENERATED ALWAYS AS IDENTITY``,
    #: so the value is assigned by the database at insert time and cannot
    #: be overridden by the application.
    event_seq: Mapped[int] = mapped_column(
        BigInteger,
        server_default=text("nextval('case_events_event_seq_seq')"),
        nullable=False,
        doc="Database-generated monotonic sequence for deterministic ordering.",
    )

    __table_args__ = (
        CheckConstraint(_EVENT_TYPE_CHECK, name="case_events_event_type_enum"),
        # Deterministic history retrieval: by case, ordered by version then
        # sequence. Multiple events may share the same case_version when
        # produced by a single transaction; event_seq guarantees the
        # insertion order is preserved (PR-03 hardening §2).
        Index(
            "ix_case_events_case_version",
            "case_id",
            "case_version",
        ),
        Index(
            "ix_case_events_case_version_seq",
            "case_id",
            "case_version",
            "event_seq",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"CaseEvent(id={self.id!r}, case_id={self.case_id!r}, "
            f"event_type={self.event_type!r}, case_version={self.case_version!r})"
        )
