"""Assembly of the versioned ``/api/v1`` API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    benchmark,
    cases,
    health,
    meta,
    phase5a,
    phase5b,
    research,
    sources,
    workbench,
    synthetic,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(meta.router)
api_router.include_router(sources.router)
api_router.include_router(workbench.router)
api_router.include_router(synthetic.router)
api_router.include_router(cases.router)
api_router.include_router(auth.router)
api_router.include_router(research.router)
# PR-09: canonical ten-run IF/LOF benchmark operations (read-only), mounted
# under /api/v1/research/benchmark on the same research API surface.
api_router.include_router(benchmark.router)
# PR-10: Phase 5A uncertainty/agreement/review-policy evidence (read-only),
# mounted under /api/v1/research/phase5a on the same research API surface.
api_router.include_router(phase5a.router)
# PR-11: Phase 5B figure gallery and objective traceability (read-only),
# mounted under /api/v1/research/phase5b on the same research API surface.
api_router.include_router(phase5b.router)
