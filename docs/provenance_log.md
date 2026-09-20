# Project Provenance and Decision Ledger
# **Provenance and Decision Log**

**Project:** MPLAD Fund-Utilization Anomaly Pattern Detection Using Unsupervised Learning  
**Document Purpose:** To maintain a transparent record of substantive decisions, identified tensions, and scope qualifications arising during the project's design and execution phases.  
**Prepared for:** Project documentation appendix; review and audit trail.

# **1\. Initial project Conception and Inference**

The project was initially assigned by the university as an academic project, after which further interest in the problem domain led to its expansion into an unsupervised anomaly-detection study motivated by documented governance concerns in the Members of Parliament Local Area Development Scheme (MPLADS). Publicly available critiques—including Comptroller and Auditor General findings noting unsupported expenditure, poor monitoring, and suspected irregularities—established a prima facie case for exploring data-driven anomaly detection as a supplementary audit tool.&nbsp;

&nbsp;

The initial formulation posited three objectives: (a) data preparation and preprocessing, (b) application of Isolation Forest and Local Outlier Factor with comparative evaluation, and (c) assessment of detection consistency, false-positive implications, and ethical considerations.

# **2\. Data Source Selection — Rationale and Identified Limitations**

Selection rationale: No publicly available MPLAD-specific transactional dataset of sufficient granularity, completeness, and volume was identified at the time of project commencement. The ULB (Université Libre de Bruxelles) Credit Card Fraud Detection dataset, hosted on Kaggle, was selected as a methodological proxy on the following grounds:

&nbsp;

* Extreme class imbalance (492 positive instances in 284,807 total; 0.172% positive rate), approximating the rarity expected in fund misutilization scenarios.  
* Availability of binary labels enabling post-hoc, label-informed evaluation of unsupervised outputs.  
* Sufficient volume to support meaningful parameter sweeps and comparative analysis.

&nbsp;

**Limitations identified at selection and reaffirmed during execution:**

&nbsp;

| LIMITATION | DETAIL |
| :---- | :---- |
| Domain irrelevance of features | Features V1–V28 are PCA-transformed principal components with no semantic labels. The dataset providers explicitly state that original features cannot be disclosed due to confidentiality constraints. No feature corresponds to MPLAD-relevant constructs (scheme category, constituency, sanctioning authority, completion status, geographical identifiers). |
| Temporal insufficiency | The dataset covers two days (September 2013). MPLAD fund utilization operates across financial years and electoral cycles. No temporal validation or concept-drift analysis—both identified in the fraud-detection literature as critical for realistic evaluation—is possible. |
| Preprocessing triviality | The dataset contains no missing values and no categorical variables requiring encoding. Objective 1's preprocessing components (missing-value handling, categorical encoding) are therefore demonstrative rather than empirically necessary on this specific data. |
| Structural mismatch in anomaly topology | Credit card fraud anomalies are point-level transactional outliers. MPLAD anomalies are expected to manifest as project-level patterns (e.g., clustered incomplete works, concentration of sanctions to specific contractors, electoral-cycle-driven expenditure spikes). The two anomaly topologies are not equivalent. |
| Benchmark overuse | The ULB dataset is the single most widely used benchmark in credit card fraud detection literature, with numerous studies reporting near-perfect metrics. Results obtained on this dataset are well-characterized in the literature and carry limited incremental informational value. |

&nbsp;

Decision: The dataset was retained as a methodological proxy, but the project documentation was required to clearly state that no domain-valid conclusions regarding MPLAD fund utilization can be drawn from results obtained on this data.

# **3\. Methodological Choices — Assumptions and Constraints**

**Isolation Forest (iForest):**

&nbsp;

* Assumes anomalies are "few and different" and can be isolated with fewer random partitions than normal observations.  
* Known sensitivity to the contamination parameter; mis-specification directly alters the anomaly set.  
* Performance degrades when anomalies are clustered rather than scattered, and when the anomaly proportion exceeds the "few" assumption.  
* Stochastic by design; results may vary across runs, particularly with limited tree counts or small subsampling sizes.  
* More efficient than density-based methods at higher dimensions and larger sample sizes.

&nbsp;

**Local Outlier Factor (LOF):**

&nbsp;

