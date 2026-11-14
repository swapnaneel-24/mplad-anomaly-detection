# PR-09 Test Matrix — Canonical Ten-Run IF/LOF Benchmark

**Branch:** `pr-09-canonical-benchmark`
**Test date:** 2026-11-14
**Environment:** Linux sandbox (clean Git checkout; DVC payloads absent)

---

## 1. Software tests

| Suite | Command | Result |
|---|---|---|
| Backend pytest (full) | `python -m pytest -q` | **650 passed** (602 baseline + 48 new benchmark-adapter tests), 78.3 s |
| Backend benchmark tests | `python -m pytest tests/test_benchmark_adapter.py -q` | **48 passed**, 10.5 s |
| Frontend typecheck | `npm run typecheck` | PASS |
| Frontend lint | `npm run lint` | PASS |
| Frontend Vitest (full) | `npm run test -- --run` | **128 passed** (120 baseline + 8 new benchmark-workspace tests), 24.2 s |
| Frontend build | `npm run build` | PASS |
| OpenAPI drift | `npm run openapi:check` | PASS (no drift) |
| Browser E2E | `bash frontend/scripts/run-e2e.sh` | **21 passed** (20 baseline + 1 new PR-09 benchmark test), 36.2 s |
| Frozen integrity | `python ci/check_frozen_integrity.py` | **28/28 match** |

---

## 2. Mandatory fixture-only CI scenarios (PR-09 brief §9) → tests

All 18 required scenarios are covered by deterministic tests. DVC payload
fixtures are **synthetic**, generated under pytest `tmp_path`, with
matching synthetic `.dvc` pointers (md5 + size), and are documented as
synthetic in the test module docstring. The real DVC payloads are absent
in this environment and are never touched.

| # | Required scenario | Test(s) |
|---|---|---|
| 1 | Exactly ten source-backed run configurations | `TestBenchmarkCatalog::test_catalog_returns_exactly_ten_runs`, `test_catalog_lists_all_ten_parameter_rows` |
| 2 | Correct run/algorithm/parameter identity mapping | `TestBenchmarkCatalog::test_run_algorithm_parameter_mapping` (+ `test_detail_includes_dataset_scope_and_provenance`) |
| 3 | Unknown run ID rejection (404) | `TestBenchmarkCatalog::test_unknown_run_id_returns_404`, `TestRecordLookup::test_record_lookup_rejects_unknown_run_first`, `TestServiceContract::test_unknown_run_raises_source_not_found`, `test_run_id_regex_boundary` |
| 4 | DVC payload missing while configuration catalog works | `TestPayloadMissing::test_catalog_works_and_metrics_report_artifact_missing`, `TestCacheIntegrity::test_catalog_survives_layer_b_failures`, `TestServiceContract::test_metrics_payload_absent_raises_unavailable` / `test_record_payload_absent_raises_unavailable`, `TestUnrelatedWorkflows::test_health_and_review_workflow_continue` |
| 5 | DVC pointer checksum match / mismatch | match: `TestLayerBVerification::test_admitted_metrics_exact_values_and_denominators`, `test_crlf_payload_form_also_verifies`; mismatch: `test_pointer_checksum_mismatch_fails_closed`, `test_pointer_size_mismatch_fails_closed` |
| 6 | Pointer malformed, missing, unexpected output path | `TestLayerBVerification::test_malformed_pointer_rejected` (8 parametrized forms), `test_missing_pointer_rejected`, `test_unexpected_output_path_rejected`, `test_two_output_entries_rejected` |
| 7 | Valid admitted metrics, exact source values, denominator semantics | `TestLayerBVerification::test_admitted_metrics_exact_values_and_denominators` (exact fixture values asserted; denominators for precision/recall asserted) |
| 8 | Row lookup by actual row_id | `TestRecordLookup::test_row_lookup_by_actual_row_id`, `test_unknown_record_returns_404` |
| 9 | Shuffled row order invariance | `TestRecordLookup::test_shuffled_row_order_invariance` (forward vs reversed CSV; record payload identical) |
| 10 | Duplicate row_id rejection | `TestRecordLookup::test_duplicate_row_id_rejected` |
| 11 | Missing required score/flag/label field, no invented defaults | `TestRecordLookup::test_missing_required_field_no_invented_defaults` (parametrized over Class / native_score / anomaly_score / flag) |
| 12 | Tampered Git-backed metadata rejection | `TestTamperedGitMetadata::test_tampered_run_metadata_rejected`, `test_tampered_config_rejected` |
| 13 | Post-cache mutation / recovery | `TestCacheIntegrity::test_payload_altered_after_warmup_fails_closed_then_recovers`, `test_payload_removed_after_warmup_fails_closed` |
| 14 | Public approved research GET access | `TestAccessControl::test_anonymous_reader_can_read_benchmark` |
| 15 | Authenticated case write + private-history isolation | `TestAccessControl::test_authenticated_case_write_and_private_history_isolation` |
| 16 | No API-triggered modelling, fitting, pickle loading, DVC downloads | `TestNoModellingOrPickle::test_no_pickle_or_sklearn_or_dvc_import_or_download` (guarded `__import__` during live requests), `test_service_source_has_no_pickle_or_dvc_calls` |
| 17 | OpenAPI / TypeScript contract consistency | `TestOpenAPIContract::test_benchmark_operations_present_in_openapi`, `test_committed_openapi_matches_app`, `test_generated_typescript_contracts_contain_benchmark`; plus the regenerated `openapi.json` + `contracts.gen.ts` drift check (PASS) |
| 18 | Unrelated application readiness and review workflows during missing payloads | `TestUnrelatedWorkflows::test_health_and_review_workflow_continue` (health live/ready, case create, PR-08 research routes, benchmark catalog OK + metrics 503) |

