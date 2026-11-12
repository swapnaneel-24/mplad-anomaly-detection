#!/usr/bin/env python3
"""Create synthetic reviewer + viewer users for E2E tests.

Run this BEFORE starting the backend. It connects directly to the
configured PostgreSQL database (via the same Settings the backend
uses) and creates a reviewer and a viewer with the E2E credentials.
Idempotent: if a user already exists, it is left unchanged.

Usage (from the backend/ directory)::

    PEIARS_DATABASE_URL=postgresql+psycopg://... \\
    PEIARS_E2E_USERNAME=reviewer_e2e \\
    PEIARS_E2E_PASSWORD='test-reviewer-password-1234' \\
    PEIARS_E2E_VIEWER_USERNAME=viewer_e2e \\
    PEIARS_E2E_VIEWER_PASSWORD='test-viewer-password-1234' \\
    python ../frontend/playwright/setup-reviewer.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.auth.passwords import hash_password  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.db.session import create_engine, create_session_factory  # noqa: E402
from app.repositories.users import UserRepository  # noqa: E402

_REVIEWER_USERNAME = os.environ.get("PEIARS_E2E_USERNAME", "reviewer_e2e")
_REVIEWER_PASSWORD = os.environ.get("PEIARS_E2E_PASSWORD", "test-reviewer-password-1234")
_VIEWER_USERNAME = os.environ.get("PEIARS_E2E_VIEWER_USERNAME", "viewer_e2e")
_VIEWER_PASSWORD = os.environ.get("PEIARS_E2E_VIEWER_PASSWORD", "test-viewer-password-1234")


def _create_user(session_factory, username: str, password: str, display_name: str, role: str) -> None:
    with session_factory() as session:
        users = UserRepository(session)
        existing = users.get_by_username(username)
        if existing is not None:
            print(f"User {username!r} already exists; leaving unchanged.")
            return
        users.create_user(
            username=username,
            password_hash=hash_password(password),
            display_name=display_name,
            role=role,
        )
        session.commit()
    print(f"User {username!r} ({role}) created successfully.")


def main() -> None:
    settings = Settings()
    if not settings.database_url:
        print("PEIARS_DATABASE_URL is not configured.", file=sys.stderr)
        sys.exit(1)

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    session_factory = create_session_factory(engine)
    try:
        _create_user(session_factory, _REVIEWER_USERNAME, _REVIEWER_PASSWORD, "Reviewer E2E", "reviewer")
        _create_user(session_factory, _VIEWER_USERNAME, _VIEWER_PASSWORD, "Viewer E2E", "viewer")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
