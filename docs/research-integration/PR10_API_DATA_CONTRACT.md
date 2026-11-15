# PR-10 — Focused Phase 5A API data contract

All Phase 5A endpoints are **public GET-only** under `/api/v1/research/phase5a`. They serve frozen, precomputed ULB Stream A evidence, not live predictions, fraud probabilities, or public-programme model results.

| Resource | Evidence returned | Dependencies |
|---|---|---|
| `GET /catalog` | Verified Phase 5A protocol, per-family availability and provenance | Git-backed `phase5_commit_manifest.json`, Phase 5 run metadata, frozen configuration and source trust chain |
| `GET /uncertainty` | Saved bootstrap point estimates / percentile intervals and saved paired `LOF_004 - IF_003` differences | Independently verified bootstrap and paired DVC CSVs; absent one => combined endpoint 503, separate legacy endpoints remain independently usable |
| `GET /agreement` | Saved Spearman and canonical 1% Jaccard matrices | Independently verified two matrix CSVs; absent one => combined endpoint 503, individual matrix routes remain independent |
| `GET /review-policies` | **Direct** disjoint `both`, `if_only`, `lof_only`, `neither` group rows, counts and saved `fraud_proportion` / `recall_contribution` | Independently verified `phase5_agreement_groups.csv` |

The old `/policies` route is retained only as a compatibility route responding with `503 SERVICE_NOT_READY` / `source_not_admitted` pending a separately approved and manifested precomputed policy-aggregate artifact. This route must not compute policy precision, recall or overlap ratios on request.

Independent source availability is preserved: missing bootstrap bytes cannot suppress saved agreement groups. An unavailable required DVC payload returns sanitized HTTP 503 with machine-readable `artifact_missing`; changed digest, size, schema or manifest identity returns 503 `integrity_failed`. The authenticated case API is untouched.

**Provenance:** frozen Git metadata must match its approved trust anchor. DVC `md5` + `size` and Phase 5 `sha256` + `size_bytes` must validate against one identical byte form, either raw or CRLF-reconstructed text, prior to parsing. Cached results are never authorization to skip this verification.

**Scientific claims:** no pickle deserialization, no model fit, no request-driven bootstrap/threshold/flag/score generation. ULB is a credit-card benchmark, not MPLADS/PMGSY. The selected pair is post-hoc. Review budget is a count of records, not computation time.
