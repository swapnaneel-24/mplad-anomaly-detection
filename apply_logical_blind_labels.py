from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd


def logical_row_annotation(row: pd.Series) -> Dict[str, str]:
    """Deterministic logical labeling (no interactive prompts, no R or tier exposed)."""
    prop = float(row["proposed_l_km"]) if pd.notna(row["proposed_l_km"]) else 0.0
    mapped = float(row["sum_geom_len_km"]) if pd.notna(row["sum_geom_len_km"]) else 0.0
    n_seg = int(row["n_segments"]) if pd.notna(row["n_segments"]) else 0
    year = int(row["ims_year"]) if pd.notna(row["ims_year"]) else -1
    batch = int(row["ims_batch"]) if pd.notna(row["ims_batch"]) else -1
    dist = int(row["lgd_distri"]) if pd.notna(row["lgd_distri"]) else -1
    state = str(row["source_state_key"])
    work = str(row["work_name"]) if pd.notna(row["work_name"]) else ""
    work_short = (work[:36] + "...") if len(work) > 36 else work

    exact_dup = bool(row.get("has_exact_geom_dup", False))
    lin_ov = bool(row.get("has_linear_overlap", False))
    ov_m = float(row.get("max_shared_overlap_m", 0.0) or 0.0)
    zero_len = bool(row.get("has_zero_len_segment", False))
    inv_geom = bool(row.get("has_invalid_segment_geom", False))

    flags: List[str] = []
    if exact_dup:
        flags.append("exact_geom_dup")
    if lin_ov:
        flags.append(f"linear_overlap={ov_m:.1f}m")
    if zero_len:
        flags.append("zero_len_seg")
    if inv_geom:
        flags.append("invalid_seg_geom")

    ratio_approx = (mapped / prop) if prop > 0 else 0.0
    km_gap = mapped - prop

    source_ev = f"{state}, yr={year}, b={batch}, dist={dist}, segs={n_seg}"
    if work_short:
        source_ev += f", work='{work_short}'"

    is_borderline = (not flags) and (
        (0.85 <= ratio_approx < 0.93)
        or (1.07 < ratio_approx <= 1.15)
        or (abs(km_gap) >= 1.5 and abs(ratio_approx - 1.0) <= 0.15)
    )

    if flags:
        obs_issue = f"Flags [{', '.join(flags)}]; mapped {mapped:.2f} km vs prop {prop:.2f} km ({n_seg} seg)"
        benign = (
            "Segment split/joint overlap or digitization tolerance"
            if (lin_ov and not exact_dup and abs(ratio_approx - 1.0) < 0.15)
            else "Geometry/digitization defect or multi-part alignment quirk"
        )
        conf = "MEDIUM" if (lin_ov and not exact_dup and abs(ratio_approx - 1.0) < 0.15) else "HIGH"
        disp = "EXPLAINABLE"
        notes = "topology-flagged-item"
    elif is_borderline:
        obs_issue = f"Borderline gap: mapped {mapped:.2f} km vs prop {prop:.2f} km (delta {km_gap:+.2f} km, {n_seg} seg)"
        benign = "Needs segment/district/batch context before locking benign explanation"
        conf = "MEDIUM"
        disp = "UNRESOLVED"
        notes = "borderline-defer-external-context"
    elif ratio_approx < 0.85:
        obs_issue = f"Mapped {mapped:.2f} km substantially shorter than prop {prop:.2f} km ({n_seg} seg)"
        benign = "Partial/phased corridor mapping or batch digitization convention"
        conf = "MEDIUM"
        disp = "EXPLAINABLE"
        notes = "shortfall-check"
    elif ratio_approx > 1.15:
        obs_issue = f"Mapped {mapped:.2f} km exceeds prop {prop:.2f} km ({n_seg} seg)"
        benign = "Extended alignment trace or route/digitization scope difference"
        conf = "MEDIUM"
        disp = "UNRESOLVED"
        notes = "overlength-check"
    else:
        obs_issue = f"Mapped {mapped:.2f} km close to prop {prop:.2f} km ({n_seg} seg; clean flags)"
        benign = "Normal alignment digitization within standard tolerance"
        conf = "HIGH"
        disp = "EXPLAINABLE"
        notes = "clean-alignment"

    return {
        "observed_geometry_issue": obs_issue,
        "supporting_source_evidence": source_ev,
        "alternative_benign_explanation": benign,
        "reviewer_confidence": conf,
        "audit_disposition": disp,
        "reviewer_notes": notes,
    }


def main() -> None:
    ws_path = Path(
        "research/pmgsy_iii_investigation/outputs/option_b_v2_evidence_review/blinded_annotation_v1/blinded_annotation_worksheet.csv"
    )
    if not ws_path.exists():
        raise FileNotFoundError(f"Worksheet not found: {ws_path}")

    df = pd.read_csv(ws_path)
    df = df.sort_values("blind_item_id").reset_index(drop=True)

    target_cols = [
        "observed_geometry_issue",
        "supporting_source_evidence",
        "alternative_benign_explanation",
        "reviewer_confidence",
        "audit_disposition",
        "reviewer_notes",
    ]
    for col in target_cols:
        if col in df.columns:
            df[col] = df[col].astype("object")

    for idx in df.index:
        ann = logical_row_annotation(df.loc[idx])
        for col, val in ann.items():
            df.loc[idx, col] = val

    df.to_csv(ws_path, index=False)

    print(f"Applied deterministic logical labels & sorted {len(df)} rows in: {ws_path}")
    print("\nDisposition counts:")
    print(df["audit_disposition"].value_counts().to_string())
    print("\nConfidence counts:")
    print(df["reviewer_confidence"].value_counts().to_string())


if __name__ == "__main__":
    main()
