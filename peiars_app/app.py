from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st

from peiars_app.db import (
    compute_signed_length_metrics,
    get_paths,
    get_snapshots_registry_rows,
    get_sources_registry_rows,
    init_and_import_sqlite,
    summarize_observation,
)
from peiars_app.exporter import export_case_dossier
from peiars_app.provenance import append_app_review_event, get_case_history, verify_baseline_162_log

st.set_page_config(page_title="PEIARS · Anomaly Review Workbench", layout="wide")

repo_root = Path.cwd()
p = get_paths(repo_root)
if not p["db_path"].exists():
    init_and_import_sqlite(repo_root)

replay_info = verify_baseline_162_log(repo_root)

st.session_state.setdefault("active_section", "02 Data")
st.session_state.setdefault("data_subview", "Package Records")
st.session_state.setdefault("show_more_filters", False)
st.session_state.setdefault("show_about_registry", False)
st.session_state.setdefault("selected_record_id", None)
st.session_state.setdefault("inspector_open", False)
st.session_state.setdefault("q_search", "")
st.session_state.setdefault("f_state", [])
st.session_state.setdefault("f_year", [])
st.session_state.setdefault("f_disp", [])
st.session_state.setdefault("f_verif", [])
st.session_state.setdefault("f_kind", "any")
st.session_state.setdefault("f_integrity", "any")

st.caption("PEIARS · Anomaly Review Workbench  |  baseline: c8aa5a1  |  local-first")

sections = ["01 Overview", "02 Data", "03 Analysis", "04 Investigations", "05 Domains", "06 Research"]
nav_cols = st.columns(len(sections))
for idx, sec in enumerate(sections):
    is_cur = st.session_state["active_section"] == sec
    if nav_cols[idx].button(sec, key=f"nav_{sec}", type="primary" if is_cur else "secondary", use_container_width=True):
        st.session_state["active_section"] = sec
        st.rerun()

conn = sqlite3.connect(str(p["db_path"]))
cases_raw = pd.read_sql_query(
    """
    SELECT case_id, package_uid, mrl_id, source_state_key, ims_year,
           queues_qualified_json, baseline_status, baseline_disposition,
           verification_status, blocker_reason, evidence_json, review_state_json
    FROM cases ORDER BY case_id
    """,
    conn,
)
conn.close()

enriched_rows = []
for row in cases_raw.itertuples(index=False):
    ev_rec = json.loads(row.evidence_json or "{}")
    metrics = compute_signed_length_metrics(ev_rec.get("measurements", {}))
    obs = summarize_observation(ev_rec, metrics, row.verification_status)
    queues = json.loads(row.queues_qualified_json or "[]")
    enriched_rows.append({
        "case_id": row.case_id,
        "package_uid": row.package_uid,
        "mrl_id": row.mrl_id,
        "state": row.source_state_key,
        "ims_year": row.ims_year,
        "queues": ", ".join(queues),
        "observation": obs,
        "disposition": row.baseline_disposition,
        "verification_status": row.verification_status,
        "blocker_reason": row.blocker_reason,
        "proposed_l_km": metrics["proposed_l_km"],
        "sum_geom_len_km": metrics["sum_geom_len_km"],
        "length_diff_km": metrics["length_diff_km"],
        "length_rel_diff_display": metrics["length_rel_diff_display"],
        "evidence_obj": ev_rec,
    })
pkg_df = pd.DataFrame(enriched_rows)
active_sec = st.session_state["active_section"]


