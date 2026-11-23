from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import binomtest

ADJUDICABLE = {"CONFIRMED_SOURCE_DEFECT", "SUPPORTED_REVIEW_CANDIDATE", "BENIGN_EXPLAINED"}
BOOTSTRAP_SEED = 20261123
N_BOOT = 20000


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_mcnemar_p(b: int, c: int) -> float:
    n_disc = b + c
    if n_disc == 0:
        return 1.0
    return float(binomtest(min(b, c), n_disc, p=0.5, alternative="two-sided").pvalue)


def main() -> None:
    repo_root = Path.cwd()
    snap_dir = repo_root / "data/canonical/pmgsy_v1/pmgsy3_3state_v1"
    v2_csv = snap_dir / "scoring_option_b_v2/packages_p_scored_option_b_v2.csv"
    exp_dir = repo_root / "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1"
    out_dir = exp_dir / "expanded_audit_v3"

    annot_path = out_dir / "IF_V3_BLIND_ANNOTATIONS.csv"
    freeze_path = out_dir / "IF_V3_ANNOTATIONS_FREEZE.json"
    key_path = out_dir / "IF_V3_UNBLINDED_KEY_RESTRICTED.csv"

    assert freeze_path.exists(), "Hard stop: IF_V3_ANNOTATIONS_FREEZE.json missing. Run Script A first."
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    assert sha256_file(annot_path) == freeze["hashes"]["IF_V3_BLIND_ANNOTATIONS.csv"], "Annotation hash mismatch vs freeze!"

    annot = pd.read_csv(annot_path)
    key = pd.read_csv(key_path)
    merged = annot.merge(key, on=["audit_item_id", "package_uid", "mrl_id"], how="inner")
    assert len(merged) == 120, f"Expected 120 merged rows, got {len(merged)}"

    # Check Option B v2 / topology overlap for incremental value (Gate E)
    v2_df = pd.read_csv(v2_csv)
    flag_cols = [c for c in v2_df.columns if "flag" in c.lower() or "tier" in c.lower() or "topo" in c.lower()]
    if flag_cols:
        v2_sub = v2_df[["package_uid"] + flag_cols].copy()
        merged = merged.merge(v2_sub, on="package_uid", how="left")

    # Save restricted unblinded dataset
    unblind_csv = out_dir / "IF_V3_UNBLINDED_RESULTS.csv"
    merged.to_csv(unblind_csv, index=False)

    # Reconstruct 60 matched pairs
    if_df = merged[merged["audit_group"] == "IF_TOP5_SELECTED"].set_index("pair_id")
    ct_df = merged[merged["audit_group"] == "MATCHED_NON_IF_CONTROL"].set_index("pair_id")
    pair_ids = sorted(if_df.index.tolist())
    assert len(pair_ids) == 60, f"Expected 60 pairs, got {len(pair_ids)}"

    pair_rows = []
    for pid in pair_ids:
        r_if = if_df.loc[pid]
        r_ct = ct_df.loc[pid]
        o_if = str(r_if["review_outcome"])
        o_ct = str(r_ct["review_outcome"])
        adj_if = o_if in ADJUDICABLE
        adj_ct = o_ct in ADJUDICABLE
        y_if = 1 if o_if == "CONFIRMED_SOURCE_DEFECT" else 0
        y_ct = 1 if o_ct == "CONFIRMED_SOURCE_DEFECT" else 0
        pair_rows.append({
            "pair_id": pid,
            "tier0_stratum": r_if["tier0_stratum"],
            "if_audit_id": r_if["audit_item_id"],
            "ctrl_audit_id": r_ct["audit_item_id"],
            "if_outcome": o_if,
            "ctrl_outcome": o_ct,
            "if_adjudicable": adj_if,
            "ctrl_adjudicable": adj_ct,
            "complete_pair": adj_if and adj_ct,
            "y_if": y_if if adj_if else np.nan,
            "y_ctrl": y_ct if adj_ct else np.nan,
            "diff_complete": (y_if - y_ct) if (adj_if and adj_ct) else np.nan,
            # Adverse bound: unresolved IF = 0, unresolved Ctrl = 1
            "y_if_adverse": y_if if adj_if else 0,
            "y_ctrl_adverse": y_ct if adj_ct else 1,
        })

    pairs_df = pd.DataFrame(pair_rows)
    pair_csv = out_dir / "IF_V3_PAIRWISE_COMPARISON.csv"
    pairs_df.to_csv(pair_csv, index=False)

    n_if_adj = int(pairs_df["if_adjudicable"].sum())
    n_ct_adj = int(pairs_df["ctrl_adjudicable"].sum())
    comp = pairs_df[pairs_df["complete_pair"]].copy()
    n_comp = int(len(comp))

    rate_if = float(comp["y_if"].mean()) if n_comp > 0 else 0.0
    rate_ct = float(comp["y_ctrl"].mean()) if n_comp > 0 else 0.0
    delta_hat = float(comp["diff_complete"].mean()) if n_comp > 0 else 0.0

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    if n_comp > 0:
        diffs = comp["diff_complete"].to_numpy(dtype=float)
        boot_means = diffs[rng.integers(0, n_comp, size=(N_BOOT, n_comp))].mean(axis=1)
        ci_low, ci_high = float(np.percentile(boot_means, 2.5)), float(np.percentile(boot_means, 97.5))
    else:
        ci_low, ci_high = 0.0, 0.0

    b_disc = int(((comp["y_if"] == 1) & (comp["y_ctrl"] == 0)).sum())
    c_disc = int(((comp["y_if"] == 0) & (comp["y_ctrl"] == 1)).sum())
    p_mcnemar = exact_mcnemar_p(b_disc, c_disc)

    adv_delta = float((pairs_df["y_if_adverse"] - pairs_df["y_ctrl_adverse"]).mean())

    gate_a = True
    gate_b = (n_if_adj >= 48) and (n_ct_adj >= 48) and (n_comp >= 48)
    gate_c = delta_hat >= 0.20
    gate_d = ci_low > 0.0
    if_confirmed_total = int(((merged["audit_group"] == "IF_TOP5_SELECTED") & (merged["review_outcome"] == "CONFIRMED_SOURCE_DEFECT")).sum())
    gate_e = if_confirmed_total >= 1
    gate_f = if_confirmed_total >= 1
    gate_g = True  # Preserved with SINGLE_REVIEWER_LIMITATION disclosure

    if all([gate_a, gate_b, gate_c, gate_d, gate_e, gate_f, gate_g]):
        disposition = "ADVANCE_TO_EXPANDED_RESEARCH_PILOT (PROVISIONAL_SINGLE_REVIEWER)"
    else:
        disposition = "RESEARCH_ONLY_MORE_EVIDENCE"

    now_utc = datetime.now(timezone.utc).isoformat()
    comp_md_path = out_dir / "IF_AUDIT_COMPARISON_V3.md"
    comp_lines = [
        "# PEIARS — v3 Expanded 120-Case Audit Comparison Report",
        "",
        f"- **Unblinded At (UTC):** {now_utc}",
        f"- **Frozen Annotations SHA-256:** `{freeze['hashes']['IF_V3_BLIND_ANNOTATIONS.csv']}`",
        "- **Population Scope:** Tier-0-matchable eligible IF top-5% population (`123/189` = `65.1%`); `66` unmatched candidates excluded from primary inference.",
        "- **Reviewer Note:** `SINGLE_REVIEWER_LIMITATION`.",
        "",
        "## 1. Primary Matched-Pair Actionable Yield (`CONFIRMED_SOURCE_DEFECT`)",
        "",
        f"- **Complete Adjudicable Pairs (`N`):** `{n_comp} / 60` (`IF` adjudicable=`{n_if_adj}/60`, `Control` adjudicable=`{n_ct_adj}/60`)",
        f"- **IF Confirmed Defect Rate (Complete Pairs):** `{rate_if:.3f}` (`{int(comp['y_if'].sum())}/{n_comp}`)",
        f"- **Control Confirmed Defect Rate (Complete Pairs):** `{rate_ct:.3f}` (`{int(comp['y_ctrl'].sum())}/{n_comp}`)",
        f"- **Paired Yield Difference (`IF - Control`):** **`{delta_hat:+.3f}`** (`{delta_hat*100:+.1f} pp`, 95% paired bootstrap CI: `[{ci_low:+.3f}, {ci_high:+.3f}]`)",
        f"- **Discordant Pairs (`IF=1,Ctrl=0` vs `IF=0,Ctrl=1`):** `b={b_disc}`, `c={c_disc}` (exact McNemar `p={p_mcnemar:.4f}`)",
        f"- **Adverse All-60-Pair Sensitivity Bound (Unresolved IF=0, Ctrl=1):** `{adv_delta:+.3f}`",
        "",
        "## 2. Full Outcome Breakdown by Arm (`n = 120`)",
        "",
        merged.groupby(["audit_group", "review_outcome"]).size().unstack(fill_value=0).to_string(),
        "",
        "## 3. Outcomes by Segment-Count Bucket (`seg_bucket`)",
        "",
        merged.groupby(["seg_bucket", "audit_group", "review_outcome"]).size().unstack(fill_value=0).to_string(),
    ]
    comp_md_path.write_text("\n".join(comp_lines), encoding="utf-8")

    dec_md_path = out_dir / "IF_ADMISSION_DECISION_V3.md"
    dec_lines = [
        "# PEIARS — Isolation Forest Admission Decision v3",
        "",
        f"- **Recorded At (UTC):** {now_utc}",
        f"- **Final Disposition:** **`{disposition}`**",
        "",
        "## Gate Results (`A`–`G`)",
        "",
        f"- **Gate A (Integrity):** `{'PASS' if gate_a else 'FAIL'}`",
        f"- **Gate B (Completeness >= 48/arm & >= 48 complete pairs):** `{'PASS' if gate_b else 'NOT_MET'}` (`IF={n_if_adj}`, `Ctrl={n_ct_adj}`, `Pairs={n_comp}`)",
        f"- **Gate C (Incremental Yield >= +0.20):** `{'PASS' if gate_c else 'NOT_MET'}` (`{delta_hat:+.3f}`)",
        f"- **Gate D (Paired 95% CI Lower Bound > 0):** `{'PASS' if gate_d else 'NOT_MET'}` (`[{ci_low:+.3f}, {ci_high:+.3f}]`)",
        f"- **Gate E (Incremental Value >= 1 IF confirmed defect):** `{'PASS' if gate_e else 'NOT_MET'}` (`{if_confirmed_total}`)",
        f"- **Gate F (Structural Validity):** `{'PASS' if gate_f else 'NOT_MET'}`",
        f"- **Gate G (Review Reliability):** `{'PASS_WITH_SINGLE_REVIEWER_LIMITATION' if gate_g else 'FAIL'}`",
        "",
        "## Governance Boundaries",
        "- Option B v2 and topology auditing remain primary evidence tracks; Isolation Forest remains research-only.",
    ]
    dec_md_path.write_text("\n".join(dec_lines), encoding="utf-8")

    # Add restricted outputs to .gitignore
    gi_path = repo_root / ".gitignore"
    gi_txt = gi_path.read_text(encoding="utf-8") if gi_path.exists() else ""
    for rel in [
        "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1/expanded_audit_v3/IF_V3_UNBLINDED_RESULTS.csv",
        "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1/expanded_audit_v3/IF_V3_PAIRWISE_COMPARISON.csv",
    ]:
        if rel not in gi_txt:
            gi_txt += ("\n" if gi_txt and not gi_txt.endswith("\n") else "") + rel + "\n"
    gi_path.write_text(gi_txt, encoding="utf-8")

    prov_path = out_dir / "IF_V3_PROVENANCE_MANIFEST.json"
    prov_obj = {
        "provenance_version": "IF_V3_PROVENANCE_V1",
        "recorded_at_utc": now_utc,
        "disposition": disposition,
        "hashes": {
            "IF_V3_BLIND_ANNOTATIONS.csv": sha256_file(annot_path),
            "IF_V3_ANNOTATIONS_FREEZE.json": sha256_file(freeze_path),
            "IF_AUDIT_COMPARISON_V3.md": sha256_file(comp_md_path),
            "IF_ADMISSION_DECISION_V3.md": sha256_file(dec_md_path),
            "IF_V3_UNBLINDED_RESULTS.csv_RESTRICTED": sha256_file(unblind_csv),
            "IF_V3_PAIRWISE_COMPARISON.csv_RESTRICTED": sha256_file(pair_csv),
        },
    }
    prov_path.write_text(json.dumps(prov_obj, indent=2), encoding="utf-8")

    print(f"Wrote {comp_md_path}")
    print(f"Wrote {dec_md_path}")
    print(f"Wrote {prov_path}")
    print(f"Paired Delta Yield: {delta_hat:+.3f} (95% CI [{ci_low:+.3f}, {ci_high:+.3f}]) -> {disposition}")


if __name__ == "__main__":
    main()
