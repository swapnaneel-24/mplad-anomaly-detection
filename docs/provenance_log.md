# Project Provenance and Decision Ledger

## Phase 1: Data Acquisition & Integrity Verification (Stream A)

- **Dataset Identifier:** `ULB_CC_Fraud_2013`
- **Source:** Kaggle (`mlg-ulb/creditcardfraud`)
- **Publishers:** Machine Learning Group (ULB) & Worldline
- **License:** Open Database License (ODbL) v1.0 / Database Contents License (DbCL) v1.0
- **Acquisition Date:** 2026-08-29

### Integrity Audit
- **Expected Dimensions:** 284,807 rows × 31 columns
- **Verified Dimensions:** 284,807 rows × 31 columns (`Passed`)
- **Class Breakdown:** 492 Fraud (0.172%), 284,315 Genuine (99.828%) (`Passed`)
- **Missing Values:** 0 (`Passed`)
- **Verification Script:** `notebooks/phase1_verification.ipynb`
- **SHA-256 Hash:** 76274b691b16a6c49d3f159c883398e03ccd6d1ee12d9d8ee38f4b4b98551a89

### Stream B Update: PMGSY-III Dataset Accepted

**Date:** 2026-09-02
**Dataset:** PMGSY-III Geospatial Registry (`PMGSY_Master_Dataset_Combined(1).csv`)

The earlier PMGSY combined file was found to be incorrectly generated, so it was replaced with the corrected dataset.

The corrected dataset contains **8,868 rows and 13 columns**. It has **3,001 exact duplicate rows**; after removing these, **5,867 unique records remain, with unique `MRL_ID`s**.

After adversarial review, PMGSY-III is **ACCEPTED WITH CONDITIONS** as the second analytical stream.

**Reason for acceptance:**
The corrected dataset provides a sufficiently large, granular government-scheme dataset for testing the project's unsupervised anomaly-detection pipeline. It contains project-level identifiers, administrative information, and temporal variables that can support feature engineering and comparison of Isolation Forest and LOF.

**Conditions for Phase 2:**

1. Remove exact duplicate rows.
2. Verify the meaning and treatment of `PROPOSAL_T` categories before modelling.
3. Define the analytical unit and feature space carefully.
4. Justify treatment of categorical variables and LOF distance calculations.
5. Avoid features that simply encode expected anomalies without methodological justification.

**Claim boundary:**
This stream can be used to study unusual infrastructure/administrative records and algorithmic anomaly patterns. It does **not** provide sufficient financial information to directly detect or establish fund misutilisation, fraud, or corruption.

**Decision:**
Proceed to preprocessing and feature engineering. The corrected dataset resolves the earlier dataset-size problem, while the remaining methodological limitations will be addressed during Phase 2.
