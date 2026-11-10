"""Typed contracts for the authentication API (PR-04 §9).

Every response model is sanitized: ``password_hash`` never appears, and
no session token is ever returned in JSON (the token lives only in the
HttpOnly cookie).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.auth.principals import AuthenticatedPrincipal
from app.auth.roles import Role

#: Bounded input sizes (PR-04 §4, §10).
_USERNAME_MIN = 3
_USERNAME_MAX = 64
_PASSWORD_MIN = 8
_PASSWORD_MAX = 128
_DISPLAY_NAME_MAX = 120


class LoginRequest(BaseModel):
    """Login credentials (bounded; login payloads cannot be oversized)."""

    model_config = ConfigDict(frozen=True)

    username: str = Field(
        min_length=_USERNAME_MIN,
        max_length=_USERNAME_MAX,
        description="Login identifier (normalized server-side).",
    )
    password: str = Field(
        min_length=_PASSWORD_MIN,
        max_length=_PASSWORD_MAX,
        description="Account password (8-128 characters).",
    )


class UserResponse(BaseModel):
    """Sanitized public representation of an authenticated user.

    Carries only approved public fields: user id, username, display
    name, role and the effective permission list. Never a password
    hash, session token or account internals.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Stable user identifier (canonical actor reference).")
    username: str = Field(description="Normalized login identifier.")
    display_name: str = Field(description="Human-readable display name.")
    role: Role = Field(description="Server-side role.")
    permissions: list[str] = Field(
        description="Effective permissions derived from the role (server-side)."
    )

    @classmethod
    def from_principal(cls, principal: AuthenticatedPrincipal) -> "UserResponse":
        return cls(
            id=principal.user_id,
            username=principal.username,
            display_name=principal.display_name,
            role=principal.role,
            permissions=sorted(principal.permissions),
        )


class LogoutResponse(BaseModel):
    """Logout acknowledgement (the session is revoked server-side)."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(description="Fixed value: 'logged_out'.")


class CsrfTokenResponse(BaseModel):
    """Bootstrap CSRF token for the future React client.

    The same value is set in the readable CSRF cookie; the client must
    echo it in the ``X-CSRF-Token`` header on every state-changing
    request. A CSRF token is not a credential.
    """

    model_config = ConfigDict(frozen=True)

    csrf_token: str = Field(description="Signed double-submit CSRF token.")
