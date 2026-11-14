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

