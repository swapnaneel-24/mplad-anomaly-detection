#!/usr/bin/env python3
"""Create a synthetic reviewer user for E2E tests.

Run this BEFORE starting the backend. It connects directly to the
configured PostgreSQL database (via the same Settings the backend
uses) and creates a reviewer with the E2E credentials. Idempotent:
if the user already exists, it exits 0 without modifying it.

Usage (from the backend/ directory)::

    PEIARS_DATABASE_URL=postgresql+psycopg://... \\
    PEIARS_E2E_USERNAME=reviewer_e2e \\
    PEIARS_E2E_PASSWORD='test-reviewer-password-1234' \\
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

_USERNAME = os.environ.get("PEIARS_E2E_USERNAME", "reviewer_e2e")
_PASSWORD = os.environ.get("PEIARS_E2E_PASSWORD", "test-reviewer-password-1234")


def main() -> None:
    settings = Settings()
    if not settings.database_url:
        print("PEIARS_DATABASE_URL is not configured.", file=sys.stderr)
        sys.exit(1)

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    session_factory = create_session_factory(engine)
    try:
        with session_factory() as session:
            users = UserRepository(session)
            existing = users.get_by_username(_USERNAME)
            if existing is not None:
                print(f"Reviewer {_USERNAME!r} already exists; leaving unchanged.")
                return
            users.create_user(
                username=_USERNAME,
                password_hash=hash_password(_PASSWORD),
                display_name="Reviewer E2E",
                role="reviewer",
            )
            session.commit()
    finally:
        engine.dispose()

    print(f"Reviewer {_USERNAME!r} created successfully.")


if __name__ == "__main__":
    main()
