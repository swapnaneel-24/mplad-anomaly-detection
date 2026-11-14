// AUTO-GENERATED from backend/contracts/openapi.json — DO NOT EDIT.
// Regenerate with: npm run openapi:check
// Source: PEIARS API v0.4.0
// This file is the reproducible source of truth for OpenAPI-mirrored types.
// The application imports from contracts.ts (hand-maintained, may include
// frontend-only helpers). Drift between the two is reported by the check.

// --- Schemas -----------------------------------------------------------

/** Input contract for adding a reviewer note to a case. */
export interface AddNoteRequest {
  /** Actor reference for the note author (≤128 chars). */
  actor_ref: string;
  /** The case version the caller read; used for optimistic concurrency. */
  expected_version: number;
  /** The note body (Unicode-safe; bounded length). */
  note_text: string;
};

/** Identity of one consumed frozen artifact. */
export interface ArtifactProvenance {
  /** Byte canonicalization applied before hashing: 'frozen-checker-compatible' (CRLF→LF, matching ci/check_frozen_integrity.py) or 'windows-commit-manifest-compatible' (LF→CRLF reconstruction matching the Windows-produced Phase 4 commit manifest). */
  canonicalization: string;
  /** Digest algorithm used for provenance. */
  digest_algorithm: "sha-256";
  /** Repository-relative path to the frozen artifact (never absolute). */
  path: string;
  /** SHA-256 digest of the artifact bytes. */
  sha256: string;
};

/** The verified ten-run benchmark catalog with capability availability. */
export interface BenchmarkCatalogResponse {
  /** Per-capability availability of the DVC-backed evidence layers ('metrics', 'row_level'): available / reason (artifact_missing or integrity_failed) / detail. The catalog itself is always served from Git-verified metadata. */
  capabilities: Record<string, never>;
  /** Number of experiments (always 10). */
  count: number;
  /** Frozen benchmark dataset identity. */
  dataset_id: string;
  /** The ten canonical runs in frozen config order. */
  experiments: Array<BenchmarkExperimentSummary>;
  /** Scientific limitations that apply to every run. */
  limitations: Array<string>;
  /** Fixed benchmark source identifier. */
  source_id: string;
};

/** Full descriptor of one canonical benchmark run. */
export interface BenchmarkExperimentDetail {
  algorithm: "IsolationForest" | "LOF";
  dataset_id: string;
  dataset_scope: DatasetScope;
  /** Fixed detector settings recorded alongside the run grid (e.g. LOF ball_tree/leaf_size); documented, frozen. */
  fixed_pipeline_settings: Record<string, never>;
  limitations: Array<string>;
  metrics_available: boolean;
  model_status: "fitted_offline_frozen";
  parameter_source: ParameterSourceProvenance;
  parameters: Record<string, never>;
  /** Provenance chain: config (parameters), run metadata (dataset scope) and commit manifest (identity). */
  provenance: Record<string, never>;
  row_lookup_available: boolean;
  run_id: string;
};

/** One canonical benchmark run in the list view. */
export interface BenchmarkExperimentSummary {
  /** Detector algorithm of the run. */
  algorithm: "IsolationForest" | "LOF";
  /** Frozen benchmark dataset identity. */
  dataset_id: string;
  /** Whether the verified saved metrics for this run are currently servable (requires the admitted DVC payload to be present and checksum-verified). */
  metrics_available: boolean;
  /** Run status: the detector was fitted offline by the frozen pipeline; nothing is fitted or refitted at request time. */
  model_status: "fitted_offline_frozen";
  /** Provenance of the parameter configuration. */
  parameter_source: ParameterSourceProvenance;
  /** Exact source-backed parameter configuration of the run, extracted verbatim from the frozen config module. */
  parameters: Record<string, never>;
  /** Whether the canonical row-level lookup is currently servable (requires the admitted DVC payload to be present and checksum-verified). */
  row_lookup_available: boolean;
  /** Canonical run identifier (IF_001..IF_005, LOF_001..LOF_005). */
  run_id: string;
};

/** Definition and denominator semantics of one saved metric. */
export interface BenchmarkMetricDefinition {
  /** How the metric was computed by the frozen pipeline. */
  definition: string;
  /** The population or count the metric is defined over (sample, flagged set, or label count). */
  denominator: string;
  /** Stable metric identifier. */
  metric_name: string;
};