* Identifies anomalies based on local density deviation from neighbours.  
* Sensitive to the neighbourhood parameter (k); different values can yield substantially different anomaly rankings.  
* Relies on distance-based density estimation, which is known to face degradation in high-dimensional spaces due to distance concentration effects, though this is partially mitigated here by the prior PCA reduction to 28 components.  
* Computationally more expensive than iForest at scale; does not scale as favourably with increasing observation count.

&nbsp;

**PCA Visualization:**

&nbsp;

* Applied for exploratory visualization of the detection output in reduced space.  
* Noted tension: the dataset's features are already PCA-transformed; applying PCA again for visualization serves a different purpose (dimensionality reduction for display) than the original transformation (anonymization), and this distinction must be disambiguated to avoid conflation.

&nbsp;

**Evaluation approach:**

&nbsp;

* Label-informed evaluation (using the Class variable) is employed to assess detector outputs. This is explicitly characterized as semi-supervised evaluation of unsupervised methods, not as purely unsupervised validation. The project does not claim unsupervised evaluation.

# **4\. Critical Reassessment — Points of Tension Identified**

During the course of the project, the following structural tensions were identified between the project's stated domain motivation and its actual executable scope:

&nbsp;

* The proxy-data–domain-claim gap: The project title references MPLAD fund utilization, but no MPLAD data is used. Any reader or reviewer examining the methodology would encounter this dissonance immediately. Continuing without acknowledgment would constitute overclaiming.  
* The preprocessing–reality gap: Objective 1's emphasis on missing-value handling and categorical encoding, while sound as pipeline design, is not exercised by the chosen dataset. Presenting these as challenges addressed would be inaccurate.  
* The "consistent anomaly pattern" claim: The stated outcome includes identifying "consistent anomaly patterns." On PCA-transformed, anonymized features, no pattern can be interpreted or mapped to any domain construct. The outcome claim requires qualification.  
* The unsupervised framing tension: Using labels for evaluation while describing the project as "unsupervised learning" requires precise terminological hygiene. The methods are unsupervised; the evaluation is not.  
* The false-positive implication gap: Discussing false-positive implications in the MPLAD context (e.g., wrongful flagging of constituencies, erosion of trust in audit processes) is ethically necessary but empirically hollow when the underlying data bears no relation to that context.

# **5\. Decisions Taken**

The following decisions were made in response to the identified tensions:

&nbsp;

| DECISION | RATIONALE |
| :---- | :---- |
| Retain the ULB dataset as primary benchmark but reframe its role explicitly as "methodological proxy for imbalanced anomaly detection," not as MPLAD data. | The dataset serves a legitimate benchmarking function. Removing it would leave no executable methodology. Reframing preserves honesty without discarding the analytical work. |
| Add a supplementary exploratory component using publicly available government expenditure data (state/district-level or any accessible public-fund dataset), subject to data availability at time of execution. | To demonstrate that the pipeline was tested beyond the proxy boundary, even if results are inconclusive. This converts the project from "proxy-only exercise" to "proxy benchmark with attempted domain transfer." |
| Reframe Objective 1 as pipeline scaffolding and reproducible methodology documentation, acknowledging that missing-value handling and categorical encoding are demonstrated procedurally rather than empirically driven by the proxy dataset. | Accuracy in claims. The preprocessing steps remain valid as reusable pipeline components for real MPLAD-style data. |
| Reframe the outcome from "identifying consistent anomaly patterns" to "identifying consistent detection behaviour across methods and parameter settings on a standardized imbalanced benchmark." | The former is unachievable on anonymized features; the latter is verifiable and honest. |
| Characterize evaluation as label-informed throughout all documentation. Use the term "unsupervised learning" strictly to describe the methods (iForest, LOF), not the evaluation protocol. | Terminological precision prevents the unsupervised/semi-supervised conflation. |
| Structure the limitations section as an engineering gap analysis directed at methods, data conditions, and deployment requirements—not at the assignment design. | A limitations section addressing what minimum data conditions, feature types, and temporal structures would be required for domain-valid deployment reads as professional maturity. A section addressing the assignment's design reads as grievance. The former serves the project; the latter does not. |
| Document this provenance log as part of the project submission. | Transparency. Any reviewer examining the project's decisions should have access to the reasoning trail, including acknowledged limitations and scope qualifications made before rather than after evaluation. |

# **6\. Scope of Claims — What This Study Can and Cannot Support**

**This study can support:**

&nbsp;

