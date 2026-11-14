# PR-08 Test Matrix

**Baseline:** `831c9b4d23349b57d48828157d68fefde5927f02`
**Branch:** `pr-08-research-readonly`

---

## 1. Software tests

| Suite | Command | Result |
|---|---|---|
| Backend pytest | `python -m pytest -q` | **602 passed** (574 baseline + 28 research adapter tests), 72.3 s |
| Frontend typecheck | `npm run typecheck` | PASS |
| Frontend lint | `npm run lint` | PASS |
| Frontend Vitest | `npm run test -- --run` | **120 passed** (115 baseline + 5 research workspace tests), 22.7 s |
| Frontend build | `npm run build` | PASS |
| OpenAPI drift | `npm run openapi:check` | PASS (no drift) |
| Browser E2E | `bash frontend/scripts/run-e2e.sh` | **20 passed** (19 baseline + 1 research workspace test), 35.3 s |
| Frozen integrity | `python ci/check_frozen_integrity.py` | **28/28 match** |

---

## 2. Backend research adapter tests (28 tests)

### Positive cases (14 tests)

| Test | Assertion |
|---|---|
| test_list_sources_returns_one_eligible_source | SC-01: catalog lists exactly one approved source |
| test_get_source_detail_returns_correct_metadata | Source detail includes artifact path, verified digest, experimental context |
| test_artifact_digest_matches_frozen_manifest | SC-07: digest matches frozen integrity manifest |
| test_supporting_artifacts_verified_and_attributed | Issue 4: phase5_analysis.py and config.py verified and attributed |
| test_get_results_returns_all_18_reference_values | SC-03: every precomputed value present; no fabrication |
| test_get_results_includes_interpretation_principles | SC-08: principles state anomaly flag is not proof of fraud |
| test_get_results_includes_exploratory_caveat | Exploratory selection caveat present |
| test_get_results_includes_provenance | SC-01: provenance back to verified frozen artifact |
| test_get_results_includes_limitations | ULB→MPLAD non-transfer limitation present |
| test_results_are_deterministic | SC-10: identical artifacts → identical results |
| test_results_do_not_contain_synthetic_markers | SC-05: no synthetic substitution |
| test_same_byte_snapshot_used_for_parsing_and_provenance | Issue 1: same verified bytes used for parsing and provenance |

### Negative cases (5 tests)

| Test | Assertion |
|---|---|
| test_unknown_source_id_returns_404 | Unknown source → 404 SOURCE_NOT_FOUND |
| test_unknown_source_results_returns_404 | Unknown source results → 404 |
| test_anonymous_request_rejected | Anonymous → 401/403 |
| test_mutation_verbs_not_allowed | POST/PUT/PATCH/DELETE → 404/405 |
| test_no_synthetic_fallback_on_research_failure | SC-05: failure returns error, not synthetic data |

### Integrity verification (4 tests — Issue 1 + Issue 3)

| Test | Assertion |
|---|---|
| test_trusted_sha256_mismatch_returns_503 | Corrupted artifact (wrong digest) → 503, never modified results |
| test_missing_source_returns_503_not_startup_failure | Missing artifact → 503 from API; app started fine |
| test_no_app_wide_startup_failure_when_artifact_missing | Issue 3: app creates successfully even if artifacts missing |
| test_corrupted_malformed_source_returns_503 | Valid Python with wrong SHA-256 → 503 (trusted-digest check catches it) |

### RBAC (2 tests)

| Test | Assertion |
|---|---|
| test_viewer_can_read_research_sources | Viewer role has read access |
| test_research_endpoints_do_not_write_case_state | Reading research results creates no case/event rows |

### OpenAPI (1 test)

| Test | Assertion |
|---|---|
| test_research_routes_in_openapi | 3 GET routes documented; no mutation methods |

### UI hash accuracy (2 tests — Issue 2)

