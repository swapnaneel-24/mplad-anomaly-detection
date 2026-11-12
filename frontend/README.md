# PEIARS Frontend

**PR-05A redesign — Desktop Scientific Workbench.**

A React + TypeScript + Vite single-page application that serves as the
scientific investigation workbench for the Public Expenditure &
Infrastructure Anomaly Review System (PEIARS). Talks to the existing
FastAPI backend (PR-02 through PR-04) exclusively through the versioned
`/api/v1` JSON API.

**Stack:** React 18, TypeScript (strict), Vite 5, React Router 6, Vitest 2,
React Testing Library, Playwright. No Redux, no enterprise UI library, no
chart library, no bundled fonts (system-font stack only).

## What changed in the redesign

The permanent left sidebar is **gone**. The post-login shell is now a
vertical stack of horizontal bands:

1. **Identity bar** (40px) — PEIARS mark + environment + connectivity + user + Sign out.
2. **Workspace switcher** (36px) — six horizontal tabs, WAI-ARIA tabs pattern.
3. **Context strip** (32px) — workspace name + contextual breadcrumb.
4. **Workspace composition** (flexible) — purpose-specific multi-panel grid per workspace.
5. **Provenance footer** (24px) — API status + version + git commit + request ID on error.

**Desktop-only.** The minimum supported viewport width is 1024 CSS pixels
(PR-06A normalized minimum; earlier revisions said 1280).
Below that, a `DesktopGate` panel replaces the composition area with a
restrained width-restriction message. There is no mobile layout, no
hamburger, no drawer.

Each workspace has a **distinct multi-panel composition** (no shared card
template):
- **Overview** — editorial 960px column with workflow map, streams, status, entry grid.
- **Data Observatory** — `240px 1fr 320px` filter rail + table + inspector.
- **Anomaly Analysis** — four-region workbench: parameter rail + dominant canvas + inspector + records.
- **Investigation** — `260px 1fr 320px` case index + evidence + assessment/history.
- **Cross-Domain** — three-column comparison + comparability matrix.
- **Research & Provenance** — `1fr 320px` methodology + sticky artifact sidebar.

## Quick start

> **Canonical startup guides (PR-06A):** `docs/dev/LOCAL_STARTUP_WINDOWS.md`
> and `docs/dev/LOCAL_STARTUP_POSIX.md` walk a fresh checkout through
> backend configuration (repository-root `.env`), migrations, user
> provisioning, and both dev servers stage by stage. The summary below is
> the short form.

```bash
# 1. Install dependencies (Node 22 LTS or 24 LTS). npm ci works on a
#    fresh checkout (no node_modules needed) as long as the committed
#    package-lock.json is valid.
cd frontend
npm ci

# 2. Configure the backend (PR-04+) on :8000 — copy backend/.env.example
#    to the repository-root .env and fill it in (database URL, a real
#    PEIARS_SESSION_SECRET, cookie secure=false for local HTTP). See
#    docs/dev/CONFIGURATION_INVENTORY.md for every variable; serve.py
#    and alembic both read the same .env file.
cd ../backend
alembic upgrade head
python scripts/serve.py

# 3. Start the Vite dev server on :5173.
cd ../frontend
npm run dev
# Open http://127.0.0.1:5173/  (use a desktop browser ≥ 1024 CSS px wide)
```

The Vite dev server proxies `/api/*` to `http://127.0.0.1:8000` (see
`vite.config.ts`). This keeps cookies same-origin from the browser's
perspective, so the signed double-submit CSRF flow and the HttpOnly
session cookie work without any backend CORS modification.

## Scripts

| Script | Purpose |
|---|---|
| `npm run dev` | Start the Vite dev server (HMR, /api proxy). |
| `npm run build` | Typecheck + production build to `dist/`. |
| `npm run preview` | Preview the production build locally. |
| `npm run typecheck` | `tsc --noEmit` (strict). |
| `npm run lint` | ESLint flat config, `--max-warnings=0`. |
| `npm test` | Vitest unit + integration tests (jsdom). |
| `npm run test:watch` | Vitest in watch mode. |
| `npm run test:e2e` | Playwright E2E tests (real backend required — see below). |
| `npm run openapi:check` | Generate `contracts.gen.ts` from OpenAPI + drift-check vs `contracts.ts`. |
| `npm run openapi:check -- --write` | Regenerate `contracts.gen.ts` (after a backend schema change). |

## Architecture

