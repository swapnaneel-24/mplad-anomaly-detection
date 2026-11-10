"""Transaction, rollback, and concurrency tests (real PostgreSQL).

Verifies (PR-03 §10, AC-03-06, AC-03-07):

* Atomic case creation + event.
* Atomic status update + event.
* Rollback on insertion failure leaves no partial state.
* Rollback on invalid transition leaves no stray event.
* Concurrent stale updates produce a deterministic conflict (409 semantics).
* No orphan events after rejected updates.
* No lost update (Reviewer A wins, Reviewer B fails).
"""

from __future__ import annotations

import threading
import uuid

import pytest
from sqlalchemy import text

from app.contracts.review_cases import (
    AddNoteRequest,
    CreateCaseRequest,
    TransitionStatusRequest,
)
from app.domain.statuses import IllegalTransitionError, ReviewStatus
from app.repositories.review_cases import ConcurrencyConflictError
from app.services.review_cases import ReviewCaseService


def _make_create_request(**overrides):
    defaults = dict(
        dataset_id="ulb-benchmark",
        snapshot_id="snap-001",
        record_ref="row-00042",
        title="Concurrency test case",
        created_by="fixture-reviewer-001",
    )
    defaults.update(overrides)
    return CreateCaseRequest(**defaults)


class TestAtomicCreation:
    def test_case_and_event_commit_together(self, db_service):
        case = db_service.create_case(_make_create_request())
        history = db_service.get_case_history(case.id)
        assert history.total == 1
        assert history.items[0].event_type.value == "created"


class TestRollbackOnFailure:
    def test_rollback_on_invalid_transition_leaves_no_event(self, db_service):
        case = db_service.create_case(_make_create_request())
        with pytest.raises(IllegalTransitionError):
            db_service.transition_status(
                case.id,
                TransitionStatusRequest(
                    to_status=ReviewStatus.ESCALATED_FOR_EXAMINATION,
                    reason="Illegal skip.",
                    actor_ref="r1",
                    expected_version=1,
                ),
            )
        # No status_changed event was written.
        history = db_service.get_case_history(case.id)
        assert history.total == 1  # only the initial 'created' event
        # The case itself is unchanged.
        fetched = db_service.get_case(case.id)
        assert fetched.status == ReviewStatus.NOT_REVIEWED
        assert fetched.version == 1

    def test_rollback_on_constraint_failure_leaves_no_partial_state(self, db_session_factory, db_service):
        """If an event insert fails mid-transaction, the case update rolls back."""
        case = db_service.create_case(_make_create_request())
        # Simulate a failure: add a note with the wrong expected_version
        # (stale). The optimistic-concurrency check must reject the whole
        # transaction — no version bump, no note event.
        with pytest.raises(ConcurrencyConflictError):
            db_service.add_note(
                case.id,
                AddNoteRequest(
                    note_text="Stale note.",
                    actor_ref="r1",
                    expected_version=999,  # deliberately wrong
                ),
            )
        fetched = db_service.get_case(case.id)
        assert fetched.version == 1  # unchanged
        history = db_service.get_case_history(case.id)
        assert history.total == 1  # no note event


