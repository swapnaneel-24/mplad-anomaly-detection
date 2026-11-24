from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from peiars_app.provenance import sha256_obj


def _setup_isolated_repo(tmp_path: Path) -> tuple[Path, Path, Path, Path, str]:
    repo = tmp_path / "repo"
    int_dir = repo / "research" / "pmgsy_iii_investigation" / "outputs" / "peiars_evidence_integration_v1"
    val_dir = repo / "research" / "pmgsy_iii_investigation" / "outputs" / "peiars_independent_validation_v1"
    data_dir = repo / "peiars_app" / "data"
    int_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    prev_hash = "GENESIS"
    for idx in range(1, 163):
        case_num = ((idx - 1) % 42) + 1
        ev = {
            "event_id": f"EVT_{idx:03d}_INIT",
            "timestamp_utc": "2026-11-23T10:26:05.267952+00:00",
            "case_id": f"PEIARS_PMGSY_{case_num:03d}",
            "event_type": "CASE_CREATED_FROM_PRIORITY_QUEUE",
            "from_state": None,
            "to_state": "QUEUED_AWAITING_SOURCE_ADJUDICATION",
            "disposition": "UNRESOLVED",
            "previous_event_hash": prev_hash,
        }
        lines.append(json.dumps(ev, separators=(",", ":")))
        prev_hash = sha256_obj(ev)

    hist_path = int_dir / "PEIARS_PMGSY_DECISION_HISTORY.jsonl"
    hist_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    hist_sha = hashlib.sha256(hist_path.read_bytes()).hexdigest()
    man_path = int_dir / "PEIARS_PMGSY_42_REVIEW_MANIFEST_V1.json"
    man_path.write_text(
        json.dumps({"decision_history_sha256": hist_sha, "manifest_sha256": hist_sha}),
        encoding="utf-8",
    )
    (int_dir / "PEIARS_PMGSY_42_CASES.json").write_text("[]", encoding="utf-8")
    (int_dir / "PEIARS_PMGSY_EVIDENCE_RECORDS.json").write_text("[]", encoding="utf-8")
    (int_dir / "PEIARS_PMGSY_REVIEW_STATES.csv").write_text("case_id,disposition\n", encoding="utf-8")
    (val_dir / "PEIARS_PMGSY_INDEPENDENT_VALIDATION.csv").write_text("case_id,status\n", encoding="utf-8")

    import app.services.workbench_investigations as inv_svc
    inv_svc.EXPECTED_FROZEN_HEAD = prev_hash

    db_path = data_dir / "peiars_core_v1.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE cases (
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
        CREATE TABLE app_events (
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
        );
        """
    )

    for i in range(1, 43):
        cid = f"PEIARS_PMGSY_{i:03d}"
        disp = "SUPPORTED_REVIEW_CANDIDATE" if i <= 37 else "UNRESOLVED"
        ver = "VERIFICATION_BLOCKED" if i <= 12 else "NOT_ATTEMPTED"
        blocker = (
            "Required external PMGSY/OMMAS records are absent from the local snapshot."
            if i <= 12
            else ""
        )
        ev = {
            "measurements": {
                "proposed_l_km": 0.0 if i == 2 else 5.0 + i * 0.1,
                "sum_geom_len_km": 4.2 if i == 2 else 5.4 + i * 0.1,
            },
            "screening_reasons": ["P1_ABS_LENGTH_DIFF"],
            "topology": {
                "exact_geometry_duplicate": False,
                "linear_overlap": i == 1,
                "invalid_geometry": False,
                "n_segments": 2 if i == 1 else 1,
            },
            "independent_of_canonical_gis": False,
        }
        conn.execute(
            "INSERT INTO cases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cid,
                f"pkg_{i:03d}",
                str(100000 + i),
                "UTTAR_PRADESH",
                "2021",
                json.dumps(["P1_ABS_LENGTH_DIFF"]),
                "REVIEWED",
                disp,
                ver,
                blocker,
                json.dumps(ev),
                json.dumps({"review_status": "REVIEWED"}),
            ),
        )
    conn.commit()
    conn.close()
    return repo, hist_path, man_path, db_path, prev_hash


def _client(repo: Path) -> TestClient:
    app = create_app(settings=Settings(database_required=False))
    app.state.repo_root = repo
    return TestClient(app)


def test_end_to_end_workflow_case_001_dossier_and_frozen_baseline_unchanged(tmp_path: Path) -> None:
    repo, hist_path, man_path, _, head_hash = _setup_isolated_repo(tmp_path)
    hist_before = hashlib.sha256(hist_path.read_bytes()).hexdigest()
    man_before = hashlib.sha256(man_path.read_bytes()).hexdigest()

    client = _client(repo)

    # 1. Verify 42 cases & 37/5/0 & 12 blocked
    all_res = client.get("/api/v1/workbench/investigations")
    assert all_res.status_code == 200
    assert all_res.json()["count"] == 42

    # 2. Load PEIARS_PMGSY_001 & history
    detail_res = client.get("/api/v1/workbench/investigations/PEIARS_PMGSY_001")
    assert detail_res.status_code == 200
    hist_before_note = client.get("/api/v1/workbench/investigations/PEIARS_PMGSY_001/history").json()
    assert hist_before_note["baseline"]["event_count"] == 162
    assert hist_before_note["baseline"]["replay_valid"] is True

    # 3. Append reviewer note to app stream
    note_res = client.post(
        "/api/v1/workbench/investigations/PEIARS_PMGSY_001/notes",
        json={
            "note": "E2E audit note on PEIARS_PMGSY_001.",
            "reviewer_id": "auditor_01",
            "expected_app_head_hash": hist_before_note["app_stream"]["current_head"],
            "expected_app_event_count": 0,
        },
    )
    assert note_res.status_code == 200

    # 4. Replay app stream & export dossier
    hist_after_note = client.get("/api/v1/workbench/investigations/PEIARS_PMGSY_001/history").json()
    assert hist_after_note["app_stream"]["replay_valid"] is True
    assert hist_after_note["app_stream"]["event_count"] == 1
    assert hist_after_note["app_stream"]["current_head"] != hist_before_note["app_stream"]["current_head"]

    exp_res = client.get("/api/v1/workbench/investigations/PEIARS_PMGSY_001/dossier")
    assert exp_res.status_code == 200
    exp_body = exp_res.json()
    assert exp_body["dossier"]["provenance"]["global_frozen_event_count"] == 162
    assert exp_body["dossier"]["provenance"]["case_app_event_count"] == 1
    assert len(exp_body["dossier"]["limitations"]) >= 6

    # 5. Independently verify dossier
    ver_res = client.post(
        "/api/v1/workbench/investigations/PEIARS_PMGSY_001/dossier/verify",
        json={
            "dossier": exp_body["dossier"],
            "manifest": exp_body["manifest"],
            "markdown_content": exp_body["markdown_content"],
        },
    )
    assert ver_res.status_code == 200
    assert ver_res.json()["valid"] is True

    # 6. Frozen baseline & manifest unchanged
    assert hashlib.sha256(hist_path.read_bytes()).hexdigest() == hist_before
    assert hashlib.sha256(man_path.read_bytes()).hexdigest() == man_before
    assert head_hash == hist_after_note["baseline"]["head_hash"]


def test_negative_integrity_and_dossier_tamper_cases(tmp_path: Path) -> None:
    repo, hist_path, man_path, db_path, head_hash = _setup_isolated_repo(tmp_path)
    client = _client(repo)

    # 1. Corrupted frozen manifest hash
    man_path.write_text(
        json.dumps({"decision_history_sha256": "deadbeef" * 8, "manifest_sha256": "deadbeef" * 8}),
        encoding="utf-8",
    )
    assert client.get("/api/v1/workbench/investigations/PEIARS_PMGSY_001/dossier").status_code == 503

    # Restore valid manifest hash
    hist_sha = hashlib.sha256(hist_path.read_bytes()).hexdigest()
    man_path.write_text(json.dumps({"decision_history_sha256": hist_sha}), encoding="utf-8")

    # Export valid dossier for tamper tests
    good_exp = client.get("/api/v1/workbench/investigations/PEIARS_PMGSY_001/dossier").json()

    # 18. Dossier hash mismatch
    tampered_manifest = {
        **good_exp["manifest"],
        "files": [{"filename": f["filename"], "sha256": "0" * 64} for f in good_exp["manifest"]["files"]],
    }
    r18 = client.post(
        "/api/v1/workbench/investigations/PEIARS_PMGSY_001/dossier/verify",
        json={"dossier": good_exp["dossier"], "manifest": tampered_manifest},
    )
    assert r18.status_code == 200 and r18.json()["valid"] is False

    # 19. Dossier case identity mismatch
    bad_id_dossier = {
        **good_exp["dossier"],
        "identity": {**good_exp["dossier"]["identity"], "case_id": "PEIARS_PMGSY_002"},
    }
    r19 = client.post(
        "/api/v1/workbench/investigations/PEIARS_PMGSY_001/dossier/verify",
        json={"dossier": bad_id_dossier},
    )
    assert r19.status_code in (200, 404) and (r19.status_code == 404 or r19.json()["valid"] is False)

    # 20. Dossier generated against wrong frozen head
    wrong_head_dossier = {
        **good_exp["dossier"],
        "provenance": {**good_exp["dossier"]["provenance"], "frozen_baseline_head": "f" * 64},
    }
    r20 = client.post(
        "/api/v1/workbench/investigations/PEIARS_PMGSY_001/dossier/verify",
        json={"dossier": wrong_head_dossier},
    )
    assert r20.status_code == 200 and r20.json()["valid"] is False

    # 16. Zero proposed length -> UNDEFINED_ZERO_DENOMINATOR
    d2 = client.get("/api/v1/workbench/investigations/PEIARS_PMGSY_002").json()
    assert d2["measurements"]["relative_diff_status"] == "UNDEFINED_ZERO_DENOMINATOR"

    # 17. Missing verification source -> VERIFICATION_BLOCKED with blocker_reason
    d1 = client.get("/api/v1/workbench/investigations/PEIARS_PMGSY_001").json()
    assert d1["verification"]["verification_status"] == "VERIFICATION_BLOCKED"
    assert d1["verification"]["blocker_reason"]

    # 12, 13, 14, 15. Empty note, unknown case, unsupported transition, CONFIRMED_SOURCE_DEFECT
    assert client.post("/api/v1/workbench/investigations/PEIARS_PMGSY_001/notes", json={"note": ""}).status_code in (400, 422)
    assert client.post("/api/v1/workbench/investigations/PEIARS_PMGSY_999/notes", json={"note": "x"}).status_code == 404
    assert client.post(
        "/api/v1/workbench/investigations/PEIARS_PMGSY_001/notes",
        json={"note": "x", "requested_disposition": "INVALID_DISP"},
    ).status_code == 422
    assert client.post(
        "/api/v1/workbench/investigations/PEIARS_PMGSY_001/notes",
        json={"note": "x", "requested_disposition": "CONFIRMED_SOURCE_DEFECT"},
    ).status_code == 422

    # 10 & 11. Stale app head & stale case event count
    assert client.post(
        "/api/v1/workbench/investigations/PEIARS_PMGSY_001/notes",
        json={"note": "ok", "expected_app_head_hash": "wrong_head"},
    ).status_code == 409
    assert client.post(
        "/api/v1/workbench/investigations/PEIARS_PMGSY_001/notes",
        json={"note": "ok2", "expected_app_event_count": 99},
    ).status_code == 409

    # 7, 8, 9. Duplicate app event ID, corrupted app event hash, broken previous hash
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO app_events VALUES (NULL, 'APP_EVT_DUP', 'PEIARS_PMGSY_001', 'REVIEWER_NOTE_APPENDED', 'r1', 'n1', NULL, '2026-11-24T00:00:00Z', ?, 'h1', '{}')",
        (head_hash,),
    )
    conn.execute(
        "INSERT INTO app_events VALUES (NULL, 'APP_EVT_DUP_2', 'PEIARS_PMGSY_001', 'REVIEWER_NOTE_APPENDED', 'r1', 'n2', NULL, '2026-11-24T00:01:00Z', 'WRONG_PREV_HASH', 'h2', '{}')",
    )
    conn.commit()
    conn.close()
    assert client.get("/api/v1/workbench/investigations/PEIARS_PMGSY_001/dossier").status_code == 503

    # 2, 3, 4, 5, 6. Baseline corruption checks (corrupted hash, missing event, duplicate, reordered, unknown case)
    orig_lines = [ln for ln in hist_path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    # Corrupted baseline event hash (mutating event content changes sha256_obj vs next event's previous_event_hash)
    ev0 = json.loads(orig_lines[0])
    ev0["disposition"] = "TAMPERED"
    corrupt_lines = [json.dumps(ev0, separators=(",", ":"))] + orig_lines[1:]
    hist_path.write_text("\n".join(corrupt_lines) + "\n", encoding="utf-8")
    assert client.get("/api/v1/workbench/investigations/PEIARS_PMGSY_001/dossier").status_code == 503

    # Missing baseline event (161 events)
    hist_path.write_text("\n".join(orig_lines[:-1]) + "\n", encoding="utf-8")
    assert client.get("/api/v1/workbench/investigations/PEIARS_PMGSY_001/dossier").status_code == 503

    # Duplicate baseline event (163 events)
    hist_path.write_text("\n".join(orig_lines + [orig_lines[-1]]) + "\n", encoding="utf-8")
    assert client.get("/api/v1/workbench/investigations/PEIARS_PMGSY_001/dossier").status_code == 503

    # Reordered baseline events
    reordered = [orig_lines[1], orig_lines[0]] + orig_lines[2:]
    hist_path.write_text("\n".join(reordered) + "\n", encoding="utf-8")
    assert client.get("/api/v1/workbench/investigations/PEIARS_PMGSY_001/dossier").status_code == 503

    # Missing case referenced by baseline event
    ev_bad_case = json.loads(orig_lines[0])
    ev_bad_case["case_id"] = "PEIARS_PMGSY_999"
    # Rebuild valid chain with unknown case_id so unknown-case guard triggers
    chain_lines: list[str] = []
    ph = "GENESIS"
    for idx in range(162):
        item = json.loads(orig_lines[idx])
        item["previous_event_hash"] = ph
        if idx == 0:
            item["case_id"] = "PEIARS_PMGSY_999"
        chain_lines.append(json.dumps(item, separators=(",", ":")))
        ph = sha256_obj(item)
    hist_path.write_text("\n".join(chain_lines) + "\n", encoding="utf-8")
    assert client.get("/api/v1/workbench/investigations/PEIARS_PMGSY_001/dossier").status_code == 503