/** Verified saved metrics for the canonical ten-run benchmark. */
export interface BenchmarkMetricsResponse {
  dataset_id: string;
  /** Always false: this endpoint never produces a live prediction. */
  is_live_prediction?: boolean;
  /** Always true: values are precomputed and frozen. */
  is_precomputed?: true;
  limitations: Array<string>;
  /** Definitions and denominator semantics that must be shown alongside the values. */
  metric_definitions: Array<BenchmarkMetricDefinition>;
  /** One row per canonical run, in frozen metadata order. */
  metrics: Array<BenchmarkRunMetrics>;
  /** Payload identity: repository-relative path, verified md5 and the verification statement. */
  provenance: Record<string, never>;
  sample: Record<string, never>;
  source_id: string;
};

/** One canonical record, resolved by exact saved row_id. */
export interface BenchmarkRecordResponse {
  dataset_id: string;
  flag: RecordFlagBlock;
  is_live_prediction?: boolean;
  is_precomputed?: true;
  label: RecordLabelBlock;
  limitations: Array<string>;
  provenance: Record<string, never>;
  /** Canonical ULB row identifier (join key). */
  row_id: number;
  run_id: string;
  sample: Record<string, never>;
  score_orientation: Record<string, never>;
  scores: RecordScoreBlock;
};

/** Saved Phase 4 metrics of one canonical run, exactly as admitted. */
export interface BenchmarkRunMetrics {
  average_precision: number;
  f1_at_1pct: number;
  flagged_count: number;
  flagged_proportion: number;
  fn: number;
  fp: number;
  fraud_count: number;
  fraud_prevalence: number;
  /** Model name recorded in the saved metrics row. */
  model: string;
  precision_at_1pct: number;
  recall_at_1pct: number;
  roc_auc: number;
  run_id: string;
  /** Recorded Phase 3 runtime of the run in seconds, when present in the admitted artifact. */
  runtime_seconds: number | unknown;
  sample_size: number;
  threshold_rule: string;
  tn: number;
  tp: number;
};

/** Full detail of a review case (single-case view). */
export interface CaseDetail {
  created_at: string;
  created_by: string;
  dataset_id: string;
  id: string;
  record_ref: string;
  snapshot_id: string;
  status: ReviewStatus;
  summary: string | unknown;
  title: string;
  updated_at: string;
  version: number;
};

/** One event in a case's append-only history. */
export interface CaseEventRecord {
  actor_ref: string;
  case_id: string;
  case_version: number;
  event_at: string;
  event_payload: Record<string, never> | unknown;
  /** Database-generated monotonic sequence for deterministic ordering. */
  event_seq: number;
  event_type: EventType;
  id: string;
  new_status: ReviewStatus | unknown;
  previous_status: ReviewStatus | unknown;
  reason: string | unknown;
};

/** The append-only event history for a case, deterministically ordered. */
export interface CaseHistoryResponse {
  case_id: string;
  items: Array<CaseEventRecord>;
  total: number;
};

/** Paginated list of review cases with a deterministic total order. */
export interface CaseListResponse {
  items: Array<CaseSummary>;
  limit: number;
  offset: number;
  /** Total number of matching cases (before pagination). */
  total: number;
};

/** Summary of a review case (list view). */
export interface CaseSummary {
  created_at: string;
  created_by: string;
  dataset_id: string;
  id: string;
  record_ref: string;
  snapshot_id: string;
  status: ReviewStatus;
  summary: string | unknown;
  title: string;
  updated_at: string;
  version: number;
};

/** Input contract for creating a review case. */
export interface CreateCaseRequest {
  /** Actor reference for the case creator (≤128 chars). Internal trusted context only. */
  created_by: string;
  /** Opaque approved dataset identifier (lowercase kebab slug, ≤64 chars). */
  dataset_id: string;
  /** Opaque stable reference to the reviewed record (≤256 chars; never a path). */
  record_ref: string;
  /** Opaque exact snapshot identifier (lowercase kebab slug, ≤128 chars). */
  snapshot_id: string;
  /** Optional human-written investigation context. */
  summary?: string | unknown;
  /** Concise case description. */
  title: string;
};

/** Bootstrap CSRF token for the future React client.

The same value is set in the readable CSRF cookie; the client must
echo it in the ``X-CSRF-Token`` header on every state-changing
request. A CSRF token is not a credential. */
export interface CsrfTokenResponse {
  /** Signed double-submit CSRF token. */
  csrf_token: string;
};

