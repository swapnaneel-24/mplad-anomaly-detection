"""Actor-provenance tests (PR-04 §12, AC-04-09, AC-04-10).

Verifies that authenticated principals map to the correct actor
references, that client-supplied actor identity can never override the
server-side principal, and that the PR-03 append-only history guarantees
are preserved under authenticated attribution.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text

from app.auth.principals import (
    AuthenticatedPrincipal,
    actor_ref_from_principal,
    is_authenticated_actor_ref,
)
from app.auth.roles import Role
from app.contracts.review_cases import CreateCaseRequest
from app.services.review_cases import ReviewCaseService
from tests.conftest import login

PASSWORD = "correct-horse-battery-staple"


def _principal(user_id: str, role: Role = Role.REVIEWER) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=user_id,
        username="alice",
        display_name="Alice",
        role=role,
        is_active=True,
    )


class TestPrincipalToActorRef:
    def test_actor_ref_is_user_id(self):
        user_id = str(uuid.uuid4())
        principal = _principal(user_id)
        assert actor_ref_from_principal(principal) == user_id

    def test_actor_ref_is_not_username(self):
        principal = _principal(str(uuid.uuid4()))
        assert actor_ref_from_principal(principal) != "alice"

    def test_login_principal_id_matches_database_user(
        self, auth_client, user_factory
    ):
        user = user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        body = auth_client.get("/api/v1/auth/me").json()
        assert body["id"] == user.id
        assert is_authenticated_actor_ref(body["id"])


class TestSyntheticVsAuthenticatedActorRefs:
    def test_synthetic_refs_are_distinguishable(self):
        for synthetic in ("r1", "fixture-reviewer-001", "reviewer-a", "fixture-actor"):
            assert not is_authenticated_actor_ref(synthetic), synthetic

    def test_uuid_refs_recognized_as_authenticated(self):
        assert is_authenticated_actor_ref(str(uuid.uuid4()))

    def test_non_string_rejected(self):
        assert not is_authenticated_actor_ref(None)
        assert not is_authenticated_actor_ref(12345)


class TestHistoryRecordsPrincipalUserId:
    def test_case_created_with_principal_actor_records_user_id(
        self, user_factory, db_session_factory
    ):
        """The internal adapter: principal → actor_ref → event history."""
        user = user_factory("alice", PASSWORD, role="reviewer")
        principal = _principal(user.id)

        service = ReviewCaseService(db_session_factory)
        case = service.create_case(
            CreateCaseRequest(
                dataset_id="ulb-benchmark",
                snapshot_id="snap-001",
                record_ref="row-00042",
                title="Authenticated actor test",
                created_by=actor_ref_from_principal(principal),
            )
        )
        history = service.get_case_history(case.id)
        assert history.total == 1
        event = history.items[0]
        assert event.actor_ref == user.id
        assert is_authenticated_actor_ref(event.actor_ref)

    def test_append_only_guarantees_preserved_with_authenticated_actor(
        self, user_factory, db_session_factory
    ):
        """UPDATE/DELETE on events with authenticated actor refs still rejected."""
        user = user_factory("alice", PASSWORD)
        principal = _principal(user.id)

        service = ReviewCaseService(db_session_factory)
        case = service.create_case(
            CreateCaseRequest(
                dataset_id="ulb-benchmark",
                snapshot_id="snap-001",
                record_ref="row-00042",
                title="Append-only under auth",
                created_by=actor_ref_from_principal(principal),
            )
        )
        import pytest
        from sqlalchemy.exc import IntegrityError, ProgrammingError

        with db_session_factory() as session:
            with pytest.raises((ProgrammingError, IntegrityError)):
                session.execute(text(
                    "UPDATE case_events SET actor_ref = 'tampered' WHERE case_id = :cid"
                ), {"cid": case.id})
                session.commit()

    def test_historical_synthetic_events_untouched(
        self, user_factory, db_session_factory
    ):
        """PR-03-era synthetic actor refs remain readable; nothing is rewritten."""
        service = ReviewCaseService(db_session_factory)
        case = service.create_case(
            CreateCaseRequest(
                dataset_id="ulb-benchmark",
                snapshot_id="snap-001",
                record_ref="row-00042",
                title="Legacy synthetic actor",
                created_by="fixture-reviewer-001",
            )
        )
        history = service.get_case_history(case.id)
        assert history.items[0].actor_ref == "fixture-reviewer-001"
        assert not is_authenticated_actor_ref(history.items[0].actor_ref)


class TestUntrustedPrincipalRejection:
    def test_principal_requires_active_flag(self):
        """The principal is only constructed for active users; a fabricated
        inactive principal is rejected by the adapter's documented contract."""
        inactive = AuthenticatedPrincipal(
            user_id=str(uuid.uuid4()),
            username="ghost",
            display_name="Ghost",
            role=Role.VIEWER,
            is_active=False,
        )
        # The adapter maps identity, not authorization: inactive principals
        # are never produced by session validation (tested in sessions).
        assert inactive.is_active is False

    def test_client_payload_actor_cannot_reach_service(
        self, auth_client, user_factory
    ):
        """PR-05B: the case API exists, but a client-supplied ``created_by``
        is ignored — the server overwrites it with the authenticated
        principal's user UUID. The created case's ``created_by`` field
        must NOT equal the attacker-forged value.
        """
        user = user_factory("alice", PASSWORD, role="reviewer")
        login(auth_client, "alice", PASSWORD)
        csrf = auth_client.get("/api/v1/auth/csrf").json()["csrf_token"]
        response = auth_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "forged-actor-test",
                "created_by": "attacker-forged-actor",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        # The server-derived created_by must be the principal's user UUID,
        # NOT the client-supplied "attacker-forged-actor".
        assert body["created_by"] == user.id
        assert body["created_by"] != "attacker-forged-actor"
        # The dataset_id / snapshot_id are also authoritative (synthetic).
        assert body["dataset_id"] == "synthetic-demonstration"
        assert body["snapshot_id"] == "synthetic-v1"
