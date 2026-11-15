# PR-10 — Acceptance test matrix (corrected patch)

**Status:** Executable test code supplied; project-level suites and Windows real-DVC acceptance not run in this patch-authoring runtime.

| Requirement | Test / evidence | Status |
|---|---|---|
| Trusted Git manifest | Pinned Phase 5 digest; tamper after cached warm-up => 503; restoration => 200 | Tests added; **NOT RUN** in full repository |
| DVC identity | Raw and LF→CRLF candidates must agree on MD5 + SHA-256 + byte size for one form | Pure-helper check PASS; backend tests NOT RUN |
| Independent availability | One absent Phase 5A CSV cannot disable other saved families | Tests included; NOT RUN |
| Synthetic isolation | Test-local patch of protocol dependency, no mutable global production override | Source inspection PASS; tests NOT RUN |
| Focused public routes | `/catalog`, `/uncertainty`, `/agreement`, `/review-policies` | Tests added; NOT RUN |
| Saved groups | `review-policies` only returns source rows and saved ratios, no runtime policy recomputation | Source inspection PASS; tests NOT RUN |
| No private case mutation | GET-only Phase 5A; independent authenticated case API | Not rerun |
| OpenAPI and frontend drift | Re-generate from actual FastAPI app / TS generator in repository | **REQUIRES LOCAL REGENERATION/VERIFICATION** |
| Frozen phase 3–6 artifacts | `python ci/check_frozen_integrity.py` | NOT RUN on maintainer checkout |
| Real Phase 5A DVC | All eight original payloads and source interpretation | NOT RUN — DATA UNAVAILABLE |
| Full frontend/browser/Compose/hosted CI | Existing suites | NOT RUN |

Do not report a passing result based on the old coding-AI delivery (`690` backend, `134` Vitest, `21` E2E). New verification is required after applying this patch to the actual post-merge branch.
