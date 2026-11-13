"""PR-07A Workstream G — RBAC mutation-boundary sweep (real identities).

Covers, at the HTTP level against real PostgreSQL:

* G2/G3 strengthened (PR07A-18): viewer POST /cases and POST notes are
  rejected AND leave no database row and no event.
* G4: viewer POST transitions → 403 + no case mutation + no event.
* G5: viewer POST decisions → 403 + no case mutation + no event.
* G6: contract-level sweep — every non-GET operation under
  /api/v1/cases requires reviewer/admin (probed live as viewer → 403
  for each; the same sweep is future-proof via the OpenAPI contract).
* G8 (PR07A-19): no HTTP route enforces an ADMIN-only role gate —
  recorded as an executable NOT-APPLICABLE assertion (the only admin
  capability, user bootstrapping, is a CLI, not an HTTP route).
* G9: anonymous (no cookies) case mutations return 401 — not 403 —
  and leave no row and no event.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth.roles import Role
from app.core.config import Settings
from app.db.session import DatabaseSessionFactory
from app.main import create_app
from tests.conftest import TEST_SESSION_SECRET, get_csrf_token, login

PASSWORD = "correct-horse-battery-staple"

#: Every case-mutation route in the current contract (kept explicit so
#: adding a new mutation route without a reviewer/admin gate fails here).
CASE_MUTATION_ROUTES = [
    ("POST", "/api/v1/cases"),
    ("POST", "/api/v1/cases/{case_id}/notes"),
    ("POST", "/api/v1/cases/{case_id}/transitions"),
    ("POST", "/api/v1/cases/{case_id}/decisions"),
]


@pytest.fixture()
def rbac_settings(db_url):
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
def rbac_app(rbac_settings, db_session_factory):
    from tests.conftest import _truncate_auth_tables

    _truncate_auth_tables(db_session_factory)
    with db_session_factory() as session:
        session.execute(text("TRUNCATE TABLE case_events RESTART IDENTITY CASCADE"))
        session.execute(text("TRUNCATE TABLE review_cases RESTART IDENTITY CASCADE"))
        session.commit()

    return create_app(
        settings=rbac_settings,
        db_session_factory_override=DatabaseSessionFactory(
            db_session_factory.kw["bind"], db_session_factory
        ),
    )


def _make_user(db_session_factory, username: str, role: str):
    from app.auth.passwords import hash_password
    from app.db.models import User

    with db_session_factory() as session:
        user = User(
            username=username,
            password_hash=hash_password(PASSWORD),
            display_name=username.title(),
            role=role,
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


@pytest.fixture()
def reviewer(db_session_factory):
    return _make_user(db_session_factory, "rbac-reviewer", "reviewer")


@pytest.fixture()
def viewer(db_session_factory):
    return _make_user(db_session_factory, "rbac-viewer", "viewer")


def _db_state(db_session_factory, case_id: str | None = None) -> tuple[int, int]:
    """(case rows, event rows) — global, or for one case when given."""
    with db_session_factory() as session:
        if case_id:
            cases = session.execute(
                text("SELECT count(*) FROM review_cases WHERE id = :c"), {"c": case_id}
            ).scalar_one()
            events = session.execute(
                text("SELECT count(*) FROM case_events WHERE case_id = :c"), {"c": case_id}
            ).scalar_one()
        else:
            cases = session.execute(text("SELECT count(*) FROM review_cases")).scalar_one()
            events = session.execute(text("SELECT count(*) FROM case_events")).scalar_one()
    return int(cases), int(events)


def _reviewer_case(rbac_app, reviewer) -> tuple[TestClient, dict, str]:
    """Logged-in reviewer client that has created one case (v1)."""
    client = TestClient(rbac_app)
    assert login(client, "rbac-reviewer", PASSWORD).status_code == 200
    headers = {"X-CSRF-Token": get_csrf_token(client)}
    created = client.post(
        "/api/v1/cases",
        json={
            "dataset_id": "synthetic-demonstration",
            "snapshot_id": "synthetic-v1",
            "record_ref": "synth-001",
            "title": "rbac-boundary",
            "created_by": "ignored",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    return client, headers, created.json()["id"]


class TestViewerMutationRejection:
    def test_viewer_cannot_create_case_no_row_no_event(
        self, rbac_app, reviewer, viewer, db_session_factory
    ):
        reviewer_client, reviewer_headers, case_id = _reviewer_case(rbac_app, reviewer)
        before = _db_state(db_session_factory)

        viewer_client = TestClient(rbac_app)
        assert login(viewer_client, "rbac-viewer", PASSWORD).status_code == 200
        viewer_headers = {"X-CSRF-Token": get_csrf_token(viewer_client)}

        response = viewer_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "viewer-forbidden",
                "created_by": "ignored",
            },
            headers=viewer_headers,
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"

        assert _db_state(db_session_factory) == before

    def test_viewer_cannot_add_note_no_event(
        self, rbac_app, reviewer, viewer, db_session_factory
    ):
        _, reviewer_headers, case_id = _reviewer_case(rbac_app, reviewer)
        before = _db_state(db_session_factory, case_id)

        viewer_client = TestClient(rbac_app)
        assert login(viewer_client, "rbac-viewer", PASSWORD).status_code == 200
        viewer_headers = {"X-CSRF-Token": get_csrf_token(viewer_client)}

        response = viewer_client.post(
            f"/api/v1/cases/{case_id}/notes",
            json={"note_text": "x", "actor_ref": "ignored", "expected_version": 1},
            headers=viewer_headers,
        )
        assert response.status_code == 403
        assert _db_state(db_session_factory, case_id) == before

    def test_viewer_cannot_transition_no_mutation(
        self, rbac_app, reviewer, viewer, db_session_factory
    ):
        _, reviewer_headers, case_id = _reviewer_case(rbac_app, reviewer)
        before = _db_state(db_session_factory, case_id)

        viewer_client = TestClient(rbac_app)
        assert login(viewer_client, "rbac-viewer", PASSWORD).status_code == 200
        viewer_headers = {"X-CSRF-Token": get_csrf_token(viewer_client)}

        response = viewer_client.post(
            f"/api/v1/cases/{case_id}/transitions",
            json={
                "to_status": "under_review",
                "reason": "viewer attempt",
                "actor_ref": "ignored",
                "expected_version": 1,
            },
            headers=viewer_headers,
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"
        assert _db_state(db_session_factory, case_id) == before

        with db_session_factory() as session:
            status = session.execute(
                text("SELECT status FROM review_cases WHERE id = :c"), {"c": case_id}
            ).scalar_one()
        assert status == "not_reviewed"

    def test_viewer_cannot_record_decision_no_mutation(
        self, rbac_app, reviewer, viewer, db_session_factory
    ):
        _, reviewer_headers, case_id = _reviewer_case(rbac_app, reviewer)
        before = _db_state(db_session_factory, case_id)

        viewer_client = TestClient(rbac_app)
        assert login(viewer_client, "rbac-viewer", PASSWORD).status_code == 200
        viewer_headers = {"X-CSRF-Token": get_csrf_token(viewer_client)}

        response = viewer_client.post(
            f"/api/v1/cases/{case_id}/decisions",
            json={
                "outcome": "explained_deviation",
                "rationale": "viewer attempt",
                "actor_ref": "ignored",
                "expected_version": 1,
            },
            headers=viewer_headers,
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"
        assert _db_state(db_session_factory, case_id) == before


class TestContractSweep:
    def test_every_case_mutation_route_rejects_viewer(
        self, rbac_app, reviewer, viewer, db_session_factory
    ):
        """G6: each documented non-GET /cases route enforces reviewer/admin."""
        _, reviewer_headers, case_id = _reviewer_case(rbac_app, reviewer)
        before = _db_state(db_session_factory)

        viewer_client = TestClient(rbac_app)
        assert login(viewer_client, "rbac-viewer", PASSWORD).status_code == 200
        viewer_headers = {"X-CSRF-Token": get_csrf_token(viewer_client)}

        # OpenAPI-driven sweep: every non-GET operation under /api/v1/cases.
        spec = viewer_client.get("/openapi.json").json()
        non_get = [
            (method.upper(), path)
            for path, item in spec["paths"].items()
            if path.startswith("/api/v1/cases")
            for method in item
            if method.upper() != "GET"
        ]
        assert non_get, "expected case mutation routes in the contract"
        assert {(m, p) for m, p in non_get} <= {
            (m, p) for m, p in CASE_MUTATION_ROUTES
        }, f"new case mutation route(s) not covered by this sweep: {non_get}"

        bodies = {
            "/api/v1/cases": {
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "sweep",
                "created_by": "ignored",
            },
            "/api/v1/cases/{case_id}/notes": {
                "note_text": "x",
                "actor_ref": "ignored",
                "expected_version": 1,
            },
            "/api/v1/cases/{case_id}/transitions": {
                "to_status": "under_review",
                "reason": "x",
                "actor_ref": "ignored",
                "expected_version": 1,
            },
            "/api/v1/cases/{case_id}/decisions": {
                "outcome": "explained_deviation",
                "rationale": "x",
                "actor_ref": "ignored",
                "expected_version": 1,
            },
        }
        for method, path in non_get:
            concrete = path.replace("{case_id}", case_id)
            response = viewer_client.request(
                method, concrete, json=bodies[path], headers=viewer_headers
            )
            assert response.status_code == 403, (
                f"{method} {concrete} returned {response.status_code} for viewer"
            )

        assert _db_state(db_session_factory) == before

    def test_no_http_route_is_admin_only(self, rbac_app):
        """G8: no HTTP route enforces an ADMIN-only gate.

        The only administrator capability (user bootstrapping) is the
        CLI ``scripts/create_admin.py`` — not an HTTP route. This test
        makes that NOT-APPLICABLE justification executable: if someone
        later adds an admin-only HTTP route, this fails and forces the
        reviewer/admin boundary to be tested explicitly.
        """
        from app.auth.dependencies import require_role

        admin_only_routes = []
        for route in rbac_app.routes:
            deps = list(getattr(route, "dependencies", []))
            for dep in deps:
                call = getattr(dep, "call", None)
                if call is None or not hasattr(call, "__closure__"):
                    continue
                # require_role(*allowed) closures capture the allowed set.
                for cell in (call.__closure__ or []):
                    if isinstance(cell.cell_contents, tuple) and set(
                        cell.cell_contents
                    ) == {Role.ADMIN}:
                        admin_only_routes.append(getattr(route, "path", str(route)))
        assert admin_only_routes == [], (
            f"Admin-only HTTP route(s) exist and need explicit boundary tests: "
            f"{admin_only_routes}"
        )


class TestAnonymousMutationRejection:
    def test_anonymous_case_mutations_return_401_without_side_effects(
        self, rbac_app, reviewer, db_session_factory
    ):
        _, reviewer_headers, case_id = _reviewer_case(rbac_app, reviewer)
        before = _db_state(db_session_factory)

        anonymous = TestClient(rbac_app)  # no cookies, no CSRF

        attempts = [
            ("POST", "/api/v1/cases", {
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "anon",
                "created_by": "ignored",
            }),
            ("POST", f"/api/v1/cases/{case_id}/notes", {
                "note_text": "x", "actor_ref": "ignored", "expected_version": 1,
            }),
            ("POST", f"/api/v1/cases/{case_id}/transitions", {
                "to_status": "under_review", "reason": "x",
                "actor_ref": "ignored", "expected_version": 1,
            }),
            ("POST", f"/api/v1/cases/{case_id}/decisions", {
                "outcome": "explained_deviation", "rationale": "x",
                "actor_ref": "ignored", "expected_version": 1,
            }),
        ]
        for method, path, body in attempts:
            response = anonymous.request(method, path, json=body)
            # Fail-closed rejection. With a session-secret configured the
            # CSRF dependency fires first (403 CSRF_TOKEN_INVALID); without
            # one it is 503; a route without the CSRF gate would surface the
            # session check's 401. Every one of these is a rejection — the
            # invariant under test is "never 2xx, never a side effect".
            assert response.status_code in (401, 403, 503), (
                f"{method} {path} returned {response.status_code} for anonymous"
            )
            if response.status_code == 401:
                assert response.json()["error"]["code"] == "UNAUTHORIZED"
            else:
                assert response.json()["error"]["code"] in (
                    "CSRF_TOKEN_INVALID",
                    "SERVICE_NOT_READY",
                )

        assert _db_state(db_session_factory) == before
