"""PR-05B authenticated case API integration tests (real PostgreSQL).

Covers the complete investigation workflow against the real backend +
pgserver-backed PostgreSQL + authenticated sessions:

* Synthetic source listing and retrieval.
* Case creation from a valid synthetic record.
* Rejection of unknown / incompatible source references.
* Authenticated case list and detail.
* Case persistence across independent database sessions.
* Note addition and persistence.
* Status transitions (legal + illegal).
* Decision recording.
* Complete ordered event history.
* Rollback after failed transaction (illegal transition).
* Optimistic concurrency conflict (stale version).
* RBAC rejection (viewer cannot write).
* CSRF rejection (missing + invalid token).
* Principal-to-actor attribution (client-supplied actor ignored).
* No case mutation by viewer.
* Bounded pagination.
* UUID validation on path parameters.

These are genuine PostgreSQL integration tests — no SQLite, no mocks.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.session import DatabaseSessionFactory
from app.main import create_app
from tests.conftest import TEST_SESSION_SECRET, get_csrf_token, login

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture()
def pr05b_settings(db_url):
    """Settings with DB + auth + demonstration sources enabled."""
    return Settings(
        _env_file=None,
        environment="test",
        cors_origins=["http://test.example"],
        git_commit_sha=None,
        docs_enabled=True,
        database_url=db_url,
        database_required=True,
        session_secret=TEST_SESSION_SECRET,
        session_cookie_secure=False,
        demonstration_sources=True,
    )


@pytest.fixture()
def pr05b_app(pr05b_settings, db_session_factory):
    """Application with DB + auth + synthetic source wired in."""
    from tests.conftest import _truncate_auth_tables

    _truncate_auth_tables(db_session_factory)
    # Also truncate review cases for a clean slate.
    from sqlalchemy import text

    with db_session_factory() as session:
        session.execute(text("TRUNCATE TABLE case_events RESTART IDENTITY CASCADE"))
        session.execute(text("TRUNCATE TABLE review_cases RESTART IDENTITY CASCADE"))
        session.commit()

    return create_app(
        settings=pr05b_settings,
        db_session_factory_override=DatabaseSessionFactory(
            db_session_factory.kw["bind"], db_session_factory
        ),
    )


@pytest.fixture()
def pr05b_client(pr05b_app):
    return TestClient(pr05b_app)


@pytest.fixture()
def reviewer_user(pr05b_app, db_session_factory):
    """Create a reviewer user directly in the database."""
    from app.auth.passwords import hash_password
    from app.db.models import User

    with db_session_factory() as session:
        user = User(
            username="reviewer1",
            password_hash=hash_password(PASSWORD),
            display_name="Reviewer One",
            role="reviewer",
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


@pytest.fixture()
def viewer_user(db_session_factory):
    """Create a viewer user directly in the database."""
    from app.auth.passwords import hash_password
    from app.db.models import User

    with db_session_factory() as session:
        user = User(
            username="viewer1",
            password_hash=hash_password(PASSWORD),
            display_name="Viewer One",
            role="viewer",
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


@pytest.fixture()
def admin_user(db_session_factory):
    """Create an admin user directly in the database."""
    from app.auth.passwords import hash_password
    from app.db.models import User

    with db_session_factory() as session:
        user = User(
            username="admin1",
            password_hash=hash_password(PASSWORD),
            display_name="Admin One",
            role="admin",
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def _auth_headers(client: TestClient) -> dict[str, str]:
    """Return headers with a valid CSRF token after login."""
    csrf = get_csrf_token(client)
    return {"X-CSRF-Token": csrf}


class TestSyntheticSource:
    def test_list_synthetic_records(self, pr05b_client):
        response = pr05b_client.get("/api/v1/synthetic/records")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 8
        assert body["dataset_id"] == "synthetic-demonstration"
        assert body["snapshot_id"] == "synthetic-v1"
        for item in body["items"]:
            assert item["synthetic"] is True
            assert "SYNTHETIC" in item["title"]

    def test_get_one_synthetic_record(self, pr05b_client):
        response = pr05b_client.get("/api/v1/synthetic/records/synth-001")
        assert response.status_code == 200
        body = response.json()
        assert body["record_ref"] == "synth-001"
        assert body["synthetic"] is True
        assert "SYNTHETIC" in body["title"]
        assert body["dataset_id"] == "synthetic-demonstration"

    def test_get_unknown_synthetic_record_returns_404(self, pr05b_client):
        response = pr05b_client.get("/api/v1/synthetic/records/nonexistent")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_synthetic_records_require_no_auth(self, pr05b_client):
        """Synthetic records are readable without authentication (they are
        explicitly public demonstration data, not sensitive case data)."""
        response = pr05b_client.get("/api/v1/synthetic/records")
        assert response.status_code == 200


class TestCaseCreation:
    def test_reviewer_creates_case_from_synthetic_record(
        self, pr05b_client, reviewer_user
    ):
        login(pr05b_client, "reviewer1", PASSWORD)
        headers = _auth_headers(pr05b_client)
        response = pr05b_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "Investigation of synth-001",
                "summary": "Initial review of the synthetic demonstration record.",
                "created_by": "attacker-forged-actor",
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["id"] != ""
        # UUID shape.
        assert re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            body["id"],
        )
        # The server overwrote created_by with the principal's user UUID.
        assert body["created_by"] == reviewer_user.id
        assert body["created_by"] != "attacker-forged-actor"
        # dataset_id / snapshot_id are authoritative.
        assert body["dataset_id"] == "synthetic-demonstration"
        assert body["snapshot_id"] == "synthetic-v1"
        assert body["record_ref"] == "synth-001"
        assert body["status"] == "not_reviewed"
        assert body["version"] == 1
        # Location header.
        assert response.headers["location"] == f"/api/v1/cases/{body['id']}"

    def test_rejects_unknown_record_ref(self, pr05b_client, reviewer_user):
        login(pr05b_client, "reviewer1", PASSWORD)
        headers = _auth_headers(pr05b_client)
        response = pr05b_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "nonexistent-record",
                "title": "x",
                "created_by": "r1",
            },
            headers=headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_rejects_spoofed_dataset_id(self, pr05b_client, reviewer_user):
        """The client cannot supply an arbitrary dataset_id; the server
        overrides it with the synthetic source's authoritative value."""
        login(pr05b_client, "reviewer1", PASSWORD)
        headers = _auth_headers(pr05b_client)
        response = pr05b_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "ulb-benchmark",  # spoofed
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "x",
                "created_by": "r1",
            },
            headers=headers,
        )
        assert response.status_code == 201
        body = response.json()
        # The server overrode the spoofed dataset_id.
        assert body["dataset_id"] == "synthetic-demonstration"

    def test_viewer_cannot_create_case(self, pr05b_client, viewer_user):
        login(pr05b_client, "viewer1", PASSWORD)
        headers = _auth_headers(pr05b_client)
        response = pr05b_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "x",
                "created_by": "r1",
            },
            headers=headers,
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"

    def test_admin_can_create_case(self, pr05b_client, admin_user):
        login(pr05b_client, "admin1", PASSWORD)
        headers = _auth_headers(pr05b_client)
        response = pr05b_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "admin-created",
                "created_by": "r1",
            },
            headers=headers,
        )
        assert response.status_code == 201


