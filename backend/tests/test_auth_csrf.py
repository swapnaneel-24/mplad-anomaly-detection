"""CSRF protection tests (PR-04 §8, §16, AC-04-06)."""

from __future__ import annotations

from tests.conftest import get_csrf_token, login

PASSWORD = "correct-horse-battery-staple"


class TestCsrfBootstrap:
    def test_csrf_endpoint_sets_cookie_and_returns_token(self, auth_client):
        response = auth_client.get("/api/v1/auth/csrf")
        assert response.status_code == 200
        token = response.json()["csrf_token"]
        assert token
        assert auth_client.cookies.get("peiars_csrf") == token

    def test_csrf_token_is_signed(self, auth_client):
        """The token carries the HMAC signature (contains a colon)."""
        token = get_csrf_token(auth_client)
        assert ":" in token


class TestMissingOrIncorrectTokens:
    def test_missing_header_403(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        auth_client.get("/api/v1/auth/csrf")  # cookie set, header omitted
        response = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": PASSWORD},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"

    def test_missing_cookie_403(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        token = get_csrf_token(auth_client)
        auth_client.cookies.delete("peiars_csrf")
        response = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": PASSWORD},
            headers={"X-CSRF-Token": token},
        )
        assert response.status_code == 403

    def test_incorrect_header_403(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        get_csrf_token(auth_client)
        response = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": PASSWORD},
            headers={"X-CSRF-Token": "forged:deadbeef"},
        )
        assert response.status_code == 403

    def test_header_cookie_mismatch_403(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        good = get_csrf_token(auth_client)
        other = get_csrf_token(auth_client)  # rotates the cookie
        # Header carries the OLD token while the cookie holds the new one.
        response = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": PASSWORD},
            headers={"X-CSRF-Token": good},
        )
        assert good != other
        assert response.status_code == 403

    def test_unsigned_value_rejected(self, auth_client, user_factory):
        """A random value without a valid signature fails even if echoed."""
        import secrets

        user_factory("alice", PASSWORD)
        forged = secrets.token_urlsafe(32)
        auth_client.cookies.set("peiars_csrf", forged)
        response = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": PASSWORD},
            headers={"X-CSRF-Token": forged},
        )
        assert response.status_code == 403


class TestCorrectToken:
    def test_correct_token_passes_login(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        response = login(auth_client, "alice", PASSWORD)
        assert response.status_code == 200

    def test_correct_token_passes_logout(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        csrf = get_csrf_token(auth_client)
        response = auth_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
        assert response.status_code == 200

    def test_get_requests_exempt(self, auth_client, user_factory):
        """Safe methods need no CSRF token (documented exemption)."""
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        auth_client.cookies.delete("peiars_csrf")
        assert auth_client.get("/api/v1/auth/me").status_code == 200
        assert auth_client.get("/api/v1/health/live").status_code == 200


class TestOriginValidation:
    def test_cross_origin_rejected(self, auth_client, user_factory):
        """An Origin from a non-approved origin is rejected (defence in depth)."""
        user_factory("alice", PASSWORD)
        token = get_csrf_token(auth_client)
        response = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": PASSWORD},
            headers={"X-CSRF-Token": token, "Origin": "http://evil.example"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"

    def test_same_origin_allowed(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        token = get_csrf_token(auth_client)
        base = str(auth_client.base_url).rstrip("/")
        response = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": PASSWORD},
            headers={"X-CSRF-Token": token, "Origin": base},
        )
        assert response.status_code == 200

    def test_approved_cors_origin_allowed(self, auth_client, user_factory):
        """The configured dev origin (http://test.example) passes."""
        user_factory("alice", PASSWORD)
        token = get_csrf_token(auth_client)
        response = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": PASSWORD},
            headers={"X-CSRF-Token": token, "Origin": "http://test.example"},
        )
        assert response.status_code == 200


class TestNoBypass:
    def test_no_global_csrf_bypass(self, auth_client, user_factory):
        """CSRF cannot be disabled by any header/flag — only by test fixtures
        that construct separate apps (documented)."""
        user_factory("alice", PASSWORD)
        get_csrf_token(auth_client)
        response = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": PASSWORD},
            headers={"X-CSRF-Bypass": "true", "X-Test-Mode": "1"},
        )
        assert response.status_code == 403

    def test_unknown_post_routes_still_404(self, client):
        """CSRF is a route dependency, so unknown routes keep the 404 contract
        (no global middleware intercepting unmatched paths)."""
        response = client.post("/api/v1/nonexistent", json={})
        assert response.status_code == 404

    def test_case_mutation_routes_require_csrf(self, auth_client, user_factory):
        """PR-05B case mutation routes exist and enforce CSRF.

        Without a valid X-CSRF-Token header, every state-changing case
        endpoint must reject with 403 CSRF_TOKEN_INVALID (not 404, not
        201). This replaces the PR-03 assertion that the routes did not
        exist.
        """
        user_factory("alice", PASSWORD, role="reviewer")
        login(auth_client, "alice", PASSWORD)
        # Do NOT fetch / set the CSRF header — the request must be rejected.
        for path, body in (
            ("/api/v1/cases", {
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "t",
                "created_by": "alice",
            }),
            ("/api/v1/cases/00000000-0000-0000-0000-000000000000/notes", {
                "note_text": "x", "actor_ref": "alice", "expected_version": 1,
            }),
            ("/api/v1/cases/00000000-0000-0000-0000-000000000000/decisions", {
                "outcome": "explained_deviation", "rationale": "x",
                "actor_ref": "alice", "expected_version": 1,
            }),
        ):
            response = auth_client.post(path, json=body)
            assert response.status_code == 403, path
            assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"
