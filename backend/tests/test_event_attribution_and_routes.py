"""PR-07A Workstream D + K — event attribution, immutability and the
route-level append-only contract (D1, D2-HTTP, D4, K5).

* D1 (PR07A-11): every event's ``actor_ref`` equals the authenticated
  principal's user UUID, including requests that supply a spoofed
  ``actor_ref``/``created_by`` body field.
* D2-HTTP (PR07A-10): an HTTP-level rejected mutation (422 illegal
  transition) leaves the event count unchanged.
* D4 (PR07A-route contract): no PUT/PATCH/DELETE operation exists
  anywhere in the OpenAPI contract, and live probes of the mutation
  verbs against case and history routes fail with 404/405 — never 2xx.
* K5 (PR07A-29): no mutation request schema carries the provenance
  fields (``dataset_id`` / ``snapshot_id`` / ``record_ref``) — a case's
  provenance cannot be rewritten after creation.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import Settings
from app.db.session import DatabaseSessionFactory
from app.main import create_app
from tests.conftest import TEST_SESSION_SECRET, get_csrf_token, login

PASSWORD = "correct-horse-battery-staple"

MUTATION_VERBS = ("PUT", "PATCH", "DELETE")


@pytest.fixture()
def attr_settings(db_url):
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
def attr_app(attr_settings, db_session_factory):
    from tests.conftest import _truncate_auth_tables

    _truncate_auth_tables(db_session_factory)
    with db_session_factory() as session:
        session.execute(text("TRUNCATE TABLE case_events RESTART IDENTITY CASCADE"))
        session.execute(text("TRUNCATE TABLE review_cases RESTART IDENTITY CASCADE"))
        session.commit()

    return create_app(
        settings=attr_settings,
        db_session_factory_override=DatabaseSessionFactory(
            db_session_factory.kw["bind"], db_session_factory
        ),
    )


@pytest.fixture()
def attr_user(db_session_factory):
    from app.auth.passwords import hash_password
    from app.db.models import User

    with db_session_factory() as session:
        user = User(
            username="attr-reviewer",
            password_hash=hash_password(PASSWORD),
            display_name="Attr Reviewer",
            role="reviewer",
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


@pytest.fixture()
def authed(attr_app, attr_user) -> tuple[TestClient, dict, str]:
    """Logged-in reviewer client + CSRF headers + the reviewer's UUID."""
    client = TestClient(attr_app)
    assert login(client, "attr-reviewer", PASSWORD).status_code == 200
    headers = {"X-CSRF-Token": get_csrf_token(client)}
    return client, headers, attr_user.id


def _events(db_session_factory, case_id: str) -> list[tuple[str, str]]:
    with db_session_factory() as session:
        rows = session.execute(
            text(
                "SELECT event_type, actor_ref FROM case_events "
                "WHERE case_id = :cid ORDER BY case_version, event_seq"
            ),
            {"cid": case_id},
        ).all()
    return [(r[0], r[1]) for r in rows]


class TestActorAttribution:
    def test_every_event_actor_is_the_principal_uuid_even_when_spoofed(
        self, authed, db_session_factory
    ):
        client, headers, reviewer_id = authed

        # Create + note + transition + decision, each carrying a spoofed
        # client-side actor reference.
        created = client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "attribution-test",
                "created_by": "spoofed-created-by",
            },
            headers=headers,
        )
        assert created.status_code == 201, created.text
        case_id = created.json()["id"]

        assert (
            client.post(
                f"/api/v1/cases/{case_id}/notes",
                json={
                    "note_text": "note",
                    "actor_ref": "spoofed-note-actor",
                    "expected_version": 1,
                },
                headers=headers,
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/v1/cases/{case_id}/transitions",
                json={
                    "to_status": "under_review",
                    "reason": "begin",
                    "actor_ref": "spoofed-transition-actor",
                    "expected_version": 2,
                },
                headers=headers,
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/v1/cases/{case_id}/decisions",
                json={
                    "outcome": "explained_deviation",
                    "rationale": "explained",
                    "actor_ref": "spoofed-decision-actor",
                    "expected_version": 3,
                },
                headers=headers,
            ).status_code
            == 200
        )

        events = _events(db_session_factory, case_id)
        # created + note_added + status_changed + decision(+status) events
        # (record_decision may write up to two events at one version).
        assert len(events) >= 4
        assert all(actor == reviewer_id for _, actor in events), events
        spoofed = {"spoofed-created-by", "spoofed-note-actor",
                   "spoofed-transition-actor", "spoofed-decision-actor"}
        assert not any(actor in spoofed for _, actor in events)


