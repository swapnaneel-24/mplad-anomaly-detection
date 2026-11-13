# PR-07A Test Matrix (Stage 2 deliverable)

Deterministic test strategies for Workstreams A-K, mapped to the mandatory
verification matrix (PR07A-01…36). Statuses in **this document are Stage-2
coverage statuses**, not final verification results: they state whether a
guarantee is currently covered, gapped, or platform-limited. Final
PASS/FAIL/PARTIAL/NOT RUN statuses will be recorded in the Stage-7 delivery
report after execution.

Legend:
- **COVERED** — existing test already establishes the guarantee (re-verified green in the baseline run).
- **QUALITY-GAP** — a test exists but does not genuinely exercise the claimed path (§6 of the audit).
- **GAP** — no test exists.
- **PLANNED** — the deterministic strategy proposed here.
- **DOCKER** — requires Docker/Compose; NOT RUN in this sandbox.

---

## Workstream A — Frontend index-refresh concurrency (Vitest)

| ID | Scenario | Current | Planned deterministic strategy |
|---|---|---|---|
| A1 | Older **successful** response arrives last | **QUALITY-GAP** (test 2 abandoned mid-design; no overlap ever created) | Deferred promises. Mount → capture the mount case-list GET's resolver (A pending). Trigger refresh B (via a mutation's sync refresh or `onRetry`). Assert two distinct GETs started (fetch-mock call count). Resolve B with the newer list (Case B present). Resolve A last with the older list (no Case B). Assert Case B still rendered; no stale `loadingIndex`; no empty-state flash. Negative control: temporarily remove guard in a scratch copy is NOT permitted — instead the test asserts the guard's observable contract; mutation-safety is proven by A2's failure branch sharing the same guard. |
| A2 | Older **failed** response arrives last | **QUALITY-GAP** (test 1 is sequential: the 503 settles before Retry) | Deferred rejection. A pending → B starts → B resolves 200 (Case A) → A rejects with 503 *afterwards*. Assert Case A remains; no error panel; `loadingIndex` false. The stale-discard branch (`indexGenRef.current !== gen` in catch) is what runs — this is the branch test 1 never reached. |
| A3 | Superseded refresh and sync-warning semantics | **GAP** | Two cases: (i) mutation's sync refresh B is superseded by a later refresh C; B rejects stale → assert **no** `indexSyncWarning` set (error discarded before re-throw); (ii) non-superseded refresh rejects → warning **is** set and cleared by a successful manual retry. Deferred promises throughout; no sleeps. |

**Acceptance A:** all three use explicit deferred resolution ordering; zero
`setTimeout`-based race orchestration; assertions on rendered state after
`act()`/`waitFor` flushes.

## Workstream B — Stale case-selection and evidence responses (Vitest)

