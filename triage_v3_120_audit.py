from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Tuple
import geopandas as gpd
import numpy as np
import pandas as pd

OUTCOMES: List[Tuple[str, str]] = [
    ("1", "CONFIRMED_SOURCE_DEFECT"),
    ("2", "SUPPORTED_REVIEW_CANDIDATE"),
    ("3", "BENIGN_EXPLAINED"),
    ("4", "UNRESOLVED"),
    ("5", "INSUFFICIENT_EVIDENCE"),
]
CONF_MAP: Dict[str, str] = {"h": "HIGH", "m": "MEDIUM", "l": "LOW"}


def calc_sin(geom) -> float:
    if geom is None or geom.is_empty:
        return np.nan
    L = float(geom.length)
    if L <= 0:
        return np.nan
    if geom.geom_type == "LineString":
        c = list(geom.coords)
        if len(c) < 2:
            return 1.0
        ch = math.hypot(c[-1][0] - c[0][0], c[-1][1] - c[0][1])
        return float(L / ch) if ch > 0 else np.nan
    if geom.geom_type == "MultiLineString":
        vals = []
        for p in geom.geoms:
            c = list(p.coords)
            if len(c) >= 2 and p.length > 0:
                ch = math.hypot(c[-1][0] - c[0][0], c[-1][1] - c[0][1])
                if ch > 0:
                    vals.append(float(p.length / ch))
        return float(np.mean(vals)) if vals else np.nan
    return np.nan


def suggest_v3_desk_classification(row: pd.Series, recomp_len: float, recomp_sin: float, recomp_valid: bool) -> Tuple[str, str, str, str]:
    """Provides a starting desk suggestion under strict v3 rules; user always confirms."""
    prop = float(row["proposed_l_km"]) if pd.notna(row.get("proposed_l_km")) else 0.0
    n_seg = int(row["n_segments"]) if pd.notna(row.get("n_segments")) else 0
    conc = float(row["seg_len_concentration"]) if pd.notna(row.get("seg_len_concentration")) else 0.0
    vpk = float(row["vertices_per_km"]) if pd.notna(row.get("vertices_per_km")) else 0.0

    if not recomp_valid:
        return (
            "CONFIRMED_SOURCE_DEFECT",
            "HIGH",
            "GEOMETRY_TOPOLOGY",
            "Invalid or empty geometry in canonical segments.parquet.",
        )
    if prop <= 0.0 and (pd.isna(recomp_len) or recomp_len <= 0.0):
        return (
            "INSUFFICIENT_EVIDENCE",
            "LOW",
            "MISSING_ATTRIBUTES",
            "Both proposed and recomputed geometry lengths are missing/zero.",
        )

    ratio = (recomp_len / prop) if (prop > 0 and pd.notna(recomp_len)) else np.nan
    rel_gap = abs(ratio - 1.0) if pd.notna(ratio) else 1.0

    # Extreme length mismatch (>=50%) or multi-segment severe gap (>=25%) -> Supported review candidate (not confirmed defect without external authoritative proof)
    if rel_gap >= 0.25 or (n_seg >= 2 and rel_gap >= 0.15):
        return (
            "SUPPORTED_REVIEW_CANDIDATE",
            "MEDIUM",
            "LENGTH_CONSISTENCY",
            f"Reproducible length divergence (geom={recomp_len:.2f} km vs prop={prop:.2f} km, r={ratio:.2f}, segs={n_seg}); needs external alignment check.",
        )

    # High sinuosity with close length match -> UNRESOLVED per v3 rule (not BENIGN_EXPLAINED and not CONFIRMED_SOURCE_DEFECT)
    if pd.notna(recomp_sin) and recomp_sin >= 2.5:
        return (
            "UNRESOLVED",
            "MEDIUM",
            "GEOMETRY_ALIGNMENT",
            f"High sinuosity ({recomp_sin:.2f}) with close length ratio (r={ratio:.2f}); lacks external alignment evidence.",
        )

    # Multi-segment split with consistent total length -> BENIGN_EXPLAINED (segmentation convention)
    if n_seg >= 2 and rel_gap < 0.10:
        return (
            "BENIGN_EXPLAINED",
            "HIGH",
            "SEGMENTATION_CONVENTION",
            f"Multi-segment package (segs={n_seg}, conc={conc:.2f}) with consistent total length (r={ratio:.2f}).",
        )

    # Moderate length gap (10% - 25%) -> SUPPORTED_REVIEW_CANDIDATE
    if 0.10 <= rel_gap < 0.25:
        return (
            "SUPPORTED_REVIEW_CANDIDATE",
            "LOW",
            "LENGTH_CONSISTENCY",
            f"Moderate length discrepancy (geom={recomp_len:.2f} km vs prop={prop:.2f} km, r={ratio:.2f}).",
        )

    return (
        "BENIGN_EXPLAINED",
        "HIGH",
        "STANDARD_ALIGNMENT",
        f"Valid geometry and consistent length/shape (r={ratio:.2f}, sin={recomp_sin:.2f}, vert/km={vpk:.1f}).",
    )


