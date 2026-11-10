"""User model and repository tests (real PostgreSQL, PR-04 §4, §16)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DataError, IntegrityError

from app.auth.passwords import hash_password
from app.db.models import User
from app.repositories.users import DuplicateUsernameError, UserRepository
from app.services.auth import normalize_username


@pytest.fixture(autouse=True)
def _clean_auth_tables(db_session_factory):
    """Reset the auth tables before each test (shared session DB)."""
    from tests.conftest import _truncate_auth_tables

    _truncate_auth_tables(db_session_factory)


class TestUserCreation:
    def test_create_user_with_argon2id_hash(self, db_session_factory):
        with db_session_factory() as session:
            repo = UserRepository(session)
            user = repo.create_user(
                username="alice",
                password_hash=hash_password("correct-horse-battery-staple"),
                display_name="Alice Example",
                role="reviewer",
            )
            session.commit()
            assert user.password_hash.startswith("$argon2id$")
            assert user.is_active is True
            assert user.last_login_at is None
            assert user.id
            uuid.UUID(user.id)  # valid UUID

    def test_timestamps_are_utc(self, db_session_factory):
        with db_session_factory() as session:
            repo = UserRepository(session)
            user = repo.create_user(
                username="bob",
                password_hash=hash_password("another-password-123"),
                display_name="Bob",
                role="viewer",
            )
            session.commit()
            assert user.created_at is not None
            assert user.created_at.tzinfo is not None
            assert user.updated_at.tzinfo is not None


class TestUsernameUniqueness:
    def test_duplicate_normalized_username_rejected(self, db_session_factory):
        with db_session_factory() as session:
            repo = UserRepository(session)
            repo.create_user(
                username="alice",
                password_hash=hash_password("correct-horse-battery-staple"),
                display_name="Alice",
                role="reviewer",
            )
            session.commit()

        with db_session_factory() as session:
            repo = UserRepository(session)
            with pytest.raises(DuplicateUsernameError):
                repo.create_user(
                    username="alice",  # identical normalized form
                    password_hash=hash_password("another-password-123"),
                    display_name="Alice 2",
                    role="viewer",
                )

    def test_casefold_collision_rejected(self, db_session_factory):
        """'Alice' and 'ALICE' normalize to the same uniqueness key."""
        with db_session_factory() as session:
            repo = UserRepository(session)
            repo.create_user(
                username=normalize_username("Alice"),
                password_hash=hash_password("correct-horse-battery-staple"),
                display_name="Alice",
                role="reviewer",
            )
            session.commit()

        with db_session_factory() as session:
            repo = UserRepository(session)
            with pytest.raises(DuplicateUsernameError):
                repo.create_user(
                    username=normalize_username("ALICE"),
                    password_hash=hash_password("another-password-123"),
                    display_name="Alice caps",
                    role="viewer",
                )

    def test_get_by_username_matches_normalized(self, db_session_factory):
        with db_session_factory() as session:
            repo = UserRepository(session)
            repo.create_user(
                username=normalize_username("Carol"),
                password_hash=hash_password("correct-horse-battery-staple"),
                display_name="Carol",
                role="admin",
            )
            session.commit()
            found = repo.get_by_username("carol")
            assert found is not None
            assert found.username == "carol"
            assert found.role == "admin"


class TestRoleConstraint:
    def test_invalid_role_rejected_by_check(self, db_session_factory):
        with db_session_factory() as session:
            user = User(
                username="eve",
                password_hash=hash_password("correct-horse-battery-staple"),
                display_name="Eve",
                role="superuser",  # not in the vocabulary
            )
            session.add(user)
            with pytest.raises(IntegrityError):
                session.commit()


class TestRequiredFields:
    @pytest.mark.parametrize(
        "overrides",
        [
            {"username": None},
            {"password_hash": None},
            {"display_name": None},
            {"role": None},
        ],
    )
    def test_missing_required_fields_rejected(self, db_session_factory, overrides):
        with db_session_factory() as session:
            values = dict(
                username="frank",
                password_hash=hash_password("correct-horse-battery-staple"),
                display_name="Frank",
                role="viewer",
            )
            values.update(overrides)
            session.add(User(**values))
            with pytest.raises(IntegrityError):
                session.commit()


class TestFieldBounds:
    def test_oversized_username_rejected(self, db_session_factory):
        with db_session_factory() as session:
            session.add(User(
                username="a" * 65,
                password_hash=hash_password("correct-horse-battery-staple"),
                display_name="X",
                role="viewer",
            ))
            with pytest.raises((DataError, IntegrityError)):
                session.commit()

    def test_oversized_display_name_rejected(self, db_session_factory):
        with db_session_factory() as session:
            session.add(User(
                username="grace",
                password_hash=hash_password("correct-horse-battery-staple"),
                display_name="x" * 121,
                role="viewer",
            ))
            with pytest.raises((DataError, IntegrityError)):
                session.commit()


class TestNoPlaintextPasswords:
    def test_password_column_stores_only_argon2id(self, db_session_factory):
        with db_session_factory() as session:
            rows = session.execute(text("SELECT password_hash FROM users")).fetchall()
            for (ph,) in rows:
                assert ph.startswith("$argon2$")


class TestNormalizeUsername:
    def test_strips_and_casefolds(self):
        assert normalize_username("  Alice  ") == "alice"

    def test_nfkc_normalization(self):
        # Fullwidth ASCII 'Ａ' (U+FF21) NFKC-normalizes to 'A' → 'a'.
        assert normalize_username("Ａlice") == "alice"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            normalize_username("   ")
