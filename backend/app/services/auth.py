"""Authentication service — login, logout, session validation (PR-04).

Transaction boundaries follow the PR-03 convention: each public method
opens its own session via the injected session factory and commits or
rolls back atomically.

Security properties implemented here:

* **Generic failures** — unknown user, wrong password and disabled
  account all produce the same :class:`AuthenticationError` message;
  usernames are not enumerated, and unknown users still pay one Argon2id
  verification (timing equalization).
* **Database-backed throttling** — the failed-login window is keyed by
  the normalized username and shared across workers; a locked key fails
  closed (:class:`AccountLockedError` → 429).
* **Session fixation prevention** — every successful login creates a
  brand-new session row and token; no pre-login session is ever reused.
* **Server-side expiration** — both the absolute TTL and the idle
  timeout are enforced from database state on every request, regardless
  of the browser cookie.
* **Revocation** — logout sets ``revoked_at``; a revoked session can
  never be validated again.
* **Immediate deactivation** — session validation re-reads the user, so
  a disabled account loses access on its next request; role changes are
  re-evaluated the same way (no stale session permission cache).
* **Bounded writes** — ``last_seen_at`` is refreshed at most every
  :data:`LAST_SEEN_UPDATE_SECONDS` on read-only requests.

No raw token, password or hash is ever logged.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.auth.passwords import verify_dummy_password, verify_password
from app.auth.principals import AuthenticatedPrincipal
from app.auth.roles import Role
from app.auth.tokens import generate_session_token, hash_session_token
from app.core.config import Settings
from app.db.models import User
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.login_throttles import LoginThrottleRepository
from app.repositories.users import UserRepository

#: Refresh ``last_seen_at`` at most every 5 minutes per session to avoid
#: excessive database writes on read-only requests (PR-04 §6).
LAST_SEEN_UPDATE_SECONDS = 300

#: The single, generic authentication-failure message (no enumeration).
GENERIC_AUTH_FAILURE = "Invalid username or password."


class AuthenticationError(Exception):
    """Generic authentication failure (no username enumeration)."""


class AccountLockedError(Exception):
    """The login throttle has locked this username (fail closed)."""


@dataclass(frozen=True)
class LoginResult:
    """Successful login outcome (raw token exists only here and in the cookie)."""

    principal: AuthenticatedPrincipal
    session_token: str
    expires_at: datetime


def normalize_username(raw: str) -> str:
    """Normalize a login identifier: NFKC + casefold + strip.

    The normalized form is the uniqueness key, so ``Alice`` and
    ``alice`` are the same account. Raises ``ValueError`` when the
    normalized value is empty.
    """
    normalized = unicodedata.normalize("NFKC", raw).casefold().strip()
    if not normalized:
        raise ValueError("Username must not be empty.")
    return normalized


class AuthService:
    """Transactional service for authentication and session management."""

    def __init__(self, session_factory, settings: Settings) -> None:
        self._session_factory = session_factory
        self._settings = settings

    # ------------------------------------------------------------------ login
    def login(self, username: str, password: str) -> LoginResult:
        """Authenticate credentials and create a fresh server-side session.

        Raises :class:`AccountLockedError` when throttled (fail closed)
        or :class:`AuthenticationError` for any credential failure.
        """
        normalized = normalize_username(username)

        with self._session_factory() as session:
            throttles = LoginThrottleRepository(session)
            users = UserRepository(session)
            auth_sessions = AuthSessionRepository(session)

            # --- Fail closed on an active lock -----------------------------
            throttle = throttles.get(normalized)
            now = datetime.now(timezone.utc)
            if throttle is not None and throttle.locked_until is not None:
                if throttle.locked_until > now:
                    raise AccountLockedError()
                # Expired lock: reset the window and allow the attempt.
                throttles.reset(normalized)

            # --- Credential verification (timing-equalized) -----------------
            user = users.get_by_username(normalized)
            if user is None:
                # Unknown user: still pay one Argon2id verification.
                verify_dummy_password(password)
                throttles.record_failure(
                    key=normalized,
                    lockout_threshold=self._settings.auth_lockout_threshold,
                    lockout_minutes=self._settings.auth_lockout_minutes,
                )
                session.commit()
                raise AuthenticationError(GENERIC_AUTH_FAILURE)

            if not verify_password(user.password_hash, password):
                throttles.record_failure(
                    key=normalized,
                    lockout_threshold=self._settings.auth_lockout_threshold,
                    lockout_minutes=self._settings.auth_lockout_minutes,
                )
                session.commit()
                raise AuthenticationError(GENERIC_AUTH_FAILURE)

            if not user.is_active:
                # Correct password but disabled account: generic failure,
                # no session, no throttle increment (the credential is
                # valid; lockout would be misleading).
                raise AuthenticationError(GENERIC_AUTH_FAILURE)

            # --- Success: fresh session (fixation prevention) ---------------
            throttles.reset(normalized)
            token = generate_session_token()
            auth_session = auth_sessions.create_session(
                user_id=user.id,
                token_hash=hash_session_token(token),
                ttl_minutes=self._settings.session_ttl_minutes,
            )
            users.touch_last_login(user.id)
            session.commit()

            return LoginResult(
                principal=AuthenticatedPrincipal(
                    user_id=user.id,
                    username=user.username,
                    display_name=user.display_name,
                    role=Role(user.role),
                    is_active=True,
                ),
                session_token=token,
                expires_at=auth_session.expires_at,
            )

    # ------------------------------------------------------------------ logout
    def logout(self, session_token: str) -> None:
        """Revoke the session named by ``session_token`` (idempotent)."""
        token_hash = hash_session_token(session_token)
        with self._session_factory() as session:
            repo = AuthSessionRepository(session)
            auth_session = repo.find_by_token_hash(token_hash)
            if auth_session is not None and auth_session.revoked_at is None:
                repo.revoke(auth_session.id)
                session.commit()

    # ------------------------------------------------------------------ validate
    def validate_session(self, session_token: str) -> AuthenticatedPrincipal | None:
        """Validate a browser session token; return the principal or ``None``.

        Enforces, in order: verifier lookup, revocation, absolute
        expiration, idle timeout and account activation. Refreshes
        ``last_seen_at`` only when it is staler than
        :data:`LAST_SEEN_UPDATE_SECONDS`.
        """
        if not session_token:
            return None
        token_hash = hash_session_token(session_token)

        with self._session_factory() as session:
            repo = AuthSessionRepository(session)
            auth_session = repo.find_by_token_hash(token_hash)
            if auth_session is None or auth_session.revoked_at is not None:
                return None

            now = datetime.now(timezone.utc)
            if auth_session.expires_at <= now:
                return None

            reference = auth_session.last_seen_at or auth_session.created_at
            idle_limit = timedelta(minutes=self._settings.session_idle_timeout_minutes)
            if reference.tzinfo is None:  # defensive: DB is TIMESTAMPTZ
                from datetime import timezone as _tz

                reference = reference.replace(tzinfo=_tz.utc)
            if now - reference > idle_limit:
                return None

            user = session.get(User, auth_session.user_id)
            if user is None or not user.is_active:
                return None

            # Bounded activity write: only when the stored value is stale.
            if (now - reference).total_seconds() >= LAST_SEEN_UPDATE_SECONDS:
                repo.touch_last_seen(auth_session.id, last_seen_at=now)
                session.commit()

            return AuthenticatedPrincipal(
                user_id=user.id,
                username=user.username,
                display_name=user.display_name,
                role=Role(user.role),
                is_active=True,
            )