def render_inspector(selected_id: str, subview: str) -> None:
    top_l, top_r = st.columns([5, 1])
    top_l.subheader(selected_id)
    if top_r.button("✕", key="close_inspector_btn", help="Close inspector", use_container_width=True):
        st.session_state["inspector_open"] = False
        st.rerun()

    if subview == "Sources":
        s = {r["source_id"]: r for r in get_sources_registry_rows()}.get(selected_id)
        if not s:
            st.info("No registered source selected.")
            return
        st.write(f"**Dataset kind:** `{s['dataset_kind']}`")
        st.write(f"**Availability:** `{s['availability']}` · **Integrity:** `{s['integrity_status']}` · **Analysis:** `{s['analysis_status']}`")
        st.caption(s["notes"])
        with st.expander("Technical provenance", expanded=False):
            st.json(s)
        return

    if subview == "Snapshots":
        sn = {r["snapshot_id"]: r for r in get_snapshots_registry_rows(repo_root)}.get(selected_id)
        if not sn:
            st.info("No snapshot selected.")
            return
        st.write(f"**Type:** {sn['snapshot_type']} (`{sn['status']}`)")
        st.write(f"**Scope:** {sn['records_scope']}")
        st.write(f"**Corroboration:** {sn['external_corroboration']}")
        st.caption(sn["registry_linkage"])
        with st.expander("Evidence & metrics summary", expanded=False):
            st.write(sn["provenance_baseline"])
        with st.expander("Technical provenance", expanded=False):
            st.json(sn)
        return

    match = pkg_df[pkg_df["case_id"] == selected_id]
    if match.empty:
        st.warning("Selected record is not in current filtered set.")
        return
    rec = match.iloc[0].to_dict()
    short_uid = f"{rec['package_uid'][:10]}…{rec['package_uid'][-6:]}" if len(rec["package_uid"]) > 18 else rec["package_uid"]

    st.write(f"**State / IMS Year:** `{rec['state']}` · `{rec['ims_year']}`")
    st.write(f"**MRL ID:** `{rec['mrl_id']}` · **Package UID:** `{short_uid}`")
    st.write(f"**Observation:** {rec['observation']}")
    st.write(f"**Disposition:** `{rec['disposition']}`")
    st.write(f"**Verification status:** `{rec['verification_status']}`")
    st.caption(f"Full package UID: {rec['package_uid']}")

    if st.button("Open related investigation →", key="jump_to_inv", type="primary", use_container_width=True):
        st.session_state["active_section"] = "04 Investigations"
        st.session_state["inv_selected_case"] = rec["case_id"]
        st.rerun()

    with st.expander("Evidence & metrics", expanded=False):
        st.write(f"Proposed length: `{rec['proposed_l_km']} km` · Mapped length: `{rec['sum_geom_len_km']} km`")
        st.write(f"Signed diff (`geom - prop`): `{rec['length_diff_km']} km` · Relative: `{rec['length_rel_diff_display']}`")
        st.write(f"Queues: `{rec['queues'] or 'none'}`")
        if rec["blocker_reason"]:
            st.caption(f"Corroboration blocker: {rec['blocker_reason']}")

    with st.expander("Technical provenance", expanded=False):
        st.caption("Frozen 162-event baseline is read-only; screening triggers are distinct from dispositions.")
        st.json({
            "case_id": rec["case_id"],
            "package_uid": rec["package_uid"],
            "mrl_id": rec["mrl_id"],
            "baseline_disposition": rec["disposition"],
            "verification_status": rec["verification_status"],
            "evidence_record": rec["evidence_obj"],
        })


