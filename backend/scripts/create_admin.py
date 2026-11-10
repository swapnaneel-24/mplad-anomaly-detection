"""Administrator bootstrap CLI (PR-04 §11).

Creates the first legitimate user — a server-side administrator —
through an explicit, narrowly scoped offline command.

Guarantees:

* No hardcoded default username or password.
* No publicly accessible bootstrap endpoint (this is a CLI, run by a
  trusted operator on the server).
* No automatic admin creation during server startup (nothing in the
  application creates users).
* Credentials are obtained interactively (hidden prompt) or from the
  ``PEIARS_BOOTSTRAP_ADMIN_PASSWORD`` environment variable — never from
  committed configuration files.
* The password is never displayed after creation and never logged.
* Repeated bootstrap for an existing username is refused
  (duplicate normalized usernames are rejected).
* The command refuses to run without a configured database URL.

Later user provisioning (viewer/reviewer accounts, role changes) will
be handled by an administrator CLI/API in a separately approved
milestone; this command intentionally creates only administrators.

Usage (from ``backend/``)::

    # Interactive (hidden password prompt):
    python scripts/create_admin.py --username admin --display-name "Administrator"

    # Non-interactive (secret from the process environment):
    PEIARS_DATABASE_URL=postgresql+psycopg://... \\
    PEIARS_BOOTSTRAP_ADMIN_PASSWORD='...' \\
    python scripts/create_admin.py --username admin --display-name "Administrator"

    # Then apply migrations first if needed:
    #   alembic upgrade head
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import unicodedata
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.auth.passwords import (  # noqa: E402
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    hash_password,
)
from app.core.config import Settings  # noqa: E402
from app.db.session import create_engine, create_session_factory  # noqa: E402
from app.repositories.users import DuplicateUsernameError, UserRepository  # noqa: E402

#: The environment variable accepted for non-interactive bootstrapping.
PASSWORD_ENV_VAR = "PEIARS_BOOTSTRAP_ADMIN_PASSWORD"

_USERNAME_MIN = 3
_USERNAME_MAX = 64
_DISPLAY_NAME_MAX = 120


def _normalize_username(raw: str) -> str:
    normalized = unicodedata.normalize("NFKC", raw).casefold().strip()
    if not (_USERNAME_MIN <= len(normalized) <= _USERNAME_MAX):
        raise SystemExit(
            f"Username must be {_USERNAME_MIN}-{_USERNAME_MAX} characters after normalization."
        )
    return normalized


def _validate_display_name(raw: str) -> str:
    display = raw.strip()
    if not display or len(display) > _DISPLAY_NAME_MAX:
        raise SystemExit(
            f"Display name must be 1-{_DISPLAY_NAME_MAX} characters after trimming."
        )
    if any(unicodedata.category(ch).startswith("C") for ch in display):
        raise SystemExit("Display name must not contain control characters.")
    return display


def _obtain_password() -> str:
    env_password = os.environ.get(PASSWORD_ENV_VAR)
    if env_password:
        password = env_password
    else:
        password = getpass.getpass("Password for the new administrator: ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            raise SystemExit("Passwords do not match; nothing was created.")
    if not (PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH):
        raise SystemExit(
            f"Password must be {PASSWORD_MIN_LENGTH}-{PASSWORD_MAX_LENGTH} characters."
        )
    return password


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create the first PEIARS administrator (offline bootstrap)."
    )
    parser.add_argument("--username", required=True, help="Login identifier.")
    parser.add_argument("--display-name", required=True, help="Human-readable name.")
    args = parser.parse_args()

    username = _normalize_username(args.username)
    display_name = _validate_display_name(args.display_name)
    password = _obtain_password()

    settings = Settings()
    if not settings.database_url:
        raise SystemExit(
            "PEIARS_DATABASE_URL is not configured. Set it in the environment "
            "or the uncommitted .env file, and run `alembic upgrade head` first."
        )

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    session_factory = create_session_factory(engine)

    try:
        with session_factory() as session:
            users = UserRepository(session)
            if users.get_by_username(username) is not None:
                raise SystemExit(
                    f"Refusing to bootstrap: a user with username "
                    f"{username!r} already exists."
                )
            users.create_user(
                username=username,
                password_hash=hash_password(password),
                display_name=display_name,
                role="admin",
            )
            session.commit()
    except DuplicateUsernameError:
        # Race with a concurrent bootstrap; the unique index refused it.
        raise SystemExit(
            f"Refusing to bootstrap: username {username!r} was created concurrently."
        )
    finally:
        engine.dispose()

    # Sanitized confirmation: no password, no hash, no connection details.
    print(f"Administrator {username!r} created successfully.")
    print(
        "You can now start the API and log in via POST /api/v1/auth/login "
        "(remember to fetch a CSRF token first: GET /api/v1/auth/csrf)."
    )


if __name__ == "__main__":
    main()