```
src/
  api/
    contracts.ts              # Hand-maintained typed contracts (imports the gen file)
    contracts.gen.ts          # AUTO-GENERATED from openapi.json (do not edit)
    client.ts                 # Credentialed fetch wrapper + ApiError
    endpoints.ts              # One typed function per API operation
    ConnectivityContext.tsx   # Health/live + health/ready state machine
  auth/
    csrf.ts                   # Read the peiars_csrf cookie; build header
    AuthContext.tsx           # login / logout / restore state machine
  components/
    StatusPill.tsx            # Reusable connectivity/status pill
    DeferredPanel.tsx         # "Not available in this release" panel
    ErrorPanel.tsx            # Sanitized error display + Retry
    Loading.tsx               # aria-busy loading indicator
    EmptyState.tsx            # Centered empty-state message
    ConnectivityUncertaintyPanel.tsx  # Full-bleed /auth/me failure panel
  layout/
    AppShell.tsx              # Vertical stack: identity + switcher + context + composition + footer
    IdentityBar.tsx           # PEIARS mark + env + connectivity + user + Sign out
    WorkspaceSwitcher.tsx     # Horizontal tab list (WAI-ARIA tabs)
    ContextStrip.tsx          # Workspace H1 + breadcrumb
    ProvenanceFooter.tsx      # API status + version + git commit
    DesktopGate.tsx           # Width-restriction panel (< 1024px)
    workspaces.ts             # Canonical workspace metadata
  pages/
    LoginPage.tsx             # CSRF bootstrap + login form (unchanged)
    OverviewPage.tsx          # Research index: workflow map + streams + status
    DataPage.tsx              # Three-column: filter rail + source table + inspector
    AnalysisPage.tsx          # Four-region workbench: params + canvas + inspector + records
    InvestigationsPage.tsx    # Three-column casebook: index + evidence + assessment
    DomainsPage.tsx           # Comparison axis + three columns + comparability matrix
    ResearchPage.tsx          # Two-column: methodology + artifact sidebar
    NotFoundPage.tsx          # 404
  routes/
    index.tsx                 # Route tree
    RequireAuth.tsx           # Auth guard (loading/anonymous/unknown/authenticated)
  styles/
    tokens.css                # CSS custom properties (color, type, spacing, shell layout)
    global.css                # Base reset + shared utility classes (.panel, .def-list, .data-table, etc.)
  utils/
    title.ts                  # Per-route document.title helper
  main.tsx                    # Mount point
  App.tsx                     # Providers + BrowserRouter
```

## Authentication (unchanged)

The frontend preserves the full PR-04 session workflow:
- **Login** (`POST /auth/login`): CSRF bootstrap + `X-CSRF-Token` header.
- **Session restoration** (`GET /auth/me`): 200 → authenticated; 401 → anonymous; network error → `unknown` (not silent logout).
- **Logout** (`POST /auth/logout`): CSRF header; clears state only on 200/401.
- **Roles**: `viewer < reviewer < admin`. Backend authorization is authoritative.

The session token is **never** in React state or localStorage. It lives only in the HttpOnly cookie.

## OpenAPI contract checking (strengthened)

The `npm run openapi:check` script now:
1. Reads `backend/contracts/openapi.json`.
2. Generates `src/api/contracts.gen.ts` (reproducible TypeScript from the OpenAPI component schemas).
3. Compares the generated file's SHA-256 against the committed `contracts.gen.ts`; reports drift.
4. Cross-checks every OpenAPI-required field against the hand-maintained `contracts.ts`; reports missing fields.

To regenerate after a backend schema change:
```bash
npm run openapi:check -- --write
```

## E2E tests

The Playwright E2E suite (`playwright/e2e.spec.ts`) runs against the real
backend + real PostgreSQL + real Chromium. The helper script
`scripts/run-e2e.sh` starts a disposable `pgserver`-backed PostgreSQL,
applies migrations, creates a synthetic reviewer user, starts the backend
and Vite, runs the tests, and tears everything down.

```bash
bash scripts/run-e2e.sh
```

See `TEST_REPORT.md` for the PR-05A-era E2E report and screenshots
(historical record, not updated per delivery); current verification
results are documented in the latest delivery report (PR-06A correction:
18 E2E tests passed).

## Known limitations

- **Desktop-only.** No mobile layout. Below 1024px the DesktopGate replaces the composition.
- **Backend CORS allows GET/OPTIONS only.** The dev Vite proxy sidesteps; production assumes same-origin (PR-06+).
- **No public case API yet.** Investigation Workspace shows honest deferred panels. Case CRUD arrives in PR-05B.
- **No research-evidence service yet.** Anomaly Analysis shows a deferred canvas. Phase 3–6 figures are not exposed through the API.
- **No administrator-management UI.** The bootstrap CLI is the only provisioning path.
- **Backend baseline discrepancy.** The actual checkout's `app/core/config.py` does NOT contain the fail-closed production-cookie validators from the prior PR-04 hardening ZIP. This is an integration blocker; the frontend does not modify backend auth/security logic. See `TEST_REPORT.md` §6.
- **CORS env var format**: `PEIARS_CORS_ORIGINS` must be a JSON array string under pydantic-settings 2.13.

## Stopping boundary

PR-05A redesign only. No PR-05B (case management UI), PR-06 (Docker/CI), or PR-07 (E2E research-evidence flow) is included.
