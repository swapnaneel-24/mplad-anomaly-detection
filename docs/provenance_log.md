# Project Provenance and Decision Ledger
# **Provenance and Decision Log**

**Project:** MPLAD Fund-Utilization Anomaly Pattern Detection Using Unsupervised Learning  
**Document Purpose:** To maintain a transparent record of substantive decisions, identified tensions, and scope qualifications arising during the project's design and execution phases.  
**Prepared for:** Project documentation appendix; review and audit trail.

# **1\. Initial project Conception and Inference**

The project was initially assigned by the university as an academic project, after which further interest in the problem domain led to its expansion into an unsupervised anomaly-detection study motivated by documented governance concerns in the Members of Parliament Local Area Development Scheme (MPLADS). Publicly available critiquesâ€”including Comptroller and Auditor General findings noting unsupported expenditure, poor monitoring, and suspected irregularitiesâ€”established a prima facie case for exploring data-driven anomaly detection as a supplementary audit tool.&nbsp;

The initial formulation posited three objectives: (a) data preparation and preprocessing, (b) application of Isolation Forest and Local Outlier Factor with comparative evaluation, and (c) assessment of detection consistency, false-positive implications, and ethical considerations.

# **2\. Data Source Selection Rationale and Identified Limitations**

Selection rationale: No publicly available MPLAD-specific transactional dataset of sufficient granularity, completeness, and volume was identified at the time of project commencement. The ULB (Université libre de Bruxelles) Credit Card Fraud Detection dataset, hosted on Kaggle, was selected as a methodological proxy on the following grounds:

* Extreme class imbalance (492 positive instances in 284,807 total; 0.172% positive rate), approximating the rarity expected in fund misutilization scenarios.  
* Availability of binary labels enabling post-hoc, label-informed evaluation of unsupervised outputs.  
* Sufficient volume to support meaningful parameter sweeps and comparative analysis.

**Limitations identified at selection and reaffirmed during execution:**

| LIMITATION | DETAIL |
| :---- | :---- |
| Domain irrelevance of features | Features V1â€“V28 are PCA-transformed principal components with no semantic labels. The dataset providers explicitly state that original features cannot be disclosed due to confidentiality constraints. No feature corresponds to MPLAD-relevant constructs (scheme category, constituency, sanctioning authority, completion status, geographical identifiers). |
| Temporal insufficiency | The dataset covers two days (September 2013). MPLAD fund utilization operates across financial years and electoral cycles. No temporal validation or concept-drift analysisâ€”both identified in the fraud-detection literature as critical for realistic evaluationâ€”is possible. |
| Preprocessing triviality | The dataset contains no missing values and no categorical variables requiring encoding. Objective 1's preprocessing components (missing-value handling, categorical encoding) are therefore demonstrative rather than empirically necessary on this specific data. |
| Structural mismatch in anomaly topology | Credit card fraud anomalies are point-level transactional outliers. MPLAD anomalies are expected to manifest as project-level patterns (e.g., clustered incomplete works, concentration of sanctions to specific contractors, electoral-cycle-driven expenditure spikes). The two anomaly topologies are not equivalent. |
| Benchmark overuse | The ULB dataset is the single most widely used benchmark in credit card fraud detection literature, with numerous studies reporting near-perfect metrics. Results obtained on this dataset are well-characterized in the literature and carry limited incremental informational value. |

Decision: The dataset was retained as a methodological proxy, but the project documentation was required to clearly state that no domain-valid conclusions regarding MPLAD fund utilization can be drawn from results obtained on this data.

# **3\. Methodological Choices Assumptions and Constraints**

**Isolation Forest (iForest):**

* Assumes anomalies are "few and different" and can be isolated with fewer random partitions than normal observations.  
* Known sensitivity to the contamination parameter; mis-specification directly alters the anomaly set.  
* Performance degrades when anomalies are clustered rather than scattered, and when the anomaly proportion exceeds the "few" assumption.  
* Stochastic by design; results may vary across runs, particularly with limited tree counts or small subsampling sizes.  
* More efficient than density-based methods at higher dimensions and larger sample sizes.

**Local Outlier Factor (LOF):**

* Identifies anomalies based on local density deviation from neighbours.  
* Sensitive to the neighbourhood parameter (k); different values can yield substantially different anomaly rankings.  
* Relies on distance-based density estimation, which is known to face degradation in high-dimensional spaces due to distance concentration effects, though this is partially mitigated here by the prior PCA reduction to 28 components.  
* Computationally more expensive than iForest at scale; does not scale as favourably with increasing observation count.

**PCA Visualization:**

* Applied for exploratory visualization of the detection output in reduced space.  
* Noted tension: the dataset's features are already PCA-transformed; applying PCA again for visualization serves a different purpose (dimensionality reduction for display) than the original transformation (anonymization), and this distinction must be disambiguated to avoid conflation.

**Evaluation approach:**

* Label-informed evaluation (using the Class variable) is employed to assess detector outputs. This is explicitly characterized as semi-supervised evaluation of unsupervised methods, not as purely unsupervised validation. The project does not claim unsupervised evaluation.

# **4\. Critical Reassessment Points of Tension Identified**

During the course of the project, the following structural tensions were identified between the project's stated domain motivation and its actual executable scope:

* The proxy-dataâ€“domain-claim gap: The project title references MPLAD fund utilization, but no MPLAD data is used. Any reader or reviewer examining the methodology would encounter this dissonance immediately. Continuing without acknowledgment would constitute overclaiming.  
* The preprocessingâ€“reality gap: Objective 1's emphasis on missing-value handling and categorical encoding, while sound as pipeline design, is not exercised by the chosen dataset. Presenting these as challenges addressed would be inaccurate.  
* The "consistent anomaly pattern" claim: The stated outcome includes identifying "consistent anomaly patterns." On PCA-transformed, anonymized features, no pattern can be interpreted or mapped to any domain construct. The outcome claim requires qualification.  
* The unsupervised framing tension: Using labels for evaluation while describing the project as "unsupervised learning" requires precise terminological hygiene. The methods are unsupervised; the evaluation is not.  
* The false-positive implication gap: Discussing false-positive implications in the MPLAD context (e.g., wrongful flagging of constituencies, erosion of trust in audit processes) is ethically necessary but empirically hollow when the underlying data bears no relation to that context.

# **5\. Decisions Taken**

The following decisions were made in response to the identified tensions:

| DECISION | RATIONALE |
| :---- | :---- |
| Retain the ULB dataset as primary benchmark but reframe its role explicitly as "methodological proxy for imbalanced anomaly detection," not as MPLAD data. | The dataset serves a legitimate benchmarking function. Removing it would leave no executable methodology. Reframing preserves honesty without discarding the analytical work. |
| Add a supplementary exploratory component using publicly available government expenditure data (state/district-level or any accessible public-fund dataset), subject to data availability at time of execution. | To demonstrate that the pipeline was tested beyond the proxy boundary, even if results are inconclusive. This converts the project from "proxy-only exercise" to "proxy benchmark with attempted domain transfer." |
| Reframe Objective 1 as pipeline scaffolding and reproducible methodology documentation, acknowledging that missing-value handling and categorical encoding are demonstrated procedurally rather than empirically driven by the proxy dataset. | Accuracy in claims. The preprocessing steps remain valid as reusable pipeline components for real MPLAD-style data. |
| Reframe the outcome from "identifying consistent anomaly patterns" to "identifying consistent detection behaviour across methods and parameter settings on a standardized imbalanced benchmark." | The former is unachievable on anonymized features; the latter is verifiable and honest. |
| Characterize evaluation as label-informed throughout all documentation. Use the term "unsupervised learning" strictly to describe the methods (iForest, LOF), not the evaluation protocol. | Terminological precision prevents the unsupervised/semi-supervised conflation. |
| Structure the limitations section as an engineering gap analysis directed at methods, data conditions, and deployment requirementsâ€”not at the assignment design. | A limitations section addressing what minimum data conditions, feature types, and temporal structures would be required for domain-valid deployment reads as professional maturity. A section addressing the assignment's design reads as grievance. The former serves the project; the latter does not. |
| Document this provenance log as part of the project submission. | Transparency. Any reviewer examining the project's decisions should have access to the reasoning trail, including acknowledged limitations and scope qualifications made before rather than after evaluation. |

# **6\. Scope of Claims What This Study Can and Cannot Support**

**This study can support:**

* Comparative characterization of Isolation Forest and LOF behaviour under extreme class imbalance on a standardized benchmark.  
* Parameter sensitivity analysis (contamination rate, tree count, neighbourhood size) and its effect on detection consistency.  
* A reproducible preprocessing and detection pipeline applicable to analogous imbalanced anomaly-detection tasks.  
* Identification of minimum data conditions (interpretable features, temporal scope, domain-relevant anomaly topology) required before unsupervised methods could be responsibly applied to MPLAD fund utilization data.

**This study cannot support:**

* Any claim about anomaly patterns in MPLAD fund utilization.  
* Any inference about the prevalence, nature, or distribution of irregularities in the MPLAD scheme.  
* Any recommendation for operational deployment of these methods in a public-fund auditing context without access to domain-appropriate data.  
* Generalization of detection rates or false-positive characteristics from the ULB benchmark to real MPLAD data, given the structural mismatches documented in Section 2\.

# **7\. Sources Informing This Log**

The following sources informed the identification of limitations and the framing of decisions documented above:

* ULB Machine Learning Group. Credit Card Fraud Detection Dataset. Kaggle. â€” Dataset description, PCA transformation, feature anonymization, class distribution.  
* Impact Cyber Trust. Credit Card Fraud Detection â€” Dataset Entry. â€” Feature descriptions (V1â€“V28 as PCA components; Time and Amount untransformed).  
* OpenML. CreditCardFraudDetection (Dataset ID 42175). â€” Confirmation of dataset size, class balance, and provenance.  
* Fraud Detection Handbook (Chapter 2: Machine Learning for Credit Card Fraud Detection). â€” Concept drift, temporal validation requirements, near-real-time operational constraints in fraud detection systems.  
* Amazon Science. Fraud Dataset Benchmark (FDB). â€” Characterization of the ULB dataset as a two-day, PCA-transformed, anonymized benchmark; contextualization within broader fraud-detection dataset landscape.  
* Agyemang, E.F. et al. (2024). "Anomaly detection using unsupervised machine learning." Results in Engineering. â€” Comparative performance of Isolation Forest, One-Class SVM, and Robust Covariance; discussion of precision-recall trade-offs.  
* Alghushairy, O. et al. (2020). "A Review of Local Outlier Factor Algorithms for Numerical Data." â€” LOF limitations: high-dimensional degradation, sensitivity to neighborhood parameter, computational scaling.  
* mbrenndoerfer.com. "Isolation Forest: Anomaly Detection â€” Limitations." â€” iForest assumptions (few and different anomalies), instability with limited trees, difficulty with clustered or local anomalies.  
* Zimek, A. (2013). "Outlier Detection in High-Dimensional Data." PAKDD Tutorial. â€” Distance concentration effects and challenges for density-based methods in higher dimensions.  
* Observer Research Foundation. "MPLAD Scheme: Need to Work on Loopholes." â€” Governance concerns: poor utilization, inadequate monitoring, inadmissible works, suspected fraud.  
* Frontline (The Hindu). "The Case Against MPLADS." â€” CAG findings: Rs. 161 crore expenditure unsupported by documentation; 33.12% of sampled works with deficient execution records.  
* Ideas for India. "Electoral Cycles and Incomplete Public Works Projects: An Analysis of the MPLAD Scheme." â€” Structural patterns in MPLAD project completion driven by electoral timing.  
* Popova, I. (2025). Credit Card Fraud Detection (arXiv). â€” Identification of ULB dataset as the most widely used benchmark; discussion of class-imbalance handling approaches.  
* Preprints.org. "A Systematic Review of Machine Learning in Credit Card Fraud Detection" (2025). â€” Review of 52 studies on the ULB benchmark; ensemble methods' performance; noted lack of temporal validation in most benchmark usage.

## Phase 1: Data Acquisition & Integrity Verification (Stream A)

- **Dataset Identifier:** `ULB_CC_Fraud_2013`
- **Source:** Kaggle (`mlg-ulb/creditcardfraud`)
- **Publishers:** Machine Learning Group (ULB) & Worldline
- **License:** Open Database License (ODbL) v1.0 / Database Contents License (DbCL) v1.0
- **Acquisition Date:** 2026-08-29

### Integrity Audit

- **Expected Dimensions:** 284,807 rows — 31 columns
- **Verified Dimensions:** 284,807 rows — 31 columns (`Passed`)
- **Class Breakdown:** 492 Fraud (0.172%), 284,315 Genuine (99.828%) (`Passed`)
- **Missing Values:** 0 (`Passed`)
- **Verification Script:** `notebooks/phase1_verification.ipynb`
- **SHA-256 Hash:** 76274b691b16a6c49d3f159c883398e03ccd6d1ee12d9d8ee38f4b4b98551a89  
*Refer - notebooks/phase1_verification.ipynb*

### Stream B Update: PMGSY-III Dataset Accepted

**Date:** 2026-09-02
**Dataset:** PMGSY-III Geospatial Registry (`PMGSY_Master_Dataset_Combined(1).csv`)
**Source:** Ministry of Rural Development, 2022. PMGSY Rural Connectivity Datasets, https://geosadak-pmgsy.nic.in/opendata/. Published under Indian Government Open Data License: https://data.gov.in/government-open-data-license-indiaâ€

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

Adversarial validation was used to determine whether the added states could be distinguished from the core Biharâ€“UPâ€“MP population. For `P` records, CORE-vs-ADDED AUC was **0.837** using `PROPOSED_L`, `IMS_BATCH` and `IMS_YEAR`, falling to **0.708** when `IMS_YEAR` was removed. For `L` records, AUC was **0.970**, falling to **0.850** without `IMS_YEAR`.

Further inspection showed that `IMS_BATCH` is strongly associated with `IMS_YEAR` and `PROPOSAL_T`, with batch composition varying substantially by state and cohort. This indicated that `IMS_BATCH` can act as a source/cohort indicator rather than a genuine infrastructure characteristic. Permutation importance supported this, particularly for `L` records, where `IMS_BATCH` was the dominant discriminator and `PROPOSED_L` provided no measurable separation.

A final adversarial test using only `PROPOSED_L` produced an AUC of **0.664** for `P` records and **0.500** for `L` records. This showed that, after excluding temporal and batch variables, the remaining cross-state shift in the `P` population was substantially lower. The `L` result also confirmed that `PROPOSED_L` contains no useful variation for that population.

**Final Decision:**
- The six-state PMGSY dataset is **accepted for Stream B**.
- `P` records will form the **primary combined ML population**.
- `L` records will be treated separately or descriptively and will not be mixed into the primary feature space.
- `IMS_BATCH` and raw `IMS_YEAR` will be excluded from the initial anomaly-detection feature space because they can encode temporal/cohort differences. They will remain available for EDA, stratified analysis and sensitivity testing.
- `MRL_ID`, `STATE_ID`, `LGD_STATE`, `LGD_DISTRI`, `DISTRICT_I`, `BLOCK_ID` and `CN_CODE` will be treated as identifiers/administrative reference fields rather than direct ML features unless later feature-engineering analysis provides a defensible reason to use them.
- No additional state will be added solely to exceed the supervisor's approximate **10,000â€“15,000 row** guideline.

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

`Raw/Current Data â†’ Extended EDA â†’ Structural Investigation â†’ Feature Engineering Candidates â†’ Feature-Space Audit â†’ Final Preprocessing â†’ Modelling`

No final preprocessing or feature-space decision is considered locked at the start of Phase 2.

---

# **STREAM A EXECUTION TRAIL - Phases 2 through 6 (ULB Proxy Benchmark)**

*This section documents the complete execution trail for Stream A, in chronological order, with all substantive decisions, identified tensions, bug discoveries, and methodology revisions. It is written to be auditable: a reviewer reading this section should be able to reconstruct why every design choice was made and what alternatives were rejected and why.*

## Phase 2 (Track A) - Initial Preprocessing and Scaling Decision

**Date:** 2026-10-21

### Initial Approach
The first preprocessing pass applied `RobustScaler` to `Time` and `Amount`, retained `V1`-`V28` untouched, and wrote a single output file `creditcard_preprocessed.csv` containing features and the `Class` label in one CSV.

### Diagnostics Driving the Scaling Choice
Pre-scaling diagnostics on `Amount`:

| Metric | Value |
| :--- | :--- |
| Mean | 88.35 |
| Median | 22.00 |
| Std | 250.12 |
| Max | 25,691.16 |
| Skewness | 16.98 |
| Kurtosis | 845.09 |
| IQR-outlier fraction (overall) | 11.20% |
| IQR-outlier fraction (legit, Class=0) | 11.19% |
| IQR-outlier fraction (fraud, Class=1) | 18.50% |

Decision: `RobustScaler` (median / IQR) chosen over `StandardScaler` (mean / std) for `Amount` on the grounds that mean/std would be inflated by extreme outliers and compress the inlier mass into a narrow band, destroying distance-based signal for downstream LOF. `Time` was scaled with `RobustScaler` for pipeline uniformity (its skewness was -0.0356, so the choice was mathematically neutral on that column). `V1`-`V28` left untouched: confirmed mean = 0.0, std approx 0.97, already PCA-transformed by the dataset curators.

### Tensions Identified at This Stage
1. **Label-in-CSV hazard:** Writing `Class` into the same CSV as the features set a trap for any downstream code that ingested the file blindly. A model pointed at this CSV could accidentally train on the target.
2. **Single-output-file opacity:** One "final" CSV did not document which feature transformations had been tried or why one was chosen. A reviewer could not reconstruct alternatives.
3. **No stable observation identifier:** No `row_id` existed. All downstream alignment relied on array position, which is fragile.

### Internal self critique (Review) and Redesign
An external review of the initial preprocessing pass produced three substantive critiques that were accepted:

