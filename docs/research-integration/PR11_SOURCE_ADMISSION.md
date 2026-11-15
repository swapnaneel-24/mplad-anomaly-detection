# PR-11 Source Admission — Phase 5B Figure Gallery, Methodology, and Objective Traceability

**Branch:** `pr-11-phase5b-gallery`
**Date:** 2026-11-15
**Status:** Mandatory pre-implementation gate
**Baseline:** `e57cc15239e2f590d9aa3ca6bc2bab7ca1310dd3` (PR-10 merge commit on `main`)

---

## 1. Decision

**ADMITTED with a conditional runtime trust anchor and a licensing-gated public binary delivery.**

| Evidence family | Decision | Basis |
|---|---|---|
| Phase 5B catalog CSV (`phase5_figure_catalog.csv`) | **ADMITTED** | Local DVC MD5 `a556c223afc2885c28fc9043cf49c6cf` matches the `.dvc` pointer; SHA-256 `b5ce8938e4ca75fbeffe99f79cdebd268e750a0fe0b5729b94a230184101bbf2` matches the figure manifest entry. |
| Eight canonical PNG binaries (`phase5_plot{1..8}_*.png`) | **ADMITTED** | All eight locally materialized; raw-byte MD5 and SHA-256 match both the `.dvc` pointers and the figure manifest; raw byte sizes match the catalog's `size_bytes` column exactly. |
| Phase 5B figure manifest (`phase5_plot_commit_manifest.json`) | **ADMITTED for trusted local evidence, conditional on implementation of the independent Phase 5B commit-manifest trust anchor before runtime publication** | The manifest is self-consistent on disk and covers the catalog, all eight PNGs, and the plot-metadata JSON (10 artifacts, `manifest_version: 1`). However, no code-pinned `TRUSTED_PHASE5_PLOT_COMMIT_MANIFEST_SHA256` constant exists in `backend/app/services/`; PR-11 implementation must introduce one. The candidate pin, LF-normalized SHA-256, is recorded in Section 4 for re-verification against the committed file at implementation time. |
| Phase 5B plot metadata JSON (`phase5_plot_metadata.json`) | **ADMITTED** | Reported Phase 4 lineage matches 3/3 pinned identities. Its own manifest verification evidence is retained in `input_manifests.phase4_commit_manifest.verified == true` and `input_manifests.phase5_commit_manifest.verified == true`. |
| Methodology documents (`Phase-0.md`, `phase5_figure_catalog.md`, `phase6_contract.md`, `phase7_synthesis.md`, `provenance_log.md`, `phase4_contract.md`, `PHASE3_MIGRATION_GUIDE.md`) | **ADMITTED** | Authoritative narrative inputs, subject to verifying exact cited passages before serving. Where the sources do not collectively establish a required detail, the evidence gap is labelled explicitly rather than filled with newly authored prose. |
| Phase 4 — Phase 5B lineage | **VERIFIED** | Three matching SHA-256 identities; see Section 6. |
| Historical/scratch PNGs (26 files at `results/stream a/phase 5/` top level, including 7 `FULL_*.png` variants) | **EXCLUDED** | No public serving under PR-11. These are historical outputs from the pre-migration Colab phase; their filenames do not consistently correspond to the canonical figure numbering, and their provenance does not carry manifest verification. |
| Clean-checkout figure availability (hosted CI without DVC) | **CONDITIONAL** | Catalog and provenance remain available from Git-tracked JSON and CSV; individual PNG serving requires the corresponding payload to be materialized and verified. Unavailable figures must report `artifact_missing` per-image, not fail globally. |
| Anonymous public PNG binary delivery | **GATED — conditional on licensing verification** | Per `docs/phase7_synthesis.md` — Stream A dataset is governed by ODbL v1.0 / DbCL v1.0; raw datasets are not redistributed; derivative artifacts are DVC-tracked. Whether rendered figure binaries constitute a redistribution of the derivative work under ODbL's share-alike terms requires explicit confirmation before anonymous public delivery is enabled. Until confirmed, PR-11 must preserve the verified catalog/provenance surface while withholding the corresponding public binary. |

Pickle payloads remain **BLOCKED** (unchanged from PR-10). No new artifacts beyond the eight canonical PNGs, the catalog CSV, the plot metadata JSON, and the figure manifest are admitted to the PR-11 serving surface.

---

## 2. Evidence examined

### 2.1 Git-tracked (present in clean checkout)

