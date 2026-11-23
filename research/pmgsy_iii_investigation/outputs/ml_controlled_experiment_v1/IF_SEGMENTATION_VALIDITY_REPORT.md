# PEIARS — Isolation Forest Segmentation Validity Report

- **Generated At (UTC):** 2026-11-23T05:48:00.007580+00:00
- **Ablation Reference:** Dropping `n_segments` gives Jaccard `0.5587` vs full 5 features; dropping `seg_len_concentration` gives `0.4649`; dropping both gives `0.1526`.

## 1. IF Top-5% Selection & Feature Profiles Within Matched Segment-Count Buckets

| seg_bucket  | total_pkgs | if_top5_n | if_top5_rate | sel_med_sinuosity | ctrl_med_sinuosity | sel_med_vert_km | ctrl_med_vert_km | sel_med_conc | ctrl_med_conc |
| ----------- | ---------- | --------- | ------------ | ----------------- | ------------------ | --------------- | ---------------- | ------------ | ------------- |
| 1_seg       | 3553       | 47        | 0.0132       | 3.254             | 1.232              | 39.69           | 24.39            | 1.0          | 1.0           |
| 2_segs      | 302        | 95        | 0.3146       | 1.205             | 1.162              | 27.27           | 17.24            | 0.715        | 0.892         |
| 3_to_5_segs | 302        | 48        | 0.1589       | 1.119             | 1.12               | 23.19           | 19.26            | 0.847        | 0.58          |
| 6_plus_segs | 204        | 29        | 0.1422       | 1.064             | 1.105              | 25.62           | 20.4             | 0.223        | 0.402         |

## 2. Diagnostic Takeaway

- Compare `if_top5_rate` and median `mean_sinuosity` / `vertices_per_km` / `seg_len_concentration` between `IF_TOP5` (`sel_*`) and non-selected rows (`ctrl_*`) within the same `seg_bucket`.
- High selection rates or concentration shifts in multi-segment buckets alongside feature-ablation turnover (`0.1526` without both segmentation features) indicate that segmentation structure strongly shapes candidate selection and requires empirical verification on the 60-case audit rather than assuming infrastructure defects.