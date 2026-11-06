# Phase 3 Migration Guide — Stage 1 (Stream A)

Migration of the established primary 30k experiment from the recovered Colab
notebook (cell index 4) into a reusable, reproducible Python pipeline.
**Methodology, configurations and output contract are preserved; nothing was
refit during the migration.**

## 1. What this delivery contains

```
mplad-anomaly-detection/
├── src/mplad/
│   ├── __init__.py
│   ├── common/
│   │   ├── __init__.py
│   │   ├── config.py        # paths + FROZEN experiment constants
│   │   ├── io.py            # artifact load/save with overwrite protection
│   │   └── validation.py    # schema, row_id, leakage validation
│   └── stream_a/
│       ├── __init__.py
│       └── phase3.py        # the primary 30k IF/LOF experiment
├── scripts/
│   └── run_phase3.py        # CLI runner (dry-run default, --execute opt-in)
├── tests/
│   ├── conftest.py
│   └── test_phase3.py       # 41 lightweight tests, synthetic data only
└── notebooks/
    └── phase3_trackA.ipynb  # new thin research notebook (guarded execution)
```

`tests/` is the only new top-level directory (required by Objective D). No
other folders are added; `common/phase4-6` and `app/` will be created in
their own stages.

## 2. Notebook retention policy (Objective A)

| File | Role | Action |
|---|---|---|
| `notebooks/phase3_trackA.ipynb` (2 deprecated contamination cells, 17,308 bytes, SHA-256 `D91C3DF1...A5E9DD` — verified against the upload) | superseded prototype | copy to `notebooks/archive/phase3_trackA_deprecated_2cell.ipynb`, then replace the live filename with the new notebook |
| recovered 14-cell Colab notebook (`phase3_trackA_alternate_14cell_candidate.ipynb`, SHA-256 `4E162852...63D95E`) | historical research source; **cell index 4** = the experiment extracted here | copy to `notebooks/archive/phase3_trackA_recovered_colab_14cell.ipynb` |
| new `notebooks/phase3_trackA.ipynb` | thin research notebook; imports `mplad.stream_a.phase3` | becomes the live notebook after the backups above are verified |

Nothing is deleted; both historical versions are preserved byte-identically
(verify with `Get-FileHash` after copying).

## 3. How the new notebook calls the module

- A bootstrap cell walks up from the notebook's directory to the repo root
  and puts `src/` on `sys.path` — no package installation required.
- Section 1 loads and validates FS-A (`mplad.common.io` + `validation`).
- Section 2 draws the 30k sample via `phase3.build_experiment_sample`
  (cheap, no fitting) and proves determinism by drawing twice.
- Section 4 is the **only** place that can fit models, behind
  `RUN_EXPERIMENT = False`; opening or running the notebook top-to-bottom
  never trains anything.
- Section 5 reloads both artifacts from disk and re-checks the contract
  (structure, dtypes, flag counts, native score orientation).

## 4. Verification tiers — do them in this order

1. **Static** (no data, no code execution): SHA-256 of the archived
   notebooks; `python -c "import ..."` smoke check; notebook JSON validity.
2. **Synthetic tests** (no real data, no 10-model fit):
   `python -m pytest tests\test_phase3.py -v` — 41 tests covering schema
   validation, `Class` rejection, row_id uniqueness, sample reproducibility
   (including bit-equality with the legacy `np.random.seed` API), run
   consistency, score direction, dtypes/counts, pickle structure, metadata
   schema and overwrite protection.
3. **Real data, no fitting**: `python scripts\run_phase3.py` (dry run) —
   loads and validates the real FS-A, draws the 30k sample twice, reports
   the planned runs and output status.
4. **Actual model execution**: `python scripts\run_phase3.py --execute
   --output-dir "results\stream a\phase 3\reproduction"` — ~10–20 minutes,
   dominated by the LOF grid. The canonical artifacts are untouched unless
   you explicitly target them with `--overwrite`.

## 5. Cell-4 fidelity notes

Preserved bit-for-bit: sampling mechanism (`RandomState(42).choice` ==
`np.random.seed(42); np.random.choice`, asserted by a test), 5+5 frozen
config grids, `n_jobs=1`, `ball_tree`/`leaf_size=40`, no `contamination`,
percentile-on-float64-then-store-float32 flagging, native score orientation,
metadata CSV schema, pickle structure.

Deliberate additions that change no numbers: input validation, overwrite
protection, parameterised paths (Colab Drive path kept only as
`config.HISTORICAL_COLAB_STORAGE_DIR` context), isolated RandomState,
`time.perf_counter()` for the runtime metadata field.

## 6. Suggested provenance entry (`docs/provenance_log.md`)

```markdown
## 2026-11-04 — Phase 3 pipeline migration (Stage 1)
- Extracted the primary 30k experiment (recovered Colab notebook, cell index 4)
  into src/mplad/stream_a/phase3.py + scripts/run_phase3.py + tests/.
- Methodology preserved: RandomState(42) 30k draw (test-verified identical to the
  legacy global API), 5 IF + 5 LOF frozen configs, bottom-1% post-hoc flags on
  native scores, float32/uint8 storage, metadata CSV schema and prediction
  pickle contract unchanged.
- Historical notebooks preserved under notebooks/archive/ (deprecated 2-cell,
  SHA-256 D91C...E9DD; recovered 14-cell Colab).
- No model refit during migration; canonical artifacts in results/stream a/phase 3/
  untouched. Larger novelty-mode experiment intentionally not implemented; its
  exact dataset size remains to be confirmed from artifacts.
```

## 7. Out of scope (next stages)

Phase 4 evaluation, Phase 5 diagnostics/plots, Phase 6 agreement, the
separately-named larger-experiment runner (after artifact inspection), and
the Streamlit app.
