"""Role vocabulary and the role-permission matrix (PR-04 §5).

Three roles with a deliberately minimal permission model — no
generalized enterprise policy engine:

========= =========================================================
 Role      Permissions
========= =========================================================
 viewer    read:analytics, read:public
 reviewer  viewer permissions + cases:read, cases:write
 admin     reviewer permissions + admin:users
========= =========================================================

Intended semantics:

* ``viewer`` — read authorized analytical information; **cannot** mutate
  review cases.
* ``reviewer`` — read authorized information **and** perform permitted
  review-case actions.
* ``admin`` — account/role administration (exposed in later milestones)
  **and** full reviewer permissions.

Authorization is always enforced on the server from the database-stored
role; frontend role visibility is never treated as authorization, and
role data from request payloads is never trusted.
"""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    """Server-side application roles."""

    VIEWER = "viewer"
    REVIEWER = "reviewer"
    ADMIN = "admin"


#: The complete permission vocabulary.
VIEWER_PERMISSIONS: frozenset[str] = frozenset(
    {
        "read:public",
        "read:analytics",
    }
)

REVIEWER_PERMISSIONS: frozenset[str] = VIEWER_PERMISSIONS | frozenset(
    {
        "cases:read",
        "cases:write",
    }
)

ADMIN_PERMISSIONS: frozenset[str] = REVIEWER_PERMISSIONS | frozenset(
    {
        "admin:users",
    }
)

#: Role → effective permission set. Roles are additive (admin ⊇ reviewer
#: ⊇ viewer) so the matrix stays reviewable and testable.
ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.VIEWER: VIEWER_PERMISSIONS,
    Role.REVIEWER: REVIEWER_PERMISSIONS,
    Role.ADMIN: ADMIN_PERMISSIONS,
}


def effective_permissions(role: Role) -> frozenset[str]:
    """Return the effective permission set for ``role``.

    Raises ``ValueError`` for an unknown role value — callers convert it
    to the sanitized error contract.
    """
    try:
        return ROLE_PERMISSIONS[Role(role)]
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Unknown role: {role!r}") from exc
