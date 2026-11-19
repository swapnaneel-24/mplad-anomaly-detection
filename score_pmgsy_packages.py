from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import geopandas as gpd
import numpy as np
import pandas as pd

NORMAL_MAD_CONSISTENCY = 0.6744897501960817


def build_scoring_prototype(
    snapshot_dir: Path,
    out_subdir: str = "scoring_option_b_v2",
    iqr_thresh: float = 3.0,
    mod_z_thresh: float = 3.5,
    min_abs_diff_med: float = 0.05,
    min_iqr_floor: float = 1e-4,
    min_mad_floor: float = 1e-4,
) -> Dict:
    seg_path = snapshot_dir / "segments.parquet"
    pkg_path = snapshot_dir / "packages.parquet"
    if not seg_path.exists() or not pkg_path.exists():
        raise FileNotFoundError(f"Expected segments.parquet and packages.parquet in {snapshot_dir}")

    seg = gpd.read_parquet(seg_path)
    pkg = gpd.read_parquet(pkg_path)

    # Segment-level hygiene flags aggregated to package_uid
    seg_work = seg.copy()
    seg_work["is_zero_len_seg"] = seg_work["geom_len_km"].fillna(0.0) <= 0.0
    seg_work["is_invalid_geom_seg"] = ~seg_work.geometry.is_valid

    seg_flags = (
        seg_work.groupby("package_uid", sort=False)
        .agg(
            n_zero_len_segments=("is_zero_len_seg", "sum"),
            n_invalid_segments=("is_invalid_geom_seg", "sum"),
            max_shared_overlap_m=("shared_overlap_m", "max"),
        )
        .reset_index()
    )
    seg_flags["has_zero_len_segment"] = seg_flags["n_zero_len_segments"] > 0
    seg_flags["has_invalid_segment_geom"] = seg_flags["n_invalid_segments"] > 0

    pkg_df = pd.DataFrame(pkg.drop(columns=["geometry"], errors="ignore")).merge(
        seg_flags, on="package_uid", how="left"
    )
    pkg_df["n_zero_len_segments"] = pkg_df["n_zero_len_segments"].fillna(0).astype(int)
    pkg_df["n_invalid_segments"] = pkg_df["n_invalid_segments"].fillna(0).astype(int)
    pkg_df["max_shared_overlap_m"] = pkg_df["max_shared_overlap_m"].fillna(0.0).astype(float)
    pkg_df["has_zero_len_segment"] = pkg_df["has_zero_len_segment"].fillna(False).astype(bool)
    pkg_df["has_invalid_segment_geom"] = pkg_df["has_invalid_segment_geom"].fillna(False).astype(bool)

    # Separate P road packages with valid positive proposed_l_km from L / non-P
    is_p_valid = (
        (pkg_df["proposal_type"] == "P")
        & pkg_df["proposed_l_km"].notna()
        & (pkg_df["proposed_l_km"] > 0)
        & pkg_df["length_ratio_r"].notna()
    )

    p_scored = pkg_df[is_p_valid].copy()
    non_p_df = pkg_df[~is_p_valid].copy()

    # State-specific reference distributions on R
    state_stats_rows: List[Dict] = []
    for st, grp in p_scored.groupby("source_state_key", sort=False):
        r = grp["length_ratio_r"].to_numpy(dtype=float)
        q25, med, q75 = np.percentile(r, [25, 50, 75])
        iqr = float(q75 - q25)
        mad = float(np.median(np.abs(r - med)))
        state_stats_rows.append(
            {
                "source_state_key": st,
                "n_p_scored": int(len(r)),
                "state_median_r": float(med),
                "state_q25_r": float(q25),
                "state_q75_r": float(q75),
                "state_iqr_r": iqr,
                "state_mad_r": mad,
            }
        )

    state_stats_df = pd.DataFrame(state_stats_rows)
    p_scored = p_scored.merge(state_stats_df, on="source_state_key", how="left")

    # Separate absolute and state-relative R deviation columns (no weighted blending)
    p_scored["r_diff_from_state_median"] = p_scored["length_ratio_r"] - p_scored["state_median_r"]
    p_scored["r_abs_diff_from_state_median"] = p_scored["r_diff_from_state_median"].abs()
    p_scored["r_diff_from_1"] = p_scored["length_ratio_r"] - 1.0
    p_scored["r_abs_diff_from_1"] = p_scored["r_diff_from_1"].abs()

    eff_iqr = np.maximum(p_scored["state_iqr_r"].to_numpy(dtype=float), min_iqr_floor)
    eff_mad = np.maximum(p_scored["state_mad_r"].to_numpy(dtype=float), min_mad_floor)

    p_scored["r_iqr_scaled_dev"] = p_scored["r_abs_diff_from_state_median"].to_numpy(dtype=float) / eff_iqr
    p_scored["r_modified_z"] = (
        NORMAL_MAD_CONSISTENCY * p_scored["r_diff_from_state_median"].to_numpy(dtype=float) / eff_mad
    )
    p_scored["r_abs_modified_z"] = p_scored["r_modified_z"].abs()

    # Exploratory cohort flag (explicitly NOT a confirmed anomaly threshold)
    p_scored["is_r_lt_0_5_exploratory"] = p_scored["length_ratio_r"] < 0.5

    # Revised policy: relative dispersion gate + practical absolute difference floor
    p_scored["passes_relative_r_gate"] = (
        (p_scored["r_iqr_scaled_dev"] >= iqr_thresh)
        | (p_scored["r_abs_modified_z"] >= mod_z_thresh)
    )
    p_scored["passes_practical_abs_floor"] = (
        p_scored["r_abs_diff_from_state_median"] >= min_abs_diff_med
    )
    p_scored["is_high_state_r_dev"] = (
        p_scored["passes_relative_r_gate"] & p_scored["passes_practical_abs_floor"]
    )

    tiers: List[str] = []
    reasons: List[str] = []
    tier_order_map = {
        "TOPOLOGY_EVIDENCE": 1,
        "HIGH_STATE_R_DEVIATION": 2,
        "SUBTHRESHOLD_REL_SHIFT": 3,
        "EXPLORATORY_R_LT_0_5": 4,
        "BASELINE_WITHIN_RANGE": 5,
    }

    for row in p_scored.itertuples(index=False):
        row_reasons: List[str] = []
        has_topo = bool(
            row.has_exact_geom_dup
            or row.has_linear_overlap
            or row.has_zero_len_segment
            or row.has_invalid_segment_geom
        )
        if row.has_exact_geom_dup:
            row_reasons.append("exact_geom_dup")
        if row.has_linear_overlap:
            row_reasons.append(f"linear_overlap_gt_1m({row.max_shared_overlap_m:.1f}m)")
        if row.has_zero_len_segment:
            row_reasons.append(f"zero_len_seg(n={row.n_zero_len_segments})")
        if row.has_invalid_segment_geom:
            row_reasons.append(f"invalid_seg_geom(n={row.n_invalid_segments})")

        if row.is_high_state_r_dev:
            row_reasons.append(
                f"state_r_dev(|d_med|={row.r_abs_diff_from_state_median:.3f}, iqr_x={row.r_iqr_scaled_dev:.2f}, mod_z={row.r_modified_z:.2f})"
            )
        elif row.passes_relative_r_gate and not row.passes_practical_abs_floor:
            row_reasons.append(
                f"below_abs_floor(|d_med|={row.r_abs_diff_from_state_median:.4f}<{min_abs_diff_med:.2f})"
            )

        if row.is_r_lt_0_5_exploratory:
            row_reasons.append("exploratory_r_lt_0_5")

        if has_topo:
            tier = "TOPOLOGY_EVIDENCE"
        elif row.is_high_state_r_dev:
            tier = "HIGH_STATE_R_DEVIATION"
        elif row.passes_relative_r_gate:
            tier = "SUBTHRESHOLD_REL_SHIFT"
        elif row.is_r_lt_0_5_exploratory:
            tier = "EXPLORATORY_R_LT_0_5"
        else:
            tier = "BASELINE_WITHIN_RANGE"
            row_reasons.append("within_state_baseline")

        tiers.append(tier)
        reasons.append("; ".join(row_reasons))

    p_scored["investigation_tier"] = tiers
    p_scored["priority_reason"] = reasons
    p_scored["_tier_sort"] = p_scored["investigation_tier"].map(tier_order_map)

    p_scored = p_scored.sort_values(
        by=["_tier_sort", "r_abs_diff_from_state_median", "r_abs_modified_z", "package_uid"],
        ascending=[True, False, False, True],
    ).reset_index(drop=True)
    p_scored["priority_rank"] = np.arange(1, len(p_scored) + 1, dtype=int)
    p_scored = p_scored.drop(columns=["_tier_sort"])

    out_dir = snapshot_dir / out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)

    scored_csv_path = out_dir / "packages_p_scored_option_b_v2.csv"
    scored_parquet_path = out_dir / "packages_p_scored_option_b_v2.parquet"
    state_ref_csv_path = out_dir / "state_r_reference_stats.csv"
    non_p_csv_path = out_dir / "packages_non_p_excluded.csv"
    summary_json_path = out_dir / "scoring_summary_v2.json"

    p_scored.to_csv(scored_csv_path, index=False)
    p_scored.to_parquet(scored_parquet_path, index=False)
    state_stats_df.to_csv(state_ref_csv_path, index=False)
    non_p_df.to_csv(non_p_csv_path, index=False)

    tier_by_state = (
        pd.crosstab(p_scored["source_state_key"], p_scored["investigation_tier"])
        .to_dict(orient="index")
    )

    summary = {
        "scoring_mode": "Option B v2 — R Ratio + Topology Focus First (Revised Descriptive Policy)",
        "validation_status": "DESCRIPTIVE_PROTOTYPE_NOT_VALIDATED_MODEL",
        "out_of_scope": ["IsolationForest", "LOF", "weighted_composite_scores", "production_scoring"],
        "policy_parameters": {
            "iqr_thresh": iqr_thresh,
            "mod_z_thresh": mod_z_thresh,
            "min_abs_diff_med": min_abs_diff_med,
            "exploratory_r_threshold": 0.5,
        },
        "exploratory_cohort_note": "is_r_lt_0_5_exploratory is an exploratory cohort flag, not a confirmed anomaly threshold.",
        "snapshot_id": str(snapshot_dir.name),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "total_packages": int(len(pkg_df)),
            "p_packages_scored": int(len(p_scored)),
            "non_p_or_missing_r_excluded": int(len(non_p_df)),
            "investigation_tiers": {
                k: int(v) for k, v in p_scored["investigation_tier"].value_counts().items()
            },
            "investigation_tiers_by_state": tier_by_state,
            "exploratory_r_lt_0_5_count": int(p_scored["is_r_lt_0_5_exploratory"].sum()),
        },
        "state_reference_stats": state_stats_rows,
        "artifacts": {
            "packages_p_scored_option_b_v2.csv": str(scored_csv_path),
            "packages_p_scored_option_b_v2.parquet": str(scored_parquet_path),
            "state_r_reference_stats.csv": str(state_ref_csv_path),
            "packages_non_p_excluded.csv": str(non_p_csv_path),
        },
    }
    summary_json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Option B v2 revised descriptive scoring policy for PMGSY P packages.")
    parser.add_argument(
        "--snapshot-dir",
        default="data/canonical/pmgsy_v1/pmgsy3_3state_v1",
        help="Path to canonical snapshot directory.",
    )
    parser.add_argument(
        "--out-subdir",
        default="scoring_option_b_v2",
        help="Subdirectory inside snapshot-dir for v2 scoring outputs.",
    )
    parser.add_argument("--iqr-thresh", type=float, default=3.0, help="State IQR multiple threshold.")
    parser.add_argument("--mod-z-thresh", type=float, default=3.5, help="State modified Z-score threshold.")
    parser.add_argument(
        "--min-abs-diff-med",
        type=float,
        default=0.05,
        help="Minimum practical |R - state_median_R| floor required for HIGH_STATE_R_DEVIATION.",
    )
    args = parser.parse_args()

    summary = build_scoring_prototype(
        snapshot_dir=Path(args.snapshot_dir).resolve(),
        out_subdir=args.out_subdir,
        iqr_thresh=args.iqr_thresh,
        mod_z_thresh=args.mod_z_thresh,
        min_abs_diff_med=args.min_abs_diff_med,
    )
    print(json.dumps(summary["counts"], indent=2))


if __name__ == "__main__":
    main()
