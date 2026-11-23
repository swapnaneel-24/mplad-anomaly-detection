from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

import run_controlled_if_experiment as exp


def seg_bucket(n_seg: int) -> str:
    if n_seg <= 1:
        return "1_seg"
    if n_seg == 2:
        return "2_segs"
    if n_seg <= 5:
        return "3_to_5_segs"
    return "6_plus_segs"


def len_band(km: float) -> str:
    if pd.isna(km) or km < 5.0:
        return "lt_5km"
    if km < 10.0:
        return "5_to_10km"
    if km < 20.0:
        return "10_to_20km"
    return "ge_20km"


def main() -> None:
    repo_root = Path.cwd()
    snap_dir = repo_root / "data/canonical/pmgsy_v1/pmgsy3_3state_v1"
    v2_csv = snap_dir / "scoring_option_b_v2/packages_p_scored_option_b_v2.csv"
    exp_dir = repo_root / "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1"

    v1_res = pd.read_csv(exp_dir / "IF_ENRICHED_AUDIT_RESULTS_V1.csv")
    exclude_uids = set(v1_res["package_uid"].astype(str))

    df = exp.build_feature_matrix(snap_dir, v2_csv)
    scores = exp.fit_stratified_if(df, seed=42, contamination=0.05)
    top5_set = exp.top_k_per_state(df, scores, frac=0.05)
    df["if_strat_top5"] = df["package_uid"].isin(top5_set)
    df["seg_bucket"] = df["n_segments"].fillna(0).astype(int).map(seg_bucket)
    df["len_band"] = df["proposed_l_km"].map(len_band)

    elig = df[~df["package_uid"].isin(exclude_uids)].copy()
    pos = elig[elig["if_strat_top5"]].copy()
    neg = elig[~elig["if_strat_top5"]].copy()

    # Check exact stratum counts: state x cohort_year_batch x seg_bucket x len_band
    strata_cols = ["source_state_key", "cohort_year_batch", "seg_bucket", "len_band"]
    pos_counts = pos.groupby(strata_cols).size().rename("n_if_top5")
    neg_counts = neg.groupby(strata_cols).size().rename("n_non_if_ctrl")
    comp = pd.concat([pos_counts, neg_counts], axis=1).fillna(0).astype(int).reset_index()
    comp["max_exact_1to1_pairs"] = np.minimum(comp["n_if_top5"], comp["n_non_if_ctrl"])

    total_pos_elig = int(len(pos))
    total_exact_pairs = int(comp["max_exact_1to1_pairs"].sum())

    # Relaxed stratum: drop len_band -> state x cohort_year_batch x seg_bucket
    rel1_cols = ["source_state_key", "cohort_year_batch", "seg_bucket"]
    p1 = pos.groupby(rel1_cols).size().rename("n_pos")
    n1 = neg.groupby(rel1_cols).size().rename("n_neg")
    c1 = pd.concat([p1, n1], axis=1).fillna(0).astype(int)
    total_rel1_pairs = int(np.minimum(c1["n_pos"], c1["n_neg"]).sum())

    # Relaxed stratum 2: drop cohort_year_batch -> state x seg_bucket
    rel2_cols = ["source_state_key", "seg_bucket"]
    p2 = pos.groupby(rel2_cols).size().rename("n_pos")
    n2 = neg.groupby(rel2_cols).size().rename("n_neg")
    c2 = pd.concat([p2, n2], axis=1).fillna(0).astype(int)
    total_rel2_pairs = int(np.minimum(c2["n_pos"], c2["n_neg"]).sum())

    report_path = exp_dir / "IF_V3_SAMPLING_FEASIBILITY_REPORT.md"
    lines = [
        "# PEIARS — v3 Expanded Audit Sampling Feasibility Report",
        "",
        f"- **Generated At (UTC):** {datetime.now(timezone.utc).isoformat()}",
        f"- **Total Canonical `P` Packages:** `{len(df)}`",
        f"- **Excluded v1 Audit Packages:** `{len(exclude_uids)}`",
        f"- **Eligible Remaining Pool:** `{len(elig)}` (`{total_pos_elig}` IF top-5%, `{len(neg)}` non-IF controls)",
        "- **Target v3 Sample Size:** `120` packages (`60` IF top-5% + `60` matched controls).",
        "",
        "## Matching Capacity Across Predefined Relaxation Tiers",
        "",
        f"- **Tier 0 (Exact: `state × cohort_year_batch × seg_bucket × len_band`):** `{total_exact_pairs}` max 1:1 pairs available across `{total_pos_elig}` eligible IF top-5% packages.",
        f"- **Tier 1 (Drop `len_band`: `state × cohort_year_batch × seg_bucket`):** `{total_rel1_pairs}` max 1:1 pairs available.",
        f"- **Tier 2 (Drop `cohort_year_batch`: `state × seg_bucket`):** `{total_rel2_pairs}` max 1:1 pairs available.",
        "",
        "## Feasibility Verdict",
        "",
        f"- With `{total_exact_pairs}` exact Tier-0 pairs and `{total_rel1_pairs}` Tier-1 pairs available for a `60`-pair target, 1:1 matched sampling is **{'FEASIBLE' if total_rel1_pairs >= 60 else 'CONSTRAINED'}** using deterministic fallback (`Tier 0 -> Tier 1 -> Tier 2`).",
        "- Sample generation remains **HOLD** until `IF_10_CASE_VALIDITY_REVIEW_V1.csv` is adjudicated and frozen.",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {report_path}\n")
    print("\n".join(lines[3:]))


if __name__ == "__main__":
    main()