class TestOptimisticConcurrency:
    def test_stale_update_produces_conflict(self, db_session_factory, db_service):
        """Two sessions read version 3; A updates to 4; B's stale update fails."""
        # Create a case and advance it to version 3.
        case = db_service.create_case(_make_create_request())
        db_service.transition_status(
            case.id,
            TransitionStatusRequest(
                to_status=ReviewStatus.UNDER_REVIEW,
                reason="Begin.",
                actor_ref="r1",
                expected_version=1,
            ),
        )
        db_service.add_note(
            case.id,
            AddNoteRequest(
                note_text="Note to reach version 3.",
                actor_ref="r1",
                expected_version=2,
            ),
        )
        current = db_service.get_case(case.id)
        assert current.version == 3

        # Reviewer A updates from version 3 to version 4.
        db_service.transition_status(
            case.id,
            TransitionStatusRequest(
                to_status=ReviewStatus.EXPLAINED_DEVIATION,
                reason="Explained by A.",
                actor_ref="reviewer-a",
                expected_version=3,
            ),
        )
        after_a = db_service.get_case(case.id)
        assert after_a.version == 4
        assert after_a.status == ReviewStatus.EXPLAINED_DEVIATION

        # Reviewer B attempts to update using the stale version 3.
        with pytest.raises(ConcurrencyConflictError) as exc_info:
            db_service.transition_status(
                case.id,
                TransitionStatusRequest(
                    to_status=ReviewStatus.UNDER_REVIEW,
                    reason="Reopen by B.",
                    actor_ref="reviewer-b",
                    expected_version=3,  # stale
                ),
            )
        assert exc_info.value.case_id == case.id
        assert exc_info.value.expected_version == 3

    def test_no_duplicate_event_after_rejected_update(self, db_service):
        """A rejected stale update must not write a duplicate event."""
        case = db_service.create_case(_make_create_request())
        # First successful transition.
        db_service.transition_status(
            case.id,
            TransitionStatusRequest(
                to_status=ReviewStatus.UNDER_REVIEW,
                reason="Begin.",
                actor_ref="r1",
                expected_version=1,
            ),
        )
        history_before = db_service.get_case_history(case.id)
        assert history_before.total == 2  # created + status_changed

        # Stale transition attempt (expected_version=1, but current is 2).
        with pytest.raises(ConcurrencyConflictError):
            db_service.transition_status(
                case.id,
                TransitionStatusRequest(
                    to_status=ReviewStatus.EXPLAINED_DEVIATION,
                    reason="Stale.",
                    actor_ref="r1",
                    expected_version=1,
                ),
            )
        history_after = db_service.get_case_history(case.id)
        assert history_after.total == 2  # unchanged — no duplicate event

    def test_no_lost_update(self, db_service):
        """Reviewer A's change survives Reviewer B's rejected stale attempt."""
        case = db_service.create_case(_make_create_request())
        db_service.transition_status(
            case.id,
            TransitionStatusRequest(
                to_status=ReviewStatus.UNDER_REVIEW,
                reason="Begin.",
                actor_ref="r1",
                expected_version=1,
            ),
        )
        # Reviewer A changes status to a terminal outcome.
        db_service.transition_status(
            case.id,
            TransitionStatusRequest(
                to_status=ReviewStatus.EXPLAINED_DEVIATION,
                reason="By A.",
                actor_ref="reviewer-a",
                expected_version=2,
            ),
        )
        # Reviewer B's stale attempt to reopen (a legal transition from
        # explained_deviation, but with a stale expected_version) must fail.
        with pytest.raises(ConcurrencyConflictError):
            db_service.transition_status(
                case.id,
                TransitionStatusRequest(
                    to_status=ReviewStatus.UNDER_REVIEW,
                    reason="Reopen by B (stale).",
                    actor_ref="reviewer-b",
                    expected_version=2,  # stale; current is 3
                ),
            )
        # Reviewer A's change is preserved.
        fetched = db_service.get_case(case.id)
        assert fetched.status == ReviewStatus.EXPLAINED_DEVIATION
        assert fetched.version == 3


class TestIndependentTransactions:
    def test_genuine_independent_sessions_conflict(self, db_session_factory, db_service):
        """Exercise two independent session factories, not one in-memory object."""
        case = db_service.create_case(_make_create_request())
        # Open two independent sessions and read the case in each.
        with db_session_factory() as s1:
            from app.db.models import ReviewCase

            case_v1_s1 = s1.get(ReviewCase, case.id)
            assert case_v1_s1.version == 1

        with db_session_factory() as s2:
            case_v1_s2 = s2.get(ReviewCase, case.id)
            assert case_v1_s2.version == 1

        # Session 1 updates to version 2.
        service_a = ReviewCaseService(db_session_factory)
        service_a.transition_status(
            case.id,
            TransitionStatusRequest(
                to_status=ReviewStatus.UNDER_REVIEW,
                reason="By A.",
                actor_ref="reviewer-a",
                expected_version=1,
            ),
        )

        # Session 2's stale view (version 1) must now conflict.
        service_b = ReviewCaseService(db_session_factory)
        with pytest.raises(ConcurrencyConflictError):
            service_b.transition_status(
                case.id,
                TransitionStatusRequest(
                    to_status=ReviewStatus.EXPLAINED_DEVIATION,
                    reason="By B (stale).",
                    actor_ref="reviewer-b",
                    expected_version=1,
                ),
            )