1. **Mathematical redundancy in the planned FS-B variant.** Applying `RobustScaler` after `log1p` compresses the distribution twice; the variance-stabilising benefit of the log is partially washed out. Amended: FS-B uses `log1p(Amount)` followed by `StandardScaler` to provide a mathematically distinct contrast, not a redundant double-compression.
2. **Label-leakage hazard.** Amended: target isolated to a separate `ground_truth_registry.csv` containing only `row_id` and `Class`. Feature-space CSVs contain strictly features plus `row_id`.
3. **String-list concatenation syntax.** Minor: column lists consolidated into single variables for DRY.

### Final Phase 2 Outputs (Track A)
Two controlled feature-space variants produced, both leak-proof and `row_id`-tracked:

| Feature Space | Features | Amount Treatment | Time Treatment | Scaling | Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FS-A (Baseline)** | V1-V28, Time, Amount | None | None | RobustScaler on (Time, Amount) | Primary baseline (median/IQR) |
| **FS-B (Sensitivity)** | V1-V28, Time, Amount | log1p | None | StandardScaler on (Time, Amount) | Sensitivity (variance stabilisation) |

Companion artefacts: `ground_truth_registry.csv` (row_id, Class), `feature_space_manifest.md` documenting the variants.

### Decision
FS-A selected as the primary feature space for Phase 3. FS-B retained for sensitivity testing if Phase 3/4 results warrant it. The single-file `creditcard_preprocessed.csv` is **deprecated** and retained only as a historical record of the initial pass.

*Refer - `notebooks/phase2_trackA_preprocessing.ipynb`*

## Phase 3 (Track A) - Methodological Execution: First Attempt and Revision

**Date:** 2026-10-21 to 2026-10-22

### First Attempt (Deprecated)
The first Phase 3 pass ran a 5x3x2 grid for iForest (contamination x n_estimators x max_samples) and a 4x5x2 grid for LOF (n_neighbors x contamination x metric). The `contamination` parameter was passed directly to both models, allowing them to set the binary flag threshold internally. Outputs were stored as raw NumPy arrays keyed by run name; `row_id` was not stored alongside predictions.

**Critical bug discovered retrospectively in Phase 4:** The first attempt's LOF grid included both `'euclidean'` and `'minkowski'` metrics. Because scikit-learn's `minkowski` defaults to `p=2`, this is mathematically identical to `'euclidean'`. The grid was running the same computation twice. Amended in the revised run: alternative metric changed to `'manhattan'` (Minkowski with `p=1`).

### External Review (ChatGPT) and Methodological Restructuring
A second external review produced a structural critique that fundamentally reshaped Phase 3:

1. **`contamination` is a decision rule, not truth.** Passing `contamination` to the model conflates the detector (which produces a continuous anomaly score) with the decision rule (which thresholds that score into a binary flag). Phase 3 should produce scores; Phase 4 should apply thresholds.
2. **Phase 3 must not be label-informed.** Using `Class` to select the "best" configuration turns unsupervised detection into supervised model selection. Phase 3 should investigate parameter sensitivity and seed stability without consulting labels; Phase 4 may use labels to evaluate the resulting outputs.
3. **Every prediction must carry `row_id` and run metadata.** No array-position alignment downstream.

### Revised Phase 3 Design (Adopted)
- Both detectors fit on the frozen FS-A feature matrix only. No `Class` consulted during fitting.
- `contamination` removed from both model constructors. Both produce continuous anomaly scores.
- Explicit decision rule applied post-hoc: flag the bottom 1% of scores (exactly 300 flags per run on the 30k sample, 2,848 on the full dataset).
- Five iForest configurations: parameter sensitivity (n_estimators, max_samples) plus seed stability (random_state 42/43/44).
- Five LOF configurations: neighbourhood-scale sensitivity (k = 5, 15, 30, 50) plus metric sensitivity (manhattan at k=30).
- Every run stored as a canonical prediction record: `row_id`, continuous `score`, binary `flag`, plus a metadata row recording parameters, seed, runtime, threshold rule.
- Score direction canonicalised: `anomaly_score = -raw_score` so that higher = more anomalous for both detectors, eliminating per-method inversion ambiguity in Phase 4.

### Implementation Notes and Bug Fixes Accepted During Revision
Several implementation critiques were accepted during the revision. They are documented here for completeness, not because they altered the methodology:

| Critique | Resolution |
| :--- | :--- |
| `max_samples='auto'` is mathematically equal to 256 when n_samples > 256. | Amended: alternative value set to 0.05 (5% sub-sample). |
| Storing pandas DataFrames inside a prediction dictionary bloats memory. | Amended: raw NumPy arrays stored, with `uint8` flags and `float32` scores. |
| `del` of local array variables before all references resolved risks namespace confusion. | Amended: cleanup moved to loop boundary. |
| `n_jobs=-1` deadlocks joblib on Colab for LOF. | Amended: `n_jobs=2` (later `n_jobs=1` on full data). |
| `algorithm='auto'` for LOF silently selects `ball_tree` when D > 20; relying on this heuristic is opaque. | Amended: `algorithm='ball_tree', leaf_size=40` set explicitly. |

### Compute Constraint - Colab Free Tier
The revised Phase 3 was first executed on a 30,000-row random unsupervised subsample of FS-A. The sample was drawn without consulting `Class`. The same 30,000 `row_id`s were supplied to all 10 runs (5 iForest + 5 LOF).

LOF on the full 284,807-row matrix deadlocks the Colab free-tier CPU even with `ball_tree`, `n_jobs=1`, and `leaf_size=40`. A second pass on the full dataset was later completed using LOF **Novelty Mode** (`novelty=True`): LOF was fit on a 50,000-row random unsupervised subsample and used `score_samples` to predict anomaly scores for all 284,807 rows. This is a computational compromise with documented consequences (see Phase 4).

### Decision
The 30k subsample run is the **primary Phase 3 artefact** because LOF operates in native `fit_predict` mode there. The 284k full-dataset run is retained as a **scale-sensitivity companion artefact** with the LOF Novelty Mode limitation explicitly flagged. Both are documented; neither is silently dropped.

*Refer - `notebooks/phase3_trackA_modelling_30k.ipynb`, `notebooks/phase3_trackA_modelling_full.ipynb`*

## Phase 4 (Track A) - Label-Informed Validation: Bug Discovery and Correction

**Date:** 2026-10-22

### First Evaluation Run (Buggy)
The first Phase 4 evaluation produced catastrophic metrics: iForest ROC-AUC approx 0.50, AP matching the base fraud rate. The numbers indicated the models were no better than random.

### Root Cause
The Phase 3 predictions were stored in the order of the 30k random subsample. Phase 4 code extracted the matching `row_id`s from `ground_truth_registry.csv` and **sorted them** before merging with the unsorted prediction arrays. The labels were decoupled from the scores they were meant to evaluate. The models had not failed; the evaluation had silently shuffled the answer key.

### Correction
Predictions and ground truth merged into a single Pandas DataFrame on `row_id` as the join key. No array-position alignment permitted downstream. This is the same `row_id`-alignment discipline that the Phase 2 redesign introduced; the bug existed because the first Phase 4 code predated full adoption of that discipline.

### Corrected Phase 4 Results - 30k Sample (47 frauds, 1% threshold = 300 flags)

| Run | Model | Config | AP | ROC-AUC | Prec@1% | Rec@1% | F1@1% | TP |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| IF_003 | iForest | n_est=100, msamp=0.05, seed=42 | 0.3126 | 0.9803 | 0.1000 | 0.6383 | 0.1729 | 30 |
| IF_004 | iForest | n_est=100, msamp=256, seed=43 | 0.2094 | 0.9787 | 0.1067 | 0.6809 | 0.1844 | 32 |
| LOF_004 | LOF | k=50, euclidean | 0.3229 | 0.9536 | 0.1267 | 0.8085 | 0.2190 | 38 |
| LOF_001 | LOF | k=5, euclidean | 0.0024 | 0.5220 | 0.0033 | 0.0213 | 0.0058 | 1 |

(Full 10-run table retained in `phase4_validation_metrics_CORRECTED.csv`.)

### Corrected Phase 4 Results - Full 284k Dataset (492 frauds, 1% threshold = 2,848 flags)

| Run | Model | AP | ROC-AUC | Prec@1% | Rec@1% | F1@1% | TP |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| IF_003 | iForest | 0.2340 | 0.9494 | 0.1113 | 0.6443 | 0.1898 | 317 |
| LOF_004 | LOF (Novelty) | 0.0562 | 0.9070 | 0.0586 | 0.3394 | 0.1000 | 167 |

(Full 10-run table retained in `FULL_phase4_metrics.csv`.)

### Key Findings
1. **iForest is scale-invariant.** Recall on 30k = 63.8%; recall on 284k = 64.4%. AP drops modestly (0.31 to 0.23) but ranking quality remains high. iForest's tree-based isolation paths do not degrade with sample size.
2. **LOF degrades under Novelty Mode.** Recall on 30k native `fit_predict` = 80.9%; recall on 284k Novelty Mode = 33.9%. The 50k density map cannot capture the micro-density fluctuations of the full 284k space. This is the cost of the compute compromise, not a property of the algorithm itself.
3. **LOF neighbourhood-scale sensitivity is dramatic.** On the 30k sample: k=5 -> AP 0.0024, k=50 -> AP 0.3229. The choice of `n_neighbors` is not a tuning detail; it determines whether LOF is useful at all on this data.
4. **iForest flags are 100% false positives when LOF disagrees.** On the 30k sample at 1%: iForest-only flags = 193 observations, 0 frauds. LOF-only flags = 193 observations, 8 frauds. Both-methods flags = 107 observations, 30 frauds (28.0% precision vs 0.16% base rate).

### Decision
Both 30k and 284k results retained as complementary evidence. The 30k run is the methodologically cleaner artefact (native LOF); the 284k run is the scale-stress artefact (LOF Novelty Mode compromise). Neither is silently discarded.

*Refer - `notebooks/phase4_trackA_validation_30k.ipynb`, `notebooks/phase4_trackA_validation_full.ipynb`*

## Phase 5 (Track A) - Diagnostic Analysis and Visualization

**Date:** 2026-10-22 to 2026-10-23

### Scope
Phase 5 was treated as **visualization + quantitative diagnostic analysis**, not a cosmetic plotting exercise. All computations consumed the canonical Phase 3/4 artefacts; no models were refit.

### Quantitative Diagnostics Computed

1. **Stratified bootstrap confidence intervals (2,000 replicates).** Performed for IF_003, IF_004, LOF_004 on AP, ROC-AUC, Precision@1%, Recall@1%, F1@1%. Fraud and legitimate rows resampled separately to preserve imbalance. Example: LOF_004 Recall@1% 95% CI on 30k = [0.6809, 0.9149]; IF_003 = [0.5106, 0.7872]. LOF's worst-case recall exceeds IF's best-case recall, supporting the claim that LOF_004's superiority at 1% is statistically meaningful, not a point-estimate artefact.

2. **Exact hypergeometric overlap test.** Expected random overlap at 1%: 3.0 (30k), 28.48 (284k). Observed: 107 (30k), 457 (284k). Enrichment: 35.67x (30k), 16.05x (284k). P-value reported via `logsf` to avoid underflow: p < 10^-140.30 (30k), p < 10^-396.37 (284k). The consensus overlap is not a chance event.

3. **10x10 pairwise score-correlation matrix (Spearman).** IF<->IF Spearman approx 0.93; LOF<->LOF Spearman varies with k; IF<->LOF Spearman approx 0.37. The two methods produce substantially different anomaly rankings.

4. **10x10 pairwise top-1% Jaccard matrix.** Visualises intra-method stability vs inter-method disagreement in one compact figure.

5. **Multi-threshold agreement analysis.** At 0.1%, 0.2%, 0.5%, 1%, 2%, 5% top-k. At 0.1% on 30k: iForest-only captures 11 unique frauds, LOF-only captures 10, both capture 3. At 1%: iForest-only captures 0, LOF-only captures 8. iForest dominates at the extreme edge; LOF dominates as the budget expands. This is the most informative single table in the project.

6. **PCA explained variance.** PC1 + PC2 capture a modest fraction of total variance (documented in plot captions). All PCA visualisations are explicitly labelled as lossy projections, not as faithful geometry.

### Visualizations Produced
Eight diagnostic figures produced for each of 30k and 284k runs (16 total), saved as high-resolution PNGs:

1. Precision-Recall curves (5 IF + 5 LOF, best runs highlighted)
2. Fraud discovery curve (recall vs review budget) + precision vs budget
3. Hypergeometric null distribution with observed overlap marked
4. 10x10 Spearman correlation heatmap
5. 10x10 top-1% Jaccard heatmap
6. Top-k Jaccard curve (0.1% to 5%)
7. Rank-vs-rank scatter (IF percentile vs LOF percentile, agreement groups highlighted)
8. PCA agreement map (Both / IF-only / LOF-only / Neither, with flagged-only overlay)

### Decision
Phase 5 closed. No additional visualisations or computations will be added unless Phase 7 gap analysis identifies a specific need.

*Refer - `notebooks/phase5_trackA_diagnostics_30k.ipynb`, `notebooks/phase5_trackA_diagnostics_full.ipynb`*

## Phase 6 (Track A) - Cross-Method Consistency Analysis

**Date:** 2026-10-23

### Scope
Phase 6 investigated whether iForest and LOF identify the same observations or different forms of unusualness, and whether their agreement is greater than chance.

### Primary Findings (30k sample, IF_003 vs LOF_004)

| Metric | Value | Interpretation |
| :--- | :--- | :--- |
| Spearman rank correlation (IF vs LOF) | 0.37 | Substantially different rankings; positive but far from agreement |
| Top-1% Jaccard | 0.2170 | ~22% of flagged items overlap |
| Top-0.5% Jaccard (peak) | ~0.27 | Agreement strongest at the extreme edge |
| Expected random overlap | 3.0 | - |
| Observed overlap | 107 | 35.67x enrichment |
| Hypergeometric p-value | < 10^-140 | Overlap is not chance |

### Agreement-Group Composition (30k, 1% threshold)

| Group | Count | Fraud | Fraud % | Recall Contribution |
| :--- | :--- | :--- | :--- | :--- |
| Both | 107 | 30 | 28.04% | 63.83% |
| iForest-only | 193 | 0 | 0.00% | 0.00% |
| LOF-only | 193 | 8 | 4.15% | 17.02% |
| Neither | 29,507 | 9 | 0.03% | 19.15% |

### Five Questions Answered (per the Phase 6 framework)

1. **Are the two methods producing similar anomaly rankings?** No. Spearman approx 0.37 confirms substantially different rankings, consistent with their different detection mechanisms.
2. **How much do their highest-ranked observations overlap?** Modestly. Jaccard peaks at ~0.27 (top 0.5%) and declines as k increases.
3. **Is the overlap greater than expected by chance?** Yes, overwhelmingly. 35.67x enrichment on 30k, 16.05x on 284k, with p-values so extreme they require `logsf` to express.
4. **When they disagree, which method-specific groups contain the known frauds?** On 30k: iForest-only = 0 frauds (100% false positives); LOF-only = 8 frauds; Both = 30 frauds (28% precision). The intersection is the highest-precision group.
5. **Is the disagreement caused by fundamentally different anomaly definitions, or by LOF's neighbourhood-scale sensitivity?** Both. LOF's k-sensitivity is dramatic (AP ranges from 0.0024 at k=5 to 0.3229 at k=50 on 30k). Even at the best k, however, the IF<->LOF Spearman remains ~0.37, indicating the methods respond to different geometric properties of the data, not merely to different scale parameters.

### Interpretive Discipline Applied
Per external review: the finding supports "the two methods identify substantially different high-anomaly populations, consistent with their different detection mechanisms." It does **not** support the stronger mechanistic claim that "LOF catches local-density anomalies invisible to iForest's isolation paths." The latter is an interpretation of why the algorithms disagree, not something the overlap experiment directly establishes.

Similarly: "the consensus group had approximately 179x the sample's baseline fraud prevalence" is defensible. "The consensus detector is 179x more accurate" is not, and is not claimed.

### Decision
Phase 6 closed. No score fusion or ensemble construction attempted. Per framework guidance, understanding *why* the methods disagree precedes any attempt to combine them.

*Refer - `notebooks/phase6_trackA_consistency.ipynb`*

## Phase 6a (Track A) - 30k vs 284k Comparison

**Date:** 2026-10-23

### Purpose
To document the effect of the LOF Novelty Mode compute compromise by comparing the 30k native-LOF run against the 284k Novelty-LOF run on identical configurations.

### Headline Comparison

| Run | Metric | 30k (native LOF) | 284k (LOF Novelty) |
| :--- | :--- | :--- | :--- |
| IF_003 | AP | 0.3126 | 0.2340 |
| IF_003 | Recall@1% | 0.6383 | 0.6443 |
| LOF_004 | AP | 0.3229 | 0.0562 |
| LOF_004 | Recall@1% | 0.8085 | 0.3394 |
| Consensus | Observed overlap | 107 | 457 |
| Consensus | Enrichment vs random | 35.67x | 16.05x |

### Findings
1. **iForest is scale-robust.** Recall essentially identical (63.8% to 64.4%). AP drops modestly. The algorithm's tree-based isolation does not depend on native density estimation over the full sample.
2. **LOF degrades sharply under Novelty Mode.** AP drops 5.7x, recall drops 2.4x. The 50k density map learned by LOF in Novelty Mode cannot represent the micro-density structure of the full 284k space. This is the cost of the Colab compute constraint, not a property of LOF on this data.
3. **Consensus enrichment dilutes with scale but remains extreme.** 35.67x to 16.05x. Expected random overlap grows quadratically with k; observed overlap grows sub-quadratically. The consensus signal remains overwhelmingly non-random (p < 10^-396 on 284k).

### Decision
The 30k run remains the **primary methodological artefact** for LOF characterization. The 284k run is the **scale-stress companion**. Both are reported; the LOF Novelty Mode limitation is documented in Phase 7.

## Current Status (as of 2026-10-23)