| ID | Scenario | Current | Planned deterministic strategy |
|---|---|---|---|
| B1 | Stale case detail/history for prior selection | COVERED (partially; uses `setTimeout(50)`) | Re-implement without sleeps: select Case A (GETs deferred), select Case B (resolve immediately), resolve A last; assert B's title/history remain and no A content in panels. |
| B2 | Stale **source-evidence** response | **GAP** | Defer the nested `getSyntheticRecord(detail.record_ref)` for A only (route mock keyed on A's record_ref). Select A → select B (B's evidence resolves) → resolve A's evidence last. Assert B's evidence shown; A's evidence text absent. |
| B3 | Stale **conflict-recovery** response | **GAP** (suspected defect PR07A-D1) | Select Case A → POST note → 409 (mock) → conflict banner visible → click "Reload latest version" (recovery GETs deferred) → select Case B (B's GETs resolve) → resolve A's recovery GETs last. Assert B's detail/history still displayed and B's loading state not cleared. **Expected RED** against baseline; minimal guard fix; GREEN after. |
| B4 | Unmount with pending requests | **GAP** | Select Case A (GETs deferred, never resolved) → unmount → assert no unhandled rejection (install a rejection spy) and no act() warnings; re-mount fresh and select B cleanly (no cross-selection corruption). |

## Workstream C — Optimistic concurrency and HTTP 409 (pytest, real PostgreSQL)

| ID | Scenario | Current | Planned deterministic strategy |
|---|---|---|---|
| C1 | Two reviewers, same version, genuinely competing | **QUALITY-GAP** (existing test is sequential, service-level) | HTTP-level against the pgserver-backed app: create case as reviewer; two `TestClient` sessions (separate cookies); both read version N; `threading.Barrier(2)` releases both POSTs simultaneously (two threads, results collected); assert exactly one 2xx + one 409, final DB version = N+1, exactly one new event, event sequence consistent. The CAS is a single atomic `UPDATE ... WHERE version=:expected`, so exactly-one-winner is the provable invariant. |
| C2 | Stale UI recovery | COVERED (E2E #11/#13 + Vitest 409 draft preservation) | Add Vitest assertion that the reload action issues GETs only (fetch-mock: no second POST) — partially exists ("SYNC RETRY"); extend to the conflict-recovery button. |
| C3 | Repeated stale request | **GAP** | HTTP-level: same stale mutation POSTed twice (same `expected_version`) → both 409; version unchanged; no new events; then authorized retry with fresh version succeeds. |

## Workstream D — Append-only audit events (pytest)

| ID | Scenario | Current | Planned deterministic strategy |
|---|---|---|---|
| D1 | Order + attribution over note/status/decision ops | COVERED (`test_event_ordering`, `test_status_transitions`) | Extend one case: assert each event's `actor_ref` equals the authenticated principal's user UUID (server-side binding), including a request that supplies a spoofed `actor_ref` body field. |
| D2 | Failed mutation → event count unchanged | COVERED (`test_database_transactions` rollback tests) | Re-verify green; add HTTP-level 422 case (illegal transition) with event count assertion. |
| D3 | Rollback atomicity (no partial case/event) | COVERED (`test_rollback_on_constraint_failure...`) | No addition planned. |
| D4 | No event mutation via APIs | PARTIAL (DB-level + ORM-level rejection tested; route-level not asserted) | Assert the OpenAPI contract contains no PUT/PATCH/DELETE on `/cases/**` or `/events/**`, plus live 405/404 probes for the mutation verbs on the history route. |
| D5 | Persistence across backend restart | **GAP** | In-process restart equivalence: create case + events → dispose engine + drop app → construct a fresh `create_app` + engine against the same pgserver DB → assert UUID, version, status, evidence refs, and full event history identical. True process restart is covered by the I-series subprocess test. |
| — | DB-role distinction | Documented | The trigger is real (migration 0001) and tested; the audit notes the app role *can* be granted direct DML by a DBA — the report will state application+trigger-enforced append-only, not superuser-proof (per contract). No schema change proposed. |

## Workstream E — Confirmed POST / failed GET (Vitest + one pytest)

| ID | Scenario | Current | Planned deterministic strategy |
|---|---|---|---|
| E1 | Note POST 200 → history GET 503 | **PASS** (frontend Vitest covers all 11 observable steps across note/transition/decision/create; backend pytest covers the per-mutation single-event invariant AND the full POST→failed-GET→recovery sequence on real PostgreSQL — defect log §6.3) | Done at `d594d06`: integrated `test_confirmed_post_then_failed_get_then_recovery_leaves_exactly_one_event` using an armed one-shot `_IntermittentSessionFactory` wrapper that raises `ApiError(503, SERVICE_NOT_READY)` through the production `_case_service` path. |
| E2 | Transition/decision variants | COVERED (transition + decision + create) | No addition planned. |
| E3 | Confirmed 409/422 rejection | COVERED (409, 422, 403 variants, draft preserved) | No addition planned. |
| E4 | Uncertain outcome (transport failure) | COVERED (timeout test: draft preserved, distinct message; no retry logic exists — grep-verified) | Add explicit assertion: after a network-failed POST, no second POST is issued by any recovery action (fetch-mock call counting), and the UI copy does not claim rejection. |

## Workstream F — Sessions and cookies (pytest; already strong)

| ID | Scenario | Current | Planned deterministic strategy |
|---|---|---|---|
| F1 | Expiry (absolute + idle) | COVERED (`test_expired_session_401`, `test_idle_timeout_401`, `test_absolute_expiry...` — via test-owned session-row manipulation, i.e. controlled clocks, no sleeps) | Re-verify green; add boundary assertion: `expires_at == now` (not just `< now`) rejects. |
| F2 | Logout invalidation (server-side replay) | COVERED (`test_logout_replay_fails`) | No addition planned. |
| F3 | Cookie attributes | COVERED (production policy, dev relaxation, max-age, logout expiry, CSRF readability, no token in JSON) | No addition planned. |
| F4 | Production config rejection | COVERED (`test_env_boot.py` drives `PEIARS_ENVIRONMENT=production` through `monkeypatch.setenv` — the real env-loading path) | No addition planned. |
| F5 | Login/CSRF rotation | PARTIAL (rotation exercised; pre-login replay not asserted) | Covered under H4. |

## Workstream G — RBAC (pytest, real identities)

| ID | Scenario | Current | Planned deterministic strategy |
|---|---|---|---|
| G1 | Viewer allowed reads | COVERED (viewer can read cases/sources) | Re-verify green. |
| G2 | Viewer POST /cases | COVERED (`test_viewer_cannot_create_case`) | Assert also: no DB row + no event (currently status-only). |
| G3 | Viewer POST note | COVERED (`test_viewer_cannot_add_note`) | Same DB+event assertion. |
| G4 | Viewer POST transition | **GAP** | Add test: 403 + no case mutation + no event. |
| G5 | Viewer POST decision | **GAP** | Add test: 403 + no case mutation + no event. |
| G6 | Other mutation routes | N/A-check | Sweep the OpenAPI paths for all non-GET routes; assert every one requires reviewer/admin (contract-level) — covers current + future routes. |
| G7 | Reviewer permitted ops | COVERED (reviewer CRUD path in `test_case_api`) | No addition planned. |
| G8 | Reviewer → admin-only op | PARTIAL (admin gate dependency tested) | Add one HTTP-level test if any admin-only route exists (bootstrap CLI is not HTTP); else record NOT APPLICABLE with justification. |
| G9 | Unauthenticated mutation | PARTIAL | Assert 401 (not 403) for each case mutation verb with no cookies; DB + event unchanged. |

## Workstream H — CSRF and Origin (pytest)

| ID | Scenario | Current | Planned deterministic strategy |
|---|---|---|---|
| H1 | Valid token + same-origin write | COVERED | No addition planned. |
| H2/H3 | Missing/invalid token | COVERED (missing header, missing cookie, incorrect, mismatch, unsigned) | No addition planned. |
| H4 | Pre-login token replayed after rotation | **GAP** | Bootstrap token T1 → login (rotates to T2) → write with T1 → 403; write with T2 → 2xx. |
| H5 | Invalid Origin, otherwise fully authenticated | PARTIAL (existing test uses the pre-auth login endpoint) | New test on POST /cases: valid session + valid CSRF + `Origin: http://evil.example` → 403. |
| H6 | nginx proxied host/port preservation | DOCKER at container level | Backend-level equivalent exists from PR-06B verification (TestClient with `Host: localhost:8080` proved `$http_host` semantics; `$host` port-stripping defect was found and fixed). Compose-level: NOT RUN here; container smoke test covers login/CSRF via proxy when Docker is available. |
| H7 | Rejection leaves version/events unchanged | **GAP** | Wrap H5/H4 assertions: version and event count identical before/after each rejected request. |
| H8 | Dev vs production cookie behavior | COVERED (F3/F4) | No addition planned. |

## Workstream I — Restart and persistence recovery (pytest, subprocess, disposable pgserver)

All against a dedicated pgserver instance owned by the test module; no
shared server is touched.

| ID | Scenario | Current | Planned deterministic strategy |
|---|---|---|---|
| I1 | Backend restart preserves cases/events | **GAP** | Subprocess: `uvicorn app.main:create_app --factory` on a free port → create case + 3 events via HTTP → SIGTERM → confirm exit → restart → assert UUID/version/status/record_ref/event history identical. Health-state polling with bounded deadline (no sleeps). |
| I2 | Sessions across restart | **GAP** | Same run: login before restart; after restart the session cookie still authorizes (DB-backed) — per the documented contract — and logout still revokes. |
| I3/I4 | DB interruption → truthful unready | **GAP** | Stop the test-owned pgserver (`pg_ctl stop -m fast` via the pgserver API or controlled process signal) while uvicorn runs → poll `/health/ready` → 503 with `postgresql`+`migrations` unavailable; `/health/live` stays 200. |
| I5/I6 | Recovery restores readiness | **GAP** | Restart PostgreSQL → poll readiness until 200 (bounded deadline, exponential backoff poll) → assert no stale healthy state was served meanwhile (readiness never 200 while DB down). |
| I7 | Cases available after recovery | **GAP** | Re-read the case from I1 after recovery. |
| I8 | Connection pool recovery | **GAP** | Issue reads+writes after recovery; assert no permanent pool failure (`pool_pre_ping` is enabled — verify it functions through the outage). |
| — | Compose-level restart | DOCKER | Container-level restart/rebuild persistence remains NOT RUN without Docker; the maintainer's Windows 11 / CI environments cover it via the existing smoke test. |

## Workstream J — Migration-aware readiness (pytest)

| ID | Scenario | Current |
|---|---|---|
| J1 | Healthy migrated → ready | COVERED |
| J2 | Unreachable → 503 sanitized | COVERED |
| J3 | Auth failure → 503 sanitized (disposable SCRAM fixture) | COVERED |
| J4 | Unmigrated → migrations failure | COVERED |
| J5 | Outdated revision → migrations failure | COVERED |
| J6 | Upgrade to head restores readiness | COVERED |
| J7 | Liveness ≠ DB readiness proxy | COVERED |
| J8 | Invalid production config never healthy | COVERED (`test_env_boot` env-loading rejection) |

No additions planned; re-verified green in the baseline run.

## Workstream K — Synthetic demonstration boundary (pytest + inspection)

| ID | Scenario | Current | Planned |
|---|---|---|---|
| K1 | Policy-gated availability | COVERED (empty registry when disabled) | Re-verify green. |
| K2 | Descriptors identify synthetic | COVERED (`SYNTHETIC DEMONSTRATION RECORD — NOT A RESEARCH FINDING`, `synthetic: true` flags) | No addition planned. |
| K3 | No research-observation language | COVERED (UI banner + API descriptors; `test_no_confirmed_fraud_status` guards status vocabulary) | No addition planned. |
| K4 | Cases preserve dataset/snapshot/record refs | COVERED (case API round-trip) | No addition planned. |
| K5 | No synthetic→genuine relabelling | PARTIAL | Assert no API accepts a `dataset_id` outside the registered sources for case creation (spoof test exists) and that no endpoint mutates a case's dataset/snapshot/record_ref after creation (routes absent). |
| K6 | Disabled sources → no alternative exposure | **PASS** (non-parameterized GET sweep with empty case table + parameterized GET sweep with a persisted case — defect log §6.4) | Done at `d594d06`: `test_no_get_endpoint_exposes_synthetic_content` (non-parameterized) + new `test_parameterized_gets_do_not_leak_synthetic_payload_with_persisted_case` (parameterized, with a case warmed while the flag was enabled then probed under the disabled flag). |
| K7 | Frozen files unchanged | COVERED (28/28 in CI job + locally) | No addition planned. |
| K8 | No fabricated scores/labels in new fixtures | Process rule | New tests use only the existing synthetic fixtures; reviewer sign-off in Stage 6. |

---

## Mandatory verification matrix — per-requirement detail

Each requirement below carries the six dimensions requested for audit
review: (1) existing test and actual assertion; (2) current coverage
status; (3) proposed deterministic test; (4) expected invariant;
(5) production-defect status; (6) priority and proposed implementation
scope. Coverage statuses are Stage-2 coverage assessments; final
PASS/FAIL/PARTIAL/NOT RUN will be recorded in the Stage-7 delivery
report after execution.

---

### PR07A-01 — Baseline commit verified

- **Existing test & assertion:** Direct git commands executed in the
  authoritative checkout (`/home/z/my-project/pr07a-work/peiars-baseline`):
  `git status --short` (empty), `git branch --show-current` (`pr-07a-dev`),
  `git rev-parse HEAD` (`21761408f31d6c0e9ff4ff502c0c98f0897f79cd`),
  `git log -1 --oneline`. `git ls-remote` confirms `refs/heads/main` and
  `refs/tags/pr-06b-accepted` both dereference to the same SHA.
- **Coverage:** Sufficient (DONE).
- **Proposed deterministic test:** None — baseline verification, not a
  test. The commit SHA is recorded as the immutable reference for all
  Stage 3/4 diffs.
- **Expected invariant:** HEAD of `main` ==
  `21761408f31d6c0e9ff4ff502c0c98f0897f79cd`; tag `pr-06b-accepted`
  dereferences to the same SHA; working tree clean; `pr-07a-dev` branched
  from `main` at this commit.
- **Production defect:** Not established.
- **Priority & scope:** Gate satisfied. No implementation work.

### PR07A-02 — True overlapping index success race (A1)

- **Existing test & assertion:** `frontend/tests/integration/index-refresh-race.test.tsx`
  test 2. The test's own source comment records an abandoned design
  ("This test design doesn't work… The first call already resolved. This
  test verifies the basic path."). The deferred promise resolves *before*
  the second request starts, so no overlap is ever created. Asserts only
  that the basic success path renders — does NOT assert that an
  older-but-slower success response is discarded.
- **Coverage:** Absent (QUALITY-GAP — test exists but does not race).
- **Proposed deterministic test:** Deferred promises. Mount → capture the
  mount case-list GET's resolver (call A pending). Trigger refresh B (via
  a mutation's sync refresh or `onRetry`). Assert two distinct GETs
  started (fetch-mock call count). Resolve B with the newer list (Case B
  present). Resolve A last with the older list (no Case B). Assert Case B
  still rendered; no stale `loadingIndex`; no empty-state flash. No
  `setTimeout` orchestration.
- **Expected invariant:** After A-resolves-last, the rendered list equals
  B's response (the newer generation); `loadingIndex` is false only for
  the latest generation; no intermediate empty-state flash is observable.
- **Production defect:** Not established. The production guard exists at
  `InvestigationsPage.tsx:112-139` (`indexGenRef` generation counter with
  stale-success discard). The gap is test coverage, not production code.
- **Priority & scope:** High. Vitest — rewrite `index-refresh-race.test.tsx`.
  Runtime impact ~5 s.

### PR07A-03 — True overlapping index failure race (A2)

- **Existing test & assertion:** `index-refresh-race.test.tsx` test 1.
  Sequential: the first call's 503 **settles** (error panel rendered)
  before Retry starts the second call, so the stale-failure-discard
  branch (`indexGenRef.current !== gen` in the catch) is never executed.
  Asserts the error panel renders on a 503 — does NOT assert that a stale
  503 is discarded.
- **Coverage:** Absent (QUALITY-GAP).
- **Proposed deterministic test:** Deferred rejection. A pending → B
  starts → B resolves 200 (Case A) → A rejects 503 *afterwards*. Assert
  Case A remains; no error panel; `loadingIndex` false. The
  stale-discard branch in the catch is what runs — this is the branch
  test 1 never reached.
- **Expected invariant:** A stale 503 from a superseded generation never
  sets an error panel and never prevents the latest generation's success
  from rendering.
- **Production defect:** Not established. Production discard branch exists
  but is untested.
- **Priority & scope:** High. Vitest — same file. Runtime impact ~5 s.

### PR07A-04 — Superseded refresh sync-warning semantics (A3)

- **Existing test & assertion:** None. No test asserts that a superseded
  refresh's failure does NOT set `indexSyncWarning`.
- **Coverage:** Absent.
- **Proposed deterministic test:** Two cases: (i) mutation's sync refresh
  B is superseded by a later refresh C; B rejects stale → assert **no**
  `indexSyncWarning` set (error discarded before re-throw); (ii)
  non-superseded refresh rejects → warning **is** set and cleared by a
  successful manual retry. Deferred promises throughout; no sleeps.
- **Expected invariant:** `indexSyncWarning` is set ONLY by a
  non-superseded refresh failure, never by a stale (superseded) failure.
- **Production defect:** Not established.
- **Priority & scope:** Medium. Vitest.

### PR07A-05 — Stale case detail/history blocked (B1)

- **Existing test & assertion:** `frontend/tests/integration/async-state-safety.test.tsx`
  — delayed history GET (B1 partial) and delayed detail GET (B1).
  Asserts that after selecting B, A's delayed content does not appear.
  However, orchestration uses `setTimeout(50)` / `setTimeout(100)` — the
  exact non-deterministic pattern the contract prohibits.
- **Coverage:** Partial (test exists, mechanism non-deterministic).
- **Proposed deterministic test:** Re-implement without sleeps: select
  Case A (GETs deferred, never resolved yet) → select Case B (resolve
  immediately) → resolve A last → assert B's title/history remain and no
  A content in panels.
- **Expected invariant:** After A-resolves-last, the detail panel shows
  Case B's title and Case B's history; Case A's data appears nowhere in
  the DOM.
- **Production defect:** Not established. The selection-load effect
  guards at `:202`/`:214`/`:217`.
- **Priority & scope:** High. Vitest — rewrite B1 path in
  `async-state-safety.test.tsx`.

### PR07A-06 — Stale source evidence blocked (B2)

- **Existing test & assertion:** None. The nested
  `getSyntheticRecord(detail.record_ref)` for a prior selection is not
  asserted.
- **Coverage:** Absent.
- **Proposed deterministic test:** Defer the nested evidence GET for Case
  A only (route mock keyed on A's `record_ref`). Select A → select B
  (B's evidence resolves) → resolve A's evidence last → assert B's
  evidence shown; A's evidence text absent.
- **Expected invariant:** The source-evidence panel reflects the
  currently-selected case's `record_ref`, never a prior selection's.
- **Production defect:** Not established. The nested GET IS guarded at
  `InvestigationsPage.tsx:207`, but the guard is untested.
- **Priority & scope:** Medium. Vitest.

### PR07A-07 — Stale conflict-recovery blocked (B3) [SUSPECTED DEFECT]

- **Existing test & assertion:** None. `handleReloadAfterConflict`
  (`InvestigationsPage.tsx:464-481`) is exercised by E2E #13 only for the
  happy path (click reload → GETs resolve → same case reloaded). No test
  holds its recovery GETs pending across a selection change.
- **Coverage:** Absent.
- **Proposed deterministic test:** Select Case A → POST note → mock 409
  → conflict banner visible → click "Reload latest version" (recovery
  GETs deferred) → select Case B (B's GETs resolve) → resolve A's
  recovery GETs last → assert B's detail/history still displayed and B's
  loading state not cleared. **Expected RED** against baseline.
- **Expected invariant:** A recovery GET initiated by
  `handleReloadAfterConflict` for a prior selection never overwrites the
  currently-selected case's detail/history and never clears its loading
  state.
- **Production defect:** **Suspected (PR07A-D1).** See audit §7 and §7.1
  for the precise source lines (`:464-481`, unguarded setters at `:474`
  / `:475` / `:479`) and the step-by-step overwrite mechanism.
  Confirmation requires the Stage 3 RED demonstration; not confirmed at
  audit stage per the contract's discipline.
- **Priority & scope:** High. Vitest — new test in
  `async-state-safety.test.tsx` or a dedicated
  `conflict-recovery-race.test.tsx`. If RED, Stage 4 applies a 3-line
  guard fix (capture `selectionGenRef.current` at `:465`; wrap the three
  setters in `if (selectionGenRef.current === currentGen)`). No
  state-architecture rewrite.

### PR07A-08 — Two-reviewer real-PostgreSQL concurrency (C1)

- **Existing test & assertion:** `backend/tests/test_database_transactions.py::test_genuine_independent_sessions_conflict`.
  Sequential: session 1 commits its update, THEN session 2 attempts a
  stale write. Asserts `ConcurrencyConflictError` at service level. No
  barrier, no threads, no HTTP layer. The contract's "do not rely on
  issuing requests sequentially" is currently relied upon.
- **Coverage:** Absent (QUALITY-GAP — sequential, service-level only).
- **Proposed deterministic test:** HTTP-level against the pgserver-backed
  app: create case as reviewer; two `TestClient` sessions (separate
  cookies); both read version N; `threading.Barrier(2)` releases both
  POSTs simultaneously (two threads, results collected); assert exactly
  one 2xx + one 409, final DB version == N+1, exactly one new event,
  event sequence consistent.
- **Expected invariant:** Exactly one of the two competing writes
  succeeds (200/201) and exactly one fails (409); the loser's
  transaction rolls back (no event written); final case version == N+1;
  total event count increments by exactly one.
- **Production defect:** Not established. The CAS is a single atomic
  `UPDATE ... WHERE id=:id AND version=:expected` (rowcount 0 → 409);
  PostgreSQL row locking serializes the competing updates. The gap is
  HTTP-level test coverage.
- **Priority & scope:** High. pytest — new `test_concurrency_http.py` or
  extension to `test_database_transactions.py`. Runtime impact ~2-5 s.

### PR07A-09 — 409 UI recovery preserves intent (C2)

- **Existing test & assertion:** E2E #11/#13 (Playwright) exercise the
  409 → reload → retry flow. `mutation-reliability.test.tsx` asserts 409
  draft preservation and that "SYNC RETRY" sends no second POST.
- **Coverage:** Sufficient (partial on the conflict-recovery button
  specifically — the GET-only assertion is not extended to that button).
- **Proposed deterministic test:** Add Vitest assertion that the reload
  action issues GETs only (fetch-mock: no second POST) — extend the
  existing "SYNC RETRY" assertion to the conflict-recovery button.
- **Expected invariant:** The conflict-recovery button triggers only GET
  requests; no POST is issued by any recovery action.
- **Production defect:** Not established.
- **Priority & scope:** Low. Vitest — small extension to existing test.

### PR07A-10 — Rejected/rolled-back mutation leaves no event

- **Existing test & assertion:** `test_database_transactions.py` rollback
  tests assert no partial case/event and no duplicate event on conflict;
  `test_case_history.py` asserts DB-level UPDATE/DELETE rejection.
- **Coverage:** Sufficient.
- **Proposed deterministic test:** Re-verify green; no addition.
- **Expected invariant:** A rejected mutation (409/422/constraint
  failure) leaves the case row and event table byte-identical to the
  pre-mutation state.
- **Production defect:** Not established.
- **Priority & scope:** None — re-verification only.

### PR07A-11 — Event ordering and attribution (D1)

- **Existing test & assertion:** `test_event_ordering.py` (ordering, seq
  monotonicity, two-event decisions), `test_status_transitions.py`.
  Attribution is implicit — `actor_ref` server-side binding is not
  asserted against a spoofed body field.
- **Coverage:** Partial (attribution assertion absent).
- **Proposed deterministic test:** Extend one case: assert each event's
  `actor_ref` equals the authenticated principal's user UUID, including a
  request that supplies a spoofed `actor_ref` body field (server
  overwrites via `actor_ref_from_principal`).
- **Expected invariant:** Every event's `actor_ref` equals the
  authenticated principal's user UUID, regardless of any client-supplied
  `actor_ref`/`created_by` field.
- **Production defect:** Not established.
- **Priority & scope:** Medium. pytest — extension to
  `test_event_ordering.py`.

### PR07A-12 — Confirmed POST + failed GET no duplicate (E1)

- **Existing test & assertion:** `mutation-reliability.test.tsx` — POST
  200 + GET 503 for note/transition/decision/create; asserts all 11
  observable frontend steps (draft cleared, sync warning shown, version
  bumped, no duplicate POST). The existing
  `test_confirmed_note_post_creates_exactly_one_event` pytest isolates
  the per-mutation single-event invariant for two consecutive
  confirmed POSTs.
- **Coverage:** PASS (two complementary layers).
  - Frontend observable steps: `mutation-reliability.test.tsx` (POST
    200 + GET 503 across all four mutation types).
  - Per-mutation single-event invariant on real PostgreSQL: existing
    `test_confirmed_note_post_creates_exactly_one_event` (two
    consecutive confirmed POSTs → exactly two `note_added` rows).
  - Full end-to-end POST→failed-GET→recovery sequence on real
    PostgreSQL: new
    `test_confirmed_post_then_failed_get_then_recovery_leaves_exactly_one_event`
    (defect log §6.3) — POST /notes 200 → armed 503 on the next
    `session_factory()` call → GET /history returns 503
    `SERVICE_NOT_READY` (raised through the production
    `_case_service`/`require_authenticated` path via an armed one-shot
    `_IntermittentSessionFactory` wrapper) → recovery GET /history 200
    → exactly two `note_added` rows in the DB (no duplicate from the
    failed GET, the recovery GET, or any retry path).
- **Expected invariant:** After a confirmed-success POST followed by a
  failed GET and subsequent recovery, the database contains exactly
  one event for that mutation.
- **Production defect:** Not established.
- **Priority & scope:** Medium. pytest — extension to
  `test_persistence_equivalence.py` (now done at `d594d06`).

### PR07A-13 — Uncertain outcome no unsafe retry (E4)

- **Existing test & assertion:** `mutation-reliability.test.tsx` timeout
  test — draft preserved, distinct "uncertain outcome" message; no retry
  logic exists in `client.ts` (grep-verified).
- **Coverage:** Sufficient (no-second-POST assertion is implicit).
- **Proposed deterministic test:** Add explicit assertion: after a
  network-failed POST, no second POST is issued by any recovery action
  (fetch-mock call counting); UI copy does not claim rejection.
- **Expected invariant:** A transport-failed POST is never retried by
  the client; the UI surfaces an "uncertain outcome" message distinct
  from "rejected"; the draft is preserved.
- **Production defect:** Not established.
- **Priority & scope:** Low. Vitest — extension.

### PR07A-14 — Session expiry verified (F1)

- **Existing test & assertion:** `test_auth_sessions.py::test_expired_session_401`,
  `test_idle_timeout_401`, `test_absolute_expiry...` — via test-owned
  session-row manipulation (controlled clocks, no sleeps).
- **Coverage:** Sufficient.
- **Proposed deterministic test:** Re-verify green; add boundary
  assertion: `expires_at == now` (not just `< now`) rejects.
- **Expected invariant:** A session whose `expires_at` equals the
  current time is rejected (boundary-inclusive rejection); idle and
  absolute timeouts enforced from DB state on every request.
- **Production defect:** Not established.
- **Priority & scope:** Low. pytest — boundary assertion.

### PR07A-15 — Logout invalidates session (F2)

- **Existing test & assertion:** `test_auth_sessions.py::test_logout_replay_fails`
  — logout sets `revoked_at`; replay with the old cookie returns 401.
- **Coverage:** Sufficient.
- **Proposed deterministic test:** None.
- **Expected invariant:** After logout, the session cookie is rejected
  on every subsequent request regardless of TTL.
- **Production defect:** Not established.
- **Priority & scope:** None.

### PR07A-16 — Cookie attributes verified (F3)

- **Existing test & assertion:** `test_auth_cookies.py` — production
  policy (HttpOnly, Secure, SameSite=Lax, Path=/, no Domain), dev
  relaxation, max-age, logout expiry, CSRF readability, no token in JSON.
- **Coverage:** Sufficient.
- **Proposed deterministic test:** None.
- **Expected invariant:** Session cookie is HttpOnly + SameSite=Lax +
  Secure (production) + Path=/ + no Domain; CSRF cookie intentionally
  readable; max-age ties to server TTL.
- **Production defect:** Not established.
- **Priority & scope:** None.

### PR07A-17 — Production cookie validation preserved (F4)

- **Existing test & assertion:** `test_env_boot.py` — drives
  `PEIARS_ENVIRONMENT=production` + `session_cookie_secure=false` through
  `monkeypatch.setenv` (real env-loading path); asserts rejection.
  Placeholder-secret markers also rejected.
- **Coverage:** Sufficient.
- **Proposed deterministic test:** None.
- **Expected invariant:** A production configuration with
  `session_cookie_secure=false` or placeholder secrets is rejected at
  startup.
- **Production defect:** Not established.
- **Priority & scope:** None.

### PR07A-18 — Viewer direct API mutations rejected (G4/G5/G6)

- **Existing test & assertion:** `test_auth_rbac.py` permission matrix;
  `test_case_api.py::test_viewer_cannot_create_case`,
  `test_viewer_cannot_add_note` — status-only (no DB/event assertion).
  Transition and decision NOT tested by name.
- **Coverage:** Partial (create + note covered status-only; transition +
  decision absent).
- **Proposed deterministic test:** Add tests: viewer POST transition →
  403 + no case mutation + no event; viewer POST decision → 403 + no
  case mutation + no event. Strengthen create/note: add DB row + event
  count assertions. Sweep OpenAPI paths for all non-GET routes; assert
  each requires reviewer/admin (contract-level, future-proof).
- **Expected invariant:** Every non-GET route under `/api/v1` requires
  reviewer or admin role; a viewer's mutation attempt returns 403 and
  leaves no DB row and no event.
- **Production defect:** Not established.
- **Priority & scope:** High. pytest — `test_auth_rbac.py` /
  `test_case_api.py` additions.

### PR07A-19 — Reviewer/admin boundaries (G8)

- **Existing test & assertion:** Admin gate dependency tested;
  `test_case_api.py` reviewer CRUD path covered.
- **Coverage:** Partial (admin-only HTTP route existence not checked).
- **Proposed deterministic test:** Add one HTTP-level test if any
  admin-only route exists (bootstrap CLI is not HTTP); else record NOT
  APPLICABLE with justification.
- **Expected invariant:** Any admin-only HTTP route rejects a reviewer
  with 403.
- **Production defect:** Not established.
- **Priority & scope:** Low. pytest — conditional on route inventory.

### PR07A-20 — Invalid CSRF rejected, no mutation (H2/H3/H7)

- **Existing test & assertion:** `test_auth_csrf.py` — missing/incorrect/
  mismatched/unsigned tokens → 403. H7 invariants (version/event
  unchanged after rejection) not asserted.
- **Coverage:** Sufficient (partial on H7 — post-rejection state
  unchanged).
- **Proposed deterministic test:** Wrap each rejection: assert version
  and event count identical before/after each rejected request.
- **Expected invariant:** A CSRF-rejected mutation leaves case version
  and event count byte-identical to the pre-request state.
- **Production defect:** Not established.
- **Priority & scope:** Medium. pytest — extension to `test_auth_csrf.py`.

### PR07A-21 — Cross-origin write rejected, no mutation (H5/H7)

- **Existing test & assertion:** `test_auth_csrf.py` cross-origin test
  uses the pre-auth LOGIN endpoint only.
- **Coverage:** Partial (authenticated mutation with valid CSRF + bad
  Origin not tested).
- **Proposed deterministic test:** New test on POST /cases: valid
  session + valid CSRF + `Origin: http://evil.example` → 403 + version/
  event unchanged.
- **Expected invariant:** An otherwise-valid authenticated mutation with
  a disallowed Origin is rejected; no DB row, no event.
- **Production defect:** Not established.
- **Priority & scope:** High. pytest — `test_auth_csrf.py`.

### PR07A-22 — nginx proxied auth/origin behavior (H6)

- **Existing test & assertion:** PR-06B verification — `TestClient` with
  `Host: localhost:8080` proved `$http_host` semantics; the `$host`
  port-stripping defect was found and fixed in PR-06B. Backend-level
  equivalent exists. Compose-level: `ci/container_smoke_test.sh` (11
  checks; `--env-file` + `-T`; real case write/read-back).
- **Coverage:** Partial (backend-level sufficient; Compose-level NOT RUN
  — no Docker in sandbox).
- **Proposed deterministic test:** Compose-level: container smoke test
  (11 checks, maintainer-executed) covers login/CSRF via proxy when
  Docker is available. No backend addition.
- **Expected invariant:** nginx forwards `Host` (with port) to the
  backend; CSRF/Origin validation uses `$http_host` (not the
  port-stripped `$host`).
- **Production defect:** Not established (the prior `$host` defect was
  corrected in PR-06B).
- **Priority & scope:** DOCKER — NOT RUN in this sandbox; maintainer CI
  evidence run `43273888391` referenced.

### PR07A-23 — Backend restart preserves cases/events (I1)

- **Existing test & assertion:** `test_restart_outage_recovery.py::
  TestRestartOutageRecovery::test_full_scenario` — test-owned
  pgserver instance + test-owned `uvicorn app.main:create_app
  --factory` subprocess on a free port. Boots, waits readiness 200,
  logs in, creates a case + 3 events, SIGTERMs the backend (bounded
  exit wait via `communicate()`), restarts, waits readiness 200,
  asserts UUID/version/status/record_ref/event-seq identical.
- **Coverage:** PASS. Hardened at `d594d06` (defect log §6.1/§6.2):
  `iac_migrated` env mutation scoped via
  `pytest.MonkeyPatch`/`undo`; backend processes and httpx clients
  tracked in resource lists and closed in a single `finally` that
  runs on the failure path; pgserver data dir released via
  `server.cleanup()` in `finally`; `_stop_backend` drains stdio pipes
  via `communicate()`.
- **Proposed deterministic test:** Done. Health-state polling with
  bounded deadline (no sleeps). Subprocess runtime ~6 s on the
  sandbox.
- **Expected invariant:** After a clean backend process restart against
  the same PostgreSQL database, every case and event row is
  byte-identical to the pre-restart state.
- **Production defect:** Not established.
- **Priority & scope:** High. pytest — module
  `test_restart_outage_recovery.py` (delivered at `d6d4afc`,
  hardened at `d594d06`).

### PR07A-24 — Session restart behavior (I2)

- **Existing test & assertion:** None.
- **Coverage:** Absent.
- **Proposed deterministic test:** Same run as I1: login before restart;
  after restart the session cookie still authorizes (DB-backed); logout
  still revokes.
- **Expected invariant:** A DB-backed session survives a backend process
  restart; logout after restart still revokes.
- **Production defect:** Not established.
- **Priority & scope:** Medium. pytest — folds into I1 module.

### PR07A-25 — DB outage → unready (I3/I4)

- **Existing test & assertion:** None.
- **Coverage:** Absent.
- **Proposed deterministic test:** Stop the test-owned pgserver
  (`pg_ctl stop -m fast` via the pgserver API or controlled process
  signal) while uvicorn runs → poll `/health/ready` → 503 with
  `postgresql`+`migrations` unavailable; `/health/live` stays 200.
- **Expected invariant:** While PostgreSQL is unreachable,
  `/health/ready` returns 503 (sanitized) and `/health/live` returns 200;
  no stale healthy state is served.
- **Production defect:** Not established.
- **Priority & scope:** High. pytest — folds into I-series module.

### PR07A-26 — Recovery restores readiness + access (I5-I8)

- **Existing test & assertion:** None.
- **Coverage:** Absent.
- **Proposed deterministic test:** Restart PostgreSQL → poll readiness
  until 200 (bounded deadline, exponential backoff poll) → assert no
  stale healthy state meanwhile → re-read case from I1 → assert
  reads/writes work (pool recovery via `pool_pre_ping`).
- **Expected invariant:** After PostgreSQL recovery, readiness returns to
  200, the case from I1 is readable, and subsequent writes succeed
  without permanent pool failure.
- **Production defect:** Not established.
- **Priority & scope:** High. pytest — folds into I-series module.

### PR07A-27 — Missing/outdated migrations detected (J1-J7)

- **Existing test & assertion:** `test_db_readiness.py` (all probe
  states), `test_failure_classification.py` (connection refused, wrong
  password via disposable SCRAM fixture, unmigrated DB, older revision,
  upgrade restores readiness). Liveness ≠ readiness covered.
- **Coverage:** Sufficient.
- **Proposed deterministic test:** None.
- **Expected invariant:** Readiness probe distinguishes
  healthy-migrated, unreachable, auth-failure, unmigrated,
  outdated-revision, and post-upgrade-healthy; liveness is independent
  of DB.
- **Production defect:** Not established.
- **Priority & scope:** None.

### PR07A-28 — Synthetic source explicitly identified (K2/K3)

- **Existing test & assertion:** `test_source_registry.py`;
  `test_no_confirmed_fraud_status` guards status vocabulary; UI banner +
  API descriptors carry `synthetic: true` and "NOT A RESEARCH FINDING"
  copy.
- **Coverage:** Sufficient.
- **Proposed deterministic test:** None.
- **Expected invariant:** Every synthetic descriptor carries
  `synthetic: true` and "NOT A RESEARCH FINDING" copy; no
  confirmed-fraud status vocabulary exists.
- **Production defect:** Not established.
- **Priority & scope:** None.

### PR07A-29 — No synthetic→genuine confusion (K5/K6)

- **Existing test & assertion:**
  - `test_source_registry.py` empty default + id validation.
  - `test_case_api.py` spoofed dataset rejected.
  - `test_synthetic_boundary_sweep.py::test_no_get_endpoint_exposes_synthetic_content`
    sweeps all non-parameterized OpenAPI GET paths with
    `demonstration_sources=false`: no synthetic record content anywhere
    (sources list, records list, case list empty, health, meta, auth).
  - `test_synthetic_boundary_sweep.py::test_parameterized_gets_do_not_leak_synthetic_payload_with_persisted_case`
    (new, defect log §6.4) warms a case from the synthetic source while
    `demonstration_sources=true`, then recreates the app with the flag
    disabled and probes all four parameterized GETs
    (`/api/v1/cases/{case_id}`, `/api/v1/cases/{case_id}/history`,
    `/api/v1/sources/{source_id}`, `/api/v1/synthetic/records/{record_ref}`)
    against the persisted case. Asserts no synthetic record PAYLOAD
    marker leaks (the case's own provenance refs
    `synth-001`/`synthetic-v1`/`synthetic-demonstration` legitimately
    appear in the case detail, as they are the case's identity).
- **Coverage:** PASS (both halves of the GET surface).
  - Non-parameterized GETs: empty-table sweep (existing).
  - Parameterized GETs: persisted-case sweep (new).
  - Provenance immutability: K5 (mutation schemas carry no
    dataset/snapshot/record fields) + `test_case_creation_from_demonstration_source_rejected`
    (creation gated 503 when the flag is disabled).
- **Expected invariant:** With demonstration sources disabled, no
  endpoint exposes synthetic record content; no API accepts or mutates
  a case's dataset/snapshot/record_ref outside creation. The case's own
  provenance refs persist legitimately on the case row (they are the
  case's identity, not synthetic content).
- **Production defect:** Not established.
- **Priority & scope:** Medium. pytest — extension to
  `test_synthetic_boundary_sweep.py` (now done at `d594d06`).

### PR07A-30 — 28 frozen files pass integrity

- **Existing test & assertion:** `ci/check_frozen_integrity.py` — 28/28
  match (exit 0), re-verified at `2176140` in this sandbox.
- **Coverage:** Sufficient.
- **Proposed deterministic test:** None.
- **Expected invariant:** All 28 frozen research files match their
  committed SHA-256 hashes at the baseline commit.
- **Production defect:** Not established.
- **Priority & scope:** None.

### PR07A-31 — Existing regressions preserved

- **Existing test & assertion:** 550 backend (pytest) / 105 frontend
  (Vitest) / 18 E2E (Playwright) — all reproduced at `2176140` in this
  sandbox. Frozen research integrity 28/28.
- **Coverage:** Sufficient (must remain green after Stage 3/4 changes).
- **Proposed deterministic test:** None (gate — enforced at every Stage
  3/4 commit).
- **Expected invariant:** All pre-existing tests remain green after
  PR-07A additions.
- **Production defect:** Not established.
- **Priority & scope:** Gate — enforced at every commit.

### PR07A-32 — Container smoke and Compose preserved

- **Existing test & assertion:** `ci/container_smoke_test.sh` (11
  checks; `--env-file` + `-T`; real case write/read-back). Compose
  design: 4 services on `peiars-net`, project-scoped volume,
  profile-gated `migrate`.
- **Coverage:** DOCKER (NOT RUN in sandbox; design preserved).
- **Proposed deterministic test:** Compose-level restart/rebuild
  persistence remains NOT RUN without Docker; maintainer CI evidence
  run `43273888391` referenced.
- **Expected invariant:** Container smoke (11 checks) passes on a
  Docker-equipped environment; Compose design unchanged.
- **Production defect:** Not established.
- **Priority & scope:** DOCKER — NOT RUN in this sandbox.

### PR07A-33 — No production secrets / unsafe test resources

- **Existing test & assertion:** Process property —
  `backend/tests/conftest.py` uses disposable pgserver; frontend tests
  use mock tokens; no shared developer volumes.
- **Coverage:** Sufficient (as a process property); strengthened at
  `d594d06` (defect log §6.1/§6.2) — the IAC test's
  `PEIARS_DATABASE_URL` env mutation is now scoped via
  `pytest.MonkeyPatch`/`undo`, and every backend subprocess / httpx
  client / pgserver data directory opened by the I-series scenario is
  tracked and closed in a `finally` block that runs on the failure
  path.
- **Proposed deterministic test:** Stage-6 audit property — all new
  tests use disposable pgserver + ephemeral fixtures; the IAC env-scope
  and harness-cleanup guarantees are verified by the I-series test
  itself running green on a recycled sandbox (no leaked env var, no
  orphaned process).
- **Expected invariant:** No production secret or shared developer
  resource is referenced by any test; the parent process environment is
  left unmodified by the IAC test's transient env mutation.
- **Production defect:** Not established.
- **Priority & scope:** Process — enforced at Stage 6 sign-off.

### PR07A-34 — No new product features / PR-07B

- **Existing test & assertion:** Process rule.
- **Coverage:** Sufficient (as a process property).
- **Proposed deterministic test:** None.
- **Expected invariant:** PR-07A introduces no new product features; all
  changes are tests or the single candidate guard fix (PR07A-D1).
- **Production defect:** Not established.
- **Priority & scope:** Process.

### PR07A-35 — New tests exercise claimed failure paths

- **Existing test & assertion:** Process rule — the test-quality audit
  (audit §6) identifies three tests that do NOT exercise their claimed
  paths (A1, A2, C1).
- **Coverage:** Sufficient (as a process property, once §6 defects are
  addressed in Stage 3).
- **Proposed deterministic test:** Stage-5 enforcement: overlap proof
  (deferred-promise resolution ordering), barrier synchronization, no
  `setTimeout`-based race orchestration, no accidental-pass conditions.
- **Expected invariant:** Every new race/concurrency test provably
  creates the overlap or contention it claims (documented resolution
  order; barrier-released threads; observable fetch-mock call counts).
- **Production defect:** Not established.
- **Priority & scope:** Process — enforced at Stage 5 review.

### PR07A-36 — Production changes have defect justification

- **Existing test & assertion:** Process rule.
- **Coverage:** Sufficient (one candidate identified, gated on RED).
- **Proposed deterministic test:** PR07A-D1 is the ONLY candidate
  production change; applied ONLY if Stage 3 demonstrates RED against
  baseline; otherwise BASELINE GREEN is recorded and no production code
  is touched.
- **Expected invariant:** No production code is modified except upon a
  demonstrated RED test that names the defect; the fix is the smallest
  correction that turns RED to GREEN.
- **Production defect:** One suspected (PR07A-D1) — not yet confirmed.
- **Priority & scope:** Conditional — Stage 3 RED → Stage 4 minimal
  guard fix (3 lines at `InvestigationsPage.tsx:464-481`).

---

## Coverage summary (counts)

Each of the 36 requirements is counted exactly once, by its Stage-2
coverage assessment:

| Coverage status | Count | Requirement IDs |
|---|---|---|
| Sufficient | 17 | 01, 09, 10, 13, 14, 15, 16, 17, 20, 27, 28, 30, 31, 33, 34, 35, 36 |
| Partial | 8 | 05, 11, 12, 18, 19, 21, 22, 29 |
| Absent (GAP / QUALITY-GAP) | 10 | 02, 03, 04, 06, 07, 08, 23, 24, 25, 26 |
| DOCKER (NOT RUN in sandbox) | 1 | 32 |

Total: 17 + 8 + 10 + 1 = **36**.

Defect annotations (not counted as separate requirements):

- **Suspected production defect:** 1 — PR07A-D1, attached to PR07A-07
  (counted above under Absent). See audit §7/§7.1.
- **Confirmed production defects:** 0 — confirmation requires the
  Stage 3 RED demonstration.

## Isolation and CI placement summary

- All new backend tests use the existing pgserver session fixtures
  (disposable per-session PostgreSQL) or a module-scoped dedicated pgserver
  + subprocess uvicorn (I-series); no shared server, no developer volume,
  no `down -v` against anything but a CI-owned unique project.
- New frontend tests reuse `renderApp` helpers with fetch interception; no
  real credentials; CSRF fixtures are mock tokens.
- Placement: pytest additions in existing backend suite; Vitest additions
  in existing frontend suite; no new workflow jobs; mandatory failures
  propagate normally (no `continue-on-error`); least-privilege permissions
  untouched.
- Runtime impact: ~5-10s (frontend), ~5-10s (backend additions), ~20-40s
  (I-series subprocess module — the only material cost, justified: it is the
  sole mechanism that proves restart/outage/recovery against a real process
  and real PostgreSQL without Docker).

**Awaiting approval to proceed to Stage 3 (deterministic test development)
and Stage 4 (minimal corrections — only PR07A-D1, and only if RED).**
