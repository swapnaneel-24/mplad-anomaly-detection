"""Audit-event ordering regression tests (PR-03 hardening §2).

``record_decision()`` with a status change writes two events at the same
``case_version``: a ``status_changed`` (or ``reopened``) event followed
by a ``decision_recorded`` event. These tests verify that:

1. The two events share the same ``case_version`` (intentional, not a bug).
2. Their intra-version order is deterministic: the status-change event
   always precedes the decision-recorded event.
3. The ``event_seq`` column provides the database-backed ordering
   guarantee (monotonic, insertion-order).
4. The full history is chronologically consistent across multiple
   operations and versions.
5. The ``event_seq`` values are strictly increasing across the entire
   history (global monotonic sequence).
6. No incorrect uniqueness constraint on ``(case_id, case_version)``
   exists (multiple events per version are accepted).
"""

from __future__ import annotations

import pytest

from app.contracts.review_cases import (
    AddNoteRequest,
    CreateCaseRequest,
    RecordDecisionRequest,
    TransitionStatusRequest,
)
from app.domain.events import EventType
from app.domain.statuses import ReviewStatus


def _make_create_request(**overrides):
    defaults = dict(
        dataset_id="ulb-benchmark",
        snapshot_id="snap-001",
        record_ref="row-00042",
        title="Decision ordering test case",
        created_by="fixture-reviewer-001",
    )
    defaults.update(overrides)
    return CreateCaseRequest(**defaults)


class TestTwoEventDecisionOrdering:
    """A decision with a status change produces two events at one version."""

    def test_decision_with_status_change_produces_two_events_same_version(
        self, db_service
    ):
        case = db_service.create_case(_make_create_request())
        db_service.transition_status(
            case.id,
            TransitionStatusRequest(
                to_status=ReviewStatus.UNDER_REVIEW,
                reason="Begin review.",
                actor_ref="r1",
                expected_version=1,
            ),
        )
        db_service.record_decision(
            case.id,
            RecordDecisionRequest(
                outcome=ReviewStatus.EXPLAINED_DEVIATION,
                rationale="Deviation explained by data-quality issue.",
                actor_ref="r1",
                expected_version=2,
            ),
        )
        history = db_service.get_case_history(case.id)
        # 1: created, 2: status_changed, 3: status_changed + decision_recorded
        assert history.total == 4
        # The last two events share the same case_version (3).
        last_two = history.items[-2:]
        assert last_two[0].case_version == last_two[1].case_version == 3

    def test_status_changed_precedes_decision_recorded(self, db_service):
        """Within the same version, the status-change event must come
        before the decision-recorded event."""
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
        db_service.record_decision(
            case.id,
            RecordDecisionRequest(
                outcome=ReviewStatus.EXPLAINED_DEVIATION,
                rationale="Explained.",
                actor_ref="r1",
                expected_version=2,
            ),
        )
        history = db_service.get_case_history(case.id)
        decision_events = [
            e for e in history.items if e.case_version == 3
        ]
        assert len(decision_events) == 2
        assert decision_events[0].event_type == EventType.STATUS_CHANGED
        assert decision_events[1].event_type == EventType.DECISION_RECORDED

    def test_event_seq_strictly_increasing_within_version(self, db_service):
        """The two events at the same version have strictly increasing
        ``event_seq`` values."""
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
        db_service.record_decision(
            case.id,
            RecordDecisionRequest(
                outcome=ReviewStatus.EXPLAINED_DEVIATION,
                rationale="Explained.",
                actor_ref="r1",
                expected_version=2,
            ),
        )
        history = db_service.get_case_history(case.id)
        decision_events = [
            e for e in history.items if e.case_version == 3
        ]
        assert decision_events[0].event_seq < decision_events[1].event_seq


