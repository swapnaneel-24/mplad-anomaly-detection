// Typed endpoint wrappers for the PEIARS API.
//
// Each function maps to one OpenAPI operation. The signatures expose the
// exact request and response types from `contracts.ts`. State-changing
// operations accept the CSRF token and add the X-CSRF-Token header.

import type {
  CsrfTokenResponse,
  HealthLiveResponse,
  LoginRequest,
  LogoutResponse,
  MetaResponse,
  ReadinessResponse,
  SourceListResponse,
  SourceSummary,
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
