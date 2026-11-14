# PR-09 API Data Contract — Canonical Ten-Run IF/LOF Benchmark

**Branch:** `pr-09-canonical-benchmark`
**Scope:** the four GET operations added under `/api/v1/research/benchmark`
(extending the existing PR-08 research API; no new top-level router, no
second verification framework, same error envelope).

---

## 1. Why new operations (existing-route inventory)

The PR-08 surface is keyed by a single Phase 6 aggregate `source_id`
(`/research/sources`, `/research/sources/{source_id}`,
`/research/sources/{source_id}/results`) and serves one frozen results
payload. PR-09 needs resources that cannot be expressed on those routes:

| New operation | Why PR-08 routes cannot cover it |
|---|---|
| `GET /research/benchmark/experiments` | A ten-run catalog keyed by `run_id`, with per-capability availability — not a single-source list. |
| `GET /research/benchmark/experiments/{run_id}` | Per-run parameter configuration, fixed pipeline settings, dataset scope and a three-artifact provenance chain. |
| `GET /research/benchmark/metrics` | A ten-row saved-metrics table with per-metric definitions and denominators — not aggregate reference values. |
| `GET /research/benchmark/experiments/{run_id}/records/{row_id}` | A canonical record lookup keyed by `(run_id, row_id)` — a new resource shape entirely. |

All four are GET-only, read-only, and **publicly readable** (FR-03 /
ADR-007), consistent with the PR-08 research routes.

---

## 2. Error matrix (verified by tests)

| Condition | HTTP | Code | `details.reason` |
|---|---|---|---|
| Verified Git metadata, DVC payload absent (catalog) | 200 | — | `capabilities.*.reason = "artifact_missing"` |
| Verified Git metadata, DVC payload absent (metrics / record) | 503 | `SERVICE_NOT_READY` | `artifact_missing` |
| Verified Git metadata, DVC payload valid | 200 | — | — |
| Payload present, checksum/size mismatch | 503 | `SERVICE_NOT_READY` | `integrity_failed` |
| Pointer absent, malformed, untrusted, multi-entry, unexpected output path | 503 | `SERVICE_NOT_READY` | `integrity_failed` (or `artifact_missing` / `source_not_admitted` when the pointer itself is unreadable) |
| Duplicate or missing required `row_id` / score / flag / label field | 503 | `SERVICE_NOT_READY` | `integrity_failed` |
| Unknown run ID or unknown `(run_id, row_id)` | 404 | `SOURCE_NOT_FOUND` | — |
| Tampered Git-backed metadata (config, run metadata, commit manifest) | 503 | `SERVICE_NOT_READY` | `integrity_failed` |
| Payload altered after cache warm-up | 503 | `SERVICE_NOT_READY` | `integrity_failed` |
| Valid payload restored | 200 on next request | — | recovery without restart |
| Unrelated case/readiness endpoints | unaffected | — | independence |

Error responses use the repository's established `ErrorEnvelope`; details
never contain server paths or stack traces. The 404 path never performs a
filesystem lookup — `run_id` is matched against the fixed
`CANONICAL_RUN_IDS` allowlist; `row_id` against the parsed, verified CSV
content.

---

## 3. Response shapes (summary)

### 3.1 `GET /api/v1/research/benchmark/experiments` → `BenchmarkCatalogResponse`

- `source_id: "canonical-if-lof-benchmark"`, `dataset_id`
- `experiments`: 10 × `BenchmarkExperimentSummary` — `run_id`
  (IF_001..IF_005, LOF_001..LOF_005), `algorithm`
  (`IsolationForest`/`LOF`), exact `parameters` (frozen config values),
  `parameter_source` (path + SHA-256 + canonicalization
  `frozen-checker-compatible` + no-defaults note), `model_status`
  (`fitted_offline_frozen`), `metrics_available`,
  `row_lookup_available`
- `capabilities`: per-layer availability `{metrics, row_level}` ×
  `{available, reason, detail}` — never a global 503 because metrics are
  absent (FR-05 / AT-10)
- `limitations`: frozen scientific limitations

### 3.2 `GET /research/benchmark/experiments/{run_id}` → `BenchmarkExperimentDetail`

Adds `fixed_pipeline_settings` (IF `n_jobs=1`; LOF `ball_tree`,
`leaf_size=40`, `n_jobs=1`), `dataset_scope`
(`sample`: 30,000 / 47 / prevalence; `registry_summary`: 284,807 / 492 /
matched 30,000; `threshold_rule` "Bottom 1.0% of scores";
`threshold_percentile` 1.0; `sample_seed` 42; `score_orientation`
native-vs-anomaly contract; recorded `environment`; `model_fitting`
models_fitted=0) and the three-artifact `provenance` chain
(`config` — frozen-checker-compatible SHA-256; `run_metadata` and
`commit_manifest` — windows-commit-manifest-compatible SHA-256, i.e. the
LF→CRLF reconstruction matching the Windows-produced manifest digests).

### 3.3 `GET /research/benchmark/metrics` → `BenchmarkMetricsResponse` (Layer B)

