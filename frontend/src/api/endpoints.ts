// Typed endpoint wrappers for the PEIARS API.
//
// Each function maps to one OpenAPI operation. The signatures expose the
// exact request and response types from `contracts.ts`. State-changing
// operations accept the CSRF token and add the X-CSRF-Token header.

import type {
  AddNoteRequest,
  BenchmarkCatalogResponse,
  BenchmarkExperimentDetail,
  BenchmarkMetricsResponse,
  BenchmarkRecordResponse,
  CaseDetail,
  CaseHistoryResponse,
  CaseListResponse,
  CreateCaseRequest,
  CsrfTokenResponse,
  HealthLiveResponse,
  LoginRequest,
  LogoutResponse,
  MetaResponse,
  ReadinessResponse,
  RecordDecisionRequest,
  ResearchResultsResponse,
  ResearchSourceDetail,
  ResearchSourceListResponse,
  ReviewStatus,
  SourceListResponse,
  SourceSummary,
  SyntheticRecordDetail,
  SyntheticRecordListResponse,
  TransitionStatusRequest,
  UserResponse,
  DatasetKind,
} from "@/api/contracts";
import { CSRF_HEADER } from "@/api/contracts";
import {
  AUTH_TIMEOUT_MS,
  DEFAULT_TIMEOUT_MS,
  type RequestOptions,
  request,
} from "@/api/client";

// --- Health -------------------------------------------------------------

export function getHealthLive(signal?: AbortSignal): Promise<HealthLiveResponse> {
  return request<HealthLiveResponse>("/health/live", { signal, timeoutMs: 4_000 });
}

export function getHealthReady(signal?: AbortSignal): Promise<ReadinessResponse> {
  return request<ReadinessResponse>("/health/ready", { signal, timeoutMs: 5_000 });
}

// --- Meta ---------------------------------------------------------------

export function getMeta(signal?: AbortSignal): Promise<MetaResponse> {
  return request<MetaResponse>("/meta", { signal, timeoutMs: DEFAULT_TIMEOUT_MS });
}

// --- Sources ------------------------------------------------------------

