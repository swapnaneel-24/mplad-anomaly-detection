# PR-07A Baseline Audit (Stage 1 + Stage 2)

**Milestone:** PR-07A — Adversarial Reliability and Security Hardening
**Stage:** 1 (Baseline verification) and 2 (Coverage audit) only.
**No production code or tests were modified.** A dedicated development branch
was created and left untouched pending approval.

---

## 1. Exact Git baseline

Mandated commands, executed in the authoritative checkout
(`/home/z/my-project/pr07a-work/peiars-baseline`):

| Command | Result |
|---|---|
| `git status --short` | (empty — clean working tree) |
| `git branch --show-current` | `pr-07a-dev` (created from `main`; see below) |
| `git rev-parse HEAD` | `21761408f31d6c0e9ff4ff502c0c98f0897f79cd` |
| `git log -1 --oneline` | `2176140 fix(ci): align serve.py boot contract, E2E repo path, and LF frozen hashes` |

**Verification of `2176140`:**

- `git ls-remote` shows `refs/heads/main` and the dereferenced
  `refs/tags/pr-06b-accepted` both at `21761408f31d6c0e9ff4ff502c0c98f0897f79cd`.
  The baseline commit **is present and is the head of `main`**.
- Baseline state checks: PR-06B artifacts present (`backend/Dockerfile`,
  `frontend/Dockerfile`, `compose.yaml`, `ci/`, `.github/workflows/ci.yml`,
  `.env.compose.example`, `frontend/nginx/default.conf`) **including all
  three PR-06B audit corrections** (migrate on `peiars-net`; no fixed
  `name: peiars_pgdata`; `$http_host`; smoke-test `--env-file` + `exec -T`).
- Development branch `pr-07a-dev` created from the verified baseline.
- **Note on the sandbox:** the pre-existing local working tree
  (`pr05b-work/repo`) is not a git checkout of the PEIARS repository. The
  authoritative baseline was therefore fetched fresh from GitHub (shallow,
  sparse: `backend/ frontend/ ci/ .github/ docs/ src/ tests/ scripts/` +
  root files) and all evidence below was produced against that checkout.
  No old PR-05B/PR-06A ZIP reconstructions were used.
- Maintainer delta vs the PR-06A tree previously audited:
  `backend/app` is byte-identical; `backend/scripts/serve.py` was condensed
  by the maintainer (docstring/comment reduction only — the import-time
  Windows selector-loop install, `.env` loading with `override=False`, and
  `Settings()` flow are preserved); `frontend/scripts/run-e2e.sh` is
  identical; frozen hashes were regenerated for LF endings (verified below).

## 2. Baseline verification results (executed in this sandbox, 2026-11-13)

| Check | Command | Result |
|---|---|---|
| Backend suite | `cd backend && python -m pytest -q` | **550 passed** (44.03s; real pgserver PostgreSQL) |
| Frontend typecheck | `npm run typecheck` | PASS |
| Frontend lint | `npm run lint` (`--max-warnings=0`) | PASS |
| Frontend Vitest | `npm run test -- --run` | **105 passed** (19 files, 18.34s) |
| Frontend build | `npm run build` | PASS |
| OpenAPI drift | `npm run openapi:check` | PASS ("no drift") |
| Browser E2E | `bash frontend/scripts/run-e2e.sh` (disposable pgserver) | **18 passed** (33.3s) |
| Frozen research integrity | `python ci/check_frozen_integrity.py` | **28/28 match** (exit 0) |

All reference baselines (550 / 105 / 18 / 11-check container smoke / 28) are
reproduced except container smoke, which requires Docker (see §6). One
environmental note: the first E2E attempt failed on a missing Playwright
browser binary (`chromium_headless_shell-1254` not cached in this sandbox);
after `npx playwright install chromium` the suite passed 18/18. That failure
was environmental, not an application defect.

