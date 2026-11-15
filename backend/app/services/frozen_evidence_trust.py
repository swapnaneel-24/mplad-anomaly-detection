"""Shared frozen-evidence trust-chain helpers (PR-09 / PR-10).

These helpers implement the accepted PR-09 identity rules so that every
read-only research adapter uses **one** verification framework rather than
a competing second one:

* ``frozen-checker-compatible`` — CRLF→LF for text files (no NUL bytes),
  matching ``ci/check_frozen_integrity.py``. Used for files anchored to
  ``ci/frozen_research_manifest.json`` (frozen source modules, docs, tests).
* ``windows-commit-manifest-compatible`` — LF→CRLF reconstruction. The Phase 4
  and Phase 5 reproduction metadata was produced on Windows (CRLF) and is
  stored LF-normalized in Git; reconstructing the CRLF form reproduces the
  recorded commit-manifest SHA-256 and byte size exactly.

For DVC-backed payloads, the ``.dvc`` pointer MD5 is compared against the raw
bytes and the CRLF-reconstructed form (the DVC materialization ending is not
assumed); a size check accompanies both.

The helpers raise sanitized adapter errors (caller-provided classes) so the
public API never leaks server paths or stack traces. They perform no model
fitting, no pickle deserialization, no DVC execution and no downloads.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

#: The pointer parser accepts a single ``outs`` entry with exactly these
#: required keys and a small allowlist of optional ones.
DVC_OUT_REQUIRED_KEYS: frozenset[str] = frozenset({"md5", "size", "hash", "path"})
DVC_OUT_ALLOWED_KEYS: frozenset[str] = frozenset(
    {"md5", "size", "hash", "path", "etag"}
)

DIGEST_ALGORITHM: str = "sha-256"
FROZEN_CHECKER_CANONICALIZATION: str = "frozen-checker-compatible"
WINDOWS_MANIFEST_CANONICALIZATION: str = "windows-commit-manifest-compatible"


# ---------------------------------------------------------------------------
# Canonicalization and digest helpers
# ---------------------------------------------------------------------------


def canonicalize_frozen_checker(data: bytes) -> bytes:
    """Frozen integrity checker's rule: CRLF→LF for text (no NUL) bytes."""
    if b"\x00" not in data:
        return data.replace(b"\r\n", b"\n")
    return data


def reconstruct_crlf(data: bytes) -> bytes:
    """Reconstruct the Windows-produced CRLF form from LF-normalized bytes."""
    if b"\x00" in data or b"\r\n" in data:
        return data
    return data.replace(b"\n", b"\r\n")


def sha256_frozen_checker(data: bytes) -> str:
    return hashlib.sha256(canonicalize_frozen_checker(data)).hexdigest()


def sha256_windows_manifest(data: bytes) -> str:
    return hashlib.sha256(reconstruct_crlf(data)).hexdigest()


