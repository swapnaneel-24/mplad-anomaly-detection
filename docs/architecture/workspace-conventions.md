# PEIARS workspace and engineering conventions (PR-01)

Status: foundation conventions introduced by PR-01. They govern all later
application pull requests (PR-02 onward). They elaborate the proposed ADRs
in `PEIARS_Architecture_ADRs_v0.1.md`; where any conflict appears, the SRS
(`MPLAD_Application_SRS_v0.2.md`) and the approved ADR register win, and the
conflict must be escalated — never silently resolved in code.

## 1. Directory responsibilities

| Directory | Responsibility | Introduced |
|---|---|---|
| `frontend/` | React + TypeScript + Vite SPA: UI components, six-workspace routing, typed API client. No analytical computation. | PR-01 (conventions) / PR-05 (application) |
| `backend/` | FastAPI application: `/api/v1` contracts, authentication boundaries, application services, review-case persistence. | PR-01 (conventions) / PR-02 (application) |
| `deploy/` | Docker and deployment configuration. | PR-06 |
| `docs/architecture/` | Engineering conventions and approved ADRs. | PR-01 |
| `src/mplad/` | Existing frozen research package (Stream A phases 3–6 and shared utilities) and future explicitly separated offline analytical modules (e.g. the R2 `enhancements` namespace). | Existing — protected |
| `scripts/` | Existing research CLI runners (`run_phase*.py`) and future offline job entry points. | Existing — protected |
| `tests/` | Existing regression suites (phases 3–6). Application tests are added as new files or subdirectories, never as modifications of frozen files. | Existing — protected |
| `data/`, `results/` | Research inputs (`data/processed/stream-a/features/...`) and canonical outputs (`results/stream a/phase N/...`). The literal spaces in the `results/stream a/` path segments are intentional historical artifacts and are preserved verbatim. | Existing — protected |

## 2. Allowed dependency directions

1. `frontend/` → backend, **only** through the versioned HTTP JSON API
   (`/api/v1`). The frontend never imports Python code, never reads files
   and never receives credentials or server-side paths.
2. `backend/` → (a) read-only, approved adapters over `src/mplad` outputs
   and registered source snapshots; (b) the application PostgreSQL database
   for review cases. HTTP handlers never fit models, recompute thresholds
   or mutate research artifacts (ADR-004: offline computation only).
3. Offline jobs (`scripts/`) → may compute and publish new versioned
   artifacts via staged publication with manifests. They never serve HTTP.
4. Nothing application-side writes into `src/mplad/`, `data/`, `results/`,
   DVC metadata or historical notebooks.
5. `src/mplad/` remains importable exactly as today: src layout without
   installation, via the documented `sys.path` adapter
   (`tests/conftest.py`). No new package roots, no renamed modules, no
   src-layout changes. Any move toward proper packaging is a separately
   reviewed change.

## 3. API namespace

All application HTTP endpoints live under `/api/v1` — the versioned JSON
API namespace. Breaking contract changes require a new version segment,
never in-place silent changes. Error responses use the structured envelope
proposed in the ADR register (stable machine-readable codes, request IDs, no
stack traces or filesystem paths). An `integrity_failed` state is never
presented as a successful verified result, and an `unavailable` artifact is
never replaced by synthetic or stale values.

## 4. Immutable research artifacts vs mutable review data

Three persistence domains, never merged:

- **Frozen research evidence** — `results/**`, manifests, figures, reports.
  Written only by offline staged publication. The API exposes them
  read-only and verifies SHA-256 manifests before labelling anything
  `verified`.
- **Approved source snapshots** — ULB, PMGSY and MPLADS data under
  server-side registry control, admitted only by offline admission jobs
  with licence verification.
- **Mutable review data** — cases, notes and append-only events in the
  application database. The only writable domain. Review writes never
  alter the first two domains.

## 5. Offline-only model fitting and experimental publication

Model fitting, threshold selection, bootstrap recomputation, projections and
any new experiment run as explicit offline CLI jobs with recorded seeds,
dependency versions and staged publication (preflight → verify inputs →
compute → validate → stage manifest → publish with rollback). Browser and
API interactions can only read stored, published results. The frozen ULB
benchmark is never refitted at runtime, and canonical review thresholds are
never recomputed from the browser.

