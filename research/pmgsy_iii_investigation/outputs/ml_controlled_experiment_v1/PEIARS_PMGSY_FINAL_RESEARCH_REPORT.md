# PEIARS ? PMGSY-III Final Research Report (v1?v3 Closure)

- **Generated At (UTC):** 2026-11-23T10:00:38.597321+00:00
- **Isolation Forest Disposition:** `CLOSED_RESEARCH_NOT_ADMITTED`
- **Primary Evidence Architecture:** Canonical `pmgsy3_3state_v1` -> Option B v2 (state-conditional length consistency) & Topology Auditing -> Evidence Review & Adjudication -> PEIARS Audit Trail.

## Summary of Findings Across Phases

- **v1 / v2 (60-Case Desk Audit):** Enriched for unusual geometry (`+16.3 pp` desk-triage yield, `6/30` vs `1/27`), but missed the `+20 pp` Gate B threshold (`RESEARCH_ONLY_MORE_EVIDENCE`) and carried high source-processing artifact share (`19/30`).
- **10-Case Validity Review:** Recomputed geometry from `segments.parquet` and reconciled `IFAUD_023` sinuosity (`4.732129` prior vs `2.866065` unweighted 2-segment mean); showed high sinuosity with close length alignment lacks independent defect confirmation without external alignment proof.
- **v3 (120-Case Tier-0 Matched Blind Audit):** `0` confirmed source defects in either arm across `44` complete pairs (`+0.000` paired difference, `[+0.000, +0.000]` bootstrap CI, `16/60` IF unresolved mostly in `1_seg`); confirmed `RESEARCH_ONLY_MORE_EVIDENCE` / `CLOSED_RESEARCH_NOT_ADMITTED`.

## Strategic Takeaway

- Reproducible audit methodology, hash provenance, and structured review/provenance trails are established; PMGSY-III primary evidence stays anchored on Option B v2 and topology auditing rather than unsupervised ML anomaly scoring.