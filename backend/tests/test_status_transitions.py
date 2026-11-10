"""Status-transition matrix tests (pure unit tests, no database).

Exercises the legal-transition validator for every allowed and disallowed
transition (PR-03 §6, AC-03-05). These tests do not touch the database;
they verify the domain layer's transition logic in isolation.
"""

from __future__ import annotations

import pytest

from app.domain.statuses import (
    INITIAL_STATUS,
    LEGAL_TRANSITIONS,
    IllegalTransitionError,
    ReviewStatus,
    is_legal_transition,
    is_terminal,
    validate_transition,
)


class TestStatusVocabulary:
    def test_exact_five_statuses(self):
        assert set(ReviewStatus) == {
            ReviewStatus.NOT_REVIEWED,
            ReviewStatus.UNDER_REVIEW,
            ReviewStatus.EXPLAINED_DEVIATION,
            ReviewStatus.NEEDS_SOURCE_VERIFICATION,
            ReviewStatus.ESCALATED_FOR_EXAMINATION,
        }

    def test_no_confirmed_fraud_status(self):
        """A statistical anomaly is never labelled as verified misconduct."""
        for status in ReviewStatus:
            assert "fraud" not in status.value
            assert "confirmed" not in status.value
            assert "verified_misconduct" not in status.value

    def test_initial_status_is_not_reviewed(self):
        assert INITIAL_STATUS == ReviewStatus.NOT_REVIEWED

    def test_status_values_are_strings(self):
        for status in ReviewStatus:
            assert isinstance(status.value, str)


class TestTerminalStatuses:
    def test_three_terminal_outcomes(self):
        terminals = {s for s in ReviewStatus if is_terminal(s)}
        assert terminals == {
            ReviewStatus.EXPLAINED_DEVIATION,
            ReviewStatus.NEEDS_SOURCE_VERIFICATION,
            ReviewStatus.ESCALATED_FOR_EXAMINATION,
        }

    def test_not_reviewed_is_not_terminal(self):
        assert not is_terminal(ReviewStatus.NOT_REVIEWED)

    def test_under_review_is_not_terminal(self):
        assert not is_terminal(ReviewStatus.UNDER_REVIEW)


