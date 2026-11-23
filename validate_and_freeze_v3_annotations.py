from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

ALLOWED_OUTCOMES = {
    "CONFIRMED_SOURCE_DEFECT",
    "SUPPORTED_REVIEW_CANDIDATE",
    "BENIGN_EXPLAINED",
    "UNRESOLVED",
    "INSUFFICIENT_EVIDENCE",
}
ALLOWED_CONF = {"HIGH", "MEDIUM", "LOW"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    repo_root = Path.cwd()
    exp_dir = repo_root / "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1"
    out_dir = exp_dir / "expanded_audit_v3"

    blind_path = out_dir / "IF_V3_BLIND_REVIEW.csv"
    annot_path = out_dir / "IF_V3_BLIND_ANNOTATIONS.csv"
    proto_path = exp_dir / "IF_EXPANDED_AUDIT_PROTOCOL_V1.md"
    add_path = out_dir / "IF_V3_STATISTICAL_ADDENDUM_V1.md"
    freeze_path = out_dir / "IF_V3_ANNOTATIONS_FREEZE.json"

    assert annot_path.exists(), f"Missing completed annotations file: {annot_path}"
    blind = pd.read_csv(blind_path)
    annot = pd.read_csv(annot_path)

    assert len(annot) == 120, f"Expected 120 rows, got {len(annot)}"
    assert annot["audit_item_id"].nunique() == 120, "Duplicate audit_item_id values"
    assert list(annot["audit_item_id"]) == list(blind["audit_item_id"]), "audit_item_id order/set altered"
    assert list(annot["package_uid"]) == list(blind["package_uid"]), "package_uid altered"

    forbidden = {"if_strat_score", "if_strat_top5", "audit_group", "pair_id", "investigation_tier"}
    leaked = forbidden.intersection(set(annot.columns))
    assert not leaked, f"Leaked selection columns in reviewer annotations: {leaked}"

    for col in ["review_outcome", "reviewer_confidence", "evidence_domain", "source_evidence_reference", "observed_finding", "alternative_explanation", "reviewer_id"]:
        assert col in annot.columns, f"Missing required column: {col}"
        blanks = int(annot[col].fillna("").astype(str).str.strip().eq("").sum())
        assert blanks == 0, f"Column {col} has {blanks} blank rows"

    bad_out = set(annot["review_outcome"].astype(str).str.strip()) - ALLOWED_OUTCOMES
    assert not bad_out, f"Invalid review_outcome values: {bad_out}"
    bad_conf = set(annot["reviewer_confidence"].astype(str).str.strip()) - ALLOWED_CONF
    assert not bad_conf, f"Invalid reviewer_confidence values: {bad_conf}"

    # Verify endpoint consistency
    expected_csd = (annot["review_outcome"] == "CONFIRMED_SOURCE_DEFECT").astype(int)
    actual_csd = pd.to_numeric(annot["confirmed_source_defect"], errors="raise").astype(int)
    assert (expected_csd == actual_csd).all(), "Inconsistent confirmed_source_defect indicator"

    freeze_obj = {
        "freeze_version": "IF_V3_ANNOTATIONS_FREEZE_V1",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "reviewer_status": "SINGLE_REVIEWER_LIMITATION (provisional admission interpretation)",
        "hashes": {
            "IF_V3_BLIND_ANNOTATIONS.csv": sha256_file(annot_path),
            "IF_V3_BLIND_REVIEW.csv": sha256_file(blind_path),
            "IF_EXPANDED_AUDIT_PROTOCOL_V1.md": sha256_file(proto_path),
            "IF_V3_STATISTICAL_ADDENDUM_V1.md": sha256_file(add_path),
        },
        "outcome_counts": annot["review_outcome"].value_counts().to_dict(),
    }
    freeze_path.write_text(json.dumps(freeze_obj, indent=2), encoding="utf-8")
    print(f"ALL ANNOTATION INTEGRITY CHECKS PASSED. Wrote -> {freeze_path}")
    print("Outcome counts:", freeze_obj["outcome_counts"])


if __name__ == "__main__":
    main()
