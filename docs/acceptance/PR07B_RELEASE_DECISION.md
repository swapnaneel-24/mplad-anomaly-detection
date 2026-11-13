# PR-07B Release Decision

**Milestone:** PR-07B — Release Candidate Acceptance
**Baseline commit:** `351aded20d4dca1b243f6db6846dcbc22dc6ff33`
**Branch:** `pr-07b-rc-verification`
**Decision date:** 2026-11-13
**Decision:** **CONDITIONAL GO**

---

## 1. Decision summary

PR-07B acceptance verification of the PEIARS stack at commit
`351aded` produces a **CONDITIONAL GO** release-candidate assessment.

Of the 16 technical-verification sub-gates, 11 PASS, 2 PARTIAL
(RC-01 prerequisite-only, RC-06 HTTP-level-only), and 3 NOT RUN
(RC-02 Windows 11, RC-03 Docker Compose, RC-11 GitHub-hosted CI).
No sub-gate FAILed. Zero production code changes were required; one
E2E test (#19, RC-05 integrated workflow) was added to close the
evidence gap between individual-step coverage and proof of one
continuous authenticated workflow.

The PEIARS workbench is suitable for a clearly bounded next use —
controlled synthetic demonstration and development of a read-only
scientific adapter — pending maintainer execution of the three NOT
RUN sub-gates and closure of the two PARTIAL evidence gaps.

The conditions are explicit, independently testable, and DO NOT
conceal any failed mandatory security or data-integrity check. No
release-blocking defect was found. Full GO is NOT claimed while
required acceptance remains outstanding.

---

## 2. Gate-by-gate assessment

Counting method: RC-07 is split into six sub-gates (A through F).
There are 16 technical-verification sub-gates plus RC-12 as the
release decision (not a technical gate). Results are the coding AI's
previously-reported Linux execution; they are NOT independently
re-executed by the reviewer.

| Gate | Status | Condition (if any) |
|---|---|---|
| RC-01 Clean-checkout reproducibility | **PARTIAL** | Prerequisite smoke checks PASS; reused-environment regression PASS; actual clean-checkout reproduction NOT RUN. Maintainer executes on a pristine machine to close. |
| RC-02 Windows 11 local acceptance | **NOT RUN** | Maintainer executes `PR07B_WINDOWS_RUNBOOK.md`; expected result 573 PASS / 1 FAIL (known harness limitation, see `PR07B_DEFECT_REGISTER.md` §2). |
| RC-03 Docker Compose release lifecycle | **NOT RUN** | Maintainer executes `PR07B_COMPOSE_RUNBOOK.md` on a Docker-equipped environment; expected result 11/11 smoke checks + persistence across restarts. Use shell-specific (Git Bash / PowerShell) credential generation. |
| RC-04 Desktop layout (1024/1280/1366/1440) | **PASS** | — |
| RC-05 Full authenticated investigation workflow | **PASS** | Individual E2E tests #1-#9 + new integrated workflow test #19 (added in this correction). |
| RC-06 Concurrent reviewer | **PARTIAL** | HTTP-level concurrency PASS via `test_concurrency_http.py`; two-browser operator workflow with visible conflict recovery NOT RUN. Maintainer may add a focused two-browser Playwright test or document the evidence gap. |
| RC-07-A Backend restart | **PASS** | — |
| RC-07-B Database unavailable | **PASS** | — |
| RC-07-C Unmigrated or outdated database | **PASS** | — |
| RC-07-D Confirmed POST + failed follow-up GET | **PASS** | — |
| RC-07-E Uncertain POST outcome | **PASS** | — |
| RC-07-F Stale response race | **PASS** | — |
| RC-08 Security integration | **PASS** | — |
| RC-09 Provenance and scientific honesty | **PASS** | — |
| RC-10 Frozen research integrity (28/28) | **PASS** | — |
| RC-11 GitHub Actions (5 jobs) | **NOT RUN** | Maintainer pushes `pr-07b-rc-verification` to the remote; expected result 5/5 jobs green against the PR-07B commit. |
| RC-12 Release-candidate decision (NOT a technical gate) | **CONDITIONAL GO** | This document. |

**Technical-verification sub-gate totals (16 entries):**
11 PASS, 0 FAIL, 2 PARTIAL (RC-01, RC-06), 3 NOT RUN (RC-02, RC-03, RC-11).

**Release decision (RC-12, separate):** CONDITIONAL GO.

---

## 3. Conditions for full GO

The CONDITIONAL GO becomes a full GO when the maintainer completes
the three NOT RUN sub-gates AND closes the two PARTIAL evidence gaps,
recording all results in `PR07B_EVIDENCE_REGISTER.md`:

### Condition 1 — Windows 11 local acceptance (RC-02)

The maintainer executes `docs/acceptance/PR07B_WINDOWS_RUNBOOK.md`
on Windows 11 and records:

- Backend pytest result. Expected: **573 PASS / 1 FAIL (known harness
  limitation)** — the identified
  `test_wrong_password_readiness_503_sanitized` fails on Windows 11
  with `pgserver` trust authentication. This is documented in
  `PR07B_DEFECT_REGISTER.md` §2 and `PR07B_ENVIRONMENT_MATRIX.md`
  §4.1 as a known harness limitation, NOT an application defect.
- Frontend typecheck/lint/Vitest/build/OpenAPI results. Expected: all
  PASS (115/115 Vitest).
- E2E result. Expected: 19/19 PASS (Playwright Chromium).
- Frozen integrity. Expected: 28/28 match.

Optional: the maintainer may verify incorrect-password rejection
using a disposable PostgreSQL instance configured with
`scram-sha-256` (see `PR07B_WINDOWS_RUNBOOK.md` §5.1). This is NOT
required for the CONDITIONAL GO → GO transition; the Linux 574/574
result is the authoritative test count.

### Condition 2 — Docker Compose release lifecycle (RC-03)

The maintainer executes `docs/acceptance/PR07B_COMPOSE_RUNBOOK.md`
on a Docker-equipped environment and records:

- 11-check container smoke test result. Expected: 11/11 PASS.
- Backend container restart preserves case/event data. Expected: PASS.
- Database container restart (no volume deletion) → readiness recovers
  to 200. Expected: PASS.
- Frontend container restart → browser-facing routes still work.
  Expected: PASS.
- No unrelated project/volume affected. Expected: PASS.

### Condition 3 — GitHub-hosted CI (RC-11)

The maintainer pushes `pr-07b-rc-verification` to the remote and
records:

- New GitHub Actions run ID.
- Per-job results for the five mandatory jobs (backend-tests,
  frozen-integrity, frontend, e2e, container). Expected: 5/5 green
  against the PR-07B commit.

The reference CI run `43395916677` (5/5 green on `351aded`) is the
pre-PR-07B state and is NOT PR-07B CI evidence.

### Condition 4 — Clean-checkout reproduction (RC-01 PARTIAL closure)

The maintainer executes the acceptance suite on a **pristine** machine
(fresh `git clone` → new Python 3.12 venv → `npm ci` from scratch →
full suite) and records:

- The machine OS and version.
- The fresh-venv `pip install -r requirements-lock.txt` result.
- The fresh `npm ci` result.
- Backend pytest result (expected 574 passed on Linux; 573/1 on
  Windows 11 with the documented harness limitation).
- Frontend typecheck/lint/Vitest/build/OpenAPI results.
- E2E result (expected 19 passed).
- Frozen integrity (expected 28/28).
- Acceptance smoke (expected 7/7).

This closes the gap between the prerequisite smoke checks (which
verify the environment in a reused sandbox) and actual clean-checkout
reproduction.

### Condition 5 — Two-browser operator workflow (RC-06 PARTIAL closure)

The maintainer either:

- **Adds a focused two-browser Playwright test** using the existing
  harness (`frontend/playwright/e2e.spec.ts`) that opens two browser
  contexts with two reviewer identities, both load the same case,
  reviewer A submits a mutation, reviewer B submits with a stale
  version and sees the 409 conflict in the UI, reviewer B reloads and
  retries successfully. OR
- **Documents the evidence gap explicitly** as an accepted limitation
  for the bounded next use (controlled synthetic demonstration),
  noting that the HTTP-level concurrency is barrier-proven by
  `test_concurrency_http.py` and the single-browser conflict recovery
  is covered by E2E tests #11 and #13.

This closes the gap between HTTP-level concurrency (PASS) and the
integrated two-browser operator workflow (NOT RUN).

---

## 4. Why NOT GO directly

The contract §17 defines GO as "All mandatory acceptance gates have
passed in the required environments. No unresolved blocker remains."
Three mandatory sub-gates (RC-02, RC-03, RC-11) have NOT executed in
their required environments (Windows 11, Docker, GitHub-hosted CI)
because the coding AI's Linux-only sandbox does not provide them.
Two sub-gates (RC-01, RC-06) are PARTIAL — the executed evidence is
sufficient for a bounded next use but does not constitute full
verification of the gate's scope (clean-checkout reproduction and
two-browser operator workflow respectively).

