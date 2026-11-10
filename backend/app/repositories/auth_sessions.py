"""Auth-session repository — typed operations for server-side sessions.

Only SHA-256 verifiers are ever stored or compared; the raw browser
token never enters this layer.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import AuthSession


class AuthSessionRepository:
    """Typed database operations for auth sessions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_session(
        self,
        *,
        user_id: str,
        token_hash: str,
        ttl_minutes: int,
    ) -> AuthSession:
        """Insert a new session row with absolute expiration. No commit."""
        now = datetime.now(timezone.utc)
        auth_session = AuthSession(
            user_id=user_id,
            token_hash=token_hash,
            created_at=now,
            expires_at=now + timedelta(minutes=ttl_minutes),
        )
        self._session.add(auth_session)
        self._session.flush()
        self._session.refresh(auth_session)
        return auth_session

    def find_by_token_hash(self, token_hash: str) -> AuthSession | None:
        """Return the session row whose verifier matches, or ``None``."""
        stmt = select(AuthSession).where(AuthSession.token_hash == token_hash)
        return self._session.execute(stmt).scalar_one_or_none()

    def revoke(self, auth_session_id: str) -> None:
        """Set ``revoked_at`` (irreversible at this layer). No commit."""
        stmt = (
            update(AuthSession)
            .where(AuthSession.id == auth_session_id)
            .values(revoked_at=datetime.now(timezone.utc))
        )
        self._session.execute(stmt)

    def touch_last_seen(
        self, auth_session_id: str, *, last_seen_at: datetime
    ) -> None:
        """Update ``last_seen_at`` for activity tracking. No commit."""
        stmt = (
            update(AuthSession)
            .where(AuthSession.id == auth_session_id)
            .values(last_seen_at=last_seen_at)
        )
        self._session.execute(stmt)