### Stream A - COMPLETE (Phases 1-6)
- Phase 1: Data acquired and verified. (Done)
- Phase 2: Two feature-space variants produced (FS-A primary, FS-B sensitivity). (Done)
- Phase 3: 10 runs (5 iForest + 5 LOF) on 30k sample; 10 runs on 284k full dataset (LOF Novelty Mode). (Done)
- Phase 4: Label-informed validation on both 30k and 284k. Alignment bug discovered and corrected. (Done)
- Phase 5: Bootstrap CIs, hypergeometric test, 10x10 matrices, multi-threshold analysis, 8 diagnostic plots per scale. (Done)
- Phase 6: Cross-method consistency analysis with five-question framework answered. (Done)

### Stream B - Phase 1 COMPLETE, Phase 2 IN PROGRESS
- Phase 1: PMGSY-III six-state dataset accepted (9,634 unique records after dedup). Adversarial validation performed. (Done)
- Phase 2: Extended EDA initiated. Provisional data-handling approach documented. In progress.

### Phases 7 and 8 - NOT YET STARTED
- Phase 7 (Limitations, Gap Analysis, Domain Transfer Conditions): to be drafted after Stream B Phase 2-6 completion, or as a single-stream gap analysis if Stream B proves non-viable.
- Phase 8 (Documentation, Reproducibility, Provenance Finalization): this log is the living draft of that phase.

### Outstanding Tensions to Resolve
1. The LOF Novelty Mode compromise on 284k is methodologically defensible but limits the strength of full-scale LOF claims. The 30k native-LOF run is the cleaner artefact and should be the primary citation for LOF behaviour.
2. The first Phase 4 alignment bug, while corrected, is a documented instance of the kind of array-position fragility the Phase 2 `row_id` redesign was meant to prevent. It is retained in this log as evidence that the redesign was necessary, not optional.
3. Stream B (PMGSY-III) has no labels. Phase 4 for Stream B will be score-distribution + manual top-N inspection only. This is anticipated by the framework but lowers the analytical ceiling for that stream.
4. The scope claim for Stream B is "pipeline reusability demonstration," not "domain anomaly findings." This must be respected in Phase 7 to avoid overclaiming.

---

*End of Stream A execution trail. Stream B execution trail will be appended as Phase 2 progresses.*

---

# Project Provenance and Decision Ledger
# **Provenance and Decision Log**

**Project:** MPLAD Fund-Utilization Anomaly Pattern Detection Using Unsupervised Learning  
**Document Purpose:** To maintain a transparent record of substantive decisions, identified tensions, and scope qualifications arising during the project's design and execution phases.  
**Prepared for:** Project documentation appendix; review and audit trail.

# **1\. Initial project Conception and Inference**

The project was initially assigned by the university as an academic project, after which further interest in the problem domain led to its expansion into an unsupervised anomaly-detection study motivated by documented governance concerns in the Members of Parliament Local Area Development Scheme (MPLADS). Publicly available critiquesâ€”including Comptroller and Auditor General findings noting unsupported expenditure, poor monitoring, and suspected irregularitiesâ€”established a prima facie case for exploring data-driven anomaly detection as a supplementary audit tool.&nbsp;

The initial formulation posited three objectives: (a) data preparation and preprocessing, (b) application of Isolation Forest and Local Outlier Factor with comparative evaluation, and (c) assessment of detection consistency, false-positive implications, and ethical considerations.

# **2\. Data Source Selection â€” Rationale and Identified Limitations**

Selection rationale: No publicly available MPLAD-specific transactional dataset of sufficient granularity, completeness, and volume was identified at the time of project commencement. The ULB (UniversitÃ© Libre de Bruxelles) Credit Card Fraud Detection dataset, hosted on Kaggle, was selected as a methodological proxy on the following grounds:

* Extreme class imbalance (492 positive instances in 284,807 total; 0.172% positive rate), approximating the rarity expected in fund misutilization scenarios.  
* Availability of binary labels enabling post-hoc, label-informed evaluation of unsupervised outputs.  
* Sufficient volume to support meaningful parameter sweeps and comparative analysis.

**Limitations identified at selection and reaffirmed during execution:**

| LIMITATION | DETAIL |
| :---- | :---- |
| Domain irrelevance of features | Features V1â€“V28 are PCA-transformed principal components with no semantic labels. The dataset providers explicitly state that original features cannot be disclosed due to confidentiality constraints. No feature corresponds to MPLAD-relevant constructs (scheme category, constituency, sanctioning authority, completion status, geographical identifiers). |
| Temporal insufficiency | The dataset covers two days (September 2013). MPLAD fund utilization operates across financial years and electoral cycles. No temporal validation or concept-drift analysisâ€”both identified in the fraud-detection literature as critical for realistic evaluationâ€”is possible. |
| Preprocessing triviality | The dataset contains no missing values and no categorical variables requiring encoding. Objective 1's preprocessing components (missing-value handling, categorical encoding) are therefore demonstrative rather than empirically necessary on this specific data. |
| Structural mismatch in anomaly topology | Credit card fraud anomalies are point-level transactional outliers. MPLAD anomalies are expected to manifest as project-level patterns (e.g., clustered incomplete works, concentration of sanctions to specific contractors, electoral-cycle-driven expenditure spikes). The two anomaly topologies are not equivalent. |
| Benchmark overuse | The ULB dataset is the single most widely used benchmark in credit card fraud detection literature, with numerous studies reporting near-perfect metrics. Results obtained on this dataset are well-characterized in the literature and carry limited incremental informational value. |

Decision: The dataset was retained as a methodological proxy, but the project documentation was required to clearly state that no domain-valid conclusions regarding MPLAD fund utilization can be drawn from results obtained on this data.

# **3\. Methodological Choices â€” Assumptions and Constraints**

**Isolation Forest (iForest):**

* Assumes anomalies are "few and different" and can be isolated with fewer random partitions than normal observations.  
* Known sensitivity to the contamination parameter; mis-specification directly alters the anomaly set.  
* Performance degrades when anomalies are clustered rather than scattered, and when the anomaly proportion exceeds the "few" assumption.  
* Stochastic by design; results may vary across runs, particularly with limited tree counts or small subsampling sizes.  
* More efficient than density-based methods at higher dimensions and larger sample sizes.

**Local Outlier Factor (LOF):**

* Identifies anomalies based on local density deviation from neighbours.  
* Sensitive to the neighbourhood parameter (k); different values can yield substantially different anomaly rankings.  
* Relies on distance-based density estimation, which is known to face degradation in high-dimensional spaces due to distance concentration effects, though this is partially mitigated here by the prior PCA reduction to 28 components.  
* Computationally more expensive than iForest at scale; does not scale as favourably with increasing observation count.

**PCA Visualization:**

* Applied for exploratory visualization of the detection output in reduced space.  
* Noted tension: the dataset's features are already PCA-transformed; applying PCA again for visualization serves a different purpose (dimensionality reduction for display) than the original transformation (anonymization), and this distinction must be disambiguated to avoid conflation.

**Evaluation approach:**

* Label-informed evaluation (using the Class variable) is employed to assess detector outputs. This is explicitly characterized as semi-supervised evaluation of unsupervised methods, not as purely unsupervised validation. The project does not claim unsupervised evaluation.

# **4\. Critical Reassessment â€” Points of Tension Identified**

During the course of the project, the following structural tensions were identified between the project's stated domain motivation and its actual executable scope:

* The proxy-dataâ€“domain-claim gap: The project title references MPLAD fund utilization, but no MPLAD data is used. Any reader or reviewer examining the methodology would encounter this dissonance immediately. Continuing without acknowledgment would constitute overclaiming.  
* The preprocessingâ€“reality gap: Objective 1's emphasis on missing-value handling and categorical encoding, while sound as pipeline design, is not exercised by the chosen dataset. Presenting these as challenges addressed would be inaccurate.  
* The "consistent anomaly pattern" claim: The stated outcome includes identifying "consistent anomaly patterns." On PCA-transformed, anonymized features, no pattern can be interpreted or mapped to any domain construct. The outcome claim requires qualification.  
* The unsupervised framing tension: Using labels for evaluation while describing the project as "unsupervised learning" requires precise terminological hygiene. The methods are unsupervised; the evaluation is not.  
* The false-positive implication gap: Discussing false-positive implications in the MPLAD context (e.g., wrongful flagging of constituencies, erosion of trust in audit processes) is ethically necessary but empirically hollow when the underlying data bears no relation to that context.

# **5\. Decisions Taken**

The following decisions were made in response to the identified tensions:

| DECISION | RATIONALE |
| :---- | :---- |
| Retain the ULB dataset as primary benchmark but reframe its role explicitly as "methodological proxy for imbalanced anomaly detection," not as MPLAD data. | The dataset serves a legitimate benchmarking function. Removing it would leave no executable methodology. Reframing preserves honesty without discarding the analytical work. |
| Add a supplementary exploratory component using publicly available government expenditure data (state/district-level or any accessible public-fund dataset), subject to data availability at time of execution. | To demonstrate that the pipeline was tested beyond the proxy boundary, even if results are inconclusive. This converts the project from "proxy-only exercise" to "proxy benchmark with attempted domain transfer." |
| Reframe Objective 1 as pipeline scaffolding and reproducible methodology documentation, acknowledging that missing-value handling and categorical encoding are demonstrated procedurally rather than empirically driven by the proxy dataset. | Accuracy in claims. The preprocessing steps remain valid as reusable pipeline components for real MPLAD-style data. |
| Reframe the outcome from "identifying consistent anomaly patterns" to "identifying consistent detection behaviour across methods and parameter settings on a standardized imbalanced benchmark." | The former is unachievable on anonymized features; the latter is verifiable and honest. |
| Characterize evaluation as label-informed throughout all documentation. Use the term "unsupervised learning" strictly to describe the methods (iForest, LOF), not the evaluation protocol. | Terminological precision prevents the unsupervised/semi-supervised conflation. |
| Structure the limitations section as an engineering gap analysis directed at methods, data conditions, and deployment requirementsâ€”not at the assignment design. | A limitations section addressing what minimum data conditions, feature types, and temporal structures would be required for domain-valid deployment reads as professional maturity. A section addressing the assignment's design reads as grievance. The former serves the project; the latter does not. |
| Document this provenance log as part of the project submission. | Transparency. Any reviewer examining the project's decisions should have access to the reasoning trail, including acknowledged limitations and scope qualifications made before rather than after evaluation. |

# **6\. Scope of Claims â€” What This Study Can and Cannot Support**

**This study can support:**

* Comparative characterization of Isolation Forest and LOF behaviour under extreme class imbalance on a standardized benchmark.  
* Parameter sensitivity analysis (contamination rate, tree count, neighbourhood size) and its effect on detection consistency.  
* A reproducible preprocessing and detection pipeline applicable to analogous imbalanced anomaly-detection tasks.  
* Identification of minimum data conditions (interpretable features, temporal scope, domain-relevant anomaly topology) required before unsupervised methods could be responsibly applied to MPLAD fund utilization data.

**This study cannot support:**

* Any claim about anomaly patterns in MPLAD fund utilization.  
* Any inference about the prevalence, nature, or distribution of irregularities in the MPLAD scheme.  
* Any recommendation for operational deployment of these methods in a public-fund auditing context without access to domain-appropriate data.  
* Generalization of detection rates or false-positive characteristics from the ULB benchmark to real MPLAD data, given the structural mismatches documented in Section 2\.

# **7\. Sources Informing This Log**

The following sources informed the identification of limitations and the framing of decisions documented above:

* ULB Machine Learning Group. Credit Card Fraud Detection Dataset. Kaggle. â€” Dataset description, PCA transformation, feature anonymization, class distribution.  
* Impact Cyber Trust. Credit Card Fraud Detection â€” Dataset Entry. â€” Feature descriptions (V1â€“V28 as PCA components; Time and Amount untransformed).  
* OpenML. CreditCardFraudDetection (Dataset ID 42175). â€” Confirmation of dataset size, class balance, and provenance.  
* Fraud Detection Handbook (Chapter 2: Machine Learning for Credit Card Fraud Detection). â€” Concept drift, temporal validation requirements, near-real-time operational constraints in fraud detection systems.  
* Amazon Science. Fraud Dataset Benchmark (FDB). â€” Characterization of the ULB dataset as a two-day, PCA-transformed, anonymized benchmark; contextualization within broader fraud-detection dataset landscape.  
* Agyemang, E.F. et al. (2024). "Anomaly detection using unsupervised machine learning." Results in Engineering. â€” Comparative performance of Isolation Forest, One-Class SVM, and Robust Covariance; discussion of precision-recall trade-offs.  
* Alghushairy, O. et al. (2020). "A Review of Local Outlier Factor Algorithms for Numerical Data." â€” LOF limitations: high-dimensional degradation, sensitivity to neighborhood parameter, computational scaling.  
* mbrenndoerfer.com. "Isolation Forest: Anomaly Detection â€” Limitations." â€” iForest assumptions (few and different anomalies), instability with limited trees, difficulty with clustered or local anomalies.  
* Zimek, A. (2013). "Outlier Detection in High-Dimensional Data." PAKDD Tutorial. â€” Distance concentration effects and challenges for density-based methods in higher dimensions.  
* Observer Research Foundation. "MPLAD Scheme: Need to Work on Loopholes." â€” Governance concerns: poor utilization, inadequate monitoring, inadmissible works, suspected fraud.  
* Frontline (The Hindu). "The Case Against MPLADS." â€” CAG findings: Rs. 161 crore expenditure unsupported by documentation; 33.12% of sampled works with deficient execution records.  
* Ideas for India. "Electoral Cycles and Incomplete Public Works Projects: An Analysis of the MPLAD Scheme." â€” Structural patterns in MPLAD project completion driven by electoral timing.  
* Popova, I. (2025). Credit Card Fraud Detection (arXiv). â€” Identification of ULB dataset as the most widely used benchmark; discussion of class-imbalance handling approaches.  
* Preprints.org. "A Systematic Review of Machine Learning in Credit Card Fraud Detection" (2025). â€” Review of 52 studies on the ULB benchmark; ensemble methods' performance; noted lack of temporal validation in most benchmark usage.

## Phase 1: Data Acquisition & Integrity Verification (Stream A)

- **Dataset Identifier:** `ULB_CC_Fraud_2013`
- **Source:** Kaggle (`mlg-ulb/creditcardfraud`)
- **Publishers:** Machine Learning Group (ULB) & Worldline
- **License:** Open Database License (ODbL) v1.0 / Database Contents License (DbCL) v1.0
- **Acquisition Date:** 2026-08-29

### Integrity Audit
- **Expected Dimensions:** 284,807 rows Ã— 31 columns
- **Verified Dimensions:** 284,807 rows Ã— 31 columns (`Passed`)
- **Class Breakdown:** 492 Fraud (0.172%), 284,315 Genuine (99.828%) (`Passed`)
- **Missing Values:** 0 (`Passed`)
- **Verification Script:** `notebooks/phase1_verification.ipynb`
- **SHA-256 Hash:** 76274b691b16a6c49d3f159c883398e03ccd6d1ee12d9d8ee38f4b4b98551a89
*Refer - notebooks/phase1_verification.ipynb*

### Stream B Update: PMGSY-III Dataset Accepted

**Date:** 2026-09-02
**Dataset:** PMGSY-III Geospatial Registry (`PMGSY_Master_Dataset_Combined(1).csv`)
**Source:** â€œMinistry of Rural Development, 2022. PMGSY Rural Connectivity Datasets, https://geosadak-pmgsy.nic.in/opendata/. Published under Indiaâ€™s Government Open Data License: https://data.gov.in/government-open-data-license-indiaâ€

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

Adversarial validation was used to determine whether the added states could be distinguished from the core Biharâ€“UPâ€“MP population. For `P` records, CORE-vs-ADDED AUC was **0.837** using `PROPOSED_L`, `IMS_BATCH` and `IMS_YEAR`, falling to **0.708** when `IMS_YEAR` was removed. For `L` records, AUC was **0.970**, falling to **0.850** without `IMS_YEAR`.

Further inspection showed that `IMS_BATCH` is strongly associated with `IMS_YEAR` and `PROPOSAL_T`, with batch composition varying substantially by state and cohort. This indicated that `IMS_BATCH` can act as a source/cohort indicator rather than a genuine infrastructure characteristic. Permutation importance supported this, particularly for `L` records, where `IMS_BATCH` was the dominant discriminator and `PROPOSED_L` provided no measurable separation.

A final adversarial test using only `PROPOSED_L` produced an AUC of **0.664** for `P` records and **0.500** for `L` records. This showed that, after excluding temporal and batch variables, the remaining cross-state shift in the `P` population was substantially lower. The `L` result also confirmed that `PROPOSED_L` contains no useful variation for that population.

**Final Decision:**
- The six-state PMGSY dataset is **accepted for Stream B**.
- `P` records will form the **primary combined ML population**.
- `L` records will be treated separately or descriptively and will not be mixed into the primary feature space.
- `IMS_BATCH` and raw `IMS_YEAR` will be excluded from the initial anomaly-detection feature space because they can encode temporal/cohort differences. They will remain available for EDA, stratified analysis and sensitivity testing.
- `MRL_ID`, `STATE_ID`, `LGD_STATE`, `LGD_DISTRI`, `DISTRICT_I`, `BLOCK_ID` and `CN_CODE` will be treated as identifiers/administrative reference fields rather than direct ML features unless later feature-engineering analysis provides a defensible reason to use them.
- No additional state will be added solely to exceed the supervisor's approximate **10,000â€“15,000 row** guideline.

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

`Raw/Current Data â†’ Extended EDA â†’ Structural Investigation â†’ Feature Engineering Candidates â†’ Feature-Space Audit â†’ Final Preprocessing â†’ Modelling`

No final preprocessing or feature-space decision is considered locked at the start of Phase 2.

---

# **STREAM A EXECUTION TRAIL - Phases 2 through 6 (ULB Proxy Benchmark)**

*This section documents the complete execution trail for Stream A, in chronological order, with all substantive decisions, identified tensions, bug discoveries, and methodology revisions. It is written to be auditable: a reviewer reading this section should be able to reconstruct why every design choice was made and what alternatives were rejected and why.*