The contract §25 explicitly says: "For ordinary missing environment
capabilities, continue other safe work and report the relevant
checks as NOT RUN" — which is what this delivery does. The contract
§17 also says: "If a gate is NOT RUN, do not silently convert it
into PASS." This decision does NOT do so, and it does NOT convert
PARTIAL into PASS.

The application itself is verified: backend 574/574, frontend 115/115,
E2E 19/19 (18 previously reported + 1 new integrated workflow test),
frozen 28/28, OpenAPI no drift, all on real PostgreSQL via
pgserver. No production code change was required (no defect found).
The conditions are environmental or evidence-scope limitations, not
application defects.

---

## 5. Why NOT NO-GO

The contract §17 defines NO-GO triggers, including:

- Data loss or unrecoverable persistence failures. **None observed**
  — `test_restart_outage_recovery.py` I1/I2 PASS; case/events
  byte-identical after backend restart; DB-backed session survives.
- Unauthorized mutations. **None observed** —
  `test_rbac_boundary_sweep.py` G2-G6 PASS (viewer rejected on all
  four mutation routes with zero rows + zero events).
- Broken CSRF/Origin enforcement. **None observed** —
  `test_csrf_origin_invariants.py` H4/H5/H7 PASS (rotation replay
  rejected; authenticated cross-origin write rejected; rejected
  writes have no side effects).
