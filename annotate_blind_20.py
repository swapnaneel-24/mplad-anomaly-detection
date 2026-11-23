from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

ALLOWED_DISPOSITIONS = {
    "1": "EXPLAINABLE",
    "2": "UNRESOLVED",
    "3": "NOT_INDEPENDENTLY_VERIFIABLE",
    "EXPLAINABLE": "EXPLAINABLE",
    "UNRESOLVED": "UNRESOLVED",
    "NOT_INDEPENDENTLY_VERIFIABLE": "NOT_INDEPENDENTLY_VERIFIABLE",
}

ALLOWED_CONFIDENCE = {
    "H": "HIGH",
    "M": "MEDIUM",
    "L": "LOW",
    "HIGH": "HIGH",
    "MEDIUM": "MEDIUM",
    "LOW": "LOW",
}


def suggest_draft(row: pd.Series) -> Dict[str, str]:
    """Factual draft helper (no R or tier exposed) following the review decision tree."""
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

    flags = []
    if exact_dup:
        flags.append("exact_geom_dup")
    if lin_ov:
        flags.append(f"linear_overlap={ov_m:.1f}m")
    if zero_len:
        flags.append("zero_len_seg")
    if inv_geom:
        flags.append("invalid_seg_geom")

    ratio_approx = (mapped / prop) if prop > 0 else 0.0

    source_ev = f"{state}, yr={year}, b={batch}, dist={dist}, segs={n_seg}"
    if work_short:
        source_ev += f", work='{work_short}'"

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


def prompt_with_default(label: str, default_val: str) -> str:
    val = input(f"  {label} [{default_val}]: ").strip()
    return default_val if val == "" else val


def prompt_disposition(default_disp: str) -> str:
    while True:
        raw = input(
            f"  audit_disposition (1=EXPLAINABLE, 2=UNRESOLVED, 3=NOT_INDEPENDENTLY_VERIFIABLE) [{default_disp}]: "
        ).strip()
        if raw == "":
            return default_disp
        norm = ALLOWED_DISPOSITIONS.get(raw.upper())
        if norm:
            return norm
        print("    Invalid choice. Enter 1, 2, 3, or the exact label name.")


def prompt_confidence(default_conf: str) -> str:
    while True:
        raw = input(f"  reviewer_confidence (H=HIGH, M=MEDIUM, L=LOW) [{default_conf}]: ").strip()
        if raw == "":
            return default_conf
        norm = ALLOWED_CONFIDENCE.get(raw.upper())
        if norm:
            return norm
        print("    Invalid choice. Enter H, M, L, or HIGH / MEDIUM / LOW.")


def main() -> None:
    ws_path = Path(
        "research/pmgsy_iii_investigation/outputs/option_b_v2_evidence_review/blinded_annotation_v1/blinded_annotation_worksheet.csv"
    )
    if not ws_path.exists():
        raise FileNotFoundError(f"Worksheet not found: {ws_path}")

    df = pd.read_csv(ws_path)
    target_mask = df["blind_item_id"].isin([f"BLIND_{i:03d}" for i in range(1, 21)])
    target_indices = df[target_mask].index.tolist()

    print(f"Loaded {len(df)} rows. Reviewing {len(target_indices)} items (BLIND_001 to BLIND_020).")
    print("Press Enter to accept the suggested value, type new text to replace, or type 'q' to save & quit.\n")

    for pos, idx in enumerate(target_indices, start=1):
        row = df.loc[idx]
        draft = suggest_draft(row)

        for col in draft:
            existing = str(row.get(col, "") or "").strip()
            if existing and existing.lower() != "nan":
                draft[col] = existing

        print("=" * 72)
        print(f"[{pos}/20] {row['blind_item_id']} | mrl_id={row['mrl_id']} | state={row['source_state_key']}")
        print(f"  year={row['ims_year']} | batch={row['ims_batch']} | dist={row['lgd_distri']} | block={row['block_id']}")
        print(f"  n_segments={row['n_segments']} | n_distinct_geom={row['n_distinct_geom']}")
        print(f"  proposed_l_km={row['proposed_l_km']} | sum_geom_len_km={row['sum_geom_len_km']}")
        print(
            f"  flags: dup={row['has_exact_geom_dup']}, overlap={row['has_linear_overlap']} "
            f"({row['max_shared_overlap_m']}m), zero_len={row['has_zero_len_segment']}, invalid={row['has_invalid_segment_geom']}"
        )
        print(f"  work_name: {row['work_name']}")
        print("-" * 72)

        obs = prompt_with_default("1. observed_geometry_issue", draft["observed_geometry_issue"])
        if obs.lower() == "q":
            break
        src = prompt_with_default("2. supporting_source_evidence", draft["supporting_source_evidence"])
        if src.lower() == "q":
            break
        ben = prompt_with_default("3. alternative_benign_explanation", draft["alternative_benign_explanation"])
        if ben.lower() == "q":
            break
        conf = prompt_confidence(draft["reviewer_confidence"])
        disp = prompt_disposition(draft["audit_disposition"])
        notes = prompt_with_default("6. reviewer_notes", draft["reviewer_notes"])
        if notes.lower() == "q":
            break

        df.loc[idx, "observed_geometry_issue"] = obs
        df.loc[idx, "supporting_source_evidence"] = src
        df.loc[idx, "alternative_benign_explanation"] = ben
        df.loc[idx, "reviewer_confidence"] = conf
        df.loc[idx, "audit_disposition"] = disp
        df.loc[idx, "reviewer_notes"] = notes

        df.to_csv(ws_path, index=False)
        print(f"  -> Saved {row['blind_item_id']} ({disp}, {conf}).")

    df.to_csv(ws_path, index=False)
    completed = df.loc[target_indices, "audit_disposition"].fillna("").astype(str).str.strip().ne("").sum()
    print(f"\nDone. {completed}/20 items (BLIND_001..BLIND_020) now have audit_disposition recorded in {ws_path}.")


if __name__ == "__main__":
    main()
