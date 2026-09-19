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

### Stream B Expansion and Final Compatibility Decision

**Date:** 2026-09-19

The PMGSY-III Stream B dataset was expanded from the original Bihar, Uttar Pradesh and Madhya Pradesh population to include Rajasthan, Maharashtra and Odisha. After exact-row deduplication, the resulting six-state working population contains **9,634 unique records**.

A stratified compatibility audit was performed separately for `P` and `L` records. The datasets share the substantive schema, but differences were observed in proposal-type composition, road-length distributions and temporal coverage. `CN_CODE` was found to be present and unique for `P` records but absent for `L` records; it was therefore treated as an identifier rather than a primary ML feature.

Adversarial validation was used to determine whether the added states could be distinguished from the core Bihar–UP–MP population. For `P` records, CORE-vs-ADDED AUC was **0.837** using `PROPOSED_L`, `IMS_BATCH` and `IMS_YEAR`, falling to **0.708** when `IMS_YEAR` was removed. For `L` records, AUC was **0.970**, falling to **0.850** without `IMS_YEAR`.

Further inspection showed that `IMS_BATCH` is strongly associated with `IMS_YEAR` and `PROPOSAL_T`, with batch composition varying substantially by state and cohort. This indicated that `IMS_BATCH` can act as a source/cohort indicator rather than a genuine infrastructure characteristic. Permutation importance supported this, particularly for `L` records, where `IMS_BATCH` was the dominant discriminator and `PROPOSED_L` provided no measurable separation.

A final adversarial test using only `PROPOSED_L` produced an AUC of **0.664** for `P` records and **0.500** for `L` records. This showed that, after excluding temporal and batch variables, the remaining cross-state shift in the `P` population was substantially lower. The `L` result also confirmed that `PROPOSED_L` contains no useful variation for that population.

**Final Decision:**
- The six-state PMGSY dataset is **accepted for Stream B**.
- `P` records will form the **primary combined ML population**.
- `L` records will be treated separately or descriptively and will not be mixed into the primary feature space.
- `IMS_BATCH` and raw `IMS_YEAR` will be excluded from the initial anomaly-detection feature space because they can encode temporal/cohort differences. They will remain available for EDA, stratified analysis and sensitivity testing.
- `MRL_ID`, `STATE_ID`, `LGD_STATE`, `LGD_DISTRI`, `DISTRICT_I`, `BLOCK_ID` and `CN_CODE` will be treated as identifiers/administrative reference fields rather than direct ML features unless later feature-engineering analysis provides a defensible reason to use them.
- No additional state will be added solely to exceed the supervisor's approximate **10,000–15,000 row** guideline.

The remaining cross-state distribution shift, particularly in `PROPOSED_L`, will be addressed during Phase 2 through EDA, feature engineering, preprocessing and feature-space validation rather than by discarding the expanded dataset.



## Phase 2 Initiation: Extended EDA and Provisional Data-Handling Approach

**Date:** 2026-09-19

Phase 2 begins with **extended exploratory data analysis (EDA) before final preprocessing and feature selection** for the PMGSY-III Stream B dataset.

The current six-state dataset and the earlier compatibility analysis provide a starting point, but the observations and decisions made so far are **provisional**. They may change, mature, or be revised as the structure and behaviour of the data become clearer through further EDA, investigation and analysis.

A particular concern is the presence of a large number of apparent duplicate records in the CSV representation. These will **not be assumed to be erroneous and removed automatically**. Since the source data originates from geospatial records, identical tabular attributes may not necessarily represent identical underlying spatial entities. Possible explanations include export duplication, repeated project/segment records, legitimate repeated observations, or loss of distinguishing information during conversion to tabular form.

Therefore, duplicate handling will be treated as an **investigative decision within Phase 2**, with possible outcomes including removal, aggregation, retention, or another justified treatment depending on the evidence.

The same principle will apply to other preprocessing decisions, including missing-value treatment, categorical encoding, temporal variables and feature selection. The objective is to understand the data first and allow the final feature space and preprocessing strategy to emerge from the evidence rather than imposing fixed assumptions in advance.

**Initial Phase 2 approach:**

`Raw/Current Data → Extended EDA → Structural Investigation → Feature Engineering Candidates → Feature-Space Audit → Final Preprocessing → Modelling`

No final preprocessing or feature-space decision is considered locked at the start of Phase 2.
