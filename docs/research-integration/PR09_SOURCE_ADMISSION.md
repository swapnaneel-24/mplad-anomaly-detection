# PR-09 Source Admission — Canonical Ten-Run IF/LOF Benchmark

**Branch:** `pr-09-canonical-benchmark`
**Baseline commit:** `0a23577dc52839ff2ea54cdc3fcbc32e35523fd3`
**Date:** 2026-11-14
**Status:** mandatory pre-implementation gate (section 2 of the PR-09 brief)

---

## 1. Decision

**PARTIALLY ADMITTED.**

| Capability | Decision | Basis |
|---|---|---|
| Configuration catalog (ten runs, algorithm/parameter identity, dataset scope, sample/threshold context) | **ADMITTED** | Frozen Git-tracked sources, verified against `ci/frozen_research_manifest.json` with the frozen-checker-compatible identity rule; run↔parameter mapping corroborated by two independent verified sources. |
| Saved per-run Phase 4 metrics (authoritative `phase4_metrics.csv`) | **PARTIALLY ADMITTED (schema admitted; payload availability conditional)** | The exact schema, identity and checksums are established from the Git-tracked commit manifest, provenance record and DVC pointer. The CSV payload itself is DVC-backed and **absent** in this clean checkout, so runtime serving is conditional on the payload being present and matching. |
| Canonical row-level lookup by `row_id` (`phase4_evaluation_dataset.csv`) | **PARTIALLY ADMITTED (schema admitted; payload availability conditional)** | Same as above: long-form schema `[run_id, row_id, Class, native_score, anomaly_score, flag]` is documented and checksum-pinned; payload is DVC-backed and absent here. |
| Phase 3 metrics (`phase3_evaluation_metrics.csv`) | **NOT ADMITTED for this PR** | Phase 3 evaluation predates the label-based Phase 4 layer; the PR-09 scope names the Phase 4 reproduction artifacts as authoritative. Not consumed. |
| Historical full-data companion (`FULL_phase4_*`) | **NOT ADMITTED for this PR** | Different evaluation population (284,807-row full-data novelty mode), explicitly required to be kept separate from the canonical 30k benchmark (FR-19 spirit; SRS §FR-13 scope). |
| `phase4_validation_metrics_CORRECTED.csv` | **NOT ADMITTED** | Historical validation variant under `phase 4/` root (not the `reproduction/` canonical set); superseded by the reproduction artifacts per the Phase 4 contract. |
| Pickle payloads (`phase3_canonical_predictions.pkl`, raw predictions) | **BLOCKED** | Deserializing research pickles inside the FastAPI request process is prohibited by the PR-09 protected-file boundary (arbitrary-code risk). No CSV-insufficient capability requires them. |

