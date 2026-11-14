# PR-08 Frozen Source Inventory

**Baseline:** `831c9b4d23349b57d48828157d68fefde5927f02` (PR-07B merge, PR #2)
**Branch:** `pr-08-research-readonly`
**Integrity checker:** `ci/check_frozen_integrity.py` (SHA-256, raw bytes)
**Result:** 28/28 artifacts match at baseline and after PR-08 changes.

---

## Classification method

Each of the 28 protected artifacts was inspected read-only. The
classification records: repository-relative path, file format, SHA-256
identity, dataset/research family, research purpose, model/analytical
method, content type, machine-readability, suitability for application
display, presence of stable record identifiers, scientific limitations,
and an eligibility decision (ELIGIBLE / CONDITIONAL / INELIGIBLE).

No frozen file was modified during inspection.

---

## 28-artifact classification

### Documentation (10 artifacts)

| # | Path | Format | SHA-256 (prefix) | Content | Eligibility |
|---|---|---|---|---|---|
| 1 | `docs/MPLAD_Project_Inference_and_decision.docx` | OOXML | `6312c4ed...` | Narrative project report | INELIGIBLE (binary, not machine-readable) |
| 2 | `docs/MPLAD_framework_pipeline.md` | Markdown | `7d5ad8da...` | Research framework (8-phase pipeline description) | INELIGIBLE (narrative methodology, no data) |
| 3 | `docs/PHASE3_MIGRATION_GUIDE.md` | Markdown | `fea14011...` | Migration guide for Phase 3 code | INELIGIBLE (administrative) |
| 4 | `docs/Phase-0.md` | Markdown | `3f00ce99...` | Phase 0 scope statement | INELIGIBLE (narrative) |
| 5 | `docs/feature_space_manifest.md` | Markdown | `bf2ee307...` | Feature space description (284,807 rows, V1-V28, Time, Amount) | INELIGIBLE (describes data not in repo) |
| 6 | `docs/phase4_contract.md` | Markdown | `3c8034b6...` | Phase 4 evaluation contract (metrics definitions, score orientation, reference checks) | CONDITIONAL (documents the evaluation methodology and reference values IF_003 AP=0.3126, LOF_004 AP=0.3229) |
| 7 | `docs/phase5_figure_catalog.md` | Markdown | `fe24df9d...` | Phase 5B figure catalog (8 figures) | INELIGIBLE (describes figures not in repo) |
| 8 | `docs/phase6_contract.md` | Markdown | `00cc73bc...` | Phase 6 cross-method consistency contract (reference values, interpretation principles) | CONDITIONAL (documents the Phase 6 reference values and interpretation rules) |
| 9 | `docs/phase7_synthesis.md` | Markdown | `7436d5dd...` | Phase 7 synthesis, limitations, governance | INELIGIBLE (narrative) |
| 10 | `docs/provenance_log.md` | Markdown | `7945c96a...` | Decision/provenance log | INELIGIBLE (administrative) |

### Source code (13 artifacts)

| # | Path | Format | SHA-256 (prefix) | Content | Eligibility |
|---|---|---|---|---|---|
| 11 | `src/mplad/__init__.py` | Python | `a9d13b60...` | Package init | INELIGIBLE (empty init) |
| 12 | `src/mplad/common/__init__.py` | Python | `cabb07d5...` | Package init | INELIGIBLE (empty init) |
| 13 | `src/mplad/common/config.py` | Python | `3e61e405...` | Frozen configuration (IF/LOF grids, threshold, paths) | CONDITIONAL (contains frozen parameter grids; values are constants) |
| 14 | `src/mplad/common/io.py` | Python | `243dc5b8...` | I/O utilities (manifest, output writing) | INELIGIBLE (infrastructure code) |
| 15 | `src/mplad/common/manifest.py` | Python | `b8bbf9f9...` | Manifest build/verify utilities | INELIGIBLE (infrastructure code) |
| 16 | `src/mplad/common/validation.py` | Python | `417a5ae6...` | Feature matrix validation | INELIGIBLE (infrastructure code) |
| 17 | `src/mplad/stream_a/__init__.py` | Python | `7c37a2bc...` | Package init | INELIGIBLE (empty init) |
| 18 | `src/mplad/stream_a/phase3.py` | Python | `4ce2d229...` | Phase 3: iForest/LOF experiment runner | INELIGIBLE (executes models; no precomputed results stored) |
| 19 | `src/mplad/stream_a/phase4.py` | Python | `fcae730c...` | Phase 4: label-based evaluation | INELIGIBLE (computes metrics; no precomputed results stored) |
| 20 | `src/mplad/stream_a/phase5.py` | Python | `e3b0c442...` | Phase 5: empty file (0 bytes) | INELIGIBLE (empty) |
| 21 | `src/mplad/stream_a/phase5_analysis.py` | Python | `8048479c...` | Phase 5A: bootstrap, Spearman/Jaccard, hypergeometric | CONDITIONAL (contains `EXPLORATORY_SELECTION_CAVEAT` constant) |
| 22 | `src/mplad/stream_a/phase5_plots.py` | Python | `473384ae...` | Phase 5B: PCA figure rendering | INELIGIBLE (plotting code; no precomputed results) |
| 23 | `src/mplad/stream_a/phase6.py` | Python | `2a9e7d79...` | Phase 6: cross-method consistency analysis | **ELIGIBLE** (contains `PHASE6_REFERENCE_VALUES` dict — 18 precomputed aggregate reference values; `INTERPRETATION_PRINCIPLES` — 7 authored strings; `PHASE6_REFERENCE_TOLERANCES`) |

### Tests (5 artifacts)

| # | Path | Format | SHA-256 (prefix) | Content | Eligibility |
|---|---|---|---|---|---|
| 24 | `tests/test_phase3.py` | Python | `c9bc1113...` | Phase 3 software-structure tests (synthetic data) | INELIGIBLE (test code) |
| 25 | `tests/test_phase4.py` | Python | `c093b676...` | Phase 4 software-structure tests (synthetic data) | INELIGIBLE (test code) |
| 26 | `tests/test_phase5_analysis.py` | Python | `70b2e7a7...` | Phase 5A software-structure tests (synthetic data) | INELIGIBLE (test code) |
| 27 | `tests/test_phase5_plots.py` | Python | `a8950526...` | Phase 5B software-structure tests (synthetic data) | INELIGIBLE (test code) |
| 28 | `tests/test_phase6.py` | Python | `f5e92884...` | Phase 6 software-structure tests (synthetic data) | INELIGIBLE (test code) |

---

## Selected eligible source

**Artifact #23: `src/mplad/stream_a/phase6.py`** — the single ELIGIBLE
artifact. Contains the `PHASE6_REFERENCE_VALUES` dict (18 precomputed
aggregate reference values from the canonical ULB benchmark experiment)
and the `INTERPRETATION_PRINCIPLES` tuple (7 authored interpretation
strings). Machine-readable, experiment-level granularity, clear
scientific provenance, documented limitations.

The `EXPLORATORY_SELECTION_CAVEAT` from `src/mplad/stream_a/phase5_analysis.py`
(artifact #21, CONDITIONAL) is also served as supplementary metadata
for the eligible source.

All other artifacts are INELIGIBLE or CONDITIONAL (documentation only,
infrastructure code, test code, or empty files). No record-level
results, no PCA coordinates, no per-observation scores are stored in
any frozen artifact — the repository contains only the research
pipeline code and its documentation, not the computed outputs.
