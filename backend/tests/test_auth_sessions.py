"""Session lifecycle tests (real PostgreSQL + HTTP, PR-04 §6, §16)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from tests.conftest import get_csrf_token, login

PASSWORD = "correct-horse-battery-staple"


def _me(client):
    return client.get("/api/v1/auth/me")


class TestValidSessions:
    def test_valid_session_accesses_me(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        response = _me(auth_client)
        assert response.status_code == 200
        assert response.json()["username"] == "alice"

    def test_me_returns_sanitized_fields(self, auth_client, user_factory):
        user = user_factory("alice", PASSWORD, role="admin")
        login(auth_client, "alice", PASSWORD)
        body = _me(auth_client).json()
        assert set(body) == {"id", "username", "display_name", "role", "permissions"}
        assert body["id"] == user.id
        assert body["role"] == "admin"
        assert "admin:users" in body["permissions"]
        assert "password_hash" not in body


class TestInvalidSessions:
    def test_missing_session_401(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)  # nobody logged in
        response = _me(auth_client)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"

    def test_malformed_session_token_401(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        auth_client.cookies.set("peiars_session", "totally-bogus-token")
        response = _me(auth_client)
        assert response.status_code == 401

    def test_expired_session_401(self, auth_client, user_factory, db_session_factory):
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        token_hash_row = _single_session(auth_client, db_session_factory)
        with db_session_factory() as session:
            session.execute(text(
                "UPDATE auth_sessions SET expires_at = now() - interval '1 minute' "
                "WHERE token_hash = :th"
            ), {"th": token_hash_row})
            session.commit()
        assert _me(auth_client).status_code == 401

    def test_revoked_session_401(self, auth_client, user_factory, db_session_factory):
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        token_hash_row = _single_session(auth_client, db_session_factory)
        with db_session_factory() as session:
            session.execute(text(
                "UPDATE auth_sessions SET revoked_at = now() WHERE token_hash = :th"
            ), {"th": token_hash_row})
            session.commit()
        assert _me(auth_client).status_code == 401

    def test_idle_timeout_401(self, auth_client, user_factory, db_session_factory):
        """Server-side inactivity expiration (last_seen_at too old)."""
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        token_hash_row = _single_session(auth_client, db_session_factory)
        with db_session_factory() as session:
            session.execute(text(
                "UPDATE auth_sessions SET last_seen_at = now() - interval '600 minutes' "
                "WHERE token_hash = :th"
            ), {"th": token_hash_row})
            session.commit()
        assert _me(auth_client).status_code == 401

    def test_absolute_expiry_enforced_even_with_valid_cookie(
        self, auth_client, user_factory, db_session_factory
    ):
        """The cookie alone proves nothing: expired server state wins."""
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        token_hash_row = _single_session(auth_client, db_session_factory)
        with db_session_factory() as session:
            session.execute(text(
                "UPDATE auth_sessions SET expires_at = now() - interval '1 second' "
                "WHERE token_hash = :th"
            ), {"th": token_hash_row})
            session.commit()
        assert auth_client.cookies.get("peiars_session") is not None
        assert _me(auth_client).status_code == 401

    def test_disabled_user_with_valid_session_401(
        self, auth_client, user_factory, db_session_factory
    ):
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        with db_session_factory() as session:
            session.execute(text("UPDATE users SET is_active = false"))
            session.commit()
        assert _me(auth_client).status_code == 401


class TestLogout:
    def test_logout_revokes_and_expires_cookie(self, auth_client, user_factory, db_session_factory):
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        token_hash_row = _single_session(auth_client, db_session_factory)

        csrf = get_csrf_token(auth_client)
        response = auth_client.post(
            "/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "logged_out"

        # Cookie expired in the browser.
        cookie_blob = " ".join(response.headers.get_list("set-cookie")).lower()
        assert "max-age=0" in cookie_blob

        # Session revoked server-side.
        with db_session_factory() as session:
            revoked = session.execute(text(
                "SELECT revoked_at FROM auth_sessions WHERE token_hash = :th"
            ), {"th": token_hash_row}).scalar_one()
        assert revoked is not None

    def test_logout_replay_fails(self, auth_client, user_factory):
        """Replay of the old (expired) session cookie cannot authenticate."""
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        old_cookie = auth_client.cookies.get("peiars_session")

        csrf = get_csrf_token(auth_client)
        auth_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})

        # Replay: restore the old cookie.
        auth_client.cookies.set("peiars_session", old_cookie)
        assert _me(auth_client).status_code == 401

    def test_logout_requires_authentication(self, auth_client):
        csrf = get_csrf_token(auth_client)
        response = auth_client.post(
            "/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}
        )
        assert response.status_code == 401

    def test_logout_requires_csrf(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        response = auth_client.post("/api/v1/auth/logout")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"

    def test_logout_idempotent_for_expired_session(self, auth_client, user_factory, db_session_factory):
        """Predictable behaviour: an expired session is simply gone."""
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        token_hash_row = _single_session(auth_client, db_session_factory)
        with db_session_factory() as session:
            session.execute(text(
                "UPDATE auth_sessions SET expires_at = now() - interval '1 hour' "
                "WHERE token_hash = :th"
            ), {"th": token_hash_row})
            session.commit()
        # /me fails, logout (unauthenticated) 401s predictably.
        assert _me(auth_client).status_code == 401
        csrf = get_csrf_token(auth_client)
        response = auth_client.post(
            "/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}
        )
        assert response.status_code == 401


class TestSessionReplacement:
    def test_second_login_creates_second_session(self, auth_client, user_factory, db_session_factory):
        """Multi-session is allowed; each login is a fresh session."""
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        with db_session_factory() as session:
            count = session.execute(
                text("SELECT count(*) FROM auth_sessions")
            ).scalar_one()
        assert count == 2

    def test_role_change_reflected_immediately(
        self, auth_client, user_factory, db_session_factory
    ):
        """Session validity reflects role changes without invalidation."""
        user_factory("alice", PASSWORD, role="viewer")
        login(auth_client, "alice", PASSWORD)
        body = _me(auth_client).json()
        assert body["role"] == "viewer"
        assert "cases:write" not in body["permissions"]

        with db_session_factory() as session:
            session.execute(text("UPDATE users SET role = 'reviewer'"))
            session.commit()

        body = _me(auth_client).json()
        assert body["role"] == "reviewer"
        assert "cases:write" in body["permissions"]


class TestSessionStorageProperties:
    def test_only_hash_stored_never_raw_token(self, auth_client, user_factory, db_session_factory):
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        raw_token = auth_client.cookies.get("peiars_session")
        with db_session_factory() as session:
            stored = session.execute(text("SELECT token_hash FROM auth_sessions")).scalar_one()
        assert stored != raw_token
        assert raw_token not in stored
        # Stored value is the SHA-256 verifier.
        import hashlib

        assert stored == hashlib.sha256(raw_token.encode()).hexdigest()

    def test_no_token_in_logs(self, auth_client, user_factory, caplog):
        import logging

        user_factory("alice", PASSWORD)
        with caplog.at_level(logging.INFO):
            login(auth_client, "alice", PASSWORD)
            _me(auth_client)
        raw_token = auth_client.cookies.get("peiars_session")
        for record in caplog.records:
            assert raw_token not in record.getMessage()
            assert raw_token not in str(record.__dict__)


def _single_session(client, db_session_factory) -> str:
    """Return the token_hash of the single session row (test helper)."""
    del client  # the session row exists regardless of the client
    with db_session_factory() as session:
        return session.execute(text("SELECT token_hash FROM auth_sessions")).scalar_one()
