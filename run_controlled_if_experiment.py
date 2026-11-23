from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

STRUCT_FEATURES: List[str] = [
    "n_segments",
    "mean_seg_len_km",
    "mean_sinuosity",
    "vertices_per_km",
    "seg_len_concentration",
]


def cramers_v(series_a: pd.Series, series_b: pd.Series) -> float:
    ct = pd.crosstab(series_a.fillna("MISSING").astype(str), series_b.fillna("MISSING").astype(str))
    if ct.shape[0] < 2 or ct.shape[1] < 2:
        return 0.0
    chi2 = chi2_contingency(ct)[0]
    n = ct.to_numpy().sum()
    if n <= 1:
        return 0.0
    min_dim = min(ct.shape[0] - 1, ct.shape[1] - 1)
    return float(np.sqrt(chi2 / (n * min_dim)))


def jaccard(a: set, b: set) -> float:
    union = a | b
    return float(len(a & b) / len(union)) if union else 1.0


def build_feature_matrix(snap_dir: Path, v2_csv: Path) -> pd.DataFrame:
    pkg = gpd.read_parquet(snap_dir / "packages.parquet")
    p = pkg[
        (pkg["proposal_type"] == "P")
        & pkg["proposed_l_km"].notna()
        & (pkg["proposed_l_km"] > 0)
    ].copy()
    p = pd.DataFrame(p.drop(columns=["geometry"]))

    p["mean_sinuosity"] = p.groupby("source_state_key")["mean_sinuosity"].transform(
        lambda s: s.fillna(s.median())
    )
    p["vertices_per_km"] = np.where(
        p["sum_geom_len_km"] > 0, p["total_vertices"] / p["sum_geom_len_km"], 0.0
    )
    p["seg_len_concentration"] = np.where(
        p["sum_geom_len_km"] > 0, p["max_seg_len_km"] / p["sum_geom_len_km"], 0.0
    )

    for col in STRUCT_FEATURES:
        p[col] = pd.to_numeric(p[col], errors="coerce").fillna(0.0)

    scored = pd.read_csv(v2_csv)
    keep_scored = [
        c
        for c in [
            "package_uid",
            "investigation_tier",
            "r_iqr_scaled_dev",
            "r_modified_z",
            "r_abs_diff_from_state_median",
        ]
        if c in scored.columns
    ]
    merged = p.merge(scored[keep_scored], on="package_uid", how="left")
    merged["cohort_year_batch"] = (
        merged["ims_year"].fillna(-1).astype(int).astype(str)
        + "_B"
        + merged["ims_batch"].fillna(-1).astype(int).astype(str)
    )
    return merged.reset_index(drop=True)


def top_k_per_state(df: pd.DataFrame, scores: np.ndarray, frac: float = 0.05) -> set:
    flagged = set()
    tmp = pd.DataFrame({
        "state": df["source_state_key"].to_numpy(),
        "uid": df["package_uid"].to_numpy(),
        "score": scores,
    })
    for _, grp in tmp.groupby("state"):
        k = max(1, int(np.ceil(len(grp) * frac)))
        top_uids = grp.sort_values("score", ascending=False).head(k)["uid"].tolist()
        flagged.update(top_uids)
    return flagged


def fit_stratified_if(df: pd.DataFrame, seed: int, contamination: float) -> np.ndarray:
    out_scores = np.zeros(len(df), dtype=float)
    for _, idx in df.groupby("source_state_key").groups.items():
        pos = np.asarray(list(idx))
        scaler = RobustScaler()
        x_scaled = scaler.fit_transform(df.loc[pos, STRUCT_FEATURES].to_numpy(dtype=float))
        model = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=seed,
            n_jobs=-1,
        )
        model.fit(x_scaled)
        # Higher score = more anomalous
        out_scores[pos] = -model.decision_function(x_scaled)
    return out_scores


