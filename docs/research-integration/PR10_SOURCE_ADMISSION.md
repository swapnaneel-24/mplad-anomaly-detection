# PR-10 Source Admission — Phase 5A Evidence

**Branch:** `pr-10-phase5a-evidence`
**Date:** 2026-11-15
**Status:** Mandatory pre-implementation gate

---

## 1. Decision

**PARTIALLY ADMITTED (all requested schemas admitted; payload availability conditional).**

| Capability | Decision | Basis |
|---|---|---|
| Phase 5A catalog (metadata, caveats, parameters) | **ADMITTED** | Frozen Git-tracked `results/stream a/phase 5/reproduction/phase5_run_metadata.json`, verified against the Git-tracked `phase5_commit_manifest.json` (which will be pinned to a trusted constant). |
| Bootstrap uncertainty (`phase5_bootstrap_metrics.csv` & `phase5_paired_bootstrap_differences.csv`) | **PARTIALLY ADMITTED (schema admitted; payload conditional)** | Exact schema and checksums established from the commit manifest. Payloads are DVC-backed and **absent** in a clean checkout; runtime serving requires the `.dvc` pointer and manifest verification to pass. |
| Method agreement (`phase5_pairwise_spearman.csv` & `phase5_pairwise_jaccard_1pct.csv`) | **PARTIALLY ADMITTED (schema admitted; payload conditional)** | As above. |
| Review policies (`phase5_multithreshold_agreement.csv` & `phase5_agreement_groups.csv`) | **PARTIALLY ADMITTED (schema admitted; payload conditional)** | As above. Note: The API must **serve the saved `phase5_agreement_groups.csv` directly**, not recompute counts dynamically. |

Pickle payloads and Phase 5B plots (`.png`) remain **BLOCKED** or out of scope for this PR.

---

## 2. Evidence examined

### 2.1 Git-tracked (present in clean checkout)

| File | Git status | Integrity anchor |
|---|---|---|
| `results/stream a/phase 5/reproduction/phase5_run_metadata.json` | tracked | `phase5_commit_manifest.json` SHA-256 (CRLF form) |
| `results/stream a/phase 5/reproduction/phase5_commit_manifest.json` | tracked | Self-consistent on disk, but **must be pinned** in Python code (`TRUSTED_PHASE5_COMMIT_MANIFEST_SHA256`) to establish an independent trust anchor. |

### 2.2 DVC-backed (payloads ABSENT in this environment; `.dvc` pointers tracked)

The following `.csv` payloads are admitted under Layer B (conditionally available):
1. `phase5_bootstrap_metrics.csv`
2. `phase5_paired_bootstrap_differences.csv`
3. `phase5_pairwise_spearman.csv`
4. `phase5_pairwise_jaccard_1pct.csv`
5. `phase5_multithreshold_agreement.csv`
6. `phase5_agreement_groups.csv`
7. *(Note: `phase5_fraud_discovery_curve.csv` is 15MB and its full-schema parsing per request is flagged as an unbounded processing risk. It is admitted, but should have bounded pagination or be deferred.)*

---

## 3. Review Policy Integrity (Crucial Finding G)

The Phase 5A source code (`src/mplad/stream_a/phase5_analysis.py`) confirms that `phase5_agreement_groups.csv` contains the **exact, authoritative saved counts** for the four disjoint partition groups (`Both`, `Run A Only`, `Run B Only`, `Neither`). 

**The PR-10 API must read these saved values directly.** It must not recalculate precision, recall, or workload totals inside the HTTP request path. If derived combinations are needed (e.g., total review budget), they must be explicit additions or clearly marked as derived from the saved group counts.

---

## 4. Consequences for PR-10 implementation

1. **Independent Trust Anchor:** The Phase 5 commit manifest must have a pinned SHA-256 constant (`TRUSTED_PHASE5_COMMIT_MANIFEST_SHA256`) in the backend adapter to prevent self-signed tampering (fixing Finding B).
2. **Layer B Independence:** Each of the 7 DVC payloads must load and cache independently so that if one payload (e.g., the 15MB discovery curve) is missing, the others (like bootstrap metrics) still return 200 (fixing Finding C).
3. **No Synthetic Production Overrides:** Test-specific manifest overrides must be injected via `unittest.mock.patch` in the tests, not exposed as mutable global variables in the production service (fixing Finding D).
4. **Representation-Compatible Verifier:** The `verify_payload_bytes()` helper must check the raw byte size **and** the CRLF-reconstructed byte size to properly validate Windows-produced LF-normalized text files against their CRLF-based `.dvc` pointers (fixing Finding E).