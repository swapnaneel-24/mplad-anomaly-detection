# PEIARS — R1 Implementation Status and Decision Ledger

- **Document ID:** `STATUS-PEIARS-R1-001`
- **Status:** Living implementation-status record
- **Current milestone:** M2 — Verified Stream A Research Integration
- **Current implementation branch:** `pr-09-canonical-benchmark`
- **Verified PR-09 baseline (`main` HEAD):** `0a23577dc52839ff2ea54cdc3fcbc32e35523fd3`
- **Last updated:** 2026-11-14

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
| M2 — Verified research integration | In progress | PR-08 merged; PR-09 implemented & locally verified on `pr-09-canonical-benchmark` (pending PR #4 CI & merge review); PR-10–12 remain |
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
- **Branch:** `pr-09-canonical-benchmark`
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
- The Windows-specific `pgserver` harness exception remains documented.
- M3 source admission and M4 public release decisions remain separate and unresolved.

## 10. Update protocol

After each PR:

1. Record PR number, title, branch, baseline and resulting merge commit.
2. List the exact backlog/SRS/ADR/acceptance mappings.
3. Record tests actually executed, environment and outcomes.
4. Record protected-file integrity and source admission.
5. Identify unresolved limitations, accepted deviations and next milestone.
6. Mark the PR accepted only after maintainer review and required checks.

Next scheduled work: PR-09 source-contract preflight, then bounded implementation if the canonical source identities and schemas pass admission.