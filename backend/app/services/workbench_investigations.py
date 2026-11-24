"""Read-only and append-only investigation service for the 42 PMGSY cases (Prompt C)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from peiars_app.db import get_paths
from peiars_app.provenance import sha256_obj, verify_baseline_162_log

from app.services.workbench_pmgsy import (
    WorkbenchLookupError,
    _load_sqlite_conn,
    compute_signed_length_metrics,
)


def _parse_json_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {}

EXPECTED_FROZEN_BASELINE_COUNT = 162
EXPECTED_FROZEN_HEAD = "9caa9735fab13e88a47848a12532653bc4216548aa69cf80e4648fc5d646d5de"
DEFAULT_PMGSY_SNAPSHOT_ID = "pmgsy3_3state_v1_curated_42"


class InvestigationIntegrityError(RuntimeError):
    """Raised when baseline or app event-chain integrity fails (fail-closed)."""

    def __init__(self, message: str, *, code: str = "PROVENANCE_INTEGRITY_FAILED", details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


class InvestigationConflictError(RuntimeError):
    """Raised when a reviewer write targets a stale app-stream head or count."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class InvestigationValidationError(ValueError):
    """Raised for invalid reviewer action inputs or disallowed promotions."""


class InvestigationSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    package_uid: str
    mrl_id: str
    state: str
    ims_year: str
    queues: list[str]
    screening_summary: str
    disposition: str
    verification_status: str
    case_status: str
    app_event_count: int = 0


class InvestigationIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    package_uid: str
    mrl_id: str
    state: str
    ims_year: str


class InvestigationSelection(BaseModel):
    model_config = ConfigDict(frozen=True)

    queues: list[str]
    screening_reasons: list[str]
    selection_ranks: dict[str, Any] | None = None


class InvestigationMeasurements(BaseModel):
    model_config = ConfigDict(frozen=True)

    proposed_l_km: float | None
    sum_geom_len_km: float | None
    signed_diff_km: float | None
    relative_diff: float | float | str | None
    relative_diff_status: str


class InvestigationTopology(BaseModel):
    model_config = ConfigDict(frozen=True)

    exact_geometry_duplicate: bool
    linear_overlap: bool
    invalid_geometry: bool
    segment_count: int | None = None


