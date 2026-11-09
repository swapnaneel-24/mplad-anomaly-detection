"""Approved source registry — architectural seam (PR-02).

Purpose and boundaries:

* The registry is the *only* future pathway by which the API will resolve
  approved dataset versions and frozen research artifacts to stable,
  opaque identifiers (see ADR §4.1 and §4.5 of the architecture record).
* PR-02 ships the contract plus a **static, empty** registry. No real
  sources are registered yet.
* Callers can never supply filesystem paths: identifiers are strictly
  validated opaque slugs (lowercase kebab-case, no separators, no ``..``).
* This module never touches the filesystem, never scans directories,
  never reads frozen research artifacts, never performs DVC pulls or
  remote-object downloads, and offers no generic file-reading capability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from app.contracts.common import DatasetKind

#: Opaque registered slug: lowercase letter/digit, then lowercase letters,
#: digits or single hyphens; 1-64 characters total. This shape excludes
#: every path construct (``/``, ``\\``, ``..``, drive letters, ``:``).
SOURCE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

#: Guard against consecutive hyphens hiding traversal-like shapes.
_FORBIDDEN_SUBSTRINGS = ("--",)


class SourceIdValidationError(ValueError):
    """Raised when a supplied source identifier is not a valid opaque slug."""


@dataclass(frozen=True)
class SourceDescriptor:
    """An approved source registration (no filesystem or storage detail)."""

    source_id: str
    dataset_kind: DatasetKind
    integrity_status: str
    analysis_status: str

    def __post_init__(self) -> None:
        validate_source_id(self.source_id)


def validate_source_id(source_id: object) -> str:
    """Validate an opaque source identifier; return it when valid.

    Raises :class:`SourceIdValidationError` for anything that is not a
    strict lowercase kebab-case slug — including all path-like input
    (``../etc/passwd``, ``C:\\data``, ``a/b``, backslashes, colons,
    whitespace, uppercase, leading hyphens and overlong values).
    """
    if not isinstance(source_id, str):
        raise SourceIdValidationError(
            "A source identifier must be a string, got "
            f"{type(source_id).__name__}."
        )
    candidate = source_id
    if (
        not candidate
        or len(candidate) > 64
        or any(part in candidate for part in _FORBIDDEN_SUBSTRINGS)
        or candidate.startswith("-")
        or candidate.endswith("-")
        or not SOURCE_ID_PATTERN.fullmatch(candidate)
    ):
        raise SourceIdValidationError(
            "A source identifier must be an opaque registered slug "
            "(lowercase letters, digits and single hyphens; at most 64 "
            "characters). Path-like values are not accepted."
        )
    return candidate


class SourceRegistry:
    """Read-only registry of approved sources."""

    def list_sources(self) -> Sequence[SourceDescriptor]:
        """Return all registered sources (empty until sources are admitted)."""
        raise NotImplementedError

    def get_source(self, source_id: str) -> SourceDescriptor:
        """Return one registered source by its opaque identifier."""
        raise NotImplementedError


class StaticSourceRegistry(SourceRegistry):
    """In-memory registry over a fixed set of descriptors.

    Used in PR-02 with an empty set; later pull requests will replace it
    with a configuration-backed registry of *admitted* snapshots. It never
    derives registrations from the filesystem.
    """

    def __init__(self, sources: Iterable[SourceDescriptor] = ()) -> None:
        self._sources: dict[str, SourceDescriptor] = {}
        for source in sources:
            if source.source_id in self._sources:
                raise ValueError(
                    f"Duplicate source registration for '{source.source_id}'."
                )
            self._sources[source.source_id] = source

    def list_sources(self) -> Sequence[SourceDescriptor]:
        return tuple(self._sources[source_id] for source_id in sorted(self._sources))

    def get_source(self, source_id: str) -> SourceDescriptor:
        key = validate_source_id(source_id)
        try:
            return self._sources[key]
        except KeyError:
            raise SourceNotFoundError(
                f"No approved source is registered under '{key}'."
            ) from None


class SourceNotFoundError(LookupError):
    """Raised when a well-formed source identifier is not registered."""


#: The PR-02 default: an explicitly empty, static registry.
EMPTY_SOURCE_REGISTRY = StaticSourceRegistry()
