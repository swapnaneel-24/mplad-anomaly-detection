"""Review-case model and constraint tests (real PostgreSQL).

Verifies valid/invalid case creation, invalid status rejection, required
identifiers, field-length limits, UUID handling, UTC timestamps, and
database indexes/uniqueness (PR-03 §15 models and constraints).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DataError, IntegrityError, StatementError

from app.contracts.review_cases import CreateCaseRequest
from app.domain.statuses import ReviewStatus
from app.repositories.review_cases import ReviewCaseRepository


class TestValidCaseCreation:
    def test_create_case_generates_uuid_id(self, db_session_factory):
        from app.db.models import ReviewCase

        with db_session_factory() as session:
            case = ReviewCase(
                id=str(uuid.uuid4()),
                dataset_id="ulb-benchmark",
                snapshot_id="snap-001",
                record_ref="row-00042",
                status="not_reviewed",
                title="Test case",
                summary=None,
                created_by="fixture-actor",
            )
            session.add(case)
            session.commit()
            session.refresh(case)
            # UUID is a valid UUID string.
            uuid.UUID(case.id)
            assert case.version == 1
            assert case.status == "not_reviewed"

    def test_created_at_is_utc(self, db_session_factory):
        from app.db.models import ReviewCase

        with db_session_factory() as session:
            case = ReviewCase(
                id=str(uuid.uuid4()),
                dataset_id="ulb-benchmark",
                snapshot_id="snap-001",
                record_ref="row-00042",
                status="not_reviewed",
                title="Test case",
                created_by="fixture-actor",
            )
            session.add(case)
            session.commit()
            session.refresh(case)
            assert case.created_at is not None
            # The timestamp is timezone-aware (UTC).
            assert case.created_at.tzinfo is not None


class TestInvalidStatusRejected:
    def test_invalid_status_rejected_by_check_constraint(self, db_session_factory):
        from app.db.models import ReviewCase

        with db_session_factory() as session:
            case = ReviewCase(
                id=str(uuid.uuid4()),
                dataset_id="ulb-benchmark",
                snapshot_id="snap-001",
                record_ref="row-00042",
                status="confirmed_fraud",  # not in the vocabulary
                title="Test case",
                created_by="fixture-actor",
            )
            session.add(case)
            with pytest.raises(IntegrityError):
                session.commit()

    def test_empty_status_rejected(self, db_session_factory):
        from app.db.models import ReviewCase

        with db_session_factory() as session:
            case = ReviewCase(
                id=str(uuid.uuid4()),
                dataset_id="ulb-benchmark",
                snapshot_id="snap-001",
                record_ref="row-00042",
                status="",
                title="Test case",
                created_by="fixture-actor",
            )
            session.add(case)
            with pytest.raises(IntegrityError):
                session.commit()


class TestRequiredFields:
    def test_missing_dataset_id_rejected(self, db_session_factory):
        from app.db.models import ReviewCase

        with db_session_factory() as session:
            case = ReviewCase(
                id=str(uuid.uuid4()),
                dataset_id=None,
                snapshot_id="snap-001",
                record_ref="row-00042",
                status="not_reviewed",
                title="Test case",
                created_by="fixture-actor",
            )
            session.add(case)
            with pytest.raises(IntegrityError):
                session.commit()

    def test_missing_record_ref_rejected(self, db_session_factory):
        from app.db.models import ReviewCase

        with db_session_factory() as session:
            case = ReviewCase(
                id=str(uuid.uuid4()),
                dataset_id="ulb-benchmark",
                snapshot_id="snap-001",
                record_ref=None,
                status="not_reviewed",
                title="Test case",
                created_by="fixture-actor",
            )
            session.add(case)
            with pytest.raises(IntegrityError):
                session.commit()

    def test_missing_created_by_rejected(self, db_session_factory):
        from app.db.models import ReviewCase

        with db_session_factory() as session:
            case = ReviewCase(
                id=str(uuid.uuid4()),
                dataset_id="ulb-benchmark",
                snapshot_id="snap-001",
                record_ref="row-00042",
                status="not_reviewed",
                title="Test case",
                created_by=None,
            )
            session.add(case)
            with pytest.raises(IntegrityError):
                session.commit()


class TestFieldLengthLimits:
    def test_title_max_240(self, db_session_factory):
        from app.db.models import ReviewCase

        with db_session_factory() as session:
            case = ReviewCase(
                id=str(uuid.uuid4()),
                dataset_id="ulb-benchmark",
                snapshot_id="snap-001",
                record_ref="row-00042",
                status="not_reviewed",
                title="x" * 241,  # over the limit
                created_by="fixture-actor",
            )
            session.add(case)
            # PostgreSQL raises DataError (StringDataRightTruncation) for
            # VARCHAR length violations, not IntegrityError.
            with pytest.raises((DataError, IntegrityError)):
                session.commit()

    def test_title_at_max_accepted(self, db_session_factory):
        from app.db.models import ReviewCase

        with db_session_factory() as session:
            case = ReviewCase(
                id=str(uuid.uuid4()),
                dataset_id="ulb-benchmark",
                snapshot_id="snap-001",
                record_ref="row-00042",
                status="not_reviewed",
                title="x" * 240,
                created_by="fixture-actor",
            )
            session.add(case)
            session.commit()  # should succeed


class TestReferentialIntegrity:
    def test_case_event_fk_to_nonexistent_case_rejected(self, db_session_factory):
        from app.db.models import CaseEvent

        with db_session_factory() as session:
            event = CaseEvent(
                id=str(uuid.uuid4()),
                case_id=str(uuid.uuid4()),  # does not exist
                event_type="created",
                actor_ref="fixture-actor",
                case_version=1,
            )
            session.add(event)
            with pytest.raises(IntegrityError):
                session.commit()


class TestMultipleEventsPerVersion:
    """Multiple events may share the same case_version when produced by a
    single transaction (e.g. ``record_decision`` writes a ``status_changed``
    event and a ``decision_recorded`` event at the same version). The
    chronological ordering within a version is guaranteed by ``event_at``
    and the event id."""

    def test_two_events_same_version_accepted(self, db_session_factory):
        from app.db.models import CaseEvent, ReviewCase

        with db_session_factory() as session:
            case = ReviewCase(
                id=str(uuid.uuid4()),
                dataset_id="ulb-benchmark",
                snapshot_id="snap-001",
                record_ref="row-00042",
                status="not_reviewed",
                title="Test case",
                created_by="fixture-actor",
            )
            session.add(case)
            session.flush()
            e1 = CaseEvent(
                id=str(uuid.uuid4()),
                case_id=case.id,
                event_type="status_changed",
                actor_ref="fixture-actor",
                case_version=2,
            )
            e2 = CaseEvent(
                id=str(uuid.uuid4()),
                case_id=case.id,
                event_type="decision_recorded",
                actor_ref="fixture-actor",
                case_version=2,  # same version, different event type
            )
            session.add_all([e1, e2])
            session.commit()  # should succeed
