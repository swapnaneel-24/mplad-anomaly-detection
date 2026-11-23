from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

import run_controlled_if_experiment as exp


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def to_md_table(df: pd.DataFrame) -> str:
    headers = [str(c) for c in df.columns]
    rows = [[str(v) for v in r] for r in df.itertuples(index=False, name=None)]
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    hdr = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    body = ["| " + " | ".join(r[i].ljust(widths[i]) for i, h in enumerate(headers)) + " |" for r in rows]
    return "\n".join([hdr, sep, *body])


def main() -> None:
    repo_root = Path.cwd()
    snap_dir = repo_root / "data/canonical/pmgsy_v1/pmgsy3_3state_v1"
    v2_csv = snap_dir / "scoring_option_b_v2/packages_p_scored_option_b_v2.csv"
    exp_dir = repo_root / "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1"
    out_dir = exp_dir / "expanded_audit_v3"

    blind_path = out_dir / "IF_V3_BLIND_REVIEW.csv"
    key_path = out_dir / "IF_V3_UNBLINDED_KEY_RESTRICTED.csv"
    diag_path = out_dir / "IF_V3_MATCHING_DIAGNOSTICS.csv"
    manifest_path = out_dir / "IF_V3_SAMPLING_MANIFEST.json"
    freeze_path = out_dir / "IF_V3_SAMPLE_FREEZE.json"
    v1_res_path = exp_dir / "IF_ENRICHED_AUDIT_RESULTS_V1.csv"

    blind = pd.read_csv(blind_path)
    key = pd.read_csv(key_path)
    v1_res = pd.read_csv(v1_res_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))

    # 1. Hard-stop hash integrity checks
    for fname, meta in freeze["files"].items():
        actual = sha256_file(out_dir / fname)
        assert actual == meta["sha256"], f"Hash mismatch for {fname}: {actual} != {meta['sha256']}"

    # 2. Hard-stop structural & blinding assertions
    assert len(blind) == 120, f"Expected 120 review rows, got {len(blind)}"
    assert blind["audit_item_id"].nunique() == 120, "Duplicate audit_item_id in blinded review"
    assert blind["package_uid"].nunique() == 120, "Duplicate package_uid in blinded review"
    assert len(key) == 120, f"Expected 120 key rows, got {len(key)}"
    assert key["package_uid"].nunique() == 120, "Duplicate package_uid in key"

    forbidden_blind_cols = {"if_strat_score", "if_strat_top5", "audit_group", "pair_id", "investigation_tier"}
    leaked_cols = forbidden_blind_cols.intersection(set(blind.columns))
    assert not leaked_cols, f"Leaked restricted columns in blinded sheet: {leaked_cols}"

    # Verify source_evidence_reference non-empty on all 120 rows
    assert blind["source_evidence_reference"].fillna("").astype(str).str.strip().ne("").all(), "Missing mandatory source_evidence_reference"

    # Verify 0 overlap with v1 60 audit packages
    v1_uids = set(v1_res["package_uid"].astype(str))
    overlap_v1 = v1_uids.intersection(set(blind["package_uid"].astype(str)))
    assert len(overlap_v1) == 0, f"Overlap with v1 audit packages: {len(overlap_v1)}"

    # Verify 60 IF-selected + 60 matched controls and exact 1:1 Tier-0 pair composition
    assert int((key["audit_group"] == "IF_TOP5_SELECTED").sum()) == 60, "Expected 60 IF_TOP5_SELECTED"
    assert int((key["audit_group"] == "MATCHED_NON_IF_CONTROL").sum()) == 60, "Expected 60 MATCHED_NON_IF_CONTROL"
    assert key["pair_id"].nunique() == 60, f"Expected 60 unique pairs, got {key['pair_id'].nunique()}"

    for pid, grp in key.groupby("pair_id"):
        assert len(grp) == 2, f"Pair {pid} does not have 2 rows"
        assert set(grp["audit_group"]) == {"IF_TOP5_SELECTED", "MATCHED_NON_IF_CONTROL"}, f"Pair {pid} bad arm composition"
        assert grp["tier0_stratum"].nunique() == 1, f"Pair {pid} mismatched Tier-0 stratum"

    # Verify all 120 packages belong to canonical P packages & model was not refitted
    canon = exp.build_feature_matrix(snap_dir, v2_csv)
    canon_p_uids = set(canon["package_uid"].astype(str))
    assert set(blind["package_uid"].astype(str)).issubset(canon_p_uids), "Non-P package detected in v3 sample"
    assert manifest["model_config"]["refitted_during_sampling"] is False, "Model refitting flag must be False"

    # 3. Diagnostic distributions & matched vs unmatched IF candidate comparison
    merged = blind.merge(key[["audit_item_id", "pair_id", "audit_group", "tier0_stratum", "if_strat_score"]], on="audit_item_id")

    dist_rows = []
    for dim in ["source_state_key", "cohort_year_batch", "seg_bucket", "len_band"]:
        ct = pd.crosstab(merged[dim], merged["audit_group"]).reset_index().rename(columns={dim: "stratum_value"})
        ct.insert(0, "dimension", dim)
        dist_rows.append(ct)
    dist_df = pd.concat(dist_rows, ignore_index=True)

    # Compare matched-eligible vs unmatched-eligible IF top-5% candidates
    scores = exp.fit_stratified_if(canon, seed=42, contamination=0.05)
    top5_set = exp.top_k_per_state(canon, scores, frac=0.05)
    canon["if_strat_top5"] = canon["package_uid"].astype(str).isin(top5_set)
    elig_pos = canon[(~canon["package_uid"].astype(str).isin(v1_uids)) & (canon["if_strat_top5"])].copy()

    diag_df = pd.read_csv(diag_path)
    matchable_strata = set(diag_df[diag_df["eligible_non_if_ctrl"] > 0]["tier0_stratum"])

    def row_stratum(r: pd.Series) -> str:
        ns = int(r["n_segments"]) if pd.notna(r["n_segments"]) else 0
        sb = "1_seg" if ns <= 1 else ("2_segs" if ns == 2 else ("3_to_5_segs" if ns <= 5 else "6_plus_segs"))
        km = r["proposed_l_km"]
        lb = "lt_5km" if (pd.isna(km) or km < 5.0) else ("5_to_10km" if km < 10.0 else ("10_to_20km" if km < 20.0 else "ge_20km"))
        return f"{r['source_state_key']}|{r['cohort_year_batch']}|{sb}|{lb}"

    elig_pos["is_tier0_matchable"] = elig_pos.apply(row_stratum, axis=1).isin(matchable_strata)
    comp_rows = []
    for flag, grp in elig_pos.groupby("is_tier0_matchable"):
        comp_rows.append({
            "pool_subset": "Tier0_Matchable_IF_Top5" if flag else "Unmatched_IF_Top5",
            "n_packages": int(len(grp)),
            "med_n_segments": round(float(grp["n_segments"].median()), 2),
            "med_seg_conc": round(float(grp["seg_len_concentration"].median()), 3),
            "med_sinuosity": round(float(grp["mean_sinuosity"].median()), 3),
            "med_vertices_km": round(float(grp["vertices_per_km"].median()), 2),
            "med_proposed_km": round(float(grp["proposed_l_km"].median()), 2),
        })
    comp_df = pd.DataFrame(comp_rows)

    cov_num = int(elig_pos["is_tier0_matchable"].sum())
    cov_den = int(len(elig_pos))

    report_path = out_dir / "IF_V3_SAMPLE_VALIDATION_REPORT.md"
    lines = [
        "# PEIARS — v3 Expanded Audit Sample Validation Report",
        "",
        f"- **Validated At (UTC):** {datetime.now(timezone.utc).isoformat()}",
        "- **All Hard-Stop Assertions:** `PASS` (120 rows, 120 unique IDs/packages, 60 exact Tier-0 1:1 pairs, 0 v1 overlap, 0 blinding leaks).",
        f"- **Tier-0 Matching Coverage:** `{cov_num} / {cov_den}` (`{cov_num / cov_den:.1%}`) of eligible IF top-5% packages have at least one exact Tier-0 control.",
        "- **Scope Caveat:** Conclusions generalize strictly to the Tier-0 matchable population; unmatched extreme singletons/rare strata are documented below.",
        "",
        "## 1. Sample Balance Across Matching Dimensions (`60` Selected vs. `60` Controls)",
        "",
        to_md_table(dist_df),
        "",
        "## 2. Tier-0 Matchable vs. Unmatched Eligible IF Top-5% Candidates (`n = 189`)",
        "",
        to_md_table(comp_df),
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print("ALL v3 SAMPLE VALIDATION ASSERTIONS PASSED.")
    print(f"Wrote validation report -> {report_path}\n")
    print(to_md_table(comp_df))


if __name__ == "__main__":
    main()

