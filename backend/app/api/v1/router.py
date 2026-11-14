"""Assembly of the versioned ``/api/v1`` API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, cases, health, meta, research, sources, synthetic

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(meta.router)
api_router.include_router(sources.router)
api_router.include_router(synthetic.router)
api_router.include_router(cases.router)
api_router.include_router(auth.router)
api_router.include_router(research.router)
