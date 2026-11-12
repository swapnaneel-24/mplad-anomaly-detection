// PR-03 review-case domain vocabulary — mirrors the backend exactly.
//
// Source of truth:
//   - backend/app/domain/statuses.py  (ReviewStatus enum + transition matrix)
//   - backend/app/domain/events.py    (EventType enum)
//
// These constants are the exact values the backend persists and accepts.

import type { CaseEventType, ReviewStatus } from "@/api/contracts";

export const REVIEW_STATUSES: readonly ReviewStatus[] = [
  "not_reviewed",
  "under_review",
  "explained_deviation",
  "needs_source_verification",
  "escalated_for_examination",
];

export const INITIAL_REVIEW_STATUS: ReviewStatus = "not_reviewed";

export const TERMINAL_REVIEW_STATUSES: readonly ReviewStatus[] = [
  "explained_deviation",
  "needs_source_verification",
  "escalated_for_examination",
];

export const CASE_EVENT_TYPES: readonly CaseEventType[] = [
  "created",
  "note_added",
  "status_changed",
  "decision_recorded",
  "reopened",
];

/** Human-readable labels for each status (display only; the value is authoritative). */
export const STATUS_LABELS: Record<ReviewStatus, string> = {
  not_reviewed: "Not reviewed",
  under_review: "Under review",
  explained_deviation: "Explained deviation",
  needs_source_verification: "Needs source verification",
  escalated_for_examination: "Escalated for examination",
};

/** Human-readable labels for each event type. */
export const EVENT_LABELS: Record<CaseEventType, string> = {
  created: "Case created",
  note_added: "Note added",
  status_changed: "Status changed",
  decision_recorded: "Decision recorded",
  reopened: "Case reopened",
};

/**
 * The legal forward transitions from a given status (PR-03 domain validator).
 * Mirrors `LEGAL_TRANSITIONS` in backend/app/domain/statuses.py.
 */
export const LEGAL_TRANSITIONS: Record<ReviewStatus, readonly ReviewStatus[]> = {
  not_reviewed: ["under_review"],
  under_review: [
    "explained_deviation",
    "needs_source_verification",
    "escalated_for_examination",
  ],
  explained_deviation: ["under_review"],
  needs_source_verification: ["under_review"],
  escalated_for_examination: ["under_review"],
};
