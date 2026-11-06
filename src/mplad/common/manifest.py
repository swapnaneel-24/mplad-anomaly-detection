"""SHA-256 artifact manifests: creation and strict verification."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Mapping, Union

from mplad.common.io import save_json

PathLike = Union[str, Path]

MANIFEST_VERSION: int = 1
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_HASH_CHUNK_SIZE: int = 1 << 16


class ManifestError(ValueError):
    """A manifest file is malformed or cannot be trusted."""


class ManifestVerificationError(ManifestError):
    """An artifact does not match the hash/size recorded in its manifest."""


def _is_safe_artifact_filename(name: object) -> bool:
    if not isinstance(name, str) or not name or name.strip() != name:
        return False
    if "/" in name or "\\" in name or ":" in name:
        return False
    p = Path(name)
    if p.is_absolute() or ".." in p.parts or len(p.parts) != 1 or p.name != name:
        return False
    if name in (".", ".."):
        return False
    return True


def compute_sha256(path: PathLike) -> str:
    """Stream a file and return its lowercase hexadecimal SHA-256 digest."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Cannot hash, not a file: {path}")
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_entry(path: PathLike) -> Dict:
    """Build one manifest entry: ``{'sha256': ..., 'size_bytes': ...}``."""
    path = Path(path)
    return {"sha256": compute_sha256(path), "size_bytes": path.stat().st_size}


def build_manifest(paths: Mapping[str, PathLike]) -> Dict:
    """Build a manifest dict from ``{filename: path}``."""
    for name in paths:
        if not _is_safe_artifact_filename(name):
            raise ManifestError(
                f"artifact {name!r}: artifact name must be a plain filename "
                "without path separators, '..' traversal, or drive prefixes"
            )
    return {
        "manifest_version": MANIFEST_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": {name: artifact_entry(path) for name, path in paths.items()},
    }


def save_manifest(manifest: Dict, path: PathLike, overwrite: bool = False) -> None:
    """Write a manifest to disk with the standard overwrite protection."""
    validate_manifest_structure(manifest)
    save_json(manifest, path, overwrite=overwrite)


def load_manifest(path: PathLike) -> Dict:
    """Load and structurally validate a manifest file."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Manifest not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Manifest is not valid JSON: {path}\n{exc}") from exc
    validate_manifest_structure(manifest)
    return manifest


def validate_manifest_structure(manifest: object) -> None:
    """Validate the manifest schema (version, safe filenames, hashes, sizes)."""
    problems = []
    if not isinstance(manifest, dict):
        raise ManifestError(f"Manifest must be a JSON object, got {type(manifest).__name__}.")

    version = manifest.get("manifest_version")
    if version != MANIFEST_VERSION:
        problems.append(
            f"unsupported manifest_version {version!r} (expected {MANIFEST_VERSION})"
        )

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        problems.append("'artifacts' must be a non-empty JSON object")
    else:
        for name, entry in artifacts.items():
            if not _is_safe_artifact_filename(name):
                problems.append(
                    f"artifact {name!r}: name must be a plain filename within the "
                    "manifest directory (no absolute paths, subdirectories, or '..')"
                )
                continue
            if not isinstance(entry, dict):
                problems.append(f"artifact '{name}': entry must be an object")
                continue
            sha = entry.get("sha256")
            if not isinstance(sha, str) or not _SHA256_PATTERN.match(sha.lower()):
                problems.append(f"artifact '{name}': 'sha256' must be 64 hex characters")
            size = entry.get("size_bytes")
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                problems.append(f"artifact '{name}': 'size_bytes' must be a non-negative integer")

    if problems:
        lines = ["Manifest structure is invalid:"]
        lines.extend(f"  {i}. {p}" for i, p in enumerate(problems, start=1))
        raise ManifestError("\n".join(lines))


def verify_manifest(
    manifest: Dict,
    base_dir: PathLike,
    required_artifacts: tuple = (),
) -> Dict:
    """Recompute and compare every recorded hash/size; refuse on any mismatch."""
    validate_manifest_structure(manifest)
    base_dir = Path(base_dir)
    base_resolved = base_dir.resolve()
    artifacts = manifest["artifacts"]

    problems = []
    for name in required_artifacts:
        if not _is_safe_artifact_filename(name):
            problems.append(f"required artifact {name!r} is not a safe plain filename")
        elif name not in artifacts:
            problems.append(
                f"manifest does not cover required artifact '{name}' -- refusing "
                f"to treat a partial manifest as verification"
            )

    report: Dict[str, Dict] = {}
    for name, entry in artifacts.items():
        path = base_dir / name
        if path.resolve().parent != base_resolved:
            problems.append(f"'{name}': resolves outside manifest directory {base_resolved}")
            continue
        if not path.is_file():
            problems.append(f"'{name}': file not found")
            continue
        actual_size = path.stat().st_size
        if actual_size != entry["size_bytes"]:
            problems.append(
                f"'{name}': size mismatch (manifest {entry['size_bytes']:,} bytes, "
                f"actual {actual_size:,} bytes)"
            )
            continue
        actual_sha = compute_sha256(path)
        if actual_sha != entry["sha256"].lower():
            problems.append(
                f"'{name}': SHA-256 mismatch (manifest {entry['sha256']}, "
                f"actual {actual_sha})"
            )
            continue
        report[name] = {"verified": True, "sha256": actual_sha, "size_bytes": actual_size}

    if problems:
        lines = ["Manifest verification FAILED:"]
        lines.extend(f"  {i}. {p}" for i, p in enumerate(problems, start=1))
        raise ManifestVerificationError("\n".join(lines))
    return report
