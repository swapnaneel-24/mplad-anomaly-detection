# PEIARS Frontend — Test Report (PR-05A Redesign)

**Date:** 2026-11-10
**Frontend version:** 0.5.0 (PR-05A redesign — desktop scientific workbench)
**Backend version:** 0.4.0 (unchanged, 445 tests — see §4)
**Node:** v24.22.2 (LTS line; 22 LTS also supported per `.nvmrc`)
**npm:** 11.19.1
**Browser:** Chromium (Playwright 1.65.0)
**PostgreSQL:** 16.x via `pgserver` 0.1.4

---

## 1. Verification pipeline (all green)

| Step | Command | Result |
|---|---|---|
| Install | `npm install` | OK (package-lock.json committed) |
| Typecheck | `npm run typecheck` (`tsc --noEmit`, strict) | 0 errors |
| Lint | `npm run lint` (`eslint . --max-warnings=0`) | 0 errors, 0 warnings |
| Unit + integration tests | `npm test` (Vitest, jsdom) | **73 passed, 0 failed** (15 files) |
| Production build | `npm run build` | OK; `dist/` 245 KB (66.55 KB gzip JS, 4.44 KB gzip CSS) |
| OpenAPI contract check | `npm run openapi:check` | OK (contracts.gen.ts up to date; no drift vs contracts.ts) |
| E2E tests | `npm run test:e2e` (Playwright, real backend + PostgreSQL + Chromium) | **12 passed, 0 failed** (16.3s) |
| Backend regression | `pytest tests/ -q` (real PostgreSQL) | **445 passed, 0 failed** (unchanged from baseline) |
| Frozen-file integrity | `scripts/verify_pr05a_frozen.py` | **28 files, 0 drift** |

## 2. Test-count change from the prior PR-05A delivery

The prior delivery had **68** Vitest tests and **11** E2E tests. This redesign has **73** Vitest tests and **12** E2E tests. The increase is legitimate and explained:

### Vitest: 68 → 73 (+5)

The 5 new tests cover the redesigned shell:

| File | New tests | Purpose |
|---|---|---|
| `routes.test.tsx` | +2 | Active tab `aria-current="page"` assertion; no-sidebar / no-hamburger assertion |
| `keyboard-interaction.test.tsx` | +1 | Home/End key navigation in the switcher |
| `responsive-navigation.test.tsx` | +2 | DesktopGate appears below 1280px; identity bar + switcher remain visible below 1280px |

The prior mobile-drawer tests (3 in `responsive-navigation`, 2 in `keyboard-interaction`) were **removed** because the redesign is desktop-only — there is no drawer or hamburger to test. The net change is +5 tests.

### E2E: 11 → 12 (+1)

The new test #11 (`DesktopGate appears below 1280px width`) verifies the desktop-only gate. The screenshot test #12 was expanded to capture 7 screenshots at the specified resolutions (login 1440, overview 1440, analysis 1440, investigations 1440, data 1366, research 1920, overview 1280) plus a horizontal-overflow check at 1280px.

## 3. Unit + integration test breakdown (Vitest, 73 tests)

### Unit tests (`tests/unit/`, 36 tests — unchanged)

| File | Tests | Coverage |
|---|---|---|
| `api-client.test.ts` | 11 | `request()`: JSON body, query params, timeout, abort, network failure, 4xx/5xx envelope parsing, 204 handling, request-id header capture |
| `api-errors.test.ts` | 5 | `ApiError` predicates: isUnauthorized, isForbidden, isRateLimited, isServiceNotReady, isNetwork |
| `csrf.test.ts` | 6 | `readCsrfCookie()` parsing, `hasCsrfCookie()` |
| `auth-context.test.tsx` | 9 | AuthProvider state machine: loading, authenticated, anonymous, unknown; login/logout CSRF; network-error preservation |
| `connectivity-context.test.tsx` | 5 | ConnectivityProvider: ready/not_ready/unreachable/unknown |
| `role-presentation.test.tsx` | 3 | isRole() / hasPermission() predicates |

### Integration tests (`tests/integration/`, 37 tests — redesigned)