- Synthetic provenance misrepresentation. **None observed** —
  `test_synthetic_boundary_sweep.py` K5/K6 PASS (provenance fields
  absent from mutation schemas; no GET endpoint — parameterized or
  not — leaks synthetic record payload when the source is disabled).
- Frozen artifact integrity failure. **None observed** — 28/28 match.
- Wrong/missing migration readiness. **None observed** —
  `test_db_readiness.py` J1-J8 PASS.
- Repeatable supported-platform startup failure. **None observed on
  Linux** — the Windows 11 trust-auth limitation is a documented
  harness limitation, not a startup failure.
- Mandatory CI failures. **NOT RUN** — branch not pushed; not a
  failure.
- Incorrect audit attribution or event history. **None observed** —
  `test_event_attribution_and_routes.py` D1 PASS (every event's
  actor_ref is the principal's UUID, including spoofed body fields).
- Severe investigation UI integrity defect. **None observed** — E2E
  19/19 PASS, including desktop-layout assertions at 1024/1280/1366/1440.
- Failure to verify a required mandatory gate. **Three gates NOT
  RUN** (RC-02, RC-03, RC-11) — but these are environmental, not
  application defects, and the contract §25 explicitly permits
  continuing safe work when environment capabilities are missing.

No NO-GO trigger applies.

---

## 6. Bounded next use

The contract §17 distinguishes a GO for PEIARS as an internally
controlled scientific investigation workbench from broader claims.
This CONDITIONAL GO explicitly does NOT imply:

- Production security certification.
- Formal external audit.
- Real-world fraud detection accuracy.
- Validation of ULB/MPLADS/PMGSY models inside the application.
- Authorization to ingest sensitive production data.
- Unrestricted public deployment.

The bounded next use is: controlled synthetic demonstration of the
investigation workflow (login → source selection → case creation →
note/transition/decision → reload → persistence) and development of
a read-only scientific adapter against the documented API contract.

---

## 7. Scientific and operational limitations (disclosed)

| Limitation | Disclosure |
|---|---|
| Synthetic demonstration data only | The application's case workflow uses synthetic demonstration records (explicitly labelled `SYNTHETIC DEMONSTRATION RECORD — NOT A RESEARCH FINDING`). The frozen research artifacts (ULB benchmark, MPLADS, PMGSY-III) are NOT integrated as application datasets. |
| No live ML execution | The application does NOT execute Isolation Forest, LOF, PCA, or any anomaly-detection model. Anomaly flags visible in the UI are part of the synthetic demonstration fixtures, not computed at runtime. |
| No public-data ingestion | The application does NOT ingest real ULB/MPLADS/PMGSY data. The source registry is empty when `demonstration_sources=false`. |
| Anomaly is not proof of fraud | The interface does NOT assert that an anomaly detection score proves corruption or fraud. `test_no_confirmed_fraud_status` guards the status vocabulary. |
| Desktop-only | The interface targets desktop widths ≥ 1024 CSS px. The DesktopGate component renders a gate at < 1024 CSS px. No mobile layout is provided. |
| Single-tenant | The application is a single-tenant investigation workbench. Multi-tenant isolation is not implemented. |
| Session cookie security | Production requires `PEIARS_SESSION_COOKIE_SECURE=true`; the Compose stack uses `false` for HTTP loopback development only. |
| Compose-level nginx proxy | Backend-level `$http_host` semantics verified in PR-06B; Compose-level proxy behavior is part of RC-03 (NOT RUN in this delivery). |

---

## 8. Production code change delta

**Zero production code changes.** PR-07B introduces:

- No backend application code changes.
- No frontend application code changes.
- No database migrations.
- No API contract changes (`openapi:check` no drift;
  `contracts.gen.ts` unchanged).
- No frozen research artifacts modified (28/28 match).

The delivery is documentation (9 markdown files under
`docs/acceptance/`) plus one acceptance automation script
(`ci/pr07b_acceptance_smoke.py`) plus one new E2E test (#19, RC-05
integrated workflow, added to the existing
`frontend/playwright/e2e.spec.ts` — a test, not application code).

---

## 9. Final assessment

The PEIARS stack at commit `351aded` is verified as an integrated,
reproducible, security-conscious scientific investigation workbench
for the executable acceptance sub-gates. The three NOT RUN sub-gates
(Windows 11, Docker Compose, GitHub-hosted CI) are environmental
limitations of the coding AI's Linux-only sandbox, NOT application
defects. The two PARTIAL sub-gates (RC-01 clean-checkout, RC-06
two-browser operator workflow) are evidence-scope limitations — the
executed evidence is sufficient for a bounded next use but does not
constitute full verification of those gates' scopes.

The maintainer's execution of the three NOT RUN sub-gates and closure
of the two PARTIAL evidence gaps are the conditions for the
CONDITIONAL GO → GO transition.

**Decision: CONDITIONAL GO.**

**Next steps for the maintainer:**
1. Execute `PR07B_WINDOWS_RUNBOOK.md` on Windows 11 (RC-02); record
   results.
2. Execute `PR07B_COMPOSE_RUNBOOK.md` on a Docker-equipped
   environment (RC-03); record results. Use the shell-specific
   credential generation sections.
3. Push `pr-07b-rc-verification` to the remote; let the five GHA
   jobs run (RC-11); record the new run ID and per-job results.
4. Execute the acceptance suite on a pristine machine (RC-01 PARTIAL
   closure); record the clean-checkout reproduction result.
5. Either add a focused two-browser Playwright test for RC-06 or
   document the evidence gap as an accepted limitation for the
   bounded next use.
6. Update `PR07B_EVIDENCE_REGISTER.md` and `PR07B_TEST_MATRIX.md`
   with all new results.
7. If the NOT RUN sub-gates PASS (with the documented Windows 11
   harness-limitation exception) and the PARTIAL sub-gates are
   closed, promote the decision to **GO**.

**STOP. No PR-08 work started.**

**STOP. Do not begin PR-08.**
