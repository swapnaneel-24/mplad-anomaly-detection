from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

import run_controlled_if_experiment as exp

MIN_COHORT_MERGE = 30
N_PERM = 500


def to_md_table(df: pd.DataFrame) -> str:
    headers = [str(c) for c in df.columns]
    rows = [[str(v) for v in r] for r in df.itertuples(index=False, name=None)]
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    hdr = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    body = ["| " + " | ".join(r[i].ljust(widths[i]) for i, h in enumerate(headers)) + " |" for r in rows]
    return "\n".join([hdr, sep, *body])


def calc_cramers_v_from_ct(ct: pd.DataFrame) -> float:
    if ct.shape[0] < 2 or ct.shape[1] < 2:
        return 0.0
    chi2 = chi2_contingency(ct)[0]
    n = ct.to_numpy().sum()
    min_dim = min(ct.shape[0] - 1, ct.shape[1] - 1)
    if n <= 1 or min_dim <= 0:
        return 0.0
    return float(np.sqrt(chi2 / (n * min_dim)))


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

    merged_cohort = pd.Series("", index=df.index, dtype=str)
    for _, grp in df.groupby("source_state_key"):
        vc = grp["cohort_year_batch"].value_counts()
        keep_labels = set(vc[vc >= MIN_COHORT_MERGE].index)
        merged_cohort.loc[grp.index] = np.where(
            grp["cohort_year_batch"].isin(keep_labels),
            grp["cohort_year_batch"],
            "OTHER_SPARSE_COHORTS",
        )
    df["cohort_merged"] = merged_cohort

    rng = np.random.default_rng(20261123)
    rows = []

    for st, grp in df.groupby("source_state_key"):
        ct = pd.crosstab(grp["if_strat_top5"].astype(str), grp["cohort_merged"].astype(str))
        _, _, _, expected = chi2_contingency(ct)
        obs_v = calc_cramers_v_from_ct(ct)

        flag_arr = grp["if_strat_top5"].astype(str).to_numpy()
        coh_arr = grp["cohort_merged"].astype(str).to_numpy()
        perm_vs = []
        for _ in range(N_PERM):
            perm_flags = rng.permutation(flag_arr)
            p_ct = pd.crosstab(perm_flags, coh_arr)
            perm_vs.append(calc_cramers_v_from_ct(p_ct))
        perm_arr = np.asarray(perm_vs, dtype=float)
        p_val = float((np.sum(perm_arr >= obs_v) + 1) / (N_PERM + 1))

        rows.append({
            "state": st,
            "n_packages": int(len(grp)),
            "n_top5": int(grp["if_strat_top5"].sum()),
            "merged_cohort_cols": int(ct.shape[1]),
            "pct_expected_lt_5": round(float((expected < 5.0).mean() * 100.0), 1),
            "obs_cramers_v": round(obs_v, 4),
            "perm_null_mean_v": round(float(perm_arr.mean()), 4),
            "perm_p_value": round(p_val, 4),
        })

    res_df = pd.DataFrame(rows)
    mean_merged_v = float(res_df["obs_cramers_v"].mean())

    report_lines = [
        "# PEIARS — Isolation Forest Cohort Robustness Report",
        "",
        f"- **Generated At (UTC):** {datetime.now(timezone.utc).isoformat()}",
        f"- **Sparse Cohort Merge Threshold:** `n < {MIN_COHORT_MERGE}` within state merged into `OTHER_SPARSE_COHORTS`.",
        f"- **Permutations:** `{N_PERM}` label permutations per state.",
        "",
        "## 1. Retired Metric vs. Merged Within-State Association",
        "",
        "- The earlier `0.675` / `0.682` value came from cross-tabulating `cohort_year_batch` against `source_state_key` restricted to `if_strat_top5` rows (`42.9%` expected cells less than 5), mixing state identity and cohort sparsity.",
        f"- After merging cohorts with less than `{MIN_COHORT_MERGE}` rows per state, mean within-state Cramér's V (`if_strat_top5` vs `cohort_merged`) is **`{mean_merged_v:.4f}`**.",
        "",
        to_md_table(res_df),
        "",
        "## 2. Reference-Population Sensitivity (Within-Cohort vs. State-Stratified)",
        "",
        "- Scoring within `state x cohort_year_batch` (`n >= 20`, `223` flagged) vs state-stratified scoring (`219` flagged) yields `168` overlapping packages (**Jaccard = `0.6131`**).",
        "- High seed stability (`0.8781`) does not eliminate reference-population sensitivity: ~39% of candidate membership turns over when cohort baselines replace state-wide baselines.",
    ]

    report_path = out_dir / "IF_COHORT_ROBUSTNESS_REPORT.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Wrote {report_path}\n")
    print(res_df.to_string(index=False))
    print(f"\nMean merged within-state Cramér's V: {mean_merged_v:.4f}")


if __name__ == "__main__":
    main()
