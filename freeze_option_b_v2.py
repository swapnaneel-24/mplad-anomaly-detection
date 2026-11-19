from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head_sha(repo_root: Path) -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "UNAVAILABLE"


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    snap_dir = repo_root / "data/canonical/pmgsy_v1/pmgsy3_3state_v1"

    tracked_files: List[Path] = [
        repo_root / "environment.yml",
        repo_root / "build_canonical_pmgsy.py",
        repo_root / "score_pmgsy_packages.py",
        repo_root / "export_review_queues_v1.py",
        snap_dir / "manifest.json",
        snap_dir / "snapshot_raw.parquet",
        snap_dir / "segments.parquet",
        snap_dir / "packages.parquet",
        snap_dir / "segments_enriched.csv",
        snap_dir / "packages_enriched.csv",
        snap_dir / "scoring_option_b_v1/scoring_summary.json",
        snap_dir / "scoring_option_b_v1/packages_p_scored_option_b.parquet",
        snap_dir / "scoring_option_b_v1/packages_p_scored_option_b.csv",
        snap_dir / "scoring_option_b_v1/threshold_sensitivity_sweep.csv",
        snap_dir / "scoring_option_b_v1/review_queues/review_queues_manifest.json",
        snap_dir / "scoring_option_b_v2/scoring_summary_v2.json",
        snap_dir / "scoring_option_b_v2/packages_p_scored_option_b_v2.parquet",
        snap_dir / "scoring_option_b_v2/packages_p_scored_option_b_v2.csv",
        snap_dir / "scoring_option_b_v2/state_r_reference_stats.csv",
        snap_dir / "scoring_option_b_v2/packages_non_p_excluded.csv",
    ]

    hashes: Dict[str, Dict] = {}
    for p in tracked_files:
        if not p.exists():
            raise FileNotFoundError(f"Cannot freeze; missing required artifact: {p}")
        rel = p.relative_to(repo_root).as_posix()
        hashes[rel] = {
            "bytes": int(p.stat().st_size),
            "sha256": sha256_file(p),
        }

    v2_summary = json.loads((snap_dir / "scoring_option_b_v2/scoring_summary_v2.json").read_text(encoding="utf-8"))

    freeze_manifest = {
        "freeze_id": "PMGSY3_CANONICAL_V1_OPTION_B_V2_FREEZE",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head_before_commit": git_head_sha(repo_root),
        "governance_status": {
            "canonical_schema": "FROZEN (v1)",
            "scoring_option_b_v1": "FROZEN_HISTORICAL_BASELINE",
            "scoring_option_b_v2": "FROZEN_CURRENT_DESCRIPTIVE_POLICY",
            "ml_fitting_authorized": False,
        },
        "v2_policy_parameters": v2_summary["policy_parameters"],
        "v2_counts": v2_summary["counts"],
        "artifact_checksums": hashes,
    }

    out_path = snap_dir / "FREEZE_MANIFEST_OPTION_B_V2.json"
    out_path.write_text(json.dumps(freeze_manifest, indent=2), encoding="utf-8")
    print(f"Wrote freeze manifest ({len(hashes)} artifacts hashed): {out_path}")


if __name__ == "__main__":
    main()
