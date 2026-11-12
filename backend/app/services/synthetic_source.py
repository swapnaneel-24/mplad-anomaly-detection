"""Synthetic demonstration source adapter (PR-05B §5).

A minimal, read-only synthetic record source for demonstrating the
investigation workflow end-to-end. The records are **explicitly
fictional** — they are NOT research findings, NOT ML anomaly scores,
and NOT real public officials. Every record carries a prominent
``SYNTHETIC DEMONSTRATION RECORD`` label.

Boundaries (PR-05B §4, §5):

* The adapter is registered **only** under the ``demonstration_sources``
  configuration flag (``PEIARS_DEMONSTRATION_SOURCES=true``). When the
  flag is false (the default), the synthetic source is invisible and
  the source registry remains empty as in PR-02.
* The adapter never reads the filesystem, never loads frozen research
  artifacts, never performs DVC pulls, and never connects to object
  storage. The records are hardcoded Python data structures.
* The records are **read-only fixtures**. A synthetic source record is
  never rewritten when its associated case status changes (PR-05B §4
  critical separation). Review cases created from these records are
  real, mutable application data persisted in PostgreSQL.
* The dataset/snapshot identifiers are explicitly synthetic
  (``synthetic-demonstration`` / ``synthetic-v1``) and do not collide
  with any frozen research identifier.

The ~10 deterministic records below describe illustrative administrative
inconsistencies (missing fields, unusual patterns) without claiming
they are confirmed misconduct. An anomaly flag is a statistical
observation requiring interpretation and investigation (PR-05B §1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.contracts.common import DatasetKind

#: The explicit synthetic dataset identifier. Does not collide with any
#: frozen research identifier (the ULB benchmark uses ``ulb-benchmark``).
SYNTHETIC_DATASET_ID: str = "synthetic-demonstration"

#: The explicit synthetic snapshot identifier.
SYNTHETIC_SNAPSHOT_ID: str = "synthetic-v1"


@dataclass(frozen=True)
class SyntheticRecord:
    """One deterministic, read-only demonstration record.

    Fields are chosen to support the investigation workflow:
    record_ref is the stable opaque reference used to bind a review
    case; the human-readable fields support the evidence-examination
    region of the Investigation Workspace.
    """

    record_ref: str
    title: str
    description: str
    evidence_summary: str
    administrative_context: str
    limitations: str

    @property
    def dataset_id(self) -> str:
        return SYNTHETIC_DATASET_ID

    @property
    def snapshot_id(self) -> str:
        return SYNTHETIC_SNAPSHOT_ID


#: The deterministic demonstration record set.
#: ~10 records covering illustrative administrative inconsistencies.
#: None of these are real; none claim confirmed misconduct.
_SYNTHETIC_RECORDS: tuple[SyntheticRecord, ...] = (
    SyntheticRecord(
        record_ref="synth-001",
        title="SYNTHETIC DEMONSTRATION RECORD — NOT A RESEARCH FINDING",
        description=(
            "Fictional administrative record with an unusually high fund "
            "utilisation ratio relative to its peer group. This is a "
            "synthetic illustration, not a measured anomaly."
        ),
        evidence_summary=(
            "Synthetic evidence: reported utilisation 98% where peer-group "
            "median is 72%. No real official or constituency is referenced."
        ),
        administrative_context=(
            "Synthetic context: a single financial year, a single "
            "administrative unit. Field definitions are illustrative."
        ),
        limitations=(
            "Synthetic data does not reflect the verified ULB benchmark "
            "schema. No Isolation Forest or LOF score is claimed."
        ),
    ),
    SyntheticRecord(
        record_ref="synth-002",
        title="SYNTHETIC DEMONSTRATION RECORD — NOT A RESEARCH FINDING",
        description=(
            "Fictional record with a missing expenditure field. This is a "
            "synthetic illustration of an incomplete administrative return."
        ),
        evidence_summary=(
            "Synthetic evidence: the ``expenditure_reported`` field is "
            "absent while peer records populate it. No real data is implied."
        ),
        administrative_context="Synthetic context: single financial year.",
        limitations="Synthetic; no ML score claimed.",
    ),
    SyntheticRecord(
        record_ref="synth-003",
        title="SYNTHETIC DEMONSTRATION RECORD — NOT A RESEARCH FINDING",
        description=(
            "Fictional record where the sanctioned amount equals the "
            "released amount exactly, an unusual administrative pattern."
        ),
        evidence_summary=(
            "Synthetic evidence: sanctioned == released to the cent. "
            "Illustrative only."
        ),
        administrative_context="Synthetic context: single financial year.",
        limitations="Synthetic; no ML score claimed.",
    ),
    SyntheticRecord(
        record_ref="synth-004",
        title="SYNTHETIC DEMONSTRATION RECORD — NOT A RESEARCH FINDING",
        description=(
            "Fictional record with a fund-release date preceding the "
            "sanction date — an illustrative temporal inconsistency."
        ),
        evidence_summary=(
            "Synthetic evidence: release_date < sanction_date by 14 days. "
            "Illustrative only."
        ),
        administrative_context="Synthetic context: single financial year.",
        limitations="Synthetic; no ML score claimed.",
    ),
    SyntheticRecord(
        record_ref="synth-005",
        title="SYNTHETIC DEMONSTRATION RECORD — NOT A RESEARCH FINDING",
        description=(
            "Fictional record with an uncharacteristically low utilisation "
            "ratio relative to its peer group. Synthetic illustration."
        ),
        evidence_summary=(
            "Synthetic evidence: reported utilisation 12% where peer-group "
            "median is 72%. Illustrative only."
        ),
        administrative_context="Synthetic context: single financial year.",
        limitations="Synthetic; no ML score claimed.",
    ),
    SyntheticRecord(
        record_ref="synth-006",
        title="SYNTHETIC DEMONSTRATION RECORD — NOT A RESEARCH FINDING",
        description=(
            "Fictional record where the implementing agency name field "
            "contains a numeric token instead of an organisational name."
        ),
        evidence_summary=(
            "Synthetic evidence: agency field = '4471' rather than a name. "
            "Illustrative only."
        ),
        administrative_context="Synthetic context: single financial year.",
        limitations="Synthetic; no ML score claimed.",
    ),
    SyntheticRecord(
        record_ref="synth-007",
        title="SYNTHETIC DEMONSTRATION RECORD — NOT A RESEARCH FINDING",
        description=(
            "Fictional record with a duplicate expenditure entry across two "
            "reporting periods. Synthetic illustration of a data-quality flag."
        ),
        evidence_summary=(
            "Synthetic evidence: identical amount in two consecutive periods. "
            "Illustrative only."
        ),
        administrative_context="Synthetic context: two reporting periods.",
        limitations="Synthetic; no ML score claimed.",
    ),
    SyntheticRecord(
        record_ref="synth-008",
        title="SYNTHETIC DEMONSTRATION RECORD — NOT A RESEARCH FINDING",
        description=(
            "Fictional record with a sanctioned amount far above the "
            "peer-group 95th percentile. Synthetic illustration."
        ),
        evidence_summary=(
            "Synthetic evidence: sanctioned amount in the top 1% of the "
            "synthetic peer group. Illustrative only."
        ),
        administrative_context="Synthetic context: single financial year.",
        limitations="Synthetic; no ML score claimed.",
    ),
    SyntheticRecord(
        record_ref="synth-009",
        title="SYNTHETIC DEMONSTRATION RECORD — NOT A RESEARCH FINDING",
        description=(
            "Fictional record with a fund-release amount exceeding the "
            "sanctioned amount — an illustrative administrative overshoot."
        ),
        evidence_summary=(
            "Synthetic evidence: released > sanctioned by 3%. Illustrative only."
        ),
        administrative_context="Synthetic context: single financial year.",
        limitations="Synthetic; no ML score claimed.",
    ),
    SyntheticRecord(
        record_ref="synth-010",
        title="SYNTHETIC DEMONSTRATION RECORD — NOT A RESEARCH FINDING",
        description=(
            "Fictional record with a missing geographical coordinate field. "
            "Synthetic illustration of a spatial-data gap."
        ),
        evidence_summary=(
            "Synthetic evidence: ``latitude`` and ``longitude`` fields are "
            "null. Illustrative only."
        ),
        administrative_context="Synthetic context: single financial year.",
        limitations="Synthetic; no ML score claimed.",
    ),
)


class SyntheticSourceRegistry:
    """Read-only registry over the deterministic synthetic record set.

    Implements the same ``list_sources`` / ``get_source`` interface as
    :class:`app.services.source_registry.SourceRegistry` but returns
    synthetic descriptors. The records themselves are retrieved through
    :meth:`list_records` and :meth:`get_record`.
    """

    def list_sources(self) -> Sequence:
        from app.services.source_registry import SourceDescriptor

        return (
            SourceDescriptor(
                source_id=SYNTHETIC_DATASET_ID,
                dataset_kind="mplads_administration",
                # Synthetic demonstration data is NOT integrity-verified real
                # data. The "unavailable" status honestly reflects that no
                # integrity verification applies to fictional fixtures.
                integrity_status="unavailable",
                # Synthetic demonstration data is "restricted" to
                # demonstration use — it must never be presented as
                # verified-benchmark or exploratory research data.
                analysis_status="restricted",
            ),
        )

    def get_source(self, source_id: str):
        from app.services.source_registry import SourceDescriptor, SourceNotFoundError, validate_source_id

        validate_source_id(source_id)
        if source_id != SYNTHETIC_DATASET_ID:
            raise SourceNotFoundError(
                f"No approved source is registered under '{source_id}'."
            )
        return SourceDescriptor(
            source_id=SYNTHETIC_DATASET_ID,
            dataset_kind="mplads_administration",
            integrity_status="unavailable",
            analysis_status="restricted",
        )

    def list_records(self) -> Sequence[SyntheticRecord]:
        """Return all synthetic demonstration records in deterministic order."""
        return _SYNTHETIC_RECORDS

    def get_record(self, record_ref: str) -> SyntheticRecord:
        """Return one synthetic record by its stable ``record_ref``.

        Raises :class:`SyntheticRecordNotFoundError` if no record matches.
        """
        for r in _SYNTHETIC_RECORDS:
            if r.record_ref == record_ref:
                return r
        raise SyntheticRecordNotFoundError(record_ref)

    def has_record(self, record_ref: str) -> bool:
        """True if ``record_ref`` identifies a known synthetic record."""
        return any(r.record_ref == record_ref for r in _SYNTHETIC_RECORDS)


class SyntheticRecordNotFoundError(LookupError):
    """Raised when a synthetic record_ref does not match any fixture."""

    def __init__(self, record_ref: str) -> None:
        self.record_ref = record_ref
        super().__init__(f"No synthetic demonstration record found with ref {record_ref!r}.")


#: Module-level singleton; constructed once, read many times.
SYNTHETIC_SOURCE_REGISTRY = SyntheticSourceRegistry()
