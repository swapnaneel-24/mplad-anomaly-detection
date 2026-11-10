"""Cookie security-attribute tests (PR-04 §7, AC-04-05)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.session import DatabaseSessionFactory
from app.main import create_app

from tests.conftest import TEST_SESSION_SECRET, get_csrf_token, login

PASSWORD = "correct-horse-battery-staple"


def _cookie_attributes(response, name: str) -> str:
    """Return the raw Set-Cookie header value for ``name`` (lowercased)."""
    for header in response.headers.get_list("set-cookie"):
        if header.lower().startswith(f"{name}="):
            return header.lower()
    raise AssertionError(f"cookie {name!r} not set")


class TestProductionCookiePolicy:
    def _prod_app(self, db_url, db_session_factory):
        settings = Settings(
            _env_file=None,
            environment="production",
            cors_origins=["http://test.example"],
            database_url=db_url,
            database_required=True,
            session_secret=TEST_SESSION_SECRET,
            session_cookie_secure=True,  # production default
        )
        return create_app(
            settings=settings,
            db_session_factory_override=DatabaseSessionFactory(
                db_session_factory.kw["bind"], db_session_factory
            ),
        )

    def _prod_login_response(self, client, username, password):
        """Drive login over plain HTTP by passing the CSRF cookie per request.

        httpx's cookie jar honours the Secure attribute (it will not resend
        Secure cookies over http), which is exactly the browser behaviour we
        want — so the CSRF cookie is attached explicitly to the request
        instead of via the jar, and the Set-Cookie attributes on the login
        response are inspected directly.
        """
        csrf_response = client.get("/api/v1/auth/csrf")
        token = csrf_response.json()["csrf_token"]
        return client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
            headers={"X-CSRF-Token": token},
            cookies={"peiars_csrf": token},
        )

    def test_session_cookie_secure_httponly_samesite_path(
        self, db_url, db_session_factory, user_factory
    ):
        user_factory("alice", PASSWORD)
        app = self._prod_app(db_url, db_session_factory)
        client = TestClient(app)
        response = self._prod_login_response(client, "alice", PASSWORD)
        assert response.status_code == 200, response.text
        attrs = _cookie_attributes(response, "peiars_session")
        assert "secure" in attrs
        assert "httponly" in attrs
        assert "samesite=lax" in attrs
        assert "path=/" in attrs
        # No Domain attribute (host-only cookie).
        assert "domain=" not in attrs

    def test_csrf_cookie_readable_not_httponly(
        self, db_url, db_session_factory, user_factory
    ):
        user_factory("alice", PASSWORD)
        app = self._prod_app(db_url, db_session_factory)
        client = TestClient(app)
        response = client.get("/api/v1/auth/csrf")
        attrs = _cookie_attributes(response, "peiars_csrf")
        assert "httponly" not in attrs  # JS must read it for double-submit
        assert "secure" in attrs
        assert "samesite=lax" in attrs
        assert "path=/" in attrs

    def test_production_defaults_do_not_permit_insecure_cookies(self):
        """The typed default is Secure=True; nothing silently relaxes it."""
        settings = Settings(
            _env_file=None,
            environment="production",
            session_secret=TEST_SESSION_SECRET,
        )
        assert settings.session_cookie_secure is True


class TestDevelopmentCookiePolicy:
    def test_dev_relaxation_is_explicit(self, auth_client, user_factory):
        """The documented local-HTTP development relaxation (Secure off)."""
        user_factory("alice", PASSWORD)
        response = login(auth_client, "alice", PASSWORD)
        attrs = _cookie_attributes(response, "peiars_session")
        assert "secure" not in attrs
        # The other protections remain.
        assert "httponly" in attrs
        assert "samesite=lax" in attrs


class TestCookieLifetime:
    def test_cookie_max_age_matches_session_ttl(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        response = login(auth_client, "alice", PASSWORD)
        attrs = _cookie_attributes(response, "peiars_session")
        # session_ttl_minutes default = 480 → 28800 seconds.
        assert "max-age=28800" in attrs

    def test_logout_expires_cookies(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        csrf = get_csrf_token(auth_client)
        response = auth_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
        attrs = _cookie_attributes(response, "peiars_session")
        csrf_attrs = _cookie_attributes(response, "peiars_csrf")
        assert "max-age=0" in attrs
        assert "max-age=0" in csrf_attrs


class TestNoTokenLeakage:
    def test_session_token_never_in_json(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        token = auth_client.cookies.get("peiars_session")
        assert token
        for response in (
            auth_client.get("/api/v1/auth/me"),
            auth_client.get("/api/v1/meta"),
            auth_client.get("/openapi.json"),
        ):
            assert token not in response.text

    def test_csrf_token_not_a_credential_in_json(self, auth_client):
        """The CSRF token is returned by design (double-submit) and is not
        an authentication credential — documented behaviour."""
        response = auth_client.get("/api/v1/auth/csrf")
        assert response.status_code == 200
        assert "csrf_token" in response.json()
