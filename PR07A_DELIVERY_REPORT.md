# PR-07A Delivery Report — Adversarial Reliability and Security Hardening

**Authoritative baseline:** `21761408f31d6c0e9ff4ff502c0c98f0897f79cd`
(`main`, tag `pr-06b-accepted`)
**Final development commit:** `d594d0682284ac9ca96c4e5a144ec23d3da19a24`
(branch `pr-07a-dev`; bounded-correction commit on top of
`d6d4afc9a66b5145086e71e1200380ac9488ecc6`)
**Scope:** PR-07A Stages 3-7 + one bounded-correction round. No
PR-07B work. No new product features.

---

## 1. Baseline and final commit

| | |
|---|---|
| Baseline | `2176140` — verified at Stage 1 as head of `main`, clean tree, `pr-06b-accepted` tag dereferences to the same SHA |
| Dev branch | `pr-07a-dev`, created from the baseline during Stage 1/2 and left untouched until this authorization |
| Stage 3-6 commit | `d6d4afc9a66b5145086e71e1200380ac9488ecc6` — `test(pr07a): adversarial reliability suite; fix conflict-recovery stale guard` |
| Bounded-correction commit (final) | `d594d0682284ac9ca96c4e5a144ec23d3da19a24` — `test(pr07a): bounded corrections — env scope, harness cleanup, E1 integrated, K6 parameterized` |
| Production code changed | exactly one function in one file (`handleReloadAfterConflict`, `frontend/src/pages/InvestigationsPage.tsx`, +11/-1 lines) — RED-justified (PR07A-D1), unchanged by the bounded-correction commit |

## 2. Changed-file inventory

Repository files (11, the same set across `d6d4afc` and `d594d06`;
three of the eleven received a bounded correction at `d594d06`):

| File | Change |
|---|---|
| `frontend/src/pages/InvestigationsPage.tsx` | PR07A-D1 fix: selection-generation guard on the conflict-recovery success/error/finally paths (unchanged by `d594d06`) |
| `frontend/tests/integration/index-refresh-race.test.tsx` | rewritten: genuine overlap for A1/A2/A3 (replaces the two non-racing tests; unchanged by `d594d06`) |
| `frontend/tests/integration/conflict-recovery-race.test.tsx` | new: B3-1/2/3 (RED→GREEN) + B3-4 GET-only recovery control (unchanged by `d594d06`) |
| `frontend/tests/integration/stale-selection-races.test.tsx` | new: B1/B2/B4 sleep-free + E4 no-second-POST (unchanged by `d594d06`) |
| `backend/tests/test_concurrency_http.py` | new: C1 barrier-proven HTTP concurrency + C3 repeated stale mutation (unchanged by `d594d06`) |
| `backend/tests/test_event_attribution_and_routes.py` | new: D1 spoofed actor, D2-HTTP, D4 route contract, K5 provenance immutability (unchanged by `d594d06`) |
| `backend/tests/test_rbac_boundary_sweep.py` | new: G2-G6 with DB-side assertions, G8 executable N/A, G9 anonymous sweep (unchanged by `d594d06`) |
| `backend/tests/test_csrf_origin_invariants.py` | new: H4 rotation replay, H5 authenticated cross-origin, H7 no-mutation invariants, F1 expiry boundary (unchanged by `d594d06`) |
| `backend/tests/test_persistence_equivalence.py` | D5 in-process restart equivalence + E1 server-side single-event invariant; **bounded correction at `d594d06`**: added `test_confirmed_post_then_failed_get_then_recovery_leaves_exactly_one_event` (integrated E1 sequence with armed one-shot 503, defect log §6.3) |
| `backend/tests/test_restart_outage_recovery.py` | I1-I8 subprocess restart/outage/recovery scenario; **bounded correction at `d594d06`**: env-var scope via `pytest.MonkeyPatch`/`undo` (defect log §6.1) and harness resource cleanup — `communicate()` pipe drain, resource-list `finally` block (defect log §6.2) |
| `backend/tests/test_synthetic_boundary_sweep.py` | K6 disabled-source endpoint sweep + creation gate; **bounded correction at `d594d06`**: added `test_parameterized_gets_do_not_leak_synthetic_payload_with_persisted_case` covering all four parameterized GETs against a warmed-then-disabled-source case (defect log §6.4) |