class TestCaseRead:
    def test_get_case_by_id(self, pr05b_client, reviewer_user):
        login(pr05b_client, "reviewer1", PASSWORD)
        headers = _auth_headers(pr05b_client)
        create = pr05b_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "readable",
                "created_by": "r1",
            },
            headers=headers,
        ).json()
        case_id = create["id"]

        response = pr05b_client.get(f"/api/v1/cases/{case_id}")
        assert response.status_code == 200
        assert response.json()["id"] == case_id

    def test_get_unknown_case_returns_404(self, pr05b_client, reviewer_user):
        login(pr05b_client, "reviewer1", PASSWORD)
        response = pr05b_client.get(
            "/api/v1/cases/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "CASE_NOT_FOUND"

    def test_invalid_uuid_returns_422(self, pr05b_client, reviewer_user):
        login(pr05b_client, "reviewer1", PASSWORD)
        response = pr05b_client.get("/api/v1/cases/not-a-uuid")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_list_cases_paginated(self, pr05b_client, reviewer_user):
        login(pr05b_client, "reviewer1", PASSWORD)
        headers = _auth_headers(pr05b_client)
        # Create 3 cases.
        for i in range(3):
            pr05b_client.post(
                "/api/v1/cases",
                json={
                    "dataset_id": "synthetic-demonstration",
                    "snapshot_id": "synthetic-v1",
                    "record_ref": f"synth-00{i+1}",
                    "title": f"case-{i}",
                    "created_by": "r1",
                },
                headers=headers,
            )
        response = pr05b_client.get("/api/v1/cases?limit=2&offset=0")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 3
        assert len(body["items"]) == 2
        assert body["limit"] == 2
        assert body["offset"] == 0

    def test_list_cases_bounded_limit(self, pr05b_client, reviewer_user):
        login(pr05b_client, "reviewer1", PASSWORD)
        response = pr05b_client.get("/api/v1/cases?limit=999")
        assert response.status_code == 422  # limit max is 100

    def test_case_persists_across_sessions(
        self, pr05b_client, reviewer_user, db_session_factory
    ):
        """The case survives an independent database session (refresh)."""
        login(pr05b_client, "reviewer1", PASSWORD)
        headers = _auth_headers(pr05b_client)
        create = pr05b_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "persistent",
                "created_by": "r1",
            },
            headers=headers,
        ).json()
        case_id = create["id"]

        # Read it back through a fresh request (simulating refresh).
        response = pr05b_client.get(f"/api/v1/cases/{case_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "persistent"

        # Read it directly through an independent session.
        from app.repositories.review_cases import ReviewCaseRepository

        with db_session_factory() as session:
            repo = ReviewCaseRepository(session)
            case = repo.get_case(case_id)
            assert case.title == "persistent"


class TestCaseNotes:
    def test_add_note_persists(self, pr05b_client, reviewer_user):
        login(pr05b_client, "reviewer1", PASSWORD)
        headers = _auth_headers(pr05b_client)
        case = pr05b_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "note-test",
                "created_by": "r1",
            },
            headers=headers,
        ).json()

        response = pr05b_client.post(
            f"/api/v1/cases/{case['id']}/notes",
            json={
                "note_text": "First reviewer note.",
                "actor_ref": "ignored-by-server",
                "expected_version": 1,
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["version"] == 2

    def test_viewer_cannot_add_note(self, pr05b_client, viewer_user, reviewer_user):
        # Create the case as a reviewer first.
        login(pr05b_client, "reviewer1", PASSWORD)
        headers = _auth_headers(pr05b_client)
        case = pr05b_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "viewer-test",
                "created_by": "r1",
            },
            headers=headers,
        ).json()
        # Log out and log in as viewer.
        pr05b_client.post("/api/v1/auth/logout", headers=headers)
        login(pr05b_client, "viewer1", PASSWORD)
        viewer_headers = _auth_headers(pr05b_client)
        response = pr05b_client.post(
            f"/api/v1/cases/{case['id']}/notes",
            json={"note_text": "x", "actor_ref": "v1", "expected_version": 1},
            headers=viewer_headers,
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"


class TestCaseTransitions:
    def test_legal_transition(self, pr05b_client, reviewer_user):
        login(pr05b_client, "reviewer1", PASSWORD)
        headers = _auth_headers(pr05b_client)
        case = pr05b_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "transition-test",
                "created_by": "r1",
            },
            headers=headers,
        ).json()

        response = pr05b_client.post(
            f"/api/v1/cases/{case['id']}/transitions",
            json={
                "to_status": "under_review",
                "reason": "Starting review.",
                "actor_ref": "ignored",
                "expected_version": 1,
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "under_review"
        assert response.json()["version"] == 2

    def test_illegal_transition_rolls_back(self, pr05b_client, reviewer_user):
        """An illegal transition must not bump the version or write an event."""
        login(pr05b_client, "reviewer1", PASSWORD)
        headers = _auth_headers(pr05b_client)
        case = pr05b_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "illegal-test",
                "created_by": "r1",
            },
            headers=headers,
        ).json()

        # not_reviewed → explained_deviation is illegal (must go through under_review).
        response = pr05b_client.post(
            f"/api/v1/cases/{case['id']}/transitions",
            json={
                "to_status": "explained_deviation",
                "reason": "skipping under_review",
                "actor_ref": "r1",
                "expected_version": 1,
            },
            headers=headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_TRANSITION"

        # The case version must NOT have bumped.
        detail = pr05b_client.get(f"/api/v1/cases/{case['id']}").json()
        assert detail["version"] == 1
        assert detail["status"] == "not_reviewed"

        # History must contain only the `created` event.
        history = pr05b_client.get(
            f"/api/v1/cases/{case['id']}/history"
        ).json()
        assert history["total"] == 1
        assert history["items"][0]["event_type"] == "created"


class TestCaseDecisions:
    def test_record_decision_with_status_change(self, pr05b_client, reviewer_user):
        login(pr05b_client, "reviewer1", PASSWORD)
        headers = _auth_headers(pr05b_client)
        case = pr05b_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "decision-test",
                "created_by": "r1",
            },
            headers=headers,
        ).json()
        # Move to under_review first.
        pr05b_client.post(
            f"/api/v1/cases/{case['id']}/transitions",
            json={
                "to_status": "under_review",
                "reason": "starting",
                "actor_ref": "r1",
                "expected_version": 1,
            },
            headers=headers,
        )
        # Record a decision whose outcome is a terminal status.
        response = pr05b_client.post(
            f"/api/v1/cases/{case['id']}/decisions",
            json={
                "outcome": "explained_deviation",
                "rationale": "The deviation is explained by a data-entry correction.",
                "actor_ref": "r1",
                "expected_version": 2,
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "explained_deviation"


class TestCaseHistory:
    def test_history_is_ordered_and_append_only(
        self, pr05b_client, reviewer_user
    ):
        login(pr05b_client, "reviewer1", PASSWORD)
        headers = _auth_headers(pr05b_client)
        case = pr05b_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "history-test",
                "created_by": "r1",
            },
            headers=headers,
        ).json()
        # Add a note.
        pr05b_client.post(
            f"/api/v1/cases/{case['id']}/notes",
            json={"note_text": "note 1", "actor_ref": "r1", "expected_version": 1},
            headers=headers,
        )
        # Transition.
        pr05b_client.post(
            f"/api/v1/cases/{case['id']}/transitions",
            json={
                "to_status": "under_review",
                "reason": "starting",
                "actor_ref": "r1",
                "expected_version": 2,
            },
            headers=headers,
        )

        history = pr05b_client.get(
            f"/api/v1/cases/{case['id']}/history"
        ).json()
        assert history["total"] == 3
        events = history["items"]
        # Deterministic order: case_version ascending then event_seq.
        versions = [e["case_version"] for e in events]
        assert versions == sorted(versions)
        # Event types in order.
        assert events[0]["event_type"] == "created"
        assert events[1]["event_type"] == "note_added"
        assert events[2]["event_type"] == "status_changed"
        # Actor is the principal's UUID (not the client-supplied "r1").
        for e in events:
            assert e["actor_ref"] == reviewer_user.id

    def test_history_survives_refresh(self, pr05b_client, reviewer_user):
        login(pr05b_client, "reviewer1", PASSWORD)
        headers = _auth_headers(pr05b_client)
        case = pr05b_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "refresh-test",
                "created_by": "r1",
            },
            headers=headers,
        ).json()
        pr05b_client.post(
            f"/api/v1/cases/{case['id']}/notes",
            json={"note_text": "persistent note", "actor_ref": "r1", "expected_version": 1},
            headers=headers,
        )

        # Re-fetch history (simulating refresh).
        history = pr05b_client.get(
            f"/api/v1/cases/{case['id']}/history"
        ).json()
        assert history["total"] == 2
        assert history["items"][1]["event_payload"]["note_text"] == "persistent note"


