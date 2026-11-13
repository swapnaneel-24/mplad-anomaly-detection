# PR-07A Defect Log

**Milestone:** PR-07A — Adversarial Reliability and Security Hardening
**Baseline:** `21761408f31d6c0e9ff4ff502c0c98f0897f79cd` (`main`, tag `pr-06b-accepted`)
**Final development commit:** `d594d0682284ac9ca96c4e5a144ec23d3da19a24` (`pr-07a-dev`; bounded-correction commit on top of `d6d4afc9a66b5145086e71e1200380ac9488ecc6`)

Classification vocabulary (contract A5): **BASELINE GREEN** — the
unchanged implementation already satisfied the invariant; **RED BEFORE →
GREEN AFTER** — a genuine defect was reproduced against the unchanged
baseline and corrected; **PARTIAL**; **NOT RUN**; **FAIL**.

---

## 1. PR07A-D1 — stale conflict-recovery response overwrites the newly
selected case

**Classification: RED BEFORE → GREEN AFTER (confirmed production
defect).**
**Suspected at Stage 2 (audit §7/§7.1); confirmed at Stage 3 by
deterministic RED demonstration.**

**Site:** `frontend/src/pages/InvestigationsPage.tsx`,
`handleReloadAfterConflict` (baseline lines 464-481). The handler lacked
the `selectionGenRef` generation guard that every other async read path
on the page has, so a recovery GET pair that settles after the user
selected a different case reapplied unconditionally:
`setCaseDetail` (:474), `setHistory` (:475), `setLoadingDetail(false)`
(:479).

### 1.1 RED evidence (unchanged baseline, deterministic deferred promises)

