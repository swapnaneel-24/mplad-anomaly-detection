"""Pytest configuration for the PEIARS backend tests.

Mirrors the repository's research-test convention: make ``backend/``
importable without package installation by inserting it into ``sys.path``.
The frozen research tree (``tests/`` at the repository root) is untouched
and never collected by this suite.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture()
def test_settings() -> Settings:
    """Isolated, deterministic settings (no ``.env`` / environment reads)."""
    return Settings(
        _env_file=None,
        environment="test",
        cors_origins=["http://test.example"],
        git_commit_sha=None,
        docs_enabled=True,
    )


@pytest.fixture()
def app(test_settings: Settings):
    """Application built from isolated settings and no readiness probes."""
    return create_app(settings=test_settings)


@pytest.fixture()
def client(app) -> TestClient:
    """Synchronous test client over the ASGI app."""
    return TestClient(app)
