# Phase 4 Contract — Stream A: Label-Based Evaluation Layer

**Status:** implemented 2026-11-05 (Stage 2 of the Colab → repository migration).
**Scope:** the Phase 4 *compute layer* only. No notebook, no Phase 5 analysis,
no bootstrapping, no plots, no Phase 6, no Streamlit.

Phase 4 consumes the frozen Phase 3 artifacts **read-only** and evaluates them
against the separately stored ground truth. It never fits, refits, retunes or
constructs a detector; the only scikit-learn import is `sklearn.metrics`.

---

## 1. Inputs (exact contract)

### 1.1 Phase 3 canonical prediction bundle

`results/stream a/phase 3/phase3_canonical_predictions.pkl`
(default constant `config.PHASE3_PREDICTIONS_PATH`, CLI `--predictions`)

```python
{
  "row_ids": <numpy 1-D int64 array>,          # ONE shared sample sequence (30,000 ids)
  "predictions": {
      "IF_001":  {"scores": <1-D float32, len 30000>,   # NATIVE scores:
                  "flags":   <1-D uint8,  len 30000>},   #   lower = more anomalous
      ...                                              # flags = saved bottom-1% rule
      "LOF_005": {"scores": ..., "flags": ...},
  },
}
```

Validated by `phase4.validate_prediction_bundle`:

- exact top-level keys `{"row_ids", "predictions"}`;
- `row_ids`: 1-D, integer dtype, unique, non-empty (the shared sequence);
- run-ID set **exactly equals** the Phase 3 metadata run IDs (default:
  `config.PHASE3_CANONICAL_RUN_IDS` = IF_001..IF_005, LOF_001..LOF_005);
- per run: exact entry keys `{"scores", "flags"}`;
- `scores`: 1-D floating, length == sample size, all finite (NaN/±inf rejected);
- `flags`: 1-D, length == sample size, binary {0, 1};
- per-run flag count == metadata `flagged_count` (the two Phase 3 artifacts
  must agree; a mismatch is rejected);
- the bundle is never sorted, reordered or mutated.

### 1.2 Phase 3 run metadata

`results/stream a/phase 3/phase3_run_metadata.csv`
(default constant `config.PHASE3_RUN_METADATA_PATH`, CLI `--run-metadata`)

Frozen 10-column schema (`config.METADATA_COLUMNS`): `run_id, model,
n_estimators, max_samples, random_state, runtime_seconds, threshold_rule,
flagged_count, n_neighbors, metric`. Validated by
`phase4.validate_phase3_run_metadata`: exact schema, unique non-null run IDs,
run set equal to the expected ten runs, integral non-negative `flagged_count`.

### 1.3 Ground-truth registry

`data/processed/stream-a/labels/ground_truth_registry.csv`
(default constant `config.DEFAULT_GROUND_TRUTH_PATH`, CLI `--ground-truth`)

Schema `row_id, Class` — nothing else. On the real repository: 284,807 unique
row IDs, 492 positive labels. Validated by
`phase4.validate_ground_truth_registry`:

- both columns present, no extra columns;
- `row_id`: no missing values, no duplicates;
- `Class`: no missing values, strictly binary (only 0 and 1);
- reports `total_observations` and `positive_labels`.

---

## 2. Phase 3 integrity manifest / legacy inputs

Phase 4 looks for `phase3_commit_manifest.json` **next to the prediction
bundle**. The hardened Stage 1 Phase 3 does not generate manifests, so on the
current repository this file is absent and the inputs are handled as a
**legacy unmanifested pair**:

- strict structural validation (section 1) is the integrity control;
- the SHA-256 hash and byte size of every consumed input are recorded in
  `phase4_run_metadata.json` (`inputs.{predictions,run_metadata,ground_truth}`);
- `input_manifest` records `{"present": false, "verified": false,
  "mode": "legacy_unmanifested"}` with an explicit note that manifest
  verification was **NOT** performed — verification is never claimed falsely.

If a manifest is ever placed there (schema: `{"manifest_version": 1,
"created_utc": ..., "artifacts": {<filename>: {"sha256", "size_bytes"}}}`,
produced by `mplad.common.manifest.build_manifest`), Phase 4 verifies every
listed hash/size **before** consuming anything, and additionally requires the
manifest to cover the two consumed Phase 3 artifacts. Any mismatch, missing
file, or partial coverage is a hard error and nothing is evaluated or written.

