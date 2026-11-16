# PEIARS — R1 Implementation Status and Decision Ledger

- **Document ID:** `STATUS-PEIARS-R1-001`
- **Status:** Living implementation-status record
- **Current milestone:** M2 — Verified Stream A Research Integration
- **Current implementation branch:** `main` (PR-12 merged at `2f96fdb`; M2 — Verified Stream A research integration COMPLETED)
- **Verified current baseline (`main` HEAD):** `2f96fdb667ca3a92c8df1ac1c521fbcb3363666f` (PR #8 merge commit; includes PR-12 M2 acceptance)
- **Last updated:** 2026-11-15

## 1. Governing documents

This ledger records implementation progress against the following controlling design baselines:

1. `MPLAD_Application_SRS_v0.2.md` — `SRS-PEIARS-001`
2. `PEIARS_Architecture_ADRs_v0.1.md` — `ARC-PEIARS-001`
3. `PEIARS_Implementation_Backlog_v0.1.md` — `PLAN-PEIARS-001`

These foundational documents retain their existing draft/proposed approval statuses. Completed engineering work does not automatically constitute formal instructor approval or convert proposed ADRs into accepted decisions.

This ledger is subordinate to the SRS, ADRs, and implementation backlog. It does not amend their requirements or authorize new features.

## 2. Release and milestone status

| Milestone | Status | Evidence / remaining obligation |
|---|---|---|
| M0 — Governance and sign-off | Operational baseline established; formal sign-off unresolved | Record accepted decisions and outstanding approvals |
| M1 — Walking skeleton | Completed as reported, PR-01 through PR-07 | React/FastAPI/PostgreSQL workflow, fixture-based case journey, auth boundary, Compose and CI |
| M2 — Verified Stream A research integration | **COMPLETED** | PR-08 through PR-12 merged; PR-12 (PR #8) accepted on 2f96fdb. Scope: verified Stream A research integration only — PMGSY modelling, MPLADS modelling and deployment readiness remain out of M2 scope. |
| M3 — PMGSY observatory and review | Not started under this roadmap | Approved source admission, record explorer, real-source case flow and export |
| M4 — R1 deployment and hardening | Not started under this roadmap | AT-01–12, public HTTPS release and security/reproducibility gates |
| M5a/M5b/M5c — R2 enhancements | Deferred | Separate gated and independently versioned experiments |
| M6 — R3 extensions | Deferred | Requires future change control |

## 3. Completed PR-08 integration

- **PR:** GitHub PR #3
- **Branch:** `pr-08-research-readonly`
- **Disposition:** Merged into `main`, as confirmed by the project maintainer.
- **Current post-merge baseline:** `0a23577dc52839ff2ea54cdc3fcbc32e35523fd3`

### Accepted scope

- Read-only serving of the admitted precomputed Phase 6 aggregate reference-value family.
- Trusted frozen-manifest validation and runtime cache-integrity checks.
- Windows-compatible text-line-ending canonicalization consistent with the accepted frozen checker.
- Public `GET` access to approved non-sensitive research aggregates (`FR-03` / `ADR-007`).
- Continued authentication for case writes and private reviewer operations.
- Existing six-workspace application architecture preserved.
- No new modelling, fitting or scoring.
- No changes to frozen Phases 3–6, protected manifests or DVC metadata.

### Reported verification evidence

| Check | Reported result |
|---|---|
| Frozen integrity checker | `28/28` matched |
| Targeted backend research/OpenAPI tests | `39/39` passed |
| Full Windows backend suite | `601/602` passed |
| Windows backend exception | Pre-existing `pgserver --auth=trust` harness incompatibility |
| Frontend typecheck/lint | Passed (`0` errors, `0` warnings) |
| Frontend Vitest | `120/120` passed (`22` files) |
| Frontend production build | Passed |
| Chromium Playwright E2E | `20/20` passed |
| Hosted GitHub Actions on PR #3 | `5/5` checks passed |

The Windows-specific backend failure is documented as a test-harness limitation, not represented as a fully passing local suite. The corresponding real-PostgreSQL/Linux CI coverage passed. These figures are maintainer-reported evidence, not a claim that this ledger independently reran those commands.

### PR-08 scope restriction

PR-08 does not establish completion of `M2-01` through `M2-05`. It does not yet make the complete ten-run benchmark, full Phase 5A/5B evidence, canonical row-level inspector or original objective trace available.

## 4. PR-09 baseline and scientific source inventory

- **Proposed PR title:** Canonical Ten-Run IF/LOF Benchmark Integration
- **Branch:** `pr-10-phase5a-evidence`
- **Starting `main` commit:** `0a23577dc52839ff2ea54cdc3fcbc32e35523fd3`
- **Working-tree status:** No tracked modifications at baseline.
- **Local untracked directories:** `.pgdata/`, `backend/.venv312/` — local development state; excluded from PR scope.
- **Frozen integrity result at baseline:** `28/28` files match (`OK`).

### Git-available research evidence

- `src/mplad/stream_a/phase3.py`
- `src/mplad/stream_a/phase4.py`
- `results/stream a/phase 4/reproduction/phase4_run_metadata.json`
- `results/stream a/phase 4/reproduction/phase4_commit_manifest.json`
- `ci/frozen_research_manifest.json`

These paths form the initial candidate source inventory for verified run configuration and experiment metadata. The exact fields, eligible run IDs and relationships must be inspected before implementation; their presence alone does not establish every requested value.

### DVC-managed research evidence

Candidate metrics:
- `results/stream a/phase 3/phase3_evaluation_metrics.csv.dvc`
- `results/stream a/phase 4/reproduction/phase4_metrics.csv.dvc`
- `results/stream a/phase 4/FULL_phase4_metrics.csv.dvc`
- `results/stream a/phase 4/phase4_validation_metrics_CORRECTED.csv.dvc`

Candidate row-level evidence:
- `results/stream a/phase 3/phase3_canonical_predictions.pkl.dvc`
- `results/stream a/phase 4/reproduction/phase4_evaluation_dataset.csv.dvc`
- `results/stream a/phase 4/FULL_phase4_evaluation_dataset.csv.dvc`

These are candidate sources, not jointly approved canonical inputs. Actual schema, sample identity, run completeness, score orientation, per-record key and source authority must be verified before one source is admitted for each capability. The DVC pointer is Git-tracked, while the payload may be absent from a clean checkout or hosted CI. No requirement permits substituting invented metrics, fixture values or Phase 6 aggregates for unavailable row-level research evidence.

## 5. PR-09 requirement traceability

| Backlog | SRS / architecture | Acceptance target |
|---|---|---|
| `M2-01` — Verified source registry | `FR-02`, `FR-04`, `FR-31/32`; `ADR-003` | Approved source identities, integrity and availability |
| `M2-02` — Canonical IF/LOF benchmark | `FR-13`, `FR-16`; `ADR-004` | `AT-02`, `AT-04` |
| `M2-04` — Evidence failure handling (applicable portion) | `FR-05`, `FR-31`; `NFR-01` | `AT-03`, `AT-10`, for covered artifacts |
| Public research read access | `FR-03`; `ADR-007` | Anonymous approved reads; case writes remain protected |

PR-09 shall not claim completion of the entire M2 milestone.

## 6. Active implementation decisions

- **D-09-01 — Frozen evidence is read-only.** No changes to `src/mplad/`, canonical research outputs, trusted manifests, existing DVC pointers or frozen scientific tests.
- **D-09-02 — Offline computation boundary.** HTTP handlers and frontend code shall not fit IF/LOF, recompute canonical scores, rethreshold flags or regenerate experiments.
- **D-09-03 — Dual evidence-availability states.** Git-verified configuration/metadata may be available when DVC-backed metrics and row-level tables are unavailable. Capability availability must be independently reported.
- **D-09-04 — DVC integrity admission.** Any locally available DVC payload must match the approved Git-tracked DVC pointer and any other applicable trusted manifest. Absent, unverified or mismatched payloads cannot be served as verified. DVC MD5 is a content-integrity check, not an independent authorization or source-licensing approval.
- **D-09-05 — Stable identity.** Row-level results must align by canonical `row_id`, not CSV position, pandas index, file order or accidental column ordering.
- **D-09-06 — No untrusted deserialization.** API requests must not unpickle research artifacts. CSV-based read-only integration is preferred when a fully verified, authoritative equivalent exists. If an indispensable metric exists only in a pickle artifact, a separate trusted offline conversion and publication decision is required.
- **D-09-07 — No synthetic scientific fallback.** Fast fixture tests can use explicitly synthetic data, but production responses must not substitute those fixtures when source artifacts are unavailable.
- **D-09-08 — Public research versus private reviews.** Approved aggregate and appropriately admitted research views may be publicly read. Reviewer-case writes and private notes remain authenticated and role-scoped.
- **D-09-09 — Fail closed, not fail globally.** Missing DVC payloads disable only dependent research capabilities. They must not stop API startup, application readiness or unrelated review-case workflows.
- **D-09-10 — Contract-first integration.** Reuse established `/api/v1` routing, typed API contracts, source registry and research/provenance boundaries. Existing accepted routes must remain compatible.

## 7. PR-09 definition of done

PR-09 is acceptable only when:

- All ten canonical experiment configurations are mapped to genuine approved, verified source fields.
- Metrics are exposed only when their independently validated DVC-backed source is available.
- Row-level lookup uses verified canonical `row_id` with exact dataset/run alignment.
- Higher-is-more-anomalous scores, native score definitions and saved top-1% flags are described accurately.
- Missing DVC payloads produce useful unavailable states and never fabricated findings.
- Modified payloads or manifests fail closed.
- Unrelated API and case functionality continues operating.
- Public read permissions and private case permissions remain separate.
- OpenAPI/types/frontend integration and negative tests pass.
- Frozen research integrity remains `28/28`.
- Windows and hosted CI evidence is reported with exact commands and honest pass/fail/skip outcomes.
- The changed-file inventory, rollback plan, security check and actual Git commit are recorded.
- Remaining `M2-03`/`04`/`05` work is left explicitly open.

## 8. Remaining R1 sequence

| Proposed PR | Scope | Backlog |
|---|---|---|
| PR-10 | Phase 5A uncertainty, comparison and review policies | `M2-03` |
| PR-11 | Phase 5B gallery, methodology and original-objective trace | `M2-03`/`05` |
| PR-12 | M2 fault injection, cross-artifact validation and acceptance | `M2-04`; `AT-02`/`03`/`04`/`10` |
| PR-13 through PR-16 | PMGSY admission, record explorer, case workflow, export | `M3-01` through `M3-04` |
| PR-17 through PR-19 | Security, deployment and R1 acceptance | `M4-01` through `M4-03` |

These PR numbers are implementation subdivisions proposed under the foundational backlog, not amendments to its milestone scope.

## 9. Outstanding decisions and risks

- Formal SRS/ADR/M0 sign-off has not been evidenced by this ledger.
- Exact source and redistribution eligibility for public row-level research display requires source-admission verification.
- Canonical Phase 4 metrics and row-level file schemas remain to be inspected.
- DVC payload availability differs between trusted local environments and normal hosted CI.
- Independently verified row-level CSV availability may be insufficient; no pickle-based API shortcut is approved.
- The Windows-specific `pgserver` harness exception was **resolved in PR-10** — the SCRAM fixture was corrected to use `host` (TCP/IPv4+IPv6) scram-sha-256 rules; the earlier `accepted Windows harness exception` classification was incorrect.
- M3 source admission and M4 public release decisions remain separate and unresolved.

## 10. Update protocol

After each PR:

1. Record PR number, title, branch, baseline and resulting merge commit.
2. List the exact backlog/SRS/ADR/acceptance mappings.
3. Record tests actually executed, environment and outcomes.
4. Record protected-file integrity and source admission.
5. Identify unresolved limitations, accepted deviations and next milestone.
6. Mark the PR accepted only after maintainer review and required checks.

Next scheduled work: M2 is COMPLETED (verified Stream A research integration, PR-12 merge 2f96fdb). M3 (PMGSY observatory) not authorized. D0 (accelerated Docker validation) authorized separately. D1 (public deployment preview) planned subject to deployment safety. M4 (production deployment) not completed.

---
## PR-10 — Phase 5A Uncertainty, Agreement, and Review-Policy Evidence

**GitHub PR:** #5
**Status:** MERGED — Accepted
**Source branch:** `pr-10-phase5a-evidence` (deleted after merge)
**Verified pre-merge head:** `8724d86287c46f09077fde6a26e65d10c5feace0`
**Main merge commit:** `e57cc15239e2f590d9aa3ca6bc2bab7ca1310dd3`
**Merge strategy:** Merge commit (`gh pr merge 5 --merge --delete-branch`)
**Milestone:** M2 — Verified Stream A Research Integration
**Backlog mapping:** M2-03, with applicable M2-04 provenance and failure-state protections
**Requirements:** FR-14, FR-17, FR-18, FR-31, FR-32; AT-02 and applicable AT-03/AT-10

### Accepted implementation

- Integrated read-only, manifest-backed Phase 5A research evidence.
- Exposed approved bootstrap uncertainty, agreement and review-policy evidence through the existing FastAPI/React architecture.
- Preserved independent DVC capability availability and fail-closed integrity behavior.
- Verified Phase 5 metadata and DVC payload identities against approved trust anchors.
- Preserved the distinction between saved scientific evidence and unsupported runtime-derived metrics.
- Maintained public read-only research access and protected reviewer-case operations.
- Protected existing Phase 3–6 science and DVC artifacts.

### Verification evidence

**Maintainer-reported Windows 11 verification:**

- Backend: 704/704 passed.
- Frontend Vitest: 134/134 passed.
- Chromium Playwright: 21/21 passed.
- Typecheck, lint, OpenAPI consistency and production build: passed.
- Real materialized Phase 5A DVC verification: passed.
- Clean-checkout unavailable-artifact verification: passed.

**Hosted GitHub Actions:**

All five required checks passed on commit `8724d86287c46f09077fde6a26e65d10c5feace0`:

1. Backend tests — Python 3.12 with PostgreSQL.
2. Browser E2E — Chromium and real backend.
3. Container build and Compose smoke.
4. Frontend — Node 22, typecheck, lint, Vitest, build, OpenAPI.
5. Frozen research integrity — SHA-256.

**Post-merge verification:**

- `main` HEAD: `e57cc15239e2f590d9aa3ca6bc2bab7ca1310dd3`.
- Working tree: clean.
- Frozen integrity: 28/28 matching.
- No unauthorized modification to protected scientific files, manifests or DVC pointers.

**Resolved issue:** The earlier PostgreSQL SCRAM fixture failure was corrected in PR-10. It is no longer classified as an accepted Windows harness exception.

**Deferred non-blocking issue:** 812 reported dependency/deprecation warnings remain for a separately scoped maintenance task.

### Scope boundary

PR-10 does not complete M2 or R1. Phase 5B figure publication, methodology, objective traceability and full M2 acceptance remain outstanding.

---

## PR-11 — Phase 5B Figure Gallery, Methodology, and Original Objective Traceability

**Status:** MERGED — Accepted
**GitHub PR:** #6
**Final reviewed head:** `9990a71cb12ad073fc9ff299d4f391998dbfc14f`
**Merge commit:** `8ed0669af2b07a2c8aa45d3d5aa174104b017335`
**Merged:** 2026-11-15T13:49:48Z
**Merge strategy:** Merge commit; reviewed implementation history preserved.

**Accepted scope:** Eight canonical Phase 5B figures, verified catalog and gated PNG delivery, source-backed methodology, source-native objectives (a)/(b)/(c), RQ1–RQ6 traceability, and historical-companion separation.

**Acceptance evidence:** All five required GitHub Actions checks passed on the final reviewed head. Windows verification reported 50/50 Phase 5B tests, 56/56 Phase 5A/OpenAPI regression tests, and 9/9 real-DVC figure/catalog integrity checks. Earlier full backend regression reported 750 passing tests; final hosted backend CI passed. Frontend verification included 134 Vitest tests, 21 Playwright tests, typecheck, lint, OpenAPI consistency, and build. Post-merge frozen integrity: 28/28 files matched.

**Review findings:** Catalog CSV DVC-pointer verification (R1) and runtime traceability verification-status accuracy (R2) were resolved in commit `9990a71`.

**Retained boundaries:** No scientific artifacts were regenerated or modified. Phase 5B public PNG binary delivery remains disabled by default pending licensing and publication authorization. The historical 284,807-record LOF Novelty Mode companion remains distinct from the canonical 30,000-record benchmark.

**Milestone:** M2 IN PROGRESS. PR-12 remains the integrated scientific acceptance and traceability gate.

**Next scheduled work:** PR-12 — M2 integrated scientific acceptance and traceability.

## PR-12 — M2 Integrated Scientific Acceptance and Traceability

**Status:** MERGED — Accepted
**GitHub PR:** #8
**Final reviewed head:** `b06abfc8ef704d3bbe2c6702f56c9784cc3d96d2`
**Merge commit:** `2f96fdb667ca3a92c8df1ac1c521fbcb3363666f`
**Merged:** 2026-11-16T04:01:07Z
**Merge strategy:** Merge commit; reviewed implementation history preserved.
**Hosted CI on final reviewed head:** 5/5 successful (run 43800723014)

**Accepted scope:** Integration acceptance gate for M2. Consolidates the accepted PR-08 through PR-11 evidence into an explicit 10-row acceptance matrix; closes frontend Phase 5B coverage (AG-2); documents the PR-08 frozen-source vs DVC-backed provenance distinction; preserves the historical 284,807-row LOF companion distinction; no new research capability added.

**Acceptance evidence:** All five required GitHub Actions jobs passed on the final reviewed head (Backend 1m52s, Browser E2E 1m18s, Container 1m17s, Frontend 44s, Frozen 11s). Windows verification: 754/754 backend tests with materialized DVC payloads (886 warnings, same three classes as PR-08 through PR-11); 141/141 frontend Vitest tests (25 files; +7 new F5B scenarios); typecheck, lint, openapi:check and build all pass; real-DVC 9/9 (8 PNGs + catalog CSV SHA-256 vs figure manifest). Playwright NOT RUN locally on Windows (POSIX env-var prefix in playwright.config.ts unsupported by Windows cmd; bash.exe is WSL launcher stub); hosted Ubuntu Playwright PASS confirms non-blocking. Post-merge frozen integrity: 28/28 files matched.

**Review findings resolved:** AG-1 (PR-08 reason-code specificity) closed as NOT APPLICABLE — the existing PR-08 contract emits `{"dependency": "research-source"}` without `details.reason`; preserving that distinction is required. AG-2 (frontend Phase 5B integration coverage) closed by `phase5b-workspace.test.tsx` (7 scenarios F5B-01 through F5B-07). AG-3 (integrated cross-surface acceptance) closed by `PR12_TEST_MATRIX.md` — 1 10-row matrix with composed-evidence framing. F5B-07 race condition (originally waited on unconditionally-rendered heading) resolved in `b06abfc8ef704d3bbe2c6702f56c9784cc3d96d2` by awaiting the ErrorPanel `role="alert"` state before asserting absence of fabricated content.

**Retained boundaries:** No scientific artifacts regenerated or modified. Phase 5B public PNG binary delivery remains disabled by default pending licensing verification. The historical 284,807-record LOF Novelty Mode companion remains distinct from the canonical 30,000-record benchmark. PR-08 failure envelope preserved as-is (no `details.reason`). DVC migration deferred to M4.

**M2 status:** **COMPLETED** — verified Stream A research integration. Explicit qualification: this refers to verified Stream A research integration only, not PMGSY modelling, MPLADS modelling or deployment readiness.

**Next scheduled work:** M3 (PMGSY observatory and review) not authorized. D0 (accelerated Docker validation) authorized separately. D1 (public deployment preview) planned subject to deployment safety. M4 (production deployment) not completed.

---

*End of PR-12 integration acceptance.*