from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import pandas as pd


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ann_dir = Path(
        "research/pmgsy_iii_investigation/outputs/option_b_v2_evidence_review/blinded_annotation_v1"
    )
    ws_path = ann_dir / "blinded_annotation_worksheet.csv"
    key_path = ann_dir / "unblinded_strata_key_DO_NOT_PEEK_DURING_BLIND_REVIEW.csv"

    if not ws_path.exists():
        raise FileNotFoundError(f"Worksheet missing: {ws_path}")

    df = pd.read_csv(ws_path)
    missing_disp = df["audit_disposition"].fillna("").astype(str).str.strip().eq("").sum()
    missing_conf = df["reviewer_confidence"].fillna("").astype(str).str.strip().eq("").sum()
    if missing_disp > 0 or missing_conf > 0:
        raise ValueError(
            f"Cannot freeze incomplete worksheet: missing_disposition={missing_disp}, missing_confidence={missing_conf}"
        )

    # Sync borderline queue for reference before freezing
    borderline_df = df[
        df["reviewer_notes"].fillna("").astype(str).str.contains("borderline-defer", case=False, na=False)
    ].copy()
    bq_path = ann_dir / "borderline_deferred_queue.csv"
    borderline_df.to_csv(bq_path, index=False)

    artifacts: Dict[str, Dict] = {}
    for p in [ws_path, bq_path, key_path]:
        if p.exists():
            artifacts[p.name] = {
                "path": str(p),
                "bytes": int(p.stat().st_size),
                "sha256": sha256_file(p),
            }

    manifest = {
        "freeze_id": "PMGSY3_BLINDED_ANNOTATIONS_V1_FROZEN",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "ml_fitting_status": "AUTHORIZED_NEXT_PER_PROTOCOL_V1",
        "total_rows": int(len(df)),
        "disposition_counts": df["audit_disposition"].value_counts().to_dict(),
        "confidence_counts": df["reviewer_confidence"].value_counts().to_dict(),
        "borderline_deferred_count": int(len(borderline_df)),
        "artifacts": artifacts,
    }

    out_manifest = ann_dir / "ANNOTATIONS_FREEZE_MANIFEST_V1.json"
    out_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Froze {len(df)} annotations -> {out_manifest}")
    print(json.dumps(manifest["disposition_counts"], indent=2))
    print(json.dumps(manifest["confidence_counts"], indent=2))


if __name__ == "__main__":
    main()
