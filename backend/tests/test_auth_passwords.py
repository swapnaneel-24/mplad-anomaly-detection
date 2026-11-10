"""Argon2id password hashing tests (PR-04 §4, AC-04-02). Pure unit tests."""

from __future__ import annotations

import pytest

from app.auth.passwords import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    DUMMY_HASH,
    hash_password,
    verify_dummy_password,
    verify_password,
)


class TestHashFormat:
    def test_hash_uses_argon2id(self):
        h = hash_password("correct horse battery staple")
        assert h.startswith("$argon2id$")

    def test_hash_contains_no_plaintext(self):
        password = "correct horse battery staple"
        h = hash_password(password)
        assert password not in h
        assert len(h) < 100  # encoded hash is compact

    def test_hash_is_salted(self):
        """Two hashes of the same password differ (unique salt per hash)."""
        h1 = hash_password("same-password-input")
        h2 = hash_password("same-password-input")
        assert h1 != h2


class TestVerification:
    def test_correct_password_verifies(self):
        h = hash_password("correct horse battery staple")
        assert verify_password(h, "correct horse battery staple") is True

    def test_wrong_password_fails(self):
        h = hash_password("correct horse battery staple")
        assert verify_password(h, "wrong password") is False

    def test_empty_password_fails(self):
        h = hash_password("correct horse battery staple")
        assert verify_password(h, "") is False

    def test_malformed_hash_fails_cleanly(self):
        assert verify_password("not-a-hash", "whatever") is False
        assert verify_password("", "whatever") is False

    def test_hashed_output_verifies_roundtrip_multiple(self):
        for pw in ("a-password-1", "ünïcode-pässwörd", " " * 8 + "x"):
            h = hash_password(pw)
            assert verify_password(h, pw) is True
            assert verify_password(h, pw + "!") is False


class TestDummyHash:
    def test_dummy_hash_is_argon2id(self):
        assert DUMMY_HASH.startswith("$argon2id$")

    def test_dummy_verification_always_fails(self):
        assert verify_dummy_password("any-password") is False
        assert verify_dummy_password("") is False

    def test_dummy_hash_corresponds_to_documented_non_credential(self):
        """The dummy hash is a well-formed hash of the documented string.

        Any *other* password fails against it, so the equalization path
        can never succeed for a real attempt.
        """
        assert verify_password(
            DUMMY_HASH, "timing-equalization-dummy-not-a-real-credential"
        ) is True
        assert verify_password(DUMMY_HASH, "any-real-attempt") is False
        assert verify_password(DUMMY_HASH, "password") is False


class TestPasswordBounds:
    def test_bounds_are_documented(self):
        assert PASSWORD_MIN_LENGTH == 8
        assert PASSWORD_MAX_LENGTH == 128
