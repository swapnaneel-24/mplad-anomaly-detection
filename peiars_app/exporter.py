from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from peiars_app.db import get_paths, sha256_file
from peiars_app.provenance import get_case_history, verify_baseline_162_log


def export_case_dossier(case_id: str, repo_root: Path | None = None) -> dict[str, Path]:
    root = repo_root or Path.cwd()
    p = get_paths(root)
    assert p["db_path"].exists(), "Database not initialized"

    conn = sqlite3.connect(str(p["db_path"]))
    row = conn.execute(
        """
        SELECT case_id, package_uid, mrl_id, source_state_key, ims_year,
               queues_qualified_json, baseline_status, baseline_disposition,
               verification_status, blocker_reason, evidence_json, review_state_json
        FROM cases WHERE case_id = ?
        """,
        (case_id,),
    ).fetchone()
    conn.close()
    assert row is not None, f"Case not found: {case_id}"

    replay_info = verify_baseline_162_log(root)
    hist = get_case_history(case_id, root)
    export_dir = p["data_dir"] / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    dossier = {
        "dossier_version": "PEIARS_CASE_DOSSIER_V1",
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "case": {
            "case_id": row[0],
            "package_uid": row[1],
            "mrl_id": row[2],
            "source_state_key": row[3],
            "ims_year": row[4],
            "queues_qualified": json.loads(row[5] or "[]"),
            "baseline_status": row[6],
            "baseline_disposition": row[7],
            "verification_status": row[8],
            "blocker_reason": row[9],
        },
        "evidence_record": json.loads(row[10] or "{}"),
        "review_state": json.loads(row[11] or "{}"),
        "provenance_verification": {
            "baseline_162_log_valid": replay_info["valid"],
            "baseline_162_head_hash": replay_info["head_hash"],
            "case_baseline_events": len(hist["baseline_events"]),
            "case_app_events": len(hist["app_events"]),
        },
        "artifact_hashes": {
            "PEIARS_PMGSY_42_CASES.json": sha256_file(p["cases_json"]),
            "PEIARS_PMGSY_EVIDENCE_RECORDS.json": sha256_file(p["ev_json"]),
            "PEIARS_PMGSY_REVIEW_STATES.csv": sha256_file(p["rs_csv"]),
            "PEIARS_PMGSY_DECISION_HISTORY.jsonl": sha256_file(p["hist_162_jsonl"]),
            "PEIARS_PMGSY_42_REVIEW_MANIFEST_V1.json": sha256_file(p["man_42_json"]),
        },
        "limitations": [
            "Desk-level dispositions do not assert external field/OMMAS source corroboration.",
            "VERIFICATION_BLOCKED indicates external PMGSY/OMMAS records are absent locally, not a confirmed source defect.",
            "CONFIRMED_SOURCE_DEFECT is not claimed without independent corroboration.",
        ],
    }

    json_out = export_dir / f"{case_id}_dossier.json"
    md_out = export_dir / f"{case_id}_dossier.md"
    json_out.write_text(json.dumps(dossier, indent=2), encoding="utf-8")

    md_lines = [
        f"# PEIARS Case Dossier — {case_id}",
        "",
        f"- **Exported At (UTC):** {dossier['exported_at_utc']}",
        f"- **Package UID:** `{row[1]}` | **MRL ID:** `{row[2]}` | **State:** `{row[3]}` | **IMS Year:** `{row[4]}`",
        f"- **Baseline Disposition:** `{row[7]}` | **Corroboration Verification Status:** `{row[8]}`",
        f"- **Verification Blocker:** {row[9] or 'None recorded'}",
        f"- **162-Event Baseline Log Verified:** `{replay_info['valid']}` (Head Hash: `{replay_info['head_hash']}`)",
        "",
        "## Limitations & Provenance Notice",
        "",
        *[f"- {lim}" for lim in dossier["limitations"]],
    ]
    md_out.write_text("\n".join(md_lines), encoding="utf-8")
    return {"json": json_out, "md": md_out}
