from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd


def main() -> None:
    diag_dir = Path(
        "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1/diagnostics"
    )
    src_path = diag_dir / "if_enriched_audit_sample.csv"
    if not src_path.exists():
        raise FileNotFoundError(f"Missing {src_path}")

    df = pd.read_csv(src_path)
    rng = np.random.default_rng(20261124)
    shuffled = df.iloc[rng.permutation(len(df))].reset_index(drop=True)
    shuffled["audit_item_id"] = [f"IFAUD_{i+1:03d}" for i in range(len(shuffled))]

    key_cols = [
        c
        for c in [
            "audit_item_id",
            "package_uid",
            "mrl_id",
            "audit_group",
            "if_strat_score",
            "if_strat_top5",
        ]
        if c in shuffled.columns
    ]
    key_path = diag_dir / "if_enriched_audit_unblinded_key_DO_NOT_PEEK.csv"
    shuffled[key_cols].to_csv(key_path, index=False)

    blind_cols = [
        c
        for c in [
            "audit_item_id",
            "package_uid",
            "mrl_id",
            "source_state_key",
            "cohort_year_batch",
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
        if c in shuffled.columns
    ]
    blind_path = diag_dir / "if_enriched_audit_blind_review.csv"
    shuffled[blind_cols].to_csv(blind_path, index=False)
    print(f"Created blinded 60-item review sheet: {blind_path}")
    print(f"Saved separate unblinded key: {key_path}")


if __name__ == "__main__":
    main()
