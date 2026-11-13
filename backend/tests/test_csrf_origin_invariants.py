"""PR-07A Workstream H + F — CSRF/Origin invariants and session-expiry
boundary (H4, H5, H7, F1-boundary).

* H4 (PR07A-20 extension): a pre-login CSRF token cannot be replayed
  after login rotates it — but the fresh post-login token works.
* H5 (PR07A-21): an otherwise fully authenticated case mutation with a
  disallowed Origin is rejected.
* H7 (PR07A-20/21): every rejection above leaves the database
  byte-identical (no case row, no event) — verified before/after.
* F1-boundary (PR07A-14): a session whose ``expires_at`` equals the
  current time is rejected (boundary-inclusive expiry).
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
CSRF_COOKIE = "peiars_csrf"


@pytest.fixture()
def csrf_settings(db_url):
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
def csrf_app(csrf_settings, db_session_factory):
    from tests.conftest import _truncate_auth_tables

    _truncate_auth_tables(db_session_factory)
    with db_session_factory() as session:
        session.execute(text("TRUNCATE TABLE case_events RESTART IDENTITY CASCADE"))
        session.execute(text("TRUNCATE TABLE review_cases RESTART IDENTITY CASCADE"))
        session.commit()

    return create_app(
        settings=csrf_settings,
        db_session_factory_override=DatabaseSessionFactory(
            db_session_factory.kw["bind"], db_session_factory
        ),
    )


@pytest.fixture()
def csrf_user(db_session_factory):
    from app.auth.passwords import hash_password
    from app.db.models import User

    with db_session_factory() as session:
        user = User(
            username="csrf-reviewer",
            password_hash=hash_password(PASSWORD),
            display_name="Csrf Reviewer",
            role="reviewer",
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def _db_state(db_session_factory) -> tuple[int, int]:
    with db_session_factory() as session:
        cases = session.execute(text("SELECT count(*) FROM review_cases")).scalar_one()
        events = session.execute(text("SELECT count(*) FROM case_events")).scalar_one()
    return int(cases), int(events)


def _case_body() -> dict:
    return {
        "dataset_id": "synthetic-demonstration",
        "snapshot_id": "synthetic-v1",
        "record_ref": "synth-001",
        "title": "csrf-invariants",
        "created_by": "ignored",
    }


class TestCsrfRotationReplay:
    def test_pre_login_token_rejected_after_rotation_fresh_token_accepted(
        self, csrf_app, csrf_user, db_session_factory
    ):
        """H4 + H7: replayed pre-login token → 403 + no mutation."""
        client = TestClient(csrf_app)

        # Bootstrap a pre-login token (T1).
        t1 = get_csrf_token(client)

        # Login with T1 — the response rotates the CSRF cookie (T2).
        assert login(client, "csrf-reviewer", PASSWORD, csrf=t1).status_code == 200
        t2 = client.cookies.get(CSRF_COOKIE)
        assert t2 is not None and t2 != t1, "login must rotate the CSRF token"

        before = _db_state(db_session_factory)

        # Replay the pre-login token T1 after rotation → 403, no case.
        replay = client.post("/api/v1/cases", json=_case_body(),
                             headers={"X-CSRF-Token": t1})
        assert replay.status_code == 403
        assert replay.json()["error"]["code"] == "CSRF_TOKEN_INVALID"
        assert _db_state(db_session_factory) == before

        # The fresh post-login token T2 is accepted.
        fresh = client.post("/api/v1/cases", json=_case_body(),
                            headers={"X-CSRF-Token": t2})
        assert fresh.status_code == 201, fresh.text
        cases, events = _db_state(db_session_factory)
        assert cases == 1 and events == 1


class TestAuthenticatedCrossOrigin:
    def test_valid_session_valid_csrf_bad_origin_rejected_no_mutation(
        self, csrf_app, csrf_user, db_session_factory
    ):
        """H5 + H7: authenticated mutation with a disallowed Origin."""
        client = TestClient(csrf_app)
        assert login(client, "csrf-reviewer", PASSWORD).status_code == 200
        token = client.cookies.get(CSRF_COOKIE)
        assert token is not None

        before = _db_state(db_session_factory)

        response = client.post(
            "/api/v1/cases",
            json=_case_body(),
            headers={"X-CSRF-Token": token, "Origin": "http://evil.example"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"
        assert _db_state(db_session_factory) == before

        # The same request with an allowed Origin succeeds (control).
        control = client.post(
            "/api/v1/cases",
            json=_case_body(),
            headers={"X-CSRF-Token": token, "Origin": "http://test.example"},
        )
        assert control.status_code == 201, control.text
        cases, events = _db_state(db_session_factory)
        assert cases == 1 and events == 1


class TestSessionExpiryBoundary:
    def test_expires_at_equal_to_now_is_rejected(
        self, csrf_app, csrf_user, db_session_factory
    ):
        """F1 boundary: expires_at == now() (not only < now()) rejects."""
        client = TestClient(csrf_app)
        assert login(client, "csrf-reviewer", PASSWORD).status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 200

        with db_session_factory() as session:
            row = session.execute(text("SELECT token_hash FROM auth_sessions")).scalar_one()
            session.execute(
                text("UPDATE auth_sessions SET expires_at = now() WHERE token_hash = :th"),
                {"th": row},
            )
            session.commit()

        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"