if active_sec == "02 Data":
    subview = st.session_state["data_subview"]
    hd_l, hd_r = st.columns([4.4, 1.0])
    hd_l.markdown(f"## 02 Data Observatory  `{subview.lower()}`")
    if hd_r.button("About registry", key="toggle_about_reg", use_container_width=True):
        st.session_state["show_about_registry"] = not st.session_state["show_about_registry"]

    if st.session_state["show_about_registry"]:
        st.info(
            "Sources, local research snapshots, and package records are distinct entities. "
            "The 42 imported PMGSY records are selected case-linked packages from the local research snapshot—not all 4,361 P packages—and "
            "VERIFICATION_BLOCKED reflects missing local external records rather than a confirmed source defect."
        )

    sv_cols = st.columns([1.2, 1.2, 1.6, 4.6])
    for idx, sv in enumerate(["Sources", "Snapshots", "Package Records"]):
        if sv_cols[idx].button(sv, key=f"subview_{sv}", type="primary" if subview == sv else "secondary", use_container_width=True):
            st.session_state["data_subview"] = sv
            st.session_state["selected_record_id"] = None
            st.session_state["inspector_open"] = False
            st.rerun()

    f1, f2, f3, f4, f5, f6 = st.columns([2.6, 1.4, 1.4, 1.1, 0.9, 1.3])
    st.session_state["q_search"] = f1.text_input("Search", value=st.session_state["q_search"], placeholder="Search ID, MRL, state, or source...", label_visibility="collapsed")

    if subview == "Package Records":
        state_opts = sorted(pkg_df["state"].dropna().unique().tolist())
        year_opts = sorted(pkg_df["ims_year"].dropna().unique().tolist())
        st.session_state["f_state"] = f2.multiselect("State", state_opts, default=[x for x in st.session_state["f_state"] if x in state_opts], placeholder="State", label_visibility="collapsed")
        st.session_state["f_year"] = f3.multiselect("Year", year_opts, default=[x for x in st.session_state["f_year"] if x in year_opts], placeholder="IMS Year", label_visibility="collapsed")
    else:
        kind_opts = ["any", "mplads_administration", "local_pmgsy_snapshot"]
        st.session_state["f_kind"] = f2.selectbox("Kind", kind_opts, index=kind_opts.index(st.session_state["f_kind"]) if st.session_state["f_kind"] in kind_opts else 0, label_visibility="collapsed")
        st.session_state["f_integrity"] = f3.selectbox("Integrity", ["any", "unavailable", "loaded_local"], index=["any", "unavailable", "loaded_local"].index(st.session_state["f_integrity"]) if st.session_state["f_integrity"] in ["any", "unavailable", "loaded_local"] else 0, label_visibility="collapsed")

    if f4.button("More filters", key="more_filters_btn", use_container_width=True):
        st.session_state["show_more_filters"] = not st.session_state["show_more_filters"]
    if f5.button("Clear", key="clear_filters_btn", use_container_width=True):
        st.session_state["q_search"] = ""
        st.session_state["f_state"] = []
        st.session_state["f_year"] = []
        st.session_state["f_disp"] = []
        st.session_state["f_verif"] = []
        st.session_state["f_kind"] = "any"
        st.session_state["f_integrity"] = "any"
        st.rerun()

    if st.session_state["show_more_filters"] and subview == "Package Records":
        mf1, mf2 = st.columns(2)
        disp_opts = sorted(pkg_df["disposition"].dropna().unique().tolist())
        verif_opts = sorted(pkg_df["verification_status"].dropna().unique().tolist())
        st.session_state["f_disp"] = mf1.multiselect("Disposition", disp_opts, default=[x for x in st.session_state["f_disp"] if x in disp_opts])
        st.session_state["f_verif"] = mf2.multiselect("Verification Status", verif_opts, default=[x for x in st.session_state["f_verif"] if x in verif_opts])

    if subview == "Sources":
        df_view = pd.DataFrame(get_sources_registry_rows())
        total_cnt = len(df_view)
        if st.session_state["q_search"].strip():
            q = st.session_state["q_search"].strip().lower()
            df_view = df_view[df_view.apply(lambda r: q in " ".join(r.astype(str)).lower(), axis=1)]
        if st.session_state["f_kind"] != "any":
            df_view = df_view[df_view["dataset_kind"] == st.session_state["f_kind"]]
        if st.session_state["f_integrity"] != "any":
            df_view = df_view[df_view["integrity_status"] == st.session_state["f_integrity"]]
        f6.caption(f"{len(df_view)}/{total_cnt} sources")
        id_col = "source_id"
        show_cols = ["source_id", "dataset_kind", "availability", "integrity_status", "analysis_status"]
    elif subview == "Snapshots":
        df_view = pd.DataFrame(get_snapshots_registry_rows(repo_root))
        total_cnt = len(df_view)
        if st.session_state["q_search"].strip():
            q = st.session_state["q_search"].strip().lower()
            df_view = df_view[df_view.apply(lambda r: q in " ".join(r.astype(str)).lower(), axis=1)]
        if st.session_state["f_integrity"] != "any":
            df_view = df_view[df_view["status"] == st.session_state["f_integrity"]]
        f6.caption(f"{len(df_view)}/{total_cnt} snapshots")
        id_col = "snapshot_id"
        show_cols = ["snapshot_id", "snapshot_type", "status", "records_scope", "external_corroboration"]
    else:
        df_view = pkg_df.copy()
        total_cnt = len(df_view)
        if st.session_state["q_search"].strip():
            q = st.session_state["q_search"].strip().lower()
            df_view = df_view[
                df_view["case_id"].str.lower().str.contains(q)
                | df_view["mrl_id"].str.lower().str.contains(q)
                | df_view["package_uid"].str.lower().str.contains(q)
                | df_view["state"].str.lower().str.contains(q)
            ]
        if st.session_state["f_state"]:
            df_view = df_view[df_view["state"].isin(st.session_state["f_state"])]
        if st.session_state["f_year"]:
            df_view = df_view[df_view["ims_year"].isin(st.session_state["f_year"])]
        if st.session_state["f_disp"]:
            df_view = df_view[df_view["disposition"].isin(st.session_state["f_disp"])]
        if st.session_state["f_verif"]:
            df_view = df_view[df_view["verification_status"].isin(st.session_state["f_verif"])]
        f6.caption(f"{len(df_view)}/{total_cnt} linked pkgs")
        id_col = "case_id"
        show_cols = ["case_id", "mrl_id", "state", "ims_year", "observation", "disposition", "verification_status"]

    show_inspector = bool(st.session_state["inspector_open"] and st.session_state["selected_record_id"] in set(df_view[id_col]))
    main_col, insp_col = st.columns([0.70, 0.30]) if show_inspector else (st.container(), None)

    with main_col:
        if df_view.empty:
            st.info("No records match the active filter. Click Clear to reset.")
        else:
            st.dataframe(df_view[show_cols], use_container_width=True, hide_index=True)
            pick = st.selectbox("Inspect record", ["— none —"] + df_view[id_col].tolist(), index=0, key=f"pick_{subview}")
            if pick != "— none —":
                st.session_state["selected_record_id"] = pick
                st.session_state["inspector_open"] = True
                st.rerun()

    if show_inspector and insp_col is not None:
        with insp_col:
            render_inspector(st.session_state["selected_record_id"], subview)