## Phase 2 (Track A) - Initial Preprocessing and Scaling Decision

**Date:** 2026-10-21

### Initial Approach
The first preprocessing pass applied `RobustScaler` to `Time` and `Amount`, retained `V1`-`V28` untouched, and wrote a single output file `creditcard_preprocessed.csv` containing features and the `Class` label in one CSV.

### Diagnostics Driving the Scaling Choice
Pre-scaling diagnostics on `Amount`:

| Metric | Value |
| :--- | :--- |
| Mean | 88.35 |
| Median | 22.00 |
| Std | 250.12 |
| Max | 25,691.16 |
| Skewness | 16.98 |
| Kurtosis | 845.09 |
| IQR-outlier fraction (overall) | 11.20% |
| IQR-outlier fraction (legit, Class=0) | 11.19% |
| IQR-outlier fraction (fraud, Class=1) | 18.50% |

Decision: `RobustScaler` (median / IQR) chosen over `StandardScaler` (mean / std) for `Amount` on the grounds that mean/std would be inflated by extreme outliers and compress the inlier mass into a narrow band, destroying distance-based signal for downstream LOF. `Time` was scaled with `RobustScaler` for pipeline uniformity (its skewness was -0.0356, so the choice was mathematically neutral on that column). `V1`-`V28` left untouched: confirmed mean = 0.0, std approx 0.97, already PCA-transformed by the dataset curators.

### Tensions Identified at This Stage
1. **Label-in-CSV hazard:** Writing `Class` into the same CSV as the features set a trap for any downstream code that ingested the file blindly. A model pointed at this CSV could accidentally train on the target.
2. **Single-output-file opacity:** One "final" CSV did not document which feature transformations had been tried or why one was chosen. A reviewer could not reconstruct alternatives.
3. **No stable observation identifier:** No `row_id` existed. All downstream alignment relied on array position, which is fragile.

### External Review (ChatGPT) and Redesign
An external review of the initial preprocessing pass produced three substantive critiques that were accepted:

1. **Mathematical redundancy in the planned FS-B variant.** Applying `RobustScaler` after `log1p` compresses the distribution twice; the variance-stabilising benefit of the log is partially washed out. Amended: FS-B uses `log1p(Amount)` followed by `StandardScaler` to provide a mathematically distinct contrast, not a redundant double-compression.
2. **Label-leakage hazard.** Amended: target isolated to a separate `ground_truth_registry.csv` containing only `row_id` and `Class`. Feature-space CSVs contain strictly features plus `row_id`.
3. **String-list concatenation syntax.** Minor: column lists consolidated into single variables for DRY.

### Final Phase 2 Outputs (Track A)
Two controlled feature-space variants produced, both leak-proof and `row_id`-tracked:

| Feature Space | Features | Amount Treatment | Time Treatment | Scaling | Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FS-A (Baseline)** | V1-V28, Time, Amount | None | None | RobustScaler on (Time, Amount) | Primary baseline (median/IQR) |
| **FS-B (Sensitivity)** | V1-V28, Time, Amount | log1p | None | StandardScaler on (Time, Amount) | Sensitivity (variance stabilisation) |

Companion artefacts: `ground_truth_registry.csv` (row_id, Class), `feature_space_manifest.md` documenting the variants.

### Decision
FS-A selected as the primary feature space for Phase 3. FS-B retained for sensitivity testing if Phase 3/4 results warrant it. The single-file `creditcard_preprocessed.csv` is **deprecated** and retained only as a historical record of the initial pass.

*Refer - `notebooks/phase2_trackA_preprocessing.ipynb`*

## Phase 3 (Track A) - Methodological Execution: First Attempt and Revision

**Date:** 2026-10-21 to 2026-10-22

### First Attempt (Deprecated)
The first Phase 3 pass ran a 5x3x2 grid for iForest (contamination x n_estimators x max_samples) and a 4x5x2 grid for LOF (n_neighbors x contamination x metric). The `contamination` parameter was passed directly to both models, allowing them to set the binary flag threshold internally. Outputs were stored as raw NumPy arrays keyed by run name; `row_id` was not stored alongside predictions.

**Critical bug discovered retrospectively in Phase 4:** The first attempt's LOF grid included both `'euclidean'` and `'minkowski'` metrics. Because scikit-learn's `minkowski` defaults to `p=2`, this is mathematically identical to `'euclidean'`. The grid was running the same computation twice. Amended in the revised run: alternative metric changed to `'manhattan'` (Minkowski with `p=1`).

### External Review (ChatGPT) and Methodological Restructuring
A second external review produced a structural critique that fundamentally reshaped Phase 3:

1. **`contamination` is a decision rule, not truth.** Passing `contamination` to the model conflates the detector (which produces a continuous anomaly score) with the decision rule (which thresholds that score into a binary flag). Phase 3 should produce scores; Phase 4 should apply thresholds.
2. **Phase 3 must not be label-informed.** Using `Class` to select the "best" configuration turns unsupervised detection into supervised model selection. Phase 3 should investigate parameter sensitivity and seed stability without consulting labels; Phase 4 may use labels to evaluate the resulting outputs.
3. **Every prediction must carry `row_id` and run metadata.** No array-position alignment downstream.

### Revised Phase 3 Design (Adopted)
- Both detectors fit on the frozen FS-A feature matrix only. No `Class` consulted during fitting.
- `contamination` removed from both model constructors. Both produce continuous anomaly scores.
- Explicit decision rule applied post-hoc: flag the bottom 1% of scores (exactly 300 flags per run on the 30k sample, 2,848 on the full dataset).
- Five iForest configurations: parameter sensitivity (n_estimators, max_samples) plus seed stability (random_state 42/43/44).
- Five LOF configurations: neighbourhood-scale sensitivity (k = 5, 15, 30, 50) plus metric sensitivity (manhattan at k=30).
- Every run stored as a canonical prediction record: `row_id`, continuous `score`, binary `flag`, plus a metadata row recording parameters, seed, runtime, threshold rule.
- Score direction canonicalised: `anomaly_score = -raw_score` so that higher = more anomalous for both detectors, eliminating per-method inversion ambiguity in Phase 4.

### Implementation Notes and Bug Fixes Accepted During Revision
Several implementation critiques were accepted during the revision. They are documented here for completeness, not because they altered the methodology:

| Critique | Resolution |
| :--- | :--- |
| `max_samples='auto'` is mathematically equal to 256 when n_samples > 256. | Amended: alternative value set to 0.05 (5% sub-sample). |
| Storing pandas DataFrames inside a prediction dictionary bloats memory. | Amended: raw NumPy arrays stored, with `uint8` flags and `float32` scores. |
| `del` of local array variables before all references resolved risks namespace confusion. | Amended: cleanup moved to loop boundary. |
| `n_jobs=-1` deadlocks joblib on Colab for LOF. | Amended: `n_jobs=2` (later `n_jobs=1` on full data). |
| `algorithm='auto'` for LOF silently selects `ball_tree` when D > 20; relying on this heuristic is opaque. | Amended: `algorithm='ball_tree', leaf_size=40` set explicitly. |

### Compute Constraint - Colab Free Tier
The revised Phase 3 was first executed on a 30,000-row random unsupervised subsample of FS-A. The sample was drawn without consulting `Class`. The same 30,000 `row_id`s were supplied to all 10 runs (5 iForest + 5 LOF).

LOF on the full 284,807-row matrix deadlocks the Colab free-tier CPU even with `ball_tree`, `n_jobs=1`, and `leaf_size=40`. A second pass on the full dataset was later completed using LOF **Novelty Mode** (`novelty=True`): LOF was fit on a 50,000-row random unsupervised subsample and used `score_samples` to predict anomaly scores for all 284,807 rows. This is a computational compromise with documented consequences (see Phase 4).

### Decision
The 30k subsample run is the **primary Phase 3 artefact** because LOF operates in native `fit_predict` mode there. The 284k full-dataset run is retained as a **scale-sensitivity companion artefact** with the LOF Novelty Mode limitation explicitly flagged. Both are documented; neither is silently dropped.

*Refer - `notebooks/phase3_trackA_modelling_30k.ipynb`, `notebooks/phase3_trackA_modelling_full.ipynb`*

## Phase 4 (Track A) - Label-Informed Validation: Bug Discovery and Correction

**Date:** 2026-10-22

### First Evaluation Run (Buggy)
The first Phase 4 evaluation produced catastrophic metrics: iForest ROC-AUC approx 0.50, AP matching the base fraud rate. The numbers indicated the models were no better than random.

### Root Cause
The Phase 3 predictions were stored in the order of the 30k random subsample. Phase 4 code extracted the matching `row_id`s from `ground_truth_registry.csv` and **sorted them** before merging with the unsorted prediction arrays. The labels were decoupled from the scores they were meant to evaluate. The models had not failed; the evaluation had silently shuffled the answer key.

### Correction
Predictions and ground truth merged into a single Pandas DataFrame on `row_id` as the join key. No array-position alignment permitted downstream. This is the same `row_id`-alignment discipline that the Phase 2 redesign introduced; the bug existed because the first Phase 4 code predated full adoption of that discipline.

### Corrected Phase 4 Results - 30k Sample (47 frauds, 1% threshold = 300 flags)

| Run | Model | Config | AP | ROC-AUC | Prec@1% | Rec@1% | F1@1% | TP |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| IF_003 | iForest | n_est=100, msamp=0.05, seed=42 | 0.3126 | 0.9803 | 0.1000 | 0.6383 | 0.1729 | 30 |
| IF_004 | iForest | n_est=100, msamp=256, seed=43 | 0.2094 | 0.9787 | 0.1067 | 0.6809 | 0.1844 | 32 |
| LOF_004 | LOF | k=50, euclidean | 0.3229 | 0.9536 | 0.1267 | 0.8085 | 0.2190 | 38 |
| LOF_001 | LOF | k=5, euclidean | 0.0024 | 0.5220 | 0.0033 | 0.0213 | 0.0058 | 1 |

(Full 10-run table retained in `phase4_validation_metrics_CORRECTED.csv`.)

### Corrected Phase 4 Results - Full 284k Dataset (492 frauds, 1% threshold = 2,848 flags)

| Run | Model | AP | ROC-AUC | Prec@1% | Rec@1% | F1@1% | TP |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| IF_003 | iForest | 0.2340 | 0.9494 | 0.1113 | 0.6443 | 0.1898 | 317 |
| LOF_004 | LOF (Novelty) | 0.0562 | 0.9070 | 0.0586 | 0.3394 | 0.1000 | 167 |

(Full 10-run table retained in `FULL_phase4_metrics.csv`.)

### Key Findings
1. **iForest is scale-invariant.** Recall on 30k = 63.8%; recall on 284k = 64.4%. AP drops modestly (0.31 to 0.23) but ranking quality remains high. iForest's tree-based isolation paths do not degrade with sample size.
2. **LOF degrades under Novelty Mode.** Recall on 30k native `fit_predict` = 80.9%; recall on 284k Novelty Mode = 33.9%. The 50k density map cannot capture the micro-density fluctuations of the full 284k space. This is the cost of the compute compromise, not a property of the algorithm itself.
3. **LOF neighbourhood-scale sensitivity is dramatic.** On the 30k sample: k=5 -> AP 0.0024, k=50 -> AP 0.3229. The choice of `n_neighbors` is not a tuning detail; it determines whether LOF is useful at all on this data.
4. **iForest flags are 100% false positives when LOF disagrees.** On the 30k sample at 1%: iForest-only flags = 193 observations, 0 frauds. LOF-only flags = 193 observations, 8 frauds. Both-methods flags = 107 observations, 30 frauds (28.0% precision vs 0.16% base rate).

### Decision
Both 30k and 284k results retained as complementary evidence. The 30k run is the methodologically cleaner artefact (native LOF); the 284k run is the scale-stress artefact (LOF Novelty Mode compromise). Neither is silently discarded.

*Refer - `notebooks/phase4_trackA_validation_30k.ipynb`, `notebooks/phase4_trackA_validation_full.ipynb`*

## Phase 5 (Track A) - Diagnostic Analysis and Visualization

**Date:** 2026-10-22 to 2026-10-23

### Scope
Phase 5 was treated as **visualization + quantitative diagnostic analysis**, not a cosmetic plotting exercise. All computations consumed the canonical Phase 3/4 artefacts; no models were refit.

### Quantitative Diagnostics Computed

1. **Stratified bootstrap confidence intervals (2,000 replicates).** Performed for IF_003, IF_004, LOF_004 on AP, ROC-AUC, Precision@1%, Recall@1%, F1@1%. Fraud and legitimate rows resampled separately to preserve imbalance. Example: LOF_004 Recall@1% 95% CI on 30k = [0.6809, 0.9149]; IF_003 = [0.5106, 0.7872]. LOF's worst-case recall exceeds IF's best-case recall, supporting the claim that LOF_004's superiority at 1% is statistically meaningful, not a point-estimate artefact.

2. **Exact hypergeometric overlap test.** Expected random overlap at 1%: 3.0 (30k), 28.48 (284k). Observed: 107 (30k), 457 (284k). Enrichment: 35.67x (30k), 16.05x (284k). P-value reported via `logsf` to avoid underflow: p < 10^-140.30 (30k), p < 10^-396.37 (284k). The consensus overlap is not a chance event.

3. **10x10 pairwise score-correlation matrix (Spearman).** IF<->IF Spearman approx 0.93; LOF<->LOF Spearman varies with k; IF<->LOF Spearman approx 0.37. The two methods produce substantially different anomaly rankings.

4. **10x10 pairwise top-1% Jaccard matrix.** Visualises intra-method stability vs inter-method disagreement in one compact figure.

5. **Multi-threshold agreement analysis.** At 0.1%, 0.2%, 0.5%, 1%, 2%, 5% top-k. At 0.1% on 30k: iForest-only captures 11 unique frauds, LOF-only captures 10, both capture 3. At 1%: iForest-only captures 0, LOF-only captures 8. iForest dominates at the extreme edge; LOF dominates as the budget expands. This is the most informative single table in the project.

6. **PCA explained variance.** PC1 + PC2 capture a modest fraction of total variance (documented in plot captions). All PCA visualisations are explicitly labelled as lossy projections, not as faithful geometry.

### Visualizations Produced
Eight diagnostic figures produced for each of 30k and 284k runs (16 total), saved as high-resolution PNGs:

1. Precision-Recall curves (5 IF + 5 LOF, best runs highlighted)
2. Fraud discovery curve (recall vs review budget) + precision vs budget
3. Hypergeometric null distribution with observed overlap marked
4. 10x10 Spearman correlation heatmap
5. 10x10 top-1% Jaccard heatmap
6. Top-k Jaccard curve (0.1% to 5%)
7. Rank-vs-rank scatter (IF percentile vs LOF percentile, agreement groups highlighted)
8. PCA agreement map (Both / IF-only / LOF-only / Neither, with flagged-only overlay)

### Decision
Phase 5 closed. No additional visualisations or computations will be added unless Phase 7 gap analysis identifies a specific need.

*Refer - `notebooks/phase5_trackA_diagnostics_30k.ipynb`, `notebooks/phase5_trackA_diagnostics_full.ipynb`*

## Phase 6 (Track A) - Cross-Method Consistency Analysis

**Date:** 2026-10-23

### Scope
Phase 6 investigated whether iForest and LOF identify the same observations or different forms of unusualness, and whether their agreement is greater than chance.

### Primary Findings (30k sample, IF_003 vs LOF_004)

| Metric | Value | Interpretation |
| :--- | :--- | :--- |
| Spearman rank correlation (IF vs LOF) | 0.37 | Substantially different rankings; positive but far from agreement |
| Top-1% Jaccard | 0.2170 | ~22% of flagged items overlap |
| Top-0.5% Jaccard (peak) | ~0.27 | Agreement strongest at the extreme edge |
| Expected random overlap | 3.0 | - |
| Observed overlap | 107 | 35.67x enrichment |
| Hypergeometric p-value | < 10^-140 | Overlap is not chance |

### Agreement-Group Composition (30k, 1% threshold)

| Group | Count | Fraud | Fraud % | Recall Contribution |
| :--- | :--- | :--- | :--- | :--- |
| Both | 107 | 30 | 28.04% | 63.83% |
| iForest-only | 193 | 0 | 0.00% | 0.00% |
| LOF-only | 193 | 8 | 4.15% | 17.02% |
| Neither | 29,507 | 9 | 0.03% | 19.15% |

### Five Questions Answered (per the Phase 6 framework)

1. **Are the two methods producing similar anomaly rankings?** No. Spearman approx 0.37 confirms substantially different rankings, consistent with their different detection mechanisms.
2. **How much do their highest-ranked observations overlap?** Modestly. Jaccard peaks at ~0.27 (top 0.5%) and declines as k increases.
3. **Is the overlap greater than expected by chance?** Yes, overwhelmingly. 35.67x enrichment on 30k, 16.05x on 284k, with p-values so extreme they require `logsf` to express.
4. **When they disagree, which method-specific groups contain the known frauds?** On 30k: iForest-only = 0 frauds (100% false positives); LOF-only = 8 frauds; Both = 30 frauds (28% precision). The intersection is the highest-precision group.
5. **Is the disagreement caused by fundamentally different anomaly definitions, or by LOF's neighbourhood-scale sensitivity?** Both. LOF's k-sensitivity is dramatic (AP ranges from 0.0024 at k=5 to 0.3229 at k=50 on 30k). Even at the best k, however, the IF<->LOF Spearman remains ~0.37, indicating the methods respond to different geometric properties of the data, not merely to different scale parameters.

### Interpretive Discipline Applied
Per external review: the finding supports "the two methods identify substantially different high-anomaly populations, consistent with their different detection mechanisms." It does **not** support the stronger mechanistic claim that "LOF catches local-density anomalies invisible to iForest's isolation paths." The latter is an interpretation of why the algorithms disagree, not something the overlap experiment directly establishes.

