"""``login_throttles`` ORM model — database-backed login abuse resistance (PR-04).

Failed-login throttling keyed by the normalized username. Being
database-backed, the policy is shared across workers/processes, so a
multi-worker deployment cannot silently bypass it (PR-04 §10).

Policy (see :mod:`app.services.auth`):

* after ``auth_lockout_threshold`` consecutive failed logins for the
  same normalized username, the account-key is locked until
  ``locked_until``;
* a locked key fails closed with a generic ``RATE_LIMITED`` response;
* a successful login deletes the throttle row (window resets);
* an expired lock also resets the window.

The key is the normalized username — not the IP — so the throttle
survives IP rotation and applies uniformly. This is deliberately simple;
it is a bounded abuse-resistance safeguard, not a general rate limiter.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

#: Key length: normalized username (<=64) — 64 is sufficient.
_KEY_MAX = 64


class LoginThrottle(Base):
    """Failed-login throttle state for one normalized username."""

    __tablename__ = "login_throttles"

    key: Mapped[str] = mapped_column(
        String(_KEY_MAX),
        primary_key=True,
        doc="Normalized username the throttle applies to.",
    )

    failed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        doc="Consecutive failed-login count within the current window.",
    )

    first_failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp of the first failure in the current window.",
    )

    last_failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp of the most recent failure.",
    )

    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp until which the key is locked (null = unlocked).",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("clock_timestamp()"),
        doc="UTC last modification timestamp.",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"LoginThrottle(key={self.key!r}, failed_count={self.failed_count!r})"