def main() -> None:
    repo_root = Path.cwd()
    snap_dir = repo_root / "data/canonical/pmgsy_v1/pmgsy3_3state_v1"
    out_dir = repo_root / "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1/expanded_audit_v3"
    blind_path = out_dir / "IF_V3_BLIND_REVIEW.csv"
    annot_path = out_dir / "IF_V3_BLIND_ANNOTATIONS.csv"

    df = pd.read_csv(annot_path if annot_path.exists() else blind_path)
    for col in [
        "confirmed_source_defect", "supported_review_candidate", "review_outcome",
        "evidence_domain", "reviewer_confidence", "observed_finding",
        "alternative_explanation", "reviewer_notes",
    ]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str)
    if "reviewer_id" not in df.columns:
        df["reviewer_id"] = "desk_reviewer_1 (SINGLE_REVIEWER_LIMITATION)"

    print("Loading canonical segments.parquet for independent geometry verification...")
    gdf = gpd.read_parquet(snap_dir / "segments.parquet")
    if gdf.crs is not None and gdf.crs.is_geographic:
        gdf = gdf.to_crs("EPSG:7755")
    uids = set(df["package_uid"].astype(str))
    gdf_sub = gdf[gdf["package_uid"].astype(str).isin(uids)].copy()

    recomp = {}
    for uid, grp in gdf_sub.groupby("package_uid"):
        l_km = float((grp.geometry.length / 1000.0).sum())
        s_val = float(np.nanmean([calc_sin(g) for g in grp.geometry]))
        v_ok = bool(grp.geometry.is_valid.all() and not grp.geometry.is_empty.any())
        recomp[str(uid)] = (l_km, s_val, v_ok)

    print("Keys: [Enter]=accept suggested | [1-5]=choose outcome | [s]=skip | [q]=save & quit\n")
    for idx, row in df.iterrows():
        uid = str(row["package_uid"])
        r_len, r_sin, r_ok = recomp.get(uid, (np.nan, np.nan, True))
        sug_out, sug_conf, sug_dom, sug_reason = suggest_v3_desk_classification(row, r_len, r_sin, r_ok)

        print("=" * 78)
        cur = row["review_outcome"].strip()
        print(f"[{idx+1}/{len(df)}] {row['audit_item_id']} | Current: {cur or 'BLANK'} | State={row['source_state_key']} | Cohort={row['cohort_year_batch']}")
        print(f"  mrl_id={row['mrl_id']} | work='{row.get('work_name', '')}'")
        print(f"  segs={row['n_segments']} (conc={row['seg_len_concentration']:.3f}) | prop={row['proposed_l_km']:.2f} km | geom={row['sum_geom_len_km']:.2f} km | recomp_geom={r_len:.2f} km")
        print(f"  sin={row['mean_sinuosity']:.2f} (recomp={r_sin:.2f}) | vert/km={row['vertices_per_km']:.1f} | geom_valid={r_ok}")
        print("\nStrict v3 Outcomes:")
        for k, lbl in OUTCOMES:
            mark = " <-- SUGGESTED" if lbl == sug_out else ""
            print(f"  [{k}] {lbl}{mark}")
        print(f"  Suggested: {sug_out} ({sug_conf}, {sug_dom}) -> {sug_reason}")

        ch = input("Select [Enter=suggested, 1-5, s=skip, q=quit]: ").strip().lower()
        if ch == "q":
            df.to_csv(annot_path, index=False)
            print(f"Saved progress to {annot_path} at row {idx+1}/{len(df)}.")
            return
        if ch == "s":
            continue

        if ch == "":
            chosen_out, chosen_conf = sug_out, sug_conf
        elif ch in dict(OUTCOMES):
            chosen_out = dict(OUTCOMES)[ch]
            c_in = input("Confidence [Enter=suggested, h=HIGH, m=MEDIUM, l=LOW]: ").strip().lower()
            chosen_conf = CONF_MAP.get(c_in, sug_conf)
        else:
            chosen_out, chosen_conf = sug_out, sug_conf

        df.loc[idx, "review_outcome"] = chosen_out
        df.loc[idx, "confirmed_source_defect"] = "1" if chosen_out == "CONFIRMED_SOURCE_DEFECT" else "0"
        df.loc[idx, "supported_review_candidate"] = "1" if chosen_out == "SUPPORTED_REVIEW_CANDIDATE" else "0"
        df.loc[idx, "evidence_domain"] = sug_dom
        df.loc[idx, "reviewer_confidence"] = chosen_conf
        df.loc[idx, "observed_finding"] = sug_reason
        df.loc[idx, "alternative_explanation"] = (
            "Batch digitization/segmentation convention or terrain alignment without external survey proof"
        )
        df.loc[idx, "reviewer_notes"] = "SINGLE_REVIEWER_LIMITATION; desk review from canonical attributes/segments.parquet"
        df.to_csv(annot_path, index=False)

    print(f"\nCompleted all {len(df)} rows -> {annot_path}")
    print(df["review_outcome"].value_counts().to_string())


if __name__ == "__main__":
    main()