Phase 4 publishes its own output manifest in the same schema
(`phase4_commit_manifest.json`), covering its three data outputs, so later
phases can verify Phase 4 artifacts the same way.

---

## 3. Alignment rules (the historical bug, made impossible)

The original Colab Phase 4 sorted labels by `row_id` while prediction arrays
stayed in draw order, then aligned by **array position** — every metric was
computed against the wrong labels. The new rules:

1. Alignment is a **key join on `row_id`**, never positional:
   `pandas.merge(..., on="row_id", how="left", validate="one_to_one")`.
2. The **prediction sequence is preserved** end-to-end: the evaluation
   dataset lists rows in the bundle's stored `row_ids` order, per run, runs in
   Phase 3 metadata order.
3. Any prediction `row_id` missing from the registry is a **hard error**
   (unmatched IDs listed, never silently dropped).
4. A changed row count after the join is a hard error (incomplete join).
5. Duplicate IDs on either side are already rejected upstream (registry
   validation, bundle validation).
6. Registry rows outside the 30,000-row sample are unused — expected and
   reported (`registry_summary.matched_to_sample`).

Because the bundle stores one shared `row_ids` array, the validated join is
performed once on that sequence and each run's scores/flags are attached to
it positionally — which is exactly how Phase 3 produced them.

## 4. Score orientation

| Column | Meaning |
|---|---|
| `native_score` | the Phase 3 stored estimator score (IF `decision_function`, LOF `negative_outlier_factor_`): **lower = more anomalous** |
| `anomaly_score` | `= -native_score`: **higher = more anomalous** (canonical orientation) |

Ranking metrics use `anomaly_score`. The distinction is kept explicit in the
evaluation dataset, the metrics table and the provenance record.

## 5. Metric definitions

Per run (`phase4.evaluate_single_run`), positive label = 1, `zero_division=0`:

- `average_precision` — `sklearn.metrics.average_precision_score(y_true, anomaly_score)`
- `roc_auc` — `sklearn.metrics.roc_auc_score(y_true, anomaly_score)`
- `precision_at_1pct`, `recall_at_1pct`, `f1_at_1pct` — computed **from the
  saved Phase 3 flags exactly as supplied** (the bottom-1% rule is never
  recomputed, re-optimised or re-thresholded in Phase 4)
- `tn`, `fp`, `fn`, `tp` — `confusion_matrix(y_true, flag, labels=[0, 1])`
- `sample_size`, `fraud_count`, `fraud_prevalence` (= fraud_count / sample_size),
  `flagged_count`, `flagged_proportion` (= flagged_count / sample_size)

A sample containing a single ground-truth class is rejected (AP/ROC-AUC
undefined). All ten runs are evaluated; there is **no model selection** and no
run is highlighted as confirmatory.

## 6. Output schemas

Location (default `config.DEFAULT_PHASE4_OUTPUT_DIR`, CLI `--output-dir`):
`results/stream a/phase 4/reproduction/` — deliberately a sub-directory so
historical Phase 4 outputs directly under `results/stream a/phase 4/` are
never touched. Existing files block execution unless `--overwrite` is passed.

### 6.1 `phase4_evaluation_dataset.csv` — long form, one row per (run_id, row_id)

10 runs × 30,000 rows = 300,000 rows on the canonical experiment.

| Column | Content |
|---|---|
| `run_id` | e.g. `IF_003`, `LOF_004` |
| `row_id` | the Phase 2 stable identifier |
| `Class` | ground-truth label (0/1), joined via row_id |
| `native_score` | Phase 3 native score (lower = more anomalous) |
| `anomaly_score` | `-native_score` (higher = more anomalous) |
| `flag` | the saved Phase 3 bottom-1% flag |

### 6.2 `phase4_metrics.csv` — one row per run, in Phase 3 metadata order

`run_id, model, n_estimators, max_samples, random_state, n_neighbors,
metric, runtime_seconds, threshold_rule` (Phase 3 metadata passthrough,
joined one-to-one on `run_id`; the metadata `flagged_count` is cross-checked
during validation and carried by the recomputed metric column) followed by:

