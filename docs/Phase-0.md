# **PHASE 0 — PROBLEM REFRAMING AND SCOPE LOCKING**

# **0.1 Project Title and Subtitle**

**MPLAD Fund-Utilization Anomaly Pattern Detection Using Unsupervised Learning**

&nbsp;

*Subtitle (to appear on all deliverables):*&nbsp;

***A Comparative Benchmarking Study of Isolation Forest and Local Outlier Factor on Extreme Class Imbalance, with Exploratory Domain Transfer Assessment***

&nbsp;

The subtitle is not decorative. It performs the critical function of immediately qualifying the project's actual scope before any content is consumed. Any reader who encounters the title alone and forms an expectation of domain-specific MPLAD analysis will be corrected by the subtitle before reaching the first paragraph of the report. This is deliberate defensive positioning against the single most likely misreading of this project.

# **0.2 Problem Statement**

## **0.2.1 Domain Motivation**

The Members of Parliament Local Area Development Scheme (MPLADS), introduced in 1993, enables Members of Parliament to recommend developmental works based on locally felt needs, with funds released as grants-in-aid directly to District Authorities. The scheme has been the subject of sustained governance scrutiny. A Comptroller and Auditor General (CAG) report studying 111 sample constituencies found that expenditure of Rs. 161 crore was not supported by any documentation, and in 33.12% of cases where documents existed, execution records were deficient. The Observer Research Foundation has noted persistent issues including poor utilization rates, inadequate monitoring by the Ministry, inadmissible works, and suspected fraud. Research on electoral cycles has further identified systematic patterns of incomplete projects correlating with electoral timing, suggesting that anomalies in MPLAD fund utilization are not merely random irregularities but may exhibit structural, predictable patterns amenable to data-driven detection.

&nbsp;

These concerns establish a legitimate motivation: if transactional or project-level data on MPLAD fund flows were available at sufficient granularity, unsupervised anomaly detection methods could serve as a supplementary screening layer for audit authorities, flagging constituencies, contractors, or expenditure patterns that deviate from normative behavior for subsequent human review.

## **0.2.2 The Methodological Pivot**

No publicly available dataset provides MPLAD fund utilization data at the transactional or project level with the granularity, completeness, and volume required to meaningfully apply and evaluate unsupervised anomaly detection methods. Government portals provide aggregate figures; RTI disclosures are ad-hoc and non-standardized; academic studies use aggregated secondary data from official reports rather than unit-level records. Without unit-level observations (individual projects, individual disbursements, individual sanction orders), the methods under study cannot be applied to the domain of interest in any meaningful sense.

&nbsp;

This project therefore executes a methodological pivot. It selects a well-characterized benchmark dataset — the ULB Credit Card Fraud Detection dataset — that shares one critical structural property with the hypothesized MPLAD problem: extreme class imbalance (0.172% positive rate). It uses this benchmark to comparatively evaluate Isolation Forest and Local Outlier Factor across multiple parameter settings, assess detection consistency, and examine false-positive implications. It then attempts an exploratory application of the same pipeline to any available public fund expenditure data to assess, however preliminarily, whether the methods' behavior on the benchmark bears any relation to their behavior on domain-adjacent data.

&nbsp;

**Side Note:** The term "pivot" is chosen deliberately over "proxy" in this section. "Proxy" describes the dataset's role; "pivot" describes the project's intellectual trajectory. The project begins with a domain motivation and pivots to a methodological benchmark because the domain data condition is unmet. This is a different intellectual move than selecting a proxy from the outset, and the distinction matters for how the project's contribution is characterized. A proxy study implies the domain was always secondary; a pivot implies the domain was primary but the data condition forced a methodological detour. The latter is more honest about intent, even if the executable output is identical.

## **0.2.3 What This Problem Statement Is Not**

This problem statement does not claim that credit card fraud and MPLAD fund misutilization are structurally analogous problems. They are not. Credit card fraud produces point-level transactional outliers in a high-frequency, near-real-time data stream. MPLAD anomalies, if they exist in detectable form, would manifest as project-level patterns in a low-frequency, multi-stage administrative workflow spanning financial years and electoral cycles. The anomaly topologies, temporal structures, feature semantics, and operational constraints are fundamentally different. The sole shared property justifying the benchmark's use is extreme class imbalance, and even this is an approximation rather than an equivalence — the true anomaly rate in MPLAD data is unknown.

