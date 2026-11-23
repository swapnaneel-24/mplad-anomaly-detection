from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd


def main() -> None:
    blind_path = Path(
        "research/pmgsy_iii_investigation/outputs/ml_controlled_experiment_v1/diagnostics/if_enriched_audit_blind_review.csv"
    )
    if not blind_path.exists():
        raise FileNotFoundError(f"Missing {blind_path}")

    df = pd.read_csv(blind_path)

    for idx, r in df.iterrows():
        prop = float(r["proposed_l_km"]) if pd.notna(r.get("proposed_l_km")) else 0.0
        mapped = float(r["sum_geom_len_km"]) if pd.notna(r.get("sum_geom_len_km")) else 0.0
        n_seg = int(r["n_segments"]) if pd.notna(r.get("n_segments")) else 0
        sin = float(r["mean_sinuosity"]) if pd.notna(r.get("mean_sinuosity")) else 0.0
        vpk = float(r["vertices_per_km"]) if pd.notna(r.get("vertices_per_km")) else 0.0
        conc = float(r["seg_len_concentration"]) if pd.notna(r.get("seg_len_concentration")) else 0.0
        state = str(r.get("source_state_key", ""))
        coh = str(r.get("cohort_year_batch", ""))
        mrl = str(r.get("mrl_id", ""))
        work = str(r.get("work_name", "") or "").strip()
        work_short = (work[:40] + "...") if len(work) > 40 else work

        diff_km = mapped - prop
        ratio = (mapped / prop) if prop > 0 else np.nan
        ratio_str = f"{ratio:.2f}" if pd.notna(ratio) else "NA"

        obs = (
            f"segs={n_seg}, conc={conc:.2f}, sin={sin:.2f}, vert/km={vpk:.1f}; "
            f"mapped={mapped:.2f} km vs prop={prop:.2f} km (delta={diff_km:+.2f} km, r={ratio_str})"
        )
        ev = f"pkg_table:{state}/{coh}, mrl_id={mrl}" + (f", work='{work_short}'" if work_short else "")
        alt = (
            "Multi-segment split or batch digitization convention"
            if n_seg > 1
            else "High curvature/vertex sampling or local alignment variance"
        )

        # Only fill blank context fields so existing manual edits are never overwritten
        if str(r.get("observed_finding", "") or "").strip() == "":
            df.loc[idx, "observed_finding"] = obs
        if str(r.get("supporting_source_evidence", "") or "").strip() == "":
            df.loc[idx, "supporting_source_evidence"] = ev
        if str(r.get("alternative_benign_explanation", "") or "").strip() == "":
            df.loc[idx, "alternative_benign_explanation"] = alt
        if str(r.get("reviewer_notes", "") or "").strip() == "":
            df.loc[idx, "reviewer_notes"] = "single-reviewer-pass; inspect before unblinding"

    df.to_csv(blind_path, index=False)
    print(f"Pre-filled factual context on {len(df)} rows in: {blind_path}")


if __name__ == "__main__":
    main()
