"""Token and CSRF-token tests (PR-04 §6, §8). Pure unit tests."""

from __future__ import annotations

import re
import secrets

from app.auth.tokens import (
    CSRF_HEADER_NAME,
    generate_csrf_token,
    generate_session_token,
    hash_session_token,
    verify_csrf_token,
)

_SECRET = "unit-test-secret-" + "x" * 40
_OTHER_SECRET = "other-secret-" + "y" * 40


class TestSessionTokens:
    def test_token_is_url_safe_base64(self):
        token = generate_session_token()
        assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token), token

    def test_tokens_are_unique(self):
        tokens = {generate_session_token() for _ in range(64)}
        assert len(tokens) == 64

    def test_token_has_256_bits_of_entropy(self):
        # 43 url-safe base64 chars = 32 bytes = 256 bits.
        token = generate_session_token()
        decoded = __import__("base64").urlsafe_b64decode(token + "=" * (4 - len(token) % 4))
        assert len(decoded) == 32

    def test_hash_is_sha256_hex(self):
        token = generate_session_token()
        digest = hash_session_token(token)
        assert re.fullmatch(r"[0-9a-f]{64}", digest)
        # Deterministic.
        assert hash_session_token(token) == digest

    def test_hash_does_not_reveal_token(self):
        token = generate_session_token()
        assert token not in hash_session_token(token)

    def test_different_tokens_hash_differently(self):
        assert hash_session_token(generate_session_token()) != hash_session_token(
            generate_session_token()
        )


class TestCsrfTokens:
    def test_generated_token_verifies(self):
        token = generate_csrf_token(_SECRET)
        assert verify_csrf_token(_SECRET, token) is True

    def test_wrong_secret_fails(self):
        token = generate_csrf_token(_SECRET)
        assert verify_csrf_token(_OTHER_SECRET, token) is False

    def test_tampered_payload_fails(self):
        token = generate_csrf_token(_SECRET)
        raw, _, sig = token.rpartition(":")
        tampered = f"{raw}x:{sig}"
        assert verify_csrf_token(_SECRET, tampered) is False

    def test_tampered_signature_fails(self):
        token = generate_csrf_token(_SECRET)
        raw, _, sig = token.rpartition(":")
        tampered = f"{raw}:{sig[:-1]}{'0' if sig[-1] != '0' else '1'}"
        assert verify_csrf_token(_SECRET, tampered) is False

    def test_malformed_values_fail_cleanly(self):
        for bad in ("", "no-colon", ":", "a:", ":b", None):
            assert verify_csrf_token(_SECRET, bad) is False  # type: ignore[arg-type]

    def test_unsigned_value_fails(self):
        """A random value without a valid signature is rejected."""
        assert verify_csrf_token(_SECRET, secrets.token_urlsafe(32)) is False

    def test_tokens_are_unique(self):
        tokens = {generate_csrf_token(_SECRET) for _ in range(32)}
        assert len(tokens) == 32

    def test_header_name_is_documented(self):
        assert CSRF_HEADER_NAME == "X-CSRF-Token"
