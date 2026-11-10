"""Login endpoint tests (real PostgreSQL + HTTP, PR-04 §9, §16)."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from tests.conftest import get_csrf_token, login

PASSWORD = "correct-horse-battery-staple"


class TestLoginSuccess:
    def test_correct_credentials_return_sanitized_user(self, auth_client, user_factory):
        user = user_factory("alice", PASSWORD, role="reviewer")
        response = login(auth_client, "alice", PASSWORD)
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == user.id
        assert body["username"] == "alice"
        assert body["display_name"] == "Alice"
        assert body["role"] == "reviewer"
        assert "cases:read" in body["permissions"]
        # Sanitized: no hash, no token.
        assert "password_hash" not in body
        assert "token" not in str(body).lower()

    def test_username_normalized_casefold(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        response = login(auth_client, "  ALICE  ", PASSWORD)
        assert response.status_code == 200
        assert response.json()["username"] == "alice"

    def test_login_sets_session_and_csrf_cookies(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        response = login(auth_client, "alice", PASSWORD)
        set_cookies = response.headers.get_list("set-cookie")
        cookie_blob = " ".join(set_cookies).lower()
        assert "peiars_session=" in cookie_blob
        assert "peiars_csrf=" in cookie_blob

    def test_login_updates_last_login_at(self, auth_client, user_factory, db_session_factory):
        user = user_factory("alice", PASSWORD)
        with db_session_factory() as session:
            before = session.execute(
                text("SELECT last_login_at FROM users WHERE id = :id"), {"id": user.id}
            ).scalar_one()
        assert before is None
        login(auth_client, "alice", PASSWORD)
        with db_session_factory() as session:
            after = session.execute(
                text("SELECT last_login_at FROM users WHERE id = :id"), {"id": user.id}
            ).scalar_one()
        assert after is not None

    def test_fresh_session_per_login(self, auth_client, user_factory):
        """Session fixation prevention: each login issues a brand-new session."""
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        first_cookie = auth_client.cookies.get("peiars_session")
        login(auth_client, "alice", PASSWORD)
        second_cookie = auth_client.cookies.get("peiars_session")
        assert first_cookie != second_cookie

    def test_no_token_in_response_json(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        response = login(auth_client, "alice", PASSWORD)
        assert "peiars_session" not in response.text
        cookie_value = auth_client.cookies.get("peiars_session")
        assert cookie_value
        assert cookie_value not in response.text


class TestLoginFailures:
    def test_wrong_password_generic_401(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        response = login(auth_client, "alice", "wrong-password-123")
        assert response.status_code == 401
        body = response.json()
        assert body["error"]["code"] == "UNAUTHORIZED"
        assert body["error"]["message"] == "Invalid username or password."

    def test_unknown_user_same_generic_message(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        known = login(auth_client, "alice", "wrong-password-123")
        unknown = login(auth_client, "nobody-here", "wrong-password-123")
        assert known.status_code == unknown.status_code == 401
        assert (
            known.json()["error"]["message"] == unknown.json()["error"]["message"]
        ), "username enumeration via differing messages"

    def test_unknown_user_creates_no_session(self, auth_client, user_factory, db_session_factory):
        user_factory("alice", PASSWORD)
        login(auth_client, "ghost-user", "wrong-password-123")
        with db_session_factory() as session:
            count = session.execute(text("SELECT count(*) FROM auth_sessions")).scalar_one()
        assert count == 0

    def test_wrong_password_creates_no_session(self, auth_client, user_factory, db_session_factory):
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", "wrong-password-123")
        with db_session_factory() as session:
            count = session.execute(text("SELECT count(*) FROM auth_sessions")).scalar_one()
        assert count == 0

    def test_disabled_user_generic_401_no_session(self, auth_client, user_factory, db_session_factory):
        user_factory("alice", PASSWORD, is_active=False)
        response = login(auth_client, "alice", PASSWORD)
        assert response.status_code == 401
        assert response.json()["error"]["message"] == "Invalid username or password."
        with db_session_factory() as session:
            count = session.execute(text("SELECT count(*) FROM auth_sessions")).scalar_one()
        assert count == 0

    def test_no_cookie_set_on_failure(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        response = login(auth_client, "alice", "wrong-password-123")
        cookie_blob = " ".join(response.headers.get_list("set-cookie")).lower()
        assert "peiars_session=" not in cookie_blob

    def test_invalid_input_422(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        csrf = get_csrf_token(auth_client)
        # Password too short (min 8) → validation error via typed contract.
        response = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "short"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_oversized_password_422(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        csrf = get_csrf_token(auth_client)
        response = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "x" * 129},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 422


class TestLoginRequiresCsrf:
    def test_login_without_csrf_403(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        response = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": PASSWORD},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"


class TestAuthServiceFailClosed:
    def test_login_without_session_secret_503(self, db_url, db_session_factory):
        """No secret configured → auth fails closed with sanitized 503."""
        from fastapi.testclient import TestClient

        from app.core.config import Settings
        from app.db.session import DatabaseSessionFactory
        from app.main import create_app

        settings = Settings(
            _env_file=None,
            environment="test",
            cors_origins=["http://test.example"],
            database_url=db_url,
            database_required=True,
            session_secret=None,
        )
        app = create_app(
            settings=settings,
            db_session_factory_override=DatabaseSessionFactory(
                db_session_factory.kw["bind"], db_session_factory
            ),
        )
        client = TestClient(app)
        response = client.get("/api/v1/auth/csrf")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "SERVICE_NOT_READY"

    def test_login_without_database_503(self, test_settings):
        """DB unconfigured → auth dependencies fail closed."""
        from fastapi.testclient import TestClient

        from app.main import create_app

        app = create_app(settings=test_settings)
        client = TestClient(app)
        response = client.get("/api/v1/auth/csrf")
        assert response.status_code == 503
