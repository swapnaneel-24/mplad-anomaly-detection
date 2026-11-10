"""Append-only case-event enforcement tests (real PostgreSQL).

Verifies that the ``case_events`` table rejects ``UPDATE`` and ``DELETE``
at the database boundary (PR-03 §7, AC-03-04), not merely through ORM
convention. Both application-level and PostgreSQL-level safeguards are
exercised.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.contracts.review_cases import CreateCaseRequest
from app.domain.events import EventType


def _seed_case(db_service) -> str:
    case = db_service.create_case(
        CreateCaseRequest(
            dataset_id="ulb-benchmark",
            snapshot_id="snap-001",
            record_ref="row-00042",
            title="Test case",
            created_by="fixture-actor",
        )
    )
    return case.id


class TestAppendOnlyUpdateRejected:
    def test_update_event_rejected_at_db_level(self, db_session_factory, db_service):
        case_id = _seed_case(db_service)
        # Direct SQL UPDATE on case_events must be rejected by the trigger.
        with db_session_factory() as session:
            with pytest.raises((ProgrammingError, IntegrityError)) as exc_info:
                session.execute(text(
                    "UPDATE case_events SET reason = 'tampered' WHERE case_id = :cid"
                ), {"cid": case_id})
                session.commit()
            assert "append-only" in str(exc_info.value).lower()

    def test_update_event_rejected_via_orm(self, db_session_factory, db_service):
        case_id = _seed_case(db_service)
        with db_session_factory() as session:
            from app.db.models import CaseEvent

            event = session.query(CaseEvent).filter_by(case_id=case_id).first()
            event.reason = "tampered"
            with pytest.raises((ProgrammingError, IntegrityError)):
                session.commit()


class TestAppendOnlyDeleteRejected:
    def test_delete_event_rejected_at_db_level(self, db_session_factory, db_service):
        case_id = _seed_case(db_service)
        with db_session_factory() as session:
            with pytest.raises((ProgrammingError, IntegrityError)) as exc_info:
                session.execute(text(
                    "DELETE FROM case_events WHERE case_id = :cid"
                ), {"cid": case_id})
                session.commit()
            assert "append-only" in str(exc_info.value).lower()

    def test_delete_event_rejected_via_orm(self, db_session_factory, db_service):
        case_id = _seed_case(db_service)
        with db_session_factory() as session:
            from app.db.models import CaseEvent

            event = session.query(CaseEvent).filter_by(case_id=case_id).first()
            session.delete(event)
            with pytest.raises((ProgrammingError, IntegrityError)):
                session.commit()


class TestExistingEventUnchanged:
    def test_existing_event_remains_after_failed_tamper(self, db_session_factory, db_service):
        case_id = _seed_case(db_service)
        with db_session_factory() as session:
            try:
                session.execute(text(
                    "UPDATE case_events SET reason = 'tampered' WHERE case_id = :cid"
                ), {"cid": case_id})
                session.commit()
            except (ProgrammingError, IntegrityError):
                session.rollback()

        # The original event is still there, unchanged.
        history = db_service.get_case_history(case_id)
        assert history.total == 1
        assert history.items[0].event_type == EventType.CREATED
        assert history.items[0].reason is None

    def test_insert_new_event_still_works(self, db_service):
        """INSERT is not blocked — only UPDATE and DELETE are."""
        from app.contracts.review_cases import AddNoteRequest

        case_id = _seed_case(db_service)
        db_service.add_note(
            case_id,
            AddNoteRequest(
                note_text="A legitimate note.",
                actor_ref="fixture-actor",
                expected_version=1,
            ),
        )
        history = db_service.get_case_history(case_id)
        assert history.total == 2