def md5_raw(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


# ---------------------------------------------------------------------------
# Git-tracked file readers and JSON parsers
# ---------------------------------------------------------------------------


def read_git_file(
    path: Path, rel_path: str, *, unavailable_cls: type[Exception]
) -> bytes:
    """Read a Git-tracked file, raising ``unavailable_cls`` if missing."""
    try:
        return path.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise unavailable_cls(
            f"The frozen evidence file {rel_path!r} is missing or "
            f"unreadable; the capability cannot be served."
        ) from exc


def parse_json_metadata(
    data: bytes, rel_path: str, *, integrity_cls: type[Exception]
) -> dict[str, Any]:
    """Parse a Git-tracked JSON metadata file (bounded, no execution)."""
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise integrity_cls(
            f"The evidence metadata file {rel_path!r} is not valid JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise integrity_cls(
            f"The evidence metadata file {rel_path!r} has an unexpected shape."
        )
    return payload


def load_frozen_manifest_digests(
    manifest_path: Path, *, unavailable_cls: type[Exception]
) -> dict[str, str]:
    """Load the trusted frozen-research manifest (path → sha256)."""
    try:
        raw = manifest_path.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise unavailable_cls(
            "The trusted frozen-research manifest is missing; the evidence "
            "catalog cannot be verified."
        ) from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise unavailable_cls(
            "The trusted frozen-research manifest is not valid JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise unavailable_cls(
            "The trusted frozen-research manifest has an unexpected shape."
        )
    return {str(k): str(v) for k, v in payload.items()}


# ---------------------------------------------------------------------------
# Bounded DVC pointer parser
# ---------------------------------------------------------------------------


def parse_dvc_pointer(
    data: bytes,
    pointer_rel_path: str,
    *,
    integrity_cls: type[Exception],
) -> dict[str, Any]:
    """Parse a Git-tracked ``.dvc`` pointer with a bounded safe loader.

    Accepts exactly one output entry under ``outs`` with the required keys
    (``md5``, ``size``, ``hash``, ``path``); rejects malformed YAML, extra
    output entries, unexpected keys and non-single-file outputs.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise integrity_cls(
            "The DVC pointer is not valid UTF-8."
        ) from exc
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not lines or lines[0].strip() != "outs:":
        raise integrity_cls(
            f"The DVC pointer {pointer_rel_path!r} does not start with 'outs:'."
        )
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in lines[1:]:
        if not line.startswith((" ", "\t", "-")):
            raise integrity_cls(
                f"The DVC pointer {pointer_rel_path!r} has unexpected top-level content."
            )
        stripped = line.strip()
        if stripped.startswith("- "):
            if current is not None:
                entries.append(current)
            current = {}
            stripped = stripped[2:].strip()
            if not stripped:
                continue
        if current is None:
            raise integrity_cls(
                f"The DVC pointer {pointer_rel_path!r} is malformed."
            )
        if ":" not in stripped:
            raise integrity_cls(
                f"The DVC pointer {pointer_rel_path!r} has a malformed entry."
            )
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if key not in DVC_OUT_ALLOWED_KEYS:
            raise integrity_cls(
                f"The DVC pointer {pointer_rel_path!r} has an unexpected key {key!r}."
            )
        current[key] = value
    if current is not None:
        entries.append(current)
    if len(entries) != 1:
        raise integrity_cls(
            f"The DVC pointer {pointer_rel_path!r} must have exactly one "
            f"output entry (got {len(entries)})."
        )
    entry = entries[0]
    missing = DVC_OUT_REQUIRED_KEYS - entry.keys()
    if missing:
        raise integrity_cls(
            f"The DVC pointer {pointer_rel_path!r} is missing keys: {sorted(missing)}."
        )
    if entry["hash"] != "md5":
        raise integrity_cls(
            f"The DVC pointer {pointer_rel_path!r} uses an unsupported hash "
            f"algorithm {entry['hash']!r}."
        )
    if not re.fullmatch(r"[0-9a-f]{32}", entry["md5"]):
        raise integrity_cls(
            f"The DVC pointer {pointer_rel_path!r} has a malformed md5 digest."
        )
    try:
        size = int(entry["size"])
    except ValueError as exc:
        raise integrity_cls(
            f"The DVC pointer {pointer_rel_path!r} has a malformed size."
        ) from exc
    return {"md5": entry["md5"], "size": size, "path": entry["path"]}


def payload_candidates(data: bytes) -> tuple[bytes, ...]:
    """The received bytes and, for text, their Windows CRLF representation."""
    if b"\x00" in data:
        return (data,)
    crlf = reconstruct_crlf(data)
    return (data,) if crlf == data else (data, crlf)


def verify_payload_bytes(
    data: bytes,
    pointer: dict[str, Any],
    payload_rel_path: str,
    *,
    integrity_cls: type[Exception],
) -> None:
    """Check MD5 AND size for the same permitted byte representation."""
    for candidate in payload_candidates(data):
        if (len(candidate) == pointer["size"] and
                md5_raw(candidate) == pointer["md5"]):
            return
    raise integrity_cls(
        f"Evidence payload DVC identity failed: {payload_rel_path!r}"
    )


def verify_payload_identity(
    data: bytes,
    pointer: dict[str, Any],
    expected_sha256: str,
    expected_size: int,
    payload_rel_path: str,
    *,
    integrity_cls: type[Exception],
) -> bytes:
    """Return only a byte form satisfying DVC and commit-manifest identities.

    Size/MD5 and size/SHA-256 must validate together for a single candidate;
    never mix raw length with a reconstructed digest, or vice versa.
    """
    for candidate in payload_candidates(data):
        if (len(candidate) == pointer["size"] == expected_size
                and md5_raw(candidate) == pointer["md5"]
                and hashlib.sha256(candidate).hexdigest() == expected_sha256):
            return candidate
    raise integrity_cls(
        f"Evidence payload identity failed: {payload_rel_path!r}"
    )


def verify_payload_sha256(
    data: bytes,
    expected_sha256: str,
    payload_rel_path: str,
    *,
    integrity_cls: type[Exception],
) -> None:
    """Verify the verified payload bytes against the commit-manifest SHA-256.

    Tries both the raw and CRLF-reconstructed forms (the manifest was
    produced on Windows; the on-disk ending is not assumed).
    """
    if sha256_frozen_checker(data) == expected_sha256:
        return
    if b"\x00" not in data and sha256_windows_manifest(data) == expected_sha256:
        return
    # Also accept the Windows-manifest digest of the LF form (covers the
    # metadata JSON case where the committed SHA is the CRLF reconstruction).
    raise integrity_cls(
        f"Evidence payload SHA-256 verification failed: {payload_rel_path!r}"
    )


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


def parse_csv_rows(
    data: bytes, rel_path: str, *, integrity_cls: type[Exception]
) -> list[dict[str, str]]:
    """Parse a verified CSV byte snapshot into rows (bounded dict reader)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise integrity_cls(
            f"The evidence payload {rel_path!r} is not valid UTF-8."
        ) from exc
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise integrity_cls(
            f"The evidence payload {rel_path!r} has no header row."
        )
    return list(reader)


def require_columns(
    rows: list[dict[str, str]],
    required: tuple[str, ...],
    rel_path: str,
    *,
    integrity_cls: type[Exception],
) -> None:
    """Assert the CSV header contains every required column."""
    if not rows:
        header: set[str] = set()
    else:
        header = set(rows[0].keys())
    missing = [c for c in required if c not in header]
    if missing:
        raise integrity_cls(
            f"The evidence payload {rel_path!r} is missing required columns: "
            f"{missing}."
        )


def coerce_float(value: str | None, *, integrity_cls: type[Exception]) -> float:
    text = (value or "").strip()
    try:
        return float(text)
    except ValueError as exc:
        raise integrity_cls(
            "A required numeric field in the evidence payload is malformed."
        ) from exc


def coerce_int(value: str | None, *, integrity_cls: type[Exception]) -> int:
    text = (value or "").strip()
    try:
        return int(text)
    except ValueError as exc:
        raise integrity_cls(
            "A required integer field in the evidence payload is malformed."
        ) from exc


def coerce_optional_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip()
    if text == "" or text.lower() == "n/a":
        return None
    try:
        return float(text)
    except ValueError:
        return None
