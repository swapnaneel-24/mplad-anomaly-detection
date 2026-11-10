"""``users`` ORM model — local application identities (PR-04).

Persistent, PostgreSQL-backed user accounts for the PEIARS application.

Security properties:

* ``password_hash`` stores an **Argon2id** encoded hash (via
  :mod:`app.auth.passwords`). Plaintext or reversibly encrypted
  passwords are never stored.
* ``username`` is the *normalized* login identifier (NFKC + casefold +
  strip, ASCII-restricted charset); a UNIQUE constraint rejects duplicate
  normalized usernames at the database boundary.
* ``role`` is the server-side authorization role (viewer/reviewer/admin),
  enforced by a CHECK constraint and always read from the database —
  never from request payloads.
* ``is_active`` gates every authenticated operation; disabled accounts
  fail closed.
* No default administrator is created at application startup; the first
  user is created through the explicitly documented
  ``backend/scripts/create_admin.py`` CLI.

The stable ``id`` (UUID) — not the mutable username — is the canonical
actor reference recorded in PR-03 case-event history.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

#: Bounded lengths (PR-04 §4: bound usernames, display names, hashes).
_USERNAME_MAX = 64
_PASSWORD_HASH_MAX = 512
_DISPLAY_NAME_MAX = 120

_ROLE_CHECK = "role IN ('viewer','reviewer','admin')"


class User(Base):
    """A local application identity."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        doc="UUID primary key, server-generated. Canonical actor reference.",
    )

    #: Normalized login identifier: NFKC + casefold + strip, charset
    #: [a-z0-9._-], length 3-64. Uniqueness enforced by the UNIQUE index.
    username: Mapped[str] = mapped_column(
        String(_USERNAME_MAX),
        nullable=False,
        index=True,
        unique=True,
        doc="Normalized, unique login identifier.",
    )

    #: Argon2id encoded hash (never plaintext; never in public responses).
    password_hash: Mapped[str] = mapped_column(
        String(_PASSWORD_HASH_MAX),
        nullable=False,
        doc="Argon2id password hash. Never exposed in any response model.",
    )

    display_name: Mapped[str] = mapped_column(
        String(_DISPLAY_NAME_MAX),
        nullable=False,
        doc="Limited human-readable display name (Unicode-safe).",
    )

    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        doc="Server-side role: viewer | reviewer | admin (see CHECK constraint).",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        doc="Account activation status; disabled accounts fail closed.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("clock_timestamp()"),
        doc="UTC creation timestamp (server-generated).",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("clock_timestamp()"),
        doc="UTC last modification timestamp (server-generated).",
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp of the most recent successful login (nullable).",
    )

    __table_args__ = (
        CheckConstraint(_ROLE_CHECK, name="users_role_enum"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"User(id={self.id!r}, username={self.username!r}, role={self.role!r})"
