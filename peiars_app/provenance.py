from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from peiars_app.db import get_paths


def sha256_obj(obj: dict) -> str:
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def verify_baseline_162_log(repo_root: Path | None = None) -> dict:
    root = repo_root or Path.cwd()
    p = get_paths(root)
    lines = [ln for ln in p["hist_162_jsonl"].read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 162, f"Expected 162 baseline events, got {len(lines)}"

    prev_hash = "GENESIS"
    case_states = {}
    for ln in lines:
        ev = json.loads(ln)
        if "previous_event_hash" in ev:
            assert ev["previous_event_hash"] == prev_hash, f"Baseline hash chain break at {ev.get('event_id')}"
        cid = ev["case_id"]
        if ev.get("event_type") == "CASE_CREATED_FROM_PRIORITY_QUEUE":
            case_states[cid] = {
                "status": ev.get("to_state", "QUEUED_AWAITING_SOURCE_ADJUDICATION"),
                "disposition": ev.get("disposition", "UNRESOLVED"),
            }
        else:
            cur = case_states.setdefault(cid, {"status": "QUEUED_AWAITING_SOURCE_ADJUDICATION", "disposition": "UNRESOLVED"})
            if "new_status" in ev:
                cur["status"] = ev["new_status"]
            if "disposition" in ev:
                cur["disposition"] = ev["disposition"]
        prev_hash = sha256_obj(ev)

    return {
        "valid": True,
        "event_count": len(lines),
        "head_hash": prev_hash,
        "cases_replayed": len(case_states),
        "case_states": case_states,
    }


def append_app_review_event(
    case_id: str,
    reviewer_id: str,
    note: str,
    disposition_override: str | None = None,
    repo_root: Path | None = None,
) -> dict:
    """Append a new review note/action to separate app stream without modifying the 162-event baseline."""
    assert note.strip(), "Reviewer note cannot be empty"
    root = repo_root or Path.cwd()
    p = get_paths(root)
    assert p["db_path"].exists(), "SQLite DB not initialized; run init_and_import_sqlite first"

    conn = sqlite3.connect(str(p["db_path"]))
    cur = conn.cursor()
    row = cur.execute("SELECT baseline_disposition FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    assert row is not None, f"Unknown case_id: {case_id}"
    base_disp = row[0]

    prev_row = cur.execute("SELECT event_hash FROM app_events ORDER BY id DESC LIMIT 1").fetchone()
    prev_hash = prev_row[0] if prev_row else verify_baseline_162_log(root)["head_hash"]

    seq = cur.execute("SELECT COUNT(*) FROM app_events").fetchone()[0] + 1
    now_utc = datetime.now(timezone.utc).isoformat()
    ev_id = f"APP_EVT_{seq:04d}"

    payload = {
        "event_id": ev_id,
        "timestamp_utc": now_utc,
        "case_id": case_id,
        "event_type": "REVIEWER_NOTE_OR_ACTION_APPENDED",
        "reviewer_id": reviewer_id.strip() or "local_reviewer",
        "note": note.strip(),
        "baseline_disposition": base_disp,
        "disposition_override": disposition_override if disposition_override else None,
        "previous_event_hash": prev_hash,
    }
    ev_hash = sha256_obj(payload)

    cur.execute(
        """
        INSERT INTO app_events (
            event_id, case_id, event_type, reviewer_id, note,
            disposition_override, timestamp_utc, previous_event_hash, event_hash, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ev_id,
            case_id,
            payload["event_type"],
            payload["reviewer_id"],
            payload["note"],
            payload["disposition_override"],
            now_utc,
            prev_hash,
            ev_hash,
            json.dumps(payload),
        ),
    )
    conn.commit()
    conn.close()

    with p["app_hist_jsonl"].open("a", encoding="utf-8") as f:
        f.write(json.dumps({**payload, "event_hash": ev_hash}) + "\n")

    return {**payload, "event_hash": ev_hash}


def get_case_history(case_id: str, repo_root: Path | None = None) -> dict:
    root = repo_root or Path.cwd()
    p = get_paths(root)
    base_lines = [ln for ln in p["hist_162_jsonl"].read_text(encoding="utf-8").splitlines() if ln.strip()]
    base_events = [json.loads(ln) for ln in base_lines if json.loads(ln).get("case_id") == case_id]

    app_events = []
    if p["db_path"].exists():
        conn = sqlite3.connect(str(p["db_path"]))
        rows = conn.execute(
            "SELECT raw_json FROM app_events WHERE case_id = ? ORDER BY id ASC",
            (case_id,),
        ).fetchall()
        conn.close()
        app_events = [json.loads(r[0]) for r in rows]

    return {
        "baseline_events": base_events,
        "app_events": app_events,
    }
