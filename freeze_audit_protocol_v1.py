from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    repo_root = Path.cwd()
    exp_dir = repo_root / "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1"
    diag_dir = exp_dir / "diagnostics"

    blind_csv = diag_dir / "if_enriched_audit_blind_review.csv"
    key_csv = diag_dir / "if_enriched_audit_unblinded_key_DO_NOT_PEEK.csv"
    if not blind_csv.exists() or not key_csv.exists():
        raise FileNotFoundError("Missing blinded 60-item review CSV or unblinded key CSV.")

    protocol_path = exp_dir / "IF_AUDIT_PROTOCOL_V1.md"
    protocol_md = "\n".join([
        "# PEIARS — Isolation Forest Blind Audit Protocol v1",
        "",
        f"- **Frozen At (UTC):** {datetime.now(timezone.utc).isoformat()}",
        "- **Scope:** 60 packages (`IFAUD_001`–`IFAUD_060`: 30 `IF_TOP5_SELECTED` + 30 `MATCHED_NON_IF_CONTROL`).",
        "- **Blinding Rule:** Do not open `if_enriched_audit_unblinded_key_DO_NOT_PEEK.csv` or inspect IF scores/group labels until all 60 adjudications are complete and frozen.",
        "- **Reviewer Note:** If single-reviewer adjudication is used, disclose single-reviewer scope in notes.",
        "",
        "## Allowed `review_outcome` Values",
        "- `VERIFIED_ACTIONABLE_IRREGULARITY` (positive actionable finding)",
        "- `VERIFIED_BENIGN_STRUCTURE`",
        "- `SOURCE_PROCESSING_ARTIFACT`",
        "- `UNRESOLVED`",
        "- `INSUFFICIENT_EVIDENCE`",
        "",
        "## Required Fields per Row in `if_enriched_audit_blind_review.csv`",
        "- `review_outcome`, `reviewer_confidence`, `observed_finding`, `supporting_source_evidence`, `alternative_benign_explanation`, `reviewer_notes`.",
        "",
        "## Proposed Gate B Research Utility Target (Frozen Pre-Unblinding)",
        "- At least 24 adjudicable cases per group (`VERIFIED_ACTIONABLE_IRREGULARITY` or `VERIFIED_BENIGN_STRUCTURE` or `SOURCE_PROCESSING_ARTIFACT`).",
        "- IF actionable rate at least 20 percentage points above matched controls with a 95% confidence interval lower bound greater than 0.",
    ])
    protocol_path.write_text(protocol_md, encoding="utf-8")

    freeze_obj = {
        "protocol_version": "IF_AUDIT_PROTOCOL_V1",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": {
            "IF_AUDIT_PROTOCOL_V1.md": {"sha256": sha256_file(protocol_path), "bytes": protocol_path.stat().st_size},
            "if_enriched_audit_blind_review.csv": {"sha256": sha256_file(blind_csv), "bytes": blind_csv.stat().st_size},
            "if_enriched_audit_unblinded_key_DO_NOT_PEEK.csv": {"sha256": sha256_file(key_csv), "bytes": key_csv.stat().st_size},
        },
    }
    freeze_path = diag_dir / "IF_AUDIT_PRE_UNBLIND_FREEZE.json"
    freeze_path.write_text(json.dumps(freeze_obj, indent=2), encoding="utf-8")
    print(f"Wrote protocol: {protocol_path}")
    print(f"Wrote pre-unblind freeze manifest: {freeze_path}")


if __name__ == "__main__":
    main()
