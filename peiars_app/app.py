from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st

from peiars_app.db import get_paths, init_and_import_sqlite
from peiars_app.exporter import export_case_dossier
from peiars_app.provenance import append_app_review_event, get_case_history, verify_baseline_162_log

st.set_page_config(page_title="PEIARS Core v1 — PMGSY Case Workbench", layout="wide")
st.title("PEIARS Core v1 — PMGSY Case & Provenance Workbench")
st.caption("Local-first review workbench built on the frozen 42-case baseline and 162-event provenance log.")

repo_root = Path.cwd()
p = get_paths(repo_root)

if not p["db_path"].exists():
    init_and_import_sqlite(repo_root)

replay_info = verify_baseline_162_log(repo_root)

conn = sqlite3.connect(str(p["db_path"]))
cases_df = pd.read_sql_query(
    "SELECT case_id, package_uid, mrl_id, source_state_key, ims_year, queues_qualified_json, baseline_disposition, verification_status FROM cases ORDER BY case_id",
    conn,
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Imported Cases", len(cases_df))
c2.metric("Supported Candidates", int((cases_df["baseline_disposition"] == "SUPPORTED_REVIEW_CANDIDATE").sum()))
c3.metric("Unresolved", int((cases_df["baseline_disposition"] == "UNRESOLVED").sum()))
c4.metric("162-Event Log Replay", "PASS" if replay_info["valid"] else "FAIL")

st.sidebar.header("Filter Case Register")
state_filter = st.sidebar.multiselect("State", sorted(cases_df["source_state_key"].dropna().unique().tolist()))
disp_filter = st.sidebar.multiselect("Baseline Disposition", sorted(cases_df["baseline_disposition"].dropna().unique().tolist()))
search_q = st.sidebar.text_input("Search case_id or mrl_id", value="PEIARS_PMGSY_001").strip()

filtered = cases_df.copy()
if state_filter:
    filtered = filtered[filtered["source_state_key"].isin(state_filter)]
if disp_filter:
    filtered = filtered[filtered["baseline_disposition"].isin(disp_filter)]
if search_q:
    q_low = search_q.lower()
    filtered = filtered[
        filtered["case_id"].str.lower().str.contains(q_low)
        | filtered["mrl_id"].str.lower().str.contains(q_low)
    ]

st.subheader("Searchable Case Register")
st.dataframe(filtered if not filtered.empty else cases_df, use_container_width=True, hide_index=True)

selectable_ids = (filtered if not filtered.empty else cases_df)["case_id"].tolist()
default_idx = selectable_ids.index("PEIARS_PMGSY_001") if "PEIARS_PMGSY_001" in selectable_ids else 0
selected_cid = st.selectbox("Select Case to Inspect", selectable_ids, index=default_idx)

full_row = conn.execute(
    "SELECT case_id, package_uid, mrl_id, source_state_key, ims_year, queues_qualified_json, baseline_status, baseline_disposition, verification_status, blocker_reason, evidence_json, review_state_json FROM cases WHERE case_id = ?",
    (selected_cid,),
).fetchone()
conn.close()

col_left, col_right = st.columns(2)
with col_left:
    st.subheader(f"Case Details: {selected_cid}")
    st.write({
        "case_id": full_row[0],
        "package_uid": full_row[1],
        "mrl_id": full_row[2],
        "source_state_key": full_row[3],
        "ims_year": full_row[4],
        "queues_qualified": json.loads(full_row[5] or "[]"),
        "baseline_status": full_row[6],
        "baseline_disposition": full_row[7],
        "verification_status": full_row[8],
        "blocker_reason": full_row[9],
    })

with col_right:
    st.subheader("Evidence Record & Review State")
    st.json(json.loads(full_row[10] or "{}"))

st.subheader("Append Reviewer Note / Action (Separate Append-Only Stream)")
with st.form("append_note_form"):
    rev_id = st.text_input("Reviewer ID", value="local_reviewer")
    note_txt = st.text_area("Reviewer Note / Evidence Observation")
    sub_btn = st.form_submit_button("Append Event")
    if sub_btn:
        if note_txt.strip():
            ev = append_app_review_event(selected_cid, rev_id, note_txt, repo_root=repo_root)
            st.success(f"Appended {ev['event_id']} (hash: {ev['event_hash'][:16]}...)")
        else:
            st.warning("Please enter a reviewer note before appending.")

hist = get_case_history(selected_cid, repo_root)
st.subheader("Chronological History (Read-Only Baseline + Appended App Events)")
st.write("**Baseline 162-Event Log Entries for Case:**")
st.json(hist["baseline_events"])
st.write("**Appended Application Events for Case:**")
st.json(hist["app_events"])

st.subheader("Verifiable Case Dossier Export")
if st.button(f"Export Dossier for {selected_cid}"):
    out_paths = export_case_dossier(selected_cid, repo_root)
    st.success(f"Exported: {out_paths['json']} and {out_paths['md']}")