class InvestigationReview(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_case_status: str
    baseline_disposition: str
    current_app_review_state: str
    app_event_count: int


class InvestigationVerification(BaseModel):
    model_config = ConfigDict(frozen=True)

    verification_status: str
    independent_of_canonical_gis: bool
    blocker_reason: str | None = None


class InvestigationProvenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    case_id: str
    package_uid: str
    frozen_baseline_event_count: int
    app_event_count: int
    frozen_head_hash: str
    app_head_hash: str
    manifest_reference: str
    verified_manifest_hash: str | None = None


class InvestigationDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    identity: InvestigationIdentity
    selection: InvestigationSelection
    measurements: InvestigationMeasurements
    topology: InvestigationTopology
    review: InvestigationReview
    verification: InvestigationVerification
    provenance: InvestigationProvenance


class HistoryEventRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    event_type: str
    timestamp_utc: str | None = None
    actor: str | None = None
    previous_state: str | None = None
    new_state: str | None = None
    disposition: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    rationale: str | None = None
    previous_event_hash: str | None = None
    event_hash: str | None = None
    stream_type: str


class BaselineStreamSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    immutable: bool = True
    event_count: int
    head_hash: str
    replay_valid: bool
    replay_error: str | None = None
    case_event_count: int
    events: list[HistoryEventRecord]


class AppStreamSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    immutable_append_only: bool = True
    parent_baseline_head: str
    event_count: int
    current_head: str
    replay_valid: bool
    replay_error: str | None = None
    events: list[HistoryEventRecord]


class InvestigationHistoryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    package_uid: str
    integrity_note: str = (
        "Hash-chain integrity verifies recorded event continuity, "
        "not the correctness of underlying evidence."
    )
    writes_allowed: bool = True
    integrity_error: str | None = None
    baseline: BaselineStreamSection
    app_stream: AppStreamSection


class AppendReviewerNoteRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    note: str = Field(min_length=1, max_length=4000)
    reviewer_id: str | None = Field(default=None, max_length=128)
    requested_disposition: str | None = Field(default=None, max_length=64)
    expected_app_head_hash: str | None = Field(default=None, max_length=128)
    expected_app_event_count: int | None = Field(default=None, ge=0)


class AppendReviewerNoteResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    event: HistoryEventRecord
    app_stream: AppStreamSection


def _ensure_app_events_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            case_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            reviewer_id TEXT NOT NULL,
            note TEXT NOT NULL,
            disposition_override TEXT,
            timestamp_utc TEXT NOT NULL,
            previous_event_hash TEXT NOT NULL,
            event_hash TEXT NOT NULL,
            raw_json TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _load_baseline_chain(repo_root: Path) -> tuple[bool, str | None, int, str, list[dict[str, Any]]]:
    """Load and verify the frozen 162-event baseline without mutating it."""
    paths = get_paths(repo_root)
    hist_path = paths["hist_162_jsonl"]
    if not hist_path.exists():
        return False, f"Missing baseline history file: {hist_path.name}", 0, EXPECTED_FROZEN_HEAD, []

    try:
        raw_lines = [ln for ln in hist_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError as exc:
        return False, f"Unable to read baseline history: {exc}", 0, EXPECTED_FROZEN_HEAD, []

    if len(raw_lines) != EXPECTED_FROZEN_BASELINE_COUNT:
        return (
            False,
            f"Expected {EXPECTED_FROZEN_BASELINE_COUNT} baseline events, found {len(raw_lines)}.",
            len(raw_lines),
            EXPECTED_FROZEN_HEAD,
            [],
        )

    parsed_events: list[dict[str, Any]] = []
    prev_hash = "GENESIS"
    try:
        for idx, line in enumerate(raw_lines):
            ev = json.loads(line)
            if not isinstance(ev, dict):
                raise ValueError(f"Baseline event at index {idx} is not a JSON object.")
            if "previous_event_hash" in ev and ev["previous_event_hash"] is not None:
                if ev["previous_event_hash"] != prev_hash:
                    raise ValueError(f"Baseline hash chain mismatch at event {ev.get('event_id', idx)}.")
            parsed_events.append(ev)
            prev_hash = sha256_obj(ev)
    except Exception as exc:
        return False, f"Baseline event chain verification failed: {exc}", len(raw_lines), prev_hash, parsed_events

    if prev_hash != EXPECTED_FROZEN_HEAD:
        return (
            False,
            f"Baseline head hash mismatch: got {prev_hash}, expected {EXPECTED_FROZEN_HEAD}.",
            len(parsed_events),
            prev_hash,
            parsed_events,
        )

    # Also run existing provenance verifier for consistency
    try:
        verify_baseline_162_log(repo_root)
    except Exception as exc:
        return False, f"Baseline provenance check failed: {exc}", len(parsed_events), prev_hash, parsed_events

    return True, None, len(parsed_events), prev_hash, parsed_events


def _load_app_stream_rows(conn: sqlite3.Connection, case_id: str | None = None) -> list[dict[str, Any]]:
    _ensure_app_events_table(conn)
    if case_id:
        rows = conn.execute(
            """
            SELECT event_id, case_id, event_type, reviewer_id, note,
                   disposition_override, timestamp_utc, previous_event_hash, event_hash, raw_json
            FROM app_events
            WHERE case_id = ?
            ORDER BY id ASC
            """,
            (case_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT event_id, case_id, event_type, reviewer_id, note,
                   disposition_override, timestamp_utc, previous_event_hash, event_hash, raw_json
            FROM app_events
            ORDER BY id ASC
            """
        ).fetchall()

    records: list[dict[str, Any]] = []
    for r in rows:
        raw_obj: dict[str, Any] = {}
        if r["raw_json"]:
            try:
                parsed = json.loads(r["raw_json"])
                if isinstance(parsed, dict):
                    raw_obj = parsed
            except json.JSONDecodeError:
                raw_obj = {}
        records.append(
            {
                "event_id": r["event_id"],
                "case_id": r["case_id"],
                "event_type": r["event_type"],
                "reviewer_id": r["reviewer_id"],
                "note": r["note"],
                "disposition_override": r["disposition_override"],
                "timestamp_utc": r["timestamp_utc"],
                "previous_event_hash": r["previous_event_hash"],
                "event_hash": r["event_hash"],
                "raw": raw_obj,
            }
        )
    return records


def _verify_app_stream(
    all_app_rows: list[dict[str, Any]],
    baseline_head: str,
) -> tuple[bool, str | None, str]:
    """Verify deterministic continuity of all app_events anchored to baseline_head."""
    expected_prev = baseline_head
    current_head = baseline_head
    for idx, row in enumerate(all_app_rows):
        prev_h = row.get("previous_event_hash")
        ev_h = row.get("event_hash")
        if prev_h != expected_prev:
            return (
                False,
                f"App event chain break at index {idx} ({row.get('event_id')}): previous_event_hash mismatch.",
                current_head,
            )
        raw_payload = row.get("raw") or {}
        if raw_payload:
            # Payload stored in raw_json may or may not include event_hash
            payload_without_hash = {k: v for k, v in raw_payload.items() if k != "event_hash"}
            recomputed = sha256_obj(payload_without_hash)
            if ev_h and ev_h != recomputed:
                return (
                    False,
                    f"App event hash mismatch at event {row.get('event_id')}.",
                    current_head,
                )
        if not ev_h:
            return False, f"Missing event_hash on app event {row.get('event_id')}.", current_head
        current_head = str(ev_h)
        expected_prev = current_head
    return True, None, current_head


def _to_baseline_history_record(ev: dict[str, Any]) -> HistoryEventRecord:
    evidence_refs: list[str] = []
    for key in ("package_uid", "register_sha256", "rule_version"):
        val = ev.get(key)
        if isinstance(val, str) and val.strip():
            evidence_refs.append(f"{key}:{val.strip()}")

    prev_state = ev.get("from_state") if isinstance(ev.get("from_state"), str) else ev.get("previous_state")
    new_state = ev.get("to_state") if isinstance(ev.get("to_state"), str) else ev.get("new_state")
    disp = ev.get("disposition") if isinstance(ev.get("disposition"), str) else None
    rationale = ev.get("rationale") or ev.get("note") or ev.get("rule_version")
    ev_hash = ev.get("event_hash") if isinstance(ev.get("event_hash"), str) else sha256_obj(ev)

    return HistoryEventRecord(
        event_id=str(ev.get("event_id") or "BASELINE_EVENT"),
        event_type=str(ev.get("event_type") or "BASELINE_EVENT"),
        timestamp_utc=str(ev["timestamp_utc"]) if ev.get("timestamp_utc") else None,
        actor=str(ev["actor"]) if ev.get("actor") else "frozen_baseline",
        previous_state=str(prev_state) if prev_state else None,
        new_state=str(new_state) if new_state else None,
        disposition=disp,
        evidence_refs=evidence_refs,
        rationale=str(rationale) if rationale else None,
        previous_event_hash=str(ev["previous_event_hash"]) if ev.get("previous_event_hash") else None,
        event_hash=ev_hash,
        stream_type="FROZEN_BASELINE",
    )


def _to_app_history_record(row: dict[str, Any]) -> HistoryEventRecord:
    disp_override = row.get("disposition_override")
    rationale = row.get("note")
    if disp_override:
        rationale = f"{rationale} [requested_disposition={disp_override}]"
    return HistoryEventRecord(
        event_id=str(row["event_id"]),
        event_type=str(row["event_type"]),
        timestamp_utc=str(row["timestamp_utc"]) if row.get("timestamp_utc") else None,
        actor=str(row["reviewer_id"]) if row.get("reviewer_id") else None,
        previous_state=None,
        new_state=str(disp_override) if disp_override else None,
        disposition=str(disp_override) if disp_override else None,
        evidence_refs=[f"case_id:{row['case_id']}"],
        rationale=str(rationale) if rationale is not None else None,
        previous_event_hash=str(row["previous_event_hash"]) if row.get("previous_event_hash") else None,
        event_hash=str(row["event_hash"]) if row.get("event_hash") else None,
        stream_type="APPENDED_APP_EVENT",
    )


def _parse_queues(raw_queues: Any) -> list[str]:
    if isinstance(raw_queues, list):
        return [str(q) for q in raw_queues if str(q).strip()]
    if isinstance(raw_queues, str) and raw_queues.strip():
        try:
            parsed = json.loads(raw_queues)
            if isinstance(parsed, list):
                return [str(q) for q in parsed if str(q).strip()]
        except json.JSONDecodeError:
            pass
        return [part.strip() for part in raw_queues.split(",") if part.strip()]
    return []


def _parse_reasons(ev_obj: dict[str, Any]) -> list[str]:
    for key in ("screening_reasons", "reasons", "flags"):
        val = ev_obj.get(key)
        if isinstance(val, list):
            return [str(x) for x in val if str(x).strip()]
    return []


def list_workbench_investigations(repo_root: Path) -> list[InvestigationSummary]:
    conn, _ = _load_sqlite_conn(repo_root)
    try:
        _ensure_app_events_table(conn)
        app_counts_rows = conn.execute(
            "SELECT case_id, COUNT(*) AS cnt FROM app_events GROUP BY case_id"
        ).fetchall()
        app_counts = {str(r["case_id"]): int(r["cnt"]) for r in app_counts_rows}

        rows = conn.execute(
            """
            SELECT case_id, package_uid, mrl_id, source_state_key, ims_year,
                   queues_qualified_json, baseline_status, baseline_disposition,
                   verification_status, evidence_json, review_state_json
            FROM cases
            ORDER BY case_id ASC
            """
        ).fetchall()

        summaries: list[InvestigationSummary] = []
        for r in rows:
            ev_obj = _parse_json_dict(r["evidence_json"])
            rev_obj = _parse_json_dict(r["review_state_json"])
            queues = _parse_queues(r["queues_qualified_json"])
            reasons = _parse_reasons(ev_obj)
            if reasons:
                screening_summary = "; ".join(reasons)
            elif queues:
                screening_summary = f"Qualified in {', '.join(queues)}"
            else:
                screening_summary = "Screening criteria recorded in case evidence"

            case_status = str(
                rev_obj.get("review_status")
                or r["baseline_status"]
                or "QUEUED_AWAITING_SOURCE_ADJUDICATION"
            )
            cid = str(r["case_id"])
            summaries.append(
                InvestigationSummary(
                    case_id=cid,
                    package_uid=str(r["package_uid"] or ""),
                    mrl_id=str(r["mrl_id"] or ""),
                    state=str(r["source_state_key"] or ""),
                    ims_year=str(r["ims_year"] or ""),
                    queues=queues,
                    screening_summary=screening_summary,
                    disposition=str(r["baseline_disposition"] or "UNRESOLVED"),
                    verification_status=str(r["verification_status"] or "NOT_ATTEMPTED"),
                    case_status=case_status,
                    app_event_count=app_counts.get(cid, 0),
                )
            )
        return summaries
    finally:
        conn.close()


def get_workbench_investigation_detail(repo_root: Path, case_id: str) -> InvestigationDetail:
    conn, paths = _load_sqlite_conn(repo_root)
    try:
        _ensure_app_events_table(conn)
        row = conn.execute(
            """
            SELECT case_id, package_uid, mrl_id, source_state_key, ims_year,
                   queues_qualified_json, baseline_status, baseline_disposition,
                   verification_status, blocker_reason, evidence_json, review_state_json
            FROM cases
            WHERE case_id = ?
            """,
            (case_id,),
        ).fetchone()
        if row is None:
            raise WorkbenchLookupError(f"Unknown investigation case_id: {case_id}")

        all_app_rows = _load_app_stream_rows(conn)
        case_app_rows = [r for r in all_app_rows if r["case_id"] == case_id]
        _, _, _, base_head, _ = _load_baseline_chain(repo_root)
        _, _, app_head = _verify_app_stream(all_app_rows, base_head)

        ev_obj = _parse_json_dict(row["evidence_json"])
        rev_obj = _parse_json_dict(row["review_state_json"])
        meas_raw = ev_obj.get("measurements") if isinstance(ev_obj.get("measurements"), dict) else {}
        metrics = compute_signed_length_metrics(meas_raw)
        topo_raw = ev_obj.get("topology") if isinstance(ev_obj.get("topology"), dict) else {}

        seg_raw = topo_raw.get("n_segments") if topo_raw.get("n_segments") is not None else topo_raw.get("segment_count")
        segment_count = int(seg_raw) if isinstance(seg_raw, (int, float)) else None

        ranks_raw = ev_obj.get("selection_ranks")
        selection_ranks = ranks_raw if isinstance(ranks_raw, dict) else None

        latest_app_override = next(
            (r["disposition_override"] for r in reversed(case_app_rows) if r.get("disposition_override")),
            None,
        )
        current_app_state = (
            f"APP_OVERRIDE_REQUESTED:{latest_app_override}"
            if latest_app_override
            else ("HAS_APP_NOTES" if case_app_rows else "BASELINE_ONLY")
        )

        ver_status = str(row["verification_status"] or "NOT_ATTEMPTED")
        blocker = row["blocker_reason"]
        blocker_str = str(blocker).strip() if blocker and str(blocker).strip() else None
        if ver_status == "VERIFICATION_BLOCKED" and not blocker_str:
            blocker_str = (
                "Required external PMGSY/OMMAS corroboration records are absent from the local snapshot."
            )

        manifest_ref = str(paths.get("man_42_json").name) if paths.get("man_42_json") else "PEIARS_PMGSY_42_REVIEW_MANIFEST_V1.json"
        verified_hash: str | None = None
        man_path = paths.get("man_42_json")
        if man_path and man_path.exists():
            try:
                man_data = json.loads(man_path.read_text(encoding="utf-8"))
                if isinstance(man_data, dict) and isinstance(man_data.get("manifest_sha256"), str):
                    verified_hash = man_data["manifest_sha256"]
            except Exception:
                verified_hash = None

        return InvestigationDetail(
            identity=InvestigationIdentity(
                case_id=str(row["case_id"]),
                package_uid=str(row["package_uid"] or ""),
                mrl_id=str(row["mrl_id"] or ""),
                state=str(row["source_state_key"] or ""),
                ims_year=str(row["ims_year"] or ""),
            ),
            selection=InvestigationSelection(
                queues=_parse_queues(row["queues_qualified_json"]),
                screening_reasons=_parse_reasons(ev_obj),
                selection_ranks=selection_ranks,
            ),
            measurements=InvestigationMeasurements(
                proposed_l_km=metrics["proposed_l_km"],
                sum_geom_len_km=metrics["sum_geom_len_km"],
                signed_diff_km=metrics["length_diff_km"],
                relative_diff=metrics["length_rel_diff"],
                relative_diff_status=metrics["length_rel_diff_status"],
            ),
            topology=InvestigationTopology(
                exact_geometry_duplicate=bool(topo_raw.get("exact_geometry_duplicate", False)),
                linear_overlap=bool(topo_raw.get("linear_overlap", False)),
                invalid_geometry=bool(topo_raw.get("invalid_geometry", False)),
                segment_count=segment_count,
            ),
            review=InvestigationReview(
                baseline_case_status=str(rev_obj.get("review_status") or row["baseline_status"] or "REVIEWED"),
                baseline_disposition=str(row["baseline_disposition"] or "UNRESOLVED"),
                current_app_review_state=current_app_state,
                app_event_count=len(case_app_rows),
            ),
            verification=InvestigationVerification(
                verification_status=ver_status,
                independent_of_canonical_gis=bool(ev_obj.get("independent_of_canonical_gis", False)),
                blocker_reason=blocker_str,
            ),
            provenance=InvestigationProvenance(
                snapshot_id=DEFAULT_PMGSY_SNAPSHOT_ID,
                case_id=str(row["case_id"]),
                package_uid=str(row["package_uid"] or ""),
                frozen_baseline_event_count=EXPECTED_FROZEN_BASELINE_COUNT,
                app_event_count=len(case_app_rows),
                frozen_head_hash=EXPECTED_FROZEN_HEAD,
                app_head_hash=app_head,
                manifest_reference=manifest_ref,
                verified_manifest_hash=verified_hash,
            ),
        )
    finally:
        conn.close()


def get_workbench_investigation_history(repo_root: Path, case_id: str) -> InvestigationHistoryResponse:
    conn, _ = _load_sqlite_conn(repo_root)
    try:
        row = conn.execute(
            "SELECT case_id, package_uid FROM cases WHERE case_id = ?",
            (case_id,),
        ).fetchone()
        if row is None:
            raise WorkbenchLookupError(f"Unknown investigation case_id: {case_id}")

        all_app_rows = _load_app_stream_rows(conn)
        case_app_rows = [r for r in all_app_rows if r["case_id"] == case_id]
    finally:
        conn.close()

    base_ok, base_err, base_count, base_head, base_events = _load_baseline_chain(repo_root)
    app_ok, app_err, app_head = _verify_app_stream(all_app_rows, base_head)

    case_base_events = [
        _to_baseline_history_record(ev)
        for ev in base_events
        if str(ev.get("case_id") or "") == case_id
    ]
    case_app_events = [_to_app_history_record(r) for r in case_app_rows]

    integrity_error: str | None = None
    if not base_ok:
        integrity_error = base_err
    elif not app_ok:
        integrity_error = app_err

    return InvestigationHistoryResponse(
        case_id=str(row["case_id"]),
        package_uid=str(row["package_uid"] or ""),
        writes_allowed=integrity_error is None,
        integrity_error=integrity_error,
        baseline=BaselineStreamSection(
            immutable=True,
            event_count=base_count,
            head_hash=base_head,
            replay_valid=base_ok,
            replay_error=base_err,
            case_event_count=len(case_base_events),
            events=case_base_events,
        ),
        app_stream=AppStreamSection(
            immutable_append_only=True,
            parent_baseline_head=base_head,
            event_count=len(case_app_events),
            current_head=app_head,
            replay_valid=app_ok,
            replay_error=app_err,
            events=case_app_events,
        ),
    )


def append_workbench_reviewer_note(
    repo_root: Path,
    case_id: str,
    payload: AppendReviewerNoteRequest,
    *,
    authenticated_actor: str | None = None,
) -> AppendReviewerNoteResponse:
    clean_note = payload.note.strip()
    if not clean_note:
        raise InvestigationValidationError("Reviewer note must not be empty.")

    requested_disp = (payload.requested_disposition or "").strip() or None
    if requested_disp == "CONFIRMED_SOURCE_DEFECT":
        raise InvestigationValidationError(
            "Promotion to CONFIRMED_SOURCE_DEFECT requires verified independent non-PMGSY corroboration evidence, which is unavailable in the local snapshot."
        )
    if requested_disp is not None and requested_disp not in {
        "SUPPORTED_REVIEW_CANDIDATE",
        "UNRESOLVED",
    }:
        raise InvestigationValidationError(
            f"Unsupported or disallowed disposition transition: {requested_disp}"
        )

    base_ok, base_err, _, base_head, _ = _load_baseline_chain(repo_root)
    if not base_ok:
        raise InvestigationIntegrityError(
            base_err or "Frozen baseline integrity check failed.",
            code="BASELINE_INTEGRITY_FAILED",
        )

    conn, paths = _load_sqlite_conn(repo_root)
    try:
        _ensure_app_events_table(conn)
        case_row = conn.execute(
            "SELECT case_id, package_uid, baseline_disposition FROM cases WHERE case_id = ?",
            (case_id,),
        ).fetchone()
        if case_row is None:
            raise WorkbenchLookupError(f"Unknown investigation case_id: {case_id}")

        all_app_rows = _load_app_stream_rows(conn)
        app_ok, app_err, current_head = _verify_app_stream(all_app_rows, base_head)
        if not app_ok:
            raise InvestigationIntegrityError(
                app_err or "Application event stream integrity check failed.",
                code="APP_STREAM_INTEGRITY_FAILED",
            )

        case_app_rows = [r for r in all_app_rows if r["case_id"] == case_id]
        if payload.expected_app_head_hash is not None and payload.expected_app_head_hash != current_head:
            raise InvestigationConflictError(
                "Stale application event stream head hash; refresh history before submitting.",
                details={
                    "expected_app_head_hash": payload.expected_app_head_hash,
                    "current_app_head_hash": current_head,
                },
            )
        if payload.expected_app_event_count is not None and payload.expected_app_event_count != len(case_app_rows):
            raise InvestigationConflictError(
                "Stale case application event count; refresh history before submitting.",
                details={
                    "expected_app_event_count": payload.expected_app_event_count,
                    "current_app_event_count": len(case_app_rows),
                },
            )

        actor = (
            (authenticated_actor or "").strip()
            or (payload.reviewer_id or "").strip()
            or "workbench_reviewer"
        )
        now_utc = datetime.now(timezone.utc).isoformat()
        seq = len(all_app_rows) + 1
        digest_suffix = hashlib.sha256(
            f"{case_id}:{seq}:{now_utc}:{clean_note}".encode("utf-8")
        ).hexdigest()[:8]
        event_id = f"APP_EVT_{seq:04d}_{digest_suffix}"

        event_payload: dict[str, Any] = {
            "event_id": event_id,
            "timestamp_utc": now_utc,
            "case_id": case_id,
            "event_type": "REVIEWER_NOTE_APPENDED",
            "reviewer_id": actor,
            "note": clean_note,
            "baseline_disposition": str(case_row["baseline_disposition"] or "UNRESOLVED"),
            "disposition_override": requested_disp,
            "previous_event_hash": current_head,
        }
        event_hash = sha256_obj(event_payload)
        stored_raw = {**event_payload, "event_hash": event_hash}

        conn.execute(
            """
            INSERT INTO app_events (
                event_id, case_id, event_type, reviewer_id, note,
                disposition_override, timestamp_utc, previous_event_hash, event_hash, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                case_id,
                event_payload["event_type"],
                actor,
                clean_note,
                requested_disp,
                now_utc,
                current_head,
                event_hash,
                json.dumps(stored_raw),
            ),
        )
        conn.commit()

        app_jsonl_path = paths.get("app_hist_jsonl")
        if app_jsonl_path is not None:
            app_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with app_jsonl_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(stored_raw) + "\n")

        updated_all = _load_app_stream_rows(conn)
        updated_case = [r for r in updated_all if r["case_id"] == case_id]
        app_valid_after, app_err_after, new_head = _verify_app_stream(updated_all, base_head)
    finally:
        conn.close()

    created_record = _to_app_history_record(
        {
            "event_id": event_id,
            "case_id": case_id,
            "event_type": event_payload["event_type"],
            "reviewer_id": actor,
            "note": clean_note,
            "disposition_override": requested_disp,
            "timestamp_utc": now_utc,
            "previous_event_hash": current_head,
            "event_hash": event_hash,
        }
    )

    return AppendReviewerNoteResponse(
        case_id=case_id,
        event=created_record,
        app_stream=AppStreamSection(
            immutable_append_only=True,
            parent_baseline_head=base_head,
            event_count=len(updated_case),
            current_head=new_head,
            replay_valid=app_valid_after,
            replay_error=app_err_after,
            events=[_to_app_history_record(r) for r in updated_case],
        ),
    )