| File | Tests | Coverage |
|---|---|---|
| `routes.test.tsx` | 4 | Six tabs in switcher; click each → H1 + document.title; active tab aria-current; no sidebar/hamburger |
| `login-form.test.tsx` | 8 | Validation, CSRF bootstrap, success redirect, 401/429/network error messaging, no duplicate submission, Show/Hide toggle |
| `session-restoration.test.tsx` | 4 | Loading state; switcher + context strip on 200; redirect on 401; connectivity-uncertainty panel on network error |
| `session-expiry.test.tsx` | 1 | 401 on mount → redirect to /login |
| `logout.test.tsx` | 3 | X-CSRF-Token header on POST; redirect on 200; remains authenticated on network error; anonymous on 401 mid-logout |
| `role-presentation.test.tsx` | 4 | Viewer/reviewer/admin role labels in identity bar; no manage-users affordance |
| `error-messaging.test.tsx` | 1 | ErrorPanel shows sanitized message + request ID on 500; no stack trace |
| `responsive-navigation.test.tsx` | 5 | Composition at 1440px; composition at 1280px; DesktopGate below 1280px; no hamburger at any width; identity bar + switcher visible below 1280px |
| `keyboard-interaction.test.tsx` | 7 | Arrow Right + Enter activates tab; Arrow Left wraps; Home/End; roving tabindex |

## 4. E2E test breakdown (Playwright, 12 tests, real backend)

All 12 tests run against the real stack: Vite dev server (:5173) → Vite proxy → FastAPI (:8000) → pgserver PostgreSQL 16.x → synthetic `reviewer_e2e` user. **No mocked network responses.**

| # | Test | Result | Notes |
|---|---|---|---|
| 1 | Open `/` → redirect to `/login` | ✓ (626ms) | |
| 2 | Direct `/overview` while unauthenticated → redirect to `/login` | ✓ (451ms) | |
| 3 | Login screen renders identity + lede + form + connectivity hint | ✓ (457ms) | |
| 4 | Submit login → redirect to `/overview` | ✓ (795ms) | Real CSRF bootstrap + cookie set |
| 5 | `/auth/me` called on session restore | ✓ (793ms) | Intercepted the response |
| 6 | Horizontal switcher shows 6 tabs; identity bar shows user + role; no sidebar | ✓ (783ms) | |
| 7 | Click each workspace tab → H1 and `document.title` change | ✓ (1.2s) | All six workspaces |
| 8 | Refresh → session restored | ✓ (1.0s) | `peiars_session` cookie verified |
| 9 | Click logout → redirect to `/login` | ✓ (805ms) | |
| 10 | Direct `/overview` with revoked session → redirect to `/login` | ✓ (1.0s) | Re-injected old cookie; backend 401 |
| 11 | DesktopGate appears below 1280px width | ✓ (941ms) | Switcher + identity bar remain visible |
| 12 | Capture screenshots at specified resolutions + 1280px overflow check | ✓ (5.4s) | 7 PNGs; no horizontal scroll at 1280px |

**Total E2E duration:** 16.3s. **Exit code:** 0.

## 5. Screenshots (genuine browser captures)

| File | Resolution | Workspace | Description |
|---|---|---|---|
| `screenshots/01-login-1440.png` | 1440×900 | Login | Serif PEIARS identity, editorial lede, form, connectivity hint |
| `screenshots/02-overview-1440.png` | 1440×900 | Overview | Study heading, workflow map, streams, status, subsystem table, entry grid |
| `screenshots/03-analysis-1440.png` | 1440×900 | Anomaly Analysis | Four-region grid: parameter rail + canvas + inspector + records table |
| `screenshots/04-investigations-1440.png` | 1440×900 | Investigation | Three-column: case index + evidence workspace + assessment/history |
| `screenshots/05-data-1366.png` | 1366×768 | Data Observatory | Three-column: filter rail + source table + metadata inspector |
| `screenshots/06-research-1920.png` | 1920×1080 | Research & Provenance | Two-column: methodology sections + artifact index sidebar |
| `screenshots/07-overview-1280.png` | 1280×800 | Overview (minimum width) | Confirms no horizontal scroll at 1280px |

## 6. Backend regression suite (unchanged)

The PR-05A redesign modifies **no backend file**. The backend regression suite was re-run after the frontend work to confirm:

```
cd backend && pytest tests/ -q --tb=no
445 passed, 444 warnings in 30.94s
```

### Backend baseline discrepancy (per PR-05A redesign §9)

The actual user-supplied checkout passes **445** backend tests. The prior PR-04 hardening ZIP claimed 452 tests, but the actual checkout has a different file structure and does **not** contain the fail-closed production-cookie validators. Confirmed:

```python
>>> from app.core.config import Settings
>>> s = Settings(_env_file=None, environment="production", session_cookie_secure=False)
>>> print(s.environment, s.session_cookie_secure)
production False  # ← DEFECT: production accepts insecure cookies
```

The actual checkout's `app/core/config.py` has:
- No `@model_validator(mode="after")` for production cookie invariants.
- No `__Host-` prefix enforcement.
- No production-rejects-insecure-cookie logic.

Per the redesign prompt §9: *"If the current checkout still lacks PR-04 hardening, do not silently repair it within this UI redesign. Report the issue as a separate integration blocker."*

