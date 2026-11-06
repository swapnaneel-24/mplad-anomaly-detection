# Stream A -- Phase 7: Synthesis, Limitations, and Governance

**Role and boundaries**
Phase 7 is the final administrative and governance layer of Stream A. It contains no executable code. Its purpose is to explicitly define the boundaries of the analytical claims made in Phases 2-6, document the computational compromises accepted during execution, outline the engineering gap between the benchmark data and the target domain, and state the legal licensing parameters of the artifacts. 

Any downstream application (such as a Streamlit dashboard) consuming the Phase 5/6 artifacts must respect and surface the limitations documented here.

## 1. Terminological and Methodological Hygiene
* **Unsupervised Detection vs. Label-Informed Evaluation**: The term *unsupervised learning* applies strictly to model fitting and score generation in Phase 3. Phases 4, 5, and 6 perform *post-hoc, label-informed evaluation* (semi-supervised evaluation of unsupervised outputs). No unsupervised validation claim is made.
* **Continuous Scores vs. Post-Hoc Decision Rules**: Detector estimation is strictly separated from the operational decision rule. The 1% threshold is a fixed policy applied *post-hoc* and is never re-optimized inside the Phase 5A bootstrap replicates.
* **Exploratory Selection Bias**: Highlighted configurations (IF_003, IF_004, LOF_004) were selected *after* inspecting label-informed Phase 4 metrics. All comparisons involving them are exploratory and subject to post-hoc selection bias.
* **Construct Separation**: Global rank association (Spearman), binary set overlap (Jaccard), per-detector overlap share, and ground-truth fraud recovery are distinct constructs. The hypergeometric test rejects only independent uniform random selection; it does not establish that flagged observations are true anomalies.

## 2. Algorithmic & Computational Scale Constraints
* **LOF Neighbourhood-Scale Sensitivity**: LOF performance is highly sensitive to the neighbourhood parameter k (Phase 4 AP ranged from 0.0024 to 0.3229).
* **Full-Scale (284k) LOF Novelty-Mode Degradation**: Executing native it_predict LOF across all 284,807 rows exceeded interactive compute envelopes. The 284k full-dataset companion run required 
ovelty=True fitted on a 50k subsample. LOF recall degraded sharply under this approximation, establishing the 30,000-row run as the primary methodological artifact for native LOF evaluation.
* **Double-PCA Disambiguation**: The Phase 5B PCA agreement map is a lossy 2-D visual projection (37.6% variance explained) of features that were *already* orthonormal principal components (V1-V28).

## 3. Proxy-to-Domain Transfer Gap (ULB -> PMGSY-III -> MPLADS)
No domain-valid conclusions regarding MPLADS fund utilization can be drawn from Stream A. 
* **Granularity**: 2-day point-level transactions vs. multi-year constituency-level projects.
* **Features**: 28 anonymized PCA components vs. high-cardinality administrative/geospatial records.
* **Anomaly Topology**: Continuous feature-space outliers vs. relational, temporal, and graph-structured irregularities (e.g., ghost works, vendor concentration).

## 4. Operational Audit & Ethical Governance
* **Flags Are Audit Priorities, Not Findings**: An unsupervised anomaly flag is never proof of fraud or administrative misconduct.
* **False-Positive Burden**: Even inside the highest-precision consensus gate (Both), 71.96% of flagged observations are legitimate transactions. Publishing raw unsupervised flags against public entities without human audit verification would generate unacceptable false-accusation rates.

## 5. Legal and Licensing Compliance
* **Stream A (ULB_CC_Fraud_2013)**: Governed by ODbL v1.0 and DbCL v1.0. Raw datasets are not redistributed; derivative prediction artifacts are tracked via DVC.
* **Stream B (PMGSY-III)**: Governed by India's Government Open Data License (GODL-India). Derivative cleaned tables carry explicit GODL-India attribution.
