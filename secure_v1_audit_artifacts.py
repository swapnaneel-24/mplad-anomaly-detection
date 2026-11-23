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
    results_csv = exp_dir / "IF_ENRICHED_AUDIT_RESULTS_V1.csv"
    key_csv = diag_dir / "if_enriched_audit_unblinded_key_DO_NOT_PEEK.csv"
    pre_freeze_json = diag_dir / "IF_AUDIT_PRE_UNBLIND_FREEZE.json"

    for p in [blind_csv, results_csv, key_csv, pre_freeze_json]:
        if not p.exists():
            raise FileNotFoundError(f"Missing expected artifact: {p}")

    pre_freeze = json.loads(pre_freeze_json.read_text(encoding="utf-8"))
    key_hash_actual = sha256_file(key_csv)
    key_hash_expected = pre_freeze["files"]["if_enriched_audit_unblinded_key_DO_NOT_PEEK.csv"]["sha256"]
    if key_hash_actual != key_hash_expected:
        raise ValueError(f"Unblinding key hash mismatch! Expected {key_hash_expected}, got {key_hash_actual}")

    manifest = {
        "manifest_version": "IF_V1_AUDIT_PROVENANCE_V1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": {
            "IF_ENRICHED_AUDIT_RESULTS_V1.csv": {
                "path": str(results_csv.relative_to(repo_root)).replace("\\", "/"),
                "sha256": sha256_file(results_csv),
                "bytes": results_csv.stat().st_size,
                "access_policy": "IMMUTABLE_VERSIONED_PUBLIC_RESEARCH",
            },
            "if_enriched_audit_blind_review.csv": {
                "path": str(blind_csv.relative_to(repo_root)).replace("\\", "/"),
                "sha256": sha256_file(blind_csv),
                "bytes": blind_csv.stat().st_size,
                "access_policy": "VERSIONED_WORKING_BLIND_SHEET",
            },
            "if_enriched_audit_unblinded_key_DO_NOT_PEEK.csv": {
                "restricted_archive_ref": "local_restricted://diagnostics/if_enriched_audit_unblinded_key_DO_NOT_PEEK.csv",
                "sha256": key_hash_actual,
                "bytes": key_csv.stat().st_size,
                "access_policy": "RESTRICTED_ARCHIVE_DO_NOT_PUBLISH_TO_MAIN",
            },
        },
    }

    manifest_path = exp_dir / "IF_V1_AUDIT_PROVENANCE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Ensure unblinding key stays excluded from public git commits
    gitignore_path = repo_root / ".gitignore"
    ignore_entry = "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1/diagnostics/if_enriched_audit_unblinded_key_DO_NOT_PEEK.csv"
    existing_gi = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    if ignore_entry not in existing_gi:
        with gitignore_path.open("a", encoding="utf-8") as f:
            if existing_gi and not existing_gi.endswith("\n"):
                f.write("\n")
            f.write(ignore_entry + "\n")

    print("Verified unblinding key SHA-256 matches pre-unblind freeze.")
    print(f"Wrote provenance manifest: {manifest_path}")
    print(f"IF_ENRICHED_AUDIT_RESULTS_V1.csv SHA-256: {manifest['artifacts']['IF_ENRICHED_AUDIT_RESULTS_V1.csv']['sha256']}")


if __name__ == "__main__":
    main()
