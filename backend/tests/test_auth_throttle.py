"""Login-throttling tests (real PostgreSQL, PR-04 §10, AC-04-03)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from tests.conftest import login

PASSWORD = "correct-horse-battery-staple"
WRONG = "wrong-password-attempt"


class TestThrottleLockout:
    def test_threshold_failures_then_429(self, auth_client, user_factory):
        """Default threshold 5: the 6th attempt is locked out."""
        user_factory("alice", PASSWORD)
        for _ in range(5):
            response = login(auth_client, "alice", WRONG)
            assert response.status_code == 401
        response = login(auth_client, "alice", WRONG)
        assert response.status_code == 429
        body = response.json()
        assert body["error"]["code"] == "RATE_LIMITED"
        # Generic message; no username confirmation.
        assert "alice" not in body["error"]["message"].lower()

    def test_lockout_applies_even_with_correct_password(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        for _ in range(5):
            login(auth_client, "alice", WRONG)
        # Correct credentials are also refused while locked (fail closed).
        response = login(auth_client, "alice", PASSWORD)
        assert response.status_code == 429

    def test_lockout_isolated_per_username(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        user_factory("bob", PASSWORD)
        for _ in range(5):
            login(auth_client, "alice", WRONG)
        assert login(auth_client, "bob", PASSWORD).status_code == 200

    def test_success_resets_window(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        for _ in range(4):
            login(auth_client, "alice", WRONG)
        assert login(auth_client, "alice", PASSWORD).status_code == 200
        # The counter restarted: four more failures are still allowed.
        for _ in range(4):
            assert login(auth_client, "alice", WRONG).status_code == 401

    def test_unknown_username_also_throttled(self, auth_client, user_factory):
        """Failures for nonexistent users count, blocking brute-force probing."""
        for _ in range(5):
            login(auth_client, "ghost-user", WRONG)
        response = login(auth_client, "ghost-user", WRONG)
        assert response.status_code == 429

    def test_expired_lock_allows_retry(self, auth_client, user_factory, db_session_factory):
        user_factory("alice", PASSWORD)
        for _ in range(5):
            login(auth_client, "alice", WRONG)
        assert login(auth_client, "alice", WRONG).status_code == 429

        # Expire the lock window (simulated elapsed time).
        with db_session_factory() as session:
            session.execute(text(
                "UPDATE login_throttles SET locked_until = now() - interval '1 minute'"
            ))
            session.commit()

        # The window reset: a fresh attempt is evaluated normally.
        response = login(auth_client, "alice", WRONG)
        assert response.status_code == 401  # not 429

    def test_throttle_row_cleared_on_success(self, auth_client, user_factory, db_session_factory):
        user_factory("alice", PASSWORD)
        for _ in range(3):
            login(auth_client, "alice", WRONG)
        with db_session_factory() as session:
            count = session.execute(
                text("SELECT count(*) FROM login_throttles")
            ).scalar_one()
        assert count == 1
        login(auth_client, "alice", PASSWORD)
        with db_session_factory() as session:
            count = session.execute(
                text("SELECT count(*) FROM login_throttles")
            ).scalar_one()
        assert count == 0


class TestThrottlePersistence:
    def test_throttle_is_database_backed(self, auth_client, user_factory, db_session_factory):
        """The counter lives in PostgreSQL (multi-worker visible), not memory."""
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", WRONG)
        with db_session_factory() as session:
            row = session.execute(
                text("SELECT key, failed_count FROM login_throttles")
            ).fetchone()
        assert row is not None
        assert row[0] == "alice"
        assert row[1] == 1


class TestThrottleSettings:
    def test_lockout_threshold_configurable(self, db_url, db_session_factory, user_factory):
        """A tighter threshold fails closed earlier."""
        from fastapi.testclient import TestClient

        from app.core.config import Settings
        from app.db.session import DatabaseSessionFactory
        from app.main import create_app
        from tests.conftest import TEST_SESSION_SECRET

        user_factory("carol", PASSWORD)
        settings = Settings(
            _env_file=None,
            environment="test",
            cors_origins=["http://test.example"],
            database_url=db_url,
            database_required=True,
            session_secret=TEST_SESSION_SECRET,
            session_cookie_secure=False,
            auth_lockout_threshold=2,
            auth_lockout_minutes=5,
        )
        app = create_app(
            settings=settings,
            db_session_factory_override=DatabaseSessionFactory(
                db_session_factory.kw["bind"], db_session_factory
            ),
        )
        client = TestClient(app)
        assert login(client, "carol", WRONG).status_code == 401
        assert login(client, "carol", WRONG).status_code == 401
        assert login(client, "carol", WRONG).status_code == 429
