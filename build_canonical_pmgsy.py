from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
from pyproj import CRS
from shapely import line_merge, wkb
from shapely.geometry import GeometryCollection, LineString, MultiLineString

METRIC_CRS_INDIA = "EPSG:7755"  # WGS 84 / India NSF LCC

DEFAULT_SHAPEFILES: Dict[str, Path] = {
    "BIHAR": Path("data/raw/Proposal_PMGSY-III_Bihar/Proposal_PMGSY-III_BIHAR.shp"),
    "UTTAR_PRADESH": Path("data/raw/Proposal_PMGSY-III_UttarPradesh/Proposal_PMGSY-III_UP.shp"),
    "MADHYA_PRADESH": Path("data/raw/Proposal_PMGSY-III_MadhyaPradesh/Proposal_PMGSY-III_MP.shp"),
}

EXTRA_SHAPEFILES: Dict[str, Path] = {
    "ODISHA": Path("data/raw/Proposal_PMGSY-III_Odisha/Proposal_PMGSY-III_ODISHA.shp"),
    "MAHARASHTRA": Path("data/raw/Proposal_PMGSY-III_Maharashtra/Proposal_PMGSY-III_MAHARASHTRA.shp"),
    "RAJASTHAN": Path("data/raw/Proposal_PMGSY-III_Rajasthan/Proposal_PMGSY-III_RAJASTHAN.shp"),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def geom_wkb_hash(geom) -> Optional[str]:
    if geom is None or geom.is_empty:
        return None
    raw = wkb.dumps(geom, hex=False)
    return hashlib.sha256(raw).hexdigest()


def count_vertices(geom) -> int:
    if geom is None or geom.is_empty:
        return 0
    gtype = geom.geom_type
    if gtype == "LineString":
        return len(geom.coords)
    if gtype == "MultiLineString":
        return sum(len(part.coords) for part in geom.geoms)
    if gtype == "GeometryCollection":
        return sum(count_vertices(part) for part in geom.geoms)
    return len(getattr(geom, "coords", []))


def chord_length_km_metric(geom_metric) -> float:
    if geom_metric is None or geom_metric.is_empty:
        return np.nan
    gtype = geom_metric.geom_type
    if gtype == "LineString":
        coords = list(geom_metric.coords)
        if len(coords) < 2:
            return np.nan
        dx = coords[-1][0] - coords[0][0]
        dy = coords[-1][1] - coords[0][1]
        return float(np.hypot(dx, dy) / 1000.0)
    if gtype == "MultiLineString":
        parts = [p for p in geom_metric.geoms if not p.is_empty and len(p.coords) >= 2]
        if not parts:
            return np.nan
        start = parts[0].coords[0]
        end = parts[-1].coords[-1]
        return float(np.hypot(end[0] - start[0], end[1] - start[1]) / 1000.0)
    return np.nan


def merge_package_geometries(geoms_4326: List) -> object:
    valid = [g for g in geoms_4326 if g is not None and not g.is_empty]
    if not valid:
        return None
    lines: List[LineString] = []
    others = []
    for g in valid:
        if isinstance(g, LineString):
            lines.append(g)
        elif isinstance(g, MultiLineString):
            lines.extend(list(g.geoms))
        else:
            others.append(g)
    if lines and not others:
        merged = line_merge(MultiLineString(lines))
        return merged
    if lines and others:
        return GeometryCollection([line_merge(MultiLineString(lines)), *others])
    return GeometryCollection(others)


def find_col(columns: List[str], candidates: List[str]) -> Optional[str]:
    col_map = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in col_map:
            return col_map[cand.lower()]
    return None


def compute_intra_package_topology(seg_metric_df: pd.DataFrame) -> pd.DataFrame:
    """Computes exact geometry duplicate flag, peer intersection flag, and max 1D shared overlap (m)
    within each package_uid using metric coordinates (EPSG:7755).
    """
    n = len(seg_metric_df)
    is_exact_dup = np.zeros(n, dtype=bool)
    intersects_peer = np.zeros(n, dtype=bool)
    shared_overlap_m = np.zeros(n, dtype=float)

    idx_lookup = {orig_idx: pos for pos, orig_idx in enumerate(seg_metric_df.index)}

    for _, grp in seg_metric_df.groupby("package_uid", sort=False):
        if len(grp) < 2:
            continue
        rows = list(grp.itertuples(index=True))
        for i in range(len(rows)):
            gi = rows[i].geom_metric
            if gi is None or gi.is_empty:
                continue
            pos_i = idx_lookup[rows[i].Index]
            for j in range(i + 1, len(rows)):
                gj = rows[j].geom_metric
                if gj is None or gj.is_empty:
                    continue
                pos_j = idx_lookup[rows[j].Index]

                # Exact / near-exact geometric equality within 1e-3 m
                if gi.equals_exact(gj, tolerance=1e-3):
                    is_exact_dup[pos_i] = True
                    is_exact_dup[pos_j] = True

                # General spatial intersection
                if gi.intersects(gj):
                    intersects_peer[pos_i] = True
                    intersects_peer[pos_j] = True

                    inter = gi.intersection(gj)
                    overlap_len_m = 0.0
                    if inter is not None and not inter.is_empty:
                        # Linear overlap length (1D LineString / MultiLineString / GeometryCollection)
                        if inter.geom_type in ("LineString", "MultiLineString", "GeometryCollection"):
                            overlap_len_m = float(inter.length)
                    if overlap_len_m > shared_overlap_m[pos_i]:
                        shared_overlap_m[pos_i] = overlap_len_m
                    if overlap_len_m > shared_overlap_m[pos_j]:
                        shared_overlap_m[pos_j] = overlap_len_m

    out = pd.DataFrame(
        {
            "is_exact_geom_dup_in_pkg": is_exact_dup,
            "intersects_pkg_peer": intersects_peer,
            "shared_overlap_m": shared_overlap_m,
        },
        index=seg_metric_df.index,
    )
    return out


def build_canonical(
    snapshot_id: str,
    include_all_shps: bool,
    out_root: Path,
    repo_root: Path,
) -> Dict:
    sources = dict(DEFAULT_SHAPEFILES)
    if include_all_shps:
        sources.update(EXTRA_SHAPEFILES)

    raw_frames: List[gpd.GeoDataFrame] = []
    file_hashes: Dict[str, Dict[str, str]] = {}

    for state_key, rel_shp in sources.items():
        shp_path = (repo_root / rel_shp).resolve()
        if not shp_path.exists():
            raise FileNotFoundError(f"Missing shapefile: {shp_path}")

        sidecar_hashes: Dict[str, str] = {}
        for ext in [".shp", ".shx", ".dbf", ".prj"]:
            sc = shp_path.with_suffix(ext)
            if not sc.exists():
                raise FileNotFoundError(f"Missing required shapefile sidecar: {sc}")
            sidecar_hashes[ext] = sha256_file(sc)
        file_hashes[state_key] = sidecar_hashes

        gdf = pyogrio.read_dataframe(shp_path)
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        else:
            gdf = gdf.to_crs("EPSG:4326")

        gdf = gdf.reset_index(drop=True)
        gdf["snapshot_id"] = snapshot_id
        gdf["source_state_key"] = state_key
        gdf["source_file"] = str(rel_shp.as_posix())
        gdf["source_file_sha256"] = sidecar_hashes[".shp"]
        gdf["source_row_idx"] = gdf.index.astype(np.int64)
        gdf["has_geometry"] = ~gdf.geometry.isna() & ~gdf.geometry.is_empty
        gdf["completeness_tier"] = "FULL_GEOM_3STATE" if state_key in DEFAULT_SHAPEFILES else "GEOM_EXTRA_6STATE"
        raw_frames.append(gdf)

    snap_raw = pd.concat(raw_frames, ignore_index=True)
    snap_raw_gdf = gpd.GeoDataFrame(snap_raw, geometry="geometry", crs="EPSG:4326")

    # Resolve attribute column names dynamically
    cols = list(snap_raw_gdf.columns)
    col_mrl = find_col(cols, ["MRL_ID", "mrl_id"])
    col_type = find_col(cols, ["PROPOSAL_T", "PROPOSAL_TYPE", "proposal_t", "proposal_type", "TYPE"])
    col_state_id = find_col(cols, ["STATE_ID", "state_id"])
    col_lgd_state = find_col(cols, ["LGD_STATE", "lgd_state"])
    col_dist_id = find_col(cols, ["DISTRICT_I", "DISTRICT_ID", "district_i", "district_id"])
    col_lgd_dist = find_col(cols, ["LGD_DISTRI", "LGD_DISTRICT", "lgd_distri", "lgd_district"])
    col_block_id = find_col(cols, ["BLOCK_ID", "block_id"])
    col_cn = find_col(cols, ["CN_CODE", "cn_code"])
    col_work = find_col(cols, ["WORK_NAME", "work_name"])
    col_year = find_col(cols, ["IMS_YEAR", "ims_year"])
    col_batch = find_col(cols, ["IMS_BATCH", "ims_batch"])
    col_prop_l = find_col(cols, ["PROPOSED_L", "proposed_l"])

    if not col_mrl:
        raise KeyError(f"Could not find MRL_ID column in {cols}")

    mrl_series = snap_raw_gdf[col_mrl].astype(str).str.strip()
    if col_type:
        prop_type_series = snap_raw_gdf[col_type].astype(str).str.strip().str.upper()
    else:
        prop_type_series = pd.Series(["P"] * len(snap_raw_gdf), index=snap_raw_gdf.index)

    state_scope_series = snap_raw_gdf["source_state_key"].astype(str).str.strip()

    # Deterministic IDs
    snap_raw_gdf["segment_uid"] = [
        sha256_text(f"{sid}|{st}|{fhash}|{ridx}")
        for sid, st, fhash, ridx in zip(
            snap_raw_gdf["snapshot_id"],
            snap_raw_gdf["source_state_key"],
            snap_raw_gdf["source_file_sha256"],
            snap_raw_gdf["source_row_idx"],
        )
    ]
    snap_raw_gdf["package_uid"] = [
        sha256_text(f"{sid}|{ptype}|{st}|{mrl}")
        for sid, ptype, st, mrl in zip(
            snap_raw_gdf["snapshot_id"],
            prop_type_series,
            state_scope_series,
            mrl_series,
        )
    ]
    snap_raw_gdf["geom_wkb_sha256"] = [geom_wkb_hash(g) for g in snap_raw_gdf.geometry]

    # Metric projection for exact length & spatial checks
    metric_gdf = snap_raw_gdf.to_crs(METRIC_CRS_INDIA)
    geom_len_km = (metric_gdf.geometry.length / 1000.0).astype(float)
    n_vertices = np.array([count_vertices(g) for g in snap_raw_gdf.geometry], dtype=np.int32)
    chord_km = np.array([chord_length_km_metric(g) for g in metric_gdf.geometry], dtype=float)

    with np.errstate(divide="ignore", invalid="ignore"):
        sinuosity = np.where(chord_km > 0.01, geom_len_km.to_numpy() / chord_km, np.nan)
        vertex_density_per_km = np.where(geom_len_km.to_numpy() > 0.0, n_vertices / geom_len_km.to_numpy(), np.nan)

    topo_df = compute_intra_package_topology(
        pd.DataFrame(
            {
                "package_uid": snap_raw_gdf["package_uid"].to_numpy(),
                "geom_metric": list(metric_gdf.geometry),
            },
            index=snap_raw_gdf.index,
        )
    )

    proposed_l_raw_km = (
        pd.to_numeric(snap_raw_gdf[col_prop_l], errors="coerce").astype(float)
        if col_prop_l
        else pd.Series(np.nan, index=snap_raw_gdf.index, dtype=float)
    )

    segments_gdf = gpd.GeoDataFrame(
        {
            "snapshot_id": snap_raw_gdf["snapshot_id"],
            "segment_uid": snap_raw_gdf["segment_uid"],
            "package_uid": snap_raw_gdf["package_uid"],
            "mrl_id": mrl_series,
            "proposal_type": prop_type_series,
            "source_state_key": state_scope_series,
            "state_id": snap_raw_gdf[col_state_id] if col_state_id else pd.NA,
            "lgd_state": snap_raw_gdf[col_lgd_state] if col_lgd_state else pd.NA,
            "district_id": snap_raw_gdf[col_dist_id] if col_dist_id else pd.NA,
            "lgd_distri": snap_raw_gdf[col_lgd_dist] if col_lgd_dist else pd.NA,
            "block_id": snap_raw_gdf[col_block_id] if col_block_id else pd.NA,
            "cn_code": snap_raw_gdf[col_cn] if col_cn else pd.NA,
            "work_name": snap_raw_gdf[col_work] if col_work else pd.NA,
            "ims_year": pd.to_numeric(snap_raw_gdf[col_year], errors="coerce") if col_year else pd.NA,
            "ims_batch": pd.to_numeric(snap_raw_gdf[col_batch], errors="coerce") if col_batch else pd.NA,
            "proposed_l_raw_km": proposed_l_raw_km,
            "geom_len_km": geom_len_km,
            "n_vertices": n_vertices,
            "chord_km": chord_km,
            "sinuosity": sinuosity,
            "vertex_density_per_km": vertex_density_per_km,
            "geom_wkb_sha256": snap_raw_gdf["geom_wkb_sha256"],
            "is_exact_geom_dup_in_pkg": topo_df["is_exact_geom_dup_in_pkg"],
            "intersects_pkg_peer": topo_df["intersects_pkg_peer"],
            "shared_overlap_m": topo_df["shared_overlap_m"],
            "has_geometry": snap_raw_gdf["has_geometry"],
            "completeness_tier": snap_raw_gdf["completeness_tier"],
            "source_file": snap_raw_gdf["source_file"],
            "source_file_sha256": snap_raw_gdf["source_file_sha256"],
            "source_row_idx": snap_raw_gdf["source_row_idx"],
            "geometry": snap_raw_gdf.geometry,
        },
        geometry="geometry",
        crs="EPSG:4326",
    )

    # Package aggregation & collision audit
    pkg_records: List[Dict] = []
    conflicting_proposed_l_count = 0
    cross_state_mrl_collisions = 0

    # Check if any mrl_id + proposal_type spans multiple source_state_key values
    mrl_state_counts = segments_gdf.groupby(["proposal_type", "mrl_id"])["source_state_key"].nunique()
    cross_state_mrl_collisions = int((mrl_state_counts > 1).sum())

    for pkg_uid, grp in segments_gdf.groupby("package_uid", sort=False):
        prop_l_vals = grp["proposed_l_raw_km"].dropna().unique()
        has_conflict_l = len(prop_l_vals) > 1
        if has_conflict_l:
            conflicting_proposed_l_count += 1

        proposed_l_km = float(prop_l_vals[0]) if len(prop_l_vals) >= 1 else np.nan
        sum_geom_len_km = float(grp["geom_len_km"].sum())
        ptype = str(grp["proposal_type"].iloc[0])

        if ptype == "P" and pd.notna(proposed_l_km) and proposed_l_km > 0:
            length_ratio_r = sum_geom_len_km / proposed_l_km
        else:
            length_ratio_r = np.nan

        pkg_records.append(
            {
                "snapshot_id": grp["snapshot_id"].iloc[0],
                "package_uid": pkg_uid,
                "mrl_id": grp["mrl_id"].iloc[0],
                "proposal_type": ptype,
                "source_state_key": grp["source_state_key"].iloc[0],
                "state_id": grp["state_id"].iloc[0],
                "lgd_state": grp["lgd_state"].iloc[0],
                "lgd_distri": grp["lgd_distri"].iloc[0],
                "block_id": grp["block_id"].iloc[0],
                "work_name": grp["work_name"].iloc[0],
                "ims_year": grp["ims_year"].iloc[0],
                "ims_batch": grp["ims_batch"].iloc[0],
                "proposed_l_km": proposed_l_km,
                "n_segments": int(len(grp)),
                "n_distinct_geom": int(grp["geom_wkb_sha256"].nunique(dropna=True)),
                "sum_geom_len_km": sum_geom_len_km,
                "mean_seg_len_km": float(grp["geom_len_km"].mean()),
                "max_seg_len_km": float(grp["geom_len_km"].max()),
                "total_vertices": int(grp["n_vertices"].sum()),
                "mean_sinuosity": float(grp["sinuosity"].mean(skipna=True)) if grp["sinuosity"].notna().any() else np.nan,
                "length_ratio_r": length_ratio_r,
                "has_conflicting_proposed_l": bool(has_conflict_l),
                "has_exact_geom_dup": bool(grp["is_exact_geom_dup_in_pkg"].any()),
                "has_linear_overlap": bool((grp["shared_overlap_m"] > 1.0).any()),
                "completeness_tier": grp["completeness_tier"].iloc[0],
                "geometry": merge_package_geometries(list(grp.geometry)),
            }
        )

    packages_gdf = gpd.GeoDataFrame(pkg_records, geometry="geometry", crs="EPSG:4326")
    assert packages_gdf["package_uid"].is_unique, "package_uid is not unique in packages table!"

    # Write outputs
    out_dir = (repo_root / out_root / snapshot_id).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_parquet_path = out_dir / "snapshot_raw.parquet"
    seg_parquet_path = out_dir / "segments.parquet"
    pkg_parquet_path = out_dir / "packages.parquet"
    seg_csv_path = out_dir / "segments_enriched.csv"
    pkg_csv_path = out_dir / "packages_enriched.csv"
    manifest_path = out_dir / "manifest.json"

    snap_raw_gdf.to_parquet(raw_parquet_path, index=False)
    segments_gdf.to_parquet(seg_parquet_path, index=False)
    packages_gdf.to_parquet(pkg_parquet_path, index=False)

    segments_gdf.drop(columns=["geometry"]).to_csv(seg_csv_path, index=False)
    packages_gdf.drop(columns=["geometry"]).to_csv(pkg_csv_path, index=False)

    manifest = {
        "schema_version": "v1",
        "snapshot_id": snapshot_id,
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "metric_crs": METRIC_CRS_INDIA,
        "metric_crs_name": CRS.from_user_input(METRIC_CRS_INDIA).name,
        "canonical_geometry_crs": "EPSG:4326",
        "include_all_shps": include_all_shps,
        "counts": {
            "raw_rows": int(len(snap_raw_gdf)),
            "segments": int(len(segments_gdf)),
            "packages": int(len(packages_gdf)),
            "packages_P": int((packages_gdf["proposal_type"] == "P").sum()),
            "packages_L": int((packages_gdf["proposal_type"] == "L").sum()),
            "multi_segment_packages": int((packages_gdf["n_segments"] > 1).sum()),
            "conflicting_proposed_l_packages": int(conflicting_proposed_l_count),
            "cross_state_mrl_collisions": int(cross_state_mrl_collisions),
        },
        "input_sidecar_sha256": file_hashes,
        "outputs": {
            "snapshot_raw.parquet": {"path": str(raw_parquet_path), "sha256": sha256_file(raw_parquet_path)},
            "segments.parquet": {"path": str(seg_parquet_path), "sha256": sha256_file(seg_parquet_path)},
            "packages.parquet": {"path": str(pkg_parquet_path), "sha256": sha256_file(pkg_parquet_path)},
            "segments_enriched.csv": {"path": str(seg_csv_path), "sha256": sha256_file(seg_csv_path)},
            "packages_enriched.csv": {"path": str(pkg_csv_path), "sha256": sha256_file(pkg_csv_path)},
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build canonical v1 PMGSY-III segment & package datasets.")
    parser.add_argument("--snapshot-id", default="pmgsy3_3state_v1", help="Versioned snapshot identifier.")
    parser.add_argument("--out-root", default="data/canonical/pmgsy_v1", help="Output directory root.")
    parser.add_argument(
        "--include-all-shps",
        action="store_true",
        help="Also ingest Odisha, Maharashtra, and Rajasthan shapefiles alongside Bihar, UP, and MP.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    manifest = build_canonical(
        snapshot_id=args.snapshot_id,
        include_all_shps=args.include_all_shps,
        out_root=Path(args.out_root),
        repo_root=repo_root,
    )
    print(json.dumps(manifest["counts"], indent=2))
    print(f"Wrote canonical outputs to: {(repo_root / args.out_root / args.snapshot_id).resolve()}")


if __name__ == "__main__":
    main()
