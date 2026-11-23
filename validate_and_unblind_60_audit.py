from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

ALLOWED_OUTCOMES = {
    "VERIFIED_ACTIONABLE_IRREGULARITY",
    "VERIFIED_BENIGN_STRUCTURE",
    "SOURCE_PROCESSING_ARTIFACT",
    "UNRESOLVED",
    "INSUFFICIENT_EVIDENCE",
}
ADJUDICABLE_OUTCOMES = {
    "VERIFIED_ACTIONABLE_IRREGULARITY",
    "VERIFIED_BENIGN_STRUCTURE",
    "SOURCE_PROCESSING_ARTIFACT",
}
ALLOWED_CONF = {"HIGH", "MEDIUM", "LOW"}


def two_prop_diff_ci95(a1: int, n1: int, a2: int, n2: int) -> tuple[float, float, float]:
    p1 = a1 / n1 if n1 > 0 else 0.0
    p2 = a2 / n2 if n2 > 0 else 0.0
    diff = p1 - p2
    se = math.sqrt(
        (p1 * (1.0 - p1) / n1 if n1 > 0 else 0.0)
        + (p2 * (1.0 - p2) / n2 if n2 > 0 else 0.0)
    )
    z = 1.959963984540054
    return diff, diff - z * se, diff + z * se


def main() -> None:
    repo_root = Path.cwd()
    exp_dir = repo_root / "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1"
    diag_dir = exp_dir / "diagnostics"

    blind_path = diag_dir / "if_enriched_audit_blind_review.csv"
    key_path = diag_dir / "if_enriched_audit_unblinded_key_DO_NOT_PEEK.csv"
    blind = pd.read_csv(blind_path)
    key = pd.read_csv(key_path)

    if len(blind) != 60 or blind["audit_item_id"].nunique() != 60:
        raise ValueError(
            f"Expected 60 unique audit_item_id rows, got {len(blind)} rows / {blind['audit_item_id'].nunique()} unique."
        )

    for col in ["review_outcome", "reviewer_confidence"]:
        if col not in blind.columns:
            raise ValueError(f"Missing required column: {col}")
        blank_n = blind[col].fillna("").astype(str).str.strip().eq("").sum()
        if blank_n > 0:
            raise ValueError(f"Column '{col}' has {blank_n} blank rows. Complete all 60 rows before unblinding.")

    for col in ["observed_finding", "supporting_source_evidence", "alternative_benign_explanation"]:
        if col not in blind.columns:
            blind[col] = ""
        blind[col] = blind[col].fillna("").astype(str)

    bad_outcomes = set(blind["review_outcome"].astype(str).str.strip()) - ALLOWED_OUTCOMES
    if bad_outcomes:
        raise ValueError(f"Invalid review_outcome values: {sorted(bad_outcomes)}")

    bad_conf = set(blind["reviewer_confidence"].astype(str).str.strip()) - ALLOWED_CONF
    if bad_conf:
        raise ValueError(f"Invalid reviewer_confidence values: {sorted(bad_conf)}")

    frozen_results_path = exp_dir / "IF_ENRICHED_AUDIT_RESULTS_V1.csv"
    blind.to_csv(frozen_results_path, index=False)
    res_sha256 = hashlib.sha256(frozen_results_path.read_bytes()).hexdigest()

    merged = blind.merge(key, on=["audit_item_id", "package_uid", "mrl_id"], how="inner")
    if len(merged) != 60:
        raise ValueError(f"Unblind merge mismatch: expected 60 rows, got {len(merged)}.")

    sel = merged[merged["audit_group"] == "IF_TOP5_SELECTED"]
    ctrl = merged[merged["audit_group"] == "MATCHED_NON_IF_CONTROL"]

    n_sel_adj = int(sel["review_outcome"].isin(ADJUDICABLE_OUTCOMES).sum())
    n_ctrl_adj = int(ctrl["review_outcome"].isin(ADJUDICABLE_OUTCOMES).sum())
    a_sel = int((sel["review_outcome"] == "VERIFIED_ACTIONABLE_IRREGULARITY").sum())
    a_ctrl = int((ctrl["review_outcome"] == "VERIFIED_ACTIONABLE_IRREGULARITY").sum())

    rate_sel = a_sel / n_sel_adj if n_sel_adj > 0 else 0.0
    rate_ctrl = a_ctrl / n_ctrl_adj if n_ctrl_adj > 0 else 0.0
    delta_yield, ci_low, ci_high = two_prop_diff_ci95(a_sel, n_sel_adj, a_ctrl, n_ctrl_adj)

    gate_b_pass = (
        (n_sel_adj >= 24)
        and (n_ctrl_adj >= 24)
        and (delta_yield >= 0.20)
        and (ci_low > 0.0)
    )
    disposition = "ADVANCE_TO_EXPANDED_RESEARCH_PILOT" if gate_b_pass else "RESEARCH_ONLY_MORE_EVIDENCE"

    comp_path = exp_dir / "IF_AUDIT_COMPARISON_REPORT.md"
    comp_md = "\n".join([
        "# PEIARS — IF 60-Case Audit Comparison Report",
        "",
        f"- **Unblinded At (UTC):** {datetime.now(timezone.utc).isoformat()}",
        f"- **Frozen Adjudications SHA-256:** `{res_sha256}`",
        "- **Scope Note:** Single-reviewer desk adjudication from canonical package geometry/attributes without external field survey data.",
        "",
        "## Primary Yield Comparison",
        f"- **IF_TOP5_SELECTED (`n={len(sel)}`, adjudicable=`{n_sel_adj}`):** `{a_sel}` verified actionable (`{rate_sel:.3f}`)",
        f"- **MATCHED_NON_IF_CONTROL (`n={len(ctrl)}`, adjudicable=`{n_ctrl_adj}`):** `{a_ctrl}` verified actionable (`{rate_ctrl:.3f}`)",
        f"- **Delta Yield (`IF - Control`):** **`{delta_yield:+.3f}`** (95% CI: `[{ci_low:+.3f}, {ci_high:+.3f}]`)",
        "",
        "## Outcome Counts by Group",
        merged.groupby(["audit_group", "review_outcome"]).size().unstack(fill_value=0).to_string(),
    ])
    comp_path.write_text(comp_md, encoding="utf-8")

    dec_path = exp_dir / "IF_ADMISSION_DECISION_V2.md"
    dec_md = "\n".join([
        "# PEIARS — Isolation Forest Admission Decision v2",
        "",
        f"- **Recorded At (UTC):** {datetime.now(timezone.utc).isoformat()}",
        f"- **Recommended Disposition:** **`{disposition}`**",
        f"- **Gate B (Adjudicable >= 24 each, Delta Yield >= +0.20, 95% CI Low > 0):** `{'PASS' if gate_b_pass else 'NOT_MET / INCONCLUSIVE'}`",
        f"- **Observed Delta Yield:** `{delta_yield:+.3f}` (95% CI `[{ci_low:+.3f}, {ci_high:+.3f}]`)",
        "- **Primary Pipeline Rule:** Option B v2 + topology audit remain primary; no production anomaly scoring or Option B v3 from this step.",
    ])
    dec_path.write_text(dec_md, encoding="utf-8")

    print(f"Wrote {frozen_results_path}")
    print(f"Wrote {comp_path}")
    print(f"Wrote {dec_path}")
    print(f"Delta yield: {delta_yield:+.3f} (95% CI [{ci_low:+.3f}, {ci_high:+.3f}]) -> {disposition}")


if __name__ == "__main__":
    main()