The two **PARTIALLY ADMITTED** capabilities are implemented as Layer B
(DVC-optional): fully functional code paths, fail-closed verification, and
deterministic synthetic-fixture tests — but at runtime they report
`artifact_missing` until the DVC payloads are pulled on an authorized
machine. This is exactly the required failure-matrix behaviour
("Verified Git metadata, DVC payload absent → catalog available; dependent
results unavailable").

---

## 2. Evidence examined

All digests below were recomputed in this environment from the actual bytes on disk.

### 2.1 Git-tracked (present in clean checkout)

| File | Git status | Integrity anchor |
|---|---|---|
| `src/mplad/stream_a/phase3.py` | tracked, frozen | `ci/frozen_research_manifest.json` SHA-256 `4ce2d229ff588915…` (verified by `python ci/check_frozen_integrity.py` → 28/28 match) |
| `src/mplad/stream_a/phase4.py` | tracked, frozen | manifest SHA-256 `fcae730cfe15edb1…` (28/28 match) |
| `src/mplad/common/config.py` | tracked, frozen | manifest SHA-256 `3e61e4052cdc1fec…` (28/28 match) |
| `results/stream a/phase 4/reproduction/phase4_run_metadata.json` | tracked | SHA-256 (CRLF form) `b17f40635e73cbc11932447a9616bc9288f9bfbbc50103e2441b8d3aeb736ac1` — matches `phase4_commit_manifest.json` |
| `results/stream a/phase 4/reproduction/phase4_commit_manifest.json` | tracked | self-consistent (its own artifacts section pins the three reproduction outputs) |

### 2.2 DVC-backed (payloads ABSENT in this environment; `.dvc` pointers tracked)

| File | `.dvc` md5 | `.dvc` size | Cross-anchor |
|---|---|---|---|
| `results/stream a/phase 4/reproduction/phase4_metrics.csv` | `2fb961b52603643dab21850bf6d950f9` | 2,397 | `phase4_commit_manifest.json` SHA-256 `6535001ce38766d7e52fef84253a7d95e6335b6183fd34f6ead12210eec99acd`, size 2,397 |
| `results/stream a/phase 4/reproduction/phase4_evaluation_dataset.csv` | `0ba7aece01f588daca3034587e4cbcf7` | 12,352,469 | commit-manifest SHA-256 `affbf02c63da594d1fdb2c66d07121f39221f7e24082eed4770b59d4598bb048`, size 12,352,469 |
| `results/stream a/phase 3/phase3_run_metadata.csv` | `c4bcb2a86e13419ed83f9fd6af46c083` | 795 | provenance record in `phase4_run_metadata.json` records input SHA-256 `94f278680b838203f3acc5dd03e9126bb3613cc4dfb8d7238f015e5cb9364bbd` (LF form), size 795 |
| `results/stream a/phase 3/phase3_evaluation_metrics.csv` | `f3048878bdb526a5be1563189f14722d` | 6,305 | (not consumed by PR-09) |
| `results/stream a/phase 4/FULL_phase4_metrics.csv` | `0ca3335c46795678f7eb3e7ca2d309bb` | 640 | (not consumed — full-data companion) |
| `results/stream a/phase 4/FULL_phase4_evaluation_dataset.csv` | `fba782b9934911800c925c41d0e0a439` | 63,843,721 | (not consumed — full-data companion) |
| `results/stream a/phase 4/phase4_validation_metrics_CORRECTED.csv` | `e56d6d8462f27bc3a47e88efe9098436` | 1,212 | (not consumed — historical variant) |
| `results/stream a/phase 3/phase3_canonical_predictions.pkl` | (pointer exists) | — | **BLOCKED**: pickle deserialization prohibited in the request process |

### 2.3 Line-ending identity rule (critical finding)

The Phase 4 artifacts were produced on Windows (CRLF); the repository stores
them with LF in the Git index (no `.gitattributes`, `i/lf w/lf` per
`git ls-files --eol`). Direct hashing of the on-disk LF bytes does **not**
reproduce the commit-manifest SHA-256. Recomputation proved:

- `phase4_run_metadata.json` on disk (LF, 3,123 bytes) hashes to `d55440a5…`
- The same bytes with LF→CRLF reconstruction (3,199 bytes) hash to
  `b17f40635e73cbc11932447a9616bc9288f9bfbbc50103e2441b8d3aeb736ac1` —
  **exactly** the recorded manifest digest and size.

Therefore the adapter verifies Git-tracked Phase 4 metadata with an
**LF→CRLF reconstructive digest** rule (the inverse of the frozen checker's
CRLF→LF rule), and documents it as `canonicalization:
"windows-commit-manifest-compatible"`. For DVC-backed payloads the pointer
MD5 is compared against both the raw bytes and (for text payloads) the
CRLF-reconstructed bytes, because the payload's on-disk ending depends on
how DVC materialized it; a size check accompanies both. A payload matching
neither form is rejected (`integrity_failed`).

---

## 3. Canonical run identity (ten runs)

Authoritative parameter source: `src/mplad/common/config.py`
(`ISOLATION_FOREST_CONFIGS`, `LOF_CONFIGS`, frozen, manifest-verified) —
the same file the frozen `phase3.py` consumed when the runs were executed.

Run↔config mapping: `PHASE3_CANONICAL_RUN_IDS` is constructed positionally
(`IF_{i:03d}` over the IF grid, then `LOF_{i:03d}` over the LOF grid). This
positional mapping is independently corroborated by the Phase 3 run-metadata
CSV (DVC pointer `c4bcb2a8…`; a byte-identical copy was verified in this
environment against both the pointer MD5 and the input SHA-256 recorded in
`phase4_run_metadata.json`), which lists the same ten `run_id`s in the same
order with the same per-run parameters, plus per-run `runtime_seconds` and
`flagged_count` (300 each — the bottom-1% rule on 30,000 rows).

| run_id | algorithm | parameters (verbatim from frozen config) | corroboration in run-metadata CSV |
|---|---|---|---|
| IF_001 | IsolationForest | `n_estimators=100, max_samples=256, random_state=42` | model=IsolationForest, 100.0, 256.0, 42 |
| IF_002 | IsolationForest | `n_estimators=200, max_samples=256, random_state=42` | 200.0, 256.0, 42 |
| IF_003 | IsolationForest | `n_estimators=100, max_samples=0.05, random_state=42` | 100.0, 0.05, 42 |
| IF_004 | IsolationForest | `n_estimators=100, max_samples=256, random_state=43` | 100.0, 256.0, 43 |
| IF_005 | IsolationForest | `n_estimators=100, max_samples=256, random_state=44` | 100.0, 256.0, 44 |
| LOF_001 | LOF | `n_neighbors=5, metric=euclidean` | LOF, 5.0, euclidean |
| LOF_002 | LOF | `n_neighbors=15, metric=euclidean` | LOF, 15.0, euclidean |
| LOF_003 | LOF | `n_neighbors=30, metric=euclidean` | LOF, 30.0, euclidean |
| LOF_004 | LOF | `n_neighbors=50, metric=euclidean` | LOF, 50.0, euclidean |
| LOF_005 | LOF | `n_neighbors=30, metric=manhattan` | LOF, 30.0, manhattan |

Fixed settings (frozen config, documented but not part of the run grid):
IF `n_jobs=1`; LOF `algorithm=ball_tree, leaf_size=40, n_jobs=1`. The
catalog reports them as fixed pipeline settings with their source, and marks
`runtime_seconds`/`flagged_count` as run-metadata values.

No parameter is derived from scikit-learn defaults: every displayed value
comes from the frozen config module or the run-metadata CSV.

---

## 4. Dataset scope and experiment context (frozen, from verified metadata)

From `phase4_run_metadata.json` (Git-tracked, manifest-verified):

- Benchmark domain: ULB credit-card transactions (Stream A).
- Canonical sample: **30,000 rows**, drawn with seed 42 (`SAMPLE_SEED_DEFAULT`).
- Sample fraud labels: **47** (`fraud_prevalence` 0.0015666666666666667).
- Full registry context: 284,807 observations, 492 positive labels (distinct
  population — reported as context only, never mixed with sample metrics).
- Threshold rule: bottom 1% of native scores (`THRESHOLD_PERCENTILE = 1.0`),
  i.e. 300 flags per run; flags are **saved Phase 3 flags**, never recomputed.
- Score orientation: `native_score` lower = more anomalous;
  `anomaly_score = -native_score`, higher = more anomalous; ranking metrics
  (AP, ROC-AUC) use `anomaly_score`; threshold metrics use saved flags.
- Evaluation layer: label-based (Phase 4), `models_fitted = 0`.
- Run mode: `execute`; environment recorded (Python 3.13.13, numpy 2.4.6,
  pandas 3.0.3, scikit-learn 1.9.0) — reported as recorded environment
  metadata, not re-executed.

---

## 5. Admitted metrics schema (`phase4_metrics.csv`)

One row per run, in Phase 3 metadata order; 10 rows. Columns (from the
frozen `phase4.py` `METRICS_TABLE_COLUMNS` and `docs/phase4_contract.md` §6.2):

`run_id, model, n_estimators, max_samples, random_state, n_neighbors,
metric, runtime_seconds, threshold_rule, average_precision, roc_auc,
precision_at_1pct, recall_at_1pct, f1_at_1pct, tn, fp, fn, tp, sample_size,
fraud_count, fraud_prevalence, flagged_count, flagged_proportion`

Denominator semantics (must be shown with the metrics):

- `average_precision`, `roc_auc`: computed on the 30,000-row sample against
  ground-truth `Class`, using `anomaly_score` (higher = more anomalous).
- `precision_at_1pct`, `recall_at_1pct`, `f1_at_1pct`, `tn/fp/fn/tp`:
  computed from the **saved Phase 3 flags** (bottom-1% rule, 300 flags) —
  never recomputed or re-thresholded.
- `sample_size` = 30,000; `fraud_count` = 47 (sample);
  `flagged_count` = 300 (saved flags); `fraud_prevalence` and
  `flagged_proportion` are the corresponding ratios.

No metric value is hardcoded in the adapter: values are read from the
admitted CSV payload only after checksum verification.

---

## 6. Admitted row-level schema (`phase4_evaluation_dataset.csv`)

Long-form, one row per `(run_id, row_id)`; 10 × 30,000 = **300,000 rows** on
the canonical experiment. Columns (frozen `EVALUATION_DATASET_COLUMNS`):

| Column | Meaning | Notes |
|---|---|---|
| `run_id` | one of the ten canonical runs | |
| `row_id` | Phase 2 stable ULB identifier (integer) | join key; unique within a run |
| `Class` | ground-truth label (0/1) | evaluation label, joined on `row_id`; distinct from the detector flag |
| `native_score` | Phase 3 native estimator score | lower = more anomalous |
| `anomaly_score` | `-native_score` | higher = more anomalous; saved column, not computed by the API |
| `flag` | saved Phase 3 bottom-1% flag (0/1) | saved canonical flag; the API never re-derives it |

Lookup contract: resolve by exact saved `row_id` **within a selected run**;
never by physical row order. Duplicate `row_id` within a run, or a missing
required field (score/flag/label), fails closed for the record capability
(`integrity_failed`). Missing labels are not converted to negative class —
they are rejected. The API performs no ranking, top-k selection or new
thresholding; it returns the saved row exactly as admitted.

---

## 7. Identity chain summary

```
frozen config.py  ──(positional grid)──▶  ten run_ids + parameters
       │                                            │
       │ (corroborates)                             │ (consumed by)
       ▼                                            ▼
phase3_run_metadata.csv (DVC md5 c4bcb2a8…)    phase4_run_metadata.json (Git, SHA b17f4063…)
                                                     │ records input/output digests
                                                     ▼
                                       phase4_commit_manifest.json (Git)
                                        ├─ phase4_metrics.csv         sha256 6535001c…, 2,397 B
                                        └─ phase4_evaluation_dataset.csv sha256 affbf02c…, 12,352,469 B
                                                     │ digests agree with
                                                     ▼
                                       .dvc pointers (Git): md5 2fb961b5… / 0ba7aece…, sizes agree
```

Every arrow above was recomputed in this environment. The Git side of the
chain is fully verifiable in a clean checkout; the payload side is
verifiable wherever the DVC objects are present.

---

## 8. Availability in this execution environment

- Clean Git checkout (this sandbox): all Git-tracked metadata present and
  verified; **all DVC payloads absent**. Catalog routes serve fully;
  metrics/row routes return sanitized `503 SERVICE_NOT_READY` with
  `reason: artifact_missing`.
- `dvc pull` was NOT run and no B2 credentials, tokens or secrets were
  requested or used (protected boundary, ADR-008: data-heavy validation
  belongs to a protected, manually dispatched pipeline).
- No pickle was deserialized; no frozen file was modified, regenerated or
  moved. `python ci/check_frozen_integrity.py` still reports **28/28 match**.

## 9. Consequences for PR-09 implementation

1. Layer A (catalog) is implemented unconditionally: ten runs, parameters,
   provenance, dataset scope, per-capability availability — all from
   Git-verified sources.
2. Layer B (metrics + row lookup) is implemented fully but conditionally:
   fixed server-side allowlist of the two admitted DVC payloads; pointer
   parsed with a bounded parser; single-output-entry requirement; MD5 +
   size (+ commit-manifest SHA-256 after successful parse) verification;
   schema validation; duplicate/missing-row_id rejection; bounded cache with
   digest re-verification per request (PR-08 policy).
3. The historical FULL_* companion, the corrected-validation variant and
   Phase 3 metrics are neither served nor mixed into the canonical view.
4. On the authorized Windows workstation where the Phase 4 reproduction DVC
   payloads are materialized (`phase4_metrics.csv` and 300,000-row
   `phase4_evaluation_dataset.csv`), both payloads were verified against
   their `.dvc` MD5 pointers and `phase4_commit_manifest.json` SHA-256 digests
   and passed full population/label/flag/score invariant checks; in clean-checkout
   CI environments without DVC payloads, Layer B fails closed with `503 artifact_missing`.