| File | Integrity anchor |
|---|---|
| `results/stream a/phase 5/figures/reproduction/phase5_figure_catalog.csv` | DVC pointer + figure manifest |
| `results/stream a/phase 5/figures/reproduction/phase5_figure_catalog.csv.dvc` | Git-tracked pointer |
| `results/stream a/phase 5/figures/reproduction/phase5_plot_commit_manifest.json` | Self-consistent on disk; **must be pinned** by PR-11 implementation |
| `results/stream a/phase 5/figures/reproduction/phase5_plot_metadata.json` | Phase 4 lineage cryptographically anchored (Section 6) |
| `results/stream a/phase 5/figures/reproduction/phase5_plot{1..8}_*.png.dvc` (8 pointers) | Git-tracked pointers, one per canonical figure |
| `results/stream a/phase 5/figures/reproduction/.gitignore` | Local-only gitignore for the reproduction directory |

### 2.2 DVC-backed binaries (materialized on this workstation; absent in hosted CI)

| File | Size (bytes) | MD5 (raw) matches pointer | SHA-256 (raw) matches manifest |
|---|---|---|---|
| `phase5_plot1_precision_recall.png` | 229,243 | OK | OK |
| `phase5_plot2_fraud_discovery.png` | 200,277 | OK | OK |
| `phase5_plot3_hypergeometric_overlap.png` | 146,198 | OK | OK |
| `phase5_plot4_spearman_matrix.png` | 211,218 | OK | OK |
| `phase5_plot5_jaccard_matrix.png` | 185,635 | OK | OK |
| `phase5_plot6_topk_jaccard.png` | 120,134 | OK | OK |
| `phase5_plot7_rank_vs_rank.png` | 369,793 | OK | OK |
| `phase5_plot8_pca_agreement.png` | 230,576 | OK | OK |

Verification performed on 2026-11-15 on Windows 11. PNGs are hashed as **raw bytes**; no CRLF or text normalization is applied. The figure-serving adapter must also validate the PNG signature and image dimensions before delivery.

### 2.3 Catalog CSV verification (reference)

- `.dvc` pointer MD5: `a556c223afc2885c28fc9043cf49c6cf` — matches raw MD5 of the CSV
- Figure manifest SHA-256 entry: `b5ce8938e4ca75fbeffe99f79cdebd268e750a0fe0b5729b94a230184101bbf2` — matches raw SHA-256 of the CSV
- Catalog rows: 8 (one per canonical figure). Columns: `figure_no, filename, title, purpose, input_artifacts, conventions, size_bytes`. The `size_bytes` column matches the actual PNG binary sizes exactly (Section 2.2).

### 2.4 Manifest verification state at admission

`phase5_plot_metadata.json` records `input_manifests.phase4_commit_manifest.verified == true` and `input_manifests.phase5_commit_manifest.verified == true`, with mode `manifest_verified` and `present == true` for both. This means the figure generation step consumed Phase 4 and Phase 5A inputs only after their own manifests verified successfully at render time. Retained as reported evidence; not re-executed under PR-11.

### 2.5 Figure generation CLI contract (documentation-only reference)

`docs/phase5_figure_catalog.md` documents the generation and verification contract:

    python scripts/run_phase5_plots.py                 # preflight
    python scripts/run_phase5_plots.py --execute       # render + publish
    verify_manifest(load_manifest(<figures dir>/phase5_plot_commit_manifest.json), <figures dir>)

PR-11 does **not** invoke this generator. It consumes the already-published artifacts strictly read-only.

---

## 3. Findings

### F1 — Three-PNG-set hazard and the figure-serving allowlist

The repository contains 34 PNG files under `results/stream a/phase 5/`:

- **8 canonical** PNGs at `results/stream a/phase 5/figures/reproduction/` — the only set admitted to PR-11
- **26 noncanonical** PNGs at `results/stream a/phase 5/` (top level), a subset of which are 7 `FULL_*.png` scale-stress companion figures

The 26-file noncanonical set includes historical scratch figures with inconsistent filenames and numbering that do not correspond to the canonical figure sequence (for example `phase5_plot1_PR_curves.png`, `phase5_plot3_ECDF.png`, `phase5_plot8_rank_vs_rank.png`). Their provenance does not carry manifest verification.

**The figure-serving adapter must never discover files through a wildcard directory scan.** The allowlist is exactly:

    phase5_plot1_precision_recall.png
    phase5_plot2_fraud_discovery.png
    phase5_plot3_hypergeometric_overlap.png
    phase5_plot4_spearman_matrix.png
    phase5_plot5_jaccard_matrix.png
    phase5_plot6_topk_jaccard.png
    phase5_plot7_rank_vs_rank.png
    phase5_plot8_pca_agreement.png

Any request parameter that names a figure must be validated against this allowlist. **No request parameter may be interpreted as an arbitrary filesystem path.**

### F2 — Two independent commit manifests

Phase 5 has two separate manifests with different trust anchors:

| Manifest | Path | Coverage | Trust anchor in backend code |
|---|---|---|---|
| Phase 5A CSV manifest | `results/stream a/phase 5/reproduction/phase5_commit_manifest.json` | 9 Phase 5A CSVs | `TRUSTED_PHASE5_COMMIT_MANIFEST_SHA256` — pinned by PR-10 (post Finding H) |
| Phase 5B figure manifest | `results/stream a/phase 5/figures/reproduction/phase5_plot_commit_manifest.json` | catalog CSV + 8 PNGs + plot metadata JSON (10 artifacts) | **NONE** — requires a new PR-11 pin |

The absence of a Phase 5B pin is the direct analogue of PR-10's Finding B on the figure side. Without it, any local modification to `phase5_plot_commit_manifest.json` would be silently accepted.

### F3 — Objective labels use source-native (a)/(b)/(c)

An exhaustive repository search for the literal `OBJ-1`/`OBJ-2`/`OBJ-3` identifiers returns no matches in project sources. The authoritative three objectives are stated in `docs/provenance_log.md` Section 1:

    The initial formulation posited three objectives:
    (a) data preparation and preprocessing,
    (b) application of Isolation Forest and Local Outlier Factor with comparative evaluation, and
    (c) assessment of detection consistency, false-positive implications, and ethical considerations.

These are the source-native identifiers. PR-11's traceability surface will use (a), (b), (c) with those exact interpretations, cross-referenced to the six research questions RQ1–RQ6 documented in `docs/Phase-0.md` Section 0.4. No new identifiers will be introduced as though they were present in the foundational documents.

Where a required detail is not collectively established by the admitted documents, the evidence gap must be labelled explicitly (for example, "no standalone preprocessing-methodology document exists; evidence gaps labelled: <list>"), not filled with newly authored prose.

### F4 — Phase 5B — Phase 4 lineage is cryptographically verified

Three Phase 4 SHA-256 identities recorded by `phase5_plot_metadata.json` match the constants already pinned by `backend/app/services/phase5a_catalog.py` exactly (see Section 6). This establishes, with cryptographic evidence, that the Phase 5B figures were rendered from the same frozen Phase 4 execution as the Phase 5A tables admitted under PR-09 and PR-10.

### F5 — Methodology documentation is substantive

The admitted methodology sources collectively cover the required PR-11 surfaces. No dedicated preprocessing-methodology document exists as a standalone artifact; preprocessing detail is distributed across `Phase-0.md` Section 0.3.1, `phase5_figure_catalog.md` Figure 8 conventions, and `provenance_log.md` Phase 2 (Track A). This is not a blocker: the sources collectively establish the required detail. Gaps, if any, will be labelled explicitly in the traceability surface rather than invented.

---

## 4. Consequences for PR-11 implementation

1. **Independent Phase 5B trust anchor.** Add a constant to the backend that pins the figure manifest:

       TRUSTED_PHASE5_PLOT_COMMIT_MANIFEST_SHA256 = (
           "e883ce52aa8269d3a841fb32ebcd4a739850a2708bd70cd66dd2acf48be5c549"
       )

   This is the LF-normalized SHA-256 of the current on-disk manifest (raw size 1,730 bytes; the raw-bytes and CRLF-reconstructed digests are `edf88ff0b6def63169e69e4690894e795a78cc5045fce41c046dfeba6c5edb76`). The value is a **candidate**, and the implementation must re-verify it against the committed file using the same LF-canonicalization logic already in place for `TRUSTED_PHASE5_COMMIT_MANIFEST_SHA256` before it is treated as authoritative. The verifier must canonicalize the approved text representation of the manifest, verify the pinned digest, and only then trust the manifest's artifact entries.

2. **Figure-manifest verification must precede artifact trust.** The catalog CSV, the eight PNGs, and the plot metadata JSON are only trusted after the figure manifest itself verifies against the pinned constant. A mismatch must fail closed — no partial trust.

3. **Raw-byte hashing only for PNGs.** The figure-serving adapter must verify each PNG against both the `.dvc` pointer (MD5 + size) and the figure manifest (SHA-256 + size) using raw bytes with no CRLF normalization. Additionally, the adapter must validate the PNG signature (`\x89PNG\r\n\x1a\n`) and image dimensions before returning the bytes to a client.

4. **Path allowlist and path-injection prevention.** Serving is restricted to the eight filenames listed in F1. No request parameter may be interpreted as an arbitrary filesystem path. Symbolic-link resolution must not escape `results/stream a/phase 5/figures/reproduction/`.

5. **Per-image availability.** Availability is reported per figure. A missing or corrupted individual PNG must not disable the catalog or other figures. The contract is `available: true` when the payload verifies and `available: false / reason: artifact_missing` when it does not, matching PR-10's per-capability pattern.