elif active_sec == "04 Investigations":
    st.subheader("04 Investigations — Case Review & Provenance")
    case_ids = pkg_df["case_id"].tolist()
    pre_sel = st.session_state.get("inv_selected_case")
    sel_case = st.selectbox("Case", case_ids, index=case_ids.index(pre_sel) if pre_sel in case_ids else 0)
    st.session_state["inv_selected_case"] = sel_case
    row = pkg_df[pkg_df["case_id"] == sel_case].iloc[0]
    st.write(f"**MRL ID:** `{row['mrl_id']}` · **State / Year:** `{row['state']}` · `{row['ims_year']}` · **Queues:** `{row['queues'] or 'none'}`")
    st.write(f"**Disposition:** `{row['disposition']}` · **Verification:** `{row['verification_status']}`")
    if row["blocker_reason"]:
        st.caption(f"Verification blocker: {row['blocker_reason']}")

    with st.form("inv_note_form"):
        rev_id = st.text_input("Reviewer ID", value="local_reviewer")
        note_txt = st.text_area("Reviewer Note (appends to separate app stream)")
        if st.form_submit_button("Append App Event"):
            if note_txt.strip():
                ev = append_app_review_event(sel_case, rev_id, note_txt, repo_root=repo_root)
                st.success(f"Appended {ev['event_id']} to separate app stream.")
            else:
                st.warning("Note cannot be empty.")

    hist = get_case_history(sel_case, repo_root)
    st.caption(f"Read-only baseline events for case: {len(hist['baseline_events'])} · Appended app events: {len(hist['app_events'])}")
    if st.button("Export Case Dossier", key="export_dossier_btn"):
        out = export_case_dossier(sel_case, repo_root)
        st.success(f"Exported {out['json'].name} and {out['md'].name}")

else:
    st.subheader(active_sec)
    st.info(
        f"{active_sec} is held for later phases. Frozen local snapshot: 42 cases "
        "(37 SUPPORTED_REVIEW_CANDIDATE, 5 UNRESOLVED, 0 CONFIRMED_SOURCE_DEFECT), 162 baseline events, "
        "12/12 VERIFICATION_BLOCKED; Isolation Forest remains CLOSED_RESEARCH_NOT_ADMITTED."
    )

st.divider()
st.caption(
    f"SQLite: ready · baseline_162_replay: {'PASS' if replay_info['valid'] else 'FAIL'} · "
    "snapshot: pmgsy3_3state_v1_curated_42 (42 linked cases, 12/12 blocked) · "
    "dispositions: 37 candidate / 5 unresolved / 0 confirmed_defect"
)
