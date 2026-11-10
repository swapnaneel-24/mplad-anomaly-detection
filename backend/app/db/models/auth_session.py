"""``auth_sessions`` ORM model — server-side session persistence (PR-04).

Opaque, cryptographically random session tokens are issued to the browser
in a secure cookie; only a SHA-256 **hash** of the token (the verifier)
is stored here. The raw token is never persisted, never logged, and never
returned in response JSON.

Server-side validation on every authenticated request checks:

* the token verifier matches a session row (unique index);
* ``revoked_at`` is NULL (logout revocation is irreversible);
* ``expires_at`` is in the future (absolute expiration);
* the idle-timeout window based on ``last_seen_at``/``created_at`` is
  not exceeded (inactivity expiration);
* the owning user is still active (deactivation takes effect
  immediately on existing sessions).

Database identity sequences are **not** assumed to be gap-free, and
session timestamps alone provide no security guarantee — validity is
always decided by the server-side checks above.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

#: SHA-256 hex digest length (the stored token verifier).
_TOKEN_HASH_MAX = 64


class AuthSession(Base):
    """A server-side session record for an authenticated user."""

    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        doc="Opaque session-record identifier (not the browser token).",
    )

    user_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key to users.id.",
    )

    #: SHA-256 hex digest of the 256-bit browser token. UNIQUE index
    #: makes verifier lookup safe and fast; the raw token is never stored.
    token_hash: Mapped[str] = mapped_column(
        String(_TOKEN_HASH_MAX),
        nullable=False,
        unique=True,
        index=True,
        doc="SHA-256 verifier of the opaque session token (never the raw token).",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("clock_timestamp()"),
        doc="UTC session creation timestamp (server-generated).",
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        doc="Absolute UTC session expiration (server-enforced).",
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC last-activity timestamp (updated at most every few minutes).",
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC revocation timestamp; a revoked session can never be reused.",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"AuthSession(id={self.id!r}, user_id={self.user_id!r})"
