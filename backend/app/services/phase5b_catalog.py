"""Verified Phase 5B figure catalog and gated delivery (PR-11).

The service consumes, strictly read-only, the frozen Phase 5B artifacts
under ``results/stream a/phase 5/figures/reproduction/``:

* ``phase5_plot_commit_manifest.json`` (Git-tracked, pinned by constant)
* ``phase5_plot_metadata.json`` (Git-tracked, verified against the manifest)
* ``phase5_figure_catalog.csv`` (DVC-backed, verified against the manifest)
* ``phase5_plot{1..8}_*.png`` (DVC-backed, verified against both the manifest
  entry and the corresponding ``.dvc`` pointer using raw bytes)

The catalog response distinguishes three independent states per figure:
``integrity`` (raw-byte identity), ``availability`` (payload present now),
and ``publication`` (binary delivery authorised). Publication is
conditional on the ``PEIARS_PHASE5B_PUBLIC_FIGURES_ENABLED`` settings
flag being explicitly enabled; the default is false.

No endpoint regenerates a Phase 5B figure, refits a detector, or
recomputes any statistical quantity. Every value is either read from a
manifest-verified artifact or explicitly marked as PR-11 application
metadata (the objective traceability links).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from app.services import frozen_evidence_trust as trust


REPO_ROOT: Path = Path(__file__).resolve().parents[3]

PHASE5_REPRO_DIR: Path = REPO_ROOT / "results" / "stream a" / "phase 5" / "reproduction"
PHASE5_FIGURES_DIR: Path = REPO_ROOT / "results" / "stream a" / "phase 5" / "figures" / "reproduction"

PHASE5_PLOT_MANIFEST_REL: str = (
    "results/stream a/phase 5/figures/reproduction/phase5_plot_commit_manifest.json"
)
PHASE5_PLOT_METADATA_REL: str = (
    "results/stream a/phase 5/figures/reproduction/phase5_plot_metadata.json"
)
PHASE5_CATALOG_REL: str = (
    "results/stream a/phase 5/figures/reproduction/phase5_figure_catalog.csv"
)

#: LF-normalized SHA-256 of the Phase 5B plot commit manifest. Candidate
#: value established during PR-11 source admission; the same
#: ``canonicalize_frozen_checker`` logic used by PR-10 applies here so the
#: pin is stable across CRLF/LF checkouts and CI platforms.
TRUSTED_PHASE5_PLOT_COMMIT_MANIFEST_SHA256: str = (
    "e883ce52aa8269d3a841fb32ebcd4a739850a2708bd70cd66dd2acf48be5c549"
)

_CANONICAL_FIGURES: dict[int, str] = {
    1: "phase5_plot1_precision_recall.png",
    2: "phase5_plot2_fraud_discovery.png",
    3: "phase5_plot3_hypergeometric_overlap.png",
    4: "phase5_plot4_spearman_matrix.png",
    5: "phase5_plot5_jaccard_matrix.png",
    6: "phase5_plot6_topk_jaccard.png",
    7: "phase5_plot7_rank_vs_rank.png",
    8: "phase5_plot8_pca_agreement.png",
}

_PNG_MAGIC: bytes = b"\x89PNG\r\n\x1a\n"
_PNG_MIN_DIM: int = 100
_PNG_MAX_DIM: int = 8000
_PNG_MIN_BYTES: int = 1024


class Phase5BUnavailableError(Exception):
    """A required Phase 5B artifact is missing (e.g. DVC payload absent)."""


class Phase5BIntegrityError(Exception):
    """A Phase 5B manifest, pointer, or binary failed verification."""


class Phase5BPublicationError(Exception):
    """Public delivery of the figure binary is not authorised."""


def _validate_png(data: bytes, filename: str) -> None:
    """Validate PNG magic, IHDR presence, and dimension bounds."""
    if len(data) < _PNG_MIN_BYTES:
        raise Phase5BIntegrityError(f"PNG too short: {filename!r}.")
    if data[:8] != _PNG_MAGIC:
        raise Phase5BIntegrityError(f"Invalid PNG signature: {filename!r}.")
    if data[12:16] != b"IHDR":
        raise Phase5BIntegrityError(f"PNG missing IHDR: {filename!r}.")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if not (_PNG_MIN_DIM <= width <= _PNG_MAX_DIM) or not (
        _PNG_MIN_DIM <= height <= _PNG_MAX_DIM
    ):
        raise Phase5BIntegrityError(
            f"PNG dimensions out of range: {filename!r} ({width}x{height})."
        )


def _read_verified_manifest() -> dict[str, Any]:
    """Read, canonicalize, pin-verify, and parse the Phase 5B plot manifest."""
    path = REPO_ROOT / PHASE5_PLOT_MANIFEST_REL
    try:
        raw = path.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise Phase5BUnavailableError(
            "The Phase 5B plot commit manifest is missing."
        ) from exc
    canonical = trust.canonicalize_frozen_checker(raw)
    digest = hashlib.sha256(canonical).hexdigest()
    if digest != TRUSTED_PHASE5_PLOT_COMMIT_MANIFEST_SHA256:
        raise Phase5BIntegrityError(
            "Untrusted Phase 5B plot commit manifest."
        )
    try:
        return json.loads(canonical.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise Phase5BIntegrityError(
            "The Phase 5B plot commit manifest is not valid JSON."
        ) from exc


def _verify_artifact_against_manifest(
    manifest: dict[str, Any], artifact_name: str, raw_bytes: bytes
) -> None:
    """Verify a raw-bytes artifact against its manifest entry (SHA-256 + size)."""
    artifacts = manifest.get("artifacts") or {}
    entry = artifacts.get(artifact_name)
    if not isinstance(entry, dict):
        raise Phase5BIntegrityError(
            f"Manifest does not list {artifact_name!r}."
        )
    expected_sha = entry.get("sha256")
    expected_size = entry.get("size_bytes")
    if not isinstance(expected_sha, str) or not isinstance(expected_size, int):
        raise Phase5BIntegrityError(
            f"Manifest entry for {artifact_name!r} is malformed."
        )
    if len(raw_bytes) != expected_size:
        raise Phase5BIntegrityError(
            f"Size mismatch for {artifact_name!r}."
        )
    actual_sha = hashlib.sha256(raw_bytes).hexdigest()
    if actual_sha != expected_sha:
        raise Phase5BIntegrityError(
            f"SHA-256 mismatch for {artifact_name!r}."
        )


def _verify_plot_metadata(manifest: dict[str, Any]) -> None:
    """Verify the Git-tracked plot metadata JSON against the manifest."""
    path = REPO_ROOT / PHASE5_PLOT_METADATA_REL
    try:
        raw = path.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise Phase5BUnavailableError(
            "The Phase 5B plot metadata JSON is missing."
        ) from exc
    _verify_artifact_against_manifest(manifest, "phase5_plot_metadata.json", raw)


def _verify_png_against_pointer(figure_no: int, raw_bytes: bytes) -> None:
    """Verify PNG raw bytes against its DVC pointer (MD5 + size)."""
    filename = _CANONICAL_FIGURES[figure_no]
    pointer_path = PHASE5_FIGURES_DIR / f"{filename}.dvc"
    try:
        pointer_bytes = pointer_path.read_bytes()
    except FileNotFoundError as exc:
        raise Phase5BIntegrityError(
            f"DVC pointer missing for figure {figure_no}."
        ) from exc
    pointer = trust.parse_dvc_pointer(
        pointer_bytes, f"{filename}.dvc", integrity_cls=Phase5BIntegrityError
    )
    if pointer["path"] != filename:
        raise Phase5BIntegrityError(
            f"DVC pointer path mismatch for figure {figure_no}."
        )
    if len(raw_bytes) != pointer["size"]:
        raise Phase5BIntegrityError(
            f"DVC size mismatch for figure {figure_no}."
        )
    if trust.md5_raw(raw_bytes) != pointer["md5"]:
        raise Phase5BIntegrityError(
            f"DVC MD5 mismatch for figure {figure_no}."
        )


def _load_catalog_csv(manifest: dict[str, Any]) -> list[dict[str, str]] | None:
    """Load the DVC-backed catalog CSV, or None when the payload is absent."""
    path = REPO_ROOT / PHASE5_CATALOG_REL
    try:
        raw = path.read_bytes()
    except (FileNotFoundError, OSError):
        return None
    _verify_artifact_against_manifest(manifest, "phase5_figure_catalog.csv", raw)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Phase5BIntegrityError("Catalog CSV is not UTF-8.") from exc
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise Phase5BIntegrityError("Catalog CSV has no header.")
    return list(reader)


class Phase5BCatalogService:
    """Read-only service over the frozen Phase 5B figure evidence."""

    source_id: str = "phase5b-figure-gallery"
    dataset_id: str = "ULB credit-card transactions (Stream A, FS-A baseline)"
    limitations: tuple[str, ...] = (
        "All figures are post-hoc, label-informed visualizations of unsupervised detector outputs.",
        "The 284,807-row full-dataset LOF Novelty Mode companion is not a canonical comparable population.",
        "PCA projections are lossy two-dimensional reductions used for visualization only.",
        "The IF_003 / IF_004 / LOF_004 pair is a post-hoc (label-informed) selection.",
        "Figure binaries are withheld by default pending independent licensing verification.",
    )

    def _publication_payload(self, publication_enabled: bool) -> dict[str, Any]:
        if publication_enabled:
            return {"enabled": True, "reason": None, "detail": None}
        return {
            "enabled": False,
            "reason": "publication_not_approved",
            "detail": (
                "Public delivery of the figure binary is disabled by default; "
                "licensing verification is required before activation."
            ),
        }

    def _per_figure_integrity(
        self, figure_no: int, manifest: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return (integrity, availability) for one figure; never raises."""
        filename = _CANONICAL_FIGURES[figure_no]
        try:
            raw = (PHASE5_FIGURES_DIR / filename).read_bytes()
        except (FileNotFoundError, OSError):
            return (
                {"state": "artifact_missing", "size_bytes": None, "sha256": None},
                {"available": False, "reason": "artifact_missing", "detail": None},
            )
        try:
            _verify_artifact_against_manifest(manifest, filename, raw)
            _verify_png_against_pointer(figure_no, raw)
            _validate_png(raw, filename)
        except Phase5BIntegrityError:
            return (
                {"state": "integrity_failed", "size_bytes": None, "sha256": None},
                {"available": False, "reason": "integrity_failed", "detail": None},
            )
        return (
            {
                "state": "verified",
                "size_bytes": len(raw),
                "sha256": manifest["artifacts"][filename]["sha256"],
            },
            {"available": True, "reason": None, "detail": None},
        )

    def get_catalog(self, *, publication_enabled: bool) -> dict[str, Any]:
        """Assemble the verified catalog with per-figure state."""
        manifest = _read_verified_manifest()
        _verify_plot_metadata(manifest)
        catalog_rows = _load_catalog_csv(manifest)

        catalog_by_no: dict[int, dict[str, str]] = {}
        if catalog_rows:
            for row in catalog_rows:
                try:
                    n = int(row["figure_no"])
                except (KeyError, ValueError):
                    continue
                catalog_by_no[n] = row

        publication = self._publication_payload(publication_enabled)
        figures: list[dict[str, Any]] = []
        for n in range(1, 9):
            filename = _CANONICAL_FIGURES[n]
            row = catalog_by_no.get(n)
            integrity, availability = self._per_figure_integrity(n, manifest)

            title = (row.get("title") if row else None) or None
            purpose = (row.get("purpose") if row else None) or None
            input_artifacts = (row.get("input_artifacts") if row else None) or None
            conventions = (row.get("conventions") if row else None) or None

            alt_text = f"Figure {n} — {title}" if title else f"Figure {n} (metadata unavailable)"

            pub_for_figure = (
                dict(publication)
                if availability["available"]
                else {
                    "enabled": False,
                    "reason": availability["reason"],
                    "detail": None,
                }
            )

            figures.append(
                {
                    "figure_no": n,
                    "filename": filename,
                    "title": title,
                    "purpose": purpose,
                    "input_artifacts": input_artifacts,
                    "conventions": conventions,
                    "alt_text": alt_text,
                    "integrity": integrity,
                    "availability": availability,
                    "publication": pub_for_figure,
                }
            )

        return {
            "source_id": self.source_id,
            "dataset_id": self.dataset_id,
            "phase": "5B",
            "stream": "A",
            "models_fitted": 0,
            "manifest_status": "verified",
            "catalog_metadata_available": catalog_rows is not None,
            "publication_gate": publication,
            "figures": figures,
            "limitations": list(self.limitations),
        }

    def get_figure_bytes(self, figure_no: int) -> bytes:
        """Return verified raw PNG bytes for the given canonical figure."""
        if figure_no not in _CANONICAL_FIGURES:
            raise Phase5BUnavailableError(
                f"Figure {figure_no} is not in the canonical allowlist."
            )
        manifest = _read_verified_manifest()
        _verify_plot_metadata(manifest)
        filename = _CANONICAL_FIGURES[figure_no]
        try:
            raw = (PHASE5_FIGURES_DIR / filename).read_bytes()
        except (FileNotFoundError, OSError) as exc:
            raise Phase5BUnavailableError(
                f"Figure {figure_no} payload is missing."
            ) from exc
        _verify_artifact_against_manifest(manifest, filename, raw)
        _verify_png_against_pointer(figure_no, raw)
        _validate_png(raw, filename)
        return raw

    def get_traceability(self) -> dict[str, Any]:
        """Return the source-native objective and RQ traceability payload."""
        return _build_traceability()


