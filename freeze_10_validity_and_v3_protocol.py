from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    repo_root = Path.cwd()
    exp_dir = repo_root / "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1"
    rev_csv = exp_dir / "IF_10_CASE_VALIDITY_REVIEW_V1.csv"
    if not rev_csv.exists():
        raise FileNotFoundError(f"Missing {rev_csv}")

    df = pd.read_csv(rev_csv)
    rev_hash = sha256_file(rev_csv)
    now_utc = datetime.now(timezone.utc).isoformat()

    # 1. Freeze 10-case validity decision addendum
    val_dec_path = exp_dir / "IF_10_CASE_VALIDITY_DECISION_V1.md"
    reclass_count = int((df["original_v2_outcome"] != df["final_adjudicated_outcome"]).sum())
    outcome_counts = df["final_adjudicated_outcome"].value_counts().to_dict()

    val_lines = [
        "# PEIARS — 10-Case Validity Review Decision Addendum v1",
        "",
        f"- **Frozen At (UTC):** {now_utc}",
        f"- **Source Sheet:** `IF_10_CASE_VALIDITY_REVIEW_V1.csv` (`SHA-256: {rev_hash}`)",
        "- **Original v1 Results Status:** `IF_ENRICHED_AUDIT_RESULTS_V1.csv` remains untouched as a historical record.",
        "- **Reviewer Limitation:** `SINGLE_REVIEWER_LIMITATION` (single desk reviewer; no external field survey data).",
        f"- **Reclassified Rows (vs. Original v2 Outcome):** `{reclass_count} / {len(df)}`",
        f"- **Final Validity Outcomes:** `{outcome_counts}`",
        "",
        "## `IFAUD_023` Sinuosity Reconciliation",
        "",
        "- Prior package feature table recorded `mean_sinuosity = 4.732129`; independent `segments.parquet` (`EPSG:7755`) recomputation yielded `2.866065` across 2 segments (`15.048 km` vs `15.350 km` proposed).",
        "- Both figures are preserved side-by-side without silent overwrite; `IFAUD_023` is held as `UNRESOLVED` pending geometry/aggregation provenance check.",
        "",
        "## Original vs. Revised Summary",
        "",
        df[["audit_id", "audit_group", "original_v2_outcome", "final_adjudicated_outcome", "confidence"]].to_string(index=False),
    ]
    val_dec_path.write_text("\n".join(val_lines), encoding="utf-8")

    # 2. Freeze v3 Expanded Audit Protocol (sample generation still HOLD)
    proto_path = exp_dir / "IF_EXPANDED_AUDIT_PROTOCOL_V1.md"
    proto_lines = [
        "# PEIARS — Expanded Isolation Forest Validation Audit Protocol v1 (v3 Study)",
        "",
        f"- **Protocol Frozen At (UTC):** {now_utc}",
        f"- **Prerequisite Validity Freeze:** `IF_10_CASE_VALIDITY_DECISION_V1.md` (`IF_10_CASE_VALIDITY_REVIEW_V1.csv` SHA-256: `{rev_hash}`)",
        "- **Sample Generation Gate:** **HOLD** until protocol freeze and bipartite Tier-0 matching check are explicitly released.",
        "",
        "## Frozen v3 Design Parameters",
        "",
        "- **Dataset & Model:** `pmgsy3_3state_v1`; frozen 5-feature state-stratified Isolation Forest (`seed = 42`, `contamination = 0.05`, `if_strat_top5`). No model retraining or threshold changes during v3.",
        "- **Sample Size & Exclusions:** `120` packages total (`60` unique 1:1 matched pairs: `60` `IF_TOP5_SELECTED` + `60` `MATCHED_NON_IF_CONTROL`) drawn from `4,301` eligible packages after excluding all `60` v1 audit packages.",
        "- **Sampling Seed & Matching:** Seed `20261123`; Tier-0 exact bipartite 1:1 matching on `(source_state_key, cohort_year_batch, seg_bucket, proposed_length_band)` with random selection of `60` disjoint pairs from maximum matching (`97` Tier-0 candidate pairs identified in feasibility check).",
        "- **Blinding & Review:** Independent, blinded evidence-based review; blinded worksheet hides IF membership/scores; unblinding key stored separately.",
        "",
        "## Primary & Secondary Endpoints",
        "",
        "- **Primary Endpoint:** Independently verified actionable irregularity (`CONFIRMED_SOURCE_DEFECT` or equivalent verified actionable defect), reported separately for source-data vs. infrastructure domains.",
        "- **Secondary Endpoints:** Supported review candidates, benign source-processing artifacts, unresolved cases, and unique IF findings not already flagged by Option B v2 or topology audit.",
        "",
        "## Statistical Analysis & Sensitivity Plan",
        "",
        "- **Pair-Aware Inference:** Matched-pair yield comparison with paired bootstrap 95% CI, discordant-pair counts, and paired binary test.",
        "- **Sensitivity Bounds:** Report complete-case yield alongside bounds treating unresolved cases as positive or negative (including an adverse bound for IF).",
        "",
        "## Decision Gates (`A`–`G`)",
        "",
        "- **Gate A (Integrity):** All 120 records accounted for; frozen sample & unblinding key; zero selection leakage.",
        "- **Gate B (Completeness):** At least `48` adjudicable cases per arm.",
        "- **Gate C (Actionable Yield):** IF minus control yield `>= +0.20` (`+20.0 pp`).",
        "- **Gate D (Uncertainty):** Lower 95% confidence bound of yield difference `> 0`.",
        "- **Gate E (Incremental Value):** At least one verified actionable IF finding not already captured by Option B v2 or topology audit.",
        "- **Gate F (Structural Validity):** Findings not solely explained by benign segmentation conventions.",
        "- **Gate G (Review Reliability):** Reviewer assessments preserved and disagreements resolved transparently.",
    ]
    proto_path.write_text("\n".join(proto_lines), encoding="utf-8")

    print(f"Wrote {val_dec_path}")
    print(f"Wrote {proto_path}")


if __name__ == "__main__":
    main()
