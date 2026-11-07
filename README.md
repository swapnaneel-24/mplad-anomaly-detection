---

# PEIARS — Application Direction (in preparation)

## From research study to review application

This repository contains the frozen, reproducible research study
**"MPLAD Fund-Utilisation Anomaly Pattern Detection Using Unsupervised
Learning"**: the Stream A benchmark on the ULB credit-card dataset (the
30,000-row canonical sample, ten IF/LOF configurations, and the complete
Phase 3–6 pipeline with regression suites, manifests, figures and the
five-question consistency synthesis), together with historical notebooks and
provenance records. Those results are complete, frozen and protected; the
application work described below does not modify them.

The project is now transitioning into the **Public Expenditure &
Infrastructure Anomaly Review System (PEIARS)** — a React + FastAPI
application that turns the verified research evidence and approved
public-data snapshots into a human review workflow: select a verified
snapshot, inspect data quality, examine anomalies from appropriately fitted
experiments, compare methods and review workloads, investigate source
records against suitable peer groups, and save an evidence-backed
human-review record.

## Roles of the three data streams

- **Stream A — ULB benchmark (labelled proxy).** The methodological
  benchmark: IF/LOF comparison, uncertainty quantification, agreement
  analysis and the Phase 6 consistency synthesis are frozen research outputs
  displayed read-only. ULB features are anonymized credit-card features;
  they say nothing about MPLADS fund utilisation, and no fitted ULB model is
  ever applied to public-programme data.
- **PMGSY-III (Stream B, unlabelled).** Real public road/bridge proposal
  data. Planned role: the R1 data observatory and data-quality review
  workflow; exploratory anomaly modelling only in R2 and only after an
  explicit feature-viability gate.
- **MPLADS (four-file snapshot, unlabelled).** Administrative records for a
  separately scoped R2 feasibility study: reconciliation, data-quality and
  linkage-failure documentation. No verified fraud labels exist for either
  public dataset, and none are fabricated.

## Proposed architecture

React + TypeScript SPA (`frontend/`) → versioned JSON API `/api/v1` on
FastAPI (`backend/`) → read-only verified research artifacts plus a separate
PostgreSQL review-case database (`deploy/` in later PRs). Model fitting,
threshold selection and any new experiment remain offline CLI jobs with
staged, manifest-backed publication; the application never refits, reranks
or mutates frozen results. These are proposed ADR choices, not implemented
facts.

## Current implementation status

| Area | Status |
|---|---|
| Research pipeline (Phases 3–6), tests, manifests, figures | Complete and frozen (locally hardened) |
| Workspace foundation (this PR-01) | Added: directories, conventions, `.env.example`, README section |
| FastAPI application and `/api/v1` endpoints | Planned — PR-02, **not implemented** |
| PostgreSQL schema and migrations | Planned — PR-03, **not implemented** |
| Authentication / authorization | Planned — PR-04, **not implemented** |
| React UI and investigation workflow | Planned — PR-05, **not implemented** |
| Docker Compose and CI/CD | Planned — PR-06, **not implemented** |
| PMGSY / MPLADS experiments | Planned R2, gated, **not implemented** |

**No functioning application, API, authentication system or deployment
exists yet.** An anomaly flag marks a record as unusual enough to merit
human inspection; it is never evidence of fraud, and no fraud-probability
outputs are produced for unlabeled records.

## Development prerequisites

- **Python 3.12.x** for the research environment. Do not upgrade NumPy,
  SciPy, scikit-learn, Pandas or other research dependencies as part of
  application work; backend dependencies are managed separately from PR-02.
- **Node.js 22 LTS** (recorded in `frontend/.nvmrc`; the 24 LTS line is
  also validated) with its bundled npm. Frontend dependencies are introduced
  in a later PR together with a committed lockfile; PR-01 requires no
  frontend installation.
- Git. DVC only for trusted research-data workflows — never required for
  application development, and never accessed by the application itself.

## Preparing the PR-01 environment

PR-01 adds no installable dependencies: the existing research environment
is sufficient. Copy `.env.example` to `.env` and fill in placeholders only
when a later PR introduces services that consume them; never commit `.env`.
See `docs/architecture/workspace-conventions.md` for the engineering rules
that later PRs follow.

## Governing documents

- `MPLAD_Application_SRS_v0.2.md` — Software Requirements Specification
- `PEIARS_Architecture_ADRs_v0.1.md` — proposed architecture decision records
- `PEIARS_Implementation_Backlog_v0.1.md` — implementation backlog and delivery gates
- `docs/architecture/` — engineering conventions (this PR)