| Test | Assertion |
|---|---|
| test_phase6_displayed_hash_matches_manifest | UI displayed SHA-256 prefix for phase6.py matches frozen manifest |
| test_all_28_displayed_hashes_match_manifest | Every displayed SHA-256 prefix in the ResearchPage matches the frozen manifest |

---

## 3. Frontend research workspace tests (5 Vitest tests)

| Test | Assertion |
|---|---|
| renders the precomputed results table | Table shows sample_size=30000, fraud_label_count=47, spearman=0.3666 |
| displays 'not live predictions' and 'not proof of fraud' | SC-08: cautions visible |
| displays provenance (artifact path and SHA-256) | SC-01: provenance visible |
| displays interpretation principles and exploratory caveat | Principles + caveat visible |
| renders heading when research endpoint fails | Error state handled |

---

## 4. E2E test #20 (real backend integration)

| Test | Assertion |
|---|---|
| PR-08 research workspace displays precomputed results with provenance | Real backend integration: fetches /api/v1/research/sources and /results; verifies sample_size, 30000, fraud_label_count, 47, spearman_if003_lof004, 0.3666; verifies "not live predictions", provenance (src/mplad/stream_a/phase6.py), "Interpretation principles" heading, "anomaly flag is not proof of fraud", "Exploratory analysis"; verifies no horizontal overflow at 1440px |

---

## 5. Scientific correctness tests (SC-01 through SC-10)

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| SC-01 | Provenance completeness | PASS | test_get_results_includes_provenance; test_artifact_digest_matches_frozen_manifest |
| SC-02 | Score semantics | PASS | values served as-is from frozen dict (no inversion/rescaling); adapter does not modify values |
| SC-03 | No fabricated results | PASS | test_get_results_returns_all_18_reference_values (exactly 18, no extras) |
| SC-04 | No unsupported joins | PASS | aggregate-level only; no per-record mapping; test_research_endpoints_do_not_write_case_state |
| SC-05 | Synthetic separation | PASS | test_results_do_not_contain_synthetic_markers; test_no_synthetic_fallback_on_research_failure |
| SC-06 | Model distinction | PASS | model_methods=["IsolationForest", "LOF"]; interpretation principles state no universal superiority |
| SC-07 | Research integrity | PASS | 28/28 frozen match; test_artifact_digest_matches_frozen_manifest |
| SC-08 | Non-accusatory | PASS | "anomaly flag is not proof of fraud" in principles; "not proof of fraud" in UI |
| SC-09 | Evaluation context | PASS | experimental_context includes sample_size, fraud_label_count, run_ids, threshold_rule |
| SC-10 | Deterministic rendering | PASS | test_results_are_deterministic (identical artifacts → identical results) |

---

## 6. Security regression

| Property | Status |
|---|---|
| Session authentication | PASS (unchanged; 574 baseline tests green) |
| Logout/session invalidation | PASS (unchanged) |
| RBAC | PASS (viewer/reviewer/admin all read; no new role) |
| CSRF/Origin | PASS (research endpoints are GET-only; no CSRF needed) |
| Audit event attribution | PASS (research reads create no events) |
| Optimistic concurrency | PASS (unchanged; research has no writes) |
| Case history ordering | PASS (unchanged; research has no case mutations) |
| Stale-response protections | PASS (unchanged; research adapter has no async selection) |
| Database readiness | PASS (research adapter does not require DB; no readiness probe added) |
| PostgreSQL restart recovery | PASS (unchanged; research adapter is stateless) |
| Synthetic-source access gating | PASS (updated sweep includes /research/* endpoints) |
| 19-test E2E baseline | PASS (20/20 — 19 existing + 1 new) |
| Frozen artifact integrity | PASS (28/28) |

---

## 7. NOT RUN

| Gate | Reason |
|---|---|
| Docker/Compose | No Docker daemon in sandbox |
| Windows 11 | Linux-only coding AI |
| GitHub-hosted CI | Branch not pushed |