/** Frozen dataset and experiment context of the canonical benchmark. */
export interface DatasetScope {
  /** Recorded execution environment of the frozen Phase 4 evaluation (reported as recorded; never re-executed). */
  environment: Record<string, never>;
  /** Frozen statement that Phase 4 fitted zero models (evaluation only). */
  model_fitting: Record<string, never>;
  /** Full-population registry context (284,807 observations, 492 positive labels) — recorded context, never mixed into sample metrics. */
  registry_summary: Record<string, never>;
  /** Canonical sample facts: sample_size, fraud_count, fraud_prevalence (30,000 rows / 47 labels on the canonical run). */
  sample: Record<string, never>;
  /** Frozen sampling seed of the 30k draw (42). */
  sample_seed: number;
  /** Frozen score-orientation contract: native lower = more anomalous; anomaly_score = -native_score; ranking metrics use anomaly_score; threshold metrics use saved flags. */
  score_orientation: Record<string, never>;
  /** Frozen threshold percentile (1.0). */
  threshold_percentile: number;
  /** Frozen post-hoc flagging rule (bottom 1% of native scores). */
  threshold_rule: string;
};

/** Machine-readable error payload (sanitized; no tracebacks). */
export interface ErrorBody {
  /** Stable machine-readable error code. */
  code: string;
  details?: Record<string, never>;
  /** Human-readable, sanitized error message. */
  message: string;
  /** Request ID for cross-referencing server logs. */
  request_id: string;
};

/** Envelope shared by every error response. */
export interface ErrorEnvelope {
  error: ErrorBody;
};

/** Controlled event-type vocabulary for the append-only ``case_events`` table. */
export type EventType = "created" | "note_added" | "status_changed" | "decision_recorded" | "reopened";

/** Liveness: the API process can answer requests. */
export interface HealthLiveResponse {
  /** Application name. */
  service: string;
  status: "alive";
  /** Backend application version. */
  version: string;
};

/** Login credentials (bounded; login payloads cannot be oversized). */
export interface LoginRequest {
  /** Account password (8-128 characters). */
  password: string;
  /** Login identifier (normalized server-side). */
  username: string;
};

/** Logout acknowledgement (the session is revoked server-side). */
export interface LogoutResponse {
  /** Fixed value: 'logged_out'. */
  status: string;
};

/** Non-sensitive application metadata (``GET /api/v1/meta``). */
export interface MetaResponse {
  /** Versioned API namespace. */
  api_version: "v1";
  /** Backend application version. */
  app_version: string;
  /** Application name. */
  application: string;
  environment: "development" | "test" | "production";
  /** Implemented versus planned application features. */
  features: Record<string, never>;
  /** Git commit SHA if supplied by the deployment environment; never fabricated. */
  git_commit_sha?: string | unknown;
  /** Availability of major application subsystems. */
  subsystems: Record<string, never>;
};

/** Provenance of a run's parameter configuration. */
export interface ParameterSourceProvenance {
  /** Byte canonicalization applied before hashing: 'frozen-checker-compatible' (CRLF→LF, matching ci/check_frozen_integrity.py) or 'windows-commit-manifest-compatible' (LF→CRLF reconstruction matching the Windows-produced Phase 4 commit manifest). */
  canonicalization: string;
  /** Digest algorithm used for provenance. */
  digest_algorithm: "sha-256";
  /** Statement of how the parameters were obtained (frozen source; no framework defaults inferred). */
  note: string;
  /** Repository-relative path to the frozen artifact (never absolute). */
  path: string;
  /** SHA-256 digest of the artifact bytes. */
  sha256: string;
};

/** One configured dependency check (name and status only; no details). */
export interface ReadinessCheck {
  name: string;
  status: "ready" | "unavailable";
};

/** Readiness: all configured required dependencies are ready. */
export interface ReadinessResponse {
  checks?: Array<ReadinessCheck>;
  status: "ready";
};

/** Input contract for recording a structured decision.

A decision is a status transition with an explicit outcome and a
review rationale. It is persisted as a ``decision_recorded`` event
(and, when the outcome changes the status, a ``status_changed``
event in the same transaction). */
export interface RecordDecisionRequest {
  /** Actor reference for the decision author (≤128 chars). */
  actor_ref: string;
  /** The case version the caller read; used for optimistic concurrency. */
  expected_version: number;
  /** Decision outcome status (must be a legal transition from the current status). */
  outcome: ReviewStatus;
  /** Structured review rationale for the decision. */
  rationale: string;
};

/** Saved detector flag of a canonical record. */
export interface RecordFlagBlock {
  /** Provenance of the flag: saved Phase 3 output; never recomputed. */
  provenance: string;
  /** Saved Phase 3 bottom-1% flag (0/1). */
  value: number;
};

