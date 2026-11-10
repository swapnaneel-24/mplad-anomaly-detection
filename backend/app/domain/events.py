"""Append-only case-event vocabulary.

Each event type corresponds to a discrete operation in the review
workflow. The event row is persisted atomically with the case mutation
it records (PR-03 §7, ADR-003 §4.3 write invariant).
"""

from __future__ import annotations

from enum import Enum


class EventType(str, Enum):
    """Controlled event-type vocabulary for the append-only ``case_events`` table."""

    CREATED = "created"
    NOTE_ADDED = "note_added"
    STATUS_CHANGED = "status_changed"
    DECISION_RECORDED = "decision_recorded"
    REOPENED = "reopened"
