from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def to_md_table(df: pd.DataFrame) -> str:
    headers = [str(c) for c in df.columns]
    rows = [[str(v) for v in r] for r in df.itertuples(index=False, name=None)]
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)] if rows else [len(h) for h in headers]
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    hdr = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    body = ["| " + " | ".join(r[i].ljust(widths[i]) for i, h in enumerate(headers)) + " |" for r in rows]
    return "\n".join([hdr, sep, *body])


def find_p0_topology_uids(reg_df: pd.DataFrame, v2_df: pd.DataFrame) -> set[str]:
    """Find the 6 topology-flagged package_uids across register and Option B v2 tables."""
    combined = reg_df.merge(
        v2_df[[c for c in v2_df.columns if c not in reg_df.columns or c == "package_uid"]],
        on="package_uid",
        how="left",
    )
    candidate_cols = [
        c for c in combined.columns
        if any(k in c.lower() for k in ["topo", "dup", "overlap", "collaps", "invalid", "self_inter", "reason", "flag", "audit", "rule"])
    ]
    print("Candidate flag/topology columns:", candidate_cols)

    # Check each candidate column for any non-zero/non-clean/non-false values
    for c in candidate_cols:
        s = combined[c]
        if pd.api.types.is_bool_dtype(s):
            m = s.fillna(False)
        elif pd.api.types.is_numeric_dtype(s):
            m = pd.to_numeric(s, errors="coerce").fillna(0) != 0
        else:
            txt = s.fillna("").astype(str).str.strip().str.lower()
            m = ~txt.isin(["", "0", "false", "none", "nan", "ok", "valid", "clean", "pass", "normal"])
        cnt = int(m.sum())
        if 0 < cnt <= 50:
            print(f"  Column '{c}' non-trivial count: {cnt} | sample values: {s[m].head(6).tolist()}")

    # Specifically match topology keywords across candidate columns
    topo_mask = pd.Series(False, index=combined.index)
    for c in candidate_cols:
        s = combined[c]
        if pd.api.types.is_bool_dtype(s) and ("topo" in c.lower() or "dup" in c.lower() or "overlap" in c.lower() or "collaps" in c.lower()):
            topo_mask = topo_mask | s.fillna(False)
        elif pd.api.types.is_numeric_dtype(s) and ("topo" in c.lower() or "dup" in c.lower() or "overlap" in c.lower() or "collaps" in c.lower()):
            topo_mask = topo_mask | (pd.to_numeric(s, errors="coerce").fillna(0) != 0)
        else:
            txt = s.fillna("").astype(str).str.lower()
            kw = txt.str.contains(r"topo|dup|overlap|collaps|invalid|self.inter|241861", regex=True)
            if int(kw.sum()) > 0 and int(kw.sum()) <= 20:
                topo_mask = topo_mask | kw

    uids = set(combined.loc[topo_mask, "package_uid"].astype(str))
    return uids


