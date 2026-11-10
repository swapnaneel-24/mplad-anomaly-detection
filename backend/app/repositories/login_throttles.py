"""Login-throttle repository — database-backed failed-login tracking.

The increment uses a PostgreSQL ``INSERT ... ON CONFLICT DO UPDATE`` so
the count is advanced atomically even when concurrent workers record
failures for the same username simultaneously (multi-worker safe).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import LoginThrottle


class LoginThrottleRepository:
    """Typed database operations for login throttles."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, key: str) -> LoginThrottle | None:
        stmt = select(LoginThrottle).where(LoginThrottle.key == key)
        return self._session.execute(stmt).scalar_one_or_none()

    def record_failure(
        self,
        *,
        key: str,
        lockout_threshold: int,
        lockout_minutes: int,
    ) -> None:
        """Atomically increment the failure count; lock when the
        threshold is reached. No commit.

        Uses an upsert so concurrent workers cannot lose counts. The
        post-increment count is re-read with a Core SELECT (bypassing
        the ORM identity map, which would otherwise serve the stale
        pre-upsert value) and the lock window is set with a Core UPDATE.
        """
        now = datetime.now(timezone.utc)
        stmt = pg_insert(LoginThrottle)
        stmt = stmt.values(
            key=key,
            failed_count=1,
            first_failed_at=now,
            last_failed_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[LoginThrottle.key],
            set_={
                "failed_count": LoginThrottle.failed_count + 1,
                "last_failed_at": now,
                "updated_at": now,
            },
        )
        self._session.execute(stmt)

        # Re-read the incremented count with a Core scalar SELECT so the
        # ORM identity map cannot mask the in-transaction change.
        current_count = self._session.execute(
            select(LoginThrottle.failed_count).where(LoginThrottle.key == key)
        ).scalar_one()

        if current_count >= lockout_threshold:
            self._session.execute(
                update(LoginThrottle)
                .where(LoginThrottle.key == key)
                .values(
                    locked_until=now + timedelta(minutes=lockout_minutes),
                    updated_at=now,
                )
            )

    def reset(self, key: str) -> None:
        """Delete the throttle row (successful login or expired lock)."""
        stmt = delete(LoginThrottle).where(LoginThrottle.key == key)
        self._session.execute(stmt)
