"""Assembly of the versioned ``/api/v1`` API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health, meta, sources

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(meta.router)
api_router.include_router(sources.router)
