"""User repository — typed database operations for local identities.

All queries are parameterized (SQLAlchemy bound parameters); no string
interpolation ever touches SQL with user input.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import User


class DuplicateUsernameError(ValueError):
    """Raised when the normalized username already exists."""

    def __init__(self, username: str) -> None:
        self.username = username
        super().__init__(f"A user with this username already exists.")


class UserRepository:
    """Typed database operations for users."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        display_name: str,
        role: str,
        is_active: bool = True,
    ) -> User:
        """Insert a new user row. Does not commit.

        Raises :class:`DuplicateUsernameError` when the normalized
        username already exists (unique-index violation).
        """
        from sqlalchemy.exc import IntegrityError

        user = User(
            username=username,
            password_hash=password_hash,
            display_name=display_name,
            role=role,
            is_active=is_active,
        )
        self._session.add(user)
        try:
            self._session.flush()
        except IntegrityError as exc:
            if "users_username" in str(getattr(exc, "orig", "")).lower():
                raise DuplicateUsernameError(username) from exc
            raise
        self._session.refresh(user)
        return user

    def get_by_username(self, username: str) -> User | None:
        """Return the user with the normalized ``username`` or ``None``."""
        stmt = select(User).where(User.username == username)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_by_id(self, user_id: str) -> User | None:
        return self._session.get(User, user_id)

    def touch_last_login(self, user_id: str) -> None:
        """Set ``last_login_at`` to now. Does not commit."""
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(last_login_at=datetime.now(timezone.utc))
        )
        self._session.execute(stmt)
