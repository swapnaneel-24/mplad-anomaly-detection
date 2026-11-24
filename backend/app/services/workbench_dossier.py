"""Case dossier export, independent verification, and chain-integrity checks (Prompt D)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from peiars_app.db import get_paths, sha256_file
from peiars_app.provenance import sha256_obj

import app.services.workbench_investigations as _inv_svc
from app.services.workbench_investigations import (
    EXPECTED_FROZEN_BASELINE_COUNT,
    InvestigationConflictError,
    InvestigationDetail,
    InvestigationHistoryResponse,
    InvestigationIntegrityError,
    InvestigationValidationError,
    _ensure_app_events_table,
    _load_app_stream_rows,
    _to_app_history_record,
    _to_baseline_history_record,
    _verify_app_stream,
    append_workbench_reviewer_note,
    get_workbench_investigation_detail,
)
from app.services.workbench_pmgsy import WorkbenchLookupError, _load_sqlite_conn

DOSSIER_SCHEMA_VERSION = "PEIARS_CASE_DOSSIER_V1"
MANIFEST_SCHEMA_VERSION = "PEIARS_DOSSIER_MANIFEST_V1"

MANDATORY_LIMITATIONS: list[str] = [
    "Screening flags are not confirmed defects.",
    "Mapped/proposed length discrepancy does not prove construction deficiency.",
    "Topology observations do not prove fraud or expenditure irregularity.",
    "SUPPORTED_REVIEW_CANDIDATE is not equivalent to CONFIRMED_SOURCE_DEFECT.",
    "VERIFICATION_BLOCKED is not evidence of benignity or disproval.",
    "Hash-chain integrity verifies recorded history continuity, not factual truth.",
]


class DossierManifestFileEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    filename: str
    sha256: str


class DossierManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = MANIFEST_SCHEMA_VERSION
    case_id: str
    generated_at_utc: str
    files: list[DossierManifestFileEntry]
    frozen_baseline_head: str
    app_stream_head: str
    snapshot_id: str


class CaseDossierPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    export_schema_version: str = DOSSIER_SCHEMA_VERSION
    generated_at_utc: str
    identity: dict[str, Any]
    snapshot: dict[str, Any]
    screening: dict[str, Any]
    measurements: dict[str, Any]
    topology: dict[str, Any]
    review: dict[str, Any]
    verification: dict[str, Any]
    event_history: dict[str, Any]
    provenance: dict[str, Any]
    limitations: list[str]


class ExportCaseDossierResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    json_filename: str
    markdown_filename: str
    manifest_filename: str
    dossier: CaseDossierPayload
    markdown_content: str
    manifest: DossierManifest


class VerifyCaseDossierRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    dossier: CaseDossierPayload
    manifest: DossierManifest | None = None
    json_content_sha256: str | None = None
    markdown_content: str | None = None


class VerifyCaseDossierResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    valid: bool
    checks: dict[str, bool]
    errors: list[str] = Field(default_factory=list)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_strict_baseline_chain(repo_root: Path, known_case_ids: set[str] | None = None) -> tuple[bool, str | None, int, str, list[dict[str, Any]]]:
    """Strictly verify the 162-event baseline log: count, no duplicates, no reordering, valid chain, and head."""
    paths = get_paths(repo_root)
    hist_path = paths["hist_162_jsonl"]
    if not hist_path.exists():
        return False, f"Missing baseline history file: {hist_path.name}", 0, _inv_svc.EXPECTED_FROZEN_HEAD, []

    try:
        raw_lines = [ln for ln in hist_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError as exc:
        return False, f"Unable to read baseline history: {exc}", 0, _inv_svc.EXPECTED_FROZEN_HEAD, []

    if len(raw_lines) != EXPECTED_FROZEN_BASELINE_COUNT:
        return (
            False,
            f"Expected {EXPECTED_FROZEN_BASELINE_COUNT} baseline events, found {len(raw_lines)}.",
            len(raw_lines),
            _inv_svc.EXPECTED_FROZEN_HEAD,
            [],
        )

    events: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    prev_hash = "GENESIS"
    try:
        for idx, line in enumerate(raw_lines):
            ev = json.loads(line)
            if not isinstance(ev, dict):
                raise ValueError(f"Baseline event at index {idx} is not an object.")
            ev_id = str(ev.get("event_id") or "")
            if ev_id:
                if ev_id in seen_ids:
                    raise ValueError(f"Duplicate baseline event_id detected: {ev_id}")
                seen_ids.add(ev_id)
            ev_case_id = str(ev.get("case_id") or "")
            if known_case_ids is not None and ev_case_id and ev_case_id not in known_case_ids:
                raise ValueError(f"Baseline event {ev_id or idx} references unknown case_id: {ev_case_id}")
            if "previous_event_hash" in ev and ev["previous_event_hash"] is not None:
                if ev["previous_event_hash"] != prev_hash:
                    raise ValueError(f"Baseline hash chain break at index {idx} ({ev_id}).")
            events.append(ev)
            prev_hash = sha256_obj(ev)
    except Exception as exc:
        return False, f"Baseline chain verification failed: {exc}", len(raw_lines), prev_hash, events

    if prev_hash != _inv_svc.EXPECTED_FROZEN_HEAD:
        return (
            False,
            f"Baseline head hash mismatch: got {prev_hash}, expected {_inv_svc.EXPECTED_FROZEN_HEAD}.",
            len(events),
            prev_hash,
            events,
        )

    # Verify frozen manifest hash if present in manifest JSON
    man_path = paths.get("man_42_json")
    hist_actual_sha = sha256_file(hist_path) if hist_path.exists() else None
    if man_path and man_path.exists() and hist_actual_sha:
        try:
            man_obj = json.loads(man_path.read_text(encoding="utf-8"))
            if isinstance(man_obj, dict):
                recorded_hist_hash = man_obj.get("decision_history_sha256") or man_obj.get("baseline_history_sha256")
                if isinstance(recorded_hist_hash, str) and recorded_hist_hash and recorded_hist_hash != hist_actual_sha:
                    return (
                        False,
                        "Frozen manifest baseline history hash mismatch.",
                        len(events),
                        prev_hash,
                        events,
                    )
        except Exception as exc:
            return False, f"Frozen manifest unreadable/corrupted: {exc}", len(events), prev_hash, events

    return True, None, len(events), prev_hash, events


def verify_strict_app_chain(
    all_app_rows: list[dict[str, Any]],
    baseline_head: str,
    known_case_ids: set[str] | None = None,
) -> tuple[bool, str | None, str]:
    """Strictly verify app_events stream: no duplicate event_id, valid case_id, and unbroken hash chain."""
    seen_event_ids: set[str] = set()
    ok, err, head = _verify_app_stream(all_app_rows, baseline_head)
    if not ok:
        return False, err, head

    for idx, row in enumerate(all_app_rows):
        ev_id = str(row.get("event_id") or "")
        if not ev_id:
            return False, f"Missing event_id on app event at index {idx}.", head
        if ev_id in seen_event_ids:
            return False, f"Duplicate app event_id detected: {ev_id}", head
        seen_event_ids.add(ev_id)

        cid = str(row.get("case_id") or "")
        if known_case_ids is not None and cid not in known_case_ids:
            return False, f"App event {ev_id} references unknown case_id: {cid}", head

    return True, None, head


def _format_dossier_markdown(dossier: CaseDossierPayload) -> str:
    ident = dossier.identity
    snap = dossier.snapshot
    scr = dossier.screening
    meas = dossier.measurements
    topo = dossier.topology
    rev = dossier.review
    ver = dossier.verification
    prov = dossier.provenance
    hist = dossier.event_history

    lines = [
        f"# PEIARS Case Dossier ? {ident.get('case_id', '')}",
        "",
        f"- **Export Schema Version:** `{dossier.export_schema_version}`",
        f"- **Generated At (UTC):** `{dossier.generated_at_utc}`",
        f"- **Case ID:** `{ident.get('case_id', '')}` | **Package UID:** `{ident.get('package_uid', '')}` | **MRL ID:** `{ident.get('mrl_id', '')}`",
        f"- **State:** `{ident.get('state', '')}` | **IMS Year:** `{ident.get('ims_year', '')}`",
        f"- **Snapshot ID:** `{snap.get('snapshot_id', '')}` | **Manifest:** `{snap.get('manifest_reference', '')}`",
        "",
        "## Screening",
        f"- **Queues:** {', '.join(scr.get('queues') or []) or 'None recorded'}",
        f"- **Screening Reasons:** {', '.join(scr.get('screening_reasons') or []) or 'Recorded in case package'}",
        "",
        "## Measurements",
        f"- **Proposed Length (km):** {meas.get('proposed_l_km')}",
        f"- **Mapped Geometry Length (km):** {meas.get('sum_geom_len_km')}",
        f"- **Signed Difference (km):** {meas.get('signed_diff_km')}",
        f"- **Relative Difference:** {meas.get('relative_diff')}",
        f"- **Zero-Denominator Status:** `{meas.get('relative_diff_status')}`",
        "",
        "## Topology",
        f"- **Exact Geometry Duplicate:** {topo.get('exact_geometry_duplicate')}",
        f"- **Linear Overlap:** {topo.get('linear_overlap')}",
        f"- **Invalid Geometry:** {topo.get('invalid_geometry')}",
        f"- **Segment Count:** {topo.get('segment_count')}",
        "",
        "## Review & Verification",
        f"- **Baseline Disposition:** `{rev.get('baseline_disposition')}`",
        f"- **Current Application Review State:** `{rev.get('current_app_review_state')}`",
        f"- **Reviewer Notes Count:** {len(rev.get('reviewer_notes') or [])}",
        f"- **Verification Status:** `{ver.get('verification_status')}`",
        f"- **Independent of Canonical GIS:** {ver.get('independent_of_canonical_gis')}",
        f"- **Blocker Reason:** {ver.get('blocker_reason') or 'None recorded'}",
        "",
        "## Provenance & Event Counts",
        f"- **Global Frozen Event Count:** {prov.get('global_frozen_event_count')}",
        f"- **Case Frozen Event Count:** {prov.get('case_frozen_event_count')}",
        f"- **Case App Event Count:** {prov.get('case_app_event_count')}",
        f"- **Frozen Baseline Head:** `{prov.get('frozen_baseline_head')}`",
        f"- **Application Stream Head:** `{prov.get('app_stream_head')}`",
        f"- **Case Baseline Events Recorded:** {len(hist.get('frozen_baseline_events') or [])}",
        f"- **Case Application Events Recorded:** {len(hist.get('application_events') or [])}",
        "",
        "## Mandatory Limitations",
        *[f"- {lim}" for lim in dossier.limitations],
    ]
    return chr(10).join(lines) + chr(10)
def build_and_export_case_dossier(
    repo_root: Path,
    case_id: str,
    *,
    write_sidecar_files: bool = False,
) -> ExportCaseDossierResponse:
    detail: InvestigationDetail = get_workbench_investigation_detail(repo_root, case_id)

    conn, paths = _load_sqlite_conn(repo_root)
    try:
        _ensure_app_events_table(conn)
        known_rows = conn.execute("SELECT case_id FROM cases").fetchall()
        known_ids = {str(r["case_id"]) for r in known_rows}
        if case_id not in known_ids:
            raise WorkbenchLookupError(f"Unknown investigation case_id: {case_id}")
        all_app_rows = _load_app_stream_rows(conn)
    finally:
        conn.close()

    base_ok, base_err, base_count, base_head, base_events = verify_strict_baseline_chain(
        repo_root, known_case_ids=known_ids
    )
    if not base_ok:
        raise InvestigationIntegrityError(
            base_err or "Frozen baseline integrity check failed.",
            code="BASELINE_INTEGRITY_FAILED",
        )

    app_ok, app_err, app_head = verify_strict_app_chain(
        all_app_rows, base_head, known_case_ids=known_ids
    )
    if not app_ok:
        raise InvestigationIntegrityError(
            app_err or "Application event stream integrity check failed.",
            code="APP_STREAM_INTEGRITY_FAILED",
        )

    case_base_events: list[dict[str, Any]] = [
        _to_baseline_history_record(ev).model_dump()
        for ev in base_events
        if str(ev.get("case_id") or "") == case_id
    ]
    case_app_rows = [r for r in all_app_rows if r["case_id"] == case_id]
    case_app_events: list[dict[str, Any]] = [
        _to_app_history_record(r).model_dump() for r in case_app_rows
    ]
    reviewer_notes: list[dict[str, Any]] = [
        {
            "event_id": r["event_id"],
            "reviewer_id": r["reviewer_id"],
            "timestamp_utc": r["timestamp_utc"],
            "note": r["note"],
            "event_hash": r["event_hash"],
        }
        for r in case_app_rows
    ]

    generated_at = datetime.now(timezone.utc).isoformat()
    hist_ref = str(paths["hist_162_jsonl"].name) if paths.get("hist_162_jsonl") else "PEIARS_PMGSY_DECISION_HISTORY.jsonl"

    dossier = CaseDossierPayload(
        export_schema_version=DOSSIER_SCHEMA_VERSION,
        generated_at_utc=generated_at,
        identity={
            "case_id": detail.identity.case_id,
            "package_uid": detail.identity.package_uid,
            "mrl_id": detail.identity.mrl_id,
            "state": detail.identity.state,
            "ims_year": detail.identity.ims_year,
        },
        snapshot={
            "snapshot_id": detail.provenance.snapshot_id,
            "frozen_baseline_reference": hist_ref,
            "manifest_reference": detail.provenance.manifest_reference,
        },
        screening={
            "queues": detail.selection.queues,
            "screening_reasons": detail.selection.screening_reasons,
            "selection_ranks": detail.selection.selection_ranks,
        },
        measurements={
            "proposed_l_km": detail.measurements.proposed_l_km,
            "sum_geom_len_km": detail.measurements.sum_geom_len_km,
            "signed_diff_km": detail.measurements.signed_diff_km,
            "relative_diff": detail.measurements.relative_diff,
            "relative_diff_status": detail.measurements.relative_diff_status,
        },
        topology={
            "exact_geometry_duplicate": detail.topology.exact_geometry_duplicate,
            "linear_overlap": detail.topology.linear_overlap,
            "invalid_geometry": detail.topology.invalid_geometry,
            "segment_count": detail.topology.segment_count,
        },
        review={
            "baseline_disposition": detail.review.baseline_disposition,
            "baseline_case_status": detail.review.baseline_case_status,
            "current_app_review_state": detail.review.current_app_review_state,
            "reviewer_notes": reviewer_notes,
        },
        verification={
            "verification_status": detail.verification.verification_status,
            "independent_of_canonical_gis": detail.verification.independent_of_canonical_gis,
            "blocker_reason": detail.verification.blocker_reason,
        },
        event_history={
            "frozen_baseline_events": case_base_events,
            "application_events": case_app_events,
        },
        provenance={
            "global_frozen_event_count": base_count,
            "case_frozen_event_count": len(case_base_events),
            "case_app_event_count": len(case_app_events),
            "frozen_baseline_head": base_head,
            "app_stream_head": app_head,
            "manifest_reference": detail.provenance.manifest_reference,
            "verified_manifest_hash": detail.provenance.verified_manifest_hash,
            "export_generation_metadata": {
                "schema_version": DOSSIER_SCHEMA_VERSION,
                "generated_at_utc": generated_at,
            },
        },
        limitations=list(MANDATORY_LIMITATIONS),
    )

    json_str = json.dumps(dossier.model_dump(), indent=2, sort_keys=True) + chr(10)
    md_str = _format_dossier_markdown(dossier)

    json_filename = f"{case_id}_dossier.json"
    md_filename = f"{case_id}_dossier.md"
    manifest_filename = f"{case_id}_dossier_manifest.json"

    manifest = DossierManifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        case_id=case_id,
        generated_at_utc=generated_at,
        files=[
            DossierManifestFileEntry(filename=json_filename, sha256=_sha256_text(json_str)),
            DossierManifestFileEntry(filename=md_filename, sha256=_sha256_text(md_str)),
        ],
        frozen_baseline_head=base_head,
        app_stream_head=app_head,
        snapshot_id=detail.provenance.snapshot_id,
    )

    if write_sidecar_files:
        export_dir = paths["data_dir"] / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        (export_dir / json_filename).write_text(json_str, encoding="utf-8")
        (export_dir / md_filename).write_text(md_str, encoding="utf-8")
        (export_dir / manifest_filename).write_text(
            json.dumps(manifest.model_dump(), indent=2, sort_keys=True) + chr(10),
            encoding="utf-8",
        )

    return ExportCaseDossierResponse(
        case_id=case_id,
        json_filename=json_filename,
        markdown_filename=md_filename,
        manifest_filename=manifest_filename,
        dossier=dossier,
        markdown_content=md_str,
        manifest=manifest,
    )


def verify_case_dossier(
    repo_root: Path,
    request_payload: VerifyCaseDossierRequest,
) -> VerifyCaseDossierResponse:
    dossier = request_payload.dossier
    case_id = str(dossier.identity.get("case_id") or "")
    errors: list[str] = []
    checks: dict[str, bool] = {
        "case_exists": False,
        "case_id_matches": False,
        "package_uid_matches": False,
        "snapshot_id_matches": False,
        "frozen_baseline_head_matches": False,
        "app_stream_head_matches": False,
        "event_counts_match": False,
        "disposition_matches": False,
        "verification_status_matches": False,
        "mandatory_limitations_present": False,
        "manifest_and_hashes_match": True,
    }

    if not case_id:
        return VerifyCaseDossierResponse(
            case_id="",
            valid=False,
            checks=checks,
            errors=["Dossier missing identity.case_id."],
        )

    try:
        live_detail = get_workbench_investigation_detail(repo_root, case_id)
    except WorkbenchLookupError:
        errors.append(f"Unknown case_id in dossier: {case_id}")
        return VerifyCaseDossierResponse(
            case_id=case_id,
            valid=False,
            checks=checks,
            errors=errors,
        )

    checks["case_exists"] = True
    checks["case_id_matches"] = dossier.identity.get("case_id") == live_detail.identity.case_id
    if not checks["case_id_matches"]:
        errors.append("Case ID mismatch between dossier and live state.")

    checks["package_uid_matches"] = dossier.identity.get("package_uid") == live_detail.identity.package_uid
    if not checks["package_uid_matches"]:
        errors.append("Package UID mismatch between dossier and live state.")

    checks["snapshot_id_matches"] = (
        dossier.snapshot.get("snapshot_id") == live_detail.provenance.snapshot_id
        and (request_payload.manifest is None or request_payload.manifest.snapshot_id == live_detail.provenance.snapshot_id)
    )
    if not checks["snapshot_id_matches"]:
        errors.append("Snapshot ID mismatch between dossier/manifest and live state.")

    dossier_frozen_head = dossier.provenance.get("frozen_baseline_head")
    checks["frozen_baseline_head_matches"] = (
        dossier_frozen_head == live_detail.provenance.frozen_head_hash
        and (request_payload.manifest is None or request_payload.manifest.frozen_baseline_head == live_detail.provenance.frozen_head_hash)
    )
    if not checks["frozen_baseline_head_matches"]:
        errors.append("Frozen baseline head hash mismatch.")

    dossier_app_head = dossier.provenance.get("app_stream_head")
    checks["app_stream_head_matches"] = (
        dossier_app_head == live_detail.provenance.app_head_hash
        and (request_payload.manifest is None or request_payload.manifest.app_stream_head == live_detail.provenance.app_head_hash)
    )
    if not checks["app_stream_head_matches"]:
        errors.append("Application stream head hash mismatch.")

    recorded_app_events = dossier.event_history.get("application_events")
    recorded_app_len = len(recorded_app_events) if isinstance(recorded_app_events, list) else -1
    recorded_base_events = dossier.event_history.get("frozen_baseline_events")
    recorded_base_len = len(recorded_base_events) if isinstance(recorded_base_events, list) else -1

    checks["event_counts_match"] = (
        dossier.provenance.get("global_frozen_event_count") == live_detail.provenance.frozen_baseline_event_count
        and dossier.provenance.get("case_app_event_count") == live_detail.provenance.app_event_count
        and recorded_app_len == live_detail.provenance.app_event_count
        and recorded_base_len == dossier.provenance.get("case_frozen_event_count")
    )
    if not checks["event_counts_match"]:
        errors.append("Event count mismatch in dossier provenance or event history.")

    checks["disposition_matches"] = (
        dossier.review.get("baseline_disposition") == live_detail.review.baseline_disposition
    )
    if not checks["disposition_matches"]:
        errors.append("Baseline disposition mismatch.")

    checks["verification_status_matches"] = (
        dossier.verification.get("verification_status") == live_detail.verification.verification_status
    )
    if not checks["verification_status_matches"]:
        errors.append("Verification status mismatch.")

    missing_lims = [lim for lim in MANDATORY_LIMITATIONS if lim not in dossier.limitations]
    checks["mandatory_limitations_present"] = len(missing_lims) == 0
    if not checks["mandatory_limitations_present"]:
        errors.append("Mandatory limitation statements missing from dossier.")

    if request_payload.json_content_sha256 is not None:
        canonical_json = json.dumps(dossier.model_dump(), indent=2, sort_keys=True) + chr(10)
        if _sha256_text(canonical_json) != request_payload.json_content_sha256:
            checks["manifest_and_hashes_match"] = False
            errors.append("Dossier JSON hash mismatch.")

    if request_payload.manifest is not None:
        if request_payload.manifest.case_id != case_id:
            checks["manifest_and_hashes_match"] = False
            errors.append("Manifest case_id does not match dossier case_id.")
        expected_json_str = json.dumps(dossier.model_dump(), indent=2, sort_keys=True) + chr(10)
        expected_json_sha = _sha256_text(expected_json_str)
        expected_md_str = request_payload.markdown_content if request_payload.markdown_content is not None else _format_dossier_markdown(dossier)
        expected_md_sha = _sha256_text(expected_md_str)

        by_name = {f.filename: f.sha256 for f in request_payload.manifest.files}
        json_file_name = f"{case_id}_dossier.json"
        md_file_name = f"{case_id}_dossier.md"
        if by_name.get(json_file_name) != expected_json_sha:
            checks["manifest_and_hashes_match"] = False
            errors.append("Manifest JSON SHA-256 does not match dossier payload.")
        if by_name.get(md_file_name) != expected_md_sha:
            checks["manifest_and_hashes_match"] = False
            errors.append("Manifest Markdown SHA-256 does not match dossier markdown.")

    is_valid = all(checks.values()) and len(errors) == 0
    return VerifyCaseDossierResponse(
        case_id=case_id,
        valid=is_valid,
        checks=checks,
        errors=errors,
    )