# **0.3 Scope Statement**

This project produces a comparative, reproducible benchmarking study of two unsupervised anomaly detection methods (Isolation Forest and Local Outlier Factor) on a standardized imbalanced dataset, with an exploratory assessment of pipeline transfer to publicly available government expenditure data. It does not produce domain-valid findings regarding MPLAD fund utilization.

## **0.3.1 In Scope**

1. Data preparation pipeline design and execution on the ULB benchmark, including scaling of non-PCA features, with documentation of all transformations and their rationale. Missing-value handling and categorical encoding are included as pipeline components demonstrated procedurally; the benchmark dataset does not require these operations empirically, and this is acknowledged.  
2. Comparative application of Isolation Forest and LOF to the benchmark dataset across a defined parameter grid (contamination rate, number of estimators/neighbors, subsampling size), with systematic recording of anomaly labels, anomaly scores, and execution time for each configuration.  
3. Label-informed evaluation of unsupervised detector outputs using precision, recall, F1, and where sample sizes permit, AUC-ROC and AUC-PR. The evaluation is explicitly characterized as semisupervised (methods are unsupervised; evaluation uses labels). This is not a contradiction but a precise description of the evaluation protocol.  
4. PCA-based diagnostic visualization of detection outputs in reduced space, with explicit assessment of what the visualization can and cannot reveal given the proportion of variance captured and the prior PCA transformation of the benchmark features.  
5. Cross-method consistency analysis examining where iForest and LOF agree and disagree in their anomaly flags, and whether agreement correlates with higher precision or recall.  
6. Exploratory domain transfer attempts applying the same pipeline to any identified publicly available government expenditure data, with honest reporting of results regardless of whether they are informative or inconclusive.  
7. Structured limitations and gap analysis identifying what minimum data conditions, feature types, temporal structures, and methodological adjustments would be required before these methods could be responsibly applied to MPLAD fund utilization data.  
8. Ethical and interpretive discussion of false-positive implications in a hypothetical MPLAD deployment context, including the operational cost of human review, the risk of wrongful flagging, and the potential for methods to encode and amplify structural biases present in historical administrative data.

## **0.3.2 Out of Scope**

1. Any claim about anomaly patterns in MPLAD fund utilization. The benchmark data contains no MPLAD data. No such claim is supportable.  
2. Any inference about the prevalence, nature, or distribution of irregularities in the MPLAD scheme. The project does not analyze MPLAD data; it analyzes credit card transaction data. Statistical properties observed on the latter do not transfer to the former.  
3. Any recommendation for operational deployment of these methods in a public-fund auditing context. Deployment requires domain data, domain validation, stakeholder engagement, and institutional context — none of which are available in this study.  
4. Feature engineering for MPLAD data. No MPLAD data is available; therefore no MPLAD-specific features can be engineered. The benchmark features are pre-transformed and uninterpretable.  
5. Temporal validation or concept-drift analysis. The benchmark covers two days. Temporal analysis is not possible.  
6. Comparison with supervised methods (e.g., Random Forest, XGBoost, neural networks). The project's contribution is the unsupervised comparison; adding supervised baselines would broaden scope without strengthening the core analysis, and the near-perfect metrics reported in the literature for supervised methods on this benchmark are well-characterized and add limited incremental insight.  
7. Novel methodological contribution. This project applies existing methods to an existing benchmark. It does not propose a new algorithm, a new evaluation metric, or a new ensemble architecture. Its contribution is comparative and diagnostic, not inventive.

&nbsp;

**Side Note:** The out-of-scope list is longer than the in-scope list. This is intentional and not a sign of project weakness. A precisely bounded project with a clear exclusion list demonstrates more intellectual discipline than an ambiguously broad one. Reviewers who encounter the out-of-scope section will recognize that the project author understands the difference between what was done and what could be done — a distinction that many projects, including published ones, fail to make.

# **0.4 Research Questions**

The following questions are what this project is designed to answer. Each is answerable within the defined scope. None requires MPLAD data. None overclaims.

&nbsp;

