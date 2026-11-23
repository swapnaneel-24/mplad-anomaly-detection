from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_bipartite_matching

import run_controlled_if_experiment as exp

SAMPLING_SEED = 20261123
MODEL_SEED = 42
CONTAMINATION = 0.05
TARGET_PAIRS = 60


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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
    out_dir = exp_dir / "expanded_audit_v3"

    # Guard against silently overwriting an already frozen v3 sample
    freeze_path = out_dir / "IF_V3_SAMPLE_FREEZE.json"
    if freeze_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing frozen v3 sample: {freeze_path}")

    # 1. Validate prerequisite frozen files
    proto_path = exp_dir / "IF_EXPANDED_AUDIT_PROTOCOL_V1.md"
    val_dec_path = exp_dir / "IF_10_CASE_VALIDITY_DECISION_V1.md"
    v1_res_path = exp_dir / "IF_ENRICHED_AUDIT_RESULTS_V1.csv"
    for p in [v2_csv, proto_path, val_dec_path, v1_res_path]:
        if not p.exists():
            raise FileNotFoundError(f"Missing prerequisite frozen artifact: {p}")

    v1_res = pd.read_csv(v1_res_path)
    exclude_uids = set(v1_res["package_uid"].astype(str))
    if len(exclude_uids) != 60:
        raise ValueError(f"Expected 60 unique v1 audit package exclusions, got {len(exclude_uids)}")

    # 2. Load canonical P packages & deterministic frozen IF top-5% selection
    df = exp.build_feature_matrix(snap_dir, v2_csv)
    assert len(df) == 4361, f"Expected 4361 canonical P packages, got {len(df)}"

    scores = exp.fit_stratified_if(df, seed=MODEL_SEED, contamination=CONTAMINATION)
    top5_set = exp.top_k_per_state(df, scores, frac=CONTAMINATION)
    df["if_strat_score"] = scores
    df["if_strat_top5"] = df["package_uid"].astype(str).isin(top5_set)
    df["seg_bucket"] = df["n_segments"].fillna(0).astype(int).map(seg_bucket)
    df["len_band"] = df["proposed_l_km"].map(len_band)
    df["tier0_stratum"] = (
        df["source_state_key"].astype(str)
        + "|" + df["cohort_year_batch"].astype(str)
        + "|" + df["seg_bucket"].astype(str)
        + "|" + df["len_band"].astype(str)
    )

    # Exclude all 60 prior v1 audit packages
    elig = df[~df["package_uid"].astype(str).isin(exclude_uids)].copy().reset_index(drop=True)
    pos = elig[elig["if_strat_top5"]].copy().reset_index(drop=True)
    neg = elig[~elig["if_strat_top5"]].copy().reset_index(drop=True)

    if len(pos) != 189:
        raise ValueError(f"Expected 189 eligible IF top-5% packages, got {len(pos)}")

    # 3. Deterministic bipartite maximum 1:1 matching on Tier-0 stratum
    rng = np.random.default_rng(SAMPLING_SEED)
    pos_perm = pos.iloc[rng.permutation(len(pos))].reset_index(drop=True)
    neg_perm = neg.iloc[rng.permutation(len(neg))].reset_index(drop=True)

    neg_by_stratum: dict[str, list[int]] = {}
    for j, st in enumerate(neg_perm["tier0_stratum"]):
        neg_by_stratum.setdefault(st, []).append(j)

    rows_idx: list[int] = []
    cols_idx: list[int] = []
    matchable_pos_count = 0
    for i, st in enumerate(pos_perm["tier0_stratum"]):
        cands = neg_by_stratum.get(st, [])
        if cands:
            matchable_pos_count += 1
            for j in cands:
                rows_idx.append(i)
                cols_idx.append(j)

    biadj = csr_matrix(
        (np.ones(len(rows_idx), dtype=np.int8), (rows_idx, cols_idx)),
        shape=(len(pos_perm), len(neg_perm)),
    )
    match_for_pos = maximum_bipartite_matching(biadj, perm_type="column")
    valid_pairs = [(i, int(j)) for i, j in enumerate(match_for_pos) if j != -1]

    if len(valid_pairs) < TARGET_PAIRS:
        raise RuntimeError(
            f"Insufficient disjoint Tier-0 pairs: found {len(valid_pairs)}, need {TARGET_PAIRS}."
        )

    # Randomly choose 60 disjoint pairs from maximum matching (not top-60 scores)
    chosen_pair_indices = rng.choice(len(valid_pairs), size=TARGET_PAIRS, replace=False)
    chosen_pairs = [valid_pairs[int(k)] for k in sorted(chosen_pair_indices)]

    paired_records = []
    for pair_num, (pi, nj) in enumerate(chosen_pairs, start=1):
        pair_id = f"PAIR_V3_{pair_num:03d}"
        p_row = pos_perm.iloc[pi].copy()
        p_row["pair_id"] = pair_id
        p_row["audit_group"] = "IF_TOP5_SELECTED"

        n_row = neg_perm.iloc[nj].copy()
        n_row["pair_id"] = pair_id
        n_row["audit_group"] = "MATCHED_NON_IF_CONTROL"

        paired_records.append(p_row)
        paired_records.append(n_row)

    sample_df = pd.DataFrame(paired_records).reset_index(drop=True)
    # Shuffle blind presentation order deterministically
    blind_shuffled = sample_df.iloc[rng.permutation(len(sample_df))].reset_index(drop=True)
    blind_shuffled["audit_item_id"] = [f"IFV3_{i+1:03d}" for i in range(len(blind_shuffled))]

    # Separate endpoints & blind reviewer worksheet columns (strictly no IF scores/membership/pair_id)
    blind_shuffled["confirmed_source_defect"] = ""
    blind_shuffled["supported_review_candidate"] = ""
    blind_shuffled["review_outcome"] = ""
    blind_shuffled["evidence_domain"] = ""
    blind_shuffled["reviewer_confidence"] = ""
    blind_shuffled["source_evidence_reference"] = blind_shuffled["mrl_id"].map(
        lambda x: f"segments.parquet|packages_p:mrl_id={x}"
    )
    blind_shuffled["observed_finding"] = ""
    blind_shuffled["alternative_explanation"] = ""
    blind_shuffled["reviewer_notes"] = ""

    blind_cols = [
        c for c in [
            "audit_item_id",
            "package_uid",
            "mrl_id",
            "source_state_key",
            "cohort_year_batch",
            "seg_bucket",
            "len_band",
            "n_segments",
            "mean_seg_len_km",
            "mean_sinuosity",
            "vertices_per_km",
            "seg_len_concentration",
            "proposed_l_km",
            "sum_geom_len_km",
            "work_name",
            "source_evidence_reference",
            "confirmed_source_defect",
            "supported_review_candidate",
            "review_outcome",
            "evidence_domain",
            "reviewer_confidence",
            "observed_finding",
            "alternative_explanation",
            "reviewer_notes",
        ] if c in blind_shuffled.columns
    ]

    key_cols = [
        "audit_item_id",
        "pair_id",
        "audit_group",
        "package_uid",
        "mrl_id",
        "tier0_stratum",
        "if_strat_score",
        "if_strat_top5",
    ]

    # Write to temporary directory first, then finalize atomically
    tmp_dir = exp_dir / "_tmp_expanded_audit_v3"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    tmp_blind = tmp_dir / "IF_V3_BLIND_REVIEW.csv"
    tmp_key = tmp_dir / "IF_V3_UNBLINDED_KEY_RESTRICTED.csv"
    tmp_diag = tmp_dir / "IF_V3_MATCHING_DIAGNOSTICS.csv"
    tmp_manifest = tmp_dir / "IF_V3_SAMPLING_MANIFEST.json"
    tmp_freeze = tmp_dir / "IF_V3_SAMPLE_FREEZE.json"

    blind_shuffled[blind_cols].to_csv(tmp_blind, index=False)
    blind_shuffled[key_cols].to_csv(tmp_key, index=False)

    # Matching diagnostics by Tier-0 stratum
    diag_rows = []
    matched_pos_uids = set(sample_df[sample_df["audit_group"] == "IF_TOP5_SELECTED"]["package_uid"].astype(str))
    for st, grp in pos.groupby("tier0_stratum"):
        n_elig_pos = int(len(grp))
        n_elig_neg = int((neg["tier0_stratum"] == st).sum())
        n_sampled = int(grp["package_uid"].astype(str).isin(matched_pos_uids).sum())
        diag_rows.append({
            "tier0_stratum": st,
            "eligible_if_top5": n_elig_pos,
            "eligible_non_if_ctrl": n_elig_neg,
            "sampled_pairs": n_sampled,
        })
    diag_df = pd.DataFrame(diag_rows).sort_values(["sampled_pairs", "eligible_if_top5"], ascending=[False, False])
    diag_df.to_csv(tmp_diag, index=False)

    now_utc = datetime.now(timezone.utc).isoformat()
    manifest_obj = {
        "protocol_version": "IF_EXPANDED_AUDIT_PROTOCOL_V1",
        "created_at_utc": now_utc,
        "dataset": "pmgsy3_3state_v1",
        "model_config": {
            "features": exp.STRUCT_FEATURES,
            "stratification": "source_state_key",
            "scaler": "RobustScaler",
            "n_estimators": 200,
            "contamination": CONTAMINATION,
            "model_seed": MODEL_SEED,
            "refitted_during_sampling": False,
        },
        "sampling_design": {
            "sampling_seed": SAMPLING_SEED,
            "matching_level": "TIER_0_EXACT (source_state_key x cohort_year_batch x seg_bucket x len_band)",
            "target_pairs": TARGET_PAIRS,
            "total_items": TARGET_PAIRS * 2,
            "excluded_v1_audit_packages": len(exclude_uids),
            "eligible_population": int(len(elig)),
            "eligible_if_top5": int(len(pos)),
            "eligible_if_top5_with_tier0_match": int(matchable_pos_count),
            "tier0_coverage_ratio": round(float(matchable_pos_count / len(pos)), 4),
            "max_disjoint_tier0_pairs": int(len(valid_pairs)),
        },
        "prerequisite_hashes": {
            "IF_EXPANDED_AUDIT_PROTOCOL_V1.md": sha256_file(proto_path),
            "IF_10_CASE_VALIDITY_DECISION_V1.md": sha256_file(val_dec_path),
            "IF_ENRICHED_AUDIT_RESULTS_V1.csv": sha256_file(v1_res_path),
        },
    }
    tmp_manifest.write_text(json.dumps(manifest_obj, indent=2), encoding="utf-8")

    freeze_obj = {
        "freeze_version": "IF_V3_SAMPLE_FREEZE_V1",
        "frozen_at_utc": now_utc,
        "files": {
            "IF_V3_BLIND_REVIEW.csv": {"sha256": sha256_file(tmp_blind), "bytes": tmp_blind.stat().st_size},
            "IF_V3_SAMPLING_MANIFEST.json": {"sha256": sha256_file(tmp_manifest), "bytes": tmp_manifest.stat().st_size},
            "IF_V3_MATCHING_DIAGNOSTICS.csv": {"sha256": sha256_file(tmp_diag), "bytes": tmp_diag.stat().st_size},
            "IF_V3_UNBLINDED_KEY_RESTRICTED.csv": {
                "sha256": sha256_file(tmp_key),
                "bytes": tmp_key.stat().st_size,
                "access_policy": "RESTRICTED_EXCLUDED_FROM_GIT",
            },
        },
    }
    tmp_freeze.write_text(json.dumps(freeze_obj, indent=2), encoding="utf-8")

    # Ensure restricted key is ignored in .gitignore before promoting files
    gitignore_path = repo_root / ".gitignore"
    ignore_entry = "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1/expanded_audit_v3/IF_V3_UNBLINDED_KEY_RESTRICTED.csv"
    existing_gi = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    if ignore_entry not in existing_gi:
        with gitignore_path.open("a", encoding="utf-8") as f:
            if existing_gi and not existing_gi.endswith("\n"):
                f.write("\n")
            f.write(ignore_entry + "\n")

    # Promote atomically to final out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for src in [tmp_blind, tmp_key, tmp_diag, tmp_manifest, tmp_freeze]:
        src.replace(out_dir / src.name)
    tmp_dir.rmdir()

    print(f"Generated frozen 120-case v3 sample in: {out_dir}")
    print(f"Max disjoint Tier-0 pairs: {len(valid_pairs)} (sampled {TARGET_PAIRS} pairs = 120 items)")
    print(f"Tier-0 matchable IF top-5% coverage: {matchable_pos_count}/189 ({matchable_pos_count/189:.1%})")


if __name__ == "__main__":
    main()