/** Ground-truth label of a canonical record. */
export interface RecordLabelBlock {
  /** Ground-truth evaluation label (0/1). */
  Class: number;
  /** Provenance of the label: ground-truth ULB evaluation label joined on row_id; distinct from the detector flag. */
  provenance: string;
};

/** Saved scores of a canonical record. */
export interface RecordScoreBlock {
  anomaly_definition: string;
  /** Saved oriented score -native_score (higher = more anomalous). */
  anomaly_score: number;
  native_definition: string;
  /** Phase 3 native estimator score (lower = more anomalous). */
  native_score: number;
};

/** Provenance of a precomputed research result (artifact + digest). */
export interface ResearchProvenance {
  /** Repository-relative path to the frozen artifact. */
  artifact_path: string;
  /** SHA-256 digest of the frozen artifact bytes. */
  artifact_sha256: string;
  /** Byte canonicalization applied before hashing. 'frozen-checker-compatible' matches ci/check_frozen_integrity.py. */
  canonicalization: "raw-bytes" | "frozen-checker-compatible";
  /** Digest algorithm. */
  digest_algorithm: "sha-256";
};

/** One precomputed aggregate reference value with its description.

``value_type`` records the primitive type of ``value`` so a consumer
can parse the value without guessing; it is one of ``"int"``,
``"float"`` or ``"str"``. */
export interface ResearchResultItem {
  /** Human-readable description of the metric. */
  description: string;
  /** Stable metric identifier. */
  metric_name: string;
  /** The precomputed value (an int, a float or a str). */
  value: number | number | string;
  /** Primitive type of ``value``: int, float or str. */
  value_type: "int" | "float" | "str";
};

/** Precomputed research results with full provenance.

Every field except ``results`` is metadata / provenance. The
``results`` list carries the 18 frozen aggregate reference values from
the ULB credit-card fraud benchmark experiment (Stream A, Phase 6). */
export interface ResearchResultsResponse {
  dataset_id: string;
  /** Post-hoc selection caveat reused verbatim from Phase 5A. */
  exploratory_caveat: string;
  /** Frozen interpretation principles every consumer must respect. */
  interpretation_principles: Array<string>;
  /** Always false: this endpoint never produces a live prediction. */
  is_live_prediction?: boolean;
  /** Always true: results are precomputed and frozen, never recomputed on request. */
  is_precomputed?: true;
  limitations: Array<string>;
  model_methods: Array<string>;
  provenance: ResearchProvenance;
  /** The precomputed aggregate reference values. */
  results: Array<ResearchResultItem>;
  source_id: string;
};

/** Full metadata for one read-only research source, with provenance.

Extends :class:`ResearchSourceSummary` with the frozen-artifact
provenance and the experimental context the results were produced
under (frozen, never recomputed). */
export interface ResearchSourceDetail {
  /** Repository-relative path to the frozen artifact (never absolute). */
  artifact_path: string;
  /** SHA-256 digest of the frozen artifact bytes. */
  artifact_sha256: string;
  /** Whether the source is currently servable. 'registered' means the source is approved but not yet verified at runtime; 'available' means verified and servable; 'unavailable' means the artifact is missing or failed integrity verification. */
  availability: "available" | "unavailable" | "registered";
  /** How the artifact bytes were canonicalized before hashing. 'frozen-checker-compatible' matches ci/check_frozen_integrity.py (CRLF→LF for text files, raw for binary). */
  canonicalization: "raw-bytes" | "frozen-checker-compatible";
  /** Frozen dataset the reported results pertain to. */
  dataset_id: string;
  /** Digest algorithm used for provenance. */
  digest_algorithm: "sha-256";
  /** Frozen experimental parameters the results were produced under (sample size, label count, threshold rule, run ids, detector grids). */
  experimental_context: Record<string, never>;
  /** Scientific limitations that apply to every result from this source. */
  limitations: Array<string>;
  /** Detector methods whose aggregate results are reported. */
  model_methods: Array<string>;
  /** Research stream or family the source belongs to. */
  research_family: string;
  /** Aggregation level of the reported results. */
  result_granularity: string;
  /** Kind of result exposed by this source. */
  result_type: string;
  /** Opaque research-source identifier (never a filesystem path). */
  source_id: string;
  /** Supporting frozen artifacts consumed by the adapter (path, SHA-256, role). Each artifact's digest is verified against the trusted frozen manifest before its bytes are parsed. */
  supporting_artifacts?: Array<Record<string, never>>;
};

