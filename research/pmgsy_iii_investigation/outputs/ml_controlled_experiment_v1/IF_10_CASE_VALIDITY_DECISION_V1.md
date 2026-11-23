# PEIARS — 10-Case Validity Review Decision Addendum v1

- **Frozen At (UTC):** 2026-11-23T09:22:36.094537+00:00
- **Source Sheet:** `IF_10_CASE_VALIDITY_REVIEW_V1.csv` (`SHA-256: 6a96423dceb5824630362bb4c793c5218c3d8b23b39e652e08b551a7644dbea1`)
- **Original v1 Results Status:** `IF_ENRICHED_AUDIT_RESULTS_V1.csv` remains untouched as a historical record.
- **Reviewer Limitation:** `SINGLE_REVIEWER_LIMITATION` (single desk reviewer; no external field survey data).
- **Reclassified Rows (vs. Original v2 Outcome):** `10 / 10`
- **Final Validity Outcomes:** `{'SUPPORTED_REVIEW_CANDIDATE': 6, 'UNRESOLVED': 4}`

## `IFAUD_023` Sinuosity Reconciliation

- Prior package feature table recorded `mean_sinuosity = 4.732129`; independent `segments.parquet` (`EPSG:7755`) recomputation yielded `2.866065` across 2 segments (`15.048 km` vs `15.350 km` proposed).
- Both figures are preserved side-by-side without silent overwrite; `IFAUD_023` is held as `UNRESOLVED` pending geometry/aggregation provenance check.

## Original vs. Revised Summary

 audit_id            audit_group              original_v2_outcome  final_adjudicated_outcome confidence
IFAUD_002       IF_TOP5_SELECTED VERIFIED_ACTIONABLE_IRREGULARITY                 UNRESOLVED     MEDIUM
IFAUD_003       IF_TOP5_SELECTED VERIFIED_ACTIONABLE_IRREGULARITY                 UNRESOLVED     MEDIUM
IFAUD_007       IF_TOP5_SELECTED VERIFIED_ACTIONABLE_IRREGULARITY SUPPORTED_REVIEW_CANDIDATE     MEDIUM
IFAUD_010       IF_TOP5_SELECTED VERIFIED_ACTIONABLE_IRREGULARITY SUPPORTED_REVIEW_CANDIDATE     MEDIUM
IFAUD_023       IF_TOP5_SELECTED VERIFIED_ACTIONABLE_IRREGULARITY                 UNRESOLVED        LOW
IFAUD_054       IF_TOP5_SELECTED VERIFIED_ACTIONABLE_IRREGULARITY                 UNRESOLVED     MEDIUM
IFAUD_043 MATCHED_NON_IF_CONTROL VERIFIED_ACTIONABLE_IRREGULARITY SUPPORTED_REVIEW_CANDIDATE     MEDIUM
IFAUD_013 MATCHED_NON_IF_CONTROL                       UNRESOLVED SUPPORTED_REVIEW_CANDIDATE        LOW
IFAUD_020 MATCHED_NON_IF_CONTROL                       UNRESOLVED SUPPORTED_REVIEW_CANDIDATE        LOW
IFAUD_028 MATCHED_NON_IF_CONTROL                       UNRESOLVED SUPPORTED_REVIEW_CANDIDATE        LOW