"""Domain layer: review-case state machine and event vocabulary.

The domain layer encodes the business rules that are independent of any
database or HTTP transport:

* the controlled review-status vocabulary,
* the legal status-transition matrix,
* the append-only event-type vocabulary,
* the typed actor reference.

These types are pure Python (enums and validators) and carry no ORM,
Pydantic-settings or FastAPI dependencies. They are imported by the
repository, service and contract layers so that a single source of truth
defines the review workflow.
"""

from __future__ import annotations

from app.domain.events import EventType
from app.domain.statuses import (
    IllegalTransitionError,
    ReviewStatus,
    TransitionTable,
    is_legal_transition,
    validate_transition,
)

__all__ = [
    "EventType",
    "IllegalTransitionError",
    "ReviewStatus",
    "TransitionTable",
    "is_legal_transition",
    "validate_transition",
]
