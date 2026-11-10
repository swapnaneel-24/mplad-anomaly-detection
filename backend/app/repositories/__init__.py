"""Repository layer: typed database operations for review cases and events.

The repository is the only layer that touches SQLAlchemy ``Session``
objects directly. It exposes typed domain operations (``insert_case``,
``find_by_id``, ``list_cases``, ``insert_event``, ``list_events``) so the
service layer can compose transactional workflows without leaking ORM
details.

Each method operates on a session supplied by the caller (the service
layer). The repository never opens or commits its own transactions: the
service layer owns the transaction boundary so that a case mutation and
its event commit atomically (PR-03 §7, ADR-003 §4.3 write invariant).
"""

from __future__ import annotations

from app.repositories.review_cases import (
    CaseNotFoundError,
    ConcurrencyConflictError,
    ReviewCaseRepository,
)

__all__ = [
    "CaseNotFoundError",
    "ConcurrencyConflictError",
    "ReviewCaseRepository",
]