Delivery-only files (ZIP root, not committed): `PR07A_BASELINE_AUDIT.md`,
`PR07A_TEST_MATRIX.md`, `PR07A_DEFECT_LOG.md`,
`PR07A_DELIVERY_REPORT.md`, `PR07A_FILE_MANIFEST.csv`.

## 3. Per-requirement verification matrix (final statuses)

| ID | Requirement | Final status |
|---|---|---|
| PR07A-01 | Baseline commit verified | **DONE** (Stage 1) |
| PR07A-02 | Overlapping index success race | **PASS** — BASELINE GREEN + negative control (guards removed → test fails) |
| PR07A-03 | Overlapping index failure race | **PASS** — BASELINE GREEN + negative control |
| PR07A-04 | Superseded-refresh warning semantics | **PASS** — BASELINE GREEN (A3-i/A3-ii) |
| PR07A-05 | Stale case detail/history blocked | **PASS** — BASELINE GREEN, sleep-free |
| PR07A-06 | Stale source evidence blocked | **PASS** — BASELINE GREEN |
| PR07A-07 | Stale conflict-recovery blocked | **PASS** — RED→GREEN (PR07A-D1; defect log §1) |
| PR07A-08 | Two-reviewer real-PostgreSQL concurrency | **PASS** — HTTP level; overlap proven by an in-flight UPDATE barrier; exactly one 200 + one 409; version N+1; one new event; winner-attributed |
| PR07A-09 | 409 UI recovery preserves intent | **PASS** — recovery is GET-only (B3-4) + existing E2E #11/#13 |
| PR07A-10 | Rejected mutation leaves no event | **PASS** — existing + HTTP-level 422 invariant |
| PR07A-11 | Event ordering and attribution | **PASS** — spoofed actor_ref/created_by overwritten by principal UUID on all four mutation types |
| PR07A-12 | Confirmed POST + failed GET, no duplicate | **PASS** — frontend observable steps (existing) + server-side single-event invariant (existing) + full POST→failed-GET→recovery integrated sequence on real PostgreSQL (new at `d594d06`; defect log §6.3) |
| PR07A-13 | Uncertain outcome, no unsafe retry | **PASS** — POST count stays 1; distinct copy; draft preserved |
| PR07A-14 | Session expiry verified | **PASS** — existing + `expires_at = now()` boundary |
| PR07A-15 | Logout invalidates session | **PASS** (existing; also re-verified post-restart in I2) |
| PR07A-16 | Cookie attributes | **PASS** (existing) |
| PR07A-17 | Production cookie validation | **PASS** (existing env-loading rejection) |
| PR07A-18 | Viewer direct-API mutations rejected | **PASS** — all four routes 403 with zero rows/events |
| PR07A-19 | Reviewer/admin boundaries | **PASS** — no admin-only HTTP route exists (executable N/A assertion) |
| PR07A-20 | Invalid CSRF rejected, no mutation | **PASS** — existing + H7 version/event invariants |
| PR07A-21 | Cross-origin write rejected, no mutation | **PASS** — authenticated mutation + valid CSRF + bad Origin → 403, no mutation |
| PR07A-22 | nginx proxied auth/origin | **PARTIAL** — backend-level `$http_host` semantics verified in PR-06B; Compose-level NOT RUN (no Docker) |
| PR07A-23 | Backend restart preserves cases/events | **PASS** — true subprocess SIGTERM/restart, full history identical; env-scope and harness-cleanup hardened at `d594d06` (defect log §6.1/§6.2) |
| PR07A-24 | Session restart behavior | **PASS** — DB-backed session survives restart; logout still revokes |
| PR07A-25 | DB outage → unready | **PASS** — readiness 503 with all probes non-ready; liveness 200; no stale healthy state while down |
| PR07A-26 | Recovery restores readiness + access | **PASS** — bounded polling to 200; case readable; write succeeds (pool recovery) |
| PR07A-27 | Migration-aware readiness | **PASS** (existing six probes; unchanged) |
| PR07A-28 | Synthetic source explicitly identified | **PASS** (existing) |
| PR07A-29 | No synthetic→genuine confusion | **PASS** — provenance fields absent from all mutation schemas; non-parameterized GET sweep clean (existing); parameterized GET sweep against a persisted case clean (new at `d594d06`; defect log §6.4); creation gated |
| PR07A-30 | 28 frozen artifacts intact | **PASS** — 28/28 at `d594d06` |
| PR07A-31 | Existing regressions preserved | **PASS** — 574/115/18 all green post-change |
| PR07A-32 | Container smoke / Compose | **NOT RUN** (no Docker daemon; design unchanged; maintainer CI run `43273888391` referenced for the pre-PR-07A state) |
| PR07A-33 | No production secrets / unsafe test resources | **PASS** — all new tests use disposable pgserver instances, ephemeral subprocesses, deterministic test-only secrets; IAC env mutation scoped via `pytest.MonkeyPatch`/`undo` at `d594d06` (defect log §6.1) |
| PR07A-34 | No new product features / PR-07B scope | **PASS** — one RED-justified guard fix; everything else is tests |
| PR07A-35 | New tests exercise claimed failure paths | **PASS** — deferred-promise resolution ordering, in-flight UPDATE barrier, negative control on the index guards, no sleep-based race orchestration, armed one-shot 503 through the production `_case_service` path |
| PR07A-36 | Production changes have defect justification | **PASS** — exactly one production change, with recorded RED evidence (defect log §1); the bounded-correction commit makes zero production changes |

