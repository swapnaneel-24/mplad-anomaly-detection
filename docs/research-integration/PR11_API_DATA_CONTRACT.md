# PR-11 API Data Contract — Phase 5B Figure Gallery and Traceability

**Branch:** `pr-11-phase5b-gallery` | **Date:** 2026-11-15 | **Status:** Implemented; hosted CI pending push

## 1. Endpoints (/api/v1/research/phase5b, GET-only)
| Method | Path | Purpose |
|---|---|---|
| GET | `/phase5b/catalog` | Verified figure catalog with per-figure integrity, availability, publication state |
| GET | `/phase5b/figures/{figure_no}/image` | Controlled delivery of one verified canonical PNG (gate-gated) |
| GET | `/phase5b/traceability` | Source-native objectives (a)/(b)/(c), RQs RQ1–RQ6, historical companion, reproducibility links |

`{figure_no}` is validated to `1 <= figure_no <= 8` (outside yields 422). No filename/path parameter exists.

## 2. Three Independent Dimensions & Error Contract
- **Integrity:** `verified` | `artifact_missing` | `integrity_failed` | `source_not_admitted`
- **Availability:** `{ available: bool, reason }`
- **Publication:** `{ enabled: bool, reason: publication_not_approved | licensing_unresolved }` (default `phase5b_public_figures_enabled = False` via `PEIARS_PHASE5B_PUBLIC_FIGURES_ENABLED`)
- **Errors:** Gate disabled -> **403** `PUBLICATION_NOT_APPROVED` (checked before reading binary); DVC absent -> **503** `artifact_missing`; digest/PNG invalid -> **503** `integrity_failed`.

## 3. Trust Anchor
`TRUSTED_PHASE5_PLOT_COMMIT_MANIFEST_SHA256 = "e883ce52aa8269d3a841fb32ebcd4a739850a2708bd70cd66dd2acf48be5c549"` (LF-normalized SHA-256 of `phase5_plot_commit_manifest.json`). PNGs are verified as raw bytes (SHA-256 + size vs manifest; MD5 + size vs `.dvc`; PNG signature + IHDR `100 <= dim <= 8000`).