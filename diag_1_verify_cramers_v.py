from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

import run_controlled_if_experiment as exp


def cramers_v_with_sparsity(a: pd.Series, b: pd.Series) -> dict:
    ct = pd.crosstab(a.fillna("MISSING").astype(str), b.fillna("MISSING").astype(str))
    if ct.shape[0] < 2 or ct.shape[1] < 2:
        return {"cramers_v": 0.0, "rows": ct.shape[0], "cols": ct.shape[1], "pct_expected_lt_5": 0.0, "min_expected": 0.0}
    chi2, _, _, expected = chi2_contingency(ct)
    n = ct.to_numpy().sum()
    min_dim = min(ct.shape[0] - 1, ct.shape[1] - 1)
    v = float(np.sqrt(chi2 / (n * min_dim))) if n > 1 and min_dim > 0 else 0.0
    pct_lt5 = float((expected < 5.0).mean() * 100.0)
    return {
        "cramers_v": round(v, 4),
        "rows": int(ct.shape[0]),
        "cols": int(ct.shape[1]),
        "pct_expected_lt_5": round(pct_lt5, 1),
        "min_expected": round(float(expected.min()), 3),
    }


def main() -> None:
    repo_root = Path.cwd()
    snap_dir = repo_root / "data/canonical/pmgsy_v1/pmgsy3_3state_v1"
    v2_csv = snap_dir / "scoring_option_b_v2/packages_p_scored_option_b_v2.csv"
    out_dir = repo_root / "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1/diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = exp.build_feature_matrix(snap_dir, v2_csv)
    scores = exp.fit_stratified_if(df, seed=42, contamination=0.05)
    top5 = exp.top_k_per_state(df, scores, frac=0.05)
    df["if_strat_top5"] = df["package_uid"].isin(top5)

    # A) Replicate the subset contingency table (cohort_year_batch vs state on if_strat_top5 == True)
    sub = df[df["if_strat_top5"]]
    sub_stats = cramers_v_with_sparsity(sub["cohort_year_batch"], sub["source_state_key"])
    print("=== A) SUBSET TABLE (if_strat_top5 == True: cohort_year_batch vs source_state_key) ===")
    print(sub_stats)

    # B) Full-population within-state association: if_strat_top5 vs cohort_year_batch per state
    within_rows = []
    for st, grp in df.groupby("source_state_key"):
        stats = cramers_v_with_sparsity(grp["if_strat_top5"].astype(str), grp["cohort_year_batch"])
        stats["source_state_key"] = st
        stats["n_packages"] = int(len(grp))
        stats["n_top5"] = int(grp["if_strat_top5"].sum())
        within_rows.append(stats)

    within_df = pd.DataFrame(within_rows)[[
        "source_state_key", "n_packages", "n_top5", "cramers_v", "rows", "cols", "pct_expected_lt_5", "min_expected"
    ]]
    print("\n=== B) WITHIN-STATE ASSOCIATION (if_strat_top5 vs cohort_year_batch) ===")
    print(within_df.to_string(index=False))
    within_df.to_csv(out_dir / "cramers_v_verification.csv", index=False)


if __name__ == "__main__":
    main()