Totals: 34 PASS (of which 1 RED→GREEN), 1 PARTIAL (PR07A-22,
Compose-level), 1 NOT RUN (PR07A-32, Docker), 0 FAIL.

## 4. Baseline-green findings

The audit's central suspicion — that the *production* async guards were
sound but *untested* — held for every workstream except B3: A1/A2/A3,
B1/B2/B4, C1 (service and HTTP level), E4, D1/D2/D4/D5, E1, F1, G2-G9,
H4/H5/H7, I-series and K5/K6 were all BASELINE GREEN. The three
pre-existing test-quality defects (non-racing "race" tests A1/A2;
sequential C1; sleep-based B1) were repaired (defect log §2). No
production change was made anywhere except the RED-demonstrated B3.

## 5. Red-to-green defect evidence (PR07A-D1)

See `PR07A_DEFECT_LOG.md` §1 for the full record: three deterministic
RED failures on the unchanged baseline (stale success overwrite —
`expected <h2 class="inv__case-title"> to be null`; stale failure —
Case B evidence replaced by an error panel; stale finally — loading
state cleared while Case B still loading), the 11-insertion guard fix,
and the GREEN rerun (4/4 in the file, 115/115 frontend, 18/18 E2E).

## 6. PostgreSQL concurrency and restart evidence

**Concurrency (C1, `test_concurrency_http.py`):** two separately
authenticated reviewer TestClients over the pgserver-backed app; both
read version 1; both POST notes with `expected_version=1`, released
simultaneously by a dispatch barrier; a second in-flight barrier inside
`before_cursor_execute` fires only when both transactions are about to
execute `UPDATE review_cases` (overlap proof — a sequential run would
break the barrier). Outcome asserted at the DB level: exactly one 200 +
one 409, final version 2, exactly two events total, the single
`note_added` event attributed to the winning reviewer's user UUID, and
a repeated stale attempt still 409 with no further events.

