# PR-10 — Changed-files patch delivery report

**Status:** Implementation patch prepared; maintainer integration and real-data acceptance **NOT RUN**.

**Patch basis:** User-provided `PEIARS_PR10_changed_files.zip`, corrected and supplemented in this delivery. The source ZIP was prepared in an external sandbox against a historical PR-09 HEAD. This delivery **does not claim** to be rebased, committed, merged, or tested in the maintainer's current `pr-10-phase5a-evidence` checkout.

## Implemented scope

- Independent, fixed trust anchor `TRUSTED_PHASE5_COMMIT_MANIFEST_SHA256` checked before any Layer A cache reuse. The pin `5e8311f2246bf3b8295648fb727d8277edeb340863002109a41ac2dc1dba7d5d` was calculated by CRLF reconstruction of the Phase 5 commit manifest embedded in the supplied project-context bundle. **Its identity against the actual authoritative Git file must be independently checked on the maintainer's checkout before merge.** Do not replace the pin with a hash of modified scientific content.
- DVC payload identity requires MD5, SHA-256, and size to agree on **the same exact byte representation**, accepting either unmodified raw bytes or the Windows CRLF reconstruction of text bytes.
- Phase 5A per-artifact caches re-verify the current trust chain and original artifact identity on every request before reuse, and independently invalidate only affected DVC capabilities.
- Synthetic fixture hashes are supplied through test-local `unittest.mock.patch` of the protocol dependency; production no longer contains `_SYNTHETIC_MANIFEST_OVERRIDE`.
- Added focused read-only `/catalog`, `/uncertainty`, `/agreement`, `/review-policies` routes, preserving compatible earlier Phase 5A routes where applicable.
- `/review-policies` returns **only the four saved disjoint agreement groups**. The previously proposed `/policies` route is kept as a compatibility endpoint with `503 source_not_admitted`; it never computes derived policy precision, recall, or overlap ratios. No fabricated scientific fallback is supplied.
- Existing ResearchPage retains the canonical benchmark and Phase 5A view, with focused catalog/uncertainty/agreement/group integration and per-source missing states.
- Backend/OpenAPI and frontend contract snapshots extended for the four focused routes.

## Checks executed in patch-authoring environment

- Python syntax compilation on changed backend modules and tests: **PASS**.
- Standalone pure-helper checks: synthetic LF payload with CRLF-pinned MD5/SHA-256/size **PASS**; invalid SHA-256 and wrong size **fail closed**.
- ZIP member inventory, exact byte sizes and SHA-256: **PASS** (see `PR10_FILE_MANIFEST.csv`).

## Checks NOT executed here

- Actual repository baseline/rebase verification: **NOT RUN**.
- FastAPI backend pytest with installed project dependencies and real app: **NOT RUN**.
- Frontend TypeScript, ESLint, Vitest and build with installed project node_modules: **NOT RUN**.
- Playwright, Compose, hosted GitHub Actions: **NOT RUN**.
- Windows trusted Phase 5A DVC payload checks (eight artifact families): **NOT RUN — DATA UNAVAILABLE**.
- Full frozen `28/28` checker in the actual maintainer checkout: **NOT RUN**.

Do **not** reuse the coding AI's earlier `690/134/21` passed counts as if they were run on this corrected delivery.

## Required maintainer acceptance

1. Extract and verify the archive, exclude older versions of status/source-admission documents, apply on a branch rooted in the post-PR-09-merge `main` commit, and inspect the diff.
2. Confirm the pinned Phase 5 commit manifest SHA against **actual** Git bytes with the approved Windows CRLF canonicalization, independently of the bundle.
3. Regenerate OpenAPI and TypeScript contracts using the repository's generators and verify drift. Prefer generated files over hand edits on conflicts.
4. Run synthetic regression including cache mutation/restoration, malformed/missing pointers, independent capabilities, and real HTTP access to all four read-only routes.
5. On a trusted Windows environment, verify each materialized Phase 5A CSV against exact DVC and commit-manifest identities, source values and population invariants; do not modify originals.
6. Rerun the frozen integrity checker, full tests, browser E2E and hosted CI. Record actual pass/fail/skip values in the maintainer's **existing** R1 implementation ledger.

**No merge approval is claimed by this patch.**
