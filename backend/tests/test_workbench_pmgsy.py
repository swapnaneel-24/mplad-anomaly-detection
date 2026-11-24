from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _build_test_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "peiars_app").mkdir(parents=True, exist_ok=True)
    db_dir = repo / "peiars_app" / "data"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "peiars_core_v1.sqlite"
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
        CREATE TABLE baseline_events_readonly (
            seq_idx INTEGER PRIMARY KEY,
            event_id TEXT,
            case_id TEXT,
            event_type TEXT,
            timestamp_utc TEXT,
            raw_json TEXT
        );
        """
    )

    for i in range(1, 43):
        cid = f"CASE_{i:03d}"
        pkg_uid = f"pmgsy3_canonical_pkg_{i:03d}"
        disp = "SUPPORTED_REVIEW_CANDIDATE" if i <= 37 else "UNRESOLVED"
        ver = "VERIFICATION_BLOCKED" if i <= 12 else "NOT_ATTEMPTED"
        blocker = "No independent non-PMGSY corroboration source available" if i <= 12 else ""
        ev = {
            "measurements": {
                "proposed_l_km": 0.0 if i == 2 else 5.0 + i * 0.1,
                "sum_geom_len_km": 6.2 if i == 2 else 5.5 + i * 0.1,
            },
            "screening_reasons": ["length_ratio_r_out_of_range"],
            "topology": {
                "exact_geometry_duplicate": False,
                "linear_overlap": i == 3,
                "invalid_geometry": False,
                "n_segments": 2 if i == 1 else 1,
            },
            "independent_of_canonical_gis": False,
        }
        conn.execute(
            """
            INSERT INTO cases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                pkg_uid,
                str(240000 + i),
                "UTTAR_PRADESH" if i % 3 == 1 else ("MADHYA_PRADESH" if i % 3 == 2 else "BIHAR"),
                "2020",
                json.dumps(["Q_LENGTH_DISCREPANCY"]),
                "REVIEWED",
                disp,
                ver,
                blocker,
                json.dumps(ev),
                json.dumps({"review_status": "REVIEWED"}),
            ),
        )

    for ev_idx in range(1, 163):
        conn.execute(
            "INSERT INTO baseline_events_readonly VALUES (?, ?, ?, ?, ?, ?)",
            (
                ev_idx,
                f"EVT_{ev_idx:04d}",
                f"CASE_{((ev_idx - 1) % 42) + 1:03d}",
                "BASELINE_IMPORT",
                "2026-11-23T00:00:00Z",
                "{}",
            ),
        )
    conn.commit()
    conn.close()
    return repo


def _make_client(tmp_path: Path) -> TestClient:
    repo = _build_test_repo(tmp_path)
    app = create_app(settings=Settings(database_required=False))
    app.state.repo_root = repo
    return TestClient(app)


def test_workbench_snapshot_endpoint(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    resp = client.get("/api/v1/workbench/snapshots")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    snap = body["snapshots"][0]
    assert snap["snapshot_id"]
    assert snap["is_admitted_source_registry"] is False
    assert snap["complete_4361_population"] is False
    assert "4,361" in snap["record_scope"]


def test_workbench_packages_42_and_37_5_0_counts(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    resp = client.get("/api/v1/workbench/pmgsy/packages")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 42
    assert len(body["packages"]) == 42

    disp_counts: dict[str, int] = {}
    blocked_count = 0
    for p in body["packages"]:
        d = p["disposition"]
        disp_counts[d] = disp_counts.get(d, 0) + 1
        if p["verification_status"] == "VERIFICATION_BLOCKED":
            blocked_count += 1
        assert p["package_uid"] != "pmgsy3_up_241861"

    assert disp_counts.get("SUPPORTED_REVIEW_CANDIDATE", 0) == 37
    assert disp_counts.get("UNRESOLVED", 0) == 5
    assert disp_counts.get("CONFIRMED_SOURCE_DEFECT", 0) == 0
    assert blocked_count == 12


def test_workbench_package_detail_and_zero_denominator(tmp_path: Path) -> None:
    client = _make_client(tmp_path)

    resp_zero = client.get("/api/v1/workbench/pmgsy/packages/CASE_002")
    assert resp_zero.status_code == 200
    detail_zero = resp_zero.json()
    assert detail_zero["identity"]["case_id"] == "CASE_002"
    assert detail_zero["identity"]["package_uid"] == "pmgsy3_canonical_pkg_002"
    assert detail_zero["measurements"]["proposed_l_km"] == 0.0
    assert detail_zero["measurements"]["length_rel_diff_status"] == "UNDEFINED_ZERO_DENOMINATOR"
    assert detail_zero["measurements"]["length_rel_diff"] == "UNDEFINED_ZERO_DENOMINATOR"
    assert detail_zero["review"]["disposition"] != detail_zero["verification"]["verification_status"]


def test_workbench_not_found_and_no_path_traversal(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    assert client.get("/api/v1/workbench/pmgsy/packages/NONEXISTENT_999").status_code == 404
    assert client.get("/api/v1/workbench/snapshots/NONEXISTENT_SNAP").status_code == 404

    traversal = client.get("/api/v1/workbench/pmgsy/packages/..%2F..%2Fetc%2Fpasswd")
    assert traversal.status_code in (400, 404, 422)


def test_sources_registry_semantics_unchanged(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    resp = client.get("/api/v1/sources")
    assert resp.status_code == 200
    body = resp.json()
    assert "sources" in body and "count" in body
    source_ids = {s["source_id"] for s in body["sources"]}
    assert "pmgsy3_3state_v1_curated_42" not in source_ids
    for pkg_idx in range(1, 43):
        assert f"pmgsy3_canonical_pkg_{pkg_idx:03d}" not in source_ids