**Restart/outage/recovery (I1-I8, `test_restart_outage_recovery.py`):**
a test-owned pgserver instance (own temporary data directory, separate
from the shared session fixtures) and a test-owned `uvicorn
app.main:create_app --factory` subprocess on a free port. Scenario:
boot → readiness 200 → login → create case + 3 events → SIGTERM
(bounded exit wait) → restart → readiness 200 → case/history/UUID/
version/status/record-ref/event sequence identical → the pre-restart
session cookie still authorizes → `pg_ctl stop -m fast` → readiness
truthfully 503 (every probe non-ready; polled continuously — no stale
200 while down) while liveness stays 200 → `ensure_postgres_running()`
→ bounded polling back to readiness 200 → the case is readable → a new
note POST succeeds (pool recovered through the outage) → logout revokes
the session. Runtime ≈7 s; all waits are bounded-deadline polls.

**In-process restart equivalence (D5):** fresh engine + fresh
`create_app` against the same database observe byte-identical case and
event state.

## 7. Frontend race-test evidence

All new frontend race tests use deterministic deferred promises with
test-owned resolvers and fixed microtask flushing — no
`setTimeout`-based race orchestration, no reliance on React StrictMode
double-effects, and no inaccessible buttons. The production refresh
path exercised is the real one (post-mutation non-blocking
`refreshIndex`, the Retry button, the "Refresh case list" button). The
index-refresh tests additionally carry a recorded negative control:
with the production guards temporarily removed (scratch run, restored
byte-exact afterwards), A1/A2/A3-i fail — proving the tests fail when
stale responses are incorrectly applied. The B3 tests held Case A's
recovery GETs pending across a real selection change to Case B.

## 8. Security regression evidence

| Property | Verification |
|---|---|
| Authentication | 550 pre-existing auth/session/cookie/throttle tests unchanged and green; `expires_at = now()` boundary added |
| Session fixation / rotation | login rotates the CSRF token; pre-login token replay → 403, no mutation (H4) |
| CSRF | signed double-submit verified missing/incorrect/mismatched/unsigned (existing) + rotation replay + authenticated cross-origin Origin rejection with version/event invariants (H4/H5/H7) |
| RBAC | viewer rejected on all four case mutation routes with DB-side zero-row/zero-event assertions; anonymous mutations fail closed (401/403/503 per configuration, never 2xx, no side effects); no admin-only HTTP route exists (executable assertion) |
| Attribution | spoofed `actor_ref`/`created_by` never appear in events; the principal UUID always does |
| Append-only audit trail | DB trigger (existing) + no PUT/PATCH/DELETE in the OpenAPI contract + live 404/405 probes + rejected-mutation byte-identical event tables |
| Secrets | no secrets in the diff; test secrets are deterministic, clearly test-only, ≥32 chars, same pattern as the existing suite |
| Production hardening | all config fail-closed tests (env-boot, production cookie rejection) unchanged and green |

## 9. Full suite results (executed 2026-11-13, sandbox environment)

| Suite | Command | Result |
|---|---|---|
| Backend | `python -m pytest -q` (real pgserver PostgreSQL) | **574 passed** (550 baseline + 22 PR-07A + 2 bounded-correction additions: integrated E1, parameterized K6), 61.6 s |
| Frontend typecheck | `npm run typecheck` | PASS |
| Frontend lint | `npm run lint` (`--max-warnings=0`) | PASS |
| Frontend Vitest | `npm run test -- --run` | **115 passed** (21 files; 105 baseline + 10 net new from PR-07A), 21.3 s |
| Frontend build | `npm run build` | PASS |
| OpenAPI drift | `npm run openapi:check` | PASS ("no drift") |
| Browser E2E | `bash frontend/scripts/run-e2e.sh` (disposable pgserver) | **18 passed**, 31.5 s |
| Frozen research integrity | `python ci/check_frozen_integrity.py` | **28/28 match**, exit 0 |