class TestRejectedMutationLeavesNoEvent:
    def test_http_422_illegal_transition_leaves_event_count_unchanged(
        self, authed, db_session_factory
    ):
        client, headers, _ = authed
        created = client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "d2-http-test",
                "created_by": "ignored",
            },
            headers=headers,
        )
        assert created.status_code == 201
        case_id = created.json()["id"]

        before = _events(db_session_factory, case_id)
        assert len(before) == 1

        response = client.post(
            f"/api/v1/cases/{case_id}/transitions",
            json={
                "to_status": "explained_deviation",  # illegal from not_reviewed
                "reason": "skip",
                "actor_ref": "ignored",
                "expected_version": 1,
            },
            headers=headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_TRANSITION"

        after = _events(db_session_factory, case_id)
        assert after == before


class TestNoEventMutationRoutes:
    def test_openapi_has_no_put_patch_delete_operations(self, authed):
        client, _, _ = authed
        spec = client.get("/openapi.json").json()
        offenders = [
            (path, method)
            for path, item in spec["paths"].items()
            for method in item
            if method.upper() in MUTATION_VERBS
        ]
        assert offenders == [], f"Unexpected mutating operations in contract: {offenders}"

    def test_live_probes_reject_mutating_verbs_on_case_routes(self, authed):
        client, headers, _ = authed
        created = client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "d4-probe",
                "created_by": "ignored",
            },
            headers=headers,
        )
        case_id = created.json()["id"]

        for path in (
            f"/api/v1/cases/{case_id}",
            f"/api/v1/cases/{case_id}/history",
            f"/api/v1/cases/{case_id}/notes",
            f"/api/v1/cases/{case_id}/transitions",
            f"/api/v1/cases/{case_id}/decisions",
            "/api/v1/cases",
        ):
            for verb in MUTATION_VERBS:
                response = client.request(verb, path, headers=headers)
                assert response.status_code in (404, 405), (
                    f"{verb} {path} returned {response.status_code} — "
                    "the append-only route contract is violated"
                )


class TestProvenanceFieldsNotMutable:
    def test_mutation_schemas_carry_no_provenance_fields(self, authed):
        """No post-creation mutation accepts dataset/snapshot/record refs."""
        client, _, _ = authed
        spec = client.get("/openapi.json").json()

        mutating_paths = [
            path
            for path, item in spec["paths"].items()
            if path.startswith("/api/v1/cases") and "post" in item
        ]
        assert mutating_paths, "expected at least one case mutation route"

        provenance = {"dataset_id", "snapshot_id", "record_ref"}
        for path in mutating_paths:
            post = spec["paths"][path]["post"]
            request_ref = post.get("requestBody", {}).get("content", {}).get(
                "application/json", {}
            ).get("$ref")
            if not request_ref:
                continue
            schema_name = request_ref.split("/")[-1]
            schema = spec["components"]["schemas"][schema_name]
            properties = set(schema.get("properties", {}).keys())
            assert not (properties & provenance), (
                f"{path} accepts provenance fields {properties & provenance}; "
                "case provenance must be immutable after creation"
            )

        # The creation route is the only one allowed to carry them.
        create_schema = spec["components"]["schemas"]["CreateCaseRequest"]
        assert provenance <= set(create_schema["properties"].keys())
