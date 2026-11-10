"""Service layer: transactional review-case workflows.

The service layer owns the database transaction boundary. Each operation
that mutates a case does so in a single transaction that also persists
the corresponding append-only event: either both commit, or neither
commits (PR-03 §7, ADR-003 §4.3 write invariant).

Operations (PR-03 §9):

* :meth:`create_case` — create a case and its initial ``created`` event.
* :meth:`get_case` — retrieve a single case.
* :meth:`list_cases` — paginated, deterministically ordered list.
* :meth:`add_note` — append a note event and bump the case version.
* :meth:`transition_status` — legal-transition-checked status change.
* :meth:`record_decision` — structured decision with rationale.
* :meth:`get_case_history` — the append-only event sequence.

Actor identity (PR-03 §8):

* ``actor_ref`` values are supplied by the caller through an internal
  trusted application context. The service never trusts a public
  ``actor_ref`` as proof of identity (PR-04 binds the authenticated
  principal).
* There is no hardcoded admin identity.
* Synthetic tests pass explicitly marked fixture actor IDs.

Optimistic concurrency (PR-03 §10):

* Every mutating operation takes ``expected_version`` and delegates to
  the repository's ``WHERE version = :expected`` update. A stale version
  raises :class:`ConcurrencyConflictError`, the transaction rolls back,
  and no duplicate event is written.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.contracts.review_cases import (
    AddNoteRequest,
    CaseDetail,
    CaseEventRecord,
    CaseHistoryResponse,
    CaseListResponse,
    CaseSummary,
    CreateCaseRequest,
    RecordDecisionRequest,
    TransitionStatusRequest,
)
from app.domain.events import EventType
from app.domain.statuses import (
    INITIAL_STATUS,
    IllegalTransitionError,
    ReviewStatus,
    validate_transition,
)
from app.repositories.review_cases import (
    CaseNotFoundError,
    ConcurrencyConflictError,
    ReviewCaseRepository,
)


class ReviewCaseService:
    """Transactional service for review-case workflows.

    Constructed with a callable that returns a fresh ``Session`` (the
    injectable session factory). Each public method opens its own
    session/transaction and commits or rolls back atomically.
    """

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ create
    def create_case(self, request: CreateCaseRequest) -> CaseDetail:
        """Create a review case and its initial ``created`` event atomically.

        The case starts in ``not_reviewed`` (the only legal initial
        status). A ``created`` event is persisted in the same transaction;
        if either write fails, neither survives (PR-03 §7.3, AC-03-02).
        """
        case_id = str(uuid.uuid4())
        event_id = str(uuid.uuid4())

        with self._session_factory() as session:
            repo = ReviewCaseRepository(session)
            case = repo.insert_case(
                case_id=case_id,
                dataset_id=request.dataset_id,
                snapshot_id=request.snapshot_id,
                record_ref=request.record_ref,
                status=INITIAL_STATUS,
                title=request.title,
                summary=request.summary,
                created_by=request.created_by,
            )
            repo.insert_event(
                event_id=event_id,
                case_id=case_id,
                event_type=EventType.CREATED,
                actor_ref=request.created_by,
                previous_status=None,
                new_status=INITIAL_STATUS,
                reason=None,
                event_payload={
                    "title": request.title,
                    "summary": request.summary,
                },
                case_version=case.version,
            )
            session.commit()
            return self._to_detail(case)

    # ------------------------------------------------------------------ read
    def get_case(self, case_id: str) -> CaseDetail:
        """Return the case with ``case_id`` or raise :class:`CaseNotFoundError`."""
        with self._session_factory() as session:
            repo = ReviewCaseRepository(session)
            return self._to_detail(repo.get_case(case_id))

    def list_cases(
        self,
        *,
        dataset_id: str | None = None,
        snapshot_id: str | None = None,
        status: ReviewStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> CaseListResponse:
        """Return a paginated, deterministically ordered list of cases."""
        # Server-side cap on page size (ADR-003 §4.4: cap 100).
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        with self._session_factory() as session:
            repo = ReviewCaseRepository(session)
            rows, total = repo.list_cases(
                dataset_id=dataset_id,
                snapshot_id=snapshot_id,
                status=status,
                limit=limit,
                offset=offset,
            )
            return CaseListResponse(
                items=[self._to_summary(r) for r in rows],
                total=total,
                limit=limit,
                offset=offset,
            )

    def get_case_history(self, case_id: str) -> CaseHistoryResponse:
        """Return the append-only event history for ``case_id``."""
        with self._session_factory() as session:
            repo = ReviewCaseRepository(session)
            # Raise CaseNotFoundError if the case does not exist.
            repo.get_case(case_id)
            events = repo.list_events(case_id)
            return CaseHistoryResponse(
                case_id=case_id,
                items=[self._to_event_record(e) for e in events],
                total=len(events),
            )

    # ------------------------------------------------------------------ note
    def add_note(self, case_id: str, request: AddNoteRequest) -> CaseDetail:
        """Append a reviewer note as a ``note_added`` event and bump the version.

        The note text is stored in the event's ``event_payload`` (the
        ``review_cases`` row itself carries no note column). Older notes
        are never overwritten (PR-03 §7.5).
        """
        with self._session_factory() as session:
            repo = ReviewCaseRepository(session)
            case = repo.get_case(case_id)
            updated = repo.bump_case_version(
                case_id=case_id,
                expected_version=request.expected_version,
            )
            repo.insert_event(
                event_id=str(uuid.uuid4()),
                case_id=case_id,
                event_type=EventType.NOTE_ADDED,
                actor_ref=request.actor_ref,
                previous_status=None,
                new_status=None,
                reason=None,
                event_payload={"note_text": request.note_text},
                case_version=updated.version,
            )
            session.commit()
            return self._to_detail(updated)

    # ------------------------------------------------------------------ transition
    def transition_status(
        self, case_id: str, request: TransitionStatusRequest
    ) -> CaseDetail:
        """Apply a legal status transition atomically with a ``status_changed`` event.

        Raises :class:`IllegalTransitionError` if the transition is not
        permitted (PR-03 §6, AC-03-05). The transaction rolls back and no
        event is written.
        """
        with self._session_factory() as session:
            repo = ReviewCaseRepository(session)
            case = repo.get_case(case_id)
            from_status = ReviewStatus(case.status)
            validate_transition(from_status, request.to_status)
            updated = repo.update_case_status(
                case_id=case_id,
                expected_version=request.expected_version,
                new_status=request.to_status,
            )
            event_type = EventType.REOPENED if _is_reopen(from_status, request.to_status) else EventType.STATUS_CHANGED
            repo.insert_event(
                event_id=str(uuid.uuid4()),
                case_id=case_id,
                event_type=event_type,
                actor_ref=request.actor_ref,
                previous_status=from_status,
                new_status=request.to_status,
                reason=request.reason,
                event_payload=None,
                case_version=updated.version,
            )
            session.commit()
            return self._to_detail(updated)

    # ------------------------------------------------------------------ decision
    def record_decision(
        self, case_id: str, request: RecordDecisionRequest
    ) -> CaseDetail:
        """Record a structured decision (outcome + rationale) atomically.

        A decision is persisted as a ``decision_recorded`` event. When the
        outcome changes the status, a ``status_changed`` (or ``reopened``)
        event is also written in the same transaction.
        """
        with self._session_factory() as session:
            repo = ReviewCaseRepository(session)
            case = repo.get_case(case_id)
            from_status = ReviewStatus(case.status)
            outcome = request.outcome
            if from_status != outcome:
                validate_transition(from_status, outcome)
                updated = repo.update_case_status(
                    case_id=case_id,
                    expected_version=request.expected_version,
                    new_status=outcome,
                )
                status_event_type = (
                    EventType.REOPENED if _is_reopen(from_status, outcome) else EventType.STATUS_CHANGED
                )
                repo.insert_event(
                    event_id=str(uuid.uuid4()),
                    case_id=case_id,
                    event_type=status_event_type,
                    actor_ref=request.actor_ref,
                    previous_status=from_status,
                    new_status=outcome,
                    reason=f"Decision outcome: {outcome.value}",
                    event_payload=None,
                    case_version=updated.version,
                )
                decision_case_version = updated.version
            else:
                updated = repo.bump_case_version(
                    case_id=case_id,
                    expected_version=request.expected_version,
                )
                decision_case_version = updated.version
            repo.insert_event(
                event_id=str(uuid.uuid4()),
                case_id=case_id,
                event_type=EventType.DECISION_RECORDED,
                actor_ref=request.actor_ref,
                previous_status=from_status,
                new_status=outcome,
                reason=request.rationale,
                event_payload={"outcome": outcome.value},
                case_version=decision_case_version,
            )
            session.commit()
            return self._to_detail(updated)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _to_summary(case) -> CaseSummary:
        return CaseSummary(
            id=case.id,
            dataset_id=case.dataset_id,
            snapshot_id=case.snapshot_id,
            record_ref=case.record_ref,
            status=ReviewStatus(case.status),
            title=case.title,
            summary=case.summary,
            created_at=case.created_at,
            updated_at=case.updated_at,
            version=case.version,
            created_by=case.created_by,
        )

    @classmethod
    def _to_detail(cls, case) -> CaseDetail:
        return CaseDetail(**cls._to_summary(case).model_dump())

    @staticmethod
    def _to_event_record(event) -> CaseEventRecord:
        return CaseEventRecord(
            id=event.id,
            case_id=event.case_id,
            event_type=EventType(event.event_type),
            event_at=event.event_at,
            actor_ref=event.actor_ref,
            previous_status=ReviewStatus(event.previous_status) if event.previous_status else None,
            new_status=ReviewStatus(event.new_status) if event.new_status else None,
            reason=event.reason,
            event_payload=event.event_payload,
            case_version=event.case_version,
            event_seq=event.event_seq,
        )


def _is_reopen(from_status: ReviewStatus, to_status: ReviewStatus) -> bool:
    """A transition is a 'reopen' when it returns from a terminal outcome to under_review."""
    from app.domain.statuses import is_terminal

    return is_terminal(from_status) and to_status == ReviewStatus.UNDER_REVIEW