* Comparative characterization of Isolation Forest and LOF behaviour under extreme class imbalance on a standardized benchmark.  
* Parameter sensitivity analysis (contamination rate, tree count, neighbourhood size) and its effect on detection consistency.  
* A reproducible preprocessing and detection pipeline applicable to analogous imbalanced anomaly-detection tasks.  
* Identification of minimum data conditions (interpretable features, temporal scope, domain-relevant anomaly topology) required before unsupervised methods could be responsibly applied to MPLAD fund utilization data.

&nbsp;

**This study cannot support:**

&nbsp;

* Any claim about anomaly patterns in MPLAD fund utilization.  
* Any inference about the prevalence, nature, or distribution of irregularities in the MPLAD scheme.  
* Any recommendation for operational deployment of these methods in a public-fund auditing context without access to domain-appropriate data.  
* Generalization of detection rates or false-positive characteristics from the ULB benchmark to real MPLAD data, given the structural mismatches documented in Section 2\.

# **7\. Sources Informing This Log**

The following sources informed the identification of limitations and the framing of decisions documented above:

&nbsp;

* ULB Machine Learning Group. Credit Card Fraud Detection Dataset. Kaggle. — Dataset description, PCA transformation, feature anonymization, class distribution.  
* Impact Cyber Trust. Credit Card Fraud Detection — Dataset Entry. — Feature descriptions (V1–V28 as PCA components; Time and Amount untransformed).  
* OpenML. CreditCardFraudDetection (Dataset ID 42175). — Confirmation of dataset size, class balance, and provenance.  
* Fraud Detection Handbook (Chapter 2: Machine Learning for Credit Card Fraud Detection). — Concept drift, temporal validation requirements, near-real-time operational constraints in fraud detection systems.  
* Amazon Science. Fraud Dataset Benchmark (FDB). — Characterization of the ULB dataset as a two-day, PCA-transformed, anonymized benchmark; contextualization within broader fraud-detection dataset landscape.  
* Agyemang, E.F. et al. (2024). "Anomaly detection using unsupervised machine learning." Results in Engineering. — Comparative performance of Isolation Forest, One-Class SVM, and Robust Covariance; discussion of precision-recall trade-offs.  
* Alghushairy, O. et al. (2020). "A Review of Local Outlier Factor Algorithms for Numerical Data." — LOF limitations: high-dimensional degradation, sensitivity to neighborhood parameter, computational scaling.  
* mbrenndoerfer.com. "Isolation Forest: Anomaly Detection — Limitations." — iForest assumptions (few and different anomalies), instability with limited trees, difficulty with clustered or local anomalies.  
* Zimek, A. (2013). "Outlier Detection in High-Dimensional Data." PAKDD Tutorial. — Distance concentration effects and challenges for density-based methods in higher dimensions.  
* Observer Research Foundation. "MPLAD Scheme: Need to Work on Loopholes." — Governance concerns: poor utilization, inadequate monitoring, inadmissible works, suspected fraud.  
* Frontline (The Hindu). "The Case Against MPLADS." — CAG findings: Rs. 161 crore expenditure unsupported by documentation; 33.12% of sampled works with deficient execution records.  
* Ideas for India. "Electoral Cycles and Incomplete Public Works Projects: An Analysis of the MPLAD Scheme." — Structural patterns in MPLAD project completion driven by electoral timing.  
* Popova, I. (2025). Credit Card Fraud Detection (arXiv). — Identification of ULB dataset as the most widely used benchmark; discussion of class-imbalance handling approaches.  
* Preprints.org. "A Systematic Review of Machine Learning in Credit Card Fraud Detection" (2025). — Review of 52 studies on the ULB benchmark; ensemble methods' performance; noted lack of temporal validation in most benchmark usage.

&nbsp;

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
*Refer - notebooks/phase1_verification.ipynb*

### Stream B Update: PMGSY-III Dataset Accepted

**Date:** 2026-09-02
**Dataset:** PMGSY-III Geospatial Registry (`PMGSY_Master_Dataset_Combined(1).csv`)
**Source:** “Ministry of Rural Development, 2022. PMGSY Rural Connectivity Datasets, https://geosadak-pmgsy.nic.in/opendata/. Published under India’s Government Open Data License: https://data.gov.in/government-open-data-license-india”

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

*Refer - notebooks/phase1_verification_PMGSY.ipynb*
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
*Refer - notebooks/phase1_verification_PMGSY.ipynb*


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