**Docker-dependent verification: NOT RUN in this sandbox (no Docker daemon).**
Per the contract, YAML parsing is not claimed as evidence of container
networking or runtime behavior. Compose-level restart/recovery (workstream I
at the container level) will be marked NOT RUN unless executed on a
Docker-equipped environment; a backend-level restart/recovery strategy that
does not require Docker is proposed in the test matrix.

## 3. Relevant files and functions

### Backend

| Area | File | Key functions / facts |
|---|---|---|
| App factory / lifecycle | `backend/app/main.py` | `create_app`; DB config fail-closed; engine dispose on shutdown; CORS explicit origins |
| Case mutations | `backend/app/services/review_cases.py` | `create_case`, `add_note`, `transition_status`, `record_decision` — each one transaction: case write + event insert commit atomically |
| Optimistic concurrency | `backend/app/repositories/review_cases.py` | `update_case_status` / `bump_case_version`: single-statement `UPDATE ... WHERE id=:id AND version=:expected`; rowcount 0 → `ConcurrencyConflictError` |
| Event append | same | `insert_event` (flush, no commit); `list_events` ordered by `case_version, event_seq, id` |
| Event schema | `backend/app/db/models/case_event.py` | `event_seq BIGINT IDENTITY`; CHECK on event_type; FK `ondelete=RESTRICT`; composite indexes |
| Append-only enforcement | `backend/migrations/versions/0001_*.py` | `enforce_case_events_append_only()` trigger rejecting UPDATE/DELETE (`trg_case_events_no_update`, `trg_case_events_no_delete`) — real, and tested |
| Actor attribution | `backend/app/api/v1/cases.py` | `actor_ref_from_principal(principal)` overwrites the request-body `actor_ref`/`created_by` with the authenticated user UUID |
| RBAC | `backend/app/api/v1/cases.py` | every mutation route: `Depends(require_csrf) + Depends(require_role(Role.REVIEWER, Role.ADMIN))` |
| Sessions | `backend/app/services/auth.py` | `login` (fresh session, fixation prevention), `logout` (sets `revoked_at`), `validate_session` (revocation → absolute TTL → idle timeout → active user, all server-side) |
| Cookies | `backend/app/auth/cookies.py` | session cookie: `HttpOnly`, `Secure` (config), `SameSite=Lax`, `Path=/`, no `Domain`; CSRF cookie intentionally readable |
| CSRF | `backend/app/auth/tokens.py`, `backend/app/auth/dependencies.py` | signed double-submit `{random}:{HMAC-SHA256}`; `require_csrf`: constant-time compare + signature verify + Origin defence-in-depth against `cors_origins ∪ {request.base_url}` |
| Readiness | `backend/app/services/db_readiness.py` | `postgresql` (SELECT 1) + `migrations` (`alembic_version` == committed head) probes, read-only, sanitized 503 |
| Config | `backend/app/core/config.py` | `env_prefix="PEIARS_"`; production + `session_cookie_secure=false` rejected by model validator; placeholder-secret markers rejected |

### Frontend

| Area | File | Key functions / facts |
|---|---|---|
| Index refresh | `frontend/src/pages/InvestigationsPage.tsx:108-141` | `refreshIndex`: `indexGenRef` generation counter; stale success AND stale failure discarded; `loadingIndex` cleared only by latest generation; non-stale errors re-thrown for callers |
| Selection loading | same, `:154-226` | `selectionGenRef` incremented on selection change; detail/history/evidence all generation-guarded; nested evidence GET guarded separately; `AbortController` cleanup on unmount/re-selection |
| Mutations | same, `:232-435` | `handleCreateCase/AddNote/Transition/Decision`: `Promise<boolean>`; POST is the sole success criterion; draft cleared only on confirmed success; post-success sync GETs are non-blocking with sync warnings; 409 → `conflictVersion` |
| Recovery | same, `:437-481` | `handleRefreshHistory` (generation-guarded), `handleRefreshCaseList`, `handleReloadAfterConflict` (**not generation-guarded — see §7**) |
| HTTP client | `frontend/src/api/client.ts` | credentialed same-origin `/api/v1`; distinct network/timeout/abort classification; **no retry logic anywhere** (verified by grep) |

