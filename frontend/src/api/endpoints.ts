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
  Phase5AAgreementGroupsResponse,
  Phase5AAgreementMatrixResponse,
  Phase5ABootstrapMetricsResponse,
  Phase5ADiscoveryCurveResponse,
  Phase5AHypergeometricResponse,
  Phase5AMultithresholdResponse,
  Phase5APairedDifferencesResponse,
  Phase5AUncertaintyResponse,
  Phase5ACombinedAgreementResponse,
  Phase5AProtocolResponse,
  FigureCatalogResponse,
  TraceabilityResponse,
  Phase5AReviewPoliciesResponse,
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
  WorkbenchPackageDetail,
  WorkbenchPackageListResponse,
  WorkbenchSnapshotDetail,
  WorkbenchSnapshotListResponse,
  DatasetKind,
  WorkbenchInvestigationListResponse,
  InvestigationDetail,
  InvestigationHistoryResponse,
  AppendInvestigationNoteRequest,
  AppendInvestigationNoteResponse,
} from "@/api/contracts";
import { CSRF_HEADER } from "@/api/contracts";
import {
  API_BASE,
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

// --- Phase 5A evidence (PR-10: uncertainty/agreement/review-policy) ------

export function getPhase5AProtocol(signal?: AbortSignal): Promise<Phase5AProtocolResponse> {
  return request<Phase5AProtocolResponse>("/research/phase5a/catalog", {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getPhase5ABootstrap(signal?: AbortSignal): Promise<Phase5ABootstrapMetricsResponse> {
  return request<Phase5ABootstrapMetricsResponse>("/research/phase5a/bootstrap", {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getPhase5APairedDifferences(
  signal?: AbortSignal,
): Promise<Phase5APairedDifferencesResponse> {
  return request<Phase5APairedDifferencesResponse>("/research/phase5a/paired-differences", {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getPhase5AAgreementMatrix(
  kind: "spearman" | "jaccard",
  signal?: AbortSignal,
): Promise<Phase5AAgreementMatrixResponse> {
  return request<Phase5AAgreementMatrixResponse>(
    `/research/phase5a/agreement/${encodeURIComponent(kind)}`,
    { signal, timeoutMs: DEFAULT_TIMEOUT_MS },
  );
}

export function getPhase5AOverlapNull(signal?: AbortSignal): Promise<Phase5AHypergeometricResponse> {
  return request<Phase5AHypergeometricResponse>("/research/phase5a/overlap-null", {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getPhase5AGroups(signal?: AbortSignal): Promise<Phase5AAgreementGroupsResponse> {
  return request<Phase5AAgreementGroupsResponse>("/research/phase5a/review-policies", {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getPhase5APolicies(signal?: AbortSignal): Promise<Phase5AReviewPoliciesResponse> {
  return request<Phase5AReviewPoliciesResponse>("/research/phase5a/policies", {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getPhase5AThresholds(signal?: AbortSignal): Promise<Phase5AMultithresholdResponse> {
  return request<Phase5AMultithresholdResponse>("/research/phase5a/thresholds", {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getPhase5ADiscoveryCurve(
  runId: string,
  opts: { limit?: number; offset?: number; signal?: AbortSignal } = {},
): Promise<Phase5ADiscoveryCurveResponse> {
  const params = new URLSearchParams({ run_id: runId });
  if (opts.limit !== undefined) params.set("limit", String(opts.limit));
  if (opts.offset !== undefined) params.set("offset", String(opts.offset));
  return request<Phase5ADiscoveryCurveResponse>(
    `/research/phase5a/discovery-curve?${params.toString()}`,
    { signal: opts.signal, timeoutMs: DEFAULT_TIMEOUT_MS },
  );
}


export function getPhase5AUncertainty(signal?: AbortSignal): Promise<Phase5AUncertaintyResponse> {
  return request<Phase5AUncertaintyResponse>("/research/phase5a/uncertainty", {
    signal, timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getPhase5AAgreement(signal?: AbortSignal): Promise<Phase5ACombinedAgreementResponse> {
  return request<Phase5ACombinedAgreementResponse>("/research/phase5a/agreement", {
    signal, timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getPhase5AReviewPolicies(signal?: AbortSignal): Promise<Phase5AAgreementGroupsResponse> {
  return request<Phase5AAgreementGroupsResponse>("/research/phase5a/review-policies", {
    signal, timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

// --- Phase 5B figures (PR-11) ------------------------------------------

export function getPhase5BCatalog(signal?: AbortSignal): Promise<FigureCatalogResponse> {
  return request<FigureCatalogResponse>("/research/phase5b/catalog", {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getPhase5BTraceability(signal?: AbortSignal): Promise<TraceabilityResponse> {
  return request<TraceabilityResponse>("/research/phase5b/traceability", {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

/** URL builder for a canonical figure PNG (usable directly as <img src=...>). */
export function phase5bFigureImageUrl(figureNo: number): string {
  return `${API_BASE}/research/phase5b/figures/${figureNo}/image`;
}

// --- Read-Only Workbench Snapshots & PMGSY Packages (Prompt B) --------

export function listWorkbenchSnapshots(
  signal?: AbortSignal,
): Promise<WorkbenchSnapshotListResponse> {
  return request<WorkbenchSnapshotListResponse>("/workbench/snapshots", {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getWorkbenchSnapshot(
  snapshotId: string,
  signal?: AbortSignal,
): Promise<WorkbenchSnapshotDetail> {
  return request<WorkbenchSnapshotDetail>(
    `/workbench/snapshots/${encodeURIComponent(snapshotId)}`,
    {
      signal,
      timeoutMs: DEFAULT_TIMEOUT_MS,
    },
  );
}

export function listWorkbenchPmgsyPackages(
  signal?: AbortSignal,
): Promise<WorkbenchPackageListResponse> {
  return request<WorkbenchPackageListResponse>("/workbench/pmgsy/packages", {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getWorkbenchPmgsyPackage(
  caseId: string,
  signal?: AbortSignal,
): Promise<WorkbenchPackageDetail> {
  return request<WorkbenchPackageDetail>(
    `/workbench/pmgsy/packages/${encodeURIComponent(caseId)}`,
    {
      signal,
      timeoutMs: DEFAULT_TIMEOUT_MS,
    },
  );
}

export function listWorkbenchInvestigations(
  signal?: AbortSignal,
): Promise<WorkbenchInvestigationListResponse> {
  return request<WorkbenchInvestigationListResponse>("/workbench/investigations", {
    signal,
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getWorkbenchInvestigation(
  caseId: string,
  signal?: AbortSignal,
): Promise<InvestigationDetail> {
  return request<InvestigationDetail>(
    `/workbench/investigations/${encodeURIComponent(caseId)}`,
    {
      signal,
      timeoutMs: DEFAULT_TIMEOUT_MS,
    },
  );
}

export function getWorkbenchInvestigationHistory(
  caseId: string,
  signal?: AbortSignal,
): Promise<InvestigationHistoryResponse> {
  return request<InvestigationHistoryResponse>(
    `/workbench/investigations/${encodeURIComponent(caseId)}/history`,
    {
      signal,
      timeoutMs: DEFAULT_TIMEOUT_MS,
    },
  );
}

export function appendWorkbenchInvestigationNote(
  caseId: string,
  body: AppendInvestigationNoteRequest,
  signal?: AbortSignal,
): Promise<AppendInvestigationNoteResponse> {
  return request<AppendInvestigationNoteResponse>(
    `/workbench/investigations/${encodeURIComponent(caseId)}/notes`,
    {
      method: "POST",
      body: body,
      signal,
      timeoutMs: DEFAULT_TIMEOUT_MS,
    },
  );
}