Similarly: "the consensus group had approximately 179x the sample's baseline fraud prevalence" is defensible. "The consensus detector is 179x more accurate" is not, and is not claimed.

### Decision
Phase 6 closed. No score fusion or ensemble construction attempted. Per framework guidance, understanding *why* the methods disagree precedes any attempt to combine them.

*Refer - `notebooks/phase6_trackA_consistency.ipynb`*

## Phase 6a (Track A) - 30k vs 284k Comparison

**Date:** 2026-10-23

### Purpose
To document the effect of the LOF Novelty Mode compute compromise by comparing the 30k native-LOF run against the 284k Novelty-LOF run on identical configurations.

### Headline Comparison

| Run | Metric | 30k (native LOF) | 284k (LOF Novelty) |
| :--- | :--- | :--- | :--- |
| IF_003 | AP | 0.3126 | 0.2340 |
| IF_003 | Recall@1% | 0.6383 | 0.6443 |
| LOF_004 | AP | 0.3229 | 0.0562 |
| LOF_004 | Recall@1% | 0.8085 | 0.3394 |
| Consensus | Observed overlap | 107 | 457 |
| Consensus | Enrichment vs random | 35.67x | 16.05x |

### Findings
1. **iForest is scale-robust.** Recall essentially identical (63.8% to 64.4%). AP drops modestly. The algorithm's tree-based isolation does not depend on native density estimation over the full sample.
2. **LOF degrades sharply under Novelty Mode.** AP drops 5.7x, recall drops 2.4x. The 50k density map learned by LOF in Novelty Mode cannot represent the micro-density structure of the full 284k space. This is the cost of the Colab compute constraint, not a property of LOF on this data.
3. **Consensus enrichment dilutes with scale but remains extreme.** 35.67x to 16.05x. Expected random overlap grows quadratically with k; observed overlap grows sub-quadratically. The consensus signal remains overwhelmingly non-random (p < 10^-396 on 284k).

### Decision
The 30k run remains the **primary methodological artefact** for LOF characterization. The 284k run is the **scale-stress companion**. Both are reported; the LOF Novelty Mode limitation is documented in Phase 7.

## Current Status (as of 2026-10-23)

### Stream A - COMPLETE (Phases 1-6)
- Phase 1: Data acquired and verified. (Done)
- Phase 2: Two feature-space variants produced (FS-A primary, FS-B sensitivity). (Done)
- Phase 3: 10 runs (5 iForest + 5 LOF) on 30k sample; 10 runs on 284k full dataset (LOF Novelty Mode). (Done)
- Phase 4: Label-informed validation on both 30k and 284k. Alignment bug discovered and corrected. (Done)
- Phase 5: Bootstrap CIs, hypergeometric test, 10x10 matrices, multi-threshold analysis, 8 diagnostic plots per scale. (Done)
- Phase 6: Cross-method consistency analysis with five-question framework answered. (Done)

### Stream B - Phase 1 COMPLETE, Phase 2 IN PROGRESS
- Phase 1: PMGSY-III six-state dataset accepted (9,634 unique records after dedup). Adversarial validation performed. (Done)
- Phase 2: Extended EDA initiated. Provisional data-handling approach documented. In progress.

### Phases 7 and 8 - NOT YET STARTED
- Phase 7 (Limitations, Gap Analysis, Domain Transfer Conditions): to be drafted after Stream B Phase 2-6 completion, or as a single-stream gap analysis if Stream B proves non-viable.
- Phase 8 (Documentation, Reproducibility, Provenance Finalization): this log is the living draft of that phase.

### Outstanding Tensions to Resolve
1. The LOF Novelty Mode compromise on 284k is methodologically defensible but limits the strength of full-scale LOF claims. The 30k native-LOF run is the cleaner artefact and should be the primary citation for LOF behaviour.
2. The first Phase 4 alignment bug, while corrected, is a documented instance of the kind of array-position fragility the Phase 2 `row_id` redesign was meant to prevent. It is retained in this log as evidence that the redesign was necessary, not optional.
3. Stream B (PMGSY-III) has no labels. Phase 4 for Stream B will be score-distribution + manual top-N inspection only. This is anticipated by the framework but lowers the analytical ceiling for that stream.
4. The scope claim for Stream B is "pipeline reusability demonstration," not "domain anomaly findings." This must be respected in Phase 7 to avoid overclaiming.

---

*End of Stream A execution trail. Stream B execution trail will be appended as Phase 2 progresses.*

## GitHub Publication Strategy (Decision Deferred)

**Date:** 2026-10-24

### Context
The project will be published to a public GitHub repository as a portfolio piece. Three substantive decisions are required before push: data file strategy, Drive link handling, and PMGSY redistribution.

### Decisions Taken
1. **Repository audience:** Portfolio piece. Will live on public GitHub long-term. Polish, README quality, and reproducibility matter.
2. **Repository visibility:** Public.
3. **Drive link policy:** Personal Google Drive links will NOT appear in the public repo. They leak account metadata, are fragile to reorganisation, are not version-controlled, and read as unprofessional. The notebook will use `os.environ.get('STORAGE_DIR', './data')` so it runs anywhere without exposing personal paths.

### Decisions Deferred
1. **Large data file strategy (ULB raw, FS-A/B, predictions pickle):** Three options remain open:
   - **Pure regeneration (preferred default):** commit only code + small final results; provide `scripts/download_ulb.sh` using Kaggle API; derived artifacts regenerated by running the pipeline.
   - **Hugging Face Datasets hosting:** host derived artifacts on a free HF dataset repo; README links to HF.
   - **Git LFS:** commit everything via LFS; bandwidth-capped, history hard to clean.

   Decision will be taken at Phase 8 (Documentation and Reproducibility Finalisation), after Stream B is complete and the full project scope is known.

2. **PMGSY-III redistribution:** Source attribution and public-good framing have been documented (Section: Stream B Update). India's Government Open Data License (GODLI) permits redistribution with attribution, but redistribution on GitHub is NOT confirmed. **Default stance until verified:** provide a `scripts/download_pmgsy.sh` pointing to data.gov.in, do not commit the raw CSV.

### Constraints Locked Regardless of Deferred Decisions
- No personal Drive links in any committed file.
- No raw ULB data re-hosted (Kaggle is the canonical source; ODbL license respected).
- No PMGSY raw CSV committed until license verified.
- Notebook outputs stripped before commit (`jupyter nbconvert --clear-output --inplace`).
- All paths parameterised via environment variables.
- `provenance_log.md` committed as a first-class artifact, not an appendix.

### Decision
Decisions deferred to Phase 8. Constraints above are locked now to prevent rework later.

*Refer - to be cross-linked to Phase 8 documentation notebook when finalised.*

---

## 2026-11-05 â€” Phase 4 Evaluation Layer Migration (Stream A, Stage 2)

**Context:** continuation of the Stage 1 pipeline migration. Phase 3 was frozen and its canonical artifacts (`results/stream a/phase 3/phase3_canonical_predictions.pkl`, `phase3_run_metadata.csv`) are the read-only source of truth; ground truth lives separately at `data/processed/stream-a/labels/ground_truth_registry.csv` (284,807 row_ids, 492 positives; 47 positives inside the 30k primary sample).