Additional coverage beyond the 18 scenarios: CRLF-materialized payload
verification; run-ID regex boundary checks; availability probe never
raising; catalog detail provenance chain; full synthetic-boundary sweep
extension (non-parameterized GETs + parameterized GETs now include the
benchmark routes and pass with `demonstration_sources` disabled).

---

## 3. Frontend Vitest tests (new: `tests/integration/benchmark-workspace.test.tsx`)

| Test | Assertion |
|---|---|
| renders all ten canonical run tabs | ten `role="tab"` elements for IF_001..LOF_005 |
| selects a run and shows frozen configuration with provenance | `IF_001 — IsolationForest`, `n_estimators=100, max_samples=256, random_state=42`, `n_jobs=1`, config path, 30,000-row sample scope, threshold rule, score-direction labelling |
| shows the explicit unavailable state when DVC payloads are absent | unavailable copy for metrics + record lookup; no metric table headers leak (`AP` absent) |
| shows saved metrics with denominators when available | ten synthetic rows render; `300 flagged rows (saved bottom-1% rule)` and `47 fraud-labelled rows in the sample` denominators visible |
| looks up a canonical record by row_id when available | input + `Look up` submit; `Saved record for IF_001 / row_id 205`; label/native/anomaly/flag rows with meaning text |
| keeps the PR-08 Phase 6 aggregate view alongside | `Precomputed Research Results` + `sample_size` still render |
| 1024px narrow viewport without horizontal overflow | `scrollWidth <= innerWidth + 1` after selecting a run |
| keyboard navigation across run tabs | focus + arrow-key reachability + click selection of IF_002 |

All fixtures are SYNTHETIC test doubles (documented as such); canonical
values are pinned by the backend adapter tests, not the UI tests.

---

## 4. E2E (new: test 21, real pgserver + uvicorn backend, no mocks)

`21. PR-09 benchmark workspace shows verified ten-run catalog and
unavailable data states` — logs in, opens Research, asserts the section
heading, four representative run tabs, selects IF_001 (frozen parameters,
config provenance, threshold rule), verifies the two explicit
DVC-unavailable states, and confirms the PR-08 aggregate view is
preserved.

---

## 5. Trusted local data verification (Windows workstation) — NOT RUN

**NOT RUN — DATA UNAVAILABLE.** The real DVC payloads
(`phase4_metrics.csv`, `phase4_evaluation_dataset.csv`) are not present in
this execution environment, and PR-09 forbids `dvc pull` / B2 credentials
here. The following acceptance steps remain for the maintainer on an
authorized Windows workstation where the payloads exist:

- [ ] Validate each payload against its committed `.dvc` pointer (`dvc status` or the adapter's own md5/size check).
- [ ] Verify admitted schema, source version and run completeness (10 runs; 300,000 evaluation rows).
- [ ] Confirm canonical row population/uniqueness and the label count (47 positives) from actual records.
- [ ] Confirm saved top-1% flag cardinality per run (300 per run).
- [ ] Verify representative metric values against the approved saved result files.
- [ ] Inspect several canonical `row_id` records with score/label/flag cross-checks (native = −anomaly; flag ∈ {0,1}).
- [ ] Test tampering/removal on disposable copies only (the adapter tests already simulate this; repeat against real bytes).
- [ ] Record commands, dataset versions, counts, hashes and any blockers in this matrix.

No synthetic test result has been recorded as trusted real-data
validation, and no DVC pointer or frozen manifest was altered to make any
result pass.

---

## 6. Existing regressions

Executed and passed in this environment (2026-11-14, this branch):

- Backend pytest: 650 passed (includes all 602 pre-existing tests).
- Frontend typecheck / lint: PASS. Vitest: 128 passed. Build: PASS.
- OpenAPI drift check: PASS. Frozen integrity: 28/28 match.
- Playwright E2E: 21 passed.

Not run / blocked:

- Windows-local trusted-payload validation (see §5) — blocked by data
  availability in this sandbox.
- Hosted CI run — to be executed on push (the suite is fixture-only and
  works on a clean checkout without DVC/B2 credentials by design).