Ten `BenchmarkRunMetrics` rows in frozen metadata order, each carrying the
saved `average_precision`, `roc_auc`, `precision_at_1pct`, `recall_at_1pct`,
`f1_at_1pct`, confusion counts (`tn/fp/fn/tp`), population counts
(`sample_size/fraud_count/flagged_count`) and ratios
(`fraud_prevalence/flagged_proportion`), plus `runtime_seconds` and
`threshold_rule` from the saved row. `metric_definitions` travels with the
values so every number carries its denominator semantics (sample vs 300
flagged vs 47 labels). `provenance` records the payload path (repo-relative
only), verified md5 and the verification statement.
`is_precomputed: true`, `is_live_prediction: false` always.

### 3.4 `GET /research/benchmark/experiments/{run_id}/records/{row_id}` → `BenchmarkRecordResponse` (Layer B)

Resolved by the **exact saved `row_id`** within the selected run (never
physical row order). Field groups keep the required distinctions explicit:

- `label.Class` — ground-truth ULB evaluation label with its provenance
  string ("distinct from the detector flag"); a missing label is never
  converted to class 0.
- `scores.native_score` (lower = more anomalous) vs
  `scores.anomaly_score` (saved `-native_score`, higher = more anomalous),
  each with its definition string.
- `flag.value` — saved Phase 3 bottom-1% flag, "never recomputed".

No rank, top-k threshold or prediction is computed by the API.

---

## 4. Integrity and verification contract

**Layer A (Git-verified, always available):**

- `src/mplad/common/config.py` — SHA-256 verified against
  `ci/frozen_research_manifest.json` (frozen-checker-compatible rule:
  CRLF→LF for text). Parameters extracted by AST parsing only (annotated
  assignments and simple assignments; the f-string threshold label is
  reconstructed from the parsed percentile, exactly as in PR-08); the
  module is never executed.
- `phase4_run_metadata.json` / `phase4_commit_manifest.json` — verified
  against the commit manifest's own artifacts section using the
  **windows-commit-manifest-compatible** rule (LF→CRLF reconstruction);
  this reproduces the recorded SHA-256 and byte size exactly (see
  PR09_SOURCE_ADMISSION.md §2.3). JSON parsing only.
- Cross-checks: the config grids must produce exactly the ten canonical
  run IDs, and the run metadata's `run_ids` must agree with the grids;
  disagreement fails closed.

**Layer B (DVC-optional):**

- Resolution exclusively from a fixed server-side
  `_DVC_PAYLOAD_SPECS` allowlist (payload path, pointer path, role);
  `run_id`/`row_id` never influence filesystem paths.
- The `.dvc` pointer is parsed by a bounded parser: exactly one `outs`
  entry, required keys `md5/size/hash/path`, `hash: md5` only, well-formed
  md5, integer size; anything else is `integrity_failed`.
- The pointer's `path` must equal the expected payload filename; the
  payload size must match; the payload MD5 must match either the raw bytes
  or the CRLF-reconstructed form (DVC materialization ending is not
  assumed).
- Schema validation against the frozen Phase 4 contract: metrics columns
  exactly as `METRICS_TABLE_COLUMNS`; evaluation columns exactly as
  `EVALUATION_DATASET_COLUMNS`; ten unique run IDs in the metrics;
  unique `(run_id, row_id)` pairs; no missing score/flag/label values.
- Metrics population cross-check: each row's `sample_size` and
  `fraud_count` must equal the manifest-verified run-metadata values.
- Cache-integrity policy (PR-08 contract): parsed payloads are cached with
  the digests verified at parse time; every request re-reads the pointers
  and payload bytes and re-verifies, so post-cache mutation fails closed
  and restoration recovers without restart.
- No pickle is ever deserialized in the request process; no `dvc` command
  is executed; nothing is downloaded.

---

## 5. Frontend contract

`contracts.ts` mirrors every new schema
(`BenchmarkCatalogResponse`, `BenchmarkExperimentSummary`,
`BenchmarkExperimentDetail`, `DatasetScope`, `BenchmarkRunMetrics`,
`BenchmarkMetricsResponse`, `BenchmarkMetricDefinition`,
`BenchmarkRecordResponse`, `ArtifactProvenance`,
`ParameterSourceProvenance`, capability-status blocks);
`contracts.gen.ts` is regenerated from the committed OpenAPI with
`npm run openapi:check -- --write` (UTF-8 no BOM, LF); the drift check
passes. Endpoint wrappers live in `endpoints.ts`
(`getBenchmarkExperiments`, `getBenchmarkExperiment`,
`getBenchmarkMetrics`, `getBenchmarkRecord`).

---

## 6. Publication decision

All four operations are served to anonymous readers (public read-only,
FR-03 / ADR-007), as with the PR-08 research routes: the served values are
precomputed, non-sensitive scientific aggregates with provenance. No
authentication, authorization or CSRF protection is removed from any case
route. Field-level publication follows the source-admission decision: only
fields backed by the admitted artifacts are served; nothing is inferred,
relabeled or substituted.
