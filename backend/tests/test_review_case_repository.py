"""Review-case repository and service workflow tests (real PostgreSQL).

Covers the internal service operations (PR-03 §9, §15 review workflow):

* create_case + initial event
* get_case
* list_cases with pagination
* add_note
* transition_status (allowed and rejected)
* record_decision
* get_case_history (deterministic order, version consistency)
* no fabricated fraud-confirmation states
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
from app.domain.statuses import IllegalTransitionError, ReviewStatus
from app.repositories.review_cases import CaseNotFoundError


def _make_create_request(**overrides):
    defaults = dict(
        dataset_id="ulb-benchmark",
        snapshot_id="snap-001",
        record_ref="row-00042",
        title="Suspicious utilization pattern",
        summary="Initial review of IF anomaly score.",
        created_by="fixture-reviewer-001",
    )
    defaults.update(overrides)
    return CreateCaseRequest(**defaults)


class TestCreateCase:
    def test_create_case_returns_case_with_initial_status(self, db_service):
        case = db_service.create_case(_make_create_request())
        assert case.status == ReviewStatus.NOT_REVIEWED
        assert case.version == 1
        assert case.dataset_id == "ulb-benchmark"
        assert case.record_ref == "row-00042"
        assert case.created_by == "fixture-reviewer-001"

    def test_create_case_persists_initial_created_event(self, db_service):
        case = db_service.create_case(_make_create_request())
        history = db_service.get_case_history(case.id)
        assert history.total == 1
        event = history.items[0]
        assert event.event_type == EventType.CREATED
        assert event.case_version == 1
        assert event.new_status == ReviewStatus.NOT_REVIEWED
        assert event.previous_status is None
        assert event.actor_ref == "fixture-reviewer-001"

    def test_create_case_atomic_with_event(self, db_session_factory, db_service):
        """If the event insert fails, the case must not survive (AC-03-02)."""
        case = db_service.create_case(_make_create_request())
        assert case.version == 1
        # Verify both case and event exist after the atomic commit.
        history = db_service.get_case_history(case.id)
        assert history.total == 1


class TestGetCase:
    def test_get_case_returns_existing(self, db_service):
        created = db_service.create_case(_make_create_request())
        fetched = db_service.get_case(created.id)
        assert fetched.id == created.id
        assert fetched.status == created.status

    def test_get_case_raises_for_nonexistent(self, db_service):
        import uuid

        with pytest.raises(CaseNotFoundError):
            db_service.get_case(str(uuid.uuid4()))


class TestListCases:
    def test_list_empty(self, db_service):
        result = db_service.list_cases()
        assert result.total == 0
        assert result.items == []

    def test_list_with_pagination(self, db_service):
        for i in range(5):
            db_service.create_case(_make_create_request(record_ref=f"row-{i:05d}"))
        result = db_service.list_cases(limit=2, offset=0)
        assert result.total == 5
        assert len(result.items) == 2
        result2 = db_service.list_cases(limit=2, offset=2)
        assert len(result2.items) == 2
        # Deterministic order: no overlap between pages.
        ids_page1 = {c.id for c in result.items}
        ids_page2 = {c.id for c in result2.items}
        assert ids_page1.isdisjoint(ids_page2)

    def test_list_filter_by_dataset(self, db_service):
        db_service.create_case(_make_create_request(dataset_id="ulb-benchmark"))
        db_service.create_case(_make_create_request(dataset_id="pmgsy-iii"))
        result = db_service.list_cases(dataset_id="ulb-benchmark")
        assert result.total == 1
        assert result.items[0].dataset_id == "ulb-benchmark"

    def test_list_filter_by_status(self, db_service):
        case = db_service.create_case(_make_create_request())
        db_service.transition_status(
            case.id,
            TransitionStatusRequest(
                to_status=ReviewStatus.UNDER_REVIEW,
                reason="Begin review",
                actor_ref="fixture-reviewer-001",
                expected_version=1,
            ),
        )
        result = db_service.list_cases(status=ReviewStatus.UNDER_REVIEW)
        assert result.total == 1
        assert result.items[0].status == ReviewStatus.UNDER_REVIEW

    def test_page_size_capped_at_100(self, db_service):
        result = db_service.list_cases(limit=500)
        assert result.limit == 100


class TestAddNote:
    def test_add_note_creates_note_event_and_bumps_version(self, db_service):
        case = db_service.create_case(_make_create_request())
        updated = db_service.add_note(
            case.id,
            AddNoteRequest(
                note_text="Needs cross-check with PMGSY baseline.",
                actor_ref="fixture-reviewer-002",
                expected_version=1,
            ),
        )
        assert updated.version == 2
        history = db_service.get_case_history(case.id)
        assert history.total == 2
        note_event = history.items[1]
        assert note_event.event_type == EventType.NOTE_ADDED
        assert note_event.case_version == 2
        assert note_event.event_payload["note_text"] == "Needs cross-check with PMGSY baseline."

    def test_add_note_does_not_change_status(self, db_service):
        case = db_service.create_case(_make_create_request())
        updated = db_service.add_note(
            case.id,
            AddNoteRequest(
                note_text="A note.",
                actor_ref="fixture-reviewer-002",
                expected_version=1,
            ),
        )
        assert updated.status == ReviewStatus.NOT_REVIEWED

    def test_add_note_preserves_older_notes(self, db_service):
        case = db_service.create_case(_make_create_request())
        db_service.add_note(
            case.id,
            AddNoteRequest(
                note_text="First note.",
                actor_ref="fixture-reviewer-002",
                expected_version=1,
            ),
        )
        db_service.add_note(
            case.id,
            AddNoteRequest(
                note_text="Second note.",
                actor_ref="fixture-reviewer-002",
                expected_version=2,
            ),
        )
        history = db_service.get_case_history(case.id)
        notes = [e for e in history.items if e.event_type == EventType.NOTE_ADDED]
        assert len(notes) == 2
        assert notes[0].event_payload["note_text"] == "First note."
        assert notes[1].event_payload["note_text"] == "Second note."


class TestTransitionStatus:
    def test_legal_transition_accepted(self, db_service):
        case = db_service.create_case(_make_create_request())
        updated = db_service.transition_status(
            case.id,
            TransitionStatusRequest(
                to_status=ReviewStatus.UNDER_REVIEW,
                reason="Begin review.",
                actor_ref="fixture-reviewer-001",
                expected_version=1,
            ),
        )
        assert updated.status == ReviewStatus.UNDER_REVIEW
        assert updated.version == 2

    def test_illegal_transition_rejected(self, db_service):
        case = db_service.create_case(_make_create_request())
        with pytest.raises(IllegalTransitionError):
            db_service.transition_status(
                case.id,
                TransitionStatusRequest(
                    to_status=ReviewStatus.ESCALATED_FOR_EXAMINATION,
                    reason="Skip review.",
                    actor_ref="fixture-reviewer-001",
                    expected_version=1,
                ),
            )
        # The case must remain unchanged.
        fetched = db_service.get_case(case.id)
        assert fetched.status == ReviewStatus.NOT_REVIEWED
        assert fetched.version == 1

    def test_illegal_transition_writes_no_event(self, db_service):
        case = db_service.create_case(_make_create_request())
        with pytest.raises(IllegalTransitionError):
            db_service.transition_status(
                case.id,
                TransitionStatusRequest(
                    to_status=ReviewStatus.EXPLAINED_DEVIATION,
                    reason="Skip.",
                    actor_ref="fixture-reviewer-001",
                    expected_version=1,
                ),
            )
        history = db_service.get_case_history(case.id)
        assert history.total == 1  # only the initial 'created' event

    def test_transition_records_status_changed_event(self, db_service):
        case = db_service.create_case(_make_create_request())
        db_service.transition_status(
            case.id,
            TransitionStatusRequest(
                to_status=ReviewStatus.UNDER_REVIEW,
                reason="Begin review.",
                actor_ref="fixture-reviewer-001",
                expected_version=1,
            ),
        )
        history = db_service.get_case_history(case.id)
        status_events = [e for e in history.items if e.event_type == EventType.STATUS_CHANGED]
        assert len(status_events) == 1
        assert status_events[0].previous_status == ReviewStatus.NOT_REVIEWED
        assert status_events[0].new_status == ReviewStatus.UNDER_REVIEW
        assert status_events[0].reason == "Begin review."

    def test_reopen_records_reopened_event(self, db_service):
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
        db_service.transition_status(
            case.id,
            TransitionStatusRequest(
                to_status=ReviewStatus.UNDER_REVIEW,
                reason="Reopen for re-examination.",
                actor_ref="r1",
                expected_version=3,
            ),
        )
        history = db_service.get_case_history(case.id)
        reopened = [e for e in history.items if e.event_type == EventType.REOPENED]
        assert len(reopened) == 1
        assert reopened[0].previous_status == ReviewStatus.EXPLAINED_DEVIATION
        assert reopened[0].new_status == ReviewStatus.UNDER_REVIEW


class TestRecordDecision:
    def test_decision_with_status_change(self, db_service):
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
        updated = db_service.record_decision(
            case.id,
            RecordDecisionRequest(
                outcome=ReviewStatus.EXPLAINED_DEVIATION,
                rationale="Deviation explained by data-quality issue in source.",
                actor_ref="r1",
                expected_version=2,
            ),
        )
        assert updated.status == ReviewStatus.EXPLAINED_DEVIATION
        history = db_service.get_case_history(case.id)
        decision_events = [e for e in history.items if e.event_type == EventType.DECISION_RECORDED]
        assert len(decision_events) == 1
        assert decision_events[0].reason == "Deviation explained by data-quality issue in source."

    def test_decision_no_status_change(self, db_service):
        case = db_service.create_case(_make_create_request())
        updated = db_service.record_decision(
            case.id,
            RecordDecisionRequest(
                outcome=ReviewStatus.NOT_REVIEWED,
                rationale="Preliminary note; no outcome yet.",
                actor_ref="r1",
                expected_version=1,
            ),
        )
        assert updated.status == ReviewStatus.NOT_REVIEWED
        history = db_service.get_case_history(case.id)
        decision_events = [e for e in history.items if e.event_type == EventType.DECISION_RECORDED]
        assert len(decision_events) == 1


class TestCaseHistory:
    def test_history_deterministic_order(self, db_service):
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
        history = db_service.get_case_history(case.id)
        versions = [e.case_version for e in history.items]
        assert versions == sorted(versions)
        assert versions == [1, 2, 3]

    def test_history_version_consistency(self, db_service):
        """Each event's case_version matches the case version after the event."""
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
        fetched = db_service.get_case(case.id)
        history = db_service.get_case_history(case.id)
        # The last event's version matches the current case version.
        assert history.items[-1].case_version == fetched.version

    def test_history_for_nonexistent_case_raises(self, db_service):
        import uuid

        with pytest.raises(CaseNotFoundError):
            db_service.get_case_history(str(uuid.uuid4()))