6. **Publication gate.** Before enabling anonymous public PNG delivery, the licensing question in Section 1's last row must be resolved. If the answer is "cannot be established in this PR", the implementation must ship with binary serving **disabled by default**, and the verified catalog/provenance surface **enabled**. The gate is enforceable as a configuration flag, not a code comment.

7. **No new endpoints beyond what PR-11 requires.** PR-11 may add: a verified figure catalog endpoint, a controlled binary delivery endpoint (once the licensing gate clears), and a methodology/objective-traceability metadata endpoint if the existing contracts in PR-08/09/10 cannot serve the required shape. The existing six-workspace navigation is unchanged. No regeneration of Phase 5B figures, no new PCA/UMAP experiments, no modification of prior scientific evidence.

8. **Objective traceability data shape.** Traceability links each source-native objective (a)/(b)/(c) and each research question RQ1–RQ6 to evidence that is already served by PR-08/09/10/11. Illustrative shape (per PR-11 authorization, not a storage commitment):

       {
         "objective_id": "b",
         "interpretation": "Application and comparative evaluation of Isolation Forest and LOF",
         "evidence": [
           { "type": "canonical_benchmark", "reference": "PR-09 benchmark catalog", "verification_status": "verified" },
           { "type": "phase5a_agreement",   "reference": "PR-10 agreement evidence", "verification_status": "verified" },
           { "type": "phase5b_figures",     "reference": "PR-11 figures 1-8",        "verification_status": "verified" }
         ]
       }

---

## 5. Explicitly excluded sources

The following are **not** admitted to the PR-11 serving surface and must **not** appear in any endpoint, gallery page, or metadata response:

- All 26 noncanonical PNGs at `results/stream a/phase 5/` (top level), including the 7 `FULL_*.png` scale-stress companion figures
- Any file outside `results/stream a/phase 5/figures/reproduction/` whose name is not in the allowlist of Section 3, Finding F1
- All Pickle artifacts (unchanged from PR-10)
- Any `.csv` or `.json` under `results/stream a/phase 5/reproduction/` not already admitted by PR-10 (Phase 5A CSVs remain PR-10's responsibility)

The 284,807-record historical ULB companion (LOF Novelty Mode) is not served by any PR-11 endpoint. It may be referenced in methodology text as a documented limitation of the benchmark analysis (per `docs/phase7_synthesis.md` Section 2), but not as a served dataset.

---

## 6. Phase 5B — Phase 4 lineage (VERIFIED)

Three Phase 4 identities recorded in `phase5_plot_metadata.json` match the constants pinned by `backend/app/services/phase5a_catalog.py` exactly:

| Artifact | SHA-256 | Source |
|---|---|---|
| `phase4_evaluation_dataset.csv` | `affbf02c63da594d1fdb2c66d07121f39221f7e24082eed4770b59d4598bb048` | `phase5_plot_metadata.json` `inputs.phase4_evaluation_dataset.sha256`; matches `PHASE4_EVAL_DATASET_SHA256` |
| `phase4_metrics.csv` | `6535001ce38766d7e52fef84253a7d95e6335b6183fd34f6ead12210eec99acd` | `phase5_plot_metadata.json` `input_manifests.phase4_commit_manifest.artifacts.phase4_metrics.csv.sha256`; matches `PHASE4_METRICS_SHA256` |
| `phase4_run_metadata.json` | `b17f40635e73cbc11932447a9616bc9288f9bfbbc50103e2441b8d3aeb736ac1` | `phase5_plot_metadata.json` `input_manifests.phase4_commit_manifest.artifacts.phase4_run_metadata.json.sha256`; matches `PHASE4_RUN_METADATA_SHA256` |

**Verdict:** the Phase 5B figures were rendered from the same frozen Phase 4 execution as the Phase 5A tables admitted under PR-09 and PR-10. The linkage is cryptographically established, not assumed.

The Phase 5B — Phase 5A lineage is established by the figure catalog's `input_artifacts` column, which names the specific Phase 5A CSV consumed by each figure (for example, "Phase 5A hypergeometric overlap summary (single row)" for figure 3, "Phase 5A 10x10 Spearman matrix" for figure 4). The `phase5_plot_metadata.json` file additionally records the SHA-256 of each Phase 5A input consumed at render time, providing an independent cross-check against the Phase 5A manifest.

---

## 7. Frozen integrity baseline at admission

`python ci/check_frozen_integrity.py` returns `28/28 files match (OK)` on the `pr-11-phase5b-gallery` branch at the time of this admission. No frozen scientific file, DVC pointer, or manifest was touched by the source-inventory work.

---

*End of PR-11 source admission.*