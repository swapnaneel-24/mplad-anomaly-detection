"""Review-status vocabulary and the legal transition matrix.

Status vocabulary (PR-03 §6, ADR-003 §4.3):

    not_reviewed
        ↓
    under_review
        ├── explained_deviation
        ├── needs_source_verification
        └── escalated_for_examination

Rules:

* ``not_reviewed`` is the only legal initial status at case creation.
* ``under_review`` is the single gateway out of ``not_reviewed``.
* The three outcome statuses are terminal for the initial review pass.
* A later reassessment is permitted only through an explicit ``reopened``
  event (recorded in the append-only history) returning a case from a
  terminal outcome back to ``under_review``. This is the only legal
  transition out of a terminal status.
* There is **no** ``confirmed_fraud`` status. A statistical anomaly is
  never labelled as verified misconduct (PR-03 §6, ADR-003 §4.3).
"""

from __future__ import annotations

from enum import Enum


class ReviewStatus(str, Enum):
    """Controlled review-status vocabulary.

    A ``str`` enum so values survive JSON round-trips and SQLA string
    columns without custom serializers.
    """

    NOT_REVIEWED = "not_reviewed"
    UNDER_REVIEW = "under_review"
    EXPLAINED_DEVIATION = "explained_deviation"
    NEEDS_SOURCE_VERIFICATION = "needs_source_verification"
    ESCALATED_FOR_EXAMINATION = "escalated_for_examination"


#: The only status a newly created case may start in.
INITIAL_STATUS = ReviewStatus.NOT_REVIEWED

#: Statuses that end the initial review pass. The only legal transition
#: out of a terminal status is the explicit ``reopened`` return to
#: ``under_review`` (recorded as a status-changed event).
_TERMINAL_STATUSES = frozenset(
    {
        ReviewStatus.EXPLAINED_DEVIATION,
        ReviewStatus.NEEDS_SOURCE_VERIFICATION,
        ReviewStatus.ESCALATED_FOR_EXAMINATION,
    }
)

#: Legal forward transitions (from -> set of permitted targets).
#:
#: - ``not_reviewed`` may only enter ``under_review``.
#: - ``under_review`` may move to any of the three outcome statuses.
#: - A terminal outcome may be explicitly reopened to ``under_review``;
#:   this is the only legal transition out of a terminal status and is
#:   always recorded as a status-changed event with a reason.
#: - ``under_review`` may also transition to itself via an explicit
#:   note-only or decision event that does not change the status (handled
#:   by the service layer, not the transition matrix).
TransitionTable = dict[ReviewStatus, frozenset[ReviewStatus]]

LEGAL_TRANSITIONS: TransitionTable = {
    ReviewStatus.NOT_REVIEWED: frozenset({ReviewStatus.UNDER_REVIEW}),
    ReviewStatus.UNDER_REVIEW: frozenset(
        {
            ReviewStatus.EXPLAINED_DEVIATION,
            ReviewStatus.NEEDS_SOURCE_VERIFICATION,
            ReviewStatus.ESCALATED_FOR_EXAMINATION,
        }
    ),
    ReviewStatus.EXPLAINED_DEVIATION: frozenset({ReviewStatus.UNDER_REVIEW}),
    ReviewStatus.NEEDS_SOURCE_VERIFICATION: frozenset({ReviewStatus.UNDER_REVIEW}),
    ReviewStatus.ESCALATED_FOR_EXAMINATION: frozenset({ReviewStatus.UNDER_REVIEW}),
}


class IllegalTransitionError(ValueError):
    """Raised when a requested status transition is not permitted.

    The message is safe to surface to the application layer (it contains
    only status names, never case data or actor identity).
    """

    def __init__(self, from_status: ReviewStatus, to_status: ReviewStatus) -> None:
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Illegal review-status transition: {from_status.value} -> {to_status.value}."
        )


def is_legal_transition(from_status: ReviewStatus, to_status: ReviewStatus) -> bool:
    """Return ``True`` if ``from_status -> to_status`` is permitted."""
    if from_status == to_status:
        # A no-op transition is allowed only as a note/decision event;
        # the service layer handles that case without consulting the
        # transition matrix. Here we report it as illegal so the matrix
        # is never used to justify a silent no-op status change.
        return False
    return to_status in LEGAL_TRANSITIONS.get(from_status, frozenset())


def validate_transition(from_status: ReviewStatus, to_status: ReviewStatus) -> None:
    """Raise :class:`IllegalTransitionError` if the transition is illegal."""
    if not is_legal_transition(from_status, to_status):
        raise IllegalTransitionError(from_status, to_status)


def is_terminal(status: ReviewStatus) -> bool:
    """Return ``True`` if ``status`` is a terminal review outcome."""
    return status in _TERMINAL_STATUSES
