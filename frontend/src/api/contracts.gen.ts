// AUTO-GENERATED from backend/contracts/openapi.json — DO NOT EDIT.
// Regenerate with: npm run openapi:check
// Source: PEIARS API v0.4.0
// This file is the reproducible source of truth for OpenAPI-mirrored types.
// The application imports from contracts.ts (hand-maintained, may include
// frontend-only helpers). Drift between the two is reported by the check.

// --- Schemas -----------------------------------------------------------

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

