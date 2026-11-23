# PEIARS ? Isolation Forest Research Closure v1

- **Closed At (UTC):** 2026-11-23T10:00:38.597321+00:00
- **Final Research Disposition:** **`CLOSED_RESEARCH_NOT_ADMITTED`**
- **Reason Code:** `PRIMARY_ENDPOINT_ZERO_CONFIRMED_DEFECTS; COMPLETENESS_GATE_FAILED; INSUFFICIENT_INDEPENDENT_EVIDENCE`
- **Historical Compatibility:** Compatible with prior `RESEARCH_ONLY_MORE_EVIDENCE` model-eligibility records; formally closes further experimental investment in the PMGSY-III Isolation Forest line (`v4` not authorized).
- **Prior Commit Reference:** `afdd70b` on `main`.

## Verified Artifact Hashes & Archive Status

- `IF_ENRICHED_AUDIT_RESULTS_V1.csv`: `b72002085fb344011b473b6afa685e74dcd08e0a6d93980de49bb84011398e9b`
- `IF_10_CASE_VALIDITY_REVIEW_V1.csv`: `6a96423dceb5824630362bb4c793c5218c3d8b23b39e652e08b551a7644dbea1`
- `IF_V3_BLIND_REVIEW.csv`: `bdf35c5611e9d8463ec09399cbf0ef4efaa8dc266bcd62660c7bec425f800615`
- `IF_V3_BLIND_ANNOTATIONS.csv`: `f389e112f954f4586f44ba0df3d5b00a88018f7645293308dad11e5c206a0c5b`
- `IF_V3_ANNOTATIONS_FREEZE.json`: `c8dd2b91684e0c89d3dfb1af29028920ddf8b68b86e2d0816526d7d494b35efe`
- Provenance `IF_V3_BLIND_ANNOTATIONS.csv`: `f389e112f954f4586f44ba0df3d5b00a88018f7645293308dad11e5c206a0c5b` (status: `True`)
- Provenance `IF_V3_ANNOTATIONS_FREEZE.json`: `c8dd2b91684e0c89d3dfb1af29028920ddf8b68b86e2d0816526d7d494b35efe` (status: `True`)
- Provenance `IF_AUDIT_COMPARISON_V3.md`: `074e90d7e2d4ef9ce79321cee98fbe9c4460da56438223af58b91cf1575f2790` (status: `True`)
- Provenance `IF_ADMISSION_DECISION_V3.md`: `4753dfef570bb954767b8b2e55a6eff0e71edb01ef44f6ab335c5c4e18a6bbb3` (status: `True`)
- Provenance `IF_V3_UNBLINDED_RESULTS.csv_RESTRICTED`: `37e8c7fdb031e842f2e41022d57ce91060f3b95cefa256b479f4b18125c0ab61` (status: `True`)
- Provenance `IF_V3_PAIRWISE_COMPARISON.csv_RESTRICTED`: `9343a53140d72321fbfe2c126e5cbedcf350a14700571f918fdec07f96f54e94` (status: `True`)

## Methodological Lessons & Scope Boundaries

- **Structural Unusualness vs. Confirmed Defects:** Isolation Forest detected unusual structural geometry (`+16.3 pp` desk-triage yield in v1), but under strict v3 desk review (`120` cases, `44` complete pairs, `0` confirmed defects in both arms, `16/60` unresolved IF cases concentrated in `1_seg`), no confirmed source defect was established.
- **Degenerate Bootstrap & Sensitivity Caveat:** A `[+0.000, +0.000]` paired bootstrap CI with zero observed events reflects zero observed positives rather than proof of exact zero effect, and `-0.017` is preserved historically without treating it as a complete bound across all unresolved cases.
- **Prohibited Next Steps:** No extra IF seeds/contamination/feature tuning, no immediate LOF/unsupervised swap, no large desk audits without new external evidence, no reclassifying unresolved cases as anomalies, and no lowering of the confirmed-defect standard.

## Work Packages (WP1?WP3)

- **WP1 (Close & Archive IF Line):** Freeze `IF_RESEARCH_CLOSURE_V1.md` and `PEIARS_PMGSY_FINAL_RESEARCH_REPORT.md` without altering v1/v2/v3 reports.
- **WP2 (Strengthen Primary Pipeline):** Consolidate Option B v2 + topology audit evidence in `PMGSY_EVIDENCE_REGISTER_V2.csv`, keeping `SUPPORTED_REVIEW_CANDIDATE` distinct from confirmed source errors.
- **WP3 (Targeted External Geometry Study ? Conditional):** Only if authoritative alignment maps/survey drawings become available, audit a bounded sample of unresolved `1_seg` high-sinuosity IF cases as source validation (not IF retraining).