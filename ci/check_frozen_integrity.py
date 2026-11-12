#!/usr/bin/env python3
"""Frozen-research integrity check (PR-06B CI).

Compares the SHA-256 hashes of the repository's frozen research artifacts
against the committed manifest ``ci/frozen_research_manifest.json``.

The manifest is authoritative: it records the exact bytes of each frozen
file at the PR-06A accepted baseline. The CI job runs this script on every
pull request and push to main; any mismatch (modified, missing, or extra
file) causes a nonzero exit so a pull request cannot silently alter frozen
research.

This is a READ-ONLY check. It never modifies any file, never imports the
research package, and never runs any research code. It only hashes bytes.

Usage (from the repository root)::

    python ci/check_frozen_integrity.py

Exit codes:
    0 — every manifest entry matches and no frozen file is missing.
    1 — one or more frozen files were modified, missing, or unexpected.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

#: Repository root: ci/check_frozen_integrity.py -> parents[1].
REPO_ROOT = Path(__file__).resolve().parents[1]

#: Committed manifest of frozen research file hashes.
MANIFEST_PATH = REPO_ROOT / "ci" / "frozen_research_manifest.json"


def sha256(path: Path) -> str:
    data = path.read_bytes()
    if b"\x00" not in data:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    if not MANIFEST_PATH.exists():
        print(f"FAIL: frozen manifest not found at {MANIFEST_PATH}", file=sys.stderr)
        return 1

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    missing: list[str] = []
    mismatched: list[tuple[str, str, str]] = []
    matched = 0

    for rel, expected in sorted(manifest.items()):
        path = REPO_ROOT / rel
        if not path.exists():
            missing.append(rel)
            continue
        actual = sha256(path)
        if actual != expected:
            mismatched.append((rel, expected[:16], actual[:16]))
        else:
            matched += 1

    print(f"frozen-research integrity: {matched}/{len(manifest)} files match")
    if missing:
        print("MISSING files:")
        for rel in missing:
            print(f"  - {rel}")
    if mismatched:
        print("MODIFIED files (expected -> actual, first 16 hex chars):")
        for rel, expected, actual in mismatched:
            print(f"  - {rel}: {expected} -> {actual}")

    ok = not missing and not mismatched
    print("OK" if ok else "FAIL: frozen research integrity violation")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
