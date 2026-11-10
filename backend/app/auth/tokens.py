"""Opaque session tokens and signed CSRF tokens (PR-04 §6, §8).

All randomness comes from ``secrets`` (the operating-system CSPRNG) —
never ``random``.

Session tokens:

* 256 bits of entropy, URL-safe base64 (43 characters);
* only the SHA-256 hex digest of the token is persisted as the server
  verifier — the raw token exists solely in the HttpOnly cookie;
* comparisons happen through database unique-index lookup of the digest,
  so no string comparison of raw tokens ever occurs.

CSRF tokens (signed double-submit):

* ``{random}.{HMAC-SHA256(secret, random)}``;
* the browser stores the value in a readable (non-HttpOnly) cookie and
  echoes it in the ``X-CSRF-Token`` header;
* the server accepts a request only when header == cookie **and** the
  embedded HMAC signature verifies against the server secret, so an
  attacker who can set a cookie on a subdomain still cannot forge a
  valid token pair;
* HMAC comparison is constant-time.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

#: CSRF header name (documented for the future React client).
CSRF_HEADER_NAME = "X-CSRF-Token"

#: Session-token entropy: 32 bytes → 256 bits.
_SESSION_TOKEN_BYTES = 32

#: CSRF-token entropy: 32 bytes → 256 bits.
_CSRF_TOKEN_BYTES = 32


def generate_session_token() -> str:
    """Generate a fresh opaque session token (256 bits of entropy)."""
    return secrets.token_urlsafe(_SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """Return the SHA-256 hex digest used as the stored verifier."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_csrf_token(secret: str) -> str:
    """Generate a signed double-submit CSRF token.

    Returns ``"{random}:{hmac_hex}"`` where ``hmac_hex`` is the
    HMAC-SHA256 of ``random`` under ``secret``.
    """
    raw = secrets.token_urlsafe(_CSRF_TOKEN_BYTES)
    signature = hmac.new(secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{raw}:{signature}"


def verify_csrf_token(secret: str, value: str) -> bool:
    """Verify the signature of a double-submit CSRF token.

    Constant-time HMAC comparison; malformed values return ``False``
    rather than raising.
    """
    if not isinstance(value, str) or ":" not in value:
        return False
    raw, _, signature = value.rpartition(":")
    if not raw or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
