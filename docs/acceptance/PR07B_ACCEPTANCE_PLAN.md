# PR-07B Acceptance Plan

**Milestone:** PR-07B — Release Candidate Acceptance
**Baseline commit:** `351aded20d4dca1b243f6db6846dcbc22dc6ff33` (`main`, PR #1 merge)
**Branch:** `pr-07b-rc-verification`
**Plan owner:** PR-07B verification (coding AI)
**Reference CI:** GitHub Actions run `43395916677` (5/5 jobs passing on `351aded`)

---

## 1. Objective

Verify the existing PEIARS stack at commit `351aded` as an integrated,
reproducible, security-conscious scientific investigation workbench
and produce an evidence-backed release-candidate readiness assessment.

**Primary principle:** VERIFY FIRST. CHANGE ONLY WHAT IS NECESSARY TO
CORRECT A REPRODUCIBLE RELEASE-BLOCKING DEFECT.

This is not a feature-development PR. The final outcome may be GO,
CONDITIONAL GO or NO-GO based on actual evidence.

---

## 2. Scope

PR-07B covers twelve acceptance gates (RC-01 through RC-12):

1. **RC-01** — Clean-checkout reproducibility.
2. **RC-02** — Windows 11 local acceptance.
3. **RC-03** — Docker Compose release lifecycle.
4. **RC-04** — Desktop layout acceptance (1024/1280/1366/1440 CSS px).
5. **RC-05** — Full authenticated investigation workflow (real PostgreSQL).
6. **RC-06** — Concurrent reviewer acceptance.
7. **RC-07** — Failure injection and recovery (A: backend restart; B: DB unavailable; C: unmigrated; D: confirmed POST + failed GET; E: uncertain POST; F: stale response race).
8. **RC-08** — Security integration (auth, sessions, cookies, RBAC, CSRF, Origin, configuration).
9. **RC-09** — Provenance and scientific honesty.
10. **RC-10** — Frozen research integrity (28/28).
11. **RC-11** — GitHub Actions and reproducibility (5 jobs).
12. **RC-12** — Release-candidate decision (GO / CONDITIONAL GO / NO-GO).

Explicit non-goals are listed in the contract §3 (no new application
functionality, no CSV upload, no live ML execution, no PCA, no
ULB/PMGSY-III integration, no new auth providers, no new RBAC roles,
no cloud/K8s, no dependency upgrades, no frozen-research changes).

---

## 3. Stages

| Stage | Description | Owner | Status |
|---|---|---|---|
| 1 | Repository and baseline audit (verify `351aded`, create branch) | coding AI | DONE |
| 2 | Acceptance matrix and environment preparation | coding AI | DONE |
| 3 | Execute available automated acceptance | coding AI | DONE |
| 4 | Full-stack operator workflows | coding AI (Linux) + maintainer (Windows/Compose) | DONE for Linux; NOT RUN for Windows/Compose |
| 5 | Desktop compatibility and security integration | coding AI | DONE |
| 6 | Correct confirmed release-blockers only | coding AI | NONE FOUND (no production code changes) |
| 7 | Release-candidate dossier (this plan + 8 companion documents) | coding AI | DONE |
| 8 | Final delivery (changed-files ZIP + manifest) | coding AI | DONE |

The required stage sequence is defined in the contract §23. Stages 1-7
are executed in this delivery; Stage 8 produces the deliverable
archive.

---

## 4. Environments

Three execution environments are tracked:

1. **Linux sandbox (this delivery)** — the coding AI's environment.
   See `PR07B_ENVIRONMENT_MATRIX.md` §2. Available: Python 3.12.16,
   Node 24, pgserver 16.x, Playwright Chromium. NOT available: Docker,
   Windows, GitHub-hosted CI (branch not pushed).
2. **GitHub Actions `ubuntu-latest`** — the reference CI environment
   (run `43395916677`). See `PR07B_ENVIRONMENT_MATRIX.md` §3.
3. **Windows 11 (maintainer local)** — documented in
   `docs/dev/LOCAL_STARTUP_WINDOWS.md`; PR-07B acceptance procedure in
   `PR07B_WINDOWS_RUNBOOK.md`. Executed by the maintainer, NOT by the
   coding AI.

---

## 5. Gates, scenarios and owners

| Gate | Scenario | Owner | Execution env | Method |
|---|---|---|---|---|
| RC-01 | Clean-checkout reproducibility | coding AI | Linux sandbox | `ci/pr07b_acceptance_smoke.py` (prerequisite checks) + existing `test_env_boot.py`, `test_db_config_validation.py`, `test_dependency_lock.py`, `test_migrations.py`, `test_app_factory.py` (reused-environment regression); actual clean-checkout reproduction NOT RUN |
| RC-02 | Windows 11 local acceptance | maintainer | Windows 11 | `PR07B_WINDOWS_RUNBOOK.md` (NOT RUN by coding AI) |
| RC-03 | Docker Compose lifecycle | maintainer | Docker-equipped env | `PR07B_COMPOSE_RUNBOOK.md` + `ci/container_smoke_test.sh` (NOT RUN by coding AI — no Docker in sandbox) |
| RC-04 | Desktop layout (1024/1280/1366/1440) | coding AI | Linux + Chromium | E2E tests #16/#17/#18 (`playwright/e2e.spec.ts`) |
| RC-05 | Full authenticated investigation workflow | coding AI | Linux + pgserver + Chromium | E2E tests #1-#9 (individual steps) + new E2E test #19 (one continuous authenticated same-case browser workflow) |
| RC-06 | Concurrent reviewer | coding AI | Linux + pgserver | `backend/tests/test_concurrency_http.py` (C1 barrier-proven HTTP concurrency — PASS); two-browser operator workflow NOT RUN |
| RC-07-A | Backend restart | coding AI | Linux + pgserver + subprocess | `backend/tests/test_restart_outage_recovery.py::test_full_scenario` (I1/I2) |
| RC-07-B | Database unavailable | coding AI | Linux + pgserver | `test_restart_outage_recovery.py` (I3/I4/I5/I6) |
| RC-07-C | Unmigrated or outdated database | coding AI | Linux + pgserver | `backend/tests/test_db_readiness.py` (J1-J8) |
| RC-07-D | Confirmed POST, failed follow-up GET | coding AI | Linux + pgserver | `backend/tests/test_persistence_equivalence.py::test_confirmed_post_then_failed_get_then_recovery_leaves_exactly_one_event` + E2E #15 |
| RC-07-E | Uncertain POST outcome | coding AI | Linux + Vitest | `frontend/tests/integration/mutation-reliability.test.tsx` (NOTE: POST timeout test) |
| RC-07-F | Stale response race | coding AI | Linux + Vitest | `frontend/tests/integration/conflict-recovery-race.test.tsx` + `stale-selection-races.test.tsx` |
| RC-08 | Security integration | coding AI | Linux + pgserver | `test_rbac_boundary_sweep.py`, `test_csrf_origin_invariants.py`, `test_event_attribution_and_routes.py`, `test_auth_*` existing suite |
| RC-09 | Provenance and scientific honesty | coding AI | Linux + pgserver | `test_synthetic_boundary_sweep.py` (K5/K6) + `test_source_registry.py` + `test_case_api.py` |
| RC-10 | Frozen research integrity | coding AI | Linux | `ci/check_frozen_integrity.py` (28/28) |
| RC-11 | GitHub Actions (5 jobs) | maintainer | GitHub Actions | NOT RUN against PR-07B commit (branch not pushed); reference run `43395916677` for `351aded` |
| RC-12 | Release-candidate decision | coding AI | n/a | `PR07B_RELEASE_DECISION.md` |

---

## 6. Expected results (per gate)

| Gate | Expected | Actual | Status |
|---|---|---|---|
| RC-01 | Reproducible from clean checkout with documented tools | Prerequisite smoke checks PASS; reused-environment regression PASS; actual clean-checkout reproduction NOT RUN | PARTIAL |
| RC-02 | Windows 11 acceptance procedure executable | Procedure documented; Windows execution NOT RUN by coding AI | NOT RUN |
| RC-03 | Compose lifecycle: 11 smoke checks pass; persistence across restarts | No Docker in sandbox | NOT RUN |
| RC-04 | Desktop layout correct at 1024/1280/1366/1440; no page-wide overflow | E2E #17 (DesktopGate at 1023 vs 1024) + #18 (no overflow at 1024/1280/1366/1440) PASS | PASS |
| RC-05 | Full authenticated workflow: login → create case → note → transition → decision → logout → re-login → case persists | E2E #1-#9 (individual steps) + new E2E #19 (integrated continuous workflow) PASS | PASS |
| RC-06 | Two reviewers, one 200 + one 409, version N+1, exactly one new event, winner-attributed | `test_concurrency_http.py` PASS (HTTP-level); two-browser operator workflow NOT RUN | PARTIAL |
| RC-07-A | Backend restart preserves cases/events; session survives | `test_restart_outage_recovery.py` I1/I2 PASS | PASS |
| RC-07-B | DB outage → readiness 503, liveness 200, no stale healthy; recovery → 200, writes succeed | `test_restart_outage_recovery.py` I3-I8 PASS | PASS |
| RC-07-C | Unmigrated → readiness detects; explicit migration → readiness recovers | `test_db_readiness.py` J1-J8 PASS | PASS |
| RC-07-D | POST 200 + GET 503 + recovery GET → exactly one event; UI no duplicate POST | integrated E1 pytest + E2E #15 PASS | PASS |
| RC-07-E | Transport failure → no auto-retry, distinct "uncertain outcome" copy, draft preserved | `mutation-reliability.test.tsx` NOTE timeout test PASS | PASS |
| RC-07-F | Stale detail/history/evidence/conflict-recovery cannot overwrite current selection | `conflict-recovery-race.test.tsx` + `stale-selection-races.test.tsx` PASS | PASS |
| RC-08 | Auth/sessions/cookies/RBAC/CSRF/Origin/configuration invariants hold | All security tests PASS | PASS |
| RC-09 | Synthetic labelled; provenance retained; no payload leak when disabled; no fraud claim | `test_synthetic_boundary_sweep.py` K5/K6 + existing PASS | PASS |
| RC-10 | 28/28 frozen artifacts match | `ci/check_frozen_integrity.py` exit 0 | PASS |
| RC-11 | 5 GHA jobs green against PR-07B commit | Branch not pushed | NOT RUN |
| RC-12 | GO / CONDITIONAL GO / NO-GO based on evidence | See `PR07B_RELEASE_DECISION.md` | CONDITIONAL GO |

---

## 7. Stop conditions

Per contract §25, work stops and is reported if:

- Baseline `351aded` cannot be verified. *(Not triggered — verified.)*
- The checkout contains unexpected changes. *(Not triggered — clean tree.)*
- The frozen artifact integrity check fails. *(Not triggered — 28/28.)*
- An acceptance test would affect shared or production data. *(Not triggered — all tests use disposable pgserver.)*
- A security validation requires weakening security controls. *(Not triggered.)*
- A production fix requires a major architecture change. *(Not triggered — no production fix required.)*
- A schema migration is necessary but not authorized. *(Not triggered — no migration needed.)*
- The testing environment cannot safely isolate required resources. *(Not triggered.)*
- Significant unexplained regression occurs. *(Not triggered — 574/574 backend, 115/115 frontend, 19/19 E2E, 28/28 frozen.)*

For ordinary missing environment capabilities (Docker, Windows,
GitHub-hosted CI), the relevant gates are marked NOT RUN and the
remaining work proceeds.

---

## 8. Deliverables

The nine required documents under `docs/acceptance/`:

1. `PR07B_ACCEPTANCE_PLAN.md` (this document).
2. `PR07B_TEST_MATRIX.md`.
3. `PR07B_ENVIRONMENT_MATRIX.md`.
4. `PR07B_WINDOWS_RUNBOOK.md`.
5. `PR07B_COMPOSE_RUNBOOK.md`.
6. `PR07B_EVIDENCE_REGISTER.md`.
7. `PR07B_DEFECT_REGISTER.md`.
8. `PR07B_RELEASE_DECISION.md`.
9. `PR07B_DELIVERY_REPORT.md`.

Plus one acceptance automation script:

- `ci/pr07b_acceptance_smoke.py` (single-command reproducibility verifier).

The final delivery archive `PEIARS_PR07B_changed_files.zip` contains
the nine markdown documents, the smoke script, and the SHA-256
manifest. No production code changes; no new tests required (the
PR-07A suite already covers every executable RC gate).
