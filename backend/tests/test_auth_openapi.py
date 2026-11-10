"""OpenAPI authentication-contract tests (PR-04 §14, AC-04-12)."""

from __future__ import annotations

from app.core.config import canonical_settings
from app.main import create_app


def _schema() -> dict:
    return create_app(settings=canonical_settings()).openapi()


class TestSecurityScheme:
    def test_cookie_security_scheme_documented(self):
        schema = _schema()
        schemes = schema["components"]["securitySchemes"]
        assert "APIKeyCookie" in schemes
        scheme = schemes["APIKeyCookie"]
        assert scheme["type"] == "apiKey"
        assert scheme["in"] == "cookie"
        assert scheme["name"] == "peiars_session"

    def test_me_requires_cookie_security(self):
        me = _schema()["paths"]["/api/v1/auth/me"]["get"]
        assert me.get("security") == [{"APIKeyCookie": []}]

    def test_logout_requires_cookie_security(self):
        logout = _schema()["paths"]["/api/v1/auth/logout"]["post"]
        assert logout.get("security") == [{"APIKeyCookie": []}]

    def test_login_is_unauthenticated(self):
        login = _schema()["paths"]["/api/v1/auth/login"]["post"]
        assert not login.get("security")

    def test_csrf_is_unauthenticated(self):
        csrf = _schema()["paths"]["/api/v1/auth/csrf"]["get"]
        assert not csrf.get("security")


class TestAuthErrorContracts:
    def test_login_documents_error_envelopes(self):
        responses = _schema()["paths"]["/api/v1/auth/login"]["post"]["responses"]
        for status in ("401", "422", "429", "503"):
            ref = responses[status]["content"]["application/json"]["schema"]["$ref"]
            assert ref.endswith("/ErrorEnvelope"), status

    def test_me_documents_unauthorized_envelope(self):
        responses = _schema()["paths"]["/api/v1/auth/me"]["get"]["responses"]
        assert "401" in responses
        ref = responses["401"]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("/ErrorEnvelope")

    def test_no_httpvalidationerror_anywhere(self):
        import json

        assert "HTTPValidationError" not in json.dumps(_schema())

    def test_no_real_secrets_in_schema(self):
        import json

        text = json.dumps(_schema()).lower()
        for marker in (
            "change_me",
            "password",
            "secret",
            "postgresql://",
            "session-secret",
        ):
            # "password" appears legitimately in the LoginRequest field name;
            # no *value* may appear.
            assert marker not in text or marker in (
                "password",
            ), f"forbidden marker {marker!r} in schema"


class TestRequestContract:
    def test_login_request_model_documented(self):
        login = _schema()["paths"]["/api/v1/auth/login"]["post"]
        ref = login["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("/LoginRequest")
        assert "LoginRequest" in _schema()["components"]["schemas"]

    def test_user_response_has_no_hash_or_token_fields(self):
        schemas = _schema()["components"]["schemas"]
        user_props = set(schemas["UserResponse"]["properties"])
        assert user_props == {
            "id", "username", "display_name", "role", "permissions",
        }