### Infrastructure

`compose.yaml` (4 services on `peiars-net`; project-scoped volume;
profile-gated `migrate`), `ci/container_smoke_test.sh` (11 checks; `--env-file`
+ `-T`; real case write/read-back), `.github/workflows/ci.yml` (5 jobs,
least-privilege `contents: read`, SHA-pinned actions), pgserver-backed test
fixtures (`backend/tests/conftest.py`), `frontend/scripts/run-e2e.sh`
(disposable pgserver per run).

## 4. Existing guarantees (implementation-level, code-verified)

1. **Index-refresh races:** only the newest `refreshIndex` generation may
   write `records`, `cases`, `indexError`, or clear `loadingIndex`
   (`InvestigationsPage.tsx:112-139`). Stale failures are discarded *before*
   the re-throw, so a superseded failed refresh cannot raise a false sync
   warning in its caller.
2. **Selection races:** all Region-2 reads are `selectionGenRef`-guarded;
   evidence (nested) has its own guard; unmount/re-selection aborts via
   `AbortController` and aborted errors never set error state.
3. **Optimistic concurrency:** atomic single-statement CAS
   (`UPDATE ... WHERE version=:expected`) — PostgreSQL row locking serializes
   competing updates; the loser sees rowcount 0 → 409, transaction rolls
   back, no event written.
4. **Atomic case+event writes:** service methods commit case mutation and
   event(s) in one transaction; `record_decision` writes up to two events at
   one `case_version`, ordered by database `event_seq` (IDENTITY, cannot be
   application-overridden).
5. **Append-only history:** database trigger rejects UPDATE/DELETE on
   `case_events` (migration 0001); no PUT/PATCH/DELETE routes exist anywhere
   in the API (grep-verified); event timestamps/types are server-generated.
6. **Trusted attribution:** `actor_ref` is overwritten from the
   authenticated principal; request-body values are ignored.
7. **Sessions:** server-side revocation, absolute TTL, and idle timeout
   enforced from DB state on every request; fresh session per login
   (fixation prevention); disabled users lose access immediately.
8. **Cookies:** session cookie `HttpOnly` + `SameSite=Lax` + `Secure`
   (production); CSRF cookie intentionally readable (double-submit design);
   max-age tied to server TTL.
9. **CSRF:** signed double-submit with constant-time HMAC verify plus Origin
   defence-in-depth; login rotates the CSRF token.
10. **RBAC:** all case mutations require reviewer/admin via server-side
    dependencies; viewer/anonymous rejection tested.
11. **Readiness:** PostgreSQL connectivity + migration-head probes with
    sanitized 503; liveness independent of DB.
12. **Config fail-closed:** production + insecure cookies rejected; placeholder
    secrets rejected (tests in `test_env_boot.py` drive this through
    `monkeypatch.setenv`, i.e. the real env-loading path).
13. **No automatic retries:** the client has no retry logic; uncertain
    POST outcomes (network/timeout) preserve drafts and surface a distinct
    message (`mutation-reliability.test.tsx` covers the timeout case).

## 5. Existing test coverage (mapped)

