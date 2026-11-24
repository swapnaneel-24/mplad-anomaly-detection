from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from peiars_app.db import (
    compute_signed_length_metrics,
    get_paths,
    get_snapshots_registry_rows,
    init_and_import_sqlite,
    summarize_observation,
)


class WorkbenchSnapshotSummary(BaseModel):
    snapshot_id: str
    label: str
    dataset_version: str
    record_scope: str
    registration_status: str
    case_linked_count: int
    disposition_counts: dict[str, int]
    verification_status_counts: dict[str, int]
    baseline_event_count: int
    notes: str


class WorkbenchSnapshotDetail(WorkbenchSnapshotSummary):
    manifest_reference: str
    manifest_sha256: str | None = None
    read_only_seam: bool = True
    is_admitted_source_registry: bool = False
    complete_4361_population: bool = False


class WorkbenchPackageSummary(BaseModel):
    case_id: str
    package_uid: str
    mrl_id: str
    state: str
    ims_year: str
    queues: list[str]
    observation_summary: str
    disposition: str
    verification_status: str


class PackageIdentitySection(BaseModel):
    case_id: str
    package_uid: str
    mrl_id: str
    state: str
    ims_year: str


class PackageScopeSection(BaseModel):
    snapshot_id: str
    record_scope: str
    source_registration_status: str
    complete_4361_population: bool = False


class PackageMeasurementsSection(BaseModel):
    proposed_l_km: float | None = None
    sum_geom_len_km: float | None = None
    length_diff_km: float | None = None
    length_rel_diff: float | str | None = None
    length_rel_diff_status: str


class PackageScreeningSection(BaseModel):
    queues: list[str] = Field(default_factory=list)
    screening_reasons: list[str] = Field(default_factory=list)


class PackageTopologySection(BaseModel):
    exact_geometry_duplicate: bool | str
    linear_overlap: bool | str
    invalid_geometry: bool | str
    segment_count: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class PackageReviewSection(BaseModel):
    disposition: str
    review_status: str


class PackageVerificationSection(BaseModel):
    verification_status: str
    independent_of_canonical_gis: bool | str
    blocker_reason: str


class PackageProvenanceSection(BaseModel):
    baseline_event_count_for_case: int
    frozen_baseline_head: str
    manifest_reference: str
    verified_manifest_hash: str | None = None
    evidence_record_present: bool = False


class WorkbenchPackageDetail(BaseModel):
    case_id: str
    identity: PackageIdentitySection
    scope: PackageScopeSection
    measurements: PackageMeasurementsSection
    screening: PackageScreeningSection
    topology: PackageTopologySection
    review: PackageReviewSection
    verification: PackageVerificationSection
    provenance: PackageProvenanceSection


_CASE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SNAPSHOT_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


class WorkbenchLookupError(Exception):
    pass


def validate_case_id(case_id: str) -> str:
    if not _CASE_ID_RE.match(case_id):
        raise WorkbenchLookupError(f"Invalid case identifier: {case_id}")
    return case_id


def validate_snapshot_id(snapshot_id: str) -> str:
    if not _SNAPSHOT_ID_RE.match(snapshot_id):
        raise WorkbenchLookupError(f"Invalid snapshot identifier: {snapshot_id}")
    return snapshot_id


def _load_sqlite_conn(repo_root: Path) -> tuple[sqlite3.Connection, dict[str, Any]]:
    paths = get_paths(repo_root)
    db_path = Path(paths.get("db_path") or paths.get("sqlite_db") or (repo_root / "peiars_app" / "data" / "peiars_core_v1.sqlite"))
    if not db_path.exists():
        init_and_import_sqlite(repo_root)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    has_cases = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='cases'"
    ).fetchone()
    if has_cases is None:
        conn.close()
        init_and_import_sqlite(repo_root)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
    return conn, paths


def _safe_json_loads(raw: Any, default: Any) -> Any:
    if raw is None or raw == "":
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return default


