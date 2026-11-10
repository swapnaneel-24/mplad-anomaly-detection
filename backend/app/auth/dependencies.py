"""FastAPI authorization dependencies and CSRF enforcement (PR-04 §5, §8).

Dependencies provided:

* :func:`get_current_user` — validates the session cookie server-side
  and returns the :class:`AuthenticatedPrincipal`; anonymous or invalid
  sessions receive ``401 UNAUTHORIZED``.
* :func:`require_authenticated` — readable alias of ``get_current_user``.
* :func:`require_role` / :func:`require_permission` — build dependencies
  that enforce the server-side role/permission matrix; failures receive
  ``403 FORBIDDEN``.
* :func:`require_csrf` — signed double-submit-cookie validation plus
  Origin defence-in-depth for state-changing requests; failures receive
  ``403 CSRF_TOKEN_INVALID``.

CSRF is applied as an explicit route dependency on every state-changing
endpoint (currently ``POST /auth/login`` and ``POST /auth/logout``).
Applying it as a dependency — rather than global middleware — keeps the
404 contract for unknown routes intact; PR-05+ must attach the same
dependency to every new state-changing router (documented in the
backend README). There is deliberately **no** test bypass.
"""

from __future__ import annotations

import hmac

from fastapi import Request, Security
from fastapi.security import APIKeyCookie

from app.auth.principals import AuthenticatedPrincipal
from app.auth.roles import Role
from app.auth.tokens import CSRF_HEADER_NAME, verify_csrf_token
from app.core.errors import ApiError, ErrorCode
from app.services.auth import AuthService

#: OpenAPI cookie-auth scheme. The cookie name is configurable at deploy
#: time; the schema documents the default ``peiars_session``.
SESSION_COOKIE_SCHEME = APIKeyCookie(
    name="peiars_session",
    auto_error=False,
    description="Opaque session token issued by POST /api/v1/auth/login.",
)

#: The generic, sanitized 401 message (no enumeration, no internals).
UNAUTHENTICATED_MESSAGE = "Authentication is required to access this resource."


def _auth_service(request: Request) -> AuthService:
    """Build the AuthService from app state; fail closed when unset."""
    db_factory = getattr(request.app.state, "db_session_factory", None)
    if db_factory is None:
        raise ApiError(
            status_code=503,
            code=ErrorCode.SERVICE_NOT_READY,
            details={"dependency": "database"},
        )
    return AuthService(db_factory.session_factory, request.app.state.settings)


def get_current_user(
    request: Request,
    token: str | None = Security(SESSION_COOKIE_SCHEME),
) -> AuthenticatedPrincipal:
    """Validate the browser session cookie and return the principal.

    Raises ``401 UNAUTHORIZED`` for anonymous, malformed, expired,
    revoked or idle-timed-out sessions, and for disabled accounts.
    """
    if not token:
        token = request.cookies.get(request.app.state.settings.session_cookie_name)
    if not token:
        raise ApiError(status_code=401, code=ErrorCode.UNAUTHORIZED)

    principal = _auth_service(request).validate_session(token)
    if principal is None:
        raise ApiError(status_code=401, code=ErrorCode.UNAUTHORIZED)
    return principal


def require_authenticated(
    request: Request,
    token: str | None = Security(SESSION_COOKIE_SCHEME),
) -> AuthenticatedPrincipal:
    """Explicit alias of :func:`get_current_user` for route readability."""
    return get_current_user(request, token)


def require_role(*allowed_roles: Role):
    """Build a dependency enforcing membership in ``allowed_roles``.

    A viewer cannot impersonate a reviewer; a reviewer cannot self-assign
    administrator privileges — the role always comes from the trusted
    database row via session validation, never from the request.
    """

    def _dependency(
        request: Request,
        token: str | None = Security(SESSION_COOKIE_SCHEME),
    ) -> AuthenticatedPrincipal:
        principal = get_current_user(request, token)
        if principal.role not in allowed_roles:
            raise ApiError(status_code=403, code=ErrorCode.FORBIDDEN)
        return principal

    return _dependency


def require_permission(permission: str):
    """Build a dependency enforcing the effective permission matrix."""

    def _dependency(
        request: Request,
        token: str | None = Security(SESSION_COOKIE_SCHEME),
    ) -> AuthenticatedPrincipal:
        principal = get_current_user(request, token)
        if not principal.has_permission(permission):
            raise ApiError(status_code=403, code=ErrorCode.FORBIDDEN)
        return principal

    return _dependency


def require_csrf(request: Request) -> None:
    """Enforce the signed double-submit-cookie CSRF contract.

    * the CSRF cookie and the ``X-CSRF-Token`` header must both be
      present and equal (constant-time comparison);
    * the embedded HMAC-SHA256 signature must verify against the server
      session secret — an attacker who can set cookies on a subdomain
      still cannot forge a valid pair;
    * when an ``Origin`` header is present it must be an approved CORS
      origin or same-origin (defence in depth; SameSite alone is not
      relied upon).

    Raises ``403 CSRF_TOKEN_INVALID`` on any failure, using the shared
    sanitized error envelope.
    """
    settings = request.app.state.settings
    secret = settings.session_secret

    if not secret:
        # Fail closed: CSRF signing requires the configured secret.
        raise ApiError(
            status_code=503,
            code=ErrorCode.SERVICE_NOT_READY,
            details={"dependency": "session-secret"},
        )

    # --- Origin defence in depth ------------------------------------------
    origin = request.headers.get("origin")
    if origin is not None:
        allowed = set(settings.cors_origins)
        allowed.add(str(request.base_url).rstrip("/"))
        if origin not in allowed:
            raise ApiError(status_code=403, code=ErrorCode.CSRF_TOKEN_INVALID)

    # --- Signed double-submit ----------------------------------------------
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get(CSRF_HEADER_NAME.lower())
    if header_token is None:
        header_token = request.headers.get(CSRF_HEADER_NAME)

    if not cookie_token or not header_token:
        raise ApiError(status_code=403, code=ErrorCode.CSRF_TOKEN_INVALID)

    if not hmac.compare_digest(cookie_token, header_token):
        raise ApiError(status_code=403, code=ErrorCode.CSRF_TOKEN_INVALID)

    if not verify_csrf_token(secret, header_token):
        raise ApiError(status_code=403, code=ErrorCode.CSRF_TOKEN_INVALID)
