"""Reproducibility contract: the installed dependency versions match the lock.

Independent review found that the committed OpenAPI snapshot drifted when
the backend was installed under newer FastAPI/Pydantic versions than the
pinned lock.  The snapshot is only reproducible under the exact versions
in ``backend/requirements-lock.txt``; regenerating it against arbitrary
versions would silently publish a contract that does not match the
locked runtime.

These tests make the reproducibility contract explicit and machine-checked:

* The installed versions of the core web framework packages match the
  pinned lock exactly.
* The Python interpreter is in the supported major.minor range (3.12).
* The lock file itself pins every package the backend depends on.

If a reviewer installs different versions, the version-mismatch test
fails *loudly* — the fix is to install the locked versions, not to
regenerate the snapshot against the mismatched ones.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = BACKEND_ROOT / "requirements-lock.txt"

#: Packages whose installed version must match the lock exactly for the
#: OpenAPI snapshot and the PostgreSQL integration tests to be reproducible.
#: PR-02: web framework + test client.
#: PR-03: persistence stack (SQLAlchemy, Alembic, psycopg) + pgserver.
#: PR-04: authentication (argon2-cffi).
_PINNED_PACKAGES = (
    "fastapi",
    "pydantic",
    "pydantic-settings",
    "starlette",
    "httpx",
    "sqlalchemy",
    "alembic",
    "psycopg",
    "psycopg-binary",
    "pgserver",
    "argon2-cffi",
)

#: Major.minor Python versions supported by the backend (PR-02 + PR-03).
_SUPPORTED_PYTHON = (3, 12)


def _parse_lock() -> dict[str, str]:
    """Parse requirements-lock.txt into a {package: version} mapping."""
    text = LOCK_PATH.read_text(encoding="utf-8")
    versions: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)==([^;\s]+)", stripped)
        if match:
            name = match.group(1).lower().replace("_", "-")
            versions[name] = match.group(2)
    return versions


class TestPythonVersion:
    def test_supported_python_version(self):
        major, minor = sys.version_info[:2]
        assert (major, minor) == _SUPPORTED_PYTHON, (
            f"backend targets Python {_SUPPORTED_PYTHON[0]}.{_SUPPORTED_PYTHON[1]}; "
            f"running on {major}.{minor}. Install the supported interpreter "
            "before regenerating the OpenAPI snapshot."
        )


class TestLockPinsCorePackages:
    def test_lock_file_exists(self):
        assert LOCK_PATH.exists(), f"missing lock file: {LOCK_PATH}"

    def test_lock_pins_every_core_package(self):
        locked = _parse_lock()
        missing = [pkg for pkg in _PINNED_PACKAGES if pkg not in locked]
        assert not missing, f"lock does not pin: {missing}"


class TestInstalledVersionsMatchLock:
    """The installed framework versions must match the lock exactly.

    If this fails, install the locked versions with
    ``pip install -r backend/requirements-lock.txt`` and re-run. Do **not**
    regenerate the OpenAPI snapshot under mismatched versions.
    """

    @pytest.fixture(scope="class")
    def locked_versions(self) -> dict[str, str]:
        return _parse_lock()

    @pytest.mark.parametrize("package", _PINNED_PACKAGES)
    def test_installed_matches_lock(self, locked_versions, package):
        import importlib.metadata as md

        try:
            installed = md.distribution(package).version
        except md.PackageNotFoundError:
            installed = None
        locked = locked_versions[package]
        assert installed is not None, f"package {package} is not installed"
        assert installed == locked, (
            f"{package}: installed {installed} != locked {locked}. "
            "Install the locked versions: pip install -r backend/requirements-lock.txt"
        )