def _to_float_or_none(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        num = float(val)
        if num != num:  # NaN check
            return None
        return num
    except (TypeError, ValueError):
        return None


def _build_package_detail_from_row(
    row: sqlite3.Row,
    baseline_event_count: int,
    snapshot_id: str,
    manifest_ref: str,
    manifest_hash: str | None,
    baseline_head: str,
) -> WorkbenchPackageDetail:
    ev_raw = _safe_json_loads(row["evidence_json"], {})
    ev = ev_raw if isinstance(ev_raw, dict) else {}
    rev_raw = _safe_json_loads(row["review_state_json"], {})
    rev = rev_raw if isinstance(rev_raw, dict) else {}
    queues_raw = _safe_json_loads(row["queues_qualified_json"], [])
    queues = [str(q) for q in queues_raw] if isinstance(queues_raw, list) else []

    meas_input = ev.get("measurements") if isinstance(ev.get("measurements"), dict) else ev
    proposed_l = _to_float_or_none(
        meas_input.get("proposed_l_km") if isinstance(meas_input, dict) else None
    )
    geom_l = _to_float_or_none(
        meas_input.get("sum_geom_len_km") if isinstance(meas_input, dict) else None
    )

    metrics = compute_signed_length_metrics(
        {
            "proposed_l_km": proposed_l,
            "sum_geom_len_km": geom_l,
        }
    )

    rel_status = str(metrics.get("length_rel_diff_status") or "UNAVAILABLE")
    rel_val: float | str | None = metrics.get("length_rel_diff")
    if proposed_l == 0.0 or rel_status == "UNDEFINED_ZERO_DENOMINATOR":
        rel_status = "UNDEFINED_ZERO_DENOMINATOR"
        rel_val = "UNDEFINED_ZERO_DENOMINATOR"

    diff_km = _to_float_or_none(metrics.get("length_diff_km"))
    if diff_km is None and proposed_l is not None and geom_l is not None:
        diff_km = round(geom_l - proposed_l, 6)

    reasons_raw = ev.get("screening_reasons") or ev.get("reasons") or []
    screening_reasons = (
        [str(r) for r in reasons_raw]
        if isinstance(reasons_raw, list)
        else ([str(reasons_raw)] if reasons_raw else [])
    )

    topo_raw = ev.get("topology") if isinstance(ev.get("topology"), dict) else {}
    seg_count_raw = topo_raw.get("n_segments") or ev.get("n_segments")
    seg_count = int(seg_count_raw) if isinstance(seg_count_raw, (int, float)) else None

    def _bool_or_unavail(key: str, alt_key: str | None = None) -> bool | str:
        for k in (key, alt_key):
            if k and k in topo_raw:
                return bool(topo_raw[k])
            if k and k in ev:
                return bool(ev[k])
        return "UNAVAILABLE"

    disposition = str(row["baseline_disposition"] or "UNRESOLVED")
    review_status = str(rev.get("review_status") or row["baseline_status"] or "REVIEWED")
    verification_status = str(row["verification_status"] or "NOT_ATTEMPTED")
    blocker_reason = str(row["blocker_reason"] or "")

    indep_raw = ev.get("independent_of_canonical_gis")
    if indep_raw is None and isinstance(ev.get("verification"), dict):
        indep_raw = ev["verification"].get("independent_of_canonical_gis")
    independent_val: bool | str = (
        bool(indep_raw) if isinstance(indep_raw, bool) else "UNAVAILABLE"
    )

    case_id = str(row["case_id"])
    package_uid = str(row["package_uid"])
    mrl_id = str(row["mrl_id"] or "")
    state = str(row["source_state_key"] or "")
    ims_year = str(row["ims_year"] or "")

    return WorkbenchPackageDetail(
        case_id=case_id,
        identity=PackageIdentitySection(
            case_id=case_id,
            package_uid=package_uid,
            mrl_id=mrl_id,
            state=state,
            ims_year=ims_year,
        ),
        scope=PackageScopeSection(
            snapshot_id=snapshot_id,
            record_scope="42 selected case-linked PMGSY packages (subset of 4,361 scored P packages)",
            source_registration_status="LOCAL_RESEARCH_SNAPSHOT_NOT_ADMITTED_SOURCE",
            complete_4361_population=False,
        ),
        measurements=PackageMeasurementsSection(
            proposed_l_km=proposed_l,
            sum_geom_len_km=geom_l,
            length_diff_km=diff_km,
            length_rel_diff=rel_val,
            length_rel_diff_status=rel_status,
        ),
        screening=PackageScreeningSection(
            queues=queues,
            screening_reasons=screening_reasons,
        ),
        topology=PackageTopologySection(
            exact_geometry_duplicate=_bool_or_unavail(
                "exact_geometry_duplicate", "has_exact_geom_dup"
            ),
            linear_overlap=_bool_or_unavail("linear_overlap", "has_linear_overlap"),
            invalid_geometry=_bool_or_unavail("invalid_geometry", "has_invalid_geom"),
            segment_count=seg_count,
            details=topo_raw if topo_raw else {},
        ),
        review=PackageReviewSection(
            disposition=disposition,
            review_status=review_status,
        ),
        verification=PackageVerificationSection(
            verification_status=verification_status,
            independent_of_canonical_gis=independent_val,
            blocker_reason=blocker_reason,
        ),
        provenance=PackageProvenanceSection(
            baseline_event_count_for_case=baseline_event_count,
            frozen_baseline_head=baseline_head,
            manifest_reference=manifest_ref,
            verified_manifest_hash=manifest_hash,
            evidence_record_present=bool(ev),
        ),
    )


def _snapshot_metadata(repo_root: Path, conn: sqlite3.Connection) -> tuple[str, str, str | None, str, int]:
    rows = conn.execute(
        "SELECT baseline_disposition, verification_status, evidence_json FROM cases"
    ).fetchall()
    disp_counts: dict[str, int] = {}
    ver_counts: dict[str, int] = {}
    for r in rows:
        d = str(r["baseline_disposition"] or "UNRESOLVED")
        v = str(r["verification_status"] or "NOT_ATTEMPTED")
        disp_counts[d] = disp_counts.get(d, 0) + 1
        ver_counts[v] = ver_counts.get(v, 0) + 1

    ev_count = int(
        conn.execute("SELECT COUNT(*) AS cnt FROM baseline_events_readonly").fetchone()["cnt"]
    )
    snap_rows = get_snapshots_registry_rows(repo_root)
    first_snap = snap_rows[0] if snap_rows else {}
    snap_id = str(first_snap.get("snapshot_id") or "pmgsy3_3state_v1_curated_42")
    manifest_ref = str(
        first_snap.get("manifest_reference") or "pmgsy3_3state_v1_evidence_integration_v1"
    )
    manifest_hash = (
        str(first_snap["manifest_sha256"])
        if first_snap.get("manifest_sha256")
        else None
    )
    baseline_head = str(first_snap.get("baseline_head") or "frozen_162_baseline_events")
    return snap_id, manifest_ref, manifest_hash, baseline_head, ev_count


def list_workbench_snapshots(repo_root: Path) -> list[WorkbenchSnapshotDetail]:
    conn, _ = _load_sqlite_conn(repo_root)
    try:
        rows = conn.execute(
            "SELECT baseline_disposition, verification_status FROM cases"
        ).fetchall()
        disp_counts: dict[str, int] = {}
        ver_counts: dict[str, int] = {}
        for r in rows:
            d = str(r["baseline_disposition"] or "UNRESOLVED")
            v = str(r["verification_status"] or "NOT_ATTEMPTED")
            disp_counts[d] = disp_counts.get(d, 0) + 1
            ver_counts[v] = ver_counts.get(v, 0) + 1

        ev_count = int(
            conn.execute("SELECT COUNT(*) AS cnt FROM baseline_events_readonly").fetchone()["cnt"]
        )
        snap_rows = get_snapshots_registry_rows(repo_root)
        items: list[WorkbenchSnapshotDetail] = []
        if snap_rows:
            for s in snap_rows:
                sid = str(s.get("snapshot_id") or "pmgsy3_3state_v1_curated_42")
                items.append(
                    WorkbenchSnapshotDetail(
                        snapshot_id=sid,
                        label=str(s.get("label") or sid),
                        dataset_version=str(s.get("dataset_version") or "pmgsy3_3state_v1"),
                        record_scope="42 selected case-linked PMGSY packages (not all 4,361 scored P packages)",
                        registration_status="LOCAL_RESEARCH_SNAPSHOT_NOT_ADMITTED_SOURCE",
                        case_linked_count=len(rows),
                        disposition_counts=disp_counts,
                        verification_status_counts=ver_counts,
                        baseline_event_count=ev_count,
                        notes=(
                            "Local frozen research/review snapshot. Not an admitted /api/v1/sources "
                            "registry entry and not the complete 4,361-package P population."
                        ),
                        manifest_reference=str(
                            s.get("manifest_reference") or "pmgsy3_3state_v1_evidence_integration_v1"
                        ),
                        manifest_sha256=(
                            str(s["manifest_sha256"]) if s.get("manifest_sha256") else None
                        ),
                        read_only_seam=True,
                        is_admitted_source_registry=False,
                        complete_4361_population=False,
                    )
                )
        else:
            items.append(
                WorkbenchSnapshotDetail(
                    snapshot_id="pmgsy3_3state_v1_curated_42",
                    label="PMGSY-III 3-State Curated 42-Case Snapshot",
                    dataset_version="pmgsy3_3state_v1",
                    record_scope="42 selected case-linked PMGSY packages (not all 4,361 scored P packages)",
                    registration_status="LOCAL_RESEARCH_SNAPSHOT_NOT_ADMITTED_SOURCE",
                    case_linked_count=len(rows),
                    disposition_counts=disp_counts,
                    verification_status_counts=ver_counts,
                    baseline_event_count=ev_count,
                    notes=(
                        "Local frozen research/review snapshot. Not an admitted /api/v1/sources "
                        "registry entry and not the complete 4,361-package P population."
                    ),
                    manifest_reference="pmgsy3_3state_v1_evidence_integration_v1",
                    manifest_sha256=None,
                    read_only_seam=True,
                    is_admitted_source_registry=False,
                    complete_4361_population=False,
                )
            )
        return items
    finally:
        conn.close()


def get_workbench_snapshot(repo_root: Path, snapshot_id: str) -> WorkbenchSnapshotDetail:
    valid_id = validate_snapshot_id(snapshot_id)
    snapshots = list_workbench_snapshots(repo_root)
    for snap in snapshots:
        if snap.snapshot_id == valid_id:
            return snap
    raise WorkbenchLookupError(f"Unknown snapshot identifier: {valid_id}")


def list_workbench_pmgsy_packages(repo_root: Path) -> list[WorkbenchPackageSummary]:
    conn, _ = _load_sqlite_conn(repo_root)
    try:
        rows = conn.execute(
            """
            SELECT case_id, package_uid, mrl_id, source_state_key, ims_year,
                   queues_qualified_json, baseline_disposition, verification_status,
                   evidence_json
            FROM cases
            ORDER BY case_id ASC
            """
        ).fetchall()

        summaries: list[WorkbenchPackageSummary] = []
        for r in rows:
            queues_raw = _safe_json_loads(r["queues_qualified_json"], [])
            queues = [str(q) for q in queues_raw] if isinstance(queues_raw, list) else []
            ev_raw = _safe_json_loads(r["evidence_json"], {})
            ev = ev_raw if isinstance(ev_raw, dict) else {}
            meas_input = ev.get("measurements") if isinstance(ev.get("measurements"), dict) else ev
            metrics = compute_signed_length_metrics(
                {
                    "proposed_l_km": _to_float_or_none(
                        meas_input.get("proposed_l_km") if isinstance(meas_input, dict) else None
                    ),
                    "sum_geom_len_km": _to_float_or_none(
                        meas_input.get("sum_geom_len_km") if isinstance(meas_input, dict) else None
                    ),
                }
            )
            ver_status = str(r["verification_status"] or "NOT_ATTEMPTED")
            obs = str(summarize_observation(ev, metrics, ver_status))
            summaries.append(
                WorkbenchPackageSummary(
                    case_id=str(r["case_id"]),
                    package_uid=str(r["package_uid"]),
                    mrl_id=str(r["mrl_id"] or ""),
                    state=str(r["source_state_key"] or ""),
                    ims_year=str(r["ims_year"] or ""),
                    queues=queues,
                    observation_summary=obs,
                    disposition=str(r["baseline_disposition"] or "UNRESOLVED"),
                    verification_status=ver_status,
                )
            )
        return summaries
    finally:
        conn.close()


def get_workbench_pmgsy_package(repo_root: Path, case_id: str) -> WorkbenchPackageDetail:
    valid_id = validate_case_id(case_id)
    conn, _ = _load_sqlite_conn(repo_root)
    try:
        row = conn.execute(
            "SELECT * FROM cases WHERE case_id = ?",
            (valid_id,),
        ).fetchone()
        if row is None:
            raise WorkbenchLookupError(f"Case not found: {valid_id}")

        ev_count_row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM baseline_events_readonly WHERE case_id = ?",
            (valid_id,),
        ).fetchone()
        case_event_count = int(ev_count_row["cnt"]) if ev_count_row else 0

        snap_id, manifest_ref, manifest_hash, baseline_head, _ = _snapshot_metadata(repo_root, conn)
        return _build_package_detail_from_row(
            row=row,
            baseline_event_count=case_event_count,
            snapshot_id=snap_id,
            manifest_ref=manifest_ref,
            manifest_hash=manifest_hash,
            baseline_head=baseline_head,
        )
    finally:
        conn.close()