* **RQ1:** How do Isolation Forest and Local Outlier Factor compare in their detection performance (precision, recall, F1) on the ULB benchmark across a range of contamination rates and estimator/neighborhood sizes?

  *Rationale:* This is the core comparative question. It requires no domain data and produces a quantified, reproducible answer. The parameter sweep ensures the comparison is not contingent on a single arbitrary configuration.  
* **RQ2:** To what extent do the two methods agree on which observations are anomalous, and does agreement correlate with higher confidence in the detection (as measured by label-informed metrics)?

  *Rationale:* Cross-method consistency is a practical concern in any deployment scenario where multiple detectors are used as an ensemble or as cross-checks. If two methods disagree on most observations, the operational value of running both diminishes. If they agree, the agreement set becomes a high-confidence candidate pool.  
* **RQ3:** How sensitive is each method's output to small changes in its primary hyperparameters (contamination for both, n\_estimators for iForest, n\_neighbors for LOF), and what does this sensitivity imply about the stability of unsupervised anomaly detection on imbalanced data?

  *Rationale:* Unsupervised methods lack a labeled training signal to calibrate hyperparameters. If the anomaly set changes substantially with small parameter adjustments, the practical utility of the method is constrained, because there is no principled way to select the "correct" parameter in an unsupervised setting. Documenting this instability is itself a contribution to the comparative understanding of these methods.  
* **RQ4:** What proportion of variance is captured by the first two and three principal components of each dataset, and does visual inspection of the reduced space reveal coherent separation between detected anomalies and normal observations?

  *Rationale:* PCA visualization is commonly used in anomaly detection studies but its interpretive limits are rarely discussed. This question forces an explicit assessment of whether the visualization is informative or merely decorative.  
* **RQ5:** When the same pipeline is applied to publicly available government expenditure data, do the detected anomalies correspond to interpretable domain patterns, or does the absence of structured, domain-relevant features render the output uninterpretable?

  *Rationale:* This is the domain transfer question, asked honestly. A negative answer ("no interpretable patterns emerged") is as valid as a positive one. The question tests whether the methods' value is contingent on feature quality, which is itself a finding about the prerequisites for domain application.  
* **RQ6:** At the false-positive rates observed on the benchmark, what would the absolute volume of flagged entries be if applied to a plausible MPLAD-scale dataset (e.g., \~543 constituencies, thousands of projects annually), and is this volume operationally tractable for human review?

  *Rationale:* This translates the abstract metric (false-positive rate) into a concrete operational figure. A 1% false-positive rate sounds manageable until it means reviewing 50 projects per constituency per year. This question grounds the ethical and operational discussion in arithmetic.

# **0.5 Boundary Conditions and Assumptions**

The following conditions are assumed to hold for the project's conclusions to be valid. If any is violated, the affected conclusions are void.

&nbsp;

| Condition | Detail | Consequence if Violated |
| :---- | :---- | :---- |
| **Benchmark data integrity** | The ULB dataset is assumed to be as described by its providers: 284,807 rows, 31 columns, 492 positive instances, PCA-transformed features, no missing values. | If the dataset has been corrupted, modified, or misdescribed, all benchmark results are invalid. *Mitigation:* verify row/column counts and class distribution before any analysis. |
| **Label accuracy** | The Class variable is assumed to be a reliable ground-truth indicator of fraud/genuine status as determined by the original data providers (reported as cardholder-confirmed fraud). | If labels are noisy or unreliable, label-informed metrics are unreliable. This is an inherited limitation from the dataset and cannot be resolved within this project. |
| **Scikit-learn implementation fidelity** | The IsolationForest and LocalOutlierFactor implementations in scikit-learn are assumed to correctly implement the algorithms as described in their respective original papers (Liu et al., 2008 for iForest; Breunig et al., 2000 for LOF). | If implementations contain bugs or deviations, results may not reflect the algorithms' true behavior. This is an inherited dependency accepted by all studies using these libraries. |
| **Stationarity within the benchmark** | The two-day window is treated as a single static dataset. No temporal ordering is imposed or assumed. | This is not a violation risk (the data has no temporal structure to exploit) but a stated assumption that precludes any temporal claim. |
| **Domain supplementary data representativeness** | Any government expenditure data identified for the exploratory transfer is assumed to be representative of at least some subset of public fund utilization, even if not of MPLAD specifically. | If the supplementary data is itself anomalous, non-representative, or fabricated, the transfer assessment is meaningless. *Mitigation:* document the supplementary data's provenance and known limitations. |
| **Parameter grid coverage** | The parameter grids defined for iForest and LOF are assumed to span the practically relevant range of configurations. | If the true optimal or most informative configuration lies outside the grid, it will not be discovered. This is an accepted scope limitation; exhaustive grid search is computationally prohibitive and intellectually unnecessary for a comparative study. |

