"""Authentication endpoints (PR-04 §9).

Routes:

* ``POST /api/v1/auth/login`` — verify credentials, create a fresh
  server-side session, set the secure session cookie, return the
  sanitized user. Failures are generic (no enumeration); throttled
  attempts fail closed with ``429 RATE_LIMITED``.
* ``POST /api/v1/auth/logout`` — require a valid session and CSRF,
  revoke the server-side session, expire the cookies. Replay of the old
  session fails.
* ``GET /api/v1/auth/me`` — the current authenticated user's approved
  public fields plus effective permissions.
* ``GET /api/v1/auth/csrf`` — bootstrap the signed double-submit CSRF
  token (sets the readable cookie; returns the token for the client).

Both state-changing routes carry the ``require_csrf`` dependency. The
session token never appears in any response body — it exists only in
the HttpOnly cookie. ``X-Request-ID`` propagation and the structured
error envelope come from the existing PR-02 middleware/handlers.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, Security

from app.auth.cookies import (
    clear_csrf_cookie,
    clear_session_cookie,
    set_csrf_cookie,
    set_session_cookie,
)
from app.auth.dependencies import (
    SESSION_COOKIE_SCHEME,
    require_authenticated,
    require_csrf,
)
from app.auth.principals import AuthenticatedPrincipal
from app.auth.tokens import generate_csrf_token
from app.contracts.auth import (
    CsrfTokenResponse,
    LoginRequest,
    LogoutResponse,
    UserResponse,
)
from app.contracts.common import ErrorEnvelope
from app.core.errors import ApiError, ErrorCode
from app.services.auth import (
    GENERIC_AUTH_FAILURE,
    AccountLockedError,
    AuthenticationError,
    AuthService,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_ERROR_RESPONSES = {
    401: {"model": ErrorEnvelope, "description": "Authentication required or invalid credentials."},
    422: {"model": ErrorEnvelope, "description": "Validation error (invalid input)."},
    429: {"model": ErrorEnvelope, "description": "Too many failed login attempts (throttled)."},
    503: {"model": ErrorEnvelope, "description": "Authentication is not configured or the database is unavailable."},
}


def _auth_service(request: Request) -> AuthService:
    db_factory = getattr(request.app.state, "db_session_factory", None)
    if db_factory is None:
        raise ApiError(
            status_code=503,
            code=ErrorCode.SERVICE_NOT_READY,
            details={"dependency": "database"},
        )
    return AuthService(db_factory.session_factory, request.app.state.settings)


def _require_session_secret(request: Request) -> str:
    secret = request.app.state.settings.session_secret
    if not secret:
        # Fail closed: cookie auth cannot operate without the signing secret.
        raise ApiError(
            status_code=503,
            code=ErrorCode.SERVICE_NOT_READY,
            details={"dependency": "session-secret"},
        )
    return secret


@router.post(
    "/login",
    response_model=UserResponse,
    dependencies=[Depends(require_csrf)],
    responses=_ERROR_RESPONSES,
    summary="Log in",
    description="Verifies credentials, creates a fresh server-side session "
    "and sets the secure session cookie. Failures are generic; throttled "
    "attempts return 429. Requires the X-CSRF-Token header from "
    "GET /api/v1/auth/csrf.",
)
def login(payload: LoginRequest, request: Request, response: Response) -> UserResponse:
    settings = request.app.state.settings
    _require_session_secret(request)
    service = _auth_service(request)

    try:
        result = service.login(payload.username, payload.password)
    except AccountLockedError:
        raise ApiError(
            status_code=429,
            code=ErrorCode.RATE_LIMITED,
            message="Too many failed login attempts. Try again later.",
        )
    except AuthenticationError:
        raise ApiError(
            status_code=401,
            code=ErrorCode.UNAUTHORIZED,
            message=GENERIC_AUTH_FAILURE,
        )

    # Fresh session cookie + rotated CSRF token (session-fixation prevention).
    set_session_cookie(response, result.session_token, settings)
    csrf_token = generate_csrf_token(settings.session_secret)
    set_csrf_cookie(response, csrf_token, settings)

    return UserResponse.from_principal(result.principal)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    dependencies=[Depends(require_csrf)],
    responses=_ERROR_RESPONSES,
    summary="Log out",
    description="Requires a valid session and the X-CSRF-Token header. "
    "Revokes the server-side session (irreversible) and expires the "
    "cookies. Replay of the old session fails.",
)
def logout(
    request: Request,
    response: Response,
    principal: AuthenticatedPrincipal = Depends(require_authenticated),
) -> LogoutResponse:
    settings = request.app.state.settings
    service = _auth_service(request)
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        service.logout(token)

    clear_session_cookie(response, settings)
    clear_csrf_cookie(response, settings)
    return LogoutResponse(status="logged_out")


@router.get(
    "/me",
    response_model=UserResponse,
    responses=_ERROR_RESPONSES,
    summary="Current user",
    description="Returns the authenticated user's approved public fields and "
    "effective permissions. Requires the session cookie.",
)
def me(
    principal: AuthenticatedPrincipal = Security(require_authenticated),
) -> UserResponse:
    return UserResponse.from_principal(principal)


@router.get(
    "/csrf",
    response_model=CsrfTokenResponse,
    responses={503: {"model": ErrorEnvelope, "description": "Authentication is not configured."}},
    summary="CSRF token bootstrap",
    description="Issues a signed double-submit CSRF token: the value is set "
    "in the readable CSRF cookie and returned in the body. The client must "
    "echo it in the X-CSRF-Token header on every state-changing request "
    "(login, logout, and future writes).",
)
def csrf(request: Request, response: Response) -> CsrfTokenResponse:
    settings = request.app.state.settings
    secret = _require_session_secret(request)

    csrf_token = generate_csrf_token(secret)
    set_csrf_cookie(response, csrf_token, settings)
    return CsrfTokenResponse(csrf_token=csrf_token)
