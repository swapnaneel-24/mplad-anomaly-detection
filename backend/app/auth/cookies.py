"""Secure browser-cookie helpers (PR-04 §7).

Production defaults for the session cookie:

* ``HttpOnly`` — the session token is never visible to JavaScript;
* ``Secure`` — sent only over HTTPS (relaxed **only** by the explicit,
  documented local-development setting ``PEIARS_SESSION_COOKIE_SECURE=false``);
* ``SameSite=Lax``;
* ``Path=/`` and no ``Domain`` attribute (host-only cookies).

The CSRF cookie is intentionally **not** HttpOnly: the future React
client must read it to echo the value in the ``X-CSRF-Token`` header
(double-submit). It carries no credential value.

``__Host-`` prefix: cookie names are configurable
(``PEIARS_SESSION_COOKIE_NAME`` / ``PEIARS_CSRF_COOKIE_NAME``). A
deployment serving the API over HTTPS on a single host may set the names
to ``__Host-peiars_session`` / ``__Host-peiars-csrf`` for the extra
browser-enforced guarantees (Secure + Path=/ + no Domain); the default
unprefixed names keep local HTTP development workable. Nothing about the
deployment hostname is hardcoded.

Cookie lifetime is derived from the same setting as server-side session
expiration, so the browser cookie can never outlive the server session.
"""

from __future__ import annotations

from fastapi.responses import Response

from app.core.config import Settings


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    """Attach the secure session cookie to ``response``."""
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_minutes * 60,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    """Expire the session cookie on ``response`` (logout)."""
    response.set_cookie(
        key=settings.session_cookie_name,
        value="",
        max_age=0,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def set_csrf_cookie(response: Response, csrf_token: str, settings: Settings) -> None:
    """Attach the readable CSRF cookie (double-submit) to ``response``."""
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        max_age=settings.session_ttl_minutes * 60,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=False,
        samesite="lax",
    )


def clear_csrf_cookie(response: Response, settings: Settings) -> None:
    """Expire the CSRF cookie on ``response`` (logout)."""
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value="",
        max_age=0,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=False,
        samesite="lax",
    )