Test file: `frontend/tests/integration/conflict-recovery-race.test.tsx`.
Sequence: select Case A → POST note → HTTP 409 → conflict banner →
click "Reload latest version" (recovery GETs held pending) → select
Case B (B's GETs resolve) → settle Case A's recovery GETs afterwards →
assert B stays authoritative. No sleeps, no StrictMode effects; the
deferred resolvers are test-owned.

| Test | Baseline result (exact failure) | Defect path |
|---|---|---|
| B3-1 stale recovery SUCCESS | `AssertionError: expected <h2 class="inv__case-title"></h2> to be null` — the panel rendered Case A's stale title "STALE RECOVERED DETAIL" over Case B | unguarded success setters |
| B3-2 stale recovery FAILURE | `TestingLibraryElementError: Unable to find an element with the text: Case B` — the stale 503 set `detailError`, replacing Case B's evidence view with an error panel | unguarded error setter |
| B3-3 stale recovery FINALLY | `TestingLibraryElementError: Unable to find an element with the text: Loading evidence…` — the stale `finally` cleared the loading state while Case B was still loading (and painted stale Case A data) | unguarded finally |
| B3-4 GET-only recovery (control) | PASSED on baseline | recovery issues no second POST |

Suite result on the unchanged baseline: **3 failed / 1 passed** —
exactly the three defect paths, with the control green.

### 1.2 Correction (Stage 4 — smallest change)

`handleReloadAfterConflict` now captures
`const currentGen = selectionGenRef.current;` at handler entry and:

- discards the success path when `selectionGenRef.current !== currentGen`
  (before `setCaseDetail`/`setHistory`);
- discards the error path when stale (no `setDetailError`);
- clears `setLoadingDetail(false)` in `finally` only when the selection
  is unchanged (the new selection's own effect owns the flag).

Net production diff: 11 insertions, 1 deletion, one function, no
state-architecture change — mirroring the guarded sibling
`handleRefreshHistory` (:441/:444) and the selection effect
(:163/:202/:214/:217).

### 1.3 GREEN evidence (after the fix)

`conflict-recovery-race.test.tsx`: **4 passed / 4** (B3-1, B3-2, B3-3
now green; B3-4 stays green). Full frontend suite after the fix:
**115 passed (21 files)**; E2E **18 passed**; typecheck/lint/build green.

---

## 2. Test-quality defects corrected (tests, not production code)

**Classification: RED BEFORE → GREEN AFTER (test repair; production
unchanged).**

1. **A1/A2 — the old "race" tests did not race.**
   `index-refresh-race.test.tsx` test 1 was sequential (the first 503
   settled before Retry started, so the stale-failure-discard branch
   never ran); test 2's own comments recorded an abandoned design ("the
   first call already resolved"). **Correction:** the file was rewritten
   with genuinely overlapping post-mutation sync refreshes held on
   test-owned deferreds (A1 older-success-last, A2 older-failure-last,
   A3-i superseded-failure sets no sync warning, A3-ii non-superseded
   failure sets and clears it). **Negative control:** with the
   production guards temporarily removed (scratch run, then restored
   byte-exact), A1/A2/A3-i FAIL and A3-ii (non-superseded path,
   correctly) still passes — proving the tests fail when stale
   responses are incorrectly applied.
2. **C1 — the old concurrency test was sequential.**
   `test_genuine_independent_sessions_conflict` committed session 1's
   update before session 2 attempted its stale write. **Correction:**
   `test_concurrency_http.py` dispatches both POSTs from separate
   authenticated reviewer sessions and proves transaction-level overlap
   with a second `threading.Barrier(2)` inside a SQLAlchemy
   `before_cursor_execute` hook that fires only when BOTH transactions
   are about to execute `UPDATE review_cases`. The barrier firing at
   all is the overlap proof; a non-overlapping run would break the
   barrier instead of passing.
3. **B-series sleep-based orchestration.**
   The prior B1 coverage used `setTimeout(50/100)` waits. **Correction:**
   `stale-selection-races.test.tsx` re-implements B1 and adds B2/B4 with
   deferred promises and fixed microtask flushes only.

---

## 3. Contract observation — anonymous mutation status code (no change)

**Classification: observation; no production defect established.**

The Stage-2 matrix expected anonymous case mutations to return 401. The
implemented contract rejects them with **403 `CSRF_TOKEN_INVALID`**
(the `require_csrf` dependency evaluates before the role gate whenever a
session secret is configured; without one it is 503; the session check's
401 surfaces only on routes without the CSRF gate, e.g. GET /auth/me).
This is fail-closed: anonymous mutations are rejected and leave no row
and no event (asserted in `test_rbac_boundary_sweep.py`). Reordering the
dependencies to surface 401 first would be a production change with no
defect demonstrated, so none was made; the G9 test asserts the actual
fail-closed contract (401/403/503, never 2xx, no side effects).

---

## 4. Items verified BASELINE GREEN (no production change)

| Area | Evidence |
|---|---|
| Index-refresh stale-success/failure discard (A1/A2) | rewritten race tests green on the guarded implementation; negative control red when guards removed |
| Superseded-refresh sync-warning semantics (A3) | A3-i/A3-ii green |
| Stale selection detail/history (B1) and nested source evidence (B2) | generation guards at :202/:214/:217 and :207 verified green, sleep-free |
| Unmount with pending requests (B4) | abort-aware deferreds; no unhandled rejection; clean re-mount |
| Uncertain POST outcome (E4) | no auto-retry; distinct copy; draft preserved; POST count stays 1 |
| HTTP-level optimistic concurrency (C1) | one 200 + one 409; version N+1; exactly one new event; winner's UUID attributed |
| Repeated stale mutation (C3) | stays 409 until a fresh version is supplied |
| Actor attribution vs spoofed bodies (D1) | every event's actor_ref is the principal's UUID |
| Rejected-mutation event invariants (D2) | 422 leaves the event table byte-identical |
| Append-only route contract (D4) | no PUT/PATCH/DELETE in the OpenAPI contract; live probes 404/405 |
| In-process restart equivalence (D5) | fresh app + engine see identical state |
| Server-side single-event invariant (E1) | one confirmed POST → exactly one `note_added` row (existing); full POST→failed-GET→recovery sequence leaves the count unchanged (new integrated test, defect log §6.3) |
| Session expiry boundary (F1) | `expires_at = now()` rejects |
| Viewer mutation rejection with DB assertions (G2-G6) | 403 + zero rows + zero events for all four mutation routes |
| No admin-only HTTP route (G8) | executable NOT-APPLICABLE assertion over route dependencies |
| CSRF rotation replay (H4) | pre-login token rejected after rotation; fresh token accepted; no mutation |
| Authenticated cross-origin write (H5/H7) | 403 with valid session + valid CSRF + disallowed Origin; no mutation |
| Restart / outage / recovery (I1-I8) | subprocess scenario green (see delivery report §6); env-var scope and harness resource cleanup hardened (defect log §6.1/§6.2) |
| Provenance immutability (K5) | mutation schemas carry no dataset/snapshot/record fields |
| Disabled-source exposure sweep (K6) | non-parameterized GET sweep clean (existing); parameterized GET sweep against a persisted case clean (new, defect log §6.4); creation gated 503 |

## 5. FAIL / NOT RUN

- **FAIL:** none outstanding. All executed suites are green at `d594d06`.
- **NOT RUN (environmental):** Docker/Compose container smoke test
  (11 checks) — no Docker daemon in the execution sandbox; design
  preserved unchanged; maintainer CI evidence run `43273888391`
  referenced for the pre-PR-07A state. GitHub-hosted CI (the five
  workflow jobs) — cannot run before the branch is pushed; explicitly
  not claimed.

---

## 6. Bounded corrections (independent ZIP audit feedback)

**Classification: test-harness/report corrections; production code
unchanged.** The PR07A-D1 production fix (`handleReloadAfterConflict`
generation guard, defect log §1) is preserved unchanged. Four
test-harness and documentation issues identified by independent
inspection of `PEIARS_PR07A_changed_files.zip` are corrected at commit
`d594d06` on top of `d6d4afc`.

### 6.1 iac_migrated environment leakage (Issue 1)

**Site:** `backend/tests/test_restart_outage_recovery.py`,
`iac_migrated` fixture (previously lines 153-181).

**Defect:** the fixture directly assigned
`os.environ["PEIARS_DATABASE_URL"] = iac_db_url` without saving or
restoring the prior value. The leak was reproducible: after
`test_restart_outage_recovery` ran, the env var pointed at the stale
IAC data directory (which `server.cleanup()` had already removed),
rather than at the shared `peiars_test` URL that the conftest
`db_engine` fixture had set earlier in the session.

**Correction:** the fixture now uses `pytest.MonkeyPatch().setenv(...)`
with `mp.undo()` in a `finally` block. This restores the prior
environment — including the case where the variable was previously
unset and including the failure path — using the same primitive
pytest itself uses for function-scoped `monkeypatch` fixtures. The
backend subprocess receives the IAC URL through the explicit `iac_env`
dict (passed to `subprocess.Popen`), NOT through `os.environ`, so
restoring the parent environment does not affect the subprocess.

**Verification:** a probe test that ran AFTER
`test_restart_outage_recovery` confirmed `PEIARS_DATABASE_URL` was
restored to `postgresql://...peiars_test...` (the conftest value), not
left at `peiars_iac`. Backend full suite (574 tests) green at
`d594d06`.

### 6.2 Restart harness resource cleanup (Issue 2)

**Site:** `backend/tests/test_restart_outage_recovery.py`,
`_stop_backend` helper and `test_full_scenario`.

**Defect:** (a) `_stop_backend` used bare `process.wait(timeout=...)`
without draining the stdout/stderr pipes — a child blocked on a write
to a full pipe could hang past SIGTERM. (b) `test_full_scenario`
re-assigned the `client` and `process` variables at the restart
boundary without closing the first client; if an assertion failed
mid-scenario, the active `client` and the orphaned first client could
both leak connection-pool resources. (c) The `iac_server` fixture
called `server.cleanup()` after `yield` (not in `finally`), so a
pytest interruption between yield and the cleanup call would skip the
data-dir removal.

**Correction:**
- `_stop_backend` now uses `process.communicate(timeout=...)` (which
  both waits for exit AND drains the OS pipe buffers) and is idempotent
  on an already-exited process.
- `test_full_scenario` tracks every backend process and httpx client
  in two lists (`processes`, `clients`) and closes/stops them in a
  single `finally` block that runs even when an assertion fails. The
  pre-restart client's cookies are captured BEFORE the client is
  closed so the post-restart client can re-use them.
- `iac_server` wraps `server.cleanup()` in a `try/finally` so an
  assertion failure during the scenario still releases the PostgreSQL
  data directory.
- `iac_db_url` wraps `admin_engine.dispose()` in `try/finally`.
- `iac_migrated` wraps `engine.dispose()` in `try/finally`.

Disposable database isolation and bounded waits are preserved: the
pgserver instance is still created in its own temporary data directory
and fully owned by the test, all waits are bounded-deadline polls, and
no shared PG or developer Compose volume is touched.

### 6.3 E1 integrated POST→failed-GET→recovery test (Issue 3)

**Site:** `backend/tests/test_persistence_equivalence.py`,
`TestServerSideSingleEventInvariantIntegrated`.

**Defect:** the existing
`test_confirmed_note_post_creates_exactly_one_event` established the
per-mutation single-event invariant for two consecutive confirmed
POSTs, but it did NOT simulate a failed follow-up GET and GET-only
recovery. The original delivery report's claim "PASS — frontend
observable steps (existing) + server-side single-event count (new)"
for PR07A-12 was therefore overstated: the combined end-to-end
sequence (POST 200 → GET 503 → recovery GET → exactly one event in
DB) was not proven as a single integrated sequence.

**Correction:** a new test
`test_confirmed_post_then_failed_get_then_recovery_leaves_exactly_one_event`
proves the complete E1 sequence end-to-end against real PostgreSQL:

1. `_build_case` POSTs create + note + transition (the case has one
   `note_added` event).
2. A second confirmed POST /notes adds a second `note_added` event.
3. An armed one-shot `_IntermittentSessionFactory` wrapper is armed to
   fail the next `session_factory()` call with
   `ApiError(503, SERVICE_NOT_READY)` — the production contract for a
   transiently unavailable database, raised through the same
   `_case_service` / `require_authenticated` path that real
   DB-unavailability would take (the wrapper sits where the real
   `DatabaseSessionFactory` sits in `app.state`).
4. GET /history returns 503 `SERVICE_NOT_READY`.
5. GET /history again returns 200 (the wrapper has disarmed).
6. The database still contains exactly two `note_added` events — one
   per confirmed POST. No duplicate was written by the failed GET, the
   recovery GET, or any retry path.

The existing `test_confirmed_note_post_creates_exactly_one_event` is
unchanged — it isolates the per-mutation invariant; the new test
proves the full sequence. The 503 is exercised through the production
path (not a mock), and the test does NOT falsely claim the prior
backend test exercised a GET 503.

**Verification:** 3 tests in `test_persistence_equivalence.py` green
at `d594d06` (D5 in-process restart equivalence + the two E1 tests).

### 6.4 K6 parameterized-GET coverage with persisted case (Issue 4)

**Site:** `backend/tests/test_synthetic_boundary_sweep.py`,
`TestDisabledSourceExposureSweep.test_parameterized_gets_do_not_leak_synthetic_payload_with_persisted_case`.

**Defect:** the existing
`test_no_get_endpoint_exposes_synthetic_content` swept the
non-parameterized GET paths against an empty case table. The OpenAPI
completeness assertion explicitly EXCLUDED parameterized GETs
(``"{" not in path``), and with the case table empty there was no
real `case_id` to substitute into `/api/v1/cases/{case_id}` and
`/api/v1/cases/{case_id}/history`. The K6 invariant was therefore not
proven for the parameterized GET surface.

**Correction:** a new test
`test_parameterized_gets_do_not_leak_synthetic_payload_with_persisted_case`
warms a case from the synthetic source while
`demonstration_sources=True`, then recreates the application with the
flag disabled and probes all four parameterized GETs against the
persisted case:

- `/api/v1/cases/{case_id}` → 200 (the case exists; the disabled flag
  does not gate reads of already-persisted cases)
- `/api/v1/cases/{case_id}/history` → 200
- `/api/v1/sources/{source_id}` → 404 `SOURCE_NOT_FOUND` (the registry
  is empty when the flag is disabled, so even the
  `synthetic-demonstration` source ID is unresolvable)
- `/api/v1/synthetic/records/{record_ref}` → 503 `SERVICE_NOT_READY`

A new `SYNTHETIC_RECORD_PAYLOAD_MARKERS` set distinguishes the
fictional record body (`SYNTHETIC DEMONSTRATION RECORD`, `Fictional
administrative record`, `Synthetic evidence:`, `Synthetic context:`,
`Synthetic data does not reflect the verified ULB benchmark`,
`NOT A RESEARCH FINDING`) from the case's own provenance refs
(`synth-001`, `synthetic-v1`, `synthetic-demonstration`) which
legitimately persist on the case row. The test asserts no parameterized
GET body carries any payload marker; a final sanity assertion confirms
the case detail body DOES carry the case's own provenance refs (these
are the case's identity, not a leak).

The existing `test_no_get_endpoint_exposes_synthetic_content` is
preserved with its non-parameterized GET sweep intact (its OpenAPI
completeness assertion was already correct for the non-parameterized
half of the surface). The K6 final status moves from "GAP" to **PASS**
with explicit coverage of both halves.

**Verification:** 3 tests in `test_synthetic_boundary_sweep.py` green
at `d594d06` (non-parameterized sweep + parameterized-with-persisted-case
+ creation gate).

### 6.5 Net production-code delta in this bounded correction

Zero. The PR07A-D1 production fix (defect log §1) is preserved
unchanged. The 11 repository files modified by PR-07A are the same 11
files; three of them (the three backend test files above) received a
bounded correction on top of their `d6d4afc` state. No new product
features; no API contract changes; no migrations; no frozen research
artifacts touched.
