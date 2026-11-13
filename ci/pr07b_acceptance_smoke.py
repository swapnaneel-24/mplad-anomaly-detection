#!/usr/bin/env python3
"""PR-07B acceptance smoke check — reproducibility verifier.

A single-command, standard-library-only check that the PEIARS repository
at the current commit is in a reproducible state for PR-07B acceptance.
Runs the cheapest deterministic checks that a maintainer can execute on
Linux, Windows 11, or CI before the full suite, and prints a summary
table with PASS/FAIL for each.

Checks performed (each independently exit-failing):

  1. Python interpreter is CPython 3.12.x (the documented supported
     runtime; the dependency lock is pinned to 3.12).
  2. Node.js is installed and at least version 22 (the documented
     supported runtime for the frontend toolchain).
  3. ``backend/requirements-lock.txt`` exists (the pinned backend
     transitive freeze).
  4. ``frontend/package-lock.json`` exists (the pinned frontend
     dependency lock; ``npm ci`` requires it).
  5. ``ci/frozen_research_manifest.json`` exists (the SHA-256 manifest
     for the 28 frozen research artifacts).
  6. The frozen research integrity check passes (``ci/check_frozen_integrity.py``).
  7. The frontend OpenAPI contract has no drift (``npm run openapi:check``).

This script does NOT run the full backend pytest, frontend Vitest, or
Playwright E2E suites — those are the maintainer's responsibility via
the documented commands in ``docs/acceptance/PR07B_WINDOWS_RUNBOOK.md``
and ``docs/acceptance/PR07B_COMPOSE_RUNBOOK.md``. It only verifies the
fast reproducibility preconditions.

Usage (from the repository root):

  python3.12 ci/pr07b_acceptance_smoke.py

Exit codes:
  0 — every smoke check passed.
  1 — one or more checks failed (sanitized details printed).

The script is read-only with respect to the repository: it does not
modify any tracked file, does not write to the working tree, and does
not acquire production credentials. It shells out to ``npm`` and to
``ci/check_frozen_integrity.py`` only.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_PY_MAJOR = 3
EXPECTED_PY_MINOR = 12


def _check_python_version() -> tuple[bool, str]:
    """Verify the active interpreter is CPython 3.12.x."""
    info = sys.implementation
    version = sys.version_info
    if info.name != "cpython":
        return False, f"not CPython (got {info.name})"
    if version.major != EXPECTED_PY_MAJOR or version.minor != EXPECTED_PY_MINOR:
        return False, (
            f"expected Python {EXPECTED_PY_MAJOR}.{EXPECTED_PY_MINOR}.x, "
            f"got {version.major}.{version.minor}.{version.micro}"
        )
    return True, f"CPython {version.major}.{version.minor}.{version.micro}"


def _check_node_version() -> tuple[bool, str]:
    """Verify Node.js is installed and at least version 22."""
    try:
        out = subprocess.check_output([shutil.which("node") or "node", "--version"], stderr=subprocess.STDOUT, text=True)
    except FileNotFoundError:
        return False, "node executable not found on PATH"
    except subprocess.CalledProcessError as exc:
        return False, f"node --version failed: {exc.output.strip()}"
    raw = out.strip()  # e.g. "v22.11.0"
    if not raw.startswith("v"):
        return False, f"unexpected node version string: {raw!r}"
    digits = raw[1:].split(".")
    try:
        major = int(digits[0])
    except (ValueError, IndexError):
        return False, f"could not parse node major version from {raw!r}"
    if major < 22:
        return False, f"Node major version {major} < 22 (got {raw})"
    return True, f"Node {raw} (>= 22)"


def _check_file_exists(rel: str) -> tuple[bool, str]:
    path = REPO_ROOT / rel
    if not path.is_file():
        return False, f"missing: {rel}"
    size = path.stat().st_size
    return True, f"{rel} ({size} bytes)"


def _check_frozen_integrity() -> tuple[bool, str]:
    """Run ci/check_frozen_integrity.py and capture its verdict."""
    script = REPO_ROOT / "ci" / "check_frozen_integrity.py"
    if not script.is_file():
        return False, "ci/check_frozen_integrity.py missing"
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return False, "ci/check_frozen_integrity.py timed out (>60s)"
    if result.returncode != 0:
        return False, f"exit {result.returncode}: {result.stdout.strip()[:200]}"
    # The script prints "frozen-research integrity: 28/28 files match" on success.
    out = (result.stdout or "").strip()
    if "28/28" not in out:
        return False, f"unexpected output: {out[:200]}"
    return True, f"28/28 match (exit 0)"


def _check_openapi_no_drift() -> tuple[bool, str]:
    """Run npm run openapi:check from the frontend directory."""
    frontend_dir = REPO_ROOT / "frontend"
    if not (frontend_dir / "package.json").is_file():
        return False, "frontend/package.json missing"
    try:
        result = subprocess.run(
            [shutil.which("npm") or "npm", "run", "openapi:check", "--silent"],
            cwd=str(frontend_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return False, "npm run openapi:check timed out (>120s)"
    if result.returncode != 0:
        return False, f"exit {result.returncode}: {(result.stderr or '').strip()[:200]}"
    out = (result.stdout or "") + (result.stderr or "")
    if "no drift" not in out.lower() and "up to date" not in out.lower():
        return False, f"unexpected output: {out.strip()[:200]}"
    return True, "no drift"


def main() -> int:
    checks: list[tuple[str, tuple[bool, str]]] = []

    checks.append(("Python 3.12.x", _check_python_version()))
    checks.append(("Node >= 22", _check_node_version()))
    checks.append(("backend/requirements-lock.txt", _check_file_exists("backend/requirements-lock.txt")))
    checks.append(("frontend/package-lock.json", _check_file_exists("frontend/package-lock.json")))
    checks.append(("ci/frozen_research_manifest.json", _check_file_exists("ci/frozen_research_manifest.json")))
    checks.append(("frozen integrity (28/28)", _check_frozen_integrity()))
    checks.append(("OpenAPI no drift", _check_openapi_no_drift()))

    print("=" * 70)
    print("PR-07B acceptance smoke check")
    print(f"Repository: {REPO_ROOT}")
    print(f"Commit:     {_git_head()}")
    print("=" * 70)
    print(f"{'Check':<40s} {'Result':<8s} Detail")
    print("-" * 70)
    failures = 0
    for name, (ok, detail) in checks:
        marker = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"{name:<40s} {marker:<8s} {detail}")
    print("-" * 70)
    if failures:
        print(f"FAILED: {failures} check(s) failed")
        return 1
    print(f"OK: all {len(checks)} smoke checks passed")
    return 0


def _git_head() -> str:
    """Best-effort git HEAD SHA (read-only; no checkout, no network)."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        ).strip()
        return out
    except Exception:
        return "(unknown)"


if __name__ == "__main__":
    sys.exit(main())
