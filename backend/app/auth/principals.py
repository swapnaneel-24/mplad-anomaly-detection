"""Authenticated principal — the trusted actor identity object (PR-04 §12).

:class:`AuthenticatedPrincipal` is the immutable identity object produced
by server-side session validation. It is the **only** trusted source of
actor attribution for review-case history:

* :func:`actor_ref_from_principal` adapts a validated principal to the
  PR-03 review-service ``actor_ref`` — it returns the persistent user
  UUID, never a client-supplied value.
* Client payloads never carry actor identity into the review services;
  the mapping happens exclusively through this adapter.
* :func:`is_authenticated_actor_ref` distinguishes authenticated
  production principals (UUID user IDs, recorded from PR-04 onward) from
  the synthetic/test actor references used by PR-03 fixtures (for
  example ``fixture-reviewer-001``, which is not a UUID). Historical
  event rows are never rewritten; both forms remain readable in the
  append-only history.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.auth.roles import Role


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Immutable identity of a validated, authenticated user.

    Built exclusively by :mod:`app.services.auth` after server-side
    session validation (cookie token → session row → active user). It is
    never constructed from request payloads.
    """

    user_id: str
    username: str
    display_name: str
    role: Role
    is_active: bool

    @property
    def permissions(self) -> frozenset[str]:
        from app.auth.roles import effective_permissions

        return effective_permissions(self.role)

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


def actor_ref_from_principal(principal: AuthenticatedPrincipal) -> str:
    """Adapt a validated principal to the PR-03 review-service actor_ref.

    Returns the persistent user UUID so case-event history records the
    stable identity rather than the mutable username.
    """
    return principal.user_id


def is_authenticated_actor_ref(actor_ref: object) -> bool:
    """Return True when ``actor_ref`` looks like an authenticated user UUID.

    PR-03-era synthetic/test actor references (e.g. ``r1``,
    ``fixture-reviewer-001``) are not UUIDs and are therefore
    distinguishable from authenticated production principals without
    rewriting any historical event row.
    """
    if not isinstance(actor_ref, str):
        return False
    try:
        uuid.UUID(actor_ref)
    except (ValueError, AttributeError, TypeError):
        return False
    return True
