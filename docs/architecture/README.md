# Architecture documentation

This directory holds engineering conventions and approved architecture
decisions for the PEIARS application transition of the
`mplad-anomaly-detection` repository.

## Contents

- `workspace-conventions.md` — directory responsibilities, allowed
  dependency directions, data and immutability boundaries, environment and
  testing conventions introduced by PR-01. Binding for all later pull
  requests.

## Governing documents (repository root)

- `MPLAD_Application_SRS_v0.2.md` — Software Requirements Specification
  (SRS-PEIARS-001)
- `PEIARS_Architecture_ADRs_v0.1.md` — proposed architecture decision
  records (ARC-PEIARS-001)
- `PEIARS_Implementation_Backlog_v0.1.md` — implementation backlog and
  delivery gates (PLAN-PEIARS-001)

## Rules for this directory

- New decision records are added here as numbered ADR Markdown files once
  approved; they never silently amend the governing documents above.
- The proposed ADR register in the governing architecture document is a
  recommendation, not an implementation claim: nothing described there
  exists in code until the corresponding pull request lands.
- Documentation here is Markdown only; generated machine-readable schemas
  and lockfiles belong next to the code they describe, not in this
  directory.