def fit_pooled_if(df: pd.DataFrame, seed: int, contamination: float) -> np.ndarray:
    scaler = RobustScaler()
    x_scaled = scaler.fit_transform(df[STRUCT_FEATURES].to_numpy(dtype=float))
    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=seed,
        n_jobs=-1,
    )
    model.fit(x_scaled)
    return -model.decision_function(x_scaled)


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    snap_dir = repo_root / "data/canonical/pmgsy_v1/pmgsy3_3state_v1"
    v2_csv = snap_dir / "scoring_option_b_v2/packages_p_scored_option_b_v2.csv"
    ann_dir = repo_root / "research/pmgsy_iii_investigation/outputs/option_b_v2_evidence_review/blinded_annotation_v1"
    freeze_path = ann_dir / "ANNOTATIONS_FREEZE_MANIFEST_V1.json"
    ws_path = ann_dir / "blinded_annotation_worksheet.csv"

    if not freeze_path.exists():
        raise FileNotFoundError(f"Frozen annotation manifest missing: {freeze_path}")

    df = build_feature_matrix(snap_dir, v2_csv)

    # Arm 0: State-Conditional R Baseline (rank by max scaled deviation; fallback to abs diff)
    r_score = np.maximum(
        pd.to_numeric(df.get("r_iqr_scaled_dev", 0.0), errors="coerce").fillna(0.0).to_numpy(),
        pd.to_numeric(df.get("r_modified_z", 0.0), errors="coerce").fillna(0.0).abs().to_numpy(),
    )
    arm0_top5 = top_k_per_state(df, r_score, frac=0.05)

    seeds = list(range(42, 52))
    contaminations = [0.02, 0.05]
    summary_rows: List[Dict] = []
    latest_strat_scores: Dict[Tuple[float, int], np.ndarray] = {}

    for cont in contaminations:
        seed_sets_strat: List[set] = []
        seed_sets_pool: List[set] = []
        v_strat_list: List[float] = []
        v_pool_list: List[float] = []

        for s in seeds:
            sc_strat = fit_stratified_if(df, seed=s, contamination=cont)
            sc_pool = fit_pooled_if(df, seed=s, contamination=cont)
            latest_strat_scores[(cont, s)] = sc_strat

            top_s = top_k_per_state(df, sc_strat, frac=0.05)
            top_p = top_k_per_state(df, sc_pool, frac=0.05)
            seed_sets_strat.append(top_s)
            seed_sets_pool.append(top_p)

            mask_s = df["package_uid"].isin(top_s)
            mask_p = df["package_uid"].isin(top_p)
            v_strat_list.append(cramers_v(df.loc[mask_s, "cohort_year_batch"], df.loc[mask_s, "source_state_key"]))
            v_pool_list.append(cramers_v(df.loc[mask_p, "cohort_year_batch"], df.loc[mask_p, "source_state_key"]))

        # Pairwise Jaccard stability across 10 seeds
        pair_jacc_strat = [
            jaccard(seed_sets_strat[i], seed_sets_strat[j])
            for i in range(len(seed_sets_strat))
            for j in range(i + 1, len(seed_sets_strat))
        ]
        pair_jacc_pool = [
            jaccard(seed_sets_pool[i], seed_sets_pool[j])
            for i in range(len(seed_sets_pool))
            for j in range(i + 1, len(seed_sets_pool))
        ]

        # Union / consensus top-5% vs Arm 0 overlap
        consensus_strat = set.intersection(*seed_sets_strat) if seed_sets_strat else set()
        union_strat = set.union(*seed_sets_strat) if seed_sets_strat else set()
        overlap_r_union = jaccard(union_strat, arm0_top5)
        overlap_r_cons = jaccard(consensus_strat, arm0_top5)

        mean_jacc_s = float(np.mean(pair_jacc_strat))
        mean_v_s = float(np.mean(v_strat_list))

        summary_rows.append({
            "contamination": cont,
            "strat_seed_jaccard_mean": round(mean_jacc_s, 4),
            "pool_seed_jaccard_mean": round(float(np.mean(pair_jacc_pool)), 4),
            "strat_vs_arm0_union_jaccard": round(overlap_r_union, 4),
            "strat_vs_arm0_consensus_jaccard": round(overlap_r_cons, 4),
            "strat_cohort_cramers_v_mean": round(mean_v_s, 4),
            "pool_cohort_cramers_v_mean": round(float(np.mean(v_pool_list)), 4),
            "consensus_top5_count": len(consensus_strat),
            "gate1_stability_pass": bool(mean_jacc_s >= 0.75),
            "gate2_nonredundancy_pass": bool(overlap_r_union < 0.60),
            "gate3_low_confounding_pass": bool(mean_v_s <= 0.35),
        })

    # Check overlap with frozen 84-item annotation worksheet (seed 42, cont 0.05)
    ws = pd.read_csv(ws_path)
    sc_ref = latest_strat_scores[(0.05, 42)]
    df["if_strat_score_s42_c05"] = sc_ref
    df["if_strat_top5_s42_c05"] = df["package_uid"].isin(top_k_per_state(df, sc_ref, frac=0.05))
    ann_merged = ws.merge(
        df[["package_uid", "if_strat_score_s42_c05", "if_strat_top5_s42_c05"]],
        on="package_uid",
        how="left",
    )

    out_dir = repo_root / "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1"
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary_rows).to_csv(out_dir / "gate_metrics_summary.csv", index=False)
    ann_merged.to_csv(out_dir / "frozen_annotations_with_if_scores.csv", index=False)

    print("=== CONTROLLED ISOLATION FOREST EXPERIMENT SUMMARY (NO THRESHOLD TUNING) ===")
    print(pd.DataFrame(summary_rows).to_string(index=False))
    print("\n=== FROZEN ANNOTATIONS VS IF TOP-5% (seed=42, contamination=0.05) ===")
    print(
        pd.crosstab(
            ann_merged["audit_disposition"].fillna("MISSING"),
            ann_merged["if_strat_top5_s42_c05"].fillna(False),
            rownames=["audit_disposition"],
            colnames=["if_strat_top5"],
        ).to_string()
    )
    print(f"\nSaved results to: {out_dir}")


if __name__ == "__main__":
    main()