### What was implemented
- `src/mplad/stream_a/phase4.py` â€” the label-based evaluation compute layer: input validation (registry / Phase 3 metadata / prediction bundle), row_id alignment, per-run metric computation, orchestration (`run_phase4_evaluation`, `collect_phase4_preflight`), and a post-hoc reference-comparison helper. It imports only `sklearn.metrics` â€” no detector is ever constructed, fitted or refitted.
- `src/mplad/common/manifest.py` â€” new additive SHA-256 manifest utilities (build/save/load/strict verify). The hardened Stage 1 Phase 3 has no manifest generation, so Phase 4 handles its inputs as a **legacy unmanifested pair**: strict structural validation, input SHA-256 hashes recorded in `phase4_run_metadata.json`, and an explicit statement that manifest verification was NOT performed. If a `phase3_commit_manifest.json` is ever placed next to the artifacts, Phase 4 verifies it (hash + size + coverage of both consumed files) before consuming anything. Phase 4 publishes its own `phase4_commit_manifest.json` over its outputs.
- `scripts/run_phase4.py` â€” CLI with preflight-by-default, explicit `--execute`, `--output-dir`, `--overwrite`, input path overrides, and an optional `--reference-metrics` post-hoc acceptance comparison.
- `tests/test_phase4.py` â€” 69 lightweight tests on synthetic fixtures covering all twenty required cases, including the explicit test that fails if labels are aligned by array position instead of `row_id`, hand-verified AP/ROC-AUC/confusion values, flag-usage (never recomputed), no-fitting (poisoned sklearn entry points), dry-run no-writes, output protection, and both manifest paths.
- `docs/phase4_contract.md` â€” the full input/output contract (this migration's schema reference).

### Additive changes to shared modules (no Phase 3 behaviour change)
- `config.py`: Phase 4 path constants (`DEFAULT_GROUND_TRUTH_PATH`, `PHASE3_PREDICTIONS_PATH`, `PHASE3_RUN_METADATA_PATH`, `DEFAULT_PHASE4_OUTPUT_DIR`, artifact filenames, `PHASE3_CANONICAL_RUN_IDS`, `LABEL_COLUMN`, `VALID_LABEL_VALUES`, `PHASE3_MANIFEST_FILENAME`). All Phase 3 constants untouched.
- `io.py`: new generic guarded writers `save_dataframe_csv` and `save_json`. Existing Phase 3 functions byte-identical (Phase 3 suite re-run: 40 passed, 1 environment-dependent skip).

### The historical alignment bug, structurally prevented
The original Colab Phase 4 sorted ground truth by `row_id` while prediction arrays stayed in draw order, then aligned by array position â€” every metric was wrong until the audit fix. The migrated layer joins predictions and labels **on `row_id` with `validate="one_to_one"`**, preserves the prediction sequence end-to-end, and hard-rejects unmatched prediction IDs, duplicate IDs, and incomplete joins. A dedicated regression test (`test_positional_alignment_would_fail_this_test`) fails under any positional implementation.

### Score orientation made explicit
`native_score` (Phase 3 storage convention, lower = more anomalous) is kept alongside `anomaly_score = -native_score` (canonical, higher = more anomalous) in the evaluation dataset; ranking metrics use `anomaly_score`; fixed-threshold metrics use the saved Phase 3 flags exactly as supplied â€” the 1% rule is never recomputed or re-optimised in Phase 4.

### Outputs (separate location; historical Phase 4 results untouched)
`results/stream a/phase 4/reproduction/`: `phase4_evaluation_dataset.csv` (long form, one row per (run_id, row_id), 300,000 rows on the canonical experiment), `phase4_metrics.csv` (one row per run, metadata passthrough + metrics), `phase4_run_metadata.json` (provenance: input hashes, manifest status, environment, `models_fitted: 0`), `phase4_commit_manifest.json`.

### Verification performed
- `python -m compileall -q src scripts tests` â€” clean.
- `python -m pytest -q tests/test_phase4.py` â€” 69 passed (synthetic fixtures only).
- `python -m pytest -q tests/test_phase3.py` â€” 40 passed, 1 skipped (optional canonical-file cross-check; the canonical results directory is absent on the migration machine) â€” no Phase 3 regression.
- End-to-end synthetic validation: a genuine ten-run Phase 3 execution on synthetic FS-A data, consumed through the full Phase 4 CLI (preflight â†’ execute), with the output manifest re-verified and the legacy-input provenance inspected.
- No execution against the real registry has occurred yet on the migration machine; the acceptance reference checks (IF_003 / LOF_004) are documented in `docs/phase4_contract.md` Â§8 and are to be confirmed by running `scripts/run_phase4.py --execute` where the canonical artifacts live.

### Out of scope (next stages)
Phase 4 notebook, Phase 5 diagnostics/bootstrapping/plots, Phase 6 agreement analysis, the separately-named larger-experiment runner, and the Streamlit app.

---

# Project Provenance and Decision Ledger
# **Provenance and Decision Log**

**Project:** MPLAD Fund-Utilization Anomaly Pattern Detection Using Unsupervised Learning  
**Document Purpose:** To maintain a transparent record of substantive decisions, identified tensions, and scope qualifications arising during the project's design and execution phases.  
**Prepared for:** Project documentation appendix; review and audit trail.

# **1\. Initial project Conception and Inference**

The project was initially assigned by the university as an academic project, after which further interest in the problem domain led to its expansion into an unsupervised anomaly-detection study motivated by documented governance concerns in the Members of Parliament Local Area Development Scheme (MPLADS). Publicly available critiquesâ€”including Comptroller and Auditor General findings noting unsupported expenditure, poor monitoring, and suspected irregularitiesâ€”established a prima facie case for exploring data-driven anomaly detection as a supplementary audit tool.&nbsp;

The initial formulation posited three objectives: (a) data preparation and preprocessing, (b) application of Isolation Forest and Local Outlier Factor with comparative evaluation, and (c) assessment of detection consistency, false-positive implications, and ethical considerations.

# **2\. Data Source Selection â€” Rationale and Identified Limitations**

Selection rationale: No publicly available MPLAD-specific transactional dataset of sufficient granularity, completeness, and volume was identified at the time of project commencement. The ULB (UniversitÃ© Libre de Bruxelles) Credit Card Fraud Detection dataset, hosted on Kaggle, was selected as a methodological proxy on the following grounds:

* Extreme class imbalance (492 positive instances in 284,807 total; 0.172% positive rate), approximating the rarity expected in fund misutilization scenarios.  
* Availability of binary labels enabling post-hoc, label-informed evaluation of unsupervised outputs.  
* Sufficient volume to support meaningful parameter sweeps and comparative analysis.

**Limitations identified at selection and reaffirmed during execution:**

| LIMITATION | DETAIL |
| :---- | :---- |
| Domain irrelevance of features | Features V1â€“V28 are PCA-transformed principal components with no semantic labels. The dataset providers explicitly state that original features cannot be disclosed due to confidentiality constraints. No feature corresponds to MPLAD-relevant constructs (scheme category, constituency, sanctioning authority, completion status, geographical identifiers). |
| Temporal insufficiency | The dataset covers two days (September 2013). MPLAD fund utilization operates across financial years and electoral cycles. No temporal validation or concept-drift analysisâ€”both identified in the fraud-detection literature as critical for realistic evaluationâ€”is possible. |
| Preprocessing triviality | The dataset contains no missing values and no categorical variables requiring encoding. Objective 1's preprocessing components (missing-value handling, categorical encoding) are therefore demonstrative rather than empirically necessary on this specific data. |
| Structural mismatch in anomaly topology | Credit card fraud anomalies are point-level transactional outliers. MPLAD anomalies are expected to manifest as project-level patterns (e.g., clustered incomplete works, concentration of sanctions to specific contractors, electoral-cycle-driven expenditure spikes). The two anomaly topologies are not equivalent. |
| Benchmark overuse | The ULB dataset is the single most widely used benchmark in credit card fraud detection literature, with numerous studies reporting near-perfect metrics. Results obtained on this dataset are well-characterized in the literature and carry limited incremental informational value. |

Decision: The dataset was retained as a methodological proxy, but the project documentation was required to clearly state that no domain-valid conclusions regarding MPLAD fund utilization can be drawn from results obtained on this data.

# **3\. Methodological Choices â€” Assumptions and Constraints**

**Isolation Forest (iForest):**

* Assumes anomalies are "few and different" and can be isolated with fewer random partitions than normal observations.  
* Known sensitivity to the contamination parameter; mis-specification directly alters the anomaly set.  
* Performance degrades when anomalies are clustered rather than scattered, and when the anomaly proportion exceeds the "few" assumption.  
* Stochastic by design; results may vary across runs, particularly with limited tree counts or small subsampling sizes.  
* More efficient than density-based methods at higher dimensions and larger sample sizes.

**Local Outlier Factor (LOF):**

* Identifies anomalies based on local density deviation from neighbours.  
* Sensitive to the neighbourhood parameter (k); different values can yield substantially different anomaly rankings.  
* Relies on distance-based density estimation, which is known to face degradation in high-dimensional spaces due to distance concentration effects, though this is partially mitigated here by the prior PCA reduction to 28 components.  
* Computationally more expensive than iForest at scale; does not scale as favourably with increasing observation count.

**PCA Visualization:**

* Applied for exploratory visualization of the detection output in reduced space.  
* Noted tension: the dataset's features are already PCA-transformed; applying PCA again for visualization serves a different purpose (dimensionality reduction for display) than the original transformation (anonymization), and this distinction must be disambiguated to avoid conflation.

**Evaluation approach:**

* Label-informed evaluation (using the Class variable) is employed to assess detector outputs. This is explicitly characterized as semi-supervised evaluation of unsupervised methods, not as purely unsupervised validation. The project does not claim unsupervised evaluation.

# **4\. Critical Reassessment â€” Points of Tension Identified**

During the course of the project, the following structural tensions were identified between the project's stated domain motivation and its actual executable scope:

* The proxy-dataâ€“domain-claim gap: The project title references MPLAD fund utilization, but no MPLAD data is used. Any reader or reviewer examining the methodology would encounter this dissonance immediately. Continuing without acknowledgment would constitute overclaiming.  
* The preprocessingâ€“reality gap: Objective 1's emphasis on missing-value handling and categorical encoding, while sound as pipeline design, is not exercised by the chosen dataset. Presenting these as challenges addressed would be inaccurate.  
* The "consistent anomaly pattern" claim: The stated outcome includes identifying "consistent anomaly patterns." On PCA-transformed, anonymized features, no pattern can be interpreted or mapped to any domain construct. The outcome claim requires qualification.  
* The unsupervised framing tension: Using labels for evaluation while describing the project as "unsupervised learning" requires precise terminological hygiene. The methods are unsupervised; the evaluation is not.  
* The false-positive implication gap: Discussing false-positive implications in the MPLAD context (e.g., wrongful flagging of constituencies, erosion of trust in audit processes) is ethically necessary but empirically hollow when the underlying data bears no relation to that context.

# **5\. Decisions Taken**

The following decisions were made in response to the identified tensions:

| DECISION | RATIONALE |
| :---- | :---- |
| Retain the ULB dataset as primary benchmark but reframe its role explicitly as "methodological proxy for imbalanced anomaly detection," not as MPLAD data. | The dataset serves a legitimate benchmarking function. Removing it would leave no executable methodology. Reframing preserves honesty without discarding the analytical work. |
| Add a supplementary exploratory component using publicly available government expenditure data (state/district-level or any accessible public-fund dataset), subject to data availability at time of execution. | To demonstrate that the pipeline was tested beyond the proxy boundary, even if results are inconclusive. This converts the project from "proxy-only exercise" to "proxy benchmark with attempted domain transfer." |
| Reframe Objective 1 as pipeline scaffolding and reproducible methodology documentation, acknowledging that missing-value handling and categorical encoding are demonstrated procedurally rather than empirically driven by the proxy dataset. | Accuracy in claims. The preprocessing steps remain valid as reusable pipeline components for real MPLAD-style data. |
| Reframe the outcome from "identifying consistent anomaly patterns" to "identifying consistent detection behaviour across methods and parameter settings on a standardized imbalanced benchmark." | The former is unachievable on anonymized features; the latter is verifiable and honest. |
| Characterize evaluation as label-informed throughout all documentation. Use the term "unsupervised learning" strictly to describe the methods (iForest, LOF), not the evaluation protocol. | Terminological precision prevents the unsupervised/semi-supervised conflation. |
| Structure the limitations section as an engineering gap analysis directed at methods, data conditions, and deployment requirementsâ€”not at the assignment design. | A limitations section addressing what minimum data conditions, feature types, and temporal structures would be required for domain-valid deployment reads as professional maturity. A section addressing the assignment's design reads as grievance. The former serves the project; the latter does not. |
| Document this provenance log as part of the project submission. | Transparency. Any reviewer examining the project's decisions should have access to the reasoning trail, including acknowledged limitations and scope qualifications made before rather than after evaluation. |

# **6\. Scope of Claims â€” What This Study Can and Cannot Support**

**This study can support:**

* Comparative characterization of Isolation Forest and LOF behaviour under extreme class imbalance on a standardized benchmark.  
* Parameter sensitivity analysis (contamination rate, tree count, neighbourhood size) and its effect on detection consistency.  
* A reproducible preprocessing and detection pipeline applicable to analogous imbalanced anomaly-detection tasks.  
* Identification of minimum data conditions (interpretable features, temporal scope, domain-relevant anomaly topology) required before unsupervised methods could be responsibly applied to MPLAD fund utilization data.

**This study cannot support:**

* Any claim about anomaly patterns in MPLAD fund utilization.  
* Any inference about the prevalence, nature, or distribution of irregularities in the MPLAD scheme.  
* Any recommendation for operational deployment of these methods in a public-fund auditing context without access to domain-appropriate data.  
* Generalization of detection rates or false-positive characteristics from the ULB benchmark to real MPLAD data, given the structural mismatches documented in Section 2\.

# **7\. Sources Informing This Log**

The following sources informed the identification of limitations and the framing of decisions documented above:

* ULB Machine Learning Group. Credit Card Fraud Detection Dataset. Kaggle. â€” Dataset description, PCA transformation, feature anonymization, class distribution.  
* Impact Cyber Trust. Credit Card Fraud Detection â€” Dataset Entry. â€” Feature descriptions (V1â€“V28 as PCA components; Time and Amount untransformed).  
* OpenML. CreditCardFraudDetection (Dataset ID 42175). â€” Confirmation of dataset size, class balance, and provenance.  
* Fraud Detection Handbook (Chapter 2: Machine Learning for Credit Card Fraud Detection). â€” Concept drift, temporal validation requirements, near-real-time operational constraints in fraud detection systems.  
* Amazon Science. Fraud Dataset Benchmark (FDB). â€” Characterization of the ULB dataset as a two-day, PCA-transformed, anonymized benchmark; contextualization within broader fraud-detection dataset landscape.  
* Agyemang, E.F. et al. (2024). "Anomaly detection using unsupervised machine learning." Results in Engineering. â€” Comparative performance of Isolation Forest, One-Class SVM, and Robust Covariance; discussion of precision-recall trade-offs.  
* Alghushairy, O. et al. (2020). "A Review of Local Outlier Factor Algorithms for Numerical Data." â€” LOF limitations: high-dimensional degradation, sensitivity to neighborhood parameter, computational scaling.  
* mbrenndoerfer.com. "Isolation Forest: Anomaly Detection â€” Limitations." â€” iForest assumptions (few and different anomalies), instability with limited trees, difficulty with clustered or local anomalies.  
* Zimek, A. (2013). "Outlier Detection in High-Dimensional Data." PAKDD Tutorial. â€” Distance concentration effects and challenges for density-based methods in higher dimensions.  
* Observer Research Foundation. "MPLAD Scheme: Need to Work on Loopholes." â€” Governance concerns: poor utilization, inadequate monitoring, inadmissible works, suspected fraud.  
* Frontline (The Hindu). "The Case Against MPLADS." â€” CAG findings: Rs. 161 crore expenditure unsupported by documentation; 33.12% of sampled works with deficient execution records.  
* Ideas for India. "Electoral Cycles and Incomplete Public Works Projects: An Analysis of the MPLAD Scheme." â€” Structural patterns in MPLAD project completion driven by electoral timing.  
* Popova, I. (2025). Credit Card Fraud Detection (arXiv). â€” Identification of ULB dataset as the most widely used benchmark; discussion of class-imbalance handling approaches.  
* Preprints.org. "A Systematic Review of Machine Learning in Credit Card Fraud Detection" (2025). â€” Review of 52 studies on the ULB benchmark; ensemble methods' performance; noted lack of temporal validation in most benchmark usage.

## Phase 1: Data Acquisition & Integrity Verification (Stream A)

- **Dataset Identifier:** `ULB_CC_Fraud_2013`
- **Source:** Kaggle (`mlg-ulb/creditcardfraud`)
- **Publishers:** Machine Learning Group (ULB) & Worldline
- **License:** Open Database License (ODbL) v1.0 / Database Contents License (DbCL) v1.0
- **Acquisition Date:** 2026-08-29

### Integrity Audit
- **Expected Dimensions:** 284,807 rows Ã— 31 columns
- **Verified Dimensions:** 284,807 rows Ã— 31 columns (`Passed`)
- **Class Breakdown:** 492 Fraud (0.172%), 284,315 Genuine (99.828%) (`Passed`)
- **Missing Values:** 0 (`Passed`)
- **Verification Script:** `notebooks/phase1_verification.ipynb`
- **SHA-256 Hash:** 76274b691b16a6c49d3f159c883398e03ccd6d1ee12d9d8ee38f4b4b98551a89
*Refer - notebooks/phase1_verification.ipynb*

### Stream B Update: PMGSY-III Dataset Accepted

**Date:** 2026-09-02
**Dataset:** PMGSY-III Geospatial Registry (`PMGSY_Master_Dataset_Combined(1).csv`)
**Source:** â€œMinistry of Rural Development, 2022. PMGSY Rural Connectivity Datasets, https://geosadak-pmgsy.nic.in/opendata/. Published under Indiaâ€™s Government Open Data License: https://data.gov.in/government-open-data-license-indiaâ€

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

Adversarial validation was used to determine whether the added states could be distinguished from the core Biharâ€“UPâ€“MP population. For `P` records, CORE-vs-ADDED AUC was **0.837** using `PROPOSED_L`, `IMS_BATCH` and `IMS_YEAR`, falling to **0.708** when `IMS_YEAR` was removed. For `L` records, AUC was **0.970**, falling to **0.850** without `IMS_YEAR`.

Further inspection showed that `IMS_BATCH` is strongly associated with `IMS_YEAR` and `PROPOSAL_T`, with batch composition varying substantially by state and cohort. This indicated that `IMS_BATCH` can act as a source/cohort indicator rather than a genuine infrastructure characteristic. Permutation importance supported this, particularly for `L` records, where `IMS_BATCH` was the dominant discriminator and `PROPOSED_L` provided no measurable separation.

A final adversarial test using only `PROPOSED_L` produced an AUC of **0.664** for `P` records and **0.500** for `L` records. This showed that, after excluding temporal and batch variables, the remaining cross-state shift in the `P` population was substantially lower. The `L` result also confirmed that `PROPOSED_L` contains no useful variation for that population.

**Final Decision:**
- The six-state PMGSY dataset is **accepted for Stream B**.
- `P` records will form the **primary combined ML population**.
- `L` records will be treated separately or descriptively and will not be mixed into the primary feature space.
- `IMS_BATCH` and raw `IMS_YEAR` will be excluded from the initial anomaly-detection feature space because they can encode temporal/cohort differences. They will remain available for EDA, stratified analysis and sensitivity testing.
- `MRL_ID`, `STATE_ID`, `LGD_STATE`, `LGD_DISTRI`, `DISTRICT_I`, `BLOCK_ID` and `CN_CODE` will be treated as identifiers/administrative reference fields rather than direct ML features unless later feature-engineering analysis provides a defensible reason to use them.
- No additional state will be added solely to exceed the supervisor's approximate **10,000â€“15,000 row** guideline.

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

`Raw/Current Data â†’ Extended EDA â†’ Structural Investigation â†’ Feature Engineering Candidates â†’ Feature-Space Audit â†’ Final Preprocessing â†’ Modelling`

No final preprocessing or feature-space decision is considered locked at the start of Phase 2.

---

# **STREAM A EXECUTION TRAIL - Phases 2 through 6 (ULB Proxy Benchmark)**

*This section documents the complete execution trail for Stream A, in chronological order, with all substantive decisions, identified tensions, bug discoveries, and methodology revisions. It is written to be auditable: a reviewer reading this section should be able to reconstruct why every design choice was made and what alternatives were rejected and why.*

## Phase 2 (Track A) - Initial Preprocessing and Scaling Decision

**Date:** 2026-10-21

### Initial Approach
The first preprocessing pass applied `RobustScaler` to `Time` and `Amount`, retained `V1`-`V28` untouched, and wrote a single output file `creditcard_preprocessed.csv` containing features and the `Class` label in one CSV.

### Diagnostics Driving the Scaling Choice
Pre-scaling diagnostics on `Amount`:

| Metric | Value |
| :--- | :--- |
| Mean | 88.35 |
| Median | 22.00 |
| Std | 250.12 |
| Max | 25,691.16 |
| Skewness | 16.98 |
| Kurtosis | 845.09 |
| IQR-outlier fraction (overall) | 11.20% |
| IQR-outlier fraction (legit, Class=0) | 11.19% |
| IQR-outlier fraction (fraud, Class=1) | 18.50% |

Decision: `RobustScaler` (median / IQR) chosen over `StandardScaler` (mean / std) for `Amount` on the grounds that mean/std would be inflated by extreme outliers and compress the inlier mass into a narrow band, destroying distance-based signal for downstream LOF. `Time` was scaled with `RobustScaler` for pipeline uniformity (its skewness was -0.0356, so the choice was mathematically neutral on that column). `V1`-`V28` left untouched: confirmed mean = 0.0, std approx 0.97, already PCA-transformed by the dataset curators.

### Tensions Identified at This Stage
1. **Label-in-CSV hazard:** Writing `Class` into the same CSV as the features set a trap for any downstream code that ingested the file blindly. A model pointed at this CSV could accidentally train on the target.
2. **Single-output-file opacity:** One "final" CSV did not document which feature transformations had been tried or why one was chosen. A reviewer could not reconstruct alternatives.
3. **No stable observation identifier:** No `row_id` existed. All downstream alignment relied on array position, which is fragile.

### External Review (ChatGPT) and Redesign
An external review of the initial preprocessing pass produced three substantive critiques that were accepted:

1. **Mathematical redundancy in the planned FS-B variant.** Applying `RobustScaler` after `log1p` compresses the distribution twice; the variance-stabilising benefit of the log is partially washed out. Amended: FS-B uses `log1p(Amount)` followed by `StandardScaler` to provide a mathematically distinct contrast, not a redundant double-compression.
2. **Label-leakage hazard.** Amended: target isolated to a separate `ground_truth_registry.csv` containing only `row_id` and `Class`. Feature-space CSVs contain strictly features plus `row_id`.
3. **String-list concatenation syntax.** Minor: column lists consolidated into single variables for DRY.

### Final Phase 2 Outputs (Track A)
Two controlled feature-space variants produced, both leak-proof and `row_id`-tracked:

| Feature Space | Features | Amount Treatment | Time Treatment | Scaling | Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FS-A (Baseline)** | V1-V28, Time, Amount | None | None | RobustScaler on (Time, Amount) | Primary baseline (median/IQR) |
| **FS-B (Sensitivity)** | V1-V28, Time, Amount | log1p | None | StandardScaler on (Time, Amount) | Sensitivity (variance stabilisation) |

Companion artefacts: `ground_truth_registry.csv` (row_id, Class), `feature_space_manifest.md` documenting the variants.

### Decision
FS-A selected as the primary feature space for Phase 3. FS-B retained for sensitivity testing if Phase 3/4 results warrant it. The single-file `creditcard_preprocessed.csv` is **deprecated** and retained only as a historical record of the initial pass.

*Refer - `notebooks/phase2_trackA_preprocessing.ipynb`*

## Phase 3 (Track A) - Methodological Execution: First Attempt and Revision

**Date:** 2026-10-21 to 2026-10-22

### First Attempt (Deprecated)
The first Phase 3 pass ran a 5x3x2 grid for iForest (contamination x n_estimators x max_samples) and a 4x5x2 grid for LOF (n_neighbors x contamination x metric). The `contamination` parameter was passed directly to both models, allowing them to set the binary flag threshold internally. Outputs were stored as raw NumPy arrays keyed by run name; `row_id` was not stored alongside predictions.

**Critical bug discovered retrospectively in Phase 4:** The first attempt's LOF grid included both `'euclidean'` and `'minkowski'` metrics. Because scikit-learn's `minkowski` defaults to `p=2`, this is mathematically identical to `'euclidean'`. The grid was running the same computation twice. Amended in the revised run: alternative metric changed to `'manhattan'` (Minkowski with `p=1`).

### External Review (ChatGPT) and Methodological Restructuring
A second external review produced a structural critique that fundamentally reshaped Phase 3:

1. **`contamination` is a decision rule, not truth.** Passing `contamination` to the model conflates the detector (which produces a continuous anomaly score) with the decision rule (which thresholds that score into a binary flag). Phase 3 should produce scores; Phase 4 should apply thresholds.
2. **Phase 3 must not be label-informed.** Using `Class` to select the "best" configuration turns unsupervised detection into supervised model selection. Phase 3 should investigate parameter sensitivity and seed stability without consulting labels; Phase 4 may use labels to evaluate the resulting outputs.
3. **Every prediction must carry `row_id` and run metadata.** No array-position alignment downstream.

### Revised Phase 3 Design (Adopted)
- Both detectors fit on the frozen FS-A feature matrix only. No `Class` consulted during fitting.
- `contamination` removed from both model constructors. Both produce continuous anomaly scores.
- Explicit decision rule applied post-hoc: flag the bottom 1% of scores (exactly 300 flags per run on the 30k sample, 2,848 on the full dataset).
- Five iForest configurations: parameter sensitivity (n_estimators, max_samples) plus seed stability (random_state 42/43/44).
- Five LOF configurations: neighbourhood-scale sensitivity (k = 5, 15, 30, 50) plus metric sensitivity (manhattan at k=30).
- Every run stored as a canonical prediction record: `row_id`, continuous `score`, binary `flag`, plus a metadata row recording parameters, seed, runtime, threshold rule.
- Score direction canonicalised: `anomaly_score = -raw_score` so that higher = more anomalous for both detectors, eliminating per-method inversion ambiguity in Phase 4.

### Implementation Notes and Bug Fixes Accepted During Revision
Several implementation critiques were accepted during the revision. They are documented here for completeness, not because they altered the methodology:

| Critique | Resolution |
| :--- | :--- |
| `max_samples='auto'` is mathematically equal to 256 when n_samples > 256. | Amended: alternative value set to 0.05 (5% sub-sample). |
| Storing pandas DataFrames inside a prediction dictionary bloats memory. | Amended: raw NumPy arrays stored, with `uint8` flags and `float32` scores. |
| `del` of local array variables before all references resolved risks namespace confusion. | Amended: cleanup moved to loop boundary. |
| `n_jobs=-1` deadlocks joblib on Colab for LOF. | Amended: `n_jobs=2` (later `n_jobs=1` on full data). |
| `algorithm='auto'` for LOF silently selects `ball_tree` when D > 20; relying on this heuristic is opaque. | Amended: `algorithm='ball_tree', leaf_size=40` set explicitly. |

### Compute Constraint - Colab Free Tier
The revised Phase 3 was first executed on a 30,000-row random unsupervised subsample of FS-A. The sample was drawn without consulting `Class`. The same 30,000 `row_id`s were supplied to all 10 runs (5 iForest + 5 LOF).

LOF on the full 284,807-row matrix deadlocks the Colab free-tier CPU even with `ball_tree`, `n_jobs=1`, and `leaf_size=40`. A second pass on the full dataset was later completed using LOF **Novelty Mode** (`novelty=True`): LOF was fit on a 50,000-row random unsupervised subsample and used `score_samples` to predict anomaly scores for all 284,807 rows. This is a computational compromise with documented consequences (see Phase 4).

### Decision
The 30k subsample run is the **primary Phase 3 artefact** because LOF operates in native `fit_predict` mode there. The 284k full-dataset run is retained as a **scale-sensitivity companion artefact** with the LOF Novelty Mode limitation explicitly flagged. Both are documented; neither is silently dropped.

*Refer - `notebooks/phase3_trackA_modelling_30k.ipynb`, `notebooks/phase3_trackA_modelling_full.ipynb`*

## Phase 4 (Track A) - Label-Informed Validation: Bug Discovery and Correction

**Date:** 2026-10-22

### First Evaluation Run (Buggy)
The first Phase 4 evaluation produced catastrophic metrics: iForest ROC-AUC approx 0.50, AP matching the base fraud rate. The numbers indicated the models were no better than random.

### Root Cause
The Phase 3 predictions were stored in the order of the 30k random subsample. Phase 4 code extracted the matching `row_id`s from `ground_truth_registry.csv` and **sorted them** before merging with the unsorted prediction arrays. The labels were decoupled from the scores they were meant to evaluate. The models had not failed; the evaluation had silently shuffled the answer key.

### Correction
Predictions and ground truth merged into a single Pandas DataFrame on `row_id` as the join key. No array-position alignment permitted downstream. This is the same `row_id`-alignment discipline that the Phase 2 redesign introduced; the bug existed because the first Phase 4 code predated full adoption of that discipline.

### Corrected Phase 4 Results - 30k Sample (47 frauds, 1% threshold = 300 flags)

| Run | Model | Config | AP | ROC-AUC | Prec@1% | Rec@1% | F1@1% | TP |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| IF_003 | iForest | n_est=100, msamp=0.05, seed=42 | 0.3126 | 0.9803 | 0.1000 | 0.6383 | 0.1729 | 30 |
| IF_004 | iForest | n_est=100, msamp=256, seed=43 | 0.2094 | 0.9787 | 0.1067 | 0.6809 | 0.1844 | 32 |
| LOF_004 | LOF | k=50, euclidean | 0.3229 | 0.9536 | 0.1267 | 0.8085 | 0.2190 | 38 |
| LOF_001 | LOF | k=5, euclidean | 0.0024 | 0.5220 | 0.0033 | 0.0213 | 0.0058 | 1 |

(Full 10-run table retained in `phase4_validation_metrics_CORRECTED.csv`.)

### Corrected Phase 4 Results - Full 284k Dataset (492 frauds, 1% threshold = 2,848 flags)

| Run | Model | AP | ROC-AUC | Prec@1% | Rec@1% | F1@1% | TP |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| IF_003 | iForest | 0.2340 | 0.9494 | 0.1113 | 0.6443 | 0.1898 | 317 |
| LOF_004 | LOF (Novelty) | 0.0562 | 0.9070 | 0.0586 | 0.3394 | 0.1000 | 167 |

(Full 10-run table retained in `FULL_phase4_metrics.csv`.)

### Key Findings
1. **iForest is scale-invariant.** Recall on 30k = 63.8%; recall on 284k = 64.4%. AP drops modestly (0.31 to 0.23) but ranking quality remains high. iForest's tree-based isolation paths do not degrade with sample size.
2. **LOF degrades under Novelty Mode.** Recall on 30k native `fit_predict` = 80.9%; recall on 284k Novelty Mode = 33.9%. The 50k density map cannot capture the micro-density fluctuations of the full 284k space. This is the cost of the compute compromise, not a property of the algorithm itself.
3. **LOF neighbourhood-scale sensitivity is dramatic.** On the 30k sample: k=5 -> AP 0.0024, k=50 -> AP 0.3229. The choice of `n_neighbors` is not a tuning detail; it determines whether LOF is useful at all on this data.
4. **iForest flags are 100% false positives when LOF disagrees.** On the 30k sample at 1%: iForest-only flags = 193 observations, 0 frauds. LOF-only flags = 193 observations, 8 frauds. Both-methods flags = 107 observations, 30 frauds (28.0% precision vs 0.16% base rate).

### Decision
Both 30k and 284k results retained as complementary evidence. The 30k run is the methodologically cleaner artefact (native LOF); the 284k run is the scale-stress artefact (LOF Novelty Mode compromise). Neither is silently discarded.

*Refer - `notebooks/phase4_trackA_validation_30k.ipynb`, `notebooks/phase4_trackA_validation_full.ipynb`*

## Phase 5 (Track A) - Diagnostic Analysis and Visualization

**Date:** 2026-10-22 to 2026-10-23

### Scope
Phase 5 was treated as **visualization + quantitative diagnostic analysis**, not a cosmetic plotting exercise. All computations consumed the canonical Phase 3/4 artefacts; no models were refit.

### Quantitative Diagnostics Computed

1. **Stratified bootstrap confidence intervals (2,000 replicates).** Performed for IF_003, IF_004, LOF_004 on AP, ROC-AUC, Precision@1%, Recall@1%, F1@1%. Fraud and legitimate rows resampled separately to preserve imbalance. Example: LOF_004 Recall@1% 95% CI on 30k = [0.6809, 0.9149]; IF_003 = [0.5106, 0.7872]. LOF's worst-case recall exceeds IF's best-case recall, supporting the claim that LOF_004's superiority at 1% is statistically meaningful, not a point-estimate artefact.

2. **Exact hypergeometric overlap test.** Expected random overlap at 1%: 3.0 (30k), 28.48 (284k). Observed: 107 (30k), 457 (284k). Enrichment: 35.67x (30k), 16.05x (284k). P-value reported via `logsf` to avoid underflow: p < 10^-140.30 (30k), p < 10^-396.37 (284k). The consensus overlap is not a chance event.

3. **10x10 pairwise score-correlation matrix (Spearman).** IF<->IF Spearman approx 0.93; LOF<->LOF Spearman varies with k; IF<->LOF Spearman approx 0.37. The two methods produce substantially different anomaly rankings.

4. **10x10 pairwise top-1% Jaccard matrix.** Visualises intra-method stability vs inter-method disagreement in one compact figure.

5. **Multi-threshold agreement analysis.** At 0.1%, 0.2%, 0.5%, 1%, 2%, 5% top-k. At 0.1% on 30k: iForest-only captures 11 unique frauds, LOF-only captures 10, both capture 3. At 1%: iForest-only captures 0, LOF-only captures 8. iForest dominates at the extreme edge; LOF dominates as the budget expands. This is the most informative single table in the project.

6. **PCA explained variance.** PC1 + PC2 capture a modest fraction of total variance (documented in plot captions). All PCA visualisations are explicitly labelled as lossy projections, not as faithful geometry.

### Visualizations Produced
Eight diagnostic figures produced for each of 30k and 284k runs (16 total), saved as high-resolution PNGs:

1. Precision-Recall curves (5 IF + 5 LOF, best runs highlighted)
2. Fraud discovery curve (recall vs review budget) + precision vs budget
3. Hypergeometric null distribution with observed overlap marked
4. 10x10 Spearman correlation heatmap
5. 10x10 top-1% Jaccard heatmap
6. Top-k Jaccard curve (0.1% to 5%)
7. Rank-vs-rank scatter (IF percentile vs LOF percentile, agreement groups highlighted)
8. PCA agreement map (Both / IF-only / LOF-only / Neither, with flagged-only overlay)

### Decision
Phase 5 closed. No additional visualisations or computations will be added unless Phase 7 gap analysis identifies a specific need.

*Refer - `notebooks/phase5_trackA_diagnostics_30k.ipynb`, `notebooks/phase5_trackA_diagnostics_full.ipynb`*

## Phase 6 (Track A) - Cross-Method Consistency Analysis

**Date:** 2026-10-23

### Scope
Phase 6 investigated whether iForest and LOF identify the same observations or different forms of unusualness, and whether their agreement is greater than chance.

### Primary Findings (30k sample, IF_003 vs LOF_004)

| Metric | Value | Interpretation |
| :--- | :--- | :--- |
| Spearman rank correlation (IF vs LOF) | 0.37 | Substantially different rankings; positive but far from agreement |
| Top-1% Jaccard | 0.2170 | ~22% of flagged items overlap |
| Top-0.5% Jaccard (peak) | ~0.27 | Agreement strongest at the extreme edge |
| Expected random overlap | 3.0 | - |
| Observed overlap | 107 | 35.67x enrichment |
| Hypergeometric p-value | < 10^-140 | Overlap is not chance |

### Agreement-Group Composition (30k, 1% threshold)

| Group | Count | Fraud | Fraud % | Recall Contribution |
| :--- | :--- | :--- | :--- | :--- |
| Both | 107 | 30 | 28.04% | 63.83% |
| iForest-only | 193 | 0 | 0.00% | 0.00% |
| LOF-only | 193 | 8 | 4.15% | 17.02% |
| Neither | 29,507 | 9 | 0.03% | 19.15% |

### Five Questions Answered (per the Phase 6 framework)

1. **Are the two methods producing similar anomaly rankings?** No. Spearman approx 0.37 confirms substantially different rankings, consistent with their different detection mechanisms.
2. **How much do their highest-ranked observations overlap?** Modestly. Jaccard peaks at ~0.27 (top 0.5%) and declines as k increases.
3. **Is the overlap greater than expected by chance?** Yes, overwhelmingly. 35.67x enrichment on 30k, 16.05x on 284k, with p-values so extreme they require `logsf` to express.
4. **When they disagree, which method-specific groups contain the known frauds?** On 30k: iForest-only = 0 frauds (100% false positives); LOF-only = 8 frauds; Both = 30 frauds (28% precision). The intersection is the highest-precision group.
5. **Is the disagreement caused by fundamentally different anomaly definitions, or by LOF's neighbourhood-scale sensitivity?** Both. LOF's k-sensitivity is dramatic (AP ranges from 0.0024 at k=5 to 0.3229 at k=50 on 30k). Even at the best k, however, the IF<->LOF Spearman remains ~0.37, indicating the methods respond to different geometric properties of the data, not merely to different scale parameters.

### Interpretive Discipline Applied
Per external review: the finding supports "the two methods identify substantially different high-anomaly populations, consistent with their different detection mechanisms." It does **not** support the stronger mechanistic claim that "LOF catches local-density anomalies invisible to iForest's isolation paths." The latter is an interpretation of why the algorithms disagree, not something the overlap experiment directly establishes.

Similarly: "the consensus group had approximately 179x the sample's baseline fraud prevalence" is defensible. "The consensus detector is 179x more accurate" is not, and is not claimed.

### Decision
Phase 6 closed. No score fusion or ensemble construction attempted. Per framework guidance, understanding *why* the methods disagree precedes any attempt to combine them.

*Refer - `notebooks/phase6_trackA_consistency.ipynb`*

## Phase 6a (Track A) - 30k vs 284k Comparison

**Date:** 2026-10-23

### Purpose
To document the effect of the LOF Novelty Mode compute compromise by comparing the 30k native-LOF run against the 284k Novelty-LOF run on identical configurations.

### Headline Comparison

| Run | Metric | 30k (native LOF) | 284k (LOF Novelty) |
| :--- | :--- | :--- | :--- |
| IF_003 | AP | 0.3126 | 0.2340 |
| IF_003 | Recall@1% | 0.6383 | 0.6443 |
| LOF_004 | AP | 0.3229 | 0.0562 |
| LOF_004 | Recall@1% | 0.8085 | 0.3394 |
| Consensus | Observed overlap | 107 | 457 |
| Consensus | Enrichment vs random | 35.67x | 16.05x |

### Findings
1. **iForest is scale-robust.** Recall essentially identical (63.8% to 64.4%). AP drops modestly. The algorithm's tree-based isolation does not depend on native density estimation over the full sample.
2. **LOF degrades sharply under Novelty Mode.** AP drops 5.7x, recall drops 2.4x. The 50k density map learned by LOF in Novelty Mode cannot represent the micro-density structure of the full 284k space. This is the cost of the Colab compute constraint, not a property of LOF on this data.
3. **Consensus enrichment dilutes with scale but remains extreme.** 35.67x to 16.05x. Expected random overlap grows quadratically with k; observed overlap grows sub-quadratically. The consensus signal remains overwhelmingly non-random (p < 10^-396 on 284k).

### Decision
The 30k run remains the **primary methodological artefact** for LOF characterization. The 284k run is the **scale-stress companion**. Both are reported; the LOF Novelty Mode limitation is documented in Phase 7.

## Current Status (as of 2026-10-23)

### Stream A - COMPLETE (Phases 1-6)
- Phase 1: Data acquired and verified. (Done)
- Phase 2: Two feature-space variants produced (FS-A primary, FS-B sensitivity). (Done)
- Phase 3: 10 runs (5 iForest + 5 LOF) on 30k sample; 10 runs on 284k full dataset (LOF Novelty Mode). (Done)
- Phase 4: Label-informed validation on both 30k and 284k. Alignment bug discovered and corrected. (Done)
- Phase 5: Bootstrap CIs, hypergeometric test, 10x10 matrices, multi-threshold analysis, 8 diagnostic plots per scale. (Done)
- Phase 6: Cross-method consistency analysis with five-question framework answered. (Done)

### Stream B - Phase 1 COMPLETE, Phase 2 IN PROGRESS
- Phase 1: PMGSY-III six-state dataset accepted (9,634 unique records after dedup). Adversarial validation performed. (Done)
- Phase 2: Extended EDA initiated. Provisional data-handling approach documented. In progress.

### Phases 7 and 8 - NOT YET STARTED
- Phase 7 (Limitations, Gap Analysis, Domain Transfer Conditions): to be drafted after Stream B Phase 2-6 completion, or as a single-stream gap analysis if Stream B proves non-viable.
- Phase 8 (Documentation, Reproducibility, Provenance Finalization): this log is the living draft of that phase.

### Outstanding Tensions to Resolve
1. The LOF Novelty Mode compromise on 284k is methodologically defensible but limits the strength of full-scale LOF claims. The 30k native-LOF run is the cleaner artefact and should be the primary citation for LOF behaviour.
2. The first Phase 4 alignment bug, while corrected, is a documented instance of the kind of array-position fragility the Phase 2 `row_id` redesign was meant to prevent. It is retained in this log as evidence that the redesign was necessary, not optional.
3. Stream B (PMGSY-III) has no labels. Phase 4 for Stream B will be score-distribution + manual top-N inspection only. This is anticipated by the framework but lowers the analytical ceiling for that stream.
4. The scope claim for Stream B is "pipeline reusability demonstration," not "domain anomaly findings." This must be respected in Phase 7 to avoid overclaiming.

---

*End of Stream A execution trail. Stream B execution trail will be appended as Phase 2 progresses.*

## GitHub Publication Strategy (Decision Deferred)

**Date:** 2026-10-24

### Context
The project will be published to a public GitHub repository as a portfolio piece. Three substantive decisions are required before push: data file strategy, Drive link handling, and PMGSY redistribution.

### Decisions Taken
1. **Repository audience:** Portfolio piece. Will live on public GitHub long-term. Polish, README quality, and reproducibility matter.
2. **Repository visibility:** Public.
3. **Drive link policy:** Personal Google Drive links will NOT appear in the public repo. They leak account metadata, are fragile to reorganisation, are not version-controlled, and read as unprofessional. The notebook will use `os.environ.get('STORAGE_DIR', './data')` so it runs anywhere without exposing personal paths.

### Decisions Deferred
1. **Large data file strategy (ULB raw, FS-A/B, predictions pickle):** Three options remain open:
   - **Pure regeneration (preferred default):** commit only code + small final results; provide `scripts/download_ulb.sh` using Kaggle API; derived artifacts regenerated by running the pipeline.
   - **Hugging Face Datasets hosting:** host derived artifacts on a free HF dataset repo; README links to HF.
   - **Git LFS:** commit everything via LFS; bandwidth-capped, history hard to clean.

   Decision will be taken at Phase 8 (Documentation and Reproducibility Finalisation), after Stream B is complete and the full project scope is known.

2. **PMGSY-III redistribution:** Source attribution and public-good framing have been documented (Section: Stream B Update). India's Government Open Data License (GODLI) permits redistribution with attribution, but redistribution on GitHub is NOT confirmed. **Default stance until verified:** provide a `scripts/download_pmgsy.sh` pointing to data.gov.in, do not commit the raw CSV.

### Constraints Locked Regardless of Deferred Decisions
- No personal Drive links in any committed file.
- No raw ULB data re-hosted (Kaggle is the canonical source; ODbL license respected).
- No PMGSY raw CSV committed until license verified.
- Notebook outputs stripped before commit (`jupyter nbconvert --clear-output --inplace`).
- All paths parameterised via environment variables.
- `provenance_log.md` committed as a first-class artifact, not an appendix.

### Decision
Decisions deferred to Phase 8. Constraints above are locked now to prevent rework later.

*Refer - to be cross-linked to Phase 8 documentation notebook when finalised.*

---

## 2026-11-05 â€” Phase 4 Evaluation Layer Migration (Stream A, Stage 2)

**Context:** continuation of the Stage 1 pipeline migration. Phase 3 was frozen and its canonical artifacts (`results/stream a/phase 3/phase3_canonical_predictions.pkl`, `phase3_run_metadata.csv`) are the read-only source of truth; ground truth lives separately at `data/processed/stream-a/labels/ground_truth_registry.csv` (284,807 row_ids, 492 positives; 47 positives inside the 30k primary sample).

### What was implemented
- `src/mplad/stream_a/phase4.py` â€” the label-based evaluation compute layer: input validation (registry / Phase 3 metadata / prediction bundle), row_id alignment, per-run metric computation, orchestration (`run_phase4_evaluation`, `collect_phase4_preflight`), and a post-hoc reference-comparison helper. It imports only `sklearn.metrics` â€” no detector is ever constructed, fitted or refitted.
- `src/mplad/common/manifest.py` â€” new additive SHA-256 manifest utilities (build/save/load/strict verify). The hardened Stage 1 Phase 3 has no manifest generation, so Phase 4 handles its inputs as a **legacy unmanifested pair**: strict structural validation, input SHA-256 hashes recorded in `phase4_run_metadata.json`, and an explicit statement that manifest verification was NOT performed. If a `phase3_commit_manifest.json` is ever placed next to the artifacts, Phase 4 verifies it (hash + size + coverage of both consumed files) before consuming anything. Phase 4 publishes its own `phase4_commit_manifest.json` over its outputs.
- `scripts/run_phase4.py` â€” CLI with preflight-by-default, explicit `--execute`, `--output-dir`, `--overwrite`, input path overrides, and an optional `--reference-metrics` post-hoc acceptance comparison.
- `tests/test_phase4.py` â€” 69 lightweight tests on synthetic fixtures covering all twenty required cases, including the explicit test that fails if labels are aligned by array position instead of `row_id`, hand-verified AP/ROC-AUC/confusion values, flag-usage (never recomputed), no-fitting (poisoned sklearn entry points), dry-run no-writes, output protection, and both manifest paths.
- `docs/phase4_contract.md` â€” the full input/output contract (this migration's schema reference).

### Additive changes to shared modules (no Phase 3 behaviour change)
- `config.py`: Phase 4 path constants (`DEFAULT_GROUND_TRUTH_PATH`, `PHASE3_PREDICTIONS_PATH`, `PHASE3_RUN_METADATA_PATH`, `DEFAULT_PHASE4_OUTPUT_DIR`, artifact filenames, `PHASE3_CANONICAL_RUN_IDS`, `LABEL_COLUMN`, `VALID_LABEL_VALUES`, `PHASE3_MANIFEST_FILENAME`). All Phase 3 constants untouched.
- `io.py`: new generic guarded writers `save_dataframe_csv` and `save_json`. Existing Phase 3 functions byte-identical (Phase 3 suite re-run: 40 passed, 1 environment-dependent skip).

### The historical alignment bug, structurally prevented
The original Colab Phase 4 sorted ground truth by `row_id` while prediction arrays stayed in draw order, then aligned by array position â€” every metric was wrong until the audit fix. The migrated layer joins predictions and labels **on `row_id` with `validate="one_to_one"`**, preserves the prediction sequence end-to-end, and hard-rejects unmatched prediction IDs, duplicate IDs, and incomplete joins. A dedicated regression test (`test_positional_alignment_would_fail_this_test`) fails under any positional implementation.

### Score orientation made explicit
`native_score` (Phase 3 storage convention, lower = more anomalous) is kept alongside `anomaly_score = -native_score` (canonical, higher = more anomalous) in the evaluation dataset; ranking metrics use `anomaly_score`; fixed-threshold metrics use the saved Phase 3 flags exactly as supplied â€” the 1% rule is never recomputed or re-optimised in Phase 4.

### Outputs (separate location; historical Phase 4 results untouched)
`results/stream a/phase 4/reproduction/`: `phase4_evaluation_dataset.csv` (long form, one row per (run_id, row_id), 300,000 rows on the canonical experiment), `phase4_metrics.csv` (one row per run, metadata passthrough + metrics), `phase4_run_metadata.json` (provenance: input hashes, manifest status, environment, `models_fitted: 0`), `phase4_commit_manifest.json`.

### Verification performed
- `python -m compileall -q src scripts tests` â€” clean.
- `python -m pytest -q tests/test_phase4.py` â€” 69 passed (synthetic fixtures only).
- `python -m pytest -q tests/test_phase3.py` â€” 40 passed, 1 skipped (optional canonical-file cross-check; the canonical results directory is absent on the migration machine) â€” no Phase 3 regression.
- End-to-end synthetic validation: a genuine ten-run Phase 3 execution on synthetic FS-A data, consumed through the full Phase 4 CLI (preflight â†’ execute), with the output manifest re-verified and the legacy-input provenance inspected.
- No execution against the real registry has occurred yet on the migration machine; the acceptance reference checks (IF_003 / LOF_004) are documented in `docs/phase4_contract.md` Â§8 and are to be confirmed by running `scripts/run_phase4.py --execute` where the canonical artifacts live.

### Out of scope (next stages)
Phase 4 notebook, Phase 5 diagnostics/bootstrapping/plots, Phase 6 agreement analysis, the separately-named larger-experiment runner, and the Streamlit app.

---

## 2026-11-05 â€” Phase 5A Quantitative Diagnostics Migration (Stream A, Stage 3)

**Context:** continuation of the staged migration. Phase 3 is frozen; Phase 4 is migrated, hardened and independently executed on the canonical 30,000-row dataset (outputs under `results/stream a/phase 4/reproduction/`, contract in `docs/phase4_contract.md`). Phase 5A consumes those verified outputs read-only.

### What was implemented
- `src/mplad/stream_a/phase5_analysis.py` â€” the quantitative diagnostic compute layer: input validation (Phase 4 dataset schema, provenance JSON, optional Phase 4 manifest verification with honest legacy fallback), cross-run alignment extraction, and the seven analyses â€” (A) 2,000-replicate class-stratified bootstrap CIs for IF_003/IF_004/LOF_004 plus the paired LOF_004âˆ’IF_003 comparison on shared replicate indices; (B) 10Ã—10 Spearman matrix on `anomaly_score`; (C) 10Ã—10 Jaccard matrix on the saved 1% flags; (D) multi-threshold agreement at 0.1â€“5% (canonical 1% = saved flags, others derived top-k under a documented tie policy); (E) hypergeometric overlap with sf/logsf tail probabilities; (F) agreement-group composition (validated exhaustive partition); (G) fraud-discovery curve data for all ten runs. Imports only `sklearn.metrics` and `scipy.stats` â€” no detector is ever constructed or fitted, no threshold is ever reselected, no plot is produced.
- `scripts/run_phase5_analysis.py` â€” CLI with preflight-by-default, explicit `--execute`, `--output-dir`, `--overwrite`, input overrides, and non-canonical-parameter warnings for `--n-replicates`/`--bootstrap-seed`.
- `tests/test_phase5_analysis.py` â€” 95 lightweight tests on synthetic fixtures covering every required case: input schema/run completeness; cross-run row-ID consistency (including the positional-alignment regression test); finite scores/binary flags; bootstrap determinism, exact stratified prevalence, paired identical indices, saved-flag policy (no threshold reselection); hand-computed metric examples; pairwise matrix diagonals; Jaccard; exact agreement-group partition; deterministic multi-threshold tie handling; hypergeometric tail against hand and scipy references; discovery-curve correctness and post-hoc-label use; no-fitting (poisoned entry points); preflight no-writes; overwrite protection; manifest paths; input/output provenance.
- `docs/phase5_analysis_contract.md` â€” the full input/analysis/output contract (this stage's schema reference).

### Additive changes to shared modules (no Phase 3/4 behaviour change)
- `config.py`: appended Phase 5A constants (input paths into the Phase 4 reproduction directory, output directory `results/stream a/phase 5/reproduction/`, artifact filenames, frozen bootstrap protocol â€” 2,000 replicates, seed 42 via a new PCG64 stream, highlighted runs IF_003/IF_004/LOF_004, paired comparison LOF_004âˆ’IF_003 â€” the multi-threshold grid, and the overlap pair). All Phase 3/Phase 4 constants untouched; Phase 3/4 suites re-run clean.

### Methodological protections carried up from earlier phases
- **Cross-run positional-alignment guard**: every pairwise analysis compares runs positionally, which is valid only because all runs share the identical `row_id` sequence. Phase 5A hard-rejects any run whose stored sequence differs in values or order â€” the Phase 4 label-misalignment bug class cannot reappear one layer up.
- **Saved-flag policy**: the canonical 1% flags are consumed exactly as supplied everywhere (Jaccard, hypergeometric overlap, agreement groups, and the fixed-threshold metrics inside every bootstrap replicate). Derived top-k masks at other thresholds use a documented deterministic tie policy (descending `anomaly_score`, ties by ascending dataset position) and are kept strictly separate from canonical flags.
- **Exploratory status recorded**: IF_003/IF_004/LOF_004 and their pairings were highlighted after inspecting label-informed Phase 4 results; the caveat is embedded in the provenance JSON and printed by the runner. Historical paired intervals are recalculated (recorded seed and protocol), never hardcoded or forced to match.
- **Interpretation discipline**: the hypergeometric result is stated only against the independent uniform-selection null; no claim that flagged observations are true anomalies.

### Outputs (separate location; historical Phase 5 results untouched)
`results/stream a/phase 5/reproduction/`: `phase5_bootstrap_metrics.csv` (15 rows), `phase5_paired_bootstrap_differences.csv` (5 rows), `phase5_pairwise_spearman.csv` (10Ã—10), `phase5_pairwise_jaccard_1pct.csv` (10Ã—10), `phase5_multithreshold_agreement.csv` (66 rows), `phase5_hypergeometric_overlap.csv` (1 row), `phase5_agreement_groups.csv` (4 rows), `phase5_fraud_discovery_curve.csv` (300,000 rows on the canonical experiment), `phase5_run_metadata.json` (input hashes, manifest status, seeds, replicate count, software versions, analytical conventions, selection caveat, `models_fitted: 0`), `phase5_commit_manifest.json` (9 artifacts).

### Verification performed
- `python -m compileall -q src scripts tests` â€” clean.
- `python -m pytest -q tests/test_phase5_analysis.py` â€” 95 passed (synthetic fixtures only).
- `python -m pytest -q tests/test_phase3.py` â€” 40 passed, 1 skipped (environment-dependent canonical-file cross-check) â€” no Phase 3 regression.
- `python -m pytest -q tests/test_phase4.py` â€” 69 passed â€” no Phase 4 regression.
- End-to-end validation at canonical scale: a structurally exact synthetic replica of the Phase 4 output set (300,000 rows, 47 frauds, ten runs, 300 saved flags per run, manifest present) driven through the full CLI (preflight â†’ execute with the full 2,000-replicate protocol â†’ artifact/manifest/structural verification â†’ overwrite protection). Runtime for the canonical bootstrap: â‰ˆ 95 s.
- No execution against the real Phase 4 outputs has occurred on the migration machine; the acceptance reference checks (section 7 of `docs/phase5_analysis_contract.md`: 30k/47/300 flags, intersection 107, union 493, expected 3.0, enrichment â‰ˆ 35.67Ã—, log10 p â‰ˆ âˆ’140.30, groups 107/193/193/29,507 with frauds 30/0/8/9, Spearman â‰ˆ 0.37, Jaccard â‰ˆ 0.217) are documented for comparison and are to be confirmed by running `scripts/run_phase5_analysis.py --execute` where the canonical Phase 4 outputs live.

### Out of scope (next stages)
Phase 5B plotting (consumes the tables produced here), Phase 6 agreement analysis, the 284,807-row LOF novelty-mode companion (to be considered separately, retaining its novelty-mode qualification), and the Streamlit app.

---

## 2026-11-05 â€” Phase 5B Visualization Layer Migration (Stream A, Stage 4)

**Context:** continuation of the staged migration. Phase 3 is frozen; Phase 4 is migrated, hardened and independently executed on the canonical 30,000-row dataset; Phase 5A is migrated, hardened and independently executed with the full 2,000-replicate bootstrap protocol (outputs under `results/stream a/phase 5/reproduction/`, contract in `docs/phase5_analysis_contract.md`). Phase 5B consumes those verified outputs, the Phase 4 row-level evaluation dataset and the FS-A feature matrix read-only, and renders the quantitative half's visual counterpart.

### What was implemented
- `src/mplad/stream_a/phase5_plots.py` â€” the visualization layer: input validation (Phase 5A table schemas, optional Phase 5A and Phase 4 manifest verification with honest legacy fallback, cross-snapshot hash consistency between the Phase 5A provenance record and the consumed Phase 4 dataset, row-level cross-checks of flagged counts / observed intersection / group composition / saved Jaccard, FS-A join coverage) and the eight authoritative figure builders â€” (1) precision-recall curves with AP and the prevalence reference; (2) two-panel fraud discovery with the correctly scaled random baselines (recall = reviewed fraction, precision = prevalence); (3) the hypergeometric log-PMF over the full valid support with the observed/expected intersections and the log-space tail annotation (never zero); (4) the zero-centred full-range Spearman matrix; (5) the full-range saved-flag Jaccard matrix; (6) top-k Jaccard curves (canonical 1% = saved flags, other budgets = derived top-k under the Phase 5A tie policy, within-family means excluding the diagonal); (7) the rank-versus-rank percentile map (percentile = 1 âˆ’ descending rank/n, 0.99 boundaries, hexbin Neither + labelled overlays); (8) the PCA agreement map (FS-A joined on row_id, stored scaling untouched, exact full-SVD PCA fitted on the joined sample, explained variance reported, lossy-projection disclaimer). Imports only `sklearn.metrics` and `sklearn.decomposition.PCA` â€” no detector is ever constructed or fitted.
- `scripts/run_phase5_plots.py` â€” CLI with preflight-by-default, explicit `--execute`, `--overwrite`, `--output-dir`, input overrides, `--dpi`, and a deliberate-only `--expected-sample-size` override (the canonical 30,000-observation / ten-run requirement is enforced by default). Non-interactive Agg backend selected before the plotting module is imported.
- `tests/test_phase5_plots.py` â€” 63 lightweight tests on synthetic fixtures (a structurally exact world whose Phase 5A outputs are produced by the real frozen `phase5_analysis` code): input/schema/manifest validation, tamper rejection on both manifests, canonical sample-size enforcement, ten-run enforcement, cross-snapshot hash rejection, score orientation (AP on `anomaly_score` vs mirrored), saved-flag operating points, correct random baselines, hypergeometric full support and no-zero tail annotation, matrix rendering with full colour ranges, top-k derivation and tie handling identical to Phase 5A, diagonal exclusion, the exact 0.99 percentile boundary at n=10,000, four-group membership and counts, PCA row alignment under a shuffled FS-A, Neither-only sampling with a fixed seed, explained-variance reporting, no-fitting (poisoned detector entry points + source scan), input immutability (SHA-256 before/after), preflight no-writes, output protection, overwrite semantics, render-failure publishes nothing, publication rollback restores originals byte-identical, manifest-published-last coverage, catalog/metadata contents, and four CLI subprocess tests.
- `docs/phase5_figure_catalog.md` â€” the per-figure contract: purpose, inputs, statistical conventions, axis definitions, sample/group scope and known interpretation limitations for all eight figures, plus the documented PCA preprocessing semantics and explained-variance reporting.

### Additive changes to shared modules (no Phase 3/4/5A behaviour change)
- `config.py`: appended Phase 5B constants (the figures directory `results/stream a/phase 5/figures/reproduction/`, the eight frozen figure filenames, the catalog/metadata/manifest filenames, input-manifest names, default dpi). All Phase 3/4/5A constants untouched; the Phase 3/4/5A suites re-run clean.

### Methodological protections carried up from earlier phases
- **Snapshot consistency:** the Phase 5A tables and the row-level Phase 4 data must come from the SAME Phase 4 execution â€” enforced by comparing the input SHA-256 recorded in `phase5_run_metadata.json` with the hash of the dataset actually consumed, before anything is rendered.
- **Saved-flag policy:** the canonical 1% flags are consumed exactly as supplied everywhere (figures 1, 5, 6, 7, 8); derived top-k masks at other budgets reuse `phase5_analysis.derive_topk_selection` verbatim (the documented tie policy) and are never written back to any artifact.
- **Interpretation discipline:** the hypergeometric figure states its null and reports the tail in log space; the PCA figure states that it is a lossy 2-D projection fitted on the joined sample with no additional rescaling; the exploratory (post-hoc) status of the highlighted runs is recorded in the plot metadata and printed by the runner.
- **Publication safety:** staged rendering with PNG-magic verification, backup/rollback on replacement, the commit manifest published last, and a new output namespace so no historical Phase 5 figure is ever deleted or overwritten.

### Outputs (separate location; historical figures untouched)
`results/stream a/phase 5/figures/reproduction/`: `phase5_plot1_precision_recall.png` â€¦ `phase5_plot8_pca_agreement.png` (exactly the eight authoritative figures â€” no alternates, no ninth figure), `phase5_figure_catalog.csv`, `phase5_plot_metadata.json`, `phase5_plot_commit_manifest.json` (10 artifacts).

### Verification performed
- `python -m compileall -q src scripts tests` â€” clean.
- `python -m pytest -q tests/test_phase5_plots.py` â€” 63 passed (synthetic fixtures only, non-interactive Agg backend).
- `python -m pytest -q tests/test_phase3.py` â€” 40 passed, 1 skipped (environment-dependent canonical-file cross-check) â€” no Phase 3 regression.
- `python -m pytest -q tests/test_phase4.py` â€” 69 passed â€” no Phase 4 regression.
- `python -m pytest -q tests/test_phase5_analysis.py` â€” 95 passed â€” no Phase 5A regression.
- End-to-end validation at canonical scale on a structurally exact synthetic replica (30,000 observations, 47 frauds, ten runs, genuine 5A outputs incl. the 2,000-replicate bootstrap) driven through the full CLI (preflight â†’ execute â†’ overwrite protection â†’ manifest re-verification), with visual inspection of all eight rendered figures.
- No execution against the real Phase 5A outputs has occurred on the migration machine; the acceptance reference checks (Spearman â‰ˆ 0.37, Jaccard â‰ˆ 0.217, observed 107 / expected 3.0 / enrichment â‰ˆ 35.67Ã— / log10 p â‰ˆ âˆ’140.30, groups 107/193/193/29,507 with frauds 30/0/8/9, paired precision difference +0.0267 with 95% CI [0.0066, 0.0489]) are documented as validation references â€” none is hardcoded in the plotting code â€” and are to be confirmed by running `scripts/run_phase5_plots.py --execute` where the canonical Phase 5A outputs live.

### Out of scope (next stages)
Phase 6 agreement analysis, the 284,807-row LOF novelty-mode companion (to be considered separately, retaining its novelty-mode qualification), and the Streamlit app.

## 2026-11-06 — Phase 7 Limitations and Governance Synthesis (Stream A, Stage 6, Final)

**Context:** The final stage of Stream A. Phase 7 is a documentation-only layer that synthesizes the engineering, methodological, and legal boundaries of the project.

### What was implemented
- docs/phase7_synthesis.md — The authoritative record of the project's limitations, computational compromises (30k native LOF vs. 284k Novelty Mode), proxy-to-domain gap analysis, and licensing compliance (ODbL v1.0 / GODL-India). 
- This document locks the interpretive parameters that any downstream presentation layer (e.g., Streamlit) must enforce.

### Verification performed
- Synthesis generated entirely from the validated Phase 2-6 frozen artifacts and the established decision ledger.
- Stream A is now conceptually and administratively closed. Next step is application architecture.
