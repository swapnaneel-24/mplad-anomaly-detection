# PR-08 Adapter Contract

**Baseline:** `831c9b4d23349b57d48828157d68fefde5927f02`
**Branch:** `pr-08-research-readonly`

---

## 1. Source schema

The approved source `phase6-reference-values` serves 18 precomputed
aggregate reference values parsed from the frozen
`src/mplad/stream_a/phase6.py` artifact via AST extraction
(`ast.literal_eval` on the `PHASE6_REFERENCE_VALUES` dict).

| Metric | Value | Type | Description |
|---|---|---|---|
| sample_size | 30000 | int | Rows in the canonical 30k sample |
| fraud_label_count | 47 | int | Positive labels in the sample |
| if003_flagged_count | 300 | int | IF_003 flagged observations (bottom 1%) |
| lof004_flagged_count | 300 | int | LOF_004 flagged observations (bottom 1%) |
| observed_intersection | 107 | int | Observations flagged by both IF_003 and LOF_004 |
| union_size | 493 | int | Observations flagged by either detector |
| both_observation_count | 107 | int | Agreement group: both |
| if_only_observation_count | 193 | int | Agreement group: IF-only |
| lof_only_observation_count | 193 | int | Agreement group: LOF-only |
| neither_observation_count | 29507 | int | Agreement group: neither |
| both_fraud_count | 30 | int | Fraud labels in the Both group |
| if_only_fraud_count | 0 | int | Fraud labels in the IF-only group |
| lof_only_fraud_count | 8 | int | Fraud labels in the LOF-only group |
| neither_fraud_count | 9 | int | Fraud labels in the Neither group |
| spearman_if003_lof004 | 0.3666 | float | Spearman rank correlation |
| jaccard_if003_lof004 | 0.2170 | float | Top-1% Jaccard overlap |
| enrichment_observed_over_expected | 35.67 | float | Hypergeometric enrichment |
| log10_upper_tail_probability | -140.30 | float | Log10 hypergeometric upper tail |

---

## 2. API endpoints

All routes are GET-only (read-only), under `/api/v1/research`, require
authentication (`require_authenticated`), and accept any role
(viewer/reviewer/admin).

| Method | Path | Response | Description |
|---|---|---|---|
| GET | `/api/v1/research/sources` | `ResearchSourceListResponse` | List approved research sources |
| GET | `/api/v1/research/sources/{source_id}` | `ResearchSourceDetail` | Metadata for one source |
| GET | `/api/v1/research/sources/{source_id}/results` | `ResearchResultsResponse` | Precomputed results with provenance |

**Error behavior:**
- Unknown `source_id` → 404 `SOURCE_NOT_FOUND`
- Anonymous request → 401/403
- Mutation verbs (POST/PUT/PATCH/DELETE) → 404/405

---

## 3. Response contracts

### ResearchSourceListResponse
```json
{
  "items": [{ "source_id": "phase6-reference-values", ... }],
  "count": 1
}
```

### ResearchResultsResponse
```json
{
  "source_id": "phase6-reference-values",
  "dataset_id": "ulb-credit-card-fraud-2013",
  "model_methods": ["IsolationForest", "LOF"],
  "results": [{ "metric_name": "sample_size", "value": 30000, ... }],
  "interpretation_principles": ["An anomaly flag is not proof of fraud...", ...],
  "exploratory_caveat": "Exploratory analysis: ...",
  "provenance": {
    "artifact_path": "src/mplad/stream_a/phase6.py",
    "artifact_sha256": "2a9e7d79...",
    "digest_algorithm": "sha-256",
    "canonicalization": "frozen-checker-compatible"
  },
  "limitations": ["ULB benchmark performance must not be assumed to transfer to MPLAD transactions.", ...],
  "is_precomputed": true,
  "is_live_prediction": false
}
```

---

## 4. Validation rules

