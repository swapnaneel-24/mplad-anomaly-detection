# **PROJECT PIPELINE FRAMEWORK**

*Note: This is a structural guide, not a rigid specification. Each phase includes decision points where the path may branch based on what the data reveals. Unexpected challenges are expected; the framework's purpose is to ensure that when they arise, they are encountered within a known context rather than in ad-hoc isolation.*

# **PHASE 0 — Problem Reframing and Scope Locking**

**Purpose:** Establish the precise claims the project will and will not make, before any data is loaded.

## **Actions**

* Write (in definitive detail) scope statement using the qualified language established in the decision log: methodological proxy, not domain application.  
* List, in plain language, the three to five questions the project will actually answer (e.g., "How do iForest and LOF compare on this benchmark under varying contamination rates?" rather than "What are the anomaly patterns in MPLAD fund utilization?").  
* Identify what "success" looks like concretely: not a detection rate, but the quality of the comparative analysis and the rigor of the limitations discussion.

&nbsp;

**Output:** A locked scope document. Refer back to it whenever a later decision risks scope creep or overclaiming.

&nbsp;

Decision point: If you cannot write a scope statement that is both honest and substantively interesting, the project definition itself needs revision before proceeding. Do not proceed with a scope you cannot defend.

# **PHASE 1 — Data Acquisition and Baseline Viability (Dual Stream)**

**Purpose:** Secure the proxy benchmark and acquire a viable domain-relevant government scheme dataset through initial ingestion, basic exploratory data analysis (EDA), and minimal preliminary preprocessing.

*(Scope Boundary: Advanced EDA, comprehensive cleaning/transformation, and feature engineering are strictly reserved for Phase 2).*

**Operational Constraint (Minimal Intervention Principle):**

Run basic structural and compatibility checks across both streams. Modifications at this stage are restricted solely to what is strictly necessary to evaluate dataset viability and baseline model compatibility—no further processing or engineering may occur in this phase.

## **Stream A — Proxy Benchmark (ULB/Kaggle)**

* Download and verify file integrity (row count: 284,807; column count: 31; class distribution: 492 positive).  
* Run baseline integrity check; retain without structural modification if baseline standards are satisfied.  
* Record source URL, access date, and license terms in the provenance log.

## **Stream B — Domain Supplementary Data (Indian Public Fund / Government Scheme)**

Identify candidate datasets reflecting public fund flows (e.g., MPLAD, state-level expenditures, DBT, or infrastructure schemes).

**Viability & Compatibility Criteria:**

* Contains at least one continuous numeric variable plausibly reflecting fund allocation or expenditure (amount, cost, disbursement).  
* Contains at least one categorical variable enabling grouping (district, state, agency, scheme component).  
* Possesses sufficient sample size to support unsupervised anomaly detection (\> several hundred rows).  
* Demonstrates structural compatibility with the intended anomaly detection architectures (e.g., iForest, LOF).

**Screening, Incompatibility Check, and Pivot Protocol:**

* Perform basic EDA and minimal preprocessing to assess primary candidate compatibility.  
* If the primary candidate is incompatible with model requirements or otherwise non-viable, systematically screen shortlisted alternative government scheme datasets against the criteria.  
* Adopt a viable alternative, only after validating that it satisfies the baseline criteria under minimal initial preprocessing.

**Output:** Two verified datasets (Stream A benchmark and Stream B viable scheme data, or a documented null search), each paired with a basic data card (source, schema, dimensions, baseline distribution checks).

**Decision point:** If the primary Stream B source fails basic compatibility checks, pivot to alternative shortlisted government scheme datasets that satisfy the criteria. If no shortlisted scheme proves viable, document the null finding and prepare to revert to single-track execution with an expanded gap analysis in Phase 7\.

# **PHASE 2 — Preprocessing (Parallel Tracks)**

Purpose: Prepare each dataset for methodological application. Demonstrate pipeline reusability across structurally different data.

## **Track A — Proxy Benchmark**

Verify no missing values (expected: none). Scale Amount (and optionally Time) using a method appropriate for the detectors — standard scaling is conventional, but consider whether robust scaling (median/IQR) is more appropriate given the extreme imbalance and potential amount outliers. Retain V1–V28 as-is; do not re-apply PCA. Document the scaling choice and its rationale.

## **Track B — Domain Data (if available)**

* Profile the data: missing values by column, variable types, cardinality of categorical fields, distribution of numeric fields.  
* Handle missing values — document the strategy per column (imputation, exclusion, flagging) and why.  
* Encode categorical variables — document the method (label encoding, one-hot, target encoding if labels exist) and why.  
* Scale numeric variables — use the same scaling logic as Track A for consistency.  
* If the dataset is very small or very dirty, note this explicitly; do not over-engineer preprocessing to compensate for data inadequacy.

&nbsp;