class TestEventSeqGlobalMonotonicity:
    """``event_seq`` is a global monotonic sequence across all events."""

    def test_event_seq_strictly_increasing_across_full_history(self, db_service):
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
                note_text="A note.",
                actor_ref="r2",
                expected_version=2,
            ),
        )
        db_service.record_decision(
            case.id,
            RecordDecisionRequest(
                outcome=ReviewStatus.EXPLAINED_DEVIATION,
                rationale="Explained.",
                actor_ref="r1",
                expected_version=3,
            ),
        )
        history = db_service.get_case_history(case.id)
        seqs = [e.event_seq for e in history.items]
        # Strictly increasing across the full history.
        for i in range(1, len(seqs)):
            assert seqs[i] > seqs[i - 1], (
                f"event_seq not monotonic at index {i}: {seqs}"
            )

    def test_event_seq_no_collisions_across_cases(self, db_service):
        """Two independent cases get distinct, increasing event_seq values."""
        case_a = db_service.create_case(_make_create_request(record_ref="row-a"))
        case_b = db_service.create_case(_make_create_request(record_ref="row-b"))
        hist_a = db_service.get_case_history(case_a.id)
        hist_b = db_service.get_case_history(case_b.id)
        # Both have one 'created' event; their seqs must differ.
        assert hist_a.items[0].event_seq != hist_b.items[0].event_seq


class TestChronologicalHistoryRetrieval:
    """The full history is chronologically consistent and deterministic."""

    def test_history_is_deterministic_across_retrievals(self, db_service):
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
        db_service.record_decision(
            case.id,
            RecordDecisionRequest(
                outcome=ReviewStatus.EXPLAINED_DEVIATION,
                rationale="Explained.",
                actor_ref="r1",
                expected_version=2,
            ),
        )
        first = db_service.get_case_history(case.id)
        second = db_service.get_case_history(case.id)
        # Same order both times (deterministic).
        assert [e.id for e in first.items] == [e.id for e in second.items]
        assert [e.event_seq for e in first.items] == [
            e.event_seq for e in second.items
        ]

    def test_history_version_then_seq_order(self, db_service):
        """History is ordered by (case_version, event_seq) ascending."""
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
                note_text="Note.",
                actor_ref="r2",
                expected_version=2,
            ),
        )
        db_service.record_decision(
            case.id,
            RecordDecisionRequest(
                outcome=ReviewStatus.EXPLAINED_DEVIATION,
                rationale="Explained.",
                actor_ref="r1",
                expected_version=3,
            ),
        )
        history = db_service.get_case_history(case.id)
        # Verify (version, seq) is monotonically non-decreasing.
        keys = [(e.case_version, e.event_seq) for e in history.items]
        for i in range(1, len(keys)):
            assert keys[i] > keys[i - 1], (
                f"history not ordered at index {i}: {keys}"
            )

    def test_reopen_decision_also_orders_correctly(self, db_service):
        """A reopen decision (terminal → under_review) also produces two
        events at the same version; verify their order."""
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
        db_service.transition_status(
            case.id,
            TransitionStatusRequest(
                to_status=ReviewStatus.EXPLAINED_DEVIATION,
                reason="Explained.",
                actor_ref="r1",
                expected_version=2,
            ),
        )
        # Reopen via a decision: outcome=under_review from a terminal status.
        db_service.record_decision(
            case.id,
            RecordDecisionRequest(
                outcome=ReviewStatus.UNDER_REVIEW,
                rationale="Reopen for re-examination.",
                actor_ref="r1",
                expected_version=3,
            ),
        )
        history = db_service.get_case_history(case.id)
        reopen_events = [e for e in history.items if e.case_version == 4]
        assert len(reopen_events) == 2
        assert reopen_events[0].event_type == EventType.REOPENED
        assert reopen_events[1].event_type == EventType.DECISION_RECORDED
        assert reopen_events[0].event_seq < reopen_events[1].event_seq


class TestNoIncorrectUniqueConstraint:
    """Verify no uniqueness constraint on (case_id, case_version) exists
    (PR-03 hardening §2: multiple events per version are intentional)."""

    def test_two_events_same_version_accepted(self, db_session_factory, db_service):
        """Directly insert two events at the same version and verify both
        are accepted (no unique constraint rejection)."""
        import uuid

        from app.db.models import CaseEvent, ReviewCase

        case = db_service.create_case(_make_create_request())
        with db_session_factory() as session:
            e1 = CaseEvent(
                id=str(uuid.uuid4()),
                case_id=case.id,
                event_type="status_changed",
                actor_ref="fixture-actor",
                case_version=99,
            )
            e2 = CaseEvent(
                id=str(uuid.uuid4()),
                case_id=case.id,
                event_type="decision_recorded",
                actor_ref="fixture-actor",
                case_version=99,  # same version
            )
            session.add_all([e1, e2])
            session.commit()  # must succeed — no unique constraint