| Area | Existing tests (file → coverage) |
|---|---|
| A index races | `index-refresh-race.test.tsx` (2 tests — **quality defect, see §6**), mount/retry error paths in `async-state-safety.test.tsx` |
| B selection races | `async-state-safety.test.tsx`: delayed history GET (B1, partial), delayed detail GET (B1) — **B2/B3/B4 not covered** |
| C concurrency | `test_database_transactions.py`: stale update → conflict, no duplicate event, no lost update, independent-session conflict (**sequential — see §6**) |
| D events | `test_event_ordering.py` (ordering, seq monotonicity, two-event decisions), `test_case_history.py` (DB-level UPDATE/DELETE rejected, ORM rejected), `test_database_transactions.py` (rollback atomicity) |
| E write semantics | `mutation-reliability.test.tsx`: POST 200 + GET 503 (note/transition/decision/create), POST 409/422/403 draft preservation, POST timeout (uncertain), repeated-click single POST, sync-retry sends no second POST; E2E #13/#15 |
| F sessions | `test_auth_sessions.py` (expired/idle/revoked/disabled 401, logout replay), `test_auth_cookies.py` (attributes, production policy, dev relaxation, max-age), `test_env_boot.py` (env-loading production rejection) |
| G RBAC | `test_auth_rbac.py` (permission matrix, anonymous 401, dependency gates), `test_case_api.py` (`test_viewer_cannot_create_case`, `test_viewer_cannot_add_note`), `test_no_public_case_endpoints.py` (anonymous rejection) |
| H CSRF/Origin | `test_auth_csrf.py` (missing/incorrect/mismatched/unsigned tokens 403, cross-origin rejected on login, same-origin + CORS-origin allowed), E2E #11 |
| I restart | **no coverage** (nothing exercises process restart or DB outage/recovery against a live app) |
| J readiness | `test_db_readiness.py` (all probe states), `test_failure_classification.py` (connection refused, wrong password via disposable SCRAM fixture, unmigrated DB, older revision, upgrade restores readiness) |
| K synthetic boundary | `test_source_registry.py` (empty default, no filesystem access, id validation), `test_case_api.py` (record-ref validation, spoofed dataset rejected), SYNTHETIC banner + "NOT A RESEARCH FINDING" copy in the UI, frozen integrity job |

## 6. Gaps in coverage (the genuine list)

**Test-quality defects (tests exist but do not test what they claim):**