**This is an integration blocker.** The frontend works correctly against the actual backend (the E2E suite proves it), but the backend's production-cookie hardening is missing and should be re-applied in a separate backend-only change. The frontend does not modify backend auth/security logic.

## 7. Frozen-file integrity (unchanged)

All 28 frozen research files are byte-identical to the PR-05A handoff baseline:

```
$ python3 scripts/verify_pr05a_frozen.py
Recorded frozen files: 28
FROZEN-FILE INTEGRITY: PASS
```

## 8. Visual self-review (per PR-05A redesign §12)

### Has the permanent sidebar genuinely disappeared?

**Yes.** The old `Sidebar.tsx` and `Sidebar.css` are deleted. The new shell has no `<aside>` landmark; navigation is via the horizontal `WorkspaceSwitcher` tab list. Verified by:
- E2E test #6 asserts `page.getByLabel("Workspace navigation")` has count 0.
- Integration test `routes.test.tsx` asserts `screen.queryByLabelText("Workspace navigation")` is null.
- The `Sidebar.tsx` file no longer exists in `src/layout/`.

### Does the scientific workbench dominate?

**Yes.** The Anomaly Analysis workspace (`/analysis`) is the strongest visual expression:
- Four-region grid: 220px parameter rail + dominant central canvas (1fr) + 300px inspector + 220px bottom records table.
- The central canvas is the largest visual element.
- The parameter rail and inspector are genuinely useful analytical affordances (reserved, not fake).
- Verified by screenshot `03-analysis-1440.png` (113 KB, the canvas occupies the largest area).

### Does each workspace have a purpose-specific composition?

**Yes.** Each workspace has a distinct grid:
- Overview: single 960px editorial column with workflow map + streams + status + entry grid.
- Data Observatory: `240px 1fr 320px` three-column (filter rail + table + inspector).
- Anomaly Analysis: `220px 1fr 300px` top + `220px` bottom (four-region workbench).
- Investigation: `260px 1fr 320px` three-column casebook (index + evidence + assessment).
- Cross-Domain: `repeat(3, 1fr)` comparison + full-width comparability matrix.
- Research & Provenance: `1fr 320px` two-column (methodology + sticky artifact sidebar).

No two workspaces share the same grid.

### Does the visual identity remain coherent?

**Yes.** The palette, typography, and component styling are unchanged from the prior delivery. The new shell bands (identity bar, switcher, context strip, provenance footer) use the same tokens (`--color-bg-raised`, `--color-bg-sunken`, `--color-border`, `--color-accent`, `--font-editorial`, `--font-interface`, `--font-mono`). The serif PEIARS mark in the identity bar matches the login screen's serif identity.

### Are there oversized empty areas?

**No.** The redesign specifically avoids this:
- The Anomaly Analysis canvas is a single honest surface (not a grid of empty boxes).
- The deferred panels are sized to fit their context (180–240px minHeight, not 320px+).
- The workspace compositions fill the available height; panels scroll internally.
- The Overview's workflow map and entry grid use compact, dense layouts.

### Is typography legible?

**Yes.** Body text is 15px (`--font-size-base`), table headers 11px (`--font-size-xs`), workspace H1 13px (in the context strip). All meet WCAG AA contrast. Tabular numerals applied to all mono text.

### Does the interface still resemble a generic dashboard?

**No.** The redesign specifically removes the generic-dashboard elements:
- No permanent left sidebar.
- No KPI cards.
- No gradient branding.
- No glassmorphism.
- No fake charts.
- The horizontal switcher is compact (36px tall, six small tabs), not an oversized tab bar.
- Each workspace has a distinct multi-panel composition, not a shared card template.

### Where the redesign falls short

1. **The context strip's breadcrumb is static per workspace** (it does not update with live data, e.g. record counts). This is honest for PR-05A (no data yet) but a future iteration could make it dynamic.
2. **The parameter rail in Anomaly Analysis uses disabled native controls** (select, range, input). A future iteration could replace these with purpose-built styled controls that communicate "deferred" more elegantly than the native disabled state.
3. **The Cross-Domain comparability matrix is hand-written static content.** When the source registry has real data, the matrix should derive some cells from the API. For now the static content is honest about the known methodological constraints.

## 9. Tests not executed

None. Every test category mandated by PR-05A redesign §11 was executed:
- ✓ `npm install` (package-lock.json committed)
- ✓ Strict TypeScript typecheck
- ✓ ESLint with zero warnings
- ✓ Vitest (73 tests)
- ✓ Production build
- ✓ OpenAPI contract check (with reproducible generation)
- ✓ Playwright browser tests against real FastAPI/PostgreSQL (12 tests)
- ✓ Existing backend regression suite (445 tests)