Environment: Linux sandbox; Python 3.12 venv; pgserver-packaged
PostgreSQL 16.x (disposable instances); Node/npm toolchain; Playwright
Chromium headless shell 158.0.8127.18 (v1254). One environmental note:
the first E2E attempt failed because the Playwright browser binary was
not cached in this recycled sandbox; after `npx playwright install
chromium` the suite passed 18/18. No application defect was involved.

A pre-existing flake in
`tests/integration/keyboard-interaction.test.tsx > Arrow Right moves
focus to the next tab and Enter activates it` surfaced on one Vitest
run during this correction cycle (it asserts `expect(element).toHaveFocus()`
after a `userEvent.keyboard` arrow-right); the test passes reliably in
isolation (`npx vitest run tests/integration/keyboard-interaction.test.tsx`
→ 4/4 green) and the full Vitest suite passed 115/115 on a re-run. No
production code or test from this correction touches the keyboard-
interaction module; the flake predates PR-07A and is unrelated to the
four bounded corrections.

## 10. Frozen integrity verification

`ci/check_frozen_integrity.py`: **28/28 files match** at `d594d06`
(exit 0). No frozen research artifact was modified; the four
`frontend/screenshots/*.png` files that the E2E run regenerated were
reverted to their committed bytes before the commit (they are not part
of the frozen manifest, but binary churn was excluded from the delivery
regardless).

## 11. Docker / CI NOT RUN items

- **Container smoke test** (`ci/container_smoke_test.sh`, 11 checks):
  NOT RUN — no Docker daemon in the execution sandbox. The script and
  Compose design are unchanged by this PR. Maintainer-side evidence for
  the pre-PR-07A state: CI run `43273888391`.
- **Compose-level restart/rebuild persistence** (workstream I at the
  container level): NOT RUN for the same reason; the backend-level
  restart/outage/recovery guarantees are fully covered by the I-series
  subprocess tests.
- **GitHub-hosted CI (the five workflow jobs):** NOT RUN and explicitly
  not claimed — the branch has not been pushed, so no job has executed
  against `d6d4afc`. The maintainer should push `pr-07a-dev` and let
  the five jobs run (no workflow file was changed; least-privilege
  permissions and SHA-pinned actions untouched).
- **Checks requiring Windows 11:** the import-time Windows
  selector-loop install in `backend/scripts/serve.py` is exercised by
  the maintainer's local Windows environment/CI, not by this sandbox;
  no change in this PR touches it.

## 12. Outstanding limitations

1. PR07A-22 remains PARTIAL at the Compose level (backend-level
   `$http_host` semantics were proven in PR-06B; the nginx proxy path
   needs a Docker-equipped run of the container smoke test).
2. PR07A-32 (container smoke) requires Docker — pending maintainer
   execution.
3. GitHub Actions must run post-push before merge (standard gate; not a
   defect).
4. The G9 status-code note (defect log §3): anonymous case mutations
   are rejected fail-closed with 403 `CSRF_TOKEN_INVALID` rather than
   401 because the CSRF dependency evaluates first. Semantically 401
   would be preferable, but no defect is demonstrated and no change was
   made; recorded for a future API-polish PR if the maintainer wants
   it.
5. The I-series scenario uses `localhost` subprocesses on Linux; the
   Windows-specific process-signal behaviour is covered by the
   maintainer's environments, not here.

## 13. Scope compliance

- No PR-07B release-candidate work; no CSV upload; no live Isolation
  Forest/LOF execution; no PCA visualization; no ULB/PMGSY-III
  integration; no UI redesign; no mobile layouts; no new auth
  providers; no new RBAC roles; no database migrations; no cloud/K8s;
  no dependency upgrades.
- API contracts unchanged (`openapi:check` green; `contracts.gen.ts`
  unchanged); architecture, authentication guarantees and desktop
  layout preserved (E2E suite — including the 1024px desktop gate —
  green).
- All 28 frozen scientific artifacts preserved (28/28).
- Synthetic demonstration records remain explicitly labelled; no
  conflation with genuine research findings (K-series green).
- One production change only, RED-justified (PR07A-D1).

## 14. Delivery manifest and integrity verification

