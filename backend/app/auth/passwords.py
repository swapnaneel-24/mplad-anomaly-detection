"""Argon2id password hashing and verification (PR-04 §4, §10).

Uses ``argon2-cffi`` with its hardened defaults (Argon2id, t=3, m=64 MiB,
p=4) — a proven library, not custom cryptography.

Timing side-channel resistance for unknown usernames: when a login
attempt names a user that does not exist, the service still runs
:func:`verify_password` against the embedded :data:`DUMMY_HASH` so that
both failure paths perform one Argon2id verification. The dummy hash is
a hash of a non-credential string; it is not a secret and discloses
nothing.

Input policy (deliberately minimal, NIST-SP-800-63B-flavoured):

* passwords: 8–128 characters, no composition rules;
* the bound prevents Argon2id DoS via very large inputs.

Plaintext or reversibly encrypted passwords are never stored, and raw
passwords never appear in logs or error messages.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

#: Password input bounds.
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

#: A hardcoded Argon2id hash of a non-credential string. Used solely to
#: equalize timing when the submitted username does not exist. Not a
#: secret — it corresponds to no usable credential.
DUMMY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$D74AOzFVbZehwFCxaU4XcQ$"
    "hYWeZdiz0GNZRjiOXs95+Asg0neAbpMrv6rwTDBWfjE"
)

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a password with Argon2id and return the encoded hash."""
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    """Verify ``password`` against an Argon2id ``stored_hash``.

    Returns ``False`` for any mismatch or malformed hash — it never
    raises for a wrong password and never logs the password.
    """
    try:
        return _hasher.verify(stored_hash, password)
    except VerifyMismatchError:
        return False
    except InvalidHashError:
        return False


def verify_dummy_password(password: str) -> bool:
    """Run a verification against the dummy hash (always False).

    Used for unknown-username login attempts to equalize timing.
    """
    return verify_password(DUMMY_HASH, password)
