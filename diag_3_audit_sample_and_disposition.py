from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

import run_controlled_if_experiment as exp


def main() -> None:
    repo_root = Path.cwd()
    snap_dir = repo_root / "data/canonical/pmgsy_v1/pmgsy3_3state_v1"
    v2_csv = snap_dir / "scoring_option_b_v2/packages_p_scored_option_b_v2.csv"
    out_dir = repo_root / "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1/diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = exp.build_feature_matrix(snap_dir, v2_csv)
    scores = exp.fit_stratified_if(df, seed=42, contamination=0.05)
    top5_set = exp.top_k_per_state(df, scores, frac=0.05)

    df["if_strat_score"] = scores
    df["if_strat_top5"] = df["package_uid"].isin(top5_set)

    rng = np.random.default_rng(20261123)
    pos_pool = df[df["if_strat_top5"]].copy()
    neg_pool = df[~df["if_strat_top5"]].copy()

    n_pos = min(30, len(pos_pool))
    pos_sample = pos_pool.loc[rng.choice(pos_pool.index.to_numpy(), size=n_pos, replace=False)].copy()
    pos_sample["audit_group"] = "IF_TOP5_SELECTED"

    # Match controls by source_state_key and cohort_year_batch where possible
    matched_indices = []
    used_neg = set()
    for _, r in pos_sample.iterrows():
        cand = neg_pool[
            (~neg_pool.index.isin(used_neg))
            & (neg_pool["source_state_key"] == r["source_state_key"])
            & (neg_pool["cohort_year_batch"] == r["cohort_year_batch"])
        ]
        if len(cand) == 0:
            cand = neg_pool[
                (~neg_pool.index.isin(used_neg))
                & (neg_pool["source_state_key"] == r["source_state_key"])
            ]
        if len(cand) > 0:
            pick = int(rng.choice(cand.index.to_numpy()))
            matched_indices.append(pick)
            used_neg.add(pick)

    neg_sample = neg_pool.loc[matched_indices].copy()
    neg_sample["audit_group"] = "MATCHED_NON_IF_CONTROL"

    audit_df = pd.concat([pos_sample, neg_sample], ignore_index=True)
    audit_df["observed_geometry_issue"] = ""
    audit_df["supporting_source_evidence"] = ""
    audit_df["alternative_benign_explanation"] = ""
    audit_df["reviewer_confidence"] = ""
    audit_df["audit_disposition"] = ""
    audit_df["reviewer_notes"] = ""

    keep_cols = [
        c
        for c in [
            "audit_group",
            "package_uid",
            "mrl_id",
            "source_state_key",
            "cohort_year_batch",
            "investigation_tier",
            "if_strat_score",
            "if_strat_top5",
            "n_segments",
            "mean_seg_len_km",
            "mean_sinuosity",
            "vertices_per_km",
            "seg_len_concentration",
            "proposed_l_km",
            "sum_geom_len_km",
            "work_name",
            "observed_geometry_issue",
            "supporting_source_evidence",
            "alternative_benign_explanation",
            "reviewer_confidence",
            "audit_disposition",
            "reviewer_notes",
        ]
        if c in audit_df.columns
    ]
    audit_path = out_dir / "if_enriched_audit_sample.csv"
    audit_df[keep_cols].to_csv(audit_path, index=False)

    disp_path = repo_root / "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1/PEIARS_IF_DISPOSITION_V1.md"
    disp_md = (
        "# PEIARS — Final Isolation Forest Experiment Disposition (v1)\n\n"
        f"- **Recorded At (UTC):** {datetime.now(timezone.utc).isoformat()}\n"
        "- **Primary Evidence Pipeline:** Option B v2 (`scoring_option_b_v2`) + Topology Audit Track (`exact_geom_dup`, `linear_overlap`, `zero_len_segment`, `invalid_segment_geom`).\n"
        "- **Isolation Forest Status:** **Research-only sandbox** (admission gate failed on cohort confounding: `strat_cohort_cramers_v_mean = 0.675` vs `<= 0.35`, despite seed stability `0.8781` and low overlap with `R` baseline `0.037`).\n"
        "- **Prohibited Actions:** No Option B v3 yet, no weighted IF + R composite score, and no production ML anomaly labels without independent validation.\n"
        "- **Diagnostic Artifacts:** `diagnostics/cramers_v_verification.csv`, `diagnostics/feature_ablation_summary.csv`, `diagnostics/if_enriched_audit_sample.csv`.\n"
    )
    disp_path.write_text(disp_md, encoding="utf-8")

    print(f"Saved IF-enriched audit sample ({len(audit_df)} rows: {len(pos_sample)} selected + {len(neg_sample)} controls) -> {audit_path}")
    print(f"Wrote formal disposition record -> {disp_path}")


if __name__ == "__main__":
    main()
