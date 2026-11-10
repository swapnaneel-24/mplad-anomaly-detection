"""Typed repository for review cases and their append-only event history.

The repository translates between the typed domain contracts and the
SQLAlchemy ORM. It never commits or rolls back its own transactions: the
service layer owns the transaction boundary so that a case mutation and
its event commit atomically (PR-03 §7, ADR-003 §4.3).

Optimistic concurrency (PR-03 §10):

* ``update_case_status`` and ``add_case_note`` issue a
  ``UPDATE ... WHERE id = :id AND version = :expected`` statement.
* If the row count is zero, the expected version no longer matches the
  stored version: :class:`ConcurrencyConflictError` is raised and the
  service layer rolls the transaction back. No duplicate event is
  written, no partial update survives.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.models import CaseEvent, ReviewCase
from app.domain.events import EventType
from app.domain.statuses import ReviewStatus


class CaseNotFoundError(LookupError):
    """Raised when a requested case id does not exist."""

    def __init__(self, case_id: str) -> None:
        self.case_id = case_id
        super().__init__(f"No review case found with id {case_id!r}.")


class ConcurrencyConflictError(RuntimeError):
    """Raised when an optimistic-concurrency check fails.

    The caller read a stale ``version``; another transaction has since
    updated the case. The caller must re-read the case and retry.
    """

    def __init__(self, case_id: str, expected_version: int) -> None:
        self.case_id = case_id
        self.expected_version = expected_version
        super().__init__(
            f"Concurrency conflict on case {case_id!r}: expected version {expected_version} "
            "is no longer current."
        )


class ReviewCaseRepository:
    """Typed database operations for review cases and events."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------ create
    def insert_case(
        self,
        *,
        case_id: str,
        dataset_id: str,
        snapshot_id: str,
        record_ref: str,
        status: ReviewStatus,
        title: str,
        summary: str | None,
        created_by: str,
    ) -> ReviewCase:
        """Insert a new review case row. Does not commit."""
        case = ReviewCase(
            id=case_id,
            dataset_id=dataset_id,
            snapshot_id=snapshot_id,
            record_ref=record_ref,
            status=status.value,
            title=title,
            summary=summary,
            created_by=created_by,
        )
        self._session.add(case)
        # Flush so server defaults (created_at, version) populate without
        # committing — the service layer owns the commit.
        self._session.flush()
        self._session.refresh(case)
        return case

    def insert_event(
        self,
        *,
        event_id: str,
        case_id: str,
        event_type: EventType,
        actor_ref: str,
        previous_status: ReviewStatus | None,
        new_status: ReviewStatus | None,
        reason: str | None,
        event_payload: dict[str, Any] | None,
        case_version: int,
    ) -> CaseEvent:
        """Insert a new append-only event row. Does not commit."""
        event = CaseEvent(
            id=event_id,
            case_id=case_id,
            event_type=event_type.value,
            actor_ref=actor_ref,
            previous_status=previous_status.value if previous_status else None,
            new_status=new_status.value if new_status else None,
            reason=reason,
            event_payload=event_payload,
            case_version=case_version,
        )
        self._session.add(event)
        self._session.flush()
        self._session.refresh(event)
        return event

    # ------------------------------------------------------------------ read
    def get_case(self, case_id: str) -> ReviewCase:
        """Return the case with ``case_id`` or raise :class:`CaseNotFoundError`."""
        case = self._session.get(ReviewCase, case_id)
        if case is None:
            raise CaseNotFoundError(case_id)
        return case

    def list_cases(
        self,
        *,
        dataset_id: str | None = None,
        snapshot_id: str | None = None,
        status: ReviewStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[ReviewCase], int]:
        """Return a paginated, deterministically ordered list of cases.

        Ordering is by ``created_at`` ascending then ``id`` ascending so
        the total order is stable across pages (PR-03 §9, ADR-003 §4.4).
        """
        stmt = select(ReviewCase)
        if dataset_id is not None:
            stmt = stmt.where(ReviewCase.dataset_id == dataset_id)
        if snapshot_id is not None:
            stmt = stmt.where(ReviewCase.snapshot_id == snapshot_id)
        if status is not None:
            stmt = stmt.where(ReviewCase.status == status.value)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self._session.execute(count_stmt).scalar_one())

        stmt = stmt.order_by(ReviewCase.created_at.asc(), ReviewCase.id.asc())
        stmt = stmt.limit(limit).offset(offset)
        rows = self._session.execute(stmt).scalars().all()
        return rows, total

    def list_events(self, case_id: str) -> Sequence[CaseEvent]:
        """Return the append-only event history for ``case_id``.

        Ordering is by ``case_version`` ascending then ``event_seq``
        ascending — the database-generated monotonic sequence that
        guarantees deterministic intra-version ordering when a single
        operation writes multiple events at the same version (PR-03
        hardening §2). The ``id`` tertiary key is a belt-and-suspenders
        tie-breaker for the theoretical case where two sequences collide
        (which cannot happen with IDENTITY, but the total order is
        preserved defensively).
        """
        stmt = (
            select(CaseEvent)
            .where(CaseEvent.case_id == case_id)
            .order_by(
                CaseEvent.case_version.asc(),
                CaseEvent.event_seq.asc(),
                CaseEvent.id.asc(),
            )
        )
        return list(self._session.execute(stmt).scalars().all())

    # ------------------------------------------------------------------ update
    def update_case_status(
        self,
        *,
        case_id: str,
        expected_version: int,
        new_status: ReviewStatus,
        new_summary: str | None = None,
    ) -> ReviewCase:
        """Atomically update the status and bump the version.

        Issues ``UPDATE ... WHERE id = :id AND version = :expected``. If
        the row count is zero, the expected version is stale:
        :class:`ConcurrencyConflictError` is raised and the caller must
        roll back. On success the row is re-read and returned.
        """
        values: dict[str, Any] = {
            "status": new_status.value,
            "version": expected_version + 1,
            "updated_at": datetime.now(timezone.utc),
        }
        if new_summary is not None:
            values["summary"] = new_summary
        stmt = (
            update(ReviewCase)
            .where(
                ReviewCase.id == case_id,
                ReviewCase.version == expected_version,
            )
            .values(**values)
        )
        result = self._session.execute(stmt)
        if result.rowcount == 0:
            raise ConcurrencyConflictError(case_id, expected_version)
        self._session.flush()
        return self.get_case(case_id)

    def bump_case_version(
        self,
        *,
        case_id: str,
        expected_version: int,
        new_summary: str | None = None,
    ) -> ReviewCase:
        """Bump the version for a note-only or decision-only update.

        Same optimistic-concurrency semantics as :meth:`update_case_status`
        but does not change the status.
        """
        values: dict[str, Any] = {
            "version": expected_version + 1,
            "updated_at": datetime.now(timezone.utc),
        }
        if new_summary is not None:
            values["summary"] = new_summary
        stmt = (
            update(ReviewCase)
            .where(
                ReviewCase.id == case_id,
                ReviewCase.version == expected_version,
            )
            .values(**values)
        )
        result = self._session.execute(stmt)
        if result.rowcount == 0:
            raise ConcurrencyConflictError(case_id, expected_version)
        self._session.flush()
        return self.get_case(case_id)
