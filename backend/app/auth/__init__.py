"""Authentication and authorization package (PR-04).

Composition of proven primitives — no custom cryptography:

* Argon2id password hashing via ``argon2-cffi`` (:mod:`app.auth.passwords`).
* Opaque 256-bit session tokens from ``secrets`` (the OS CSPRNG),
  stored only as SHA-256 verifiers (:mod:`app.auth.tokens`).
* Signed double-submit CSRF tokens (HMAC-SHA256) (:mod:`app.auth.tokens`).
* Server-side session validation and revocation
  (:mod:`app.services.auth`, PostgreSQL-backed).
* Role-based authorization dependencies (:mod:`app.auth.dependencies`).
"""

from __future__ import annotations

from app.auth.cookies import (
    clear_csrf_cookie,
    clear_session_cookie,
    set_csrf_cookie,
    set_session_cookie,
)
from app.auth.passwords import (
    PASSWORD_MIN_LENGTH,
    PASSWORD_MAX_LENGTH,
    hash_password,
    verify_password,
)
from app.auth.principals import (
    AuthenticatedPrincipal,
    actor_ref_from_principal,
    is_authenticated_actor_ref,
)
from app.auth.roles import (
    ROLE_PERMISSIONS,
    Role,
    effective_permissions,
)
from app.auth.tokens import (
    generate_csrf_token,
    generate_session_token,
    hash_session_token,
    verify_csrf_token,
)

__all__ = [
    "AuthenticatedPrincipal",
    "PASSWORD_MAX_LENGTH",
    "PASSWORD_MIN_LENGTH",
    "ROLE_PERMISSIONS",
    "Role",
    "actor_ref_from_principal",
    "clear_csrf_cookie",
    "clear_session_cookie",
    "effective_permissions",
    "generate_csrf_token",
    "generate_session_token",
    "hash_password",
    "hash_session_token",
    "is_authenticated_actor_ref",
    "set_csrf_cookie",
    "set_session_cookie",
    "verify_csrf_token",
    "verify_password",
]
