# PMGSY-III Investigation — Consolidated REPORT_BACK

**Reviewer / executor:** <REDACTED>
**Date (UTC):** 2026-11-18
**Git branch / commit:** N/A — read-only analysis, no code change
**Execution environment:**
- Python 3.13.18
- pandas 2.2.3 | numpy 2.4.6
- geopandas 1.2.0 | pyogrio 0.13.0 | GDAL 3.8.4
- Google Colab, Linux-6.6.159+-x86_64
- Inputs mounted read-only from `<DRIVE_ROOT>/<DRIVE_FOLDER>`

**Overall disposition:** PARTIAL
- INV-01 PASS (CSV-side) / CONDITIONAL (raw URL + license unverified)
- INV-02 PASS (geometry-aware) — flags master-CSV fidelity issue
- INV-03 PASS
- INV-04 CONDITIONAL (descriptive only, no model)
- INV-05 CONDITIONAL (ML gates fail; descriptive observatory is the R1 deliverable)
- INV-06 BLOCKED

**Source permission status:** UNVERIFIED — no license text present in handoff

---

## Input manifest

| File | SHA-256 | Bytes | Features / rows | CRS | Encoding |
|---|---|---|---|---|---|
| `PMGSY_Master_Dataset_Combined(1).csv` | `773a799b4ada7a95b33f2d6d0c057e5ff70bb8b861fc489503dc3ad8dc835408` | 910,937 | 8,868 | n/a | UTF-8 |
| `pmgsy_stream_b_p_unique.csv` | `1c577758bfae2468a1bee5c6768998bd19ba33d6eb62e824ec0674dead079e6a` | 282,810 | 7,670 | n/a | UTF-8 |
| `pmgsy_stream_b_l_unique.csv` | `50bd95061a239b987e77225406528e607d1ff9ab3431d07f28be5c6cd81dbbde` | — | 1,964 | n/a | UTF-8 |
| `Bihar_PMGSY-III.shp/.shx/.dbf/.prj` | per-part hashes in `INV01_raw_inventory.csv` | — | 1,476 | EPSG:4326 | (from .cpg, pending) |
| `UP_PMGSY-III.shp/.shx/.dbf/.prj` | same | — | 2,757 | EPSG:4326 | same |
| `MP_PMGSY-III.shp/.shx/.dbf/.prj` | same | — | 4,635 | EPSG:4326 | same |
| `csv_audit.json` | n/a | — | — | — | JSON manifest |

Source URI / acquisition date / license: **UNKNOWN** in handoff.

---

## INV-01 — Raw geospatial source inventory and lineage reconstruction

**Disposition:** **PASS** (CSV-side reconciliation) + **CONDITIONAL** (raw URLs and license unverified)

### A. Input manifest
See consolidated manifest.

### B. Reproduction
Colab session executed read-only. All 12 shapefile components present and read cleanly via geopandas 1.2.0 / pyogrio 0.13.0.

### C. Results

| finding_id | measure | value | population | source |
|---|---|---|---|---|
| INV01-F1 | CSV SHA-256 matches audit | 3 / 3 | P/L/Master | `csv_audit.json` |
| INV01-F2 | Master rows | 8,868 | master CSV | `773a799b…` |
| INV01-F3 | Master exact row duplicates | 3,001 | master CSV | same |
| INV01-F4 | Master unique MRL_ID | 5,867 | master CSV | same |
| INV01-F5 | P rows / exact duplicates | 7,670 / 0 | P CSV | `1c577758…` |
| INV01-F6 | L rows / exact duplicates | 1,964 / 0 | L CSV | `50bd9506…` |
| INV01-F7 | P+L shared MRL_ID | 0 | P ∪ L | both |
| INV01-F8 | P+L total rows | 9,634 | P+L | both |
| INV01-F9 | master unique (5,867) == Bihar_UP_MP rows in P+L (4,361 + 1,506) | 5,867 | cross-file | both |
| INV01-F10 | Source groups in split files | Bihar_UP_MP, Maharashtra, Odisha, Rajasthan | P+L | both |

**Reconciliation:** master CSV is the 3-state subset (Bihar, MP, UP) after attribute deduplication. Split files add three states (Odisha, Maharashtra, Rajasthan) → 9,634 rows total. Master is a proper subset of split.

### D. Competing explanations for the 3,001 master surplus
- *Hypothesis:* notebook's `astype(str).str.strip()` + `to_numeric` normalisation collapsed raw distinctions.
- *Hypothesis:* `(1)`-suffixed master is a different generation than the base file downloaded in cell 6 of the historical notebook.
- **Status:** INDETERMINATE. Cannot resolve from CSVs alone.

### E. Decisions
- **ACCEPT** CSV hashes as authentic.
- **DEFER** admission of master CSV as faithful serialization.
- **BLOCKED:** original URLs, acquisition dates, license.

### F. Acceptance mapping
- `INV01_raw_inventory.csv` — present
- `INV01_lineage_graph.md` — not produced; textual lineage recorded in section C
- `INV01_warnings.md` — not produced

### G. Next handoff
Obtain original download URLs, acquisition dates, `.cpg` encoding declarations, and license evidence before INV-06.

---

## INV-02 — Geometry-aware duplicate and analytical-unit forensics

**Disposition:** **PASS (geometry-aware)**
**Headline:** `MRL_ID` is **not** a physical-segment primary key in this data.

### A. Input manifest
Raw shapefiles as in INV-01.

### B. Reproduction
Cell 5. Geometry hash = `sha256(geometry.wkb_hex)[:16]`; duplicate grouping on 12 non-geometry attribute columns.

### C. Results

| finding_id | measure | value | population |
|---|---|---|---|
| INV02-F1 | Master MRL_ID groups with n > 1 | 841 | master CSV |
| INV02-F2 | Rows in those groups | 3,842 | master CSV |
| INV02-F3 | Bihar MRL_ID groups n > 1 | 37 | Bihar shp |
| INV02-F4 | Bihar groups: distinct geometry | 37 / 37 | Bihar shp |
| INV02-F5 | UP MRL_ID groups n > 1 | 143 | UP shp |
| INV02-F6 | UP groups: distinct geometry | 142 / 143 | UP shp |
| INV02-F7 | UP groups: same geometry | 1 / 143 | UP shp |
| INV02-F8 | MP MRL_ID groups n > 1 | 661 | MP shp |
| INV02-F9 | MP groups: distinct geometry | 661 / 661 | MP shp |
| INV02-F10 | Whole-attribute duplicate groups in raw shapefiles | 1 (UP only) | 3 state shps |
| INV02-F11 | Whole-row exact duplicates in master CSV | 3,001 | master CSV |

**Three consequences:**
1. MRL_ID is a *label* that can attach to multiple distinct physical LineStrings. 840 / 841 groups span distinct geometries.
2. Master CSV introduces ~3,000 row duplications absent from raw source.
3. P/L split deduplicates on MRL_ID, discarding ~3,000 physical road segments from the 3-state subset. Any analysis using P/L split files must state this underrepresentation explicitly.

### D. Competing explanations
- *Benign:* MRL_ID denotes a road-name lineage, not a physical segment; multiple proposed segments per MRL are legitimate. **Consistent with all three state-level findings.**
- *Benign:* Segments re-proposed across IMS editions under the same MRL label. **Would require IMS_YEAR × MRL_ID cross-tab to confirm — not run.**
- *Not supported:* "Fragmented roads" — raw features are distinct LineStrings, no attribute duplication.