`PEIARS_PR07A_changed_files.zip` (this bounded-correction delivery,
supersedes the previous ZIP) contains the 11 changed repository files
at their repository-relative paths (with the three bounded-corrected
backend test files in their `d594d06` state) plus the four Markdown
deliverables and `PR07A_FILE_MANIFEST.csv` at the archive root.
`PR07A_FILE_MANIFEST.csv` records `path,sha256,bytes` for every
archive member. The archive was reopened after generation and every
member was verified against the manifest (byte size + SHA-256), and
the ZIP's own SHA-256 is recorded in the delivery message. The bundle
was built by `scripts/assemble_pr07a_delivery.py` (in the sandbox
scripts area, not part of the repository delivery), which reads each
file's exact bytes from the working tree at `d594d06`.

## 15. Bounded corrections (independent ZIP audit feedback)

Independent inspection of the previous `PEIARS_PR07A_changed_files.zip`
identified four test-harness/report issues that required resolution
before merge. All four are corrected at commit `d594d06` on top of
`d6d4afc`; the PR07A-D1 production fix is preserved unchanged. See
`PR07A_DEFECT_LOG.md` §6 for the per-issue site, defect, correction
and verification record. Summary:

1. **iac_migrated env leakage** (`test_restart_outage_recovery.py`):
   the bare `os.environ["PEIARS_DATABASE_URL"] = iac_db_url` assignment
   is replaced with `pytest.MonkeyPatch().setenv(...)` + `mp.undo()` in
   `finally`, restoring the prior environment on both success and
   failure paths. Verified by a probe test confirming the env var is
   restored to the conftest `peiars_test` value (not left at the stale
   IAC URL) after the IAC test runs.
2. **Restart harness resource cleanup** (`test_restart_outage_recovery.py`):
   `_stop_backend` now drains stdio pipes via `communicate()`; the
   scenario tracks every backend process and httpx client in resource
   lists and closes/stops them in a single `finally` that runs on
   assertion-failure paths; `iac_server` wraps `server.cleanup()` in
   `try/finally` so the PG data dir is released even on mid-scenario
   failures. Disposable database isolation and bounded waits preserved.
3. **E1 integrated test** (`test_persistence_equivalence.py`):
   `test_confirmed_post_then_failed_get_then_recovery_leaves_exactly_one_event`
   proves the complete E1 sequence end-to-end on real PostgreSQL:
   POST 200 → armed 503 → GET /history 503 `SERVICE_NOT_READY` (raised
   through the production `_case_service`/`require_authenticated` path
   via a one-shot `_IntermittentSessionFactory` wrapper) → recovery
   GET 200 → exactly two `note_added` rows (no duplicate). The
   existing `test_confirmed_note_post_creates_exactly_one_event` is
   unchanged. The previous delivery report's claim that PR07A-12 was
   "PASS — server-side single-event count (new)" was overstated; the
   new integrated test closes that gap and the report now states the
   three complementary layers accurately.
4. **K6 parameterized-GET coverage** (`test_synthetic_boundary_sweep.py`):
   `test_parameterized_gets_do_not_leak_synthetic_payload_with_persisted_case`
   warms a case from the synthetic source while the flag is enabled,
   recreates the app with the flag disabled, and probes all four
   parameterized GETs against the persisted case. A new
   `SYNTHETIC_RECORD_PAYLOAD_MARKERS` set distinguishes the fictional
   record body from the case's own provenance refs (which legitimately
   persist on the case row). The existing non-parameterized sweep is
   preserved; K6 final status moves from "GAP" to PASS with both
   halves covered.

Net production-code delta in this bounded-correction round: **zero**.
The 11 repository files modified by PR-07A are the same 11 files; the
ZIP is a complete changed-files-only bundle (not a patch on the
previous ZIP), with the three corrected backend test files in their
`d594d06` state and the four markdown deliverables updated to reflect
the corrections.

**PR-07A is complete. No PR-07B work was started.**