class TestLegalTransitions:
    """Every allowed transition in the matrix."""

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            (ReviewStatus.NOT_REVIEWED, ReviewStatus.UNDER_REVIEW),
            (ReviewStatus.UNDER_REVIEW, ReviewStatus.EXPLAINED_DEVIATION),
            (ReviewStatus.UNDER_REVIEW, ReviewStatus.NEEDS_SOURCE_VERIFICATION),
            (ReviewStatus.UNDER_REVIEW, ReviewStatus.ESCALATED_FOR_EXAMINATION),
            # Reopen from terminal back to under_review.
            (ReviewStatus.EXPLAINED_DEVIATION, ReviewStatus.UNDER_REVIEW),
            (ReviewStatus.NEEDS_SOURCE_VERIFICATION, ReviewStatus.UNDER_REVIEW),
            (ReviewStatus.ESCALATED_FOR_EXAMINATION, ReviewStatus.UNDER_REVIEW),
        ],
    )
    def test_legal_transition_accepted(self, from_status, to_status):
        assert is_legal_transition(from_status, to_status) is True
        validate_transition(from_status, to_status)  # must not raise

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            # not_reviewed cannot skip to a terminal outcome.
            (ReviewStatus.NOT_REVIEWED, ReviewStatus.EXPLAINED_DEVIATION),
            (ReviewStatus.NOT_REVIEWED, ReviewStatus.NEEDS_SOURCE_VERIFICATION),
            (ReviewStatus.NOT_REVIEWED, ReviewStatus.ESCALATED_FOR_EXAMINATION),
            # under_review cannot go back to not_reviewed.
            (ReviewStatus.UNDER_REVIEW, ReviewStatus.NOT_REVIEWED),
            # Terminal statuses cannot transition to other terminal statuses
            # (must reopen to under_review first).
            (ReviewStatus.EXPLAINED_DEVIATION, ReviewStatus.NEEDS_SOURCE_VERIFICATION),
            (ReviewStatus.EXPLAINED_DEVIATION, ReviewStatus.ESCALATED_FOR_EXAMINATION),
            (ReviewStatus.NEEDS_SOURCE_VERIFICATION, ReviewStatus.EXPLAINED_DEVIATION),
            (ReviewStatus.NEEDS_SOURCE_VERIFICATION, ReviewStatus.ESCALATED_FOR_EXAMINATION),
            (ReviewStatus.ESCALATED_FOR_EXAMINATION, ReviewStatus.EXPLAINED_DEVIATION),
            (ReviewStatus.ESCALATED_FOR_EXAMINATION, ReviewStatus.NEEDS_SOURCE_VERIFICATION),
            # Terminal statuses cannot go to not_reviewed.
            (ReviewStatus.EXPLAINED_DEVIATION, ReviewStatus.NOT_REVIEWED),
            (ReviewStatus.NEEDS_SOURCE_VERIFICATION, ReviewStatus.NOT_REVIEWED),
            (ReviewStatus.ESCALATED_FOR_EXAMINATION, ReviewStatus.NOT_REVIEWED),
        ],
    )
    def test_illegal_transition_rejected(self, from_status, to_status):
        assert is_legal_transition(from_status, to_status) is False
        with pytest.raises(IllegalTransitionError):
            validate_transition(from_status, to_status)

    def test_no_op_transition_rejected(self):
        """A no-op transition is not permitted via the matrix."""
        for status in ReviewStatus:
            assert is_legal_transition(status, status) is False

    def test_illegal_transition_error_carries_statuses(self):
        try:
            validate_transition(ReviewStatus.NOT_REVIEWED, ReviewStatus.ESCALATED_FOR_EXAMINATION)
        except IllegalTransitionError as exc:
            assert exc.from_status == ReviewStatus.NOT_REVIEWED
            assert exc.to_status == ReviewStatus.ESCALATED_FOR_EXAMINATION
            assert "not_reviewed" in str(exc)
            assert "escalated_for_examination" in str(exc)
        else:
            pytest.fail("expected IllegalTransitionError")

    def test_error_message_contains_no_case_data(self):
        """The error message is safe to surface (only status names)."""
        try:
            validate_transition(ReviewStatus.UNDER_REVIEW, ReviewStatus.NOT_REVIEWED)
        except IllegalTransitionError as exc:
            msg = str(exc)
            assert "under_review" in msg
            assert "not_reviewed" in msg
            # No case data, actor refs, or paths.
            for forbidden in ("case", "actor", "/", "\\", "uuid"):
                assert forbidden not in msg.lower()


class TestTransitionMatrixShape:
    def test_every_status_has_an_entry(self):
        for status in ReviewStatus:
            assert status in LEGAL_TRANSITIONS

    def test_not_reviewed_only_goes_to_under_review(self):
        assert LEGAL_TRANSITIONS[ReviewStatus.NOT_REVIEWED] == frozenset(
            {ReviewStatus.UNDER_REVIEW}
        )

    def test_under_review_goes_to_three_outcomes(self):
        assert LEGAL_TRANSITIONS[ReviewStatus.UNDER_REVIEW] == frozenset(
            {
                ReviewStatus.EXPLAINED_DEVIATION,
                ReviewStatus.NEEDS_SOURCE_VERIFICATION,
                ReviewStatus.ESCALATED_FOR_EXAMINATION,
            }
        )

    def test_terminals_only_reopen_to_under_review(self):
        for terminal in (
            ReviewStatus.EXPLAINED_DEVIATION,
            ReviewStatus.NEEDS_SOURCE_VERIFICATION,
            ReviewStatus.ESCALATED_FOR_EXAMINATION,
        ):
            assert LEGAL_TRANSITIONS[terminal] == frozenset({ReviewStatus.UNDER_REVIEW})