export function listSources(
  opts: { datasetKind?: DatasetKind; signal?: AbortSignal } = {},
): Promise<SourceListResponse> {
  const query: RequestOptions["query"] = {};
  if (opts.datasetKind) query.dataset_kind = opts.datasetKind;
  return request<SourceListResponse>("/sources", {
    query,
    signal: opts.signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getSource(sourceId: string, signal?: AbortSignal): Promise<SourceSummary> {
  return request<SourceSummary>(`/sources/${encodeURIComponent(sourceId)}`, {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

// --- Synthetic demonstration records (PR-05B) ---------------------------

export function listSyntheticRecords(signal?: AbortSignal): Promise<SyntheticRecordListResponse> {
  return request<SyntheticRecordListResponse>("/synthetic/records", {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getSyntheticRecord(recordRef: string, signal?: AbortSignal): Promise<SyntheticRecordDetail> {
  return request<SyntheticRecordDetail>(`/synthetic/records/${encodeURIComponent(recordRef)}`, {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

// --- Auth ---------------------------------------------------------------

/** Bootstrap the signed double-submit CSRF token (sets the readable cookie). */
export function getCsrfToken(signal?: AbortSignal): Promise<CsrfTokenResponse> {
  return request<CsrfTokenResponse>("/auth/csrf", {
    signal,
    timeoutMs: AUTH_TIMEOUT_MS,
  });
}

/** Resolve the authenticated user (restore session on app load). */
export function getCurrentUser(signal?: AbortSignal): Promise<UserResponse> {
  return request<UserResponse>("/auth/me", {
    signal,
    timeoutMs: AUTH_TIMEOUT_MS,
  });
}

/** Verify credentials and create a server-side session (sets HttpOnly cookie). */
export function login(
  payload: LoginRequest,
  csrfToken: string,
  signal?: AbortSignal,
): Promise<UserResponse> {
  return request<UserResponse>("/auth/login", {
    method: "POST",
    json: payload,
    headers: { [CSRF_HEADER]: csrfToken },
    signal,
    timeoutMs: AUTH_TIMEOUT_MS,
  });
}

/** Revoke the server-side session (expires both cookies). */
export function logout(csrfToken: string, signal?: AbortSignal): Promise<LogoutResponse> {
  return request<LogoutResponse>("/auth/logout", {
    method: "POST",
    headers: { [CSRF_HEADER]: csrfToken },
    signal,
    timeoutMs: AUTH_TIMEOUT_MS,
  });
}

// --- Review cases (PR-05B) ----------------------------------------------

export function listCases(
  opts: { status?: ReviewStatus; limit?: number; offset?: number; signal?: AbortSignal } = {},
): Promise<CaseListResponse> {
  const query: RequestOptions["query"] = {};
  if (opts.status) query.status = opts.status;
  if (opts.limit !== undefined) query.limit = opts.limit;
  if (opts.offset !== undefined) query.offset = opts.offset;
  return request<CaseListResponse>("/cases", {
    query,
    signal: opts.signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function createCase(
  payload: CreateCaseRequest,
  csrfToken: string,
  signal?: AbortSignal,
): Promise<CaseDetail> {
  return request<CaseDetail>("/cases", {
    method: "POST",
    json: payload,
    headers: { [CSRF_HEADER]: csrfToken },
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getCase(caseId: string, signal?: AbortSignal): Promise<CaseDetail> {
  return request<CaseDetail>(`/cases/${encodeURIComponent(caseId)}`, {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getCaseHistory(caseId: string, signal?: AbortSignal): Promise<CaseHistoryResponse> {
  return request<CaseHistoryResponse>(`/cases/${encodeURIComponent(caseId)}/history`, {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function addCaseNote(
  caseId: string,
  payload: AddNoteRequest,
  csrfToken: string,
  signal?: AbortSignal,
): Promise<CaseDetail> {
  return request<CaseDetail>(`/cases/${encodeURIComponent(caseId)}/notes`, {
    method: "POST",
    json: payload,
    headers: { [CSRF_HEADER]: csrfToken },
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function transitionCaseStatus(
  caseId: string,
  payload: TransitionStatusRequest,
  csrfToken: string,
  signal?: AbortSignal,
): Promise<CaseDetail> {
  return request<CaseDetail>(`/cases/${encodeURIComponent(caseId)}/transitions`, {
    method: "POST",
    json: payload,
    headers: { [CSRF_HEADER]: csrfToken },
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function recordCaseDecision(
  caseId: string,
  payload: RecordDecisionRequest,
  csrfToken: string,
  signal?: AbortSignal,
): Promise<CaseDetail> {
  return request<CaseDetail>(`/cases/${encodeURIComponent(caseId)}/decisions`, {
    method: "POST",
    json: payload,
    headers: { [CSRF_HEADER]: csrfToken },
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

// --- Research (PR-08: read-only frozen scientific results) --------------

export function getResearchSources(signal?: AbortSignal): Promise<ResearchSourceListResponse> {
  return request<ResearchSourceListResponse>("/research/sources", {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getResearchSource(
  sourceId: string,
  signal?: AbortSignal,
): Promise<ResearchSourceDetail> {
  return request<ResearchSourceDetail>(
    `/research/sources/${encodeURIComponent(sourceId)}`,
    { signal, timeoutMs: DEFAULT_TIMEOUT_MS },
  );
}

export function getResearchResults(
  sourceId: string,
  signal?: AbortSignal,
): Promise<ResearchResultsResponse> {
  return request<ResearchResultsResponse>(
    `/research/sources/${encodeURIComponent(sourceId)}/results`,
    { signal, timeoutMs: DEFAULT_TIMEOUT_MS },
  );
}

// --- Benchmark (PR-09: canonical ten-run IF/LOF benchmark) --------------

export function getBenchmarkExperiments(
  signal?: AbortSignal,
): Promise<BenchmarkCatalogResponse> {
  return request<BenchmarkCatalogResponse>("/research/benchmark/experiments", {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getBenchmarkExperiment(
  runId: string,
  signal?: AbortSignal,
): Promise<BenchmarkExperimentDetail> {
  return request<BenchmarkExperimentDetail>(
    `/research/benchmark/experiments/${encodeURIComponent(runId)}`,
    { signal, timeoutMs: DEFAULT_TIMEOUT_MS },
  );
}

export function getBenchmarkMetrics(
  signal?: AbortSignal,
): Promise<BenchmarkMetricsResponse> {
  return request<BenchmarkMetricsResponse>("/research/benchmark/metrics", {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getBenchmarkRecord(
  runId: string,
  rowId: number,
  signal?: AbortSignal,
): Promise<BenchmarkRecordResponse> {
  return request<BenchmarkRecordResponse>(
    `/research/benchmark/experiments/${encodeURIComponent(runId)}/records/${rowId}`,
    { signal, timeoutMs: DEFAULT_TIMEOUT_MS },
  );
}