- The `source_id` is validated against the allowlisted catalog (one
  entry: `phase6-reference-values`). Unknown IDs are rejected.
- The artifact path is fixed and relative (`src/mplad/stream_a/phase6.py`);
  it is never constructed from user input. No path traversal is possible.
- **Trusted integrity verification:** the adapter loads the approved
  SHA-256 digests from `ci/frozen_research_manifest.json` (the same
  manifest used by `ci/check_frozen_integrity.py`). It reads the
  artifact's bytes, normalizes CRLF to LF for text files (retaining raw bytes for binary files), computes their SHA-256, and compares it to the
  approved trusted digest BEFORE parsing. On mismatch, a
  `ResearchIntegrityError` is raised → 503 `SERVICE_NOT_READY`. The
  adapter NEVER serves modified results and NEVER falls back to
  synthetic data.
- **Same-snapshot guarantee:** the SAME verified byte snapshot is used
  for both provenance (SHA-256 reported in the API response) and parsing
  (AST extraction of constants).
- **Supporting artifacts verified:** `phase5_analysis.py` and
  `config.py` are also verified against the frozen manifest before
  their bytes are parsed. Their verified digests are reported in the
  `supporting_artifacts` field of the source detail response.
- **Startup safety:** all file reading and verification is lazy — it
  happens on the first research request, not at module import time. If
  the frozen artifacts are missing, the module imports successfully and
  the FastAPI application starts normally. The research API returns a
  sanitized 503 only when a research endpoint is actually called.
- **Bounded cache-integrity policy:** the cache stores both the parsed
  constants and the verified digests of the three artifacts at parse
  time. On every request, the adapter re-reads the artifact files,
  re-computes their digests, and compares to the cached digests. If all
  match, the cached parsed constants are reused (no AST reprocessing).
  If any mismatch, the cache is invalidated and a 503 is returned. If
  the artifacts are later restored, the next request re-verifies against
  the manifest and recovers without restart. No reliance on modification
  time alone — the digest is the proof of content integrity.
- **Windows digest compatibility:** the adapter uses the SAME
  canonicalization as `ci/check_frozen_integrity.py`: text files (no
  null bytes) have CRLF replaced with LF before hashing; binary files
  are hashed as raw bytes. This ensures digests match the frozen
  manifest on both Linux (LF) and Windows (CRLF after git checkout).
  Windows 11 verification NOT RUN in this sandbox; the maintainer should
  execute `python ci/check_frozen_integrity.py` on Windows 11 to verify.
- The frozen constants are parsed via `ast.literal_eval` (no code
  execution). F-strings and function calls are handled specially
  (reconstructed from parsed components, not executed). Reconstructed
  values (`threshold_rule_label`, `phase3_canonical_run_ids`) are
  clearly documented as reconstructed, not verbatim frozen constants.
- All numeric values are finite (no NaN/Infinity).
- No synthetic fallback: if the source is unavailable or corrupted,
  the API returns a sanitized error (503), never synthetic data.

---

## 5. RBAC

- Reuses the existing `require_authenticated` dependency.
- All roles (viewer, reviewer, admin) have read access.
- No new RBAC role is introduced.
- No mutation endpoints exist on the research API.

---

## 6. Deployment assumptions

The frozen `src/mplad/stream_a/phase6.py` file is part of the
repository source tree. The adapter reads it relative to the repository
root. No additional data files, model artifacts, or dataset downloads
are required.

The adapter does NOT require numpy, pandas, scikit-learn, or any
research dependency to be installed in the backend environment. The
AST-based parsing uses only the Python standard library (`ast`,
`hashlib`, `json`, `pathlib`).

**Deployment verification not yet executed:** whether every container
image (Docker, Compose, CI) contains the frozen research directory has
NOT been independently verified. The maintainer should verify this on a
Docker-equipped environment. If the frozen artifacts are absent from a
container, the research API returns a sanitized 503; all other
application endpoints remain operational.
