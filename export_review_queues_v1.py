from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import geopandas as gpd
import numpy as np
import pandas as pd


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def assign_abs_dev_stratum(abs_diff: float) -> str:
    if abs_diff < 0.02:
        return "SMALL_ABS_DIFF_LT_0.02"
    if abs_diff < 0.15:
        return "MODERATE_ABS_DIFF_0.02_TO_0.15"
    return "LARGE_ABS_DIFF_GE_0.15"


def export_queues(
    snapshot_dir: Path,
    scoring_subdir: str = "scoring_option_b_v1",
    out_subdir: str = "review_queues",
    per_state_target: int = 30,
    seed: int = 42,
) -> Dict:
    scoring_dir = snapshot_dir / scoring_subdir
    scored_csv = scoring_dir / "packages_p_scored_option_b.csv"
    seg_parquet = snapshot_dir / "segments.parquet"

    if not scored_csv.exists():
        raise FileNotFoundError(f"Missing scored packages CSV: {scored_csv}")
    if not seg_parquet.exists():
        raise FileNotFoundError(f"Missing canonical segments Parquet: {seg_parquet}")

    df = pd.read_csv(scored_csv)
    seg = gpd.read_parquet(seg_parquet)

    # Add explicit absolute discrepancy vs 1.0 alongside state-median deviations
    df["r_diff_from_1"] = df["length_ratio_r"] - 1.0
    df["r_abs_diff_from_1"] = df["r_diff_from_1"].abs()
    df["abs_dev_stratum"] = df["r_abs_diff_from_state_median"].apply(assign_abs_dev_stratum)

    # Reviewer annotation columns (blank templates for manual audit)
    df["reviewer_category"] = ""
    df["reviewer_notes"] = ""

    review_cols = [
        "priority_rank",
        "investigation_tier",
        "priority_reason",
        "source_state_key",
        "mrl_id",
        "work_name",
        "ims_year",
        "ims_batch",
        "n_segments",
        "n_distinct_geom",
        "proposed_l_km",
        "sum_geom_len_km",
        "length_ratio_r",
        "state_median_r",
        "state_iqr_r",
        "state_mad_r",
        "r_diff_from_state_median",
        "r_abs_diff_from_state_median",
        "r_diff_from_1",
        "r_abs_diff_from_1",
        "r_iqr_scaled_dev",
        "r_modified_z",
        "abs_dev_stratum",
        "is_r_lt_0_5_exploratory",
        "has_exact_geom_dup",
        "has_linear_overlap",
        "max_shared_overlap_m",
        "has_zero_len_segment",
        "n_zero_len_segments",
        "has_invalid_segment_geom",
        "n_invalid_segments",
        "package_uid",
        "snapshot_id",
        "completeness_tier",
        "reviewer_category",
        "reviewer_notes",
    ]
    review_cols = [c for c in review_cols if c in df.columns]

    # Queue 1: All TOPOLOGY_EVIDENCE packages (n = 6) + segment-level detail
    q1_pkg = (
        df[df["investigation_tier"] == "TOPOLOGY_EVIDENCE"]
        .sort_values("priority_rank")
        .loc[:, review_cols]
        .reset_index(drop=True)
    )

    seg_detail = seg[seg["package_uid"].isin(q1_pkg["package_uid"])].copy()
    seg_detail["is_valid_geom"] = seg_detail.geometry.is_valid
    seg_detail["geom_type"] = seg_detail.geometry.geom_type
    seg_detail_cols = [
        "source_state_key",
        "mrl_id",
        "package_uid",
        "segment_uid",
        "source_row_idx",
        "geom_type",
        "is_valid_geom",
        "geom_len_km",
        "chord_km",
        "sinuosity",
        "n_vertices",
        "is_exact_geom_dup_in_pkg",
        "intersects_pkg_peer",
        "shared_overlap_m",
        "geom_wkb_sha256",
        "source_file",
    ]
    q1_seg = (
        seg_detail.drop(columns=["geometry"])
        .loc[:, [c for c in seg_detail_cols if c in seg_detail.columns]]
        .sort_values(["source_state_key", "mrl_id", "source_row_idx"])
        .reset_index(drop=True)
    )

    # Queue 2: Exploratory R < 0.5 cohort (n = 135)
    q2_exp = (
        df[df["is_r_lt_0_5_exploratory"].fillna(False)]
        .sort_values(["length_ratio_r", "source_state_key", "mrl_id"], ascending=[True, True, True])
        .loc[:, review_cols]
        .reset_index(drop=True)
    )

    # Queue 3: Stratified sample from HIGH_STATE_R_DEVIATION (n = 1,129)
    high_dev = df[df["investigation_tier"] == "HIGH_STATE_R_DEVIATION"].copy()
    rng = np.random.default_rng(seed)

    strata_order = [
        "SMALL_ABS_DIFF_LT_0.02",
        "MODERATE_ABS_DIFF_0.02_TO_0.15",
        "LARGE_ABS_DIFF_GE_0.15",
    ]
    per_bin_quota = per_state_target // len(strata_order)

    sampled_parts: List[pd.DataFrame] = []
    stratum_summary: List[Dict] = []

    for st, st_grp in high_dev.groupby("source_state_key", sort=True):
        chosen_uids: List[str] = []
        # First pass: draw up to per_bin_quota from each absolute-deviation stratum
        for b_name in strata_order:
            b_grp = st_grp[st_grp["abs_dev_stratum"] == b_name]
            k = min(len(b_grp), per_bin_quota)
            if k > 0:
                idx = rng.choice(b_grp.index.to_numpy(), size=k, replace=False)
                chosen_uids.extend(b_grp.loc[idx, "package_uid"].tolist())

        # Second pass: if a state had fewer than quota in some bin, backfill from remaining rows in that state
        rem = st_grp[~st_grp["package_uid"].isin(chosen_uids)]
        need = min(len(rem), per_state_target - len(chosen_uids))
        if need > 0:
            idx = rng.choice(rem.index.to_numpy(), size=need, replace=False)
            chosen_uids.extend(rem.loc[idx, "package_uid"].tolist())

        st_sample = st_grp[st_grp["package_uid"].isin(chosen_uids)].copy()
        sampled_parts.append(st_sample)

        for b_name in strata_order:
            stratum_summary.append(
                {
                    "state": st,
                    "abs_dev_stratum": b_name,
                    "pool_count": int((st_grp["abs_dev_stratum"] == b_name).sum()),
                    "sampled_count": int((st_sample["abs_dev_stratum"] == b_name).sum()),
                }
            )

    q3_sample = (
        pd.concat(sampled_parts, ignore_index=True)
        .sort_values(["source_state_key", "abs_dev_stratum", "r_abs_diff_from_state_median"], ascending=[True, True, False])
        .loc[:, review_cols]
        .reset_index(drop=True)
    )

    out_dir = scoring_dir / out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)

    p_q1 = out_dir / "queue_1_topology_evidence.csv"
    p_q1b = out_dir / "queue_1b_topology_segments_detail.csv"
    p_q2 = out_dir / "queue_2_exploratory_r_lt_0_5.csv"
    p_q3 = out_dir / "queue_3_high_r_dev_stratified_sample.csv"
    p_manifest = out_dir / "review_queues_manifest.json"

    q1_pkg.to_csv(p_q1, index=False)
    q1_seg.to_csv(p_q1b, index=False)
    q2_exp.to_csv(p_q2, index=False)
    q3_sample.to_csv(p_q3, index=False)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_scored_csv": str(scored_csv),
        "sampling_seed": seed,
        "per_state_sample_target": per_state_target,
        "queues": {
            "queue_1_topology_evidence.csv": {
                "path": str(p_q1),
                "rows": int(len(q1_pkg)),
                "sha256": sha256_file(p_q1),
            },
            "queue_1b_topology_segments_detail.csv": {
                "path": str(p_q1b),
                "rows": int(len(q1_seg)),
                "sha256": sha256_file(p_q1b),
            },
            "queue_2_exploratory_r_lt_0_5.csv": {
                "path": str(p_q2),
                "rows": int(len(q2_exp)),
                "sha256": sha256_file(p_q2),
            },
            "queue_3_high_r_dev_stratified_sample.csv": {
                "path": str(p_q3),
                "rows": int(len(q3_sample)),
                "sha256": sha256_file(p_q3),
            },
        },
        "high_r_dev_strata_breakdown": stratum_summary,
    }
    p_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Export focused Option B review queues for PEIARS evidence review.")
    parser.add_argument(
        "--snapshot-dir",
        default="data/canonical/pmgsy_v1/pmgsy3_3state_v1",
        help="Canonical snapshot directory.",
    )
    parser.add_argument("--per-state-target", type=int, default=30, help="Stratified sample target per state for Queue 3.")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic RNG seed.")
    args = parser.parse_args()

    manifest = export_queues(
        snapshot_dir=Path(args.snapshot_dir).resolve(),
        per_state_target=args.per_state_target,
        seed=args.seed,
    )
    print("=== EXPORTED REVIEW QUEUES ===")
    for name, info in manifest["queues"].items():
        print(f"{name:42s} | rows={info['rows']:4d}")
    print("\n=== QUEUE 3 STRATA BREAKDOWN (HIGH_STATE_R_DEVIATION) ===")
    print(pd.DataFrame(manifest["high_r_dev_strata_breakdown"]).to_string(index=False))


if __name__ == "__main__":
    main()
