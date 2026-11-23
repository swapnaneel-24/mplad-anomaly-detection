from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def draw_stratum(
    df: pd.DataFrame,
    mask: pd.Series,
    n_target: int,
    rng: np.random.Generator,
    stratum_name: str,
) -> Tuple[pd.DataFrame, Dict]:
    pool = df[mask].copy()
    k = min(len(pool), n_target)
    if k > 0:
        idx = rng.choice(pool.index.to_numpy(), size=k, replace=False)
        picked = pool.loc[idx].copy()
    else:
        picked = pool.iloc[0:0].copy()
    picked["sampling_stratum"] = stratum_name
    meta = {
        "stratum": stratum_name,
        "pool_size": int(len(pool)),
        "requested": int(n_target),
        "sampled": int(len(picked)),
    }
    return picked, meta


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    snap_dir = repo_root / "data/canonical/pmgsy_v1/pmgsy3_3state_v1"
    v2_path = snap_dir / "scoring_option_b_v2/packages_p_scored_option_b_v2.csv"
    out_dir = repo_root / "research/pmgsy_iii_investigation/outputs/option_b_v2_evidence_review/blinded_annotation_v1"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(v2_path)
    rng = np.random.default_rng(20261119)

    is_up = df["source_state_key"] == "UTTAR_PRADESH"
    is_up_2020_b1 = is_up & (df["ims_year"] == 2020) & (df["ims_batch"] == 1)
    is_up_later = is_up & (~is_up_2020_b1)
    is_bh = df["source_state_key"] == "BIHAR"
    is_mp = df["source_state_key"] == "MADHYA_PRADESH"

    is_high = df["investigation_tier"] == "HIGH_STATE_R_DEVIATION"
    is_base = df["investigation_tier"] == "BASELINE_WITHIN_RANGE"
    is_sub = df["investigation_tier"] == "SUBTHRESHOLD_REL_SHIFT"

    specs: List[Tuple[pd.Series, int, str]] = [
        # UP 2020 / Batch 1 (n = 24)
        (is_up_2020_b1 & is_high, 14, "UP_2020_B1__HIGH_STATE_R_DEVIATION"),
        (is_up_2020_b1 & is_base, 10, "UP_2020_B1__BASELINE_WITHIN_RANGE"),
        # UP Later Cohorts (n = 20)
        (is_up_later & is_high, 10, "UP_LATER_COHORTS__HIGH_STATE_R_DEVIATION"),
        (is_up_later & is_base, 10, "UP_LATER_COHORTS__BASELINE_WITHIN_RANGE"),
        # Bihar (n = 20)
        (is_bh & is_high, 10, "BIHAR__HIGH_STATE_R_DEVIATION"),
        (is_bh & is_base, 10, "BIHAR__BASELINE_WITHIN_RANGE"),
        # Madhya Pradesh (n = 20)
        (is_mp & is_high, 8, "MADHYA_PRADESH__HIGH_STATE_R_DEVIATION"),
        (is_mp & is_sub, 6, "MADHYA_PRADESH__SUBTHRESHOLD_REL_SHIFT"),
        (is_mp & is_base, 6, "MADHYA_PRADESH__BASELINE_WITHIN_RANGE"),
    ]

    parts: List[pd.DataFrame] = []
    strata_meta: List[Dict] = []
    for mask, n_req, s_name in specs:
        picked, meta = draw_stratum(df, mask, n_req, rng, s_name)
        parts.append(picked)
        strata_meta.append(meta)

    sampled = pd.concat(parts, ignore_index=True)
    # Shuffle review order deterministically so strata are interleaved during blind inspection
    order = rng.permutation(len(sampled))
    sampled = sampled.iloc[order].reset_index(drop=True)
    sampled["blind_item_id"] = [f"BLIND_{i+1:03d}" for i in range(len(sampled))]

    # Unblinded reference key kept separately (not placed in the reviewer worksheet)
    unblinded_cols = [
        "blind_item_id",
        "package_uid",
        "source_state_key",
        "mrl_id",
        "sampling_stratum",
        "investigation_tier",
        "is_r_lt_0_5_exploratory",
        "length_ratio_r",
        "state_median_r",
        "r_diff_from_state_median",
        "r_abs_diff_from_state_median",
        "r_iqr_scaled_dev",
        "r_modified_z",
        "priority_reason",
    ]
    unblinded_cols = [c for c in unblinded_cols if c in sampled.columns]
    p_key = out_dir / "unblinded_strata_key_DO_NOT_PEEK_DURING_BLIND_REVIEW.csv"
    sampled[unblinded_cols].to_csv(p_key, index=False)

    # Blinded worksheet: strips rule tiers, R ratio, and R deviation metrics
    sampled["observed_geometry_issue"] = ""
    sampled["supporting_source_evidence"] = ""
    sampled["alternative_benign_explanation"] = ""
    sampled["reviewer_confidence"] = ""
    sampled["audit_disposition"] = ""
    sampled["reviewer_notes"] = ""

    blind_cols = [
        "blind_item_id",
        "package_uid",
        "source_state_key",
        "mrl_id",
        "work_name",
        "ims_year",
        "ims_batch",
        "lgd_distri",
        "block_id",
        "n_segments",
        "n_distinct_geom",
        "proposed_l_km",
        "sum_geom_len_km",
        "has_exact_geom_dup",
        "has_linear_overlap",
        "max_shared_overlap_m",
        "has_zero_len_segment",
        "n_zero_len_segments",
        "has_invalid_segment_geom",
        "n_invalid_segments",
        "observed_geometry_issue",
        "supporting_source_evidence",
        "alternative_benign_explanation",
        "reviewer_confidence",
        "audit_disposition",
        "reviewer_notes",
    ]
    blind_cols = [c for c in blind_cols if c in sampled.columns]
    p_ws = out_dir / "blinded_annotation_worksheet.csv"
    sampled[blind_cols].to_csv(p_ws, index=False)

    manifest = {
        "phase": "MANUAL_BLINDED_EVIDENCE_ANNOTATION_PRE_ML",
        "ml_fitting_status": "DEFERRED_UNTIL_ANNOTATIONS_FROZEN",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": 20261119,
        "total_sampled_packages": int(len(sampled)),
        "allowed_audit_dispositions": [
            "EXPLAINABLE",
            "UNRESOLVED",
            "NOT_INDEPENDENTLY_VERIFIABLE",
        ],
        "blinded_columns_omitted_from_worksheet": [
            "investigation_tier",
            "priority_reason",
            "length_ratio_r",
            "state_median_r",
            "r_diff_from_state_median",
            "r_abs_diff_from_state_median",
            "r_iqr_scaled_dev",
            "r_modified_z",
            "r_abs_modified_z",
            "is_r_lt_0_5_exploratory",
            "sampling_stratum",
        ],
        "strata_breakdown": strata_meta,
        "artifacts": {
            "blinded_annotation_worksheet.csv": {
                "path": str(p_ws),
                "sha256": sha256_file(p_ws),
            },
            "unblinded_strata_key": {
                "path": str(p_key),
                "sha256": sha256_file(p_key),
            },
        },
    }
    p_man = out_dir / "blinded_sampling_manifest.json"
    p_man.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Append provisional human-audit amendment to ml_experiment_protocol_v1.md
    proto_path = repo_root / "research/pmgsy_iii_investigation/outputs/option_b_v2_evidence_review/ml_experiment_protocol_v1.md"
    if proto_path.exists():
        amendment = (
            "\n## 6. Protocol Amendment v1.1 — Provisional Human-Audit Gate & Annotation Freeze\n\n"
            "- **Status:** Human-audit gate (`>= 60%` explainable cases) is **PROVISIONAL** pending completion and freeze of the blinded stratified annotation set (`blinded_annotation_worksheet.csv`, `N = 84`).\n"
            "- **Open Definitions to Lock Before ML Fitting:** (a) exact denominator and per-stratum weighting vs. unweighted pooling, (b) sampling stratification across UP 2020/Batch 1, later UP cohorts, Bihar, and MP, and (c) operational definition of `EXPLAINABLE` separating explainable digitization/batch artifacts from substantive infrastructure or coverage discrepancies.\n"
            "- **Lock Rule:** Do not fit Isolation Forest or adjust thresholds based on observed results until completed annotations and their SHA-256 manifest are frozen.\n"
        )
        proto_text = proto_path.read_text(encoding="utf-8")
        if "Protocol Amendment v1.1" not in proto_text:
            proto_path.write_text(proto_text + amendment, encoding="utf-8")

    print(json.dumps({
        "blinded_worksheet": str(p_ws),
        "sampling_manifest": str(p_man),
        "total_sampled": int(len(sampled)),
        "strata": strata_meta,
    }, indent=2))


if __name__ == "__main__":
    main()