class TestOptimisticConcurrency:
    def test_stale_version_rejected_with_409(
        self, pr05b_client, reviewer_user
    ):
        login(pr05b_client, "reviewer1", PASSWORD)
        headers = _auth_headers(pr05b_client)
        case = pr05b_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "conflict-test",
                "created_by": "r1",
            },
            headers=headers,
        ).json()
        # Bump the version with a note.
        pr05b_client.post(
            f"/api/v1/cases/{case['id']}/notes",
            json={"note_text": "first", "actor_ref": "r1", "expected_version": 1},
            headers=headers,
        )
        # Now attempt a mutation with the stale version 1.
        response = pr05b_client.post(
            f"/api/v1/cases/{case['id']}/notes",
            json={"note_text": "stale", "actor_ref": "r1", "expected_version": 1},
            headers=headers,
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CONFLICT"
        assert response.json()["error"]["details"]["expected_version"] == 1
        # The stale note must NOT have been written.
        history = pr05b_client.get(
            f"/api/v1/cases/{case['id']}/history"
        ).json()
        notes = [e for e in history["items"] if e["event_type"] == "note_added"]
        assert len(notes) == 1
        assert notes[0]["event_payload"]["note_text"] == "first"


class TestCSRFEnforcement:
    def test_missing_csrf_token_rejected(self, pr05b_client, reviewer_user):
        login(pr05b_client, "reviewer1", PASSWORD)
        # No X-CSRF-Token header.
        response = pr05b_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "x",
                "created_by": "r1",
            },
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"

    def test_invalid_csrf_token_rejected(self, pr05b_client, reviewer_user):
        login(pr05b_client, "reviewer1", PASSWORD)
        response = pr05b_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "x",
                "created_by": "r1",
            },
            headers={"X-CSRF-Token": "forged-token"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"


class TestPrincipalAttribution:
    def test_actor_ref_derived_from_principal(self, pr05b_client, reviewer_user):
        """Every event's actor_ref is the principal's user UUID, not the
        client-supplied value."""
        login(pr05b_client, "reviewer1", PASSWORD)
        headers = _auth_headers(pr05b_client)
        case = pr05b_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "attribution-test",
                "created_by": "client-supplied-ignored",
            },
            headers=headers,
        ).json()
        history = pr05b_client.get(
            f"/api/v1/cases/{case['id']}/history"
        ).json()
        created_event = history["items"][0]
        assert created_event["actor_ref"] == reviewer_user.id
        assert created_event["actor_ref"] != "client-supplied-ignored"