def main() -> None:
    repo_root = Path.cwd()
    snap_dir = repo_root / "data/canonical/pmgsy_v1/pmgsy3_3state_v1"
    v2_csv = snap_dir / "scoring_option_b_v2/packages_p_scored_option_b_v2.csv"
    seg_parquet = snap_dir / "segments.parquet"
    opt_b_dir = repo_root / "research/pmgsy_iii_investigation/outputs/option_b_v2_evidence_review"
    reg_csv = opt_b_dir / "PMGSY_EVIDENCE_REGISTER_V2.csv"
    out_dir = repo_root / "research/pmgsy_iii_investigation/outputs/peiars_evidence_integration_v1"
    out_dir.mkdir(parents=True, exist_ok=True)

    v2_df = pd.read_csv(v2_csv)
    reg_df = pd.read_csv(reg_csv)
    assert len(reg_df) == 4361 and reg_df["package_uid"].nunique() == 4361

    # Attach ims_year from Option B v2 to resolve blank cohort_year_batch
    ims_map = v2_df.set_index("package_uid")["ims_year"].astype(str)
    reg_df["ims_year"] = reg_df["package_uid"].astype(str).map(ims_map).fillna("UNSPECIFIED")
    reg_df["cohort_year_batch"] = reg_df["ims_year"]

    p0_uids = find_p0_topology_uids(reg_df, v2_df)
    p0_idx = list(reg_df[reg_df["package_uid"].astype(str).isin(p0_uids)].index)
    print(f"Found P0 topology count: {len(p0_idx)}")

    reg_df["_abs_diff"] = pd.to_numeric(reg_df["length_diff_km"], errors="coerce").abs()
    reg_df["_abs_rel"] = pd.to_numeric(reg_df["length_rel_diff"], errors="coerce").abs()
    p1_df = reg_df.sort_values("_abs_diff", ascending=False).head(25)
    p2_df = reg_df.sort_values("_abs_rel", ascending=False).head(25)

    p1_ranks = {int(idx): r + 1 for r, idx in enumerate(p1_df.index)}
    p2_ranks = {int(idx): r + 1 for r, idx in enumerate(p2_df.index)}
    p0_set = set(p0_idx)

    union_indices = []
    seen = set()
    for idx in list(p0_idx) + list(p1_df.index) + list(p2_df.index):
        if int(idx) not in seen:
            seen.add(int(idx))
            union_indices.append(int(idx))

    print(f"Queue sizes -> P0={len(p0_idx)}, P1={len(p1_df)}, P2={len(p2_df)}, union={len(union_indices)}")

    now_utc = datetime.now(timezone.utc).isoformat()
    v2_hash = sha256_file(v2_csv)
    seg_hash = sha256_file(seg_parquet)
    reg_hash = sha256_file(reg_csv)

    cases = []
    evidence_records = []
    review_states = []
    history_events = []

    for seq_num, idx in enumerate(union_indices, start=1):
        r = reg_df.loc[idx]
        uid = str(r["package_uid"])
        case_id = f"PEIARS_PMGSY_{seq_num:03d}"
        ev_id = f"EV_PMGSY_{seq_num:03d}"

        reasons = []
        if idx in p0_set:
            reasons.append("P0_TOPOLOGY_FLAG")
        if idx in p1_ranks:
            reasons.append(f"P1_ABS_LEN_DIFF_TOP25(#{p1_ranks[idx]})")
        if idx in p2_ranks:
            reasons.append(f"P2_ABS_REL_DIFF_TOP25(#{p2_ranks[idx]})")

        prop_km = float(r["proposed_l_km"]) if pd.notna(r["proposed_l_km"]) else None
        geom_km = float(r["sum_geom_len_km"]) if pd.notna(r["sum_geom_len_km"]) else None
        diff_km = float(r["length_diff_km"]) if pd.notna(r["length_diff_km"]) else None
        rel_diff = float(r["length_rel_diff"]) if pd.notna(r["length_rel_diff"]) else None
        n_seg = int(r["n_segments"]) if pd.notna(r.get("n_segments")) else None

        cases.append({
            "case_id": case_id,
            "package_uid": uid,
            "mrl_id": str(r.get("mrl_id", "")),
            "source_state_key": str(r.get("source_state_key", "")),
            "ims_year": str(r.get("ims_year", "")),
            "cohort_year_batch": str(r.get("cohort_year_batch", "")),
            "work_name": str(r.get("work_name", "")),
            "queues_qualified": reasons,
            "primary_queue": reasons[0] if reasons else "NONE",
            "case_status": "OPEN_FOR_SOURCE_ADJUDICATION",
            "adjudication_outcome": "UNRESOLVED",
            "created_at_utc": now_utc,
            "lineage": {
                "dataset": "pmgsy3_3state_v1",
                "cohort_field_source": "ims_year (Option B v2; no separate batch column in v2)",
                "rule_version": "OPTION_B_V2_AND_TOPOLOGY_AUDIT",
                "register_csv_sha256": reg_hash,
                "v2_scored_csv_sha256": v2_hash,
                "segments_parquet_sha256": seg_hash,
            },
        })

        evidence_records.append({
            "evidence_id": ev_id,
            "case_id": case_id,
            "package_uid": uid,
            "recorded_at_utc": now_utc,
            "source_references": {
                "packages_table": "data/canonical/pmgsy_v1/pmgsy3_3state_v1/scoring_option_b_v2/packages_p_scored_option_b_v2.csv",
                "segments_geometry": "data/canonical/pmgsy_v1/pmgsy3_3state_v1/segments.parquet",
                "evidence_register": "research/pmgsy_iii_investigation/outputs/option_b_v2_evidence_review/PMGSY_EVIDENCE_REGISTER_V2.csv",
            },
            "measurements": {
                "n_segments": n_seg,
                "proposed_l_km": prop_km,
                "sum_geom_len_km": geom_km,
                "length_diff_km": diff_km,
                "length_rel_diff": rel_diff,
            },
            "rule_and_hash_lineage": {
                "rule_version": "OPTION_B_V2_AND_TOPOLOGY_AUDIT",
                "v2_scored_csv_sha256": v2_hash,
                "segments_parquet_sha256": seg_hash,
            },
            "alternative_explanations": [
                "Batch or state digitization/segmentation convention",
                "Incomplete mapped segment coverage or missing/zero proposed length attribute",
                "Legitimate alignment or administrative package boundary",
            ],
            "verification_note": "Selected in priority queue; requires source-level adjudication before any defect claim.",
        })

        review_states.append({
            "case_id": case_id,
            "package_uid": uid,
            "mrl_id": str(r.get("mrl_id", "")),
            "source_state_key": str(r.get("source_state_key", "")),
            "ims_year": str(r.get("ims_year", "")),
            "cohort_year_batch": str(r.get("cohort_year_batch", "")),
            "queues_qualified": " | ".join(reasons),
            "review_state": "QUEUED_AWAITING_SOURCE_ADJUDICATION",
            "disposition": "UNRESOLVED",
            "confidence": "NONE",
            "reviewer_id": "",
            "notes": "Queue membership verified; source-level adjudication pending.",
        })

        history_events.append(json.dumps({
            "event_id": f"EVT_{seq_num:03d}_INIT",
            "timestamp_utc": now_utc,
            "case_id": case_id,
            "package_uid": uid,
            "event_type": "CASE_CREATED_FROM_PRIORITY_QUEUE",
            "from_state": None,
            "to_state": "QUEUED_AWAITING_SOURCE_ADJUDICATION",
            "disposition": "UNRESOLVED",
            "rule_version": "OPTION_B_V2_AND_TOPOLOGY_AUDIT",
            "register_sha256": reg_hash,
        }))

    (out_dir / "PEIARS_PMGSY_42_CASES.json").write_text(json.dumps(cases, indent=2), encoding="utf-8")
    pd.DataFrame([{
        "case_id": c["case_id"],
        "package_uid": c["package_uid"],
        "mrl_id": c["mrl_id"],
        "source_state_key": c["source_state_key"],
        "ims_year": c["ims_year"],
        "cohort_year_batch": c["cohort_year_batch"],
        "queues_qualified": " | ".join(c["queues_qualified"]),
        "case_status": c["case_status"],
        "adjudication_outcome": c["adjudication_outcome"],
    } for c in cases]).to_csv(out_dir / "PEIARS_PMGSY_42_CASES.csv", index=False)

    (out_dir / "PEIARS_PMGSY_EVIDENCE_RECORDS.json").write_text(json.dumps(evidence_records, indent=2), encoding="utf-8")
    pd.DataFrame(review_states).to_csv(out_dir / "PEIARS_PMGSY_REVIEW_STATES.csv", index=False)
    (out_dir / "PEIARS_PMGSY_DECISION_HISTORY.jsonl").write_text("\n".join(history_events) + "\n", encoding="utf-8")

    rs_df = pd.DataFrame(review_states)
    cohort_breakdown = rs_df.groupby(["source_state_key", "ims_year"]).size().reset_index(name="cases")
    up_2020 = int(((rs_df["source_state_key"] == "UTTAR_PRADESH") & (rs_df["ims_year"] == "2020")).sum())

    rep_path = out_dir / "PEIARS_PMGSY_INTEGRATION_REPORT_V1.md"
    rep_lines = [
        "# PEIARS — PMGSY Evidence & Provenance Integration Report v1",
        "",
        f"- **Generated At (UTC):** {now_utc}",
        "- **Milestone:** `PEIARS-PMGSY-EVIDENCE-INTEGRATION-V1`",
        f"- **Exported Unique Cases:** `{len(cases)}` (`0` confirmed defects claimed).",
        f"- **`UTTAR_PRADESH` / `ims_year=2020` Count:** `{up_2020} / {len(cases)}` (`{up_2020 / len(cases):.1%}`).",
        f"- **Source Hashes:** Register `{reg_hash}`, Option B v2 `{v2_hash}`, Segments `{seg_hash}`.",
        "",
        "## State & `ims_year` Breakdown",
        "",
        to_md_table(cohort_breakdown),
        "",
        "## Status Boundary",
        "",
        "- Cases are initialized in `QUEUED_AWAITING_SOURCE_ADJUDICATION` with `UNRESOLVED` disposition; queue selection does not establish confirmed defects.",
    ]
    rep_path.write_text("\n".join(rep_lines), encoding="utf-8")

    print(f"Exported {len(cases)} PEIARS cases -> {out_dir}")
    print(f"UTTAR_PRADESH ims_year=2020: {up_2020}/{len(cases)}")
    print(to_md_table(cohort_breakdown))


if __name__ == "__main__":
    main()
