# PEIARS — Isolation Forest Blind Audit Protocol v1

- **Frozen At (UTC):** 2026-11-23T05:54:13.090562+00:00
- **Scope:** 60 packages (`IFAUD_001`–`IFAUD_060`: 30 `IF_TOP5_SELECTED` + 30 `MATCHED_NON_IF_CONTROL`).
- **Blinding Rule:** Do not open `if_enriched_audit_unblinded_key_DO_NOT_PEEK.csv` or inspect IF scores/group labels until all 60 adjudications are complete and frozen.
- **Reviewer Note:** If single-reviewer adjudication is used, disclose single-reviewer scope in notes.

## Allowed `review_outcome` Values
- `VERIFIED_ACTIONABLE_IRREGULARITY` (positive actionable finding)
- `VERIFIED_BENIGN_STRUCTURE`
- `SOURCE_PROCESSING_ARTIFACT`
- `UNRESOLVED`
- `INSUFFICIENT_EVIDENCE`

## Required Fields per Row in `if_enriched_audit_blind_review.csv`
- `review_outcome`, `reviewer_confidence`, `observed_finding`, `supporting_source_evidence`, `alternative_benign_explanation`, `reviewer_notes`.

## Proposed Gate B Research Utility Target (Frozen Pre-Unblinding)
- At least 24 adjudicable cases per group (`VERIFIED_ACTIONABLE_IRREGULARITY` or `VERIFIED_BENIGN_STRUCTURE` or `SOURCE_PROCESSING_ARTIFACT`).
- IF actionable rate at least 20 percentage points above matched controls with a 95% confidence interval lower bound greater than 0.