&nbsp;

**Side Note:** Publishing boundary conditions is uncommon in semester projects but standard in any research or engineering context where claims need to be defensible. Its inclusion here serves a dual purpose: it protects the project's claims by making their prerequisites explicit, and it signals to any reviewer that the project author understands the concept of conditional validity — a concept that distinguishes rigorous work from careless work regardless of the project's scale.

# **0.6 Success Criteria**

"Success" for this project is not a detection rate. It is the quality of the comparative analysis and the rigor of the limitations discussion. The following are the specific criteria against which the project should be evaluated.

## **0.6.1 Minimum Viable Completion**

The project meets minimum viable completion if and only if all of the following are true:

&nbsp;

* Both detectors have been applied to the benchmark dataset with at least three distinct contamination values and at least two distinct estimator/neighborhood values each.  
* Label-informed metrics (precision, recall, F1) have been computed for each configuration.  
* At least one PCA visualization has been produced with an honest assessment of its informativeness.  
* The limitations section explicitly states that no domain-valid MPLAD conclusions can be drawn.  
* The important portions of the provenance/decision log is included as an appendix, rest complete version as a complimentary document.&nbsp;

## **0.6.2 Competent Completion**

The project achieves competent completion if it meets all minimum viable criteria and additionally:

&nbsp;

* The parameter grid is sufficiently dense to reveal sensitivity patterns (not just "method A is better than method B" but "method A is better at low contamination but method B is more stable across contamination values").  
* Cross-method consistency analysis is performed quantitatively (overlap counts or Jaccard indices) rather than only descriptively.  
* The domain transfer attempt is executed (even if it yields null results) rather than discussed only hypothetically.  
* The false-positive operational translation (RQ6) is computed with explicit arithmetic rather than only discussed qualitatively.

## **0.6.3 Strong Completion**

The project achieves strong completion if it meets all competent criteria and additionally:

&nbsp;

* The limitations section includes a structured gap analysis specifying minimum data conditions for domain transfer (not just "we need better data" but "we need data with at least X variables of types Y and Z, spanning at least W time periods, with at least V observations per group").  
* The ethical discussion connects false-positive rates to specific institutional consequences (audit burden, political sensitivity, trust erosion) rather than remaining at the level of general principle.  
* The exploratory domain transfer yields at least one interpretable finding, even if the finding is a well-documented negative result (e.g., "LOF flagged the three highest-expenditure districts, but these are also the three largest districts by population and budget allocation, suggesting the method is detecting scale rather than anomaly").

## **0.6.4 What Success Is Not**

Success is not:

&nbsp;

