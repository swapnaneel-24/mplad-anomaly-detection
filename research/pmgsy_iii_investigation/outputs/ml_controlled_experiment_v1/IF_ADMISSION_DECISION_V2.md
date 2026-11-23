# PEIARS ? Final Isolation Forest Admission Decision v2

- **Recorded At (UTC):** 2026-11-23T07:47:00.367559+00:00
- **Disposition:** **`RESEARCH_ONLY_MORE_EVIDENCE`** (`GATE_B_NOT_MET`)
- **Frozen Audit Results SHA-256:** `b72002085fb344011b473b6afa685e74dcd08e0a6d93980de49bb84011398e9b`
- **Audit Scope & Caveat:** Single-reviewer desk audit of 60 enriched/control rows without external field survey data. The 20.0% (6/30) actionable yield and +16.3 pp (+0.163, 95% CI [+0.003, +0.323]) difference reflect an enriched audit sample, not general-population precision across all 4,361 `P` packages.

## Governance Decisions (`PEIARS-IF-001` ? `PEIARS-IF-007`)

| Decision ID | Decision |
| :--- | :--- |
| `PEIARS-IF-001` | Option B v2 (state-conditional R) and topology auditing remain primary evidence tracks |
| `PEIARS-IF-002` | Five-feature Isolation Forest v1 remains frozen and research-only |
| `PEIARS-IF-003` | Gate B not met: observed incremental actionable yield +0.163 (+16.3 pp) vs required +0.20 (+20.0 pp); 95% CI [+0.003, +0.323] |
| `PEIARS-IF-004` | No retrospective relaxation of admission criteria or retraining on the 60-case audit |
| `PEIARS-IF-005` | Source-processing artifacts (19/30 IF-selected vs 6/30 controls) tracked separately for source-quality diagnostics, not conflated with actionable infrastructure irregularities |
| `PEIARS-IF-006` | Expanded independent audit (indicative 100?150 cases with pre-registered protocol) required before any v3 research-pilot admission decision |
| `PEIARS-IF-007` | No IF + R weighted composite score and no production anomaly or fraud detection |

## Immediate Follow-Up Checks Before Expanded Pilot

1. Inspect the 7 `VERIFIED_ACTIONABLE_IRREGULARITY` rows and 3 `UNRESOLVED` control rows in `IF_ENRICHED_AUDIT_RESULTS_V1.csv` against source attributes and verify matching/CI assumptions.
2. Commit frozen artifacts, reports, and scripts to version control with original admission rules intact.