1. **A1/A2 — the "race" tests do not race.**
   `index-refresh-race.test.tsx` test 1 is *sequential*: the first call's
   503 **settles** (error panel rendered) before Retry starts the second
   call, so the stale-failure-discard branch (`indexGenRef.current !== gen`
   in the catch) is never exercised. Test 2's own source comments record an
   abandoned design ("This test design doesn't work… The first call already
   resolved. This test verifies the basic path.") — the deferred promise is
   resolved *before* the second request, so no overlap ever exists. The
   contract's suspicion is confirmed: **no existing test keeps request A
   pending while B starts and then resolves A last.**
2. **B tests use arbitrary sleeps.** `async-state-safety.test.tsx` uses
   `setTimeout(50)`/`setTimeout(100)` waits — the exact pattern the contract
   prohibits for race orchestration.
3. **C1 is sequential.** `test_genuine_independent_sessions_conflict`
   commits session 1's update, *then* attempts session 2's stale write. No
   barrier, no threads, no genuinely competing transactions, and no HTTP
   layer (service-level only). "Do not rely on issuing requests
   sequentially" — currently relied upon.

**Missing coverage (no test exists):**

4. **B2** — delayed *source-evidence* GET for a previous selection.
5. **B3** — stale *conflict-recovery* response (see §7: suspected defect).
6. **B4** — unmount with pending requests (no unhandled rejection /
   post-unmount state corruption assertion).
7. **A3** — superseded-refresh sync-warning semantics (stale failure must
   not set/clear warnings; only an applied refresh may).
8. **C1 (HTTP-level)** — two authenticated reviewers, same version,
   barrier-synchronized competing requests, exactly one 200/201 + one 409,
   event count/version agreement.
9. **C3** — repeated stale mutation stays 409 without authorized retry.
10. **D4 (HTTP-level)** — no event-mutation routes (405/404 method
    contract) — DB-level rejection is tested, route-level absence is not
    asserted by name.
11. **D5** — history persistence across a backend restart (in-process app
    recreation or subprocess).
12. **E1 server-side** — "only one note event exists" after POST-success +
    GET-failure + recovery (frontend mock coverage exists; DB-level count
    does not).
13. **G4/G5** — viewer direct-API transition and decision rejection (create
    and note are tested; transition/decision are not, by test name).
14. **G9 (case routes)** — anonymous case-mutation rejection is asserted in
    `test_no_public_case_endpoints.py` (route existence class) — verify it
    covers each mutation verb; otherwise add.
15. **H4** — pre-login CSRF token replayed after login rotation is rejected
    (rotation is exercised implicitly, the replay is not asserted).
16. **H5/H7 (authenticated)** — cross-origin rejection on an *authenticated*
    case mutation with otherwise-valid CSRF (the existing test uses login,
    i.e. pre-authentication), and rejection leaving version/event count
    unchanged.
17. **I1-I8** — no restart, DB-outage, or recovery coverage at all.
18. **F5** — post-login rotated CSRF token requirement for subsequent
    writes is implicit in E2E but not unit/integration-asserted.
19. **K6** — with demonstration sources disabled, no alternative endpoint
    exposes synthetic records (source registry empty-state is tested;
    endpoint-level sweep is not).

## 7. Confirmed defects, if any

**No production defect is CONFIRMED at audit stage** (confirming requires
the Stage 3 RED demonstration per the contract's discipline). One strong
**suspected defect** is identified:

> **SUSPECTED PR07A-D1 (Workstream B3):** `handleReloadAfterConflict`
> (`frontend/src/pages/InvestigationsPage.tsx:464-481`) lacks the
> `selectionGenRef` generation guard that every other async read path has
> (`handleRefreshHistory` guards at `:441-447`; the selection effect guards
> at `:175-217`). It unconditionally calls `setCaseDetail(detail)`,
> `setHistory(hist)`, and `setLoadingDetail(false)` after awaiting
> `getCase` + `getCaseHistory`. If the user clicks "Reload latest version"
> (after a 409) and then selects a different case before the recovery GETs
> return, the delayed recovery response can overwrite the newly selected
> case's detail and history and clear its loading state — exactly scenario
> B3.
>
> **Planned handling:** write the deterministic deferred-promise test first
> (select Case A → force 409 → click reload → select Case B → resolve B →
> resolve A's recovery GETs → assert B remains). Expected: RED. Then apply
> the smallest correction (capture `selectionGenRef.current` at handler
> start; guard the three setters), rerun the same test to GREEN, then the
> surrounding suites. If the test unexpectedly passes, record
> BASELINE GREEN and no production change is made.

### 7.1 Precise source lines and overwrite mechanism (PR07A-D1)

**File:** `frontend/src/pages/InvestigationsPage.tsx` (baseline `2176140`).
All line numbers verified against the checkout in
`/home/z/my-project/pr07a-work/peiars-baseline`.

**A. The selection-generation counter and its bump on selection change
(`:154-156`):**

```tsx
  useEffect(() => {
    selectionGenRef.current += 1;
  }, [selection]);
```

Every selection change (record pick or case pick) increments
`selectionGenRef.current`. This is the stamp every guarded async read path
captures at start and re-checks before applying results.

**B. The guarded selection-load effect (`:158-221`, abridged to the case
branch):**

```tsx
  useEffect(() => {
    const gen = selectionGenRef.current;                 // :163 capture
    if (selection.kind === "case" && selection.caseId) {
      const caseId = selection.caseId;
      setLoadingDetail(true);
      // ...
      (async () => {
        try {
          const [detail, hist] = await Promise.all([
            getCase(caseId, controller.signal),
            getCaseHistory(caseId, controller.signal),
          ]);
          if (selectionGenRef.current !== gen) return;   // :202 stale-discard
          setCaseDetail(detail);
          setHistory(hist);
          // ... nested evidence GET, also gen-guarded at :207 ...
        } catch (err) {
          if (err instanceof ApiError && err.aborted) return;
          if (selectionGenRef.current !== gen) return;   // :214 stale-discard
          setDetailError(err instanceof ApiError ? err : null);
        } finally {
          if (selectionGenRef.current === gen && !controller.signal.aborted)
            setLoadingDetail(false);                     // :217 guarded clear
        }
      })();
      return () => controller.abort();
    }
    // ...
  }, [selection]);
```

Note the three guard sites at `:202`, `:207`, `:214`, and the guarded
`setLoadingDetail(false)` at `:217`. A response whose captured `gen` no
longer equals `selectionGenRef.current` is discarded before any setter
runs.

**C. The guarded `handleRefreshHistory` (`:439-451`) — the recovery
sibling that DOES it right:**

```tsx
  const handleRefreshHistory = useCallback(async () => {
    if (!caseDetail) return;
    const currentGen = selectionGenRef.current;          // :441 capture
    try {
      const hist = await getCaseHistory(caseDetail.id);
      if (selectionGenRef.current === currentGen) {      // :444 guard
        setHistory(hist);
        setHistorySyncWarning(false);
      }
    } catch {
      // Warning stays; the user can retry.
    }
  }, [caseDetail]);
```

**D. The unguarded `handleReloadAfterConflict` (`:464-481`) — the
suspected defect:**

```tsx
  const handleReloadAfterConflict = useCallback(async () => {
    if (!caseDetail) return;
    setMutationError(null);
    setConflictVersion(null);
    setLoadingDetail(true);
    try {
      const [detail, hist] = await Promise.all([
        getCase(caseDetail.id),                          // :471 — no signal
        getCaseHistory(caseDetail.id),                   // :472 — no signal
      ]);
      setCaseDetail(detail);                             // :474 — UNGUARDED
      setHistory(hist);                                  // :475 — UNGUARDED
    } catch (err) {
      setDetailError(err instanceof ApiError ? err : null);
    } finally {
      setLoadingDetail(false);                           // :479 — UNGUARDED
    }
  }, [caseDetail]);
```

There is **no capture of `selectionGenRef.current` at handler entry** and
**no guard around the three setters** at `:474`, `:475`, `:479`. Contrast
with the guarded sibling at `:441`/`:444` and the selection effect at
`:163`/`:202`/`:217`. The handler also passes no `AbortController` signal
to `getCase`/`getCaseHistory`, so the requests are neither cancelled nor
generation-checked on resolution.

**Overwrite mechanism — how a stale recovery response clobbers a newly
selected case (scenario B3):**

1. User selects **Case A**. The selection effect runs: captures
   `gen = N`, sets `loadingDetail = true`, starts `getCase(A)` and
   `getCaseHistory(A)`. Both resolve; `caseDetail` now holds Case A.
2. User adds a note; the POST returns **409** (version conflict — another
   reviewer updated Case A). `conflictVersion` is set; the conflict banner
   renders with a "Reload latest version" button.
3. User clicks "Reload latest version". `handleReloadAfterConflict` runs:
   it reads `caseDetail.id` (still Case A), sets `loadingDetail = true`,
   and awaits `Promise.all([getCase(A), getCaseHistory(A)])`. **These two
   GETs are now in flight with no generation stamp and no abort signal.**
4. Before those GETs resolve, the user selects **Case B** from the index.
   The selection effect runs again: `selectionGenRef.current` is
   incremented to `N+1`; the effect captures `gen = N+1`, sets
   `loadingDetail = true`, clears `caseDetail`/`history`, and starts
   `getCase(B)` + `getCaseHistory(B)` (with a fresh `AbortController`).
5. Case B's GETs resolve. The `:202` guard passes
   (`gen === N+1 === selectionGenRef.current`); `setCaseDetail(B)` and
   `setHistory(B)` run. The UI now shows Case B.
6. **Case A's recovery GETs (from step 3) resolve last.** Because
   `handleReloadAfterConflict` captured no generation and checks none
   before `:474`/`:475`/`:479`, the handlers run unconditionally:
   - `setCaseDetail(A)` — **overwrites Case B's detail with Case A's**.
   - `setHistory(A)` — **overwrites Case B's history with Case A's**.
   - `setLoadingDetail(false)` (in `finally`) — **clears the loading
     spinner even though the user is now looking at Case B**, which may
     itself still be loading or have just finished; at minimum the
     loading state is now inconsistent with the displayed case.

   The user is left viewing Case A's stale detail and history under what
   they believe is Case B's selection — a silent data-integrity
   corruption in an evidence-review workbench. There is no error, no
   banner, no log; the conflict-recovery path appears to have succeeded.

**Why the existing tests miss it:** E2E #13 exercises the happy path
(click reload → GETs resolve → Case A reloaded) with no selection change
between the click and the resolution, so the unguarded setters happen to
apply to the still-current case. No Vitest test holds the recovery GETs
pending across a selection change. The B3 row of the test matrix is the
planned deterministic demonstration.

**Scope of the suspected fix (NOT applied at audit stage):** capture
`const currentGen = selectionGenRef.current;` at `:465` (handler entry,
after the `if (!caseDetail) return` guard) and wrap the three setters at
`:474`/`:475`/`:479` in `if (selectionGenRef.current === currentGen) { … }`
— a 3-line change mirroring `handleRefreshHistory` at `:441`/`:444`. No
state-architecture rewrite, no new abort signal required (the guard alone
prevents the stale apply). This is contingent on Stage 3 demonstrating
RED against baseline.

Additionally, the four test-quality defects in §6 items 1-3 are defects in
*tests* (they do not exercise their claimed race), not in production code.

## 8. Proposed minimal corrections

1. **PR07A-D1 (only if RED is demonstrated):** add the generation guard to
   `handleReloadAfterConflict` (3-line change mirroring
   `handleRefreshHistory`). No state-architecture rewrite.
2. No other production changes are proposed. Every other workstream is
   expected to be BASELINE GREEN; the work is deterministic test
   development, not repair. Per the contract, the absence of a test is not
   proof of a production defect, and no production code will be modified
   except upon a demonstrated RED.

## 9. Tests needed to prove each guarantee

See `PR07A_TEST_MATRIX.md` for the complete per-scenario plan, including
the exact deterministic mechanisms (deferred promises, `threading.Barrier`,
test-owned session-row manipulation for controlled expiry, subprocess
uvicorn + disposable pgserver stop/start for restart/recovery with
health-state polling under a bounded deadline) and the target suite for
each. Summary of placement:

- **pytest (backend):** C1/C3 (HTTP-level barrier race), D4 route contract,
  D5 restart persistence, E1 server-side event count, G4/G5/G9, H4/H5/H7,
  I-series (subprocess restart/outage/recovery), K6 endpoint sweep.
- **Vitest (frontend):** A1/A2/A3 (true deferred-promise overlap), B1-B4
  (deferred promises, no sleeps), F-adjacent UI states already covered;
  E-series additions if gaps emerge.
- **Playwright:** only if a browser-level guarantee cannot be established in
  Vitest (planned: none new; existing 18 preserved).
- **CI:** all new tests join the existing five jobs; no new jobs; no
  `continue-on-error`; permissions unchanged.

**Runtime impact estimate:** frontend additions ≈ 5-10s; backend
concurrency (threads + barrier) ≈ 2-5s; the restart/recovery subprocess
test is the only material cost (≈ 20-40s) and will be kept as a single
module with a bounded deadline loop (no sleeps) inside the existing
backend job — justification recorded in the matrix.

## Stage gate

Stage 1 and Stage 2 are complete. **Awaiting approval before Stage 3
(test development) and Stage 4 (minimal corrections).** No production or
test files have been modified on `pr-07a-dev`.