* Achieving a high AUC-ROC value (this is well-characterized in the literature and demonstrates dataset familiarity, not analytical skill).  
* Detecting "interesting" anomalies in the domain data (a null result is intellectually honest; forcing an interesting result is not).  
* Producing a visually impressive dashboard or interactive visualization (the project's contribution is analytical, not presentational).  
* Implementing novel methodological variations (the project's scope is comparative, not inventive).

&nbsp;

**Side Note:** Defining success criteria before execution is a practice borrowed from engineering and regulatory contexts, where it serves to prevent scope creep and post-hoc rationalization. In academic work, it prevents the common failure mode of defining "what the project achieved" after seeing what the project produced, which invariably leads to overclaiming. If the project produces a strong result, the pre-defined success criteria confirm it. If it produces a weak result, the criteria prevent the weak result from being retroactively redefined as strong.

# **0.7 Risk Register**

The following identifies foreseeable risks to project execution and the planned response to each.

&nbsp;

| Risk | Likelihood | Impact | Mitigation |
| :---- | :---- | :---- | :---- |
| **No viable domain supplementary data is found** | Moderate | Moderate — reverts project to single-track benchmark | Document the search effort and null result. Expand the gap analysis in Phase 7 to treat the absence of public data as itself a structural barrier to domain application. |
| **Domain supplementary data is found but is too degraded for analysis** | Moderate | Low — the attempt itself is the artifact | Document the degradation. Report preprocessing attempts and where they failed. A documented failed attempt is more valuable than no attempt. |
| **LOF execution time is prohibitive at full dataset scale with certain parameter combinations** | High | Low — subsampling is an accepted response | Subsample with documented strategy (e.g., stratified by class). Note that subsampling changes the anomaly rate and may affect LOF's density estimates. |
| **All parameter configurations produce near-identical results, making the comparison uninformative** | Low | Moderate — weakens RQ1 and RQ3 | Report the near-identicality as a finding: "on this benchmark, these methods are insensitive to parameter variation in the tested range." This is a valid if unexciting conclusion. |
| **PCA visualization captures very low variance and is uninformative** | Moderate | Low — this is itself an answer to RQ4 | Report the variance captured and state that the visualization is not informative. Consider supplementary t-SNE/UMAP with appropriate caveats. |
| **The two methods disagree on nearly all observations** | Low–Moderate | Moderate — complicates RQ2 but is itself a finding | Report the disagreement. Discuss its implications for ensemble approaches and operational deployment. A finding of instability is more valuable than a falsely optimistic finding of consistency. |
| **Scope creep: temptation to add supervised baselines, deep learning methods, or novel ensembles** | High | High — dilutes focus and risks overclaiming | Return to this scope document. If the addition does not directly serve one of the six research questions, it is out of scope. |
| **Scope creep: temptation to over-interpret domain transfer results** | High | High — risks the central credibility constraint | Return to the scope statement. No MPLAD claim is supportable. If the domain data yields a pattern, describe it as a pattern in that specific dataset, not as evidence about MPLAD. |

# **0.8 Epistemic Positioning**

This section addresses a question that is often implicit but rarely stated: what kind of knowledge does this project produce?

&nbsp;

This project does not produce empirical knowledge about MPLAD fund utilization. It does not produce theoretical knowledge about anomaly detection algorithms (no new theorems, no new proofs, no algorithmic innovations). It produces comparative diagnostic knowledge: a characterized understanding of how two specific methods behave on one specific benchmark under specified conditions, with an assessment of whether that behavior appears to transfer to a different data context.

&nbsp;

Comparative diagnostic knowledge is not the most prestigious form of knowledge in machine learning. It is not a SOTA result, a new architecture, or a novel theoretical insight. It is, however, the form of knowledge that is most immediately useful to a practitioner who needs to decide which method to apply, under what conditions, and with what expectations. A practitioner choosing between iForest and LOF for an imbalanced detection task benefits more from knowing that "iForest is more sensitive to contamination specification but more stable across neighborhood sizes" than from knowing that "a new transformer-based anomaly detector achieved 0.999 AUC on a benchmark."

&nbsp;

This project's epistemic position is therefore closer to engineering testing than to scientific discovery. It asks not "what is true?" but "what happens when we do this, and what does that tell us about when it would be appropriate to do it elsewhere?" This is a legitimate and underappreciated form of intellectual contribution, particularly in a field where benchmark results are frequently reported without the contextual qualification that would make them actionable.

&nbsp;

**Side Note:** The term "epistemic positioning" may appear grandiose for a semester project. It is included because the alternative — leaving the knowledge-type implicit — allows the project to be silently judged against the standard of empirical domain knowledge, which it cannot meet. Stating the knowledge-type explicitly forces the evaluation to occur on the correct axis. This is not pretension; it is precision.

# **0.9 Scope Locking Declaration**

The scope defined in this document — Sections 0.3 through 0.8 — is considered locked as of the date of this writing Sep 6, 2026\. Subsequent phases of the project will be executed within this scope. If execution-phase discoveries require scope modification, the modification will be documented in the provenance log with a dated entry explaining what changed, why, and what the implications are for the research questions and success criteria.

&nbsp;

* No claim will appear in the final report that is not supportable within this defined scope.  
* No MPLAD-specific conclusion will appear in the final report.  
* No metric will be reported without the context necessary to interpret it (class distribution, parameter settings, evaluation protocol).

&nbsp;

*Phase 0 complete. Proceed to Phase 1: Data Acquisition (Dual Stream).*