### E. Decisions
- **CONFIRMED:** MRL_ID is not a physical-segment primary key.
- **CONFIRMED:** master CSV is not a faithful serialization of the raw shapefiles.
- **DEFER:** any deduplication rule adoption.
- **AFFECTED DOWNSTREAM:** P/L split under-represents true proposed-segment count by ~3,000 in the 3-state subset.

### F. Acceptance mapping
- `INV02_geometry_categories.csv` — present
- `INV02_duplicate_group_ledger.csv`, `INV02_sensitivity.csv`, `INV02_examples.geojson` — not produced (example extraction blocked on rights + top-multiplicity extraction cell)

### G. Next handoff
Extract top-N highest-multiplicity MRL_ID groups as concrete examples once license permits.

---

## INV-03 — Semantics, data quality and P/L cohort profile

**Disposition:** **PASS**
**Caveat:** Field dictionary carries `UNVERIFIED` flags on 3 fields (`MRL_ID`, `CN_CODE`, `PROPOSAL_T`) that require official source documentation before any downstream model or public claim. PASS here means "CSV-side profile complete; unknowns honestly flagged", not "field semantics fully resolved".

### A. Input manifest
P and L split files (deduplicated, MRL_ID-unique). Master CSV used only for missingness comparison.

### B. Reproduction
Cell 6 executed. Outputs written to `INV03_field_dictionary.csv` and `INV03_cohort_cube.csv`.

### C. Results

**Field dictionary (14 fields):** 8 IDENTIFIER, 4 CONTEXT/TEMPORAL, 1 MEASUREMENT (`PROPOSED_L`), 3 UNVERIFIED (`MRL_ID`, `CN_CODE`, `PROPOSAL_T`). See `INV03_field_dictionary.csv`.

**Missingness:**

| cohort | field | missing % |
|---|---|---|
| master | CN_CODE | 17.42 (all 1,545 L rows) |
| P | (none) | 0.00 |
| L | CN_CODE | 100.00 |

**Cohort cube:** 53 state × year × batch cells. **6 cells** below min-cell threshold of 5 (all reported, none interpreted):
- 4 P cells at n=3–4 (STATE_ID 20/2021/b2, 29/2022/b1, 33/2024/b1, 5/2024/b1)
- 2 L cells at n=3–4 (STATE_ID 26/2020/b1, 33/2020/b1) — both with `n_zero_len == n`, consistent with L's all-zero PROPOSED_L

**P `PROPOSED_L` profile:** n=7,670; mean 8.0543 km; median 6.8190 km.

**P heaping (descriptive only, no inference on measurement intent):**

| quantum | share on exact multiples |
|---|---|
| 1.0 | 17.5% |
| 0.5 | 24.4% |
| 0.25 | 27.4% |
| 0.1 | 4.3% |

Substantial 0.5 km heaping is present. For context: if `PROPOSED_L` were continuously distributed at its observed precision, expected share on 0.5 km multiples would be ~0.2%; observed 24.4% is ~120× higher. **Reported as a measurement-convention observation. Does not establish estimation bias, intent, or fraud.**

**L `PROPOSED_L`:** all-zero across all 1,964 rows (INV03-P3). L cohort carries no length signal.

### D. Competing explanations
- Heaping on 0.5 km: could reflect a *specification convention* (officers rounding proposed lengths to nearest half-kilometre when filling IMS forms), a *data-entry convention*, or a *unit conversion artefact*. **INDETERMINATE** without official field documentation.
- L cohort all-zero length: most plausibly "bridge proposals do not carry a linear length field" (bridges are point features, not road segments). **CONSISTENT** with INV02 findings (L geometry distinct from P, `CN_CODE` unique to L).

### E. Decisions
- **CONFIRMED:** Field dictionary drafted; 3 fields remain UNVERIFIED pending source documentation.
- **CONFIRMED:** L cohort cannot support any length-based analysis.
- **DEFER:** interpretation of heaping magnitude.
- **AFFECTED DOWNSTREAM:** Any anomaly/outlier/quality metric that uses `PROPOSED_L` must be restricted to the P cohort and must not use P-only distributions as a proxy for L.

### F. Acceptance mapping
- `INV03_field_dictionary.csv` — present
- `INV03_cohort_cube.csv` — present
- `INV03_quality_profile.csv` — not produced as a discrete file; profile is this section
- `INV03_eda_claims_audit.md` — not produced; would retract the earlier notebook's "laziness / 19.7% PASS" claim (this pass observes 24.4% heaping, which is *more*, not less, and is descriptive only)
- `INV03_exception_examples.csv` — not produced

### G. Next handoff
Obtain official PMGSY field dictionary to lift the UNVERIFIED flags. Prior to public claims, replace the historical notebook's "laziness score ✅ PASS" language with the descriptive heaping share.

---

## INV-04 — Cross-state / temporal compatibility and sampling bias

**Disposition:** **CONDITIONAL** — descriptive only. No model, no generalisation claim.

### A. Input manifest
P and L split files.

### B. Reproduction
Cell 7 executed. Outputs to `INV04_P_by_source.csv`, `INV04_L_by_source.csv`.

### C. Results

**P by SOURCE_STATE:**

| SOURCE_STATE | n | mean_len | median_len | p95_len | min_year | max_year |
|---|---|---|---|---|---|---|
| Bihar_UP_MP | 4,361 | 8.576 | 7.10 | 17.00 | 2019 | 2024 |
| Odisha | 1,400 | 6.669 | 6.00 | 12.80 | 2020 | 2021 |
| Maharashtra | 992 | 6.456 | 5.80 | 11.82 | 2020 | 2024 |
| Rajasthan | 917 | 9.418 | 8.00 | 19.24 | 2019 | 2024 |

**L by SOURCE_STATE:**

| SOURCE_STATE | n | min_year | max_year |
|---|---|---|---|
| Bihar_UP_MP | 1,506 | 2019 | 2024 |
| Maharashtra | 274 | 2023 | 2026 |
| Odisha | 144 | 2020 | 2022 |
| Rajasthan | 40 | 2020 | 2022 |

**Three observations that must constrain any cross-source comparison:**
1. **Sample sizes span 109×**: from 40 (Rajasthan L) to 4,361 (Bihar_UP_MP P). Any mean/median comparison must state n.
2. **Temporal coverage is not uniform:** Odisha P appears only in 2020–2021; Maharashtra L extends to 2026 (the only 2026 rows in the entire corpus); Rajasthan L only 2020–2022. Cross-source means are confounded by year.
3. **The Bihar_UP_MP group is not a single state** — it aggregates three states. Comparisons against single-state groups (Odisha, Maharashtra, Rajasthan) are structurally asymmetric.