## 6. Approved-source access instead of arbitrary filesystem access

The backend resolves datasets only through an explicit server-side source
registry (an allowlist of approved snapshot versions). Arbitrary filesystem
paths, client-supplied paths and directory crawling are prohibited.
`../../`-style or otherwise malicious path input is rejected at the adapter
boundary. Missing manifests or failing hashes surface explicit
`unavailable` / `integrity_failed` states — never synthetic fallback
values.

## 7. Environment variables and secret handling

- `.env.example` at the repository root is the only committed environment
  template: **placeholders only**.
- Real values live in uncommitted `.env` files (local) or a proper secret
  store (CI/hosting); never in code, prompts, logs or CI artifacts.
- Research-artifact storage credentials (DVC remotes, object storage) are
  provisioned only inside trusted offline workflows. Public PR builds never
  pull DVC data, never touch remote storage and never receive such
  credentials.
- Application logs never contain credentials, reviewer notes or raw
  administrative record fields.

## 8. Naming, imports and testing conventions

- **Python**: follow the existing research-package style (module
  docstrings, explicit constants, typed signatures where present). Backend
  modules live under `backend/app/...` per ADR-002. Test files are named
  `test_*.py`; new application fixtures go under `tests/fixtures/` (new) or
  `backend/tests/` and must be small and deterministic.
- **TypeScript**: `frontend/src/...` with route-based feature modules and
  strict mode enabled.
- **Frozen test files** (`tests/test_phase3.py` … `tests/test_phase6.py`,
  `tests/conftest.py`) are never modified by application PRs. Application
  tests are added as new files.
- Dependency changes require the matching lockfile update in the same pull
  request; installs use `npm ci` (frontend) and pinned requirements
  (backend), never floating latest versions.

## 9. Synthetic development fixtures vs actual ULB, PMGSY and MPLADS data

- Development and CI use clearly labelled **synthetic fixtures** only.
  Fixture files and outputs carry visible `SYNTHETIC` labelling.
- Real ULB (credit-card proxy benchmark), PMGSY-III and MPLADS snapshots
  never enter the repository through application PRs; they are admitted
  via the source-admission workflow with licence and integrity
  verification.
- ULB labels are used for post-hoc evaluation only. No verified fraud
  labels exist for PMGSY or MPLADS; no fraud-probability outputs are
  produced for unlabeled records, and no fitted ULB model is applied to
  public-programme feature spaces.
- Synthetic sandbox outputs must never be presented as canonical research
  results; canonical numbers come only from the frozen, manifest-verified
  artifacts.

## 10. How later PRs introduce migrations, authentication and deployment

Planned, **not implemented** — this section only fixes where they will land:

- **PR-02 — FastAPI application:** app factory, `/api/v1/health/live`,
  `/health/ready`, `/meta`, error envelopes, request-ID middleware,
  OpenAPI schema export; separate backend dependency management.
- **PR-03 — database:** SQLAlchemy models for cases, append-only case
  events and reviewer identity, plus Alembic migrations under
  `backend/migrations/`; case mutations and their events commit in one
  transaction.
- **PR-04 — authentication:** a maintained session/identity integration
  (provider decision pending); server-enforced roles on case routes;
  HttpOnly cookies with CSRF protection where cookie auth is used.
- **PR-05 — React application:** Vite + React + TypeScript scaffold, six
  workspace routes with honest not-yet-available states, one synthetic
  review workflow, typed API client generated from the OpenAPI schema.
- **PR-06 — deployment and CI:** `deploy/compose.yaml` (API, PostgreSQL,
  frontend/proxy, health checks, named volumes) and GitHub Actions
  fast-fixture pipelines; trusted, manually dispatched workflows for
  data-dependent verification.
- **PR-07 — M1 release candidate:** integrated fault tests, troubleshooting
  docs, before/after hash inventory of frozen files.

None of these exist yet. Until the corresponding pull request lands, the
repository contains no application functionality beyond the workspace
foundation and this documentation.
