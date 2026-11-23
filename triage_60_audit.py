from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

OUTCOME_CHOICES: List[Tuple[str, str]] = [
    ("1", "VERIFIED_ACTIONABLE_IRREGULARITY"),
    ("2", "VERIFIED_BENIGN_STRUCTURE"),
    ("3", "SOURCE_PROCESSING_ARTIFACT"),
    ("4", "UNRESOLVED"),
    ("5", "INSUFFICIENT_EVIDENCE"),
]

CONF_CHOICES: Dict[str, str] = {
    "h": "HIGH",
    "m": "MEDIUM",
    "l": "LOW",
}


def recommend_desk_outcome(row: pd.Series) -> Tuple[str, str, str]:
    """Heuristic desk suggestion (always user-confirmed; never auto-committed silently)."""
    prop = pd.to_numeric(row.get("proposed_l_km"), errors="coerce")
    mapped = pd.to_numeric(row.get("sum_geom_len_km"), errors="coerce")
    n_seg = pd.to_numeric(row.get("n_segments"), errors="coerce")
    sin = pd.to_numeric(row.get("mean_sinuosity"), errors="coerce")
    vpk = pd.to_numeric(row.get("vertices_per_km"), errors="coerce")
    conc = pd.to_numeric(row.get("seg_len_concentration"), errors="coerce")

    prop_v = float(prop) if pd.notna(prop) else 0.0
    mapped_v = float(mapped) if pd.notna(mapped) else 0.0
    n_seg_v = int(n_seg) if pd.notna(n_seg) else 0
    sin_v = float(sin) if pd.notna(sin) else 0.0
    vpk_v = float(vpk) if pd.notna(vpk) else 0.0
    conc_v = float(conc) if pd.notna(conc) else 0.0

    if prop_v <= 0.0 and mapped_v <= 0.0:
        return (
            "INSUFFICIENT_EVIDENCE",
            "LOW",
            "Both proposed and mapped lengths are missing/zero in desk attributes.",
        )

    ratio = (mapped_v / prop_v) if prop_v > 0 else np.nan
    abs_rel_gap = abs(ratio - 1.0) if pd.notna(ratio) else 1.0

    # Large length discrepancy or extreme sinuosity/vertex density
    if abs_rel_gap >= 0.25 or sin_v >= 3.0 or vpk_v >= 120.0:
        return (
            "VERIFIED_ACTIONABLE_IRREGULARITY",
            "MEDIUM",
            f"Notable desk divergence (r={ratio:.2f} if finite, sin={sin_v:.2f}, vert/km={vpk_v:.1f}).",
        )

    # Multi-segment or split-concentration pattern likely reflecting GIS/segmentation convention
    if n_seg_v >= 2 and (conc_v < 0.85 or abs_rel_gap >= 0.08):
        return (
            "SOURCE_PROCESSING_ARTIFACT",
            "MEDIUM",
            f"Multi-segment structure (n_segments={n_seg_v}, conc={conc_v:.2f}) suggests segmentation/processing convention.",
        )

    # Borderline length gap or moderate curvature
    if (0.08 <= abs_rel_gap < 0.25) or (1.8 <= sin_v < 3.0):
        return (
            "UNRESOLVED",
            "LOW",
            f"Moderate desk variation (r={ratio:.2f} if finite, sin={sin_v:.2f}); borderline without external map.",
        )

    return (
        "VERIFIED_BENIGN_STRUCTURE",
        "HIGH",
        f"Lengths and structure look consistent with standard alignment (r={ratio:.2f} if finite, segs={n_seg_v}).",
    )


def main() -> None:
    blind_path = Path(
        "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1/diagnostics/if_enriched_audit_blind_review.csv"
    )
    if not blind_path.exists():
        raise FileNotFoundError(f"Missing {blind_path}")

    df = pd.read_csv(blind_path)
    for col in [
        "review_outcome",
        "reviewer_confidence",
        "observed_finding",
        "supporting_source_evidence",
        "alternative_benign_explanation",
        "reviewer_notes",
    ]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str)

    print(f"Loaded {len(df)} rows. Columns ({len(df.columns)}): {', '.join(df.columns)}")
    print("Keys: [Enter] = accept recommended | [1-5] = pick outcome | [s] = skip row | [q] = save & quit\n")

    for idx, row in df.iterrows():
        existing_out = row["review_outcome"].strip()
        rec_out, rec_conf, rec_reason = recommend_desk_outcome(row)

        print("=" * 76)
        item_id = row.get("audit_item_id", f"ROW_{idx+1:03d}")
        print(f"[{idx+1}/{len(df)}] {item_id}  |  Current outcome: '{existing_out or 'BLANK'}'")

        # Print all non-empty data columns cleanly (excluding long blank review fields)
        skip_display = {
            "review_outcome",
            "reviewer_confidence",
            "observed_finding",
            "supporting_source_evidence",
            "alternative_benign_explanation",
            "reviewer_notes",
        }
        for col in df.columns:
            if col in skip_display:
                continue
            val = row[col]
            if pd.notna(val) and str(val).strip() != "":
                print(f"  {col}: {val}")

        print("\nOptions:")
        for num, label in OUTCOME_CHOICES:
            marker = " <-- RECOMMENDED" if label == rec_out else ""
            print(f"  [{num}] {label}{marker}")
        print(f"  Recommended confidence: {rec_conf}  |  Reason: {rec_reason}")

        choice = input("Select [Enter=recommended, 1-5, s=skip, q=quit]: ").strip().lower()
        if choice == "q":
            df.to_csv(blind_path, index=False)
            print(f"\nSaved progress and quit at row {idx+1}/{len(df)}.")
            return
        if choice == "s":
            continue

        if choice == "":
            chosen_outcome = rec_out
            chosen_conf = rec_conf
        elif choice in dict(OUTCOME_CHOICES):
            chosen_outcome = dict(OUTCOME_CHOICES)[choice]
            conf_in = input("Confidence [Enter=recommended, h=HIGH, m=MEDIUM, l=LOW]: ").strip().lower()
            chosen_conf = CONF_CHOICES.get(conf_in, rec_conf)
        else:
            print("Unrecognized input; accepting recommended option.")
            chosen_outcome = rec_out
            chosen_conf = rec_conf

        df.loc[idx, "review_outcome"] = chosen_outcome
        df.loc[idx, "reviewer_confidence"] = chosen_conf
        if df.loc[idx, "reviewer_notes"].strip() == "":
            df.loc[idx, "reviewer_notes"] = f"desk-triage ({rec_reason})"

        df.to_csv(blind_path, index=False)

    print("\nCompleted all rows and saved to:", blind_path)
    print("\nOutcome summary:")
    print(df["review_outcome"].value_counts().to_string())


if __name__ == "__main__":
    main()