### D. Competing explanations
Apparent state-level differences in `PROPOSED_L` mean are consistent with at least four competing explanations:
- *Covariate shift* (state differences in road network density / terrain)
- *Selection bias* (different proposal volumes per state per year)
- *Processing vintage* (different IMS editions captured different proposal types)
- *Measurement-version differences* (Odisha's 2020–2021 concentration may reflect a specific data-extract vintage)

**Status:** INDETERMINATE. No attempt to separate these is authorised in this pass.

### E. Decisions
- **CONFIRMED:** The four SOURCE_STATE groups are **not** analytically exchangeable. No comparison across them without explicit sample-size and year-range reporting.
- **DEFER:** all cross-source difference claims.
- **NOT ASSESSED:** reproducibility of historical AUC values (0.837 / 0.970). **No AUC was run in this pass.**

### F. Acceptance mapping
- `INV04_P_by_source.csv` — present
- `INV04_L_by_source.csv` — present
- `INV04_reproduction_diff.md`, `INV04_bias_and_leakage_review.md`, figures — not produced (no model, no figures in this pass)

### G. Next handoff
If cross-source comparison is required, use stratified reporting on `IMS_YEAR` and `IMS_BATCH` and state n per stratum. Do not pool.

---

## INV-05 — Feature suitability and optional experimental sandbox

**Disposition:** **CONDITIONAL** — ML gates fail for both cohorts. Descriptive observatory is the authorised R1 deliverable.

### A. Input manifest
P and L split files.

### B. Reproduction
Cell 8 executed. Output to `INV05_feature_eligibility.csv`.

### C. Results

| finding_id | measure | value |
|---|---|---|
| INV05-F1 | P numeric MEASUREMENT columns | **1** (`PROPOSED_L`, 1,922 unique) |
| INV05-F2 | L numeric MEASUREMENT columns | **0** |
| INV05-F3 | P IDENTIFIER_OR_STRATIFIER columns | 10 |
| INV05-F4 | L IDENTIFIER_OR_STRATIFIER columns | 10 |
| INV05-F5 | P CONSTANT_OR_MISSING | 1 (`PROPOSAL_T` — expected, P is all-P) |
| INV05-F6 | L CONSTANT_OR_MISSING | 3 (`PROPOSAL_T`, `PROPOSED_L`, `CN_CODE`) |
| INV05-F7 | P CONTEXT_OR_STRATIFICATION | 1 (`WORK_NAME`, 7,663 unique) |
| INV05-F8 | L CONTEXT_OR_STRATIFICATION | 1 (`WORK_NAME`, 1,106 unique) |
| INV05-F9 | P gate (>1 independent numeric MEASUREMENT) | **FAIL** |
| INV05-F10 | L gate | **FAIL** |

**P cohort:** Only `PROPOSED_L` qualifies as a numeric MEASUREMENT. All other numeric-looking fields (`IMS_YEAR`, `IMS_BATCH`) are stratifiers, not measurements. `CN_CODE` is 7,670 unique values across 7,670 rows — i.e. every P row has a distinct CN_CODE — but no numeric meaning is established, and treating it as a feature would leak row identity.

**L cohort:** `PROPOSED_L` is constant (all zero). `CN_CODE` is constant in L. No numeric feature whatsoever.

### D. Competing explanations
- *Benign:* PMGSY proposals are administratively lean by design; the source schema may simply not carry the numeric fields needed for an unsupervised ranking that would be defensible at R1. **Consistent with the shape of the schema.**
- *Less benign:* The CSV extract may have dropped fields present in the raw source. **Cannot be ruled out without re-inspecting raw .dbf attributes** (which are in the shapefiles, but only the 12 documented columns were read). Worth checking in a follow-up.

### E. Decisions
- **CONFIRMED:** ML on P is BLOCKED — single numeric measurement does not meet INV-05 gate.
- **CONFIRMED:** ML on L is BLOCKED — no numeric feature at all.
- **CONFIRMED:** R1 authorised deliverable = descriptive data-quality observatory, not anomaly ranking.
- **NOT ADOPTED:** LOF, IF, or any distance-based anomaly method. Running any of these on a single feature would produce a ranking that cannot be defended.
- **NOT TRANSFERRED:** ULB or MPLADS fitted objects, thresholds, contamination ratios, or performance metrics. No cross-dataset model transfer is authorised.

### F. Acceptance mapping
- `INV05_feature_eligibility.csv` — present
- `INV05_feasibility_decision.md` — this section is the decision record
- `INV05_candidate_policy.md` — not produced
- `INV05_experiment_protocol.md` — not produced (sandbox not authorised)

### G. Next handoff
Re-inspect raw .dbf fields for any numeric measurement not carried into the CSVs. If none, adopt descriptive observatory as final R1 outcome.

---

## INV-06 — Source admission, product integration scope and handoff

**Disposition:** **BLOCKED**

### A. Input manifest
All INV-01..05 outputs.

### B. Reproduction
N/A — blocked.

### C. Results

**Blocking conditions (all must be resolved):**

1. **License / redistribution status** — UNVERIFIED. No license text present in handoff. Public redistribution of record-level geometry, attributes, or derived figures is **not authorised**.
2. **Master CSV fidelity** — INV02-F11 shows master CSV introduces ~3,000 duplicate rows absent from raw source. Master CSV cannot be admitted as authoritative until provenance is resolved.
3. **Ground truth decision** — for the 3-state subset, the choice between "master CSV" and "raw shapefile" as the canonical population is unresolved. P/L split files further diverge (deduplicated on MRL_ID, discarding ~3,000 physical segments).
4. **Field dictionary UNVERIFIED flags** — 3 fields (`MRL_ID`, `CN_CODE`, `PROPOSAL_T`) lack source documentation.
5. **Downstream not ready** — no source-admission record, identity contract, evidence taxonomy, or implementation scope drafted yet.

### D. Competing explanations
The decision point is not technical — it is procedural. Admitting the data before (1) and (2) are resolved would embed an unresolved discrepancy into any downstream UI, evidence object, or case record.

### E. Decisions
- **REJECT** immediate source admission.
- **DEFER** pending license verification + master CSV provenance resolution.
- **NO PRODUCTION DATABASE WRITES** authorised.
- **NO RAILWAY DEPLOYMENT** for this dataset authorised.
- **NO PUBLIC REDISTRIBUTION** of geometry, attributes, or derived figures authorised.

### F. Acceptance mapping
None — INV-06 deliverables not produced.

### G. Next handoff
- `next_action`: obtain license text and original download metadata; resolve master-vs-raw provenance; re-inspect raw .dbf for any numeric measurements not in CSVs.
- `required_artifact`: license evidence; provenance record for `PMGSY_Master_Dataset_Combined(1).csv`.
- `blocking_dependency`: INV-03 UNVERIFIED fields; INV-02-F11 mechanism.
- `reviewer_approval_needed`: whether master CSV or raw shapefile is the authoritative 3-state source.

---

## Single-message summary

- **INV-01 / PASS (CSV-side) + CONDITIONAL (URLs, license unverified):**
  - **SOURCE SET:** 3 CSVs (SHA-256 verified) + 3 shapefile bundles (12 parts, `EPSG:4326`)
  - **RECONCILIATION:** raw 8,868 (Bihar 1,476 + UP 2,757 + MP 4,635) → master unique 5,867; P/L split = 9,634 (`Bihar_UP_MP` 5,867 + Odisha 1,544 + Maharashtra 1,266 + Rajasthan 957). Master CSV is a proper **subset** of split; not superset.

- **INV-02 / PASS (geometry-aware):**
  - **HEADLINE 1:** `MRL_ID` is **not** a physical-segment primary key. 840 of 841 multi-MRL groups span distinct geometries (Bihar 37/37, UP 142/143, MP 661/661).
  - **HEADLINE 2:** Master CSV has 3,001 whole-row duplicates; raw shapefiles have 1 whole-attribute duplicate group. Master CSV is **not** a faithful serialization.
  - **HEADLINE 3:** P/L split discards ~3,000 real road segments from the 3-state subset by deduplicating on `MRL_ID`.
  - **DECISIONS:** No deletion rule adopted; example extraction blocked on rights.

- **INV-03 / PASS:**
  - **FIELD DICT:** 14 fields; 3 `UNVERIFIED` (`MRL_ID`, `CN_CODE`, `PROPOSAL_T`).
  - **MISSINGNESS:** Master `CN_CODE` 17.42% (all L); P complete; L `CN_CODE` 100% missing.
  - **COHORT CUBE:** 53 `state × year × batch` cells; 6 below min-cell-5 (reported, not interpreted).
  - **P `PROPOSED_L`:** `n = 7,670`, `mean = 8.054 km`, `median = 6.819 km`.
  - **HEAPING (descriptive only):** 0.5 km multiples = 24.4% (uniform-expected ~0.2%); 1.0 km multiples = 17.5%.
  - **CAVEAT:** Heaping reported, not adjudicated. Field semantics still require official documentation for the 3 `UNVERIFIED` fields.

- **INV-04 / CONDITIONAL (descriptive only):**
  - **SAMPLE SIZES:** 40..4,361 (109× range). Report comparisons with `n`.
  - **TEMPORAL COVERAGE NOT UNIFORM:**
    - Odisha P present only 2020–2021
    - Maharashtra L extends to 2026 (only 2026 rows in corpus)
    - Rajasthan L only 2020–2022
  - `Bihar_UP_MP` aggregates 3 states; comparisons vs single-state groups are structurally asymmetric. No model, no AUC, no generalisation claim made.

- **INV-05 / CONDITIONAL:**
  - P numeric `MEASUREMENT` columns: **1** → gate **FAILS**
  - L numeric `MEASUREMENT` columns: **0** → gate **FAILS** (`PROPOSED_L` constant, `CN_CODE` constant)
  - **R1 deliverable:** Descriptive data-quality observatory, not anomaly ranking.
  - **NOT ADOPTED:** LOF / IF / any single-feature anomaly model.
  - **NOT TRANSFERRED:** ULB / MPLADS fitted objects, thresholds, or metrics.

- **INV-06 / BLOCKED:**
  - License `UNVERIFIED` (no license text in handoff)
  - Master CSV fidelity unresolved (`INV-02-F11`)
  - Ground-truth choice (master vs raw) undecided
  - 3 field-dictionary `UNVERIFIED` flags
  - Source-admission, identity-contract, evidence-taxonomy artefacts not drafted

### Requested decisions from reviewer

1. Accept INV-02 finding that `MRL_ID` is a label, not a physical-segment key?
2. For the 3-state subset, is the authoritative source master CSV or raw shapefiles? If raw, P/L split files must be re-derived (not used as-is).
3. Is the license text / original download URL recoverable? Without it, no public redistribution of records, geometry, or derived figures.
4. Accept descriptive-only R1 deliverable given INV-05 gate fails?
5. Authorise the follow-up *"re-inspect raw `.dbf` for numeric measurements not carried into CSVs"* step? If yes, INV-05 may partially reopen.

---

## File manifest at time of handoff

- `INV01_raw_inventory.csv` (2,062 bytes)
- `INV02_geometry_categories.csv` (224 bytes)
- `INV03_cohort_cube.csv` (3,097 bytes)
- `INV03_field_dictionary.csv` (884 bytes)
- `INV04_L_by_source.csv` (130 bytes)
- `INV04_P_by_source.csv` (310 bytes)
- `INV05_feature_eligibility.csv` (1,043 bytes)

**Handoff note:** The lead finding is `INV-02-F11` — the master CSV is not a faithful serialization of the raw data. This must be communicated to any downstream consumer. INV-06 stays `BLOCKED` until the license question and the master-vs-raw provenance question are resolved; neither is a technical problem that further analysis can solve.

# PMGSY-III Investigation — Source-Fidelity and Feature-Recovery Addendum

**Reviewer / executor:** <REDACTED>
**Date (UTC):** 2026-11-18
**Git branch / commit:** N/A — read-only forensic addendum, no repository code change
**Execution environment:**
- Python 3.13.18
- pandas 2.2.3 | numpy 2.4.6
- geopandas 1.2.0 | pyogrio 0.13.0 | GDAL 3.8.4
- Google Colab, Linux-6.6.159+-x86_64
- Inputs mounted read-only from `<DRIVE_ROOT>/<DRIVE_FOLDER>`

**Addendum disposition:**
- **INV-01 — Source lineage:** **CONDITIONAL** (CSV-to-shapefile feature lineage fully reconciled; original portal URL and redistribution license remain unverified)
- **INV-02 — Geometry-aware duplicates & master-CSV fidelity:** **PASS — RESOLVED** (exact mechanism of the 3,001 master CSV duplicate rows reconstructed at 1:1 feature parity)
- **INV-03 — Field semantics & `.dbf` schema completeness:** **PASS (schema complete)** — 0 omitted `.dbf` columns; 3 field definitions (`MRL_ID`, `CN_CODE`, `PROPOSAL_T`) still await official PMGSY documentation
- **INV-04 — Dataset compatibility:** **CONDITIONAL** (unchanged — descriptive stratified reporting only)
- **INV-05 — Modelling feasibility (reopened conditionally):** **CONDITIONAL — FEATURE GATE MET ON RAW GEOMETRY (P COHORT), SANDBOX NOT YET AUTHORIZED** (4 independent geometry-derived measurements recovered for P; production/benchmark model fitting remains unauthorized pending canonical observational-unit and provenance sign-off)
- **INV-06 — Source admission:** **BLOCKED** (license text and canonical observational-unit decision still required)

---

## Executive summary of forensic findings

1. **Exact mechanism of the 3,001 master CSV duplicates (`ADD-02`):**
   - `PMGSY_Master_Dataset_Combined(1).csv` (`8,868` rows) is a **1:1 lossless tabular serialization** of the `8,868` raw shapefile features (`Bihar 1,476 + MP 4,635 + UP 2,757 = 8,868`) with the `geometry` column dropped.
   - Across all `5,867` distinct normalized attribute signatures, **every single signature matches exact multiplicity between raw shapefiles and master CSV (`delta = 0`; `0` features dropped, `0` rows inflated, `0` rows collapsed)**.
   - The `3,001` whole-row duplicates in `master` arise because the upstream PMGSY-III shapefiles store **multi-segment road packages** under a single `MRL_ID` where every physical `LineString` feature repeats the exact same 12 package-level `.dbf` attributes (including package-level `PROPOSED_L`). Stripping `geometry` turns `841` multi-segment packages (`3,842` physical `LineString`s) into `841` repeated-row blocks (`3,001` duplicate occurrences).
   - **Terminology correction applied:** The `5,867` distinct `MRL_ID` records form the 3-state subset of the deduplicated P/L split files (`pmgsy_stream_b_p_unique.csv` + `pmgsy_stream_b_l_unique.csv`), whereas the `8,868`-row master CSV preserves raw feature multiplicity (`8,868` features) without geometry. Deduplicating on `MRL_ID` in the P/L split files collapses `3,001` distinct physical road segments into single representative rows.

2. **Complete `.dbf` schema audit (`ADD-01`):**
   - All three state `.dbf` files (`Bihar_PMGSY-III.dbf`, `UP_PMGSY-III.dbf`, `MP_PMGSY-III.dbf`) contain **12 attribute columns + `geometry`**. **Zero columns were omitted** during extraction to `PMGSY_Master_Dataset_Combined(1).csv`. None of the three shapefile bundles includes a `.cpg` sidecar (`pyogrio` decodes all three cleanly as `UTF-8`).

3. **Geometry-aware duplicate & spatial-overlap ledger (`ADD-03`):**
   - Across all `841` multi-`MRL_ID` groups (`3,842` features):
     - `840 / 841` groups have `n_distinct_geom_fp == n_features` (every feature is a distinct physical `LineString`); only `1` group (`Uttar Pradesh`) contains an identical geometry pair.
     - `342 / 841` groups contain touching/intersecting endpoints (`n_intersecting_pairs > 0`, e.g., contiguous road links meeting at nodes with `max_shared_length_m = 0.0`), while only `4 / 841` groups exhibit true linear overlap (`max_shared_length_m > 1.0 m`).
     - `0 / 841` groups span multiple `IMS_YEAR` editions or multiple `WORK_NAME` strings, confirming that multi-feature `MRL_ID` groups represent **intra-sanction multi-segment packages** rather than cross-year re-proposals.

4. **Reopening `INV-05` — Geometry-derived features (`ADD-04`):**
   - Evaluating raw geometries projected to **EPSG:7755 (WGS 84 / India NSF LCC)** recovers **4 independent numeric measurements** for the 3-state P cohort (`n = 7,323`) that exhibit **near-zero correlation with `PROPOSED_L`**:
     - `_geom_len_km`: `median = 4.9681 km`, `IQR = 6.1625`, `Pearson r = 0.0749`, `Spearman r = 0.0355`
     - `_n_vertices`: `median = 84.0`, `IQR = 158.0`, `Pearson r = -0.0118`, `Spearman r = -0.1183`
     - `_sinuosity`: `median = 1.1436`, `IQR = 0.2646`, `Pearson r = -0.0716`, `Spearman r = -0.1557`
     - `_vertex_density_per_km`: `median = 24.7281`, `IQR = 23.2300`, `Pearson r = 0.0106`, `Spearman r = -0.1164`
   - Because `PROPOSED_L` (`median = 8.0750 km`) reflects **package-level proposed length** repeated across constituent segments while `_geom_len_km` (`median = 4.9681 km`) measures **individual physical segment length**, the two are structurally non-redundant (`r = 0.0749`).
   - For the 3-state L cohort (`n = 1,545` bridge proposals), geometries are short 2-vertex (`median = 2.0`) `LineString` spans (`median length = 0.0295 km` / `29.5 m`, `sinuosity = 1.0000`).

---

## ADD-01 — Complete Raw `.dbf` Schema & Omission Audit

### Method
Inspected `Bihar_PMGSY-III.dbf`, `UP_PMGSY-III.dbf`, and `MP_PMGSY-III.dbf` via `pyogrio 0.13.0` / `geopandas 1.2.0` (`Cell 10`), checking `.cpg` presence, encoding, column names, native dtypes, non-null counts, numeric parseability, and inclusion in `PMGSY_Master_Dataset_Combined(1).csv`.

### Results
- **`.cpg` sidecar files:** `False` across all three states; `pyogrio.read_info()` reports `UTF-8` encoding for all three `.dbf` tables.
- **Omitted columns:** `0` (`NONE — every raw .dbf column is already present in master CSV`).
- **Schema uniformity:** All three shapefiles share the exact same 12 attribute columns (`MRL_ID`, `STATE_ID`, `DISTRICT_I`, `LGD_STATE`, `LGD_DISTRI`, `BLOCK_ID`, `CN_CODE`, `PROPOSED_L`, `WORK_NAME`, `IMS_YEAR`, `IMS_BATCH`, `Proposal_T`) plus `geometry` (`LineString`, `EPSG:4326`, `0` multipart geometries).

---

## ADD-02 — Feature-Level Shapefile-to-Master Reconstruction

### Method
Concatenated all `8,868` raw shapefile features (`Bihar 1,476 + MP 4,635 + UP 2,757`), tagged `STATE_NAME`, normalized string/numeric fields identically to the master CSV serialization, and compared normalized attribute-signature multiplicities (`raw_mult` vs `master_mult`) across all `8,868` records (`Cell 11`).

### Results

| Metric | Value | Notes |
|---|---|---|
| Total raw shapefile features | `8,868` | Bihar `1,476` + MP `4,635` + UP `2,757` |
| Total `master` CSV rows | `8,868` | Exact 1:1 row-count match |
| Distinct normalized attribute signatures | `5,867` | Equals `master["MRL_ID"].nunique()` |
| Signatures in raw ONLY (dropped in `master`) | `0` (`0` features) | Zero data loss on attributes |
| Signatures in `master` ONLY (absent in raw) | `0` (`0` rows) | Zero fabricated or appended rows |
| Signatures matched `1:1` (`raw=1, master=1`) | `5,026` (`5,026` rows) | Single-segment `MRL_ID` packages |
| Signatures with `raw_mult == master_mult > 1` | `841` (`3,842` rows) | Multi-segment `MRL_ID` packages (`3,001` duplicate occurrences) |
| Signatures with `delta != 0` (`master_mult != raw_mult`) | `0` (`0` rows) | **Exact multiplicity conservation** |

**Row-index ordering in `master` CSV:**
- `Bihar` duplicate occurrences (`43` rows across `37` groups): row indices `137..1467` (within the Bihar block `0..1475`).
- `Madhya Pradesh` duplicate occurrences (`2,761` rows across `661` groups): row indices `1481..6108` (within the MP block `1476..6110`).
- `Uttar Pradesh` duplicate occurrences (`197` rows across `143` groups): row indices `6190..8839` (within the UP block `6111..8867`).

**Forensic conclusion:** `PMGSY_Master_Dataset_Combined(1).csv` was created by concatenating the three state attribute tables in order (`Bihar` → `MP` → `UP`), adding `STATE_NAME`, and dropping `geometry`. No accidental row-doubling bug occurred; rather, **the upstream `.dbf` tables store one feature per physical road segment while repeating package-level attributes across all segments sharing an `MRL_ID`**.

---

## ADD-03 — Geometry-Aware Duplicate Ledger & Spatial Overlap Audit

### Method
Projected all `8,868` raw features to `EPSG:7755` (`WGS 84 / India NSF LCC`) and evaluated pairwise exact equality (`tolerance = 1e-3 m`), topological intersection, shared linear overlap (`intersection.length`), and centroid separation across all `841` multi-`MRL_ID` groups (`Cell 12`).

### Summary Diagnostics (`n = 841` multi-`MRL_ID` groups)

| Diagnostic | Count | Share of 841 groups |
|---|---|---|
| Groups where all features have distinct WKB hashes | `840` | `99.88%` |
| Groups with `>= 1` identical geometry pair (`<= 1 mm`) | `1` (UP only) | `0.12%` |
| Groups with `>= 1` intersecting/touching pair | `342` | `40.67%` |
| Groups with shared linear overlap (`> 1.0 m`) | `4` | `0.48%` |
| Groups spanning multiple `IMS_YEAR` editions | `0` | `0.00%` |
| Groups with distinct `WORK_NAME` values | `0` | `0.00%` |

### Representative High-Multiplicity Groups (from `ADD03_duplicate_group_ledger.csv`)

| `MRL_ID` | State | `n_features` | Distinct Geoms | `IMS_YEAR` | Intersecting Pairs | Max Shared Overlap (m) |
|---|---|---|---|---|---|---|
| `234868` | Madhya Pradesh | `67` | `67` | `2020` | `21` | `0.0` |
| `234917` | Madhya Pradesh | `31` | `31` | `2020` | `2` | `0.0` |
| `234818` | Madhya Pradesh | `29` | `29` | `2020` | `7` | `0.0` |
| `248297` | Madhya Pradesh | `28` | `28` | `2021` | `0` | `0.0` |
| `252952` | Madhya Pradesh | `26` | `26` | `2022` | `2` | `0.0` |
| `252588` | Madhya Pradesh | `24` | `24` | `2022` | `4` | `0.0` |
| `234810` | Madhya Pradesh | `23` | `23` | `2020` | `8` | `0.0` |
| `252949` | Madhya Pradesh | `21` | `21` | `2022` | `1` | `0.0` |

---

## ADD-04 — Conditional Re-Evaluation of Geometry-Derived Features (`INV-05`)

### Method
Computed physical segment length (`_geom_len_km`), vertex count (`_n_vertices`), sinuosity (`_geom_len_km / _chord_km`), vertex density (`_n_vertices / _geom_len_km`), and geometry-to-proposed length ratio (`_geom_len_km / PROPOSED_L`) in `EPSG:7755`, evaluating Pearson and Spearman rank correlations against `PROPOSED_L` without fitting any anomaly model (`Cell 13`).

### P Cohort (`n = 7,323` physical segments in 3-state shapefiles)

| Candidate Feature | `n_valid` | `n_unique` | Median | IQR | Pearson `r` vs `PROPOSED_L` | Spearman `r` vs `PROPOSED_L` | Independence Assessment |
|---|---|---|---|---|---|---|---|
| `PROPOSED_L` (package attr, km) | `7,323` | `1,272` | `8.0750` | `6.1700` | `1.0000` | `1.0000` | Baseline package-level attribute |
| `_geom_len_km` (segment, km) | `7,323` | `7,319` | `4.9681` | `6.1625` | `0.0749` | `0.0355` | **Independent** (`r = 0.075`) — measures segment vs package |
| `_n_vertices` | `7,323` | `590` | `84.0000` | `158.0000` | `-0.0118` | `-0.1183` | **Independent** (`r = -0.012`) — geometric detail/complexity |
| `_sinuosity` | `7,094` | `6,776` | `1.1436` | `0.2646` | `-0.0716` | `-0.1557` | **Independent** (`r = -0.072`) — route curvature/tortuosity |
| `_vertex_density_per_km` | `7,096` | `7,095` | `24.7281` | `23.2300` | `0.0106` | `-0.1164` | **Independent** (`r = 0.011`) — digitization resolution |
| `_len_ratio_geom_to_prop` | `7,323` | `7,319` | `0.6694` | `0.8997` | `-0.3592` | `-0.3489` | Derived ratio (`_geom_len_km / PROPOSED_L`); do not pair directly with both inputs |

### L Cohort (`n = 1,545` bridge proposals in 3-state shapefiles)

| Candidate Feature | `n_valid` | `n_unique` | Median | IQR | Notes |
|---|---|---|---|---|---|
| `_geom_len_km` | `1,545` | `1,545` | `0.0295` | `0.0341` | Short bridge-span lines (~29.5 m median) |
| `_n_vertices` | `1,545` | `21` | `2.0000` | `1.0000` | Predominantly 2-point segments |
| `_sinuosity` | `1,510` | `387` | `1.0000` | `0.0000` | Straight chord spans (`IQR = 0`) |
| `_vertex_density_per_km` | `1,510` | `1,510` | `77.1331` | `71.2285` | Inverse-length artifact of 2-vertex spans |

### `INV-05` Gate Determination
1. **3-State Raw Shapefile P Cohort (`n = 7,323`):** **PASSES the multidimensional feature-availability gate** (`>= 2` independent numeric measurements recovered: `PROPOSED_L` at package level plus `_geom_len_km`, `_n_vertices`, `_sinuosity`, and `_vertex_density_per_km` at segment level, with `|r| <= 0.075` against `PROPOSED_L`).
2. **Odisha, Maharashtra, and Rajasthan (`3,767` rows in P/L CSVs):** **FAIL** — only deduplicated CSVs are present in the handoff (no raw shapefiles), leaving only 1 numeric measurement (`PROPOSED_L`) for P and `0` for L.
3. **L Cohort (`n = 1,545` in shapefiles / `1,964` in CSV):** **FAIL** — 2-vertex straight bridge spans (`sinuosity = 1.0`, `PROPOSED_L = 0`) do not support multidimensional anomaly ranking.
4. **Authorization boundary:** No anomaly model (IF, LOF, or cross-stream transfer) has been fitted. Any experimental sandbox on the 3-state P shapefiles requires explicit reviewer authorization defining the **observational unit** (`segment-level` with hierarchical `MRL_ID` grouping vs `MRL_ID-aggregated` package-level features).

---

## Remaining Governance & Blocking Conditions (`INV-06`)

`INV-06` remains **BLOCKED** pending three non-code decisions:
1. **License & redistribution verification:** Obtain the original OGD / PMGSY portal source URL, acquisition timestamp, and license text before admitting records or publishing derived figures.
2. **Canonical observational-unit decision (3-state corpus):**
   - **Option A (Segment-level, `n = 8,868`):** Retain all physical `LineString` features from the raw shapefiles (`P = 7,323`, `L = 1,545`), treating `MRL_ID` as a hierarchical package grouping key rather than a unique row key, and correcting the 1 exact duplicate geometry pair in UP.
   - **Option B (Package-level, `n = 5,867`):** Aggregate multi-segment `MRL_ID` packages deliberately (e.g., summing `_geom_len_km` across constituent segments to compare against package-level `PROPOSED_L`) rather than arbitrarily dropping `3,001` segments via first-row deduplication.
3. **3-state vs 6-state scope:** Confirm whether R1 / M3 restricts scope to the 3 geometry-backed states (`Bihar`, `Madhya Pradesh`, `Uttar Pradesh`) or treats the 6-state CSV corpus (`9,634` deduplicated `MRL_ID` rows) strictly as a descriptive data-quality observatory.

---

## File Manifest (`outputs_addendum_2026-11-18T1701Z/`)

- `ADD01_raw_dbf_schema_audit.csv` (`3,817` bytes) — Complete 36-row `.dbf` column, encoding, and master-CSV inclusion audit.
- `ADD02_feature_reconciliation.csv` (`632,673` bytes) — Exact `5,867`-signature multiplicity reconciliation (`raw_mult` vs `master_mult`, `delta = 0`).
- `ADD03_duplicate_group_ledger.csv` (`125,487` bytes) — Full `841`-group geometry, `IMS_YEAR`, intersection, and shared-overlap ledger.
- `ADD04_geometry_feature_audit.csv` (`425` bytes) — P-cohort geometry feature distributions and Pearson/Spearman correlations vs `PROPOSED_L`.

# PMGSY-III Investigation — Feature-Dependence and R-Metric Addendum (ADD-05, ADD-06)

**Reviewer / executor:** <REDACTED>
**Date (UTC):** 2026-11-19
**Git branch / commit:** N/A — read-only forensic addendum, no repository code change
**Execution environment:**
- Python 3.13.18
- pandas 2.2.3 | numpy 2.4.6
- geopandas 1.2.0 | pyogrio 0.13.0 | GDAL 3.8.4
- Google Colab, Linux-6.6.159+-x86_64
- Inputs mounted read-only from `<DRIVE_ROOT>/<DRIVE_FOLDER>`

**Addendum disposition:**
- **ADD-05 — Inter-feature dependence audit:** COMPLETE. Effective feature space is **3 dimensions**, not 4 (or 5). `_n_vertices` is a proxy for `_geom_len_km` (Spearman ρ = 0.83) and must not enter any protocol as a separate input.
- **ADD-06 — Package-level R distribution:** COMPLETE. `R = sum(_geom_len_km per MRL_ID) / PROPOSED_L` clusters tightly at 0.98 (p25–p75: 0.967–0.985), confirming `PROPOSED_L` and mapped geometry measure approximately the same quantity. R is validated as a defensible consistency metric — **subject to state stratification**, because Madhya Pradesh is degenerate (IQR = 0.003) and Uttar Pradesh carries all usable variance.

---

## Executive summary of Addendum-2 findings

1. **Inter-feature dependence (ADD-05):**
   - Pearson correlation matrix understates dependence; the operative matrix is **Spearman rank**.
   - `_geom_len_km` × `_n_vertices`: **ρ = 0.8322** — functionally the same feature.
   - `_n_vertices` × `_sinuosity`: **ρ = 0.6553**.
   - `_geom_len_km` × `_sinuosity`: **ρ = 0.5690**.
   - `_vertex_density_per_km` × `_geom_len_km`: **ρ = −0.3812** (inverse, by construction — density = vertices / length).
   - `PROPOSED_L` remains independent of every geometry feature (Spearman |ρ| < 0.17 across all four).
   - **Effective feature space: 3 dimensions.**
     - `PROPOSED_L` — independent.
     - `_geom_len_km` — one axis; `_n_vertices` is a proxy, do not use both.
     - `_vertex_density_per_km` — orthogonal (Spearman |ρ| < 0.4 everywhere) but a digitization artifact, not an infrastructure measurement.
     - `_sinuosity` — partially redundant (0.57–0.66 against other features); carries residual curvature signal but is not fully independent.
   - VIFs reported by the Pearson matrix are misleading (all ≈ 1.0) because Pearson is suppressed by heavy-tailed outliers; the Spearman correlation is the honest indicator.

2. **Package-level R distribution (ADD-06):**
   - `n = 4,361` P packages (multi-segment collapsed per `MRL_ID`).
   - **Median R = 0.9806.** Tight IQR: p25 = 0.9666, p75 = 0.9851. p10 = 0.8356, p90 = 1.0285.
   - Systematic ~2% offset from 1.0 plausibly attributable to rounding convention or geometry simplification; the tight central clustering is the substantive finding.
   - `PROPOSED_L` is confirmed constant within `MRL_ID` (`0` packages with >1 distinct `PROPOSED_L`); `0` packages span multiple states. Both confirm the package-level unit is structurally coherent.
   - **State stratification is mandatory:**
     - **Madhya Pradesh** — n = 1,074, **IQR = 0.003** (degenerate). No R signal.
     - **Bihar** — n = 731, IQR = 0.022.
     - **Uttar Pradesh** — n = 2,556, **IQR = 0.051**, p05 = 0.489, p95 = 1.162. **All 192 packages below R = 0.60 and all 82 above R = 1.40 are in UP.**
   - Single-segment packages (n = 3,553) have IQR = 0.027; multi-segment packages (n = 808) have IQR = 0.004 — near-constant R across multi-segment packages is consistent with `PROPOSED_L` being derived from geometry sum rather than independently recorded. Provenance note, not anomaly.

3. **Implications for INV-05 gate determination:**
   - Gate **still passes** — the three-state raw-shapefile P cohort has ≥2 independent numeric measurements.
   - But the defensible feature count is **3, not 4 or 5**, and any modelling protocol must reflect this.
   - Any R-based analysis must be **UP-scoped**; MP should be excluded; global thresholds are invalid.

---

## ADD-05 — Inter-feature dependence audit

### Method
Computed Pearson and Spearman correlation matrices over the five candidate features (`PROPOSED_L`, `_geom_len_km`, `_n_vertices`, `_sinuosity`, `_vertex_density_per_km`) on the three-state P cohort (n = 7,323 segment-level features, EPSG:7755). Reported eigenvalues and VIFs of the Pearson matrix, with explicit caveat that Pearson-based diagnostics can understate dependence when outliers are present.

### Results

**Pearson correlation (misleading — see Spearman below):**

|  | PROPOSED_L | _geom_len_km | _n_vertices | _sinuosity | _vertex_density |
|---|---|---|---|---|---|
| PROPOSED_L | 1.0000 | 0.0749 | −0.0118 | −0.0638 | 0.0356 |
| _geom_len_km | 0.0749 | 1.0000 | 0.2669 | 0.1744 | −0.0408 |
| _n_vertices | −0.0118 | 0.2669 | 1.0000 | 0.0899 | −0.0100 |
| _sinuosity | −0.0638 | 0.1744 | 0.0899 | 1.0000 | −0.0144 |
| _vertex_density | 0.0356 | −0.0408 | −0.0100 | −0.0144 | 1.0000 |

Pearson max |r| off-diagonal = 0.267. Condition number of Pearson matrix = 1.98; VIFs all between 1.003 and 1.115. On this matrix alone, all five features appear roughly independent.

**Spearman rank correlation (operative matrix):**

|  | PROPOSED_L | _geom_len_km | _n_vertices | _sinuosity | _vertex_density |
|---|---|---|---|---|---|
| PROPOSED_L | 1.0000 | 0.0355 | −0.1183 | −0.1619 | −0.0947 |
| _geom_len_km | 0.0355 | 1.0000 | **0.8322** | **0.5690** | **−0.3812** |
| _n_vertices | −0.1183 | **0.8322** | 1.0000 | **0.6553** | 0.0482 |
| _sinuosity | −0.1619 | **0.5690** | **0.6553** | 1.0000 | −0.0793 |
| _vertex_density | −0.0947 | **−0.3812** | 0.0482 | −0.0793 | 1.0000 |

Spearman reveals strong monotonic dependence that Pearson missed. `_geom_len_km` and `_n_vertices` are essentially the same feature in rank space (ρ = 0.83).

### Interpretation

**The Pearson matrix is an artifact of heavy tails.** `PROPOSED_L` has skewness ≈ 2.27 (from INV-03); a small number of very large segments inflate variance and depress linear correlations. Rank correlation is insensitive to this and is the correct diagnostic for dependence structure.

**Feature-space collapse:**
- `_n_vertices` → drop; proxy for `_geom_len_km` (ρ = 0.83).
- `_sinuosity` → optional residual axis (ρ = 0.57–0.66 with two others); not an independent dimension but not fully redundant either.
- `_vertex_density_per_km` → orthogonal (|ρ| < 0.4) but a digitization artifact; usable only if explicitly labelled as such.
- `_geom_len_km` → one genuine axis.
- `PROPOSED_L` → independent of all geometry (|ρ| < 0.17).

**Defensible feature space: 3 dimensions** — `PROPOSED_L`, `_geom_len_km`, `_vertex_density_per_km` (with `_sinuosity` as a candidate fourth only if a protocol justifies it).

### Consequences for INV-05
- Gate **passes**, but the reported `4 independent numeric measurements` should be corrected to **3**.
- `_n_vertices` must not be included in any future model as a separate input; its information is already in `_geom_len_km`.
- `_vertex_density_per_km` is mathematically derived; it must be declared as a digitization characteristic if used, not an infrastructure measurement.

---

## ADD-06 — Package-level R distribution

### Method
Computed `R = sum(_geom_len_km across all features sharing MRL_ID) / PROPOSED_L` for each P package in the three-state raw-shapefile corpus. EPSG:7755 projection. Reported full quantile distribution, tail counts at |R−1| ∈ {0.05, 0.10, 0.20, 0.40}, and breakdowns by state and by segment count. Descriptive only — no thresholds applied, no model fitted.

### Results

**Package counts:**
- Total P packages: 4,361
- Single-segment: 3,553
- Multi-segment: 808
- Spanning multiple states: 0
- `MRL_ID`s with >1 distinct `PROPOSED_L`: **0** — confirms `PROPOSED_L` is genuinely a package-level attribute.

**R distribution (n = 4,361):**

| quantile | R |
|---|---|
| p01 | 0.2121 |
| p05 | 0.6376 |
| p10 | 0.8356 |
| p25 | 0.9666 |
| **p50** | **0.9806** |
| p75 | 0.9851 |
| p90 | 1.0285 |
| p95 | 1.1211 |
| p99 | 1.6074 |
| mean | 0.9603 |
| min | 0.0284 |
| max | 3.4632 |

**Tail counts:**

| threshold | R < 1−t | R > 1+t |
|---|---|---|
| \|R−1\| > 0.05 | 823 | 365 |
| \|R−1\| > 0.10 | 591 | 250 |
| \|R−1\| > 0.20 | 384 | 153 |
| \|R−1\| > 0.40 | 192 | 82 |

**By state:**

| state | n | median | IQR | p05 | p95 |
|---|---|---|---|---|---|
| Bihar | 731 | 0.980 | 0.022 | 0.902 | 1.207 |
| Madhya Pradesh | 1,074 | 0.981 | **0.003** | 0.964 | 0.994 |
| Uttar Pradesh | 2,556 | 0.980 | 0.051 | 0.489 | 1.162 |

All 192 packages below R = 0.60 and all 82 above R = 1.40 are in Uttar Pradesh.

**By segment count:**

| group | n | median | IQR |
|---|---|---|---|
| single | 3,553 | 0.980 | 0.027 |
| multi | 808 | 0.981 | 0.004 |

### Interpretation

**R ≈ 0.98 is the empirical baseline.** The central mass (p25–p75: 0.967–0.985) is tightly clustered. This is the strongest available evidence that `PROPOSED_L` and `sum(_geom_len_km)` measure approximately the same underlying quantity at the package level. The systematic ~2% offset (0.9806 instead of 1.0) is plausibly a rounding convention or geometry-simplification effect; it does not undermine the interpretation of R as a consistency metric.

**Madhya Pradesh is degenerate.** IQR = 0.003 across 1,074 packages means essentially zero R-variance. Whatever produced MP's `PROPOSED_L` was derived from the mapped geometry directly, or vice versa — they are not independent measurements. **MP contributes no R signal and should be excluded from any R-based analysis.** Tail counts within MP are noise, not anomaly.

**Uttar Pradesh carries all usable variance.** p05 = 0.489, p95 = 1.162, and the full 274-package tail (192 + 82 at |R−1| > 0.40) is in UP. Any R-based investigation is effectively a UP investigation.

**Multi-segment packages have near-constant R.** IQR = 0.004 vs 0.027 for single-segment. Combined with the observation that `PROPOSED_L` is constant within `MRL_ID` (0 violations), this is consistent with `PROPOSED_L` being computed from the aggregated geometry sum for multi-segment packages rather than independently recorded. Recorded as a provenance note; not an anomaly claim.

### Consequences for downstream scope
- R is validated as a **defensible consistency metric** at package level.
- R analysis **must be state-stratified**; a global threshold (e.g. "|R − 1| > 0.40 is anomalous") would flag 274 packages — all from UP — and none from Bihar or MP. That is a state indicator, not a consistency indicator.
- MP should be excluded from R-based investigation until the MP `PROPOSED_L` provenance is documented.
- Any exploratory R-tail characterisation should be **UP-scoped** and descriptive — no threshold-based ranking, no anomaly scores.

---

## Consolidated feature-space conclusion (supersedes ADD-04 §INV-05 gate determination)

| Feature | Status after ADD-05 | Use in any future protocol |
|---|---|---|
| `PROPOSED_L` | Independent (Spearman \|ρ\| < 0.17 vs all) | **Use** — package-level |
| `_geom_len_km` | One axis; `_n_vertices` is a proxy | **Use** — segment-level |
| `_vertex_density_per_km` | Orthogonal but digitization artifact | **Use only with explicit labelling** |
| `_sinuosity` | Partially redundant (ρ 0.57–0.66) | **Optional fourth axis** |
| `_n_vertices` | Proxy for `_geom_len_km` (ρ = 0.83) | **Do not use separately** |

**Defensible feature space: 3 (or at most 4 with `_sinuosity`).** The `4 independent numeric measurements` reported in ADD-04 should be superseded by this table.

---

## Addendum-2 file manifest (`outputs/`)

- `ADD05_corr_pearson.csv` — Pearson correlation matrix
- `ADD05_corr_spearman.csv` — Spearman correlation matrix (operative)
- `ADD05_vif.csv` — Variance Inflation Factors (Pearson-based; retained for transparency, not operative)
- `ADD06_package_R_distribution.csv` — Per-package `R` with `state`, `n_segments`, `sum_geom_km`, `proposed_L`, `ims_year`

---

## What this changes in the main report (for internal consistency)

Two passages in the earlier report/Addendum are now superseded and should be updated before external circulation:

1. **ADD-04 §INV-05 gate determination**, item 1: `"PASSES the multidimensional feature-availability gate (>= 2 independent numeric measurements recovered: PROPOSED_L at package level plus _geom_len_km, _n_vertices, _sinuosity, and _vertex_density_per_km...)"` — replace `_n_vertices, _sinuosity, and _vertex_density_per_km` with `_geom_len_km, _vertex_density_per_km (with digitization caveat), and optionally _sinuosity`; state feature count as **3, not 4**.

2. **INV-06 §Blocking conditions**, item 3 (`Canonical observational-unit decision`): add a note that ADD-06 provides empirical support for **Option B (package-level)** as the primary unit — the tight R clustering at 0.98 is consistent with package-level `PROPOSED_L` tracking aggregate mapped geometry, which is the strongest available evidence for the package-level interpretation. Segment-level remains the correct unit for geometry-aware spatial investigation per INV-02. The observational-unit decision is now *partially resolved* (package-level for length-consistency work, segment-level for spatial work) but still requires reviewer sign-off before any modelling protocol proceeds.