
# Phase 2 — Feature Space Manifest

## Dataset Integrity
- **Rows:** 284,807
- **Missing Values:** 0
- **Target (Class):** Isolated to `ground_truth_registry.csv` to prevent unsupervised leakage.

## Feature Taxonomy
- **Group A (V1-V28):** PCA-derived. Left strictly untouched.
- **Group B (Time):** Elapsed seconds. Scaled.
- **Group C (Amount):** Transaction value. Highly skewed (skew=16.98).

## Controlled Variants
| Feature Space | Features | Transformations | Scaling | Purpose |
|---|---|---|---|---|
| **FS-A** | V1-V28, Time, Amount | Baseline | RobustScaler (Time, Amount) | Primary baseline (median/IQR) |
| **FS-B** | V1-V28, Time, Amount | log1p(Amount) | StandardScaler (Time, Amount) | Sensitivity (variance stabilization) |

## Output Artefacts
1. `ground_truth_registry.csv` (row_id, Class)
2. `ULB_FS_A_Baseline.csv` (row_id, features)
3. `ULB_FS_B_LogAmount.csv` (row_id, features)