**Output:** Two clean, scaled feature matrices (X\_proxy, X\_domain) with corresponding label vectors where available (y\_proxy, y\_domain). A preprocessing log documenting every transformation with rationale.

&nbsp;

Decision point: If Track B data proves too degraded for meaningful analysis after preprocessing, document the degradation and proceed with Track A only. The attempt itself is the artifact.

# **PHASE 3 — Methodological Execution**

**Purpose:** Apply iForest and LOF to each dataset across multiple parameter settings.

## **Detector 1 — Isolation Forest**

Define a parameter grid. At minimum, vary:

&nbsp;

* **contamination:** e.g., 0.001, 0.005, 0.01, 0.017 (matching the known fraud rate), 0.05  
* **n\_estimators:** e.g., 100, 200, 500  
* **max\_samples:** default (256) and one alternative (e.g., 'auto' or a fraction of dataset size)

&nbsp;

Fix `random_state` for reproducibility; note that this eliminates stochastic variation and that real-world deployment would not have this luxury. For each parameter combination, record: anomaly labels, anomaly scores, execution time.

## **Detector 2 — Local Outlier Factor**

Define a parameter grid. At minimum, vary:

&nbsp;

* **n\_neighbors:** e.g., 5, 10, 20, 50  
* **contamination:** same values as iForest for comparability  
* **metric:** 'euclidean' (default) and at least one alternative if dimensionality warrants (e.g., 'minkowski') — though on PCA-reduced data this is less critical.

&nbsp;

*Note: LOF in scikit-learn does not natively support fit/predict separation for novelty detection in all configurations; decide whether you are using it in outlier detection mode (fit on full data) or novelty mode (fit on inliers only), and document this choice.*

&nbsp;

For each parameter combination, record: anomaly labels, negative outlier factors (scores), execution time.

## **Cross-dataset application**

If Track B data exists, run both detectors on it using the same parameter grids (adjusted for class imbalance ratio if known). If Track B has no labels, evaluation for this track will be score-based and qualitative rather than metric-based.

&nbsp;

Output: A structured results store (dictionary, DataFrame, or similar) containing all runs, parameters, predictions, and scores. This is the raw material for all subsequent analysis.

&nbsp;

Decision point: If execution time for LOF becomes prohibitive on the full 284k-row proxy dataset at certain parameter combinations, subsample and document the subsampling strategy. Do not silently drop combinations.

# **PHASE 4 — Evaluation**

Purpose: Assess detector outputs using label-informed metrics (where labels exist) and score-based diagnostics (where they do not).

## **For the proxy benchmark (labels available)**

For each parameter combination, compute:

&nbsp;

* **Confusion matrix-derived metrics:** precision, recall, F1. Not accuracy — document explicitly why accuracy is misleading on this class distribution.  
* **AUC-ROC and AUC-PR** (Precision-Recall curve), if sample sizes permit, with a note that AUC-PR is more informative than AUC-ROC under extreme imbalance.  
* **Construct a comparison matrix:** methods × parameter settings × metrics.  
* **Identify the best-performing setting** for each method by each metric. Note whether they agree or conflict (e.g., iForest best by recall but LOF best by precision at different contamination levels).

## **For the domain data (labels may not exist)**

* **Examine score distributions:** histogram or kernel density of anomaly scores for each detector.  
* **Identify top-N flagged observations:** inspect the top-N flagged observations by score manually. Document what makes them unusual in domain terms (e.g., "highest expenditure in a single district," "only constituency with zero completions") — this is where domain interpretability, however limited, enters.  
* **Heuristic validation:** If partial labels or heuristic labels can be constructed (e.g., "flag any entry with expenditure above 3 standard deviations from constituency mean"), compute metrics against these heuristic labels and explicitly note their limitations.

&nbsp;

**Output:** Metric tables for the proxy benchmark. Score distributions and manual inspection notes for the domain data.

&nbsp;

**Decision point:** If the domain data yields no interpretable patterns upon manual inspection, state this directly. A null finding ("the methods flagged observations, but no coherent domain pattern emerged from manual review") is more honest than forcing an interpretation.

# **PHASE 5 — PCA Visualization and Interpretability Assessment**

**Purpose:** Use dimensionality reduction to visually examine the separation (or lack thereof) between detected anomalies and normal observations, and to assess what PCA visualization can and cannot reveal.

## **Actions**

Apply PCA to the scaled feature matrix of each dataset (Track A and Track B separately).

&nbsp;

* For the proxy benchmark, reduce to 2 and 3 components. Plot observations colored by:  
  * True label (fraud/genuine) — to show the ground-truth structure.  
  * iForest prediction (at a selected parameter setting).  
  * LOF prediction (at a comparable parameter setting).  
* For the domain data, reduce similarly and plot colored by detector predictions and by available categorical groupings (district, category, etc.).

## **Visual Assessment**

