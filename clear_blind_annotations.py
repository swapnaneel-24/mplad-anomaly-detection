from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import pandas as pd

REVIEW_COLS: List[str] = [
    "observed_geometry_issue",
    "supporting_source_evidence",
    "alternative_benign_explanation",
    "reviewer_confidence",
    "audit_disposition",
    "reviewer_notes",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Clear review remarks on blinded annotation rows.")
    parser.add_argument("--items", nargs="*", default=["BLIND_013"], help="Specific BLIND_xxx IDs to clear (default: BLIND_013).")
    parser.add_argument("--start", type=int, default=None, help="Optional start BLIND item number.")
    parser.add_argument("--end", type=int, default=None, help="Optional end BLIND item number.")
    parser.add_argument("--all", action="store_true", help="Clear all rows in worksheet.")
    args = parser.parse_args()

    ws_path = Path(
        "research/pmgsy_iii_investigation/outputs/option_b_v2_evidence_review/blinded_annotation_v1/blinded_annotation_worksheet.csv"
    )
    if not ws_path.exists():
        raise FileNotFoundError(f"Worksheet not found: {ws_path}")

    df = pd.read_csv(ws_path)
    for col in REVIEW_COLS:
        if col in df.columns:
            df[col] = df[col].astype("object")

    if args.all:
        mask = pd.Series(True, index=df.index)
        label = "ALL rows"
    elif args.start is not None or args.end is not None:
        lo = 1 if args.start is None else args.start
        hi = len(df) if args.end is None else args.end
        ids = {f"BLIND_{i:03d}" for i in range(lo, hi + 1)}
        mask = df["blind_item_id"].isin(ids)
        label = f"BLIND_{lo:03d}..BLIND_{hi:03d}"
    else:
        ids = {x.strip().upper() for x in args.items if x.strip()}
        mask = df["blind_item_id"].isin(ids)
        label = ", ".join(sorted(ids))

    matched = int(mask.sum())
    for col in REVIEW_COLS:
        if col in df.columns:
            df.loc[mask, col] = ""

    df.to_csv(ws_path, index=False)
    print(f"Cleared {REVIEW_COLS} on {matched} row(s) [{label}] in {ws_path}.")


if __name__ == "__main__":
    main()
