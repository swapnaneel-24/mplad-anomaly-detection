# PEIARS — v3 Expanded 120-Case Audit Comparison Report

- **Unblinded At (UTC):** 2026-11-23T09:52:36.195008+00:00
- **Frozen Annotations SHA-256:** `f389e112f954f4586f44ba0df3d5b00a88018f7645293308dad11e5c206a0c5b`
- **Population Scope:** Tier-0-matchable eligible IF top-5% population (`123/189` = `65.1%`); `66` unmatched candidates excluded from primary inference.
- **Reviewer Note:** `SINGLE_REVIEWER_LIMITATION`.

## 1. Primary Matched-Pair Actionable Yield (`CONFIRMED_SOURCE_DEFECT`)

- **Complete Adjudicable Pairs (`N`):** `44 / 60` (`IF` adjudicable=`44/60`, `Control` adjudicable=`59/60`)
- **IF Confirmed Defect Rate (Complete Pairs):** `0.000` (`0/44`)
- **Control Confirmed Defect Rate (Complete Pairs):** `0.000` (`0/44`)
- **Paired Yield Difference (`IF - Control`):** **`+0.000`** (`+0.0 pp`, 95% paired bootstrap CI: `[+0.000, +0.000]`)
- **Discordant Pairs (`IF=1,Ctrl=0` vs `IF=0,Ctrl=1`):** `b=0`, `c=0` (exact McNemar `p=1.0000`)
- **Adverse All-60-Pair Sensitivity Bound (Unresolved IF=0, Ctrl=1):** `-0.017`

## 2. Full Outcome Breakdown by Arm (`n = 120`)

review_outcome          BENIGN_EXPLAINED  SUPPORTED_REVIEW_CANDIDATE  UNRESOLVED
audit_group                                                                     
IF_TOP5_SELECTED                      38                           6          16
MATCHED_NON_IF_CONTROL                55                           4           1

## 3. Outcomes by Segment-Count Bucket (`seg_bucket`)

review_outcome                      BENIGN_EXPLAINED  SUPPORTED_REVIEW_CANDIDATE  UNRESOLVED
seg_bucket  audit_group                                                                     
1_seg       IF_TOP5_SELECTED                       8                           2          15
            MATCHED_NON_IF_CONTROL                22                           2           1
2_segs      IF_TOP5_SELECTED                      16                           4           1
            MATCHED_NON_IF_CONTROL                20                           1           0
3_to_5_segs IF_TOP5_SELECTED                       2                           0           0
            MATCHED_NON_IF_CONTROL                 2                           0           0
6_plus_segs IF_TOP5_SELECTED                      12                           0           0
            MATCHED_NON_IF_CONTROL                11                           1           0