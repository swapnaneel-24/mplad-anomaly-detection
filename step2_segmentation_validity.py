from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

import run_controlled_if_experiment as exp


def to_md_table(df: pd.DataFrame) -> str:
    headers = [str(c) for c in df.columns]
    rows = [[str(v) for v in r] for r in df.itertuples(index=False, name=None)]
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    hdr = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    body = ["| " + " | ".join(r[i].ljust(widths[i]) for i, h in enumerate(headers)) + " |" for r in rows]
    return "\n".join([hdr, sep, *body])


def seg_bucket(n_seg: int) -> str:
    if n_seg <= 1:
        return "1_seg"
    if n_seg == 2:
        return "2_segs"
    if n_seg <= 5:
        return "3_to_5_segs"
    return "6_plus_segs"


def main() -> None:
    repo_root = Path.cwd()
    snap_dir = repo_root / "data/canonical/pmgsy_v1/pmgsy3_3state_v1"
    v2_csv = snap_dir / "scoring_option_b_v2/packages_p_scored_option_b_v2.csv"
    out_dir = repo_root / "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = exp.build_feature_matrix(snap_dir, v2_csv)
    scores = exp.fit_stratified_if(df, seed=42, contamination=0.05)
    top5_set = exp.top_k_per_state(df, scores, frac=0.05)
    df["if_strat_top5"] = df["package_uid"].isin(top5_set)
    df["seg_bucket"] = df["n_segments"].fillna(0).astype(int).map(seg_bucket)

    bucket_rows = []
    for bkt, grp in df.groupby("seg_bucket", sort=False):
        sel = grp[grp["if_strat_top5"]]
        ctrl = grp[~grp["if_strat_top5"]]
        bucket_rows.append({
            "seg_bucket": bkt,
            "total_pkgs": int(len(grp)),
            "if_top5_n": int(len(sel)),
            "if_top5_rate": round(float(len(sel) / max(1, len(grp))), 4),
            "sel_med_sinuosity": round(float(sel["mean_sinuosity"].median()), 3) if len(sel) else np.nan,
            "ctrl_med_sinuosity": round(float(ctrl["mean_sinuosity"].median()), 3) if len(ctrl) else np.nan,
            "sel_med_vert_km": round(float(sel["vertices_per_km"].median()), 2) if len(sel) else np.nan,
            "ctrl_med_vert_km": round(float(ctrl["vertices_per_km"].median()), 2) if len(ctrl) else np.nan,
            "sel_med_conc": round(float(sel["seg_len_concentration"].median()), 3) if len(sel) else np.nan,
            "ctrl_med_conc": round(float(ctrl["seg_len_concentration"].median()), 3) if len(ctrl) else np.nan,
        })

    bkt_df = pd.DataFrame(bucket_rows)

    lines = [
        "# PEIARS — Isolation Forest Segmentation Validity Report",
        "",
        f"- **Generated At (UTC):** {datetime.now(timezone.utc).isoformat()}",
        "- **Ablation Reference:** Dropping `n_segments` gives Jaccard `0.5587` vs full 5 features; dropping `seg_len_concentration` gives `0.4649`; dropping both gives `0.1526`.",
        "",
        "## 1. IF Top-5% Selection & Feature Profiles Within Matched Segment-Count Buckets",
        "",
        to_md_table(bkt_df),
        "",
        "## 2. Diagnostic Takeaway",
        "",
        "- Compare `if_top5_rate` and median `mean_sinuosity` / `vertices_per_km` / `seg_len_concentration` between `IF_TOP5` (`sel_*`) and non-selected rows (`ctrl_*`) within the same `seg_bucket`.",
        "- High selection rates or concentration shifts in multi-segment buckets alongside feature-ablation turnover (`0.1526` without both segmentation features) indicate that segmentation structure strongly shapes candidate selection and requires empirical verification on the 60-case audit rather than assuming infrastructure defects.",
    ]

    report_path = out_dir / "IF_SEGMENTATION_VALIDITY_REPORT.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {report_path}\n")
    print(bkt_df.to_string(index=False))


if __name__ == "__main__":
    main()
