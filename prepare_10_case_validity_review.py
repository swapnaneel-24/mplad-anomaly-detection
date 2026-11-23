from __future__ import annotations

import math
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd

TARGET_IDS = [
    "IFAUD_002", "IFAUD_003", "IFAUD_007", "IFAUD_010", "IFAUD_023", "IFAUD_054",
    "IFAUD_043",
    "IFAUD_013", "IFAUD_020", "IFAUD_028",
]


def calc_sinuosity(geom) -> float:
    if geom is None or geom.is_empty:
        return np.nan
    length = float(geom.length)
    if length <= 0:
        return np.nan
    if geom.geom_type == "LineString":
        coords = list(geom.coords)
        if len(coords) < 2:
            return 1.0
        chord = math.hypot(coords[-1][0] - coords[0][0], coords[-1][1] - coords[0][1])
        return float(length / chord) if chord > 0 else np.nan
    if geom.geom_type == "MultiLineString":
        vals = []
        for part in geom.geoms:
            c = list(part.coords)
            if len(c) >= 2 and part.length > 0:
                ch = math.hypot(c[-1][0] - c[0][0], c[-1][1] - c[0][1])
                if ch > 0:
                    vals.append(float(part.length / ch))
        return float(np.mean(vals)) if vals else np.nan
    return np.nan


def count_vertices(geom) -> int:
    if geom is None or geom.is_empty:
        return 0
    if geom.geom_type == "LineString":
        return len(geom.coords)
    if geom.geom_type == "MultiLineString":
        return sum(len(p.coords) for p in geom.geoms)
    return 0


def main() -> None:
    repo_root = Path.cwd()
    snap_dir = repo_root / "data/canonical/pmgsy_v1/pmgsy3_3state_v1"
    exp_dir = repo_root / "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1"

    res = pd.read_csv(exp_dir / "IF_ENRICHED_AUDIT_RESULTS_V1.csv")
    key = pd.read_csv(exp_dir / "diagnostics/if_enriched_audit_unblinded_key_DO_NOT_PEEK.csv")
    sub = res[res["audit_item_id"].isin(TARGET_IDS)].merge(
        key[["audit_item_id", "audit_group"]], on="audit_item_id", how="left"
    )
    sub["order"] = sub["audit_item_id"].map({k: i for i, k in enumerate(TARGET_IDS)})
    sub = sub.sort_values("order").drop(columns=["order"]).reset_index(drop=True)

    # Locate canonical segments vector file in snap_dir
    seg_candidates = list(snap_dir.glob("*segment*.gpkg")) + list(snap_dir.glob("*segment*.parquet")) + list(snap_dir.glob("*.gpkg"))
    if not seg_candidates:
        raise FileNotFoundError(f"No canonical geometry file found in {snap_dir}")
    seg_path = seg_candidates[0]
    print(f"Reading canonical geometries from: {seg_path}")

    gdf = gpd.read_file(seg_path) if seg_path.suffix.lower() != ".parquet" else gpd.read_parquet(seg_path)
    if gdf.crs is not None and gdf.crs.is_geographic:
        # Project to India Albers / UTM-like metric CRS for independent length/sinuosity recomputation
        gdf = gdf.to_crs("EPSG:7755")

    uid_col = "package_uid" if "package_uid" in gdf.columns else None
    if uid_col is None:
        raise KeyError(f"'package_uid' not found in {seg_path}; columns={list(gdf.columns)}")

    sub_uids = set(sub["package_uid"])
    gdf_sub = gdf[gdf[uid_col].isin(sub_uids)].copy()

    recomp_rows = []
    for uid, grp in gdf_sub.groupby(uid_col):
        lengths_km = grp.geometry.length / 1000.0
        tot_km = float(lengths_km.sum())
        max_km = float(lengths_km.max()) if len(lengths_km) else 0.0
        conc = float(max_km / tot_km) if tot_km > 0 else np.nan
        sin_vals = [calc_sinuosity(g) for g in grp.geometry]
        verts = sum(count_vertices(g) for g in grp.geometry)
        valid_all = bool(grp.geometry.is_valid.all())
        empty_any = bool(grp.geometry.is_empty.any())
        recomp_rows.append({
            "package_uid": uid,
            "recomp_n_segments": int(len(grp)),
            "recomp_geom_len_km": round(tot_km, 6),
            "recomp_seg_len_conc": round(conc, 6) if pd.notna(conc) else np.nan,
            "recomp_mean_sinuosity": round(float(np.nanmean(sin_vals)), 6) if len(sin_vals) else np.nan,
            "recomp_vertices_per_km": round(float(verts / tot_km), 3) if tot_km > 0 else np.nan,
            "recomp_geom_valid": valid_all and (not empty_any),
        })

    recomp_df = pd.DataFrame(recomp_rows)
    out = sub.merge(recomp_df, on="package_uid", how="left")
    out["original_v1_outcome"] = out["review_outcome"]
    out["validity_adjudication"] = ""  # Allowed: CONFIRMED_SOURCE_DEFECT, SUPPORTED_REVIEW_CANDIDATE, BENIGN_EXPLAINED, UNRESOLVED
    out["source_feature_reference"] = out["mrl_id"].map(lambda x: f"{seg_path.name}:mrl_id={x}")
    out["validity_reviewer_id"] = "single_reviewer_v1"
    out["validity_confidence"] = ""
    out["validity_evidence_note"] = ""

    keep_cols = [
        c for c in [
            "audit_item_id", "audit_group", "original_v1_outcome",
            "source_state_key", "cohort_year_batch", "package_uid", "mrl_id", "work_name",
            "proposed_l_km", "sum_geom_len_km", "recomp_geom_len_km",
            "n_segments", "recomp_n_segments",
            "seg_len_concentration", "recomp_seg_len_conc",
            "mean_sinuosity", "recomp_mean_sinuosity",
            "vertices_per_km", "recomp_vertices_per_km",
            "recomp_geom_valid",
            "source_feature_reference", "validity_adjudication",
            "validity_reviewer_id", "validity_confidence", "validity_evidence_note",
        ] if c in out.columns
    ]

    out_path = exp_dir / "IF_10_CASE_VALIDITY_REVIEW_V1.csv"
    out[keep_cols].to_csv(out_path, index=False)
    print(f"Wrote 10-case validity review sheet -> {out_path}")
    print(out[[
        "audit_item_id", "audit_group", "original_v1_outcome",
        "recomp_n_segments", "recomp_geom_len_km", "proposed_l_km",
        "recomp_mean_sinuosity", "recomp_geom_valid"
    ]].to_string(index=False))


if __name__ == "__main__":
    main()
