from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

import run_controlled_if_experiment as exp

MIN_COHORT_N = 20


def within_state_cohort_cramers_v(df: pd.DataFrame, flag_col: str) -> float:
    vals = []
    for _, grp in df.groupby("source_state_key"):
        ct = pd.crosstab(grp[flag_col].astype(str), grp["cohort_year_batch"].astype(str))
        if ct.shape[0] < 2 or ct.shape[1] < 2:
            continue
        chi2 = chi2_contingency(ct)[0]
        n = ct.to_numpy().sum()
        min_dim = min(ct.shape[0] - 1, ct.shape[1] - 1)
        if n > 1 and min_dim > 0:
            vals.append(float(np.sqrt(chi2 / (n * min_dim))))
    return float(np.mean(vals)) if vals else 0.0


def fit_stratified_with_features(df: pd.DataFrame, features: list[str], seed: int = 42, cont: float = 0.05) -> np.ndarray:
    scores = np.zeros(len(df), dtype=float)
    for _, idx in df.groupby("source_state_key").groups.items():
        pos = np.asarray(list(idx))
        scaler = RobustScaler()
        x = scaler.fit_transform(df.loc[pos, features].to_numpy(dtype=float))
        clf = IsolationForest(n_estimators=200, contamination=cont, random_state=seed, n_jobs=-1)
        clf.fit(x)
        scores[pos] = -clf.decision_function(x)
    return scores


def main() -> None:
    repo_root = Path.cwd()
    snap_dir = repo_root / "data/canonical/pmgsy_v1/pmgsy3_3state_v1"
    v2_csv = snap_dir / "scoring_option_b_v2/packages_p_scored_option_b_v2.csv"
    out_dir = repo_root / "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1/diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = exp.build_feature_matrix(snap_dir, v2_csv)

    # --- DIAGNOSTIC 1: Within-cohort (state x cohort_year_batch, n >= 20) ---
    cohort_counts = df.groupby(["source_state_key", "cohort_year_batch"])["package_uid"].transform("count")
    elig_mask = cohort_counts >= MIN_COHORT_N
    within_scores = np.full(len(df), np.nan, dtype=float)
    within_flags = np.zeros(len(df), dtype=bool)

    for _, grp in df[elig_mask].groupby(["source_state_key", "cohort_year_batch"]):
        pos = grp.index.to_numpy()
        scaler = RobustScaler()
        x = scaler.fit_transform(df.loc[pos, exp.STRUCT_FEATURES].to_numpy(dtype=float))
        clf = IsolationForest(n_estimators=200, contamination=0.05, random_state=42, n_jobs=-1)
        clf.fit(x)
        sc = -clf.decision_function(x)
        within_scores[pos] = sc
        k = max(1, int(np.ceil(len(pos) * 0.05)))
        top_pos = pos[np.argsort(-sc)[:k]]
        within_flags[top_pos] = True

    state_top5_set = exp.top_k_per_state(df, exp.fit_stratified_if(df, seed=42, contamination=0.05), frac=0.05)
    state_top5_bool = df["package_uid"].isin(state_top5_set).to_numpy()
    within_flag_uids = set(df.loc[within_flags, "package_uid"])
    overlap_with_state_top5 = exp.jaccard(within_flag_uids, state_top5_set)

    print(f"=== DIAGNOSTIC 1: WITHIN-COHORT (n >= {MIN_COHORT_N}) ===")
    print(f"Eligible packages: {int(elig_mask.sum())} / {len(df)}")
    print(f"Within-cohort top-5% flagged count: {int(within_flags.sum())}")
    print(f"Jaccard vs state-stratified top-5%: {overlap_with_state_top5:.4f}")
    print(f"Overlap count with state-stratified top-5%: {int((within_flags & state_top5_bool).sum())}")

    # --- DIAGNOSTIC 2: Feature Ablation ---
    base_scores = fit_stratified_with_features(df, exp.STRUCT_FEATURES, seed=42, cont=0.05)
    base_top5 = exp.top_k_per_state(df, base_scores, frac=0.05)

    ablations = {
        "full_5_features": exp.STRUCT_FEATURES,
        "drop_n_segments": [c for c in exp.STRUCT_FEATURES if c != "n_segments"],
        "drop_seg_len_concentration": [c for c in exp.STRUCT_FEATURES if c != "seg_len_concentration"],
        "drop_both_n_seg_and_conc": [c for c in exp.STRUCT_FEATURES if c not in {"n_segments", "seg_len_concentration"}],
    }

    ab_rows = []
    for name, feats in ablations.items():
        sc = fit_stratified_with_features(df, feats, seed=42, cont=0.05)
        top_set = exp.top_k_per_state(df, sc, frac=0.05)
        col_name = f"ab_top5_{name}"
        df[col_name] = df["package_uid"].isin(top_set)
        ab_rows.append({
            "ablation": name,
            "n_features": len(feats),
            "top5_count": len(top_set),
            "jaccard_vs_full_5feat": round(exp.jaccard(top_set, base_top5), 4),
            "within_state_cohort_cramers_v": round(within_state_cohort_cramers_v(df, col_name), 4),
        })

    ab_df = pd.DataFrame(ab_rows)
    print("\n=== DIAGNOSTIC 2: FEATURE ABLATION ===")
    print(ab_df.to_string(index=False))
    ab_df.to_csv(out_dir / "feature_ablation_summary.csv", index=False)


if __name__ == "__main__":
    main()