* Do the detected anomalies form a coherent cluster, or are they scattered?  
* Does visual separation correspond to high precision/recall, or can visually "obvious" outliers still be misclassified?  
* How much of the variance is captured in 2–3 components? If very little, note that the visualization is a severe lossy compression and should not be overinterpreted.

&nbsp;

**Output:** Plots with captions that interpret what is visible and what is not. A brief interpretability assessment: "PCA visualization on this data reveals/does not reveal clear anomaly separation because..."

&nbsp;

Decision point: If 2-component PCA captures very low variance (e.g., \<30%), consider t-SNE or UMAP as supplementary visualizations but explicitly note that these introduce non-linear distortion and are not suitable for quantitative claims — only for hypothesis generation.

# **PHASE 6 — Cross-Method Consistency Analysis**

**Purpose:** Examine where iForest and LOF agree and disagree, and what this implies.

## **Actions**

Compute the overlap between anomaly sets flagged by each method at comparable contamination levels (e.g., both at 0.01 contamination).

&nbsp;

* **For the proxy benchmark**, break down the overlap into:  
  * True positives detected by both.  
  * True positives detected by only one.  
  * False positives detected by both.  
  * False positives detected by only one.  
* **For the domain data**, compute overlap without label breakdown; characterize the disagreed-upon observations.  
* **Examine systematic disagreement:** Determine whether disagreement is systematic (e.g., LOF consistently flags points in dense regions that iForest misses, suggesting local vs. global anomaly sensitivity) or random.  
* **Stability analysis:** If multiple parameter settings produce stable overlap patterns, note this as evidence of consistent detection behavior. If overlap fluctuates wildly with small parameter changes, note this as instability.

&nbsp;

**Output:** Overlap matrices or Venn-style characterizations. A narrative summary of what agreement and disagreement reveal about each method's behavior on this data.

&nbsp;

**Decision point:** If the two methods disagree on nearly everything, this is itself a finding — it suggests that on this data, "anomaly" is method-dependent rather than data-dependent, which has direct implications for any deployment scenario.

# **PHASE 7 — Limitations, Gap Analysis, and Domain Transfer Conditions**

**Purpose:** Synthesize all identified limitations into a structured gap analysis and specify what would be required for legitimate domain application.

## **Actions**

Compile limitations into categories:

&nbsp;

* **Data limitations:** proxy irrelevance, temporal insufficiency, feature uninterpretability, preprocessing triviality.  
* **Method limitations:** iForest assumptions violated or untested (clustered anomalies, contamination sensitivity), LOF dimensionality and neighborhood sensitivity, stochasticity of iForest (mitigated by `random_state` but not in deployment).  
* **Evaluation limitations:** label-informed evaluation is not unsupervised evaluation; metrics on a benchmark do not predict operational performance; no temporal validation.  
* **Domain transfer limitations:** what MPLAD-specific constructs (scheme hierarchy, electoral cycles, multi-stage approval workflow) are entirely absent and cannot be approximated.

&nbsp;

For each category, specify the minimum condition that would need to be met for the limitation to be resolved. For example:

&nbsp;

* *"Feature interpretability requires access to original, unlabeled MPLAD transactional or project-level data with at minimum: sanction amount, completion status, scheme category, implementing agency, constituency identifier, and date of sanction/completion."*  
* *"Temporal validation requires data spanning at least two electoral cycles (approximately 10 years) with time-stamped entries."*

&nbsp;

Discuss false-positive implications specifically: at the observed false-positive rates on the proxy benchmark, what would the absolute number of flagged constituencies/projects be if applied to the full MPLAD dataset (approximately 543 constituencies, thousands of projects annually)? Is this operationally tractable for a human review process?

&nbsp;

Output: A structured limitations and gap analysis section. This is the section that converts the project from a benchmark exercise into an engineering requirements document for future domain application.

&nbsp;

**Decision point:** If the gap analysis reveals that domain transfer would require data that demonstrably does not exist in the public domain, state this. "This analysis identifies the data conditions for responsible domain application; those conditions are not currently met by any known public dataset" is a complete and valid conclusion.

# **PHASE 8 — Documentation, Reproducibility, and Provenance Finalization**

Purpose: Ensure the entire project can be independently reproduced and that the decision trail is complete.

## **Actions**

* Ensure all code is commented, with each major section corresponding to a phase in this framework.  
* Fix all random seeds and library versions in a requirements file or environment specification.  
* Finalize this provenance/decision log with any additions or revisions prompted by execution-phase discoveries.  
* Ensure the scope statement from Phase 0 is consistent with the final claims in the report. If execution reveals that even the reframed claims need further qualification, update both and note the change.

&nbsp;

**Output:** Complete project package: code, data cards, results, visualizations, report, provenance log.

&nbsp;

Decision point: Before submission, re-read the scope statement. If any sentence in the final report would cause you discomfort if read aloud to a technically competent reviewer, revise it. The standard is not perfection — it is defensibility.

&nbsp;

End of Framework.