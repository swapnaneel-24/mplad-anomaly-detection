"""Read-only research-results adapter service (PR-08).

A strictly read-only adapter that exposes the frozen aggregate scientific
reference values from the ULB credit-card fraud benchmark experiment
(Stream A, Phase 6) through the PEIARS API.

What it serves
--------------

The single approved source ``phase6-reference-values`` exposes the 18
precomputed aggregate reference values recorded in
``src/mplad/stream_a/phase6.py`` as ``PHASE6_REFERENCE_VALUES`` (sample
size, fraud label count, IF_003/LOF_004 flag counts, intersection /
union / agreement-group counts, Spearman and Jaccard of the comparison
pair, hypergeometric enrichment and log10 upper-tail probability), plus
the frozen ``INTERPRETATION_PRINCIPLES`` (7 strings) and the
``EXPLORATORY_SELECTION_CAVEAT`` reused verbatim from Phase 5A.

Boundaries (PR-08)
------------------

* The adapter NEVER fits a model, NEVER recomputes a threshold, NEVER
  recomputes a bootstrap estimate, a hypergeometric probability or a
  correlation matrix, and NEVER produces a live prediction. Every value
  it serves is a precomputed, frozen constant exported by the frozen
  ``phase6.py`` module.
* The frozen ``mplad`` package is NEVER imported. The adapter reads the
  frozen source files' raw bytes, verifies their SHA-256 digests against
  the trusted frozen manifest (``ci/frozen_research_manifest.json``),
  and parses the verified bytes via :func:`ast.literal_eval` to extract
  the exported constants. No ``import mplad``, no ``importlib``, no
  numpy, no pandas, no scikit-learn, no code execution.
* The adapter NEVER executes a research pipeline, NEVER deserializes a
  data file (no pickle, no CSV, no DVC pull) and NEVER dynamically loads
  an arbitrary file. It only reads the frozen Python source files'
  exported constants via AST extraction.
* The service is read-only: it exposes no write method and creates no
  database rows.

Trusted integrity verification
------------------------------

The adapter does NOT trust the file it happens to read. It loads the
approved SHA-256 digests from ``ci/frozen_research_manifest.json`` (the
same manifest used by ``ci/check_frozen_integrity.py``) and compares
the computed digest of every consumed file against the approved value
BEFORE parsing. On mismatch, a ``ResearchIntegrityError`` is raised,
which the API layer maps to a sanitized 503 ``SERVICE_NOT_READY``
response. The adapter NEVER returns modified results or substitutes
synthetic data on integrity failure.

Startup safety
--------------

All file reading and verification is **lazy** — it happens on the first
research request, not at module import time. If the frozen artifacts are
missing, the module imports successfully and the FastAPI application
starts normally. Authentication, readiness, case-review workflows and
all other endpoints remain operational. The research API returns a
sanitized unavailable response only when a research endpoint is actually
called.

Security
--------

* Unknown ``source_id`` values are rejected with
  :class:`SourceNotFoundError`. The ``source_id`` is never used to
  construct a filesystem path -- the artifact path is fixed and relative
  to the repository root.
* The ``source_id`` is validated against an allowlist (currently exactly
  one entry). No path traversal, no absolute-path injection, no
  directory traversal, no symlink escaping.
* No filesystem discovery from user requests; the artifact paths are
  hardcoded constants.
* File-size is bounded by the source file's natural size (a few KB of
  Python source); no unbounded materialization.
* No dynamic execution of source files; :func:`ast.literal_eval` only
  evaluates literal expressions (dict, list, tuple, str, int, float,
  bool, None).
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

#: Reuse the canonical source-not-found error so the API layer can map it
#: to ``SOURCE_NOT_FOUND`` exactly like the source-registry seam.
from app.services.source_registry import SourceNotFoundError

# ---------------------------------------------------------------------------
# Repository root and frozen-artifact paths (module-level constants; no
# file I/O happens at import time)
# ---------------------------------------------------------------------------

#: Repository root: backend/app/services/research_source.py
#:   -> parents[0] = services/, parents[1] = app/, parents[2] = backend/,
#:      parents[3] = repository root (the parent of ``backend/``).
REPO_ROOT: Path = Path(__file__).resolve().parents[3]

#: Path to the trusted frozen-research manifest (the same file used by
#: ``ci/check_frozen_integrity.py``). This is the authoritative source of
#: approved SHA-256 digests.
FROZEN_MANIFEST_PATH: Path = REPO_ROOT / "ci" / "frozen_research_manifest.json"

#: Repository-relative paths to the frozen source artifacts consumed by
#: this adapter. These are the exact strings recorded in the frozen
#: manifest and in every provenance payload.
ARTIFACT_REL_PATH: str = "src/mplad/stream_a/phase6.py"
PHASE5_REL_PATH: str = "src/mplad/stream_a/phase5_analysis.py"
CONFIG_REL_PATH: str = "src/mplad/common/config.py"

#: Absolute paths (resolved but NOT read at import time).
ARTIFACT_PATH: Path = REPO_ROOT / ARTIFACT_REL_PATH
PHASE5_PATH: Path = REPO_ROOT / PHASE5_REL_PATH
CONFIG_PATH: Path = REPO_ROOT / CONFIG_REL_PATH

#: Digest algorithm and canonicalization recorded in provenance payloads.
DIGEST_ALGORITHM: str = "sha-256"
#: The frozen integrity checker (``ci/check_frozen_integrity.py``)
#: canonicalizes text files (no null bytes) by replacing CRLF with LF
#: before hashing. Binary files (containing null bytes) are hashed as
#: raw bytes. The adapter uses the SAME canonicalization so its computed
#: digests match the manifest on both Linux (LF) and Windows (CRLF).
CANONICALIZATION: str = "frozen-checker-compatible"

# ---------------------------------------------------------------------------
# Source identity (frozen)
# ---------------------------------------------------------------------------

#: The single approved read-only research source identifier.
PHASE6_REFERENCE_SOURCE_ID: str = "phase6-reference-values"

#: Frozen dataset the reported results pertain to.
DATASET_ID: str = "ulb-credit-card-fraud-2013"

#: Research family / stream the source belongs to.
RESEARCH_FAMILY: str = "stream-a-anomaly-detection"

#: Detector methods whose aggregate results are reported (frozen order).
MODEL_METHODS: tuple[str, ...] = ("IsolationForest", "LOF")

#: Result type recorded on the source descriptor.
RESULT_TYPE: str = "aggregate-reference-values"

#: Result granularity recorded on the source descriptor.
RESULT_GRANULARITY: str = "experiment-level"


# ---------------------------------------------------------------------------
# Trusted digest loading (lazy; happens on first research request)
# ---------------------------------------------------------------------------


class ResearchIntegrityError(Exception):
    """Raised when a frozen artifact's computed digest does not match
    the approved trusted digest from the frozen manifest.

    This is an integrity failure: the file on disk has been modified,
    corrupted, or is not the approved artifact. The API layer maps this
    to a sanitized 503 ``SERVICE_NOT_READY`` response.
    """


class ResearchUnavailableError(Exception):
    """Raised when a frozen artifact is missing or unreadable.

    The API layer maps this to a sanitized 503 ``SERVICE_NOT_READY``
    response. The application remains operational for all non-research
    endpoints.
    """


def _load_trusted_digests() -> dict[str, str]:
    """Load the approved SHA-256 digests from the frozen manifest.

    Returns a dict mapping repository-relative path to the approved
    SHA-256 hex digest. This is the same manifest used by
    ``ci/check_frozen_integrity.py`` — it is the authoritative source
    of trusted artifact identities.

    Raises :class:`ResearchUnavailableError` if the manifest itself is
    missing or unreadable (the research adapter cannot operate without
    trusted digests).
    """
    try:
        manifest_bytes = FROZEN_MANIFEST_PATH.read_bytes()
        manifest: dict[str, str] = json.loads(manifest_bytes)
        return manifest
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        raise ResearchUnavailableError(
            "The frozen research manifest is missing or unreadable; "
            "research results cannot be served."
        ) from exc


def _canonicalize(data: bytes) -> bytes:
    """Apply the SAME canonicalization as ``ci/check_frozen_integrity.py``.

    Text files (no null bytes): CRLF → LF replacement.
    Binary files (null bytes present): raw bytes, unchanged.

    This ensures the adapter's computed digests match the frozen manifest
    on both Linux (LF endings) and Windows (CRLF endings after git
    checkout). The frozen integrity checker uses this exact logic.
    """
    if b"\x00" not in data:
        return data.replace(b"\r\n", b"\n")
    return data


def _sha256_canonicalized(data: bytes) -> str:
    """Compute the SHA-256 of the canonicalized bytes."""
    return hashlib.sha256(_canonicalize(data)).hexdigest()


def _read_and_verify(path: Path, rel_path: str, trusted_digests: dict[str, str]) -> bytes:
    """Read a frozen artifact's raw bytes, canonicalize them, verify the
    SHA-256 against the trusted manifest, and return the **canonicalized**
    byte snapshot.

    The returned canonicalized bytes are the SAME bytes used for both
    provenance (SHA-256 reported in the API response) and parsing (AST
    extraction of constants) — the same-snapshot guarantee.

    Raises :class:`ResearchUnavailableError` if the file is missing.
    Raises :class:`ResearchIntegrityError` if the computed digest does
    not match the approved trusted digest.
    """
    try:
        raw = path.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise ResearchUnavailableError(
            f"The frozen research artifact {rel_path!r} is missing or "
            f"unreadable; research results cannot be served."
        ) from exc

    approved_digest = trusted_digests.get(rel_path)
    if approved_digest is None:
        raise ResearchIntegrityError(
            f"The frozen research artifact {rel_path!r} is not listed in "
            f"the trusted manifest; research results cannot be served."
        )

    canonicalized = _canonicalize(raw)
    computed_digest = hashlib.sha256(canonicalized).hexdigest()
    if computed_digest != approved_digest:
        raise ResearchIntegrityError(
            f"The frozen research artifact {rel_path!r} has a SHA-256 "
            f"digest that does not match the approved trusted value; "
            f"research results cannot be served."
        )

    return canonicalized


# ---------------------------------------------------------------------------
# Human-readable metric descriptions (one per reference value)
# ---------------------------------------------------------------------------

_METRIC_DESCRIPTIONS: dict[str, str] = {
    "sample_size": (
        "Number of observations in the canonical 30,000-row ULB sample "
        "(ten validated run blocks share this row count)."
    ),
    "fraud_label_count": (
        "Number of positive (fraud) labels in the canonical sample "
        "(count(Class == 1) per run block)."
    ),
    "if003_flagged_count": (
        "Observations flagged by Isolation Forest run IF_003 under the "
        "saved canonical 1% threshold (bottom 1% of scores)."
    ),
    "lof004_flagged_count": (
        "Observations flagged by LOF run LOF_004 under the saved canonical "
        "1% threshold (bottom 1% of scores)."
    ),
    "observed_intersection": (
        "Observations flagged by both IF_003 and LOF_004 (the size of the "
        "intersection of the two saved 1% flag sets)."
    ),
    "union_size": (
        "Observations flagged by IF_003 or LOF_004 (the size of the union "
        "of the two saved 1% flag sets)."
    ),
    "both_observation_count": (
        "Agreement-group 'both': observations flagged by both detectors "
        "(identical to the observed intersection)."
    ),
    "if_only_observation_count": (
        "Agreement-group 'if_only': observations flagged only by IF_003."
    ),
    "lof_only_observation_count": (
        "Agreement-group 'lof_only': observations flagged only by LOF_004."
    ),
    "neither_observation_count": (
        "Agreement-group 'neither': observations flagged by neither detector."
    ),
    "both_fraud_count": (
        "Labelled-fraud observations in agreement-group 'both' "
        "(flagged by both detectors)."
    ),
    "if_only_fraud_count": (
        "Labelled-fraud observations in agreement-group 'if_only' "
        "(flagged only by IF_003)."
    ),
    "lof_only_fraud_count": (
        "Labelled-fraud observations in agreement-group 'lof_only' "
        "(flagged only by LOF_004)."
    ),
    "neither_fraud_count": (
        "Labelled-fraud observations in agreement-group 'neither' "
        "(flagged by neither detector)."
    ),
    "spearman_if003_lof004": (
        "Spearman rank correlation between the IF_003 and LOF_004 "
        "anomaly-score vectors (published 4-dp rounding)."
    ),
    "jaccard_if003_lof004": (
        "Jaccard similarity of the IF_003 and LOF_004 saved 1% flag sets "
        "(|intersection| / |union|; published 4-dp rounding)."
    ),
    "enrichment_observed_over_expected": (
        "Observed-over-expected enrichment of the IF_003/LOF_004 flag "
        "intersection under the hypergeometric null "
        "(observed / expected; published 2-dp rounding)."
    ),
    "log10_upper_tail_probability": (
        "log10 of the hypergeometric upper-tail (survival) probability of "
        "the observed IF_003/LOF_004 intersection under the null "
        "(published as approximate)."
    ),
}

# ---------------------------------------------------------------------------
# Scientific limitations (apply to every result from this source)
# ---------------------------------------------------------------------------

_LIMITATIONS: tuple[str, ...] = (
    "Results are aggregate reference values from a single 30,000-row sample "
    "of the ULB credit-card fraud benchmark; they are not row-level "
    "predictions and must not be used to score individual transactions.",
    "The IF_003/LOF_004 comparison is exploratory and subject to "
    "label-informed selection bias (the pair was highlighted after inspecting "
    "the Phase 4 label-informed results).",
    "Performance observed on the ULB credit-card fraud benchmark must not be "
    "assumed to transfer to MPLAD transactions or any other domain.",
    "No universal superiority of LOF or Isolation Forest is claimed; the "
    "evidence covers one benchmark sample and post-hoc selected runs.",
    "An anomaly flag is not proof of fraud; flags are detector opinions at a "
    "fixed 1% budget, not adjudicated findings.",
    "Reference values are precomputed and frozen; this endpoint does not "
    "refit models, recompute thresholds or produce live predictions.",
    "Float reference values are published roundings compared with documented "
    "tolerances; integer references compare exactly.",
)


# ---------------------------------------------------------------------------
# AST extraction (pure-Python, no module import)
# ---------------------------------------------------------------------------


def _extract_constant_from_ast(
    source: str, constant_name: str
) -> Any:
    """Extract a top-level constant assignment from Python source via AST.

    Parses the source file's AST, finds the ``constant_name = ...``
    assignment (or ``constant_name: type = ...`` annotated assignment) at
    module level, and returns the literal value via
    :func:`ast.literal_eval`. This avoids importing the module (which
    would pull in numpy/pandas/sklearn) while still reading the exact
    frozen values from the frozen source file.

    Supports dict, list, tuple, str, int, float, bool, and None literals
    (anything :func:`ast.literal_eval` handles).
    """
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == constant_name:
                    return ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and target.id == constant_name:
                return ast.literal_eval(node.value)
    raise KeyError(
        f"constant {constant_name!r} not found at module level in the parsed source"
    )


# ---------------------------------------------------------------------------
# Bounded cache-integrity policy
# ---------------------------------------------------------------------------
#
# The cache stores BOTH the parsed constants AND the verified digests of
# the three frozen artifacts at the time they were parsed.
#
# On every request:
#   1. Read all three artifact files' raw bytes.
#   2. Compute their canonicalized SHA-256 digests.
#   3. If the cache exists AND all three computed digests match the cached
#      digests → reuse the cached parsed constants (no AST reprocessing).
#   4. If the cache exists AND any digest does NOT match → invalidate the
#      cache, raise ResearchIntegrityError (503). The next request after
#      the artifact is restored will re-verify and recover.
#   5. If the cache does NOT exist → verify against the manifest, parse via
#      AST, cache both the constants and the verified digests.
#   6. If any file is missing → raise ResearchUnavailableError (503),
#      invalidate the cache.
#
# This policy ensures:
#   - Changed/missing source → 503 (fail closed).
#   - Restored valid source → recovers without restart.
#   - Unchanged source → reuses parsed constants (no unnecessary AST work).
#   - No reliance on modification time alone (digest is the proof).

#: The bounded cache entry. ``None`` means no cache (first request or
#: after invalidation). When populated, it holds the parsed constants
#: and the verified digests of the three artifacts at parse time.
_RESEARCH_CACHE: dict[str, Any] | None = None

#: The three artifact paths and their rel-path identifiers, as a tuple
#: of (abs_path, rel_path) pairs, checked in this order.
_ARTIFACT_SPECS: tuple[tuple[Path, str], ...] = (
    (ARTIFACT_PATH, ARTIFACT_REL_PATH),
    (PHASE5_PATH, PHASE5_REL_PATH),
    (CONFIG_PATH, CONFIG_REL_PATH),
)


def _compute_current_digests() -> dict[str, str]:
    """Read all three artifacts and compute their canonicalized SHA-256
    digests. Does NOT verify against the manifest — just computes.

    Returns a dict mapping rel_path → computed_digest.

    Raises :class:`ResearchUnavailableError` if any file is missing.
    """
    digests: dict[str, str] = {}
    for abs_path, rel_path in _ARTIFACT_SPECS:
        try:
            raw = abs_path.read_bytes()
        except (FileNotFoundError, OSError) as exc:
            raise ResearchUnavailableError(
                f"The frozen research artifact {rel_path!r} is missing or "
                f"unreadable; research results cannot be served."
            ) from exc
        digests[rel_path] = _sha256_canonicalized(raw)
    return digests


def _load_research_constants() -> dict[str, Any]:
    """Return the verified, parsed research constants.

    Implements the bounded cache-integrity policy:

    - First request: verify all three artifact digests against the trusted
      manifest, parse via AST, cache the constants and the verified digests.
    - Subsequent requests: re-read the artifacts, re-compute their digests,
      and compare to the cached digests. If they all match, reuse the cached
      parsed constants (no AST reprocessing). If any mismatch, invalidate
      the cache and raise :class:`ResearchIntegrityError`.
    - Missing artifact: raise :class:`ResearchUnavailableError`, invalidate
      the cache.
    - Restored artifact: the next request after restoration will find no
      cache (it was invalidated), re-verify against the manifest, and
      recover without restart.

    Raises:
        ResearchUnavailableError: if any artifact is missing.
        ResearchIntegrityError: if any computed digest does not match the
            approved trusted digest (manifest check on cache miss) or the
            cached digest (cache-integrity check on cache hit).
    """
    global _RESEARCH_CACHE

    # Step 1: compute current digests (re-reads files on every request).
    try:
        current_digests = _compute_current_digests()
    except ResearchUnavailableError:
        # A file is missing — invalidate the cache and re-raise.
        _RESEARCH_CACHE = None
        raise

    # Step 2: verify current artifacts against the approved manifest on every request.
    try:
        trusted_digests = _load_trusted_digests()
    except ResearchUnavailableError:
        _RESEARCH_CACHE = None
        raise

    for rel_path, current_digest in current_digests.items():
        if trusted_digests.get(rel_path) != current_digest:
            _RESEARCH_CACHE = None
            raise ResearchIntegrityError(
                f"Frozen research integrity verification failed: {rel_path}"
            )

    # Step 3: if cache exists and current digests match cached digests, reuse cached AST constants.
    if _RESEARCH_CACHE is not None:
        cached_digests = _RESEARCH_CACHE["_verified_digests"]
        if current_digests == cached_digests:
            return _RESEARCH_CACHE
        _RESEARCH_CACHE = None

    # Step 4: cache miss — read, verify against trusted manifest, and parse.

    # Read, verify, and parse each artifact using _ARTIFACT_SPECS so
    # that tests patching _ARTIFACT_SPECS affect both the cache-check
    # path (step 1) and the cache-miss path (step 3) consistently.
    verified_bytes: dict[str, bytes] = {}
    for abs_path, rel_path in _ARTIFACT_SPECS:
        verified_bytes[rel_path] = _read_and_verify(abs_path, rel_path, trusted_digests)

    phase6_bytes = verified_bytes[ARTIFACT_REL_PATH]
    phase6_source = phase6_bytes.decode("utf-8")
    reference_values = _extract_constant_from_ast(phase6_source, "PHASE6_REFERENCE_VALUES")
    reference_tolerances = _extract_constant_from_ast(phase6_source, "PHASE6_REFERENCE_TOLERANCES")
    interpretation_principles = _extract_constant_from_ast(phase6_source, "INTERPRETATION_PRINCIPLES")
    phase6_sha256 = hashlib.sha256(phase6_bytes).hexdigest()

    phase5_bytes = verified_bytes[PHASE5_REL_PATH]
    phase5_source = phase5_bytes.decode("utf-8")
    exploratory_caveat = _extract_constant_from_ast(phase5_source, "EXPLORATORY_SELECTION_CAVEAT")
    phase5_sha256 = hashlib.sha256(phase5_bytes).hexdigest()

    config_bytes = verified_bytes[CONFIG_REL_PATH]
    config_source = config_bytes.decode("utf-8")
    threshold_percentile = _extract_constant_from_ast(config_source, "THRESHOLD_PERCENTILE")
    # RECONSTRUCTED (not verbatim): f-string cannot be parsed by ast.literal_eval.
    threshold_rule_label = f"Bottom {threshold_percentile}% of scores"
    isolation_forest_configs = [
        dict(c) for c in _extract_constant_from_ast(config_source, "ISOLATION_FOREST_CONFIGS")
    ]
    lof_configs = [
        dict(c) for c in _extract_constant_from_ast(config_source, "LOF_CONFIGS")
    ]
    # RECONSTRUCTED (not verbatim): tuple(comprehension) cannot be parsed.
    phase3_canonical_run_ids = (
        [f"IF_{i:03d}" for i in range(1, len(isolation_forest_configs) + 1)]
        + [f"LOF_{i:03d}" for i in range(1, len(lof_configs) + 1)]
    )
    config_sha256 = hashlib.sha256(config_bytes).hexdigest()

    payload: dict[str, Any] = {
        "reference_values": dict(reference_values),
        "reference_tolerances": dict(reference_tolerances),
        "interpretation_principles": list(interpretation_principles),
        "exploratory_caveat": exploratory_caveat,
        "threshold_rule_label": threshold_rule_label,
        "threshold_percentile": float(threshold_percentile),
        "phase3_canonical_run_ids": phase3_canonical_run_ids,
        "isolation_forest_configs": isolation_forest_configs,
        "lof_configs": lof_configs,
        "phase6_sha256": phase6_sha256,
        "phase5_sha256": phase5_sha256,
        "config_sha256": config_sha256,
        "phase5_rel_path": PHASE5_REL_PATH,
        "config_rel_path": CONFIG_REL_PATH,
        # Store the verified digests so subsequent requests can check
        # whether the artifacts have changed without re-parsing.
        "_verified_digests": current_digests,
    }
    _RESEARCH_CACHE = payload
    return payload


def _invalidate_cache() -> None:
    """Invalidate the research constants cache.

    Used by tests to simulate cache invalidation between requests.
    """
    global _RESEARCH_CACHE
    _RESEARCH_CACHE = None


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class ResearchSourceService:
    """Read-only adapter over the frozen Phase 6 reference values.

    The service exposes ``list_sources``, ``get_source`` and
    ``get_results``. It performs no writes, creates no database rows and
    holds no mutable state beyond the module-level research-constant
    cache (which is populated lazily on first use, with trusted
    integrity verification).

    If the frozen artifacts are missing or their digests do not match
    the trusted manifest, the service raises
    :class:`ResearchUnavailableError` or :class:`ResearchIntegrityError`
    respectively. These are caught by the API layer and mapped to a
    sanitized 503 ``SERVICE_NOT_READY`` response. The application
    remains operational for all non-research endpoints.
    """

    def list_sources(self) -> list[dict[str, Any]]:
        """Return the summary descriptors of every approved research source.

        Currently exactly one source (``phase6-reference-values``) is
        approved. The summaries carry no provenance and no experimental
        detail; use :meth:`get_source` for those.

        This method does NOT access the frozen artifacts — it returns
        static metadata only. The availability field reflects whether
        the source is registered, not whether the artifact is currently
        readable. Use :meth:`get_source` or :meth:`get_results` to
        verify runtime availability.
        """
        return [self._summary_descriptor()]

    def get_source(self, source_id: str) -> dict[str, Any]:
        """Return the full metadata for one research source.

        Raises :class:`SourceNotFoundError` for an unknown identifier.
        Raises :class:`ResearchUnavailableError` or
        :class:`ResearchIntegrityError` if the frozen artifact is
        missing or its digest does not match the trusted manifest.
        """
        self._require_known_source(source_id)
        constants = _load_research_constants()
        reference_values: dict[str, Any] = constants["reference_values"]
        experimental_context: dict[str, Any] = {
            "sample_size": reference_values["sample_size"],
            "fraud_label_count": reference_values["fraud_label_count"],
            "threshold_rule": constants["threshold_rule_label"],
            "threshold_percentile": constants["threshold_percentile"],
            "run_ids": list(constants["phase3_canonical_run_ids"]),
            "if_config": list(constants["isolation_forest_configs"]),
            "lof_config": list(constants["lof_configs"]),
        }
        return {
            **self._summary_descriptor(),
            "artifact_path": ARTIFACT_REL_PATH,
            "artifact_sha256": constants["phase6_sha256"],
            "digest_algorithm": DIGEST_ALGORITHM,
            "canonicalization": CANONICALIZATION,
            "experimental_context": experimental_context,
            "limitations": list(_LIMITATIONS),
            "supporting_artifacts": [
                {
                    "path": constants["phase5_rel_path"],
                    "sha256": constants["phase5_sha256"],
                    "role": "exploratory_selection_caveat",
                },
                {
                    "path": constants["config_rel_path"],
                    "sha256": constants["config_sha256"],
                    "role": "experiment_configuration",
                },
            ],
        }

    def get_results(self, source_id: str) -> dict[str, Any]:
        """Return the precomputed results with full provenance.

        Raises :class:`SourceNotFoundError` for an unknown identifier.
        Raises :class:`ResearchUnavailableError` or
        :class:`ResearchIntegrityError` if the frozen artifact is
        missing or its digest does not match the trusted manifest.
        """
        self._require_known_source(source_id)
        constants = _load_research_constants()
        reference_values: dict[str, Any] = constants["reference_values"]
        results: list[dict[str, Any]] = [
            self._result_item(name, value)
            for name, value in reference_values.items()
        ]
        return {
            "source_id": PHASE6_REFERENCE_SOURCE_ID,
            "dataset_id": DATASET_ID,
            "model_methods": list(MODEL_METHODS),
            "results": results,
            "interpretation_principles": list(constants["interpretation_principles"]),
            "exploratory_caveat": constants["exploratory_caveat"],
            "provenance": {
                "artifact_path": ARTIFACT_REL_PATH,
                "artifact_sha256": constants["phase6_sha256"],
                "digest_algorithm": DIGEST_ALGORITHM,
                "canonicalization": CANONICALIZATION,
            },
            "limitations": list(_LIMITATIONS),
            "is_precomputed": True,
            "is_live_prediction": False,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_known_source(self, source_id: str) -> None:
        """Reject any identifier other than the single approved source."""
        if not isinstance(source_id, str) or source_id != PHASE6_REFERENCE_SOURCE_ID:
            raise SourceNotFoundError(
                f"No approved research source is registered under {source_id!r}."
            )

    def _summary_descriptor(self) -> dict[str, Any]:
        """Build the list-view source descriptor (no provenance)."""
        return {
            "source_id": PHASE6_REFERENCE_SOURCE_ID,
            "dataset_id": DATASET_ID,
            "research_family": RESEARCH_FAMILY,
            "model_methods": list(MODEL_METHODS),
            "result_type": RESULT_TYPE,
            "result_granularity": RESULT_GRANULARITY,
            "availability": "registered",
        }

    def _result_item(self, name: str, value: Any) -> dict[str, Any]:
        """Build one :class:`ResearchResultItem`-shaped dict."""
        coerced, value_type = _classify_value(value)
        description = _METRIC_DESCRIPTIONS.get(
            name,
            "Precomputed aggregate reference value from the Phase 6 frozen artifact.",
        )
        return {
            "metric_name": name,
            "value": coerced,
            "value_type": value_type,
            "description": description,
        }


def _classify_value(value: Any) -> tuple[Any, str]:
    """Return ``(coerced_value, value_type)`` for a reference value."""
    if isinstance(value, bool):
        return str(value), "str"
    if isinstance(value, int):
        return value, "int"
    if isinstance(value, float):
        return value, "float"
    return str(value), "str"


#: Module-level singleton; constructed once, read many times. Construction
#: is cheap (no file I/O); the frozen artifacts are verified and parsed
#: lazily on the first call to ``get_source`` / ``get_results``.
RESEARCH_SOURCE_SERVICE = ResearchSourceService()
