from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
import pandas as pd


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def get_paths(repo_root: Path) -> dict[str, Path]:
    int_dir = repo_root / "research/pmgsy_iii_investigation/outputs/peiars_evidence_integration_v1"
    val_dir = repo_root / "research/pmgsy_iii_investigation/outputs/peiars_independent_validation_v1"
    app_dir = repo_root / "peiars_app"
    data_dir = app_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return {
        "repo_root": repo_root,
        "int_dir": int_dir,
        "val_dir": val_dir,
        "app_dir": app_dir,
        "data_dir": data_dir,
        "db_path": data_dir / "peiars_core_v1.sqlite",
        "cases_json": int_dir / "PEIARS_PMGSY_42_CASES.json",
        "ev_json": int_dir / "PEIARS_PMGSY_EVIDENCE_RECORDS.json",
        "rs_csv": int_dir / "PEIARS_PMGSY_REVIEW_STATES.csv",
        "hist_162_jsonl": int_dir / "PEIARS_PMGSY_DECISION_HISTORY.jsonl",
        "man_42_json": int_dir / "PEIARS_PMGSY_42_REVIEW_MANIFEST_V1.json",
        "corr_reg_json": val_dir / "PEIARS_PMGSY_EXTERNAL_EVIDENCE_REGISTER_V1.json",
        "corr_man_json": val_dir / "PEIARS_PMGSY_CORROBORATION_MANIFEST_V1.json",
        "app_hist_jsonl": data_dir / "app_decision_history.jsonl",
    }


def init_and_import_sqlite(repo_root: Path | None = None) -> dict:
    root = repo_root or Path.cwd()
    p = get_paths(root)

    for req in [p["cases_json"], p["ev_json"], p["rs_csv"], p["hist_162_jsonl"], p["man_42_json"]]:
        assert req.exists(), f"Missing required frozen file: {req}"

    man_42 = json.loads(p["man_42_json"].read_text(encoding="utf-8"))
    for fname, expected_hash in man_42.get("hashes", {}).items():
        fpath = p["int_dir"] / fname
        if fpath.exists():
            actual = sha256_file(fpath)
            assert actual == expected_hash, f"Hash mismatch for {fname}: {actual} != {expected_hash}"

    cases = json.loads(p["cases_json"].read_text(encoding="utf-8"))
    ev_recs = json.loads(p["ev_json"].read_text(encoding="utf-8"))
    rs_df = pd.read_csv(p["rs_csv"]).set_index("case_id")

    corr_map = {}
    if p["corr_reg_json"].exists():
        corr_data = json.loads(p["corr_reg_json"].read_text(encoding="utf-8"))
        for rec in corr_data.get("records", []):
            corr_map[rec["case_id"]] = rec

    ev_map = {e["case_id"]: e for e in ev_recs}

    conn = sqlite3.connect(str(p["db_path"]))
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS cases (
            case_id TEXT PRIMARY KEY,
            package_uid TEXT NOT NULL,
            mrl_id TEXT,
            source_state_key TEXT,
            ims_year TEXT,
            queues_qualified_json TEXT,
            baseline_status TEXT,
            baseline_disposition TEXT,
            verification_status TEXT,
            blocker_reason TEXT,
            evidence_json TEXT,
            review_state_json TEXT
        );

        CREATE TABLE IF NOT EXISTS baseline_events_readonly (
            seq_idx INTEGER PRIMARY KEY,
            event_id TEXT,
            case_id TEXT,
            event_type TEXT,
            timestamp_utc TEXT,
            raw_json TEXT
        );

        CREATE TABLE IF NOT EXISTS app_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE,
            case_id TEXT,
            event_type TEXT,
            reviewer_id TEXT,
            note TEXT,
            disposition_override TEXT,
            timestamp_utc TEXT,
            previous_event_hash TEXT,
            event_hash TEXT,
            raw_json TEXT
        );
    """)

    cur.execute("DELETE FROM cases")
    for c in cases:
        cid = c["case_id"]
        corr = corr_map.get(cid, {})
        v_status = corr.get("verification_status", "NOT_ATTEMPTED")
        blocker = corr.get("blocker_reason", "")
        r_state = rs_df.loc[cid].to_dict() if cid in rs_df.index else {}
        cur.execute(
            """
            INSERT INTO cases (
                case_id, package_uid, mrl_id, source_state_key, ims_year,
                queues_qualified_json, baseline_status, baseline_disposition,
                verification_status, blocker_reason, evidence_json, review_state_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                c["package_uid"],
                str(c.get("mrl_id", "")),
                str(c.get("source_state_key", "")),
                str(c.get("ims_year", "")),
                json.dumps(c.get("queues_qualified", [])),
                str(c.get("case_status", "REVIEWED")),
                str(c.get("adjudication_outcome", "UNRESOLVED")),
                v_status,
                blocker,
                json.dumps(ev_map.get(cid, {})),
                json.dumps(r_state, default=str),
            ),
        )

    cur.execute("DELETE FROM baseline_events_readonly")
    lines = [ln for ln in p["hist_162_jsonl"].read_text(encoding="utf-8").splitlines() if ln.strip()]
    for idx, ln in enumerate(lines, start=1):
        ev = json.loads(ln)
        cur.execute(
            """
            INSERT INTO baseline_events_readonly (seq_idx, event_id, case_id, event_type, timestamp_utc, raw_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (idx, ev.get("event_id", f"BASE_{idx:04d}"), ev.get("case_id", ""), ev.get("event_type", ""), ev.get("timestamp_utc", ""), ln),
        )

    conn.commit()

    counts_df = pd.read_sql_query(
        "SELECT baseline_disposition, COUNT(*) AS n FROM cases GROUP BY baseline_disposition",
        conn,
    )
    conn.close()

    disp_dict = dict(zip(counts_df["baseline_disposition"], counts_df["n"]))
    assert len(cases) == 42
    assert disp_dict.get("SUPPORTED_REVIEW_CANDIDATE", 0) == 37
    assert disp_dict.get("UNRESOLVED", 0) == 5
    assert disp_dict.get("CONFIRMED_SOURCE_DEFECT", 0) == 0

    return {
        "db_path": str(p["db_path"]),
        "cases_imported": len(cases),
        "baseline_events_loaded": len(lines),
        "dispositions": disp_dict,
    }
