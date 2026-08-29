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