`average_precision, roc_auc, precision_at_1pct, recall_at_1pct, f1_at_1pct,
tn, fp, fn, tp, sample_size, fraud_count, fraud_prevalence, flagged_count,
flagged_proportion`

### 6.3 `phase4_run_metadata.json` — provenance record

```json
{
  "phase": "4", "stream": "A", "layer": "label_based_evaluation",
  "run_mode": "execute", "created_utc": "...",
  "inputs": {
    "predictions":   {"path": "...", "sha256": "...", "size_bytes": ...},
    "run_metadata":  {"path": "...", "sha256": "...", "size_bytes": ...},
    "ground_truth":  {"path": "...", "sha256": "...", "size_bytes": ...}
  },
  "input_manifest": {"present": false, "verified": false,
                     "mode": "legacy_unmanifested", "path": "...", "note": "..."},
  "registry_summary": {"total_observations": 284807, "positive_labels": 492,
                       "matched_to_sample": 30000},
  "sample": {"sample_size": 30000, "fraud_count": 47, "fraud_prevalence": ...},
  "run_ids": ["IF_001", "...", "LOF_005"],
  "score_orientation": {"native_score": "...", "anomaly_score": "...", "...": "..."},
  "outputs": {"evaluation_dataset": "...", "metrics": "...",
              "run_metadata": "...", "manifest": "..."},
  "environment": {"python": "...", "numpy": "...", "pandas": "...",
                  "scikit-learn": "...", "executable": "..."},
  "model_fitting": {"models_fitted": 0, "note": "..."},
  "reference_comparison": {"path": "...", "comparisons": ..., "matches": ...,
                           "all_match": true}
}
```

### 6.4 `phase4_commit_manifest.json`

`{"manifest_version": 1, "created_utc": "...", "artifacts": {"<filename>":
{"sha256": "<64 hex>", "size_bytes": ...}}}` covering the three outputs
above. Verify with:

```python
from mplad.common.manifest import load_manifest, verify_manifest
verify_manifest(load_manifest(<manifest path>), <output dir>)
```

## 7. CLI

```
python scripts/run_phase4.py                # preflight (default): validate only
python scripts/run_phase4.py --execute      # calculate + write
python scripts/run_phase4.py --execute --overwrite
python scripts/run_phase4.py --execute --output-dir "results/stream a/phase 4/reproduction_v2"
python scripts/run_phase4.py --execute --reference-metrics <reference.csv>
```

Input overrides: `--predictions`, `--run-metadata`, `--ground-truth`.
Preflight writes nothing and calculates nothing; `--execute` refuses to
replace existing outputs without `--overwrite`.

## 8. Acceptance reference checks (post-hoc, NOT computation inputs)

The corrected historical Phase 4 results, quoted from the migration
specification as **rounded reference checks** — Phase 4 must reproduce these
from the saved predictions and labels, independently recalculated:

| run | AP | ROC-AUC | P@1% | R@1% | F1@1% | TP |
|---|---|---|---|---|---|---|
| IF_003 | 0.3126 | 0.9803 | 0.1000 | 0.6383 | 0.1729 | 30 |
| LOF_004 | 0.3229 | 0.9536 | 0.1267 | 0.8085 | 0.2190 | 38 |

(Sanity: 47 frauds in the 30k sample → IF_003 recall 30/47 = 0.6383,
LOF_004 recall 38/47 = 0.8085; 300 flags → precisions 30/300 = 0.1000 and
38/300 ≈ 0.1267.)

These values are **not hardcoded anywhere in the code** — the metrics are
always recalculated. To compare all ten runs against an existing corrected
table (e.g. the historical Phase 4 metrics CSV), pass it via
`--reference-metrics <csv with a run_id column>`: the runner prints a
side-by-side comparison (values match when equal at 4-decimal rounding) and
records the outcome in the provenance JSON.

## 9. Scope restrictions honoured

Phase 3 code, configurations, scores, flags and the 30,000-row sample are
untouched; no new threshold is introduced; raw/processed datasets, DVC
files and historical notebooks are not modified; historical Phase 4 outputs
are never overwritten (separate `reproduction/` output directory); Phase 5/6
and Streamlit are out of scope.