/** List of approved read-only research sources. */
export interface ResearchSourceListResponse {
  /** Number of items in ``items``. */
  count: number;
  /** Approved research sources in deterministic order. */
  items: Array<ResearchSourceSummary>;
};

/** Public summary of one approved read-only research source.

Carries no provenance or experimental detail: it is the list-view
descriptor. Use the detail endpoint for artifact provenance and the
frozen experimental context. */
export interface ResearchSourceSummary {
  /** Whether the source is currently servable. 'registered' means the source is approved but not yet verified at runtime; 'available' means verified and servable; 'unavailable' means the artifact is missing or failed integrity verification. */
  availability: "available" | "unavailable" | "registered";
  /** Frozen dataset the reported results pertain to. */
  dataset_id: string;
  /** Detector methods whose aggregate results are reported. */
  model_methods: Array<string>;
  /** Research stream or family the source belongs to. */
  research_family: string;
  /** Aggregation level of the reported results. */
  result_granularity: string;
  /** Kind of result exposed by this source. */
  result_type: string;
  /** Opaque research-source identifier (never a filesystem path). */
  source_id: string;
};

/** Controlled review-status vocabulary.

A ``str`` enum so values survive JSON round-trips and SQLA string
columns without custom serializers. */
export type ReviewStatus = "not_reviewed" | "under_review" | "explained_deviation" | "needs_source_verification" | "escalated_for_examination";

/** Server-side application roles. */
export type Role = "viewer" | "reviewer" | "admin";

/** All registered sources (currently none are configured). */
export interface SourceListResponse {
  count: number;
  sources: Array<SourceSummary>;
};

/** Public description of an approved, registered data source. */
export interface SourceSummary {
  analysis_status: "verified_benchmark" | "exploratory" | "restricted" | "blocked" | "unavailable";
  dataset_kind: "ulb_benchmark" | "pmgsy_infrastructure" | "mplads_administration";
  integrity_status: "verified" | "unverified_legacy" | "integrity_failed" | "unavailable";
  /** Opaque registered source identifier (not a filesystem path). */
  source_id: string;
};

/** Full detail of one synthetic demonstration record.

Explicitly fictional. No ML anomaly score is included. The evidence
fields are illustrative descriptions, not measured results. */
export interface SyntheticRecordDetail {
  administrative_context: string;
  dataset_id: string;
  /** Fictional description; NOT a research finding. */
  description: string;
  /** Illustrative evidence description; not a measured result. */
  evidence_summary: string;
  /** Explicit scientific limitations of the synthetic data. */
  limitations: string;
  record_ref: string;
  snapshot_id: string;
  synthetic?: boolean;
  title: string;
};

/** List of synthetic demonstration records. */
export interface SyntheticRecordListResponse {
  /** The synthetic dataset identifier. */
  dataset_id: string;
  items: Array<SyntheticRecordSummary>;
  /** The synthetic snapshot identifier. */
  snapshot_id: string;
  total: number;
};

/** One synthetic demonstration record (list view).

Explicitly fictional — NOT a research finding. The ``synthetic`` flag
is always true; the ``label`` field carries the prominent
``SYNTHETIC DEMONSTRATION RECORD`` warning. */
export interface SyntheticRecordSummary {
  /** Synthetic dataset identifier. */
  dataset_id: string;
  /** Stable opaque reference to the synthetic record. */
  record_ref: string;
  /** Synthetic snapshot identifier. */
  snapshot_id: string;
  /** Always true for demonstration records. */
  synthetic?: boolean;
  /** Synthetic record title (always carries the SYNTHETIC warning). */
  title: string;
};

/** Input contract for a status transition. */
export interface TransitionStatusRequest {
  /** Actor reference for the transition author (≤128 chars). */
  actor_ref: string;
  /** The case version the caller read; used for optimistic concurrency. */
  expected_version: number;
  /** Human-readable reason for the transition (required). */
  reason: string;
  /** Target status (must be a legal transition). */
  to_status: ReviewStatus;
};

/** Sanitized public representation of an authenticated user.

Carries only approved public fields: user id, username, display
name, role and the effective permission list. Never a password
hash, session token or account internals. */
export interface UserResponse {
  /** Human-readable display name. */
  display_name: string;
  /** Stable user identifier (canonical actor reference). */
  id: string;
  /** Effective permissions derived from the role (server-side). */
  permissions: Array<string>;
  /** Server-side role. */
  role: Role;
  /** Normalized login identifier. */
  username: string;
};

