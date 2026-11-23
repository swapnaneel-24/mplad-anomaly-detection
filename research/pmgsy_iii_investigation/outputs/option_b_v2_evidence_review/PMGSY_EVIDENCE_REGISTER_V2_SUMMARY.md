# PEIARS — PMGSY Evidence Register v2 Validation & Queue Summary

- **Generated At (UTC):** 2026-11-23T10:16:36.806845+00:00
- **Register Status:** `4,361` unique `P` packages verified (`0` duplicate `package_uid`, exact match to Option B v2 UIDs, `length_diff_km` and `length_rel_diff` arithmetic verified).
- **Full CSV SHA-256 (`PMGSY_EVIDENCE_REGISTER_V2.csv`, gitignored):** `4b578e6bcf8ece5f6e1f88af1bd07526e69564f6ee30a0a8162bd23d2fbda98f`
- **Relative Difference Definition (`length_rel_diff`):** `(sum_geom_len_km - proposed_l_km) / proposed_l_km` (`> 0` = geometry longer than proposed; `< 0` = geometry shorter than proposed).
- **Queue Sizes:** `P0` topology = `6`, `P1` top-25 `|length_diff_km|` = `25`, `P2` top-25 `|length_rel_diff|` = `25`, deduplicated union = `42`.
- **Cohort Concentration Note:** `UTTAR_PRADESH` / `2020_B1` accounts for `0 / 42` (`0.0%`) of deduplicated queue packages.

## Register Column Null Counts (Non-Zero Only)

None (0 nulls across all columns)

## Deduplicated Queue Concentration by State & Cohort

| source_state_key | cohort_year_batch | queued_packages |
| ---------------- | ----------------- | --------------- |
| UTTAR_PRADESH    |                   | 34              |
| MADHYA_PRADESH   |                   | 6               |
| BIHAR            |                   | 2               |