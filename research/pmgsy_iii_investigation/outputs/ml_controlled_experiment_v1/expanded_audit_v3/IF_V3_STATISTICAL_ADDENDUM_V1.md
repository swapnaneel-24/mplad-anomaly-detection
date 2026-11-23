# PEIARS ? v3 Prespecified Statistical Analysis Clarification v1

- **Recorded At (UTC):** 2026-11-23T09:51:23.095145+00:00
- **Timing:** Recorded prior to v3 annotation freeze and unblinding.

## Prespecified Rules

1. **Complete-Pair Completeness Clarification (Gate B):** In addition to at least 48 adjudicable cases per arm, require at least `48` complete adjudicable pairs (`N >= 48` where both IF and matched control in the pair have adjudicable outcomes: `CONFIRMED_SOURCE_DEFECT`, `SUPPORTED_REVIEW_CANDIDATE`, or `BENIGN_EXPLAINED`) for the primary paired analysis.
2. **Primary Endpoint Coding:** `Y = 1` strictly for independently substantiated, actionable `CONFIRMED_SOURCE_DEFECT`; `Y = 0` for `SUPPORTED_REVIEW_CANDIDATE` and `BENIGN_EXPLAINED`. `UNRESOLVED` and `INSUFFICIENT_EVIDENCE` are excluded from the primary complete-pair estimate.
3. **Paired Bootstrap & McNemar:** Compute paired yield difference `Delta = mean(Y_i,IF - Y_i,Control)` across complete pairs, a 95% percentile bootstrap CI using `20,000` pair-level resamples (`seed = 20261123`), discordant-pair counts (`b`: IF=1/Ctrl=0, `c`: IF=0/Ctrl=1), and exact two-sided McNemar p-value.
4. **Unresolved Sensitivity Bounds:** Report complete-pair estimates alongside all-60-pair bounds, including an adverse sensitivity scenario assigning unresolved IF items `0` and unresolved controls `1`.
5. **Single-Reviewer Disclosure:** If adjudicated by a single reviewer, record `SINGLE_REVIEWER_LIMITATION` in Gate G and treat any positive admission recommendation as provisional.