"""Repository layer: typed database operations.

The repository is the only layer that touches SQLAlchemy ``Session``
objects directly. It exposes typed domain operations so the service
layer can compose transactional workflows without leaking ORM details.

Each method operates on a session supplied by the caller (the service
layer). The repository never opens or commits its own transactions: the
service layer owns the transaction boundary so that multi-row writes
commit atomically (PR-03 §7, ADR-003 §4.3 write invariant; PR-04
authentication transactions follow the same convention).
"""

from __future__ import annotations

from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.login_throttles import LoginThrottleRepository
from app.repositories.review_cases import (
    CaseNotFoundError,
    ConcurrencyConflictError,
    ReviewCaseRepository,
)
from app.repositories.users import (
    DuplicateUsernameError,
    UserRepository,
)

__all__ = [
    "AuthSessionRepository",
    "CaseNotFoundError",
    "ConcurrencyConflictError",
    "DuplicateUsernameError",
    "LoginThrottleRepository",
    "ReviewCaseRepository",
    "UserRepository",
]