def _build_traceability() -> dict[str, Any]:
    """Compose the traceability payload from admitted source documents."""

    objectives = [
        {
            "objective_id": "(a)",
            "statement": "Data preparation and preprocessing.",
            "research_questions": [],
            "methodology_sources": [
                "docs/Phase-0.md §0.3.1 (in-scope pipeline design)",
                "docs/provenance_log.md §5 (Phase 2 Track A preprocessing decisions)",
                "docs/phase5_figure_catalog.md §3 Figure 8 conventions (FS-A frozen preprocessing)",
            ],
            "evidence": [
                {
                    "type": "methodology",
                    "source_id": None,
                    "reference": "docs/Phase-0.md §0.3.1",
                    "verification_status": "verified",
                },
                {
                    "type": "methodology",
                    "source_id": None,
                    "reference": "docs/provenance_log.md §5",
                    "verification_status": "verified",
                },
            ],
            "limitations": [
                "No standalone preprocessing-methodology document exists; the evidence is distributed across the cited passages.",
                "ULB benchmark has no missing values or categorical variables; preprocessing components are demonstrative on this dataset.",
            ],
        },
        {
            "objective_id": "(b)",
            "statement": "Application of Isolation Forest and Local Outlier Factor with comparative evaluation.",
            "research_questions": ["RQ1", "RQ3", "RQ4"],
            "methodology_sources": [
                "docs/Phase-0.md §0.4 (RQ1, RQ3, RQ4)",
                "docs/provenance_log.md §6 (Stream A Phases 3–4 execution)",
                "docs/phase5_figure_catalog.md (per-figure conventions)",
            ],
            "evidence": [
                {
                    "type": "canonical_benchmark",
                    "source_id": "pr-09-benchmark",
                    "reference": "PR-09 ten-run IF/LOF catalog",
                    "verification_status": "verified",
                },
                {
                    "type": "phase5a_agreement",
                    "source_id": "pr-10-phase5a",
                    "reference": "PR-10 Phase 5A uncertainty/agreement evidence",
                    "verification_status": "verified",
                },
                {
                    "type": "phase5b_figures",
                    "source_id": "pr-11-phase5b",
                    "reference": "PR-11 eight canonical figures",
                    "verification_status": "verified",
                },
            ],
            "limitations": [
                "The IF_003 / IF_004 / LOF_004 pair was selected post-hoc from label-informed results; all pair-specific comparisons are exploratory.",
                "The 30,000-row subsample is the canonical experiment for LOF; the 284,807-row companion used Novelty Mode and is not directly comparable.",
            ],
        },
        {
            "objective_id": "(c)",
            "statement": "Assessment of detection consistency, false-positive implications, and ethical considerations.",
            "research_questions": ["RQ2", "RQ5", "RQ6"],
            "methodology_sources": [
                "docs/Phase-0.md §0.4 (RQ2, RQ5, RQ6)",
                "docs/phase6_contract.md §4 (five-question consistency synthesis)",
                "docs/phase7_synthesis.md §4 (operational audit and ethical governance)",
            ],
            "evidence": [
                {
                    "type": "phase5a_agreement",
                    "source_id": "pr-10-phase5a",
                    "reference": "PR-10 Phase 5A agreement groups and review policies",
                    "verification_status": "verified",
                },
                {
                    "type": "phase6_synthesis",
                    "source_id": "phase6",
                    "reference": "Phase 6 five-question consistency report",
                    "verification_status": "verified",
                },
                {
                    "type": "phase7_limitations",
                    "source_id": "phase7",
                    "reference": "Phase 7 limitations and governance",
                    "verification_status": "verified",
                },
            ],
            "limitations": [
                "Empirical false-positive operations are illustrated on the ULB benchmark only; no MPLAD deployment claim is supported.",
                "The historical 284,807-row companion is not a canonical comparable population.",
            ],
        },
    ]

    research_questions = [
        {
            "rq_id": "RQ1",
            "statement": "How do Isolation Forest and Local Outlier Factor compare in their detection performance (precision, recall, F1) on the ULB benchmark across a range of contamination rates and estimator/neighborhood sizes?",
            "source_reference": "docs/Phase-0.md §0.4",
            "linked_objective": "(b)",
        },
        {
            "rq_id": "RQ2",
            "statement": "To what extent do the two methods agree on which observations are anomalous, and does agreement correlate with higher confidence in the detection (as measured by label-informed metrics)?",
            "source_reference": "docs/Phase-0.md §0.4",
            "linked_objective": "(c)",
        },
        {
            "rq_id": "RQ3",
            "statement": "How sensitive is each method's output to small changes in its primary hyperparameters (contamination for both, n_estimators for iForest, n_neighbors for LOF), and what does this sensitivity imply about the stability of unsupervised anomaly detection on imbalanced data?",
            "source_reference": "docs/Phase-0.md §0.4",
            "linked_objective": "(b)",
        },
        {
            "rq_id": "RQ4",
            "statement": "What proportion of variance is captured by the first two and three principal components of each dataset, and does visual inspection of the reduced space reveal coherent separation between detected anomalies and normal observations?",
            "source_reference": "docs/Phase-0.md §0.4",
            "linked_objective": "(b)",
        },
        {
            "rq_id": "RQ5",
            "statement": "When the same pipeline is applied to publicly available government expenditure data, do the detected anomalies correspond to interpretable domain patterns, or does the absence of structured, domain-relevant features render the output uninterpretable?",
            "source_reference": "docs/Phase-0.md §0.4",
            "linked_objective": "(c)",
        },
        {
            "rq_id": "RQ6",
            "statement": "At the false-positive rates observed on the benchmark, what would the absolute volume of flagged entries be if applied to a plausible MPLAD-scale dataset (e.g., ~543 constituencies, thousands of projects annually), and is this volume operationally tractable for human review?",
            "source_reference": "docs/Phase-0.md §0.4",
            "linked_objective": "(c)",
        },
    ]

    return {
        "source_identity": {
            "document": "docs/provenance_log.md",
            "section": "1",
            "status": "source_verified",
        },
        "objectives": objectives,
        "research_questions": research_questions,
        "historical_companion": {
            "population": 284807,
            "canonical_comparable": False,
            "limitations": [
                "The 284,807-row full-dataset run used LOF Novelty Mode fitted on a 50,000-row subsample.",
                "Recall degraded from 80.9% (30k native LOF) to 33.9% (284k Novelty Mode).",
                "The historical companion is documented in docs/phase7_synthesis.md §2 as a scale-stress artefact, not canonical evidence.",
            ],
        },
        "reproducibility": {
            "source_references": [
                {"document": "docs/provenance_log.md", "purpose": "Per-phase decision trail"},
                {"document": "docs/phase5_figure_catalog.md", "purpose": "Figure generation contract"},
                {"document": "docs/phase6_contract.md", "purpose": "Five-question synthesis methodology"},
                {"document": "docs/phase7_synthesis.md", "purpose": "Limitations and licensing"},
            ],
            "artifact_references": [
                {
                    "path": "results/stream a/phase 5/figures/reproduction/phase5_figure_catalog.csv",
                    "kind": "catalog",
                },
                {
                    "path": "results/stream a/phase 5/figures/reproduction/phase5_plot_commit_manifest.json",
                    "kind": "manifest",
                },
                {
                    "path": "results/stream a/phase 5/figures/reproduction/phase5_plot_metadata.json",
                    "kind": "metadata",
                },
            ],
            "limitations": [
                "Reproducibility references pin source identities; live values remain served by their respective verified adapters.",
                "Publication of PNG binaries requires independent licensing review per docs/phase7_synthesis.md §5.",
            ],
        },
        "limitations": list(Phase5BCatalogService.limitations),
    }


PHASE5B_CATALOG_SERVICE: Phase5BCatalogService = Phase5BCatalogService()