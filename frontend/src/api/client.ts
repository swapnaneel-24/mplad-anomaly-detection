// Centralized HTTP client for the PEIARS API.
//
// Design (PR-05A §10):
//   - All traffic goes through /api/v1/* (same-origin in dev via the Vite
//     proxy; same-origin in production by deployment design).
//   - Credentialed (cookies attached) so the HttpOnly session cookie and
//     the readable CSRF cookie flow with every request.
//   - Controlled timeout via AbortController; caller may pass an external
//     AbortSignal for cancellation.
//   - Structured ErrorEnvelope parsing on every non-2xx; network failures
//     raise a distinct ApiError with code "REQUEST_FAILED" so callers can
//     distinguish "server said no" from "could not reach server".
//   - The X-Request-ID response header is captured and surfaced for
//     debugging; when the server's envelope includes a request_id it is
//     preferred (it is the authoritative ID).
//   - No stack traces, no headers, no cookies, no bodies are ever logged.
//     Only the request method, path, status and request ID are logged at
//     warn/error level.

import type {
  ErrorEnvelope,
  ErrorBody,
} from "@/api/contracts";
import { REQUEST_ID_HEADER } from "@/api/contracts";

/** API base path (served same-origin; the Vite dev proxy forwards to :8000). */
export const API_BASE = "/api/v1" as const;

/** Default request timeout. State-changing auth requests use a shorter one. */
export const DEFAULT_TIMEOUT_MS = 12_000;
export const AUTH_TIMEOUT_MS = 8_000;

/** Discriminated error thrown by `request()` for any non-success outcome. */
export interface ApiErrorOptions {
  /** HTTP status (0 for network failure / timeout / abort). */
  status: number;
  /** Stable machine-readable code (from the envelope when available). */
  code: string;
  /** Sanitized human-readable message. */
  message: string;
  /** Authoritative request ID (envelope value preferred over header). */
  requestId: string | null;
  /** True when the request was aborted via AbortSignal. */
  aborted: boolean;
  /** True when the request timed out. */
  timedOut: boolean;
  /** True when the fetch never reached the server (network error). */
  network: boolean;
  /** Optional structured details from the envelope. */
  details?: Record<string, unknown>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;
  readonly aborted: boolean;
  readonly timedOut: boolean;
  readonly network: boolean;
  readonly details?: Record<string, unknown>;

  constructor(opts: ApiErrorOptions) {
    super(opts.message);
    this.name = "ApiError";
    this.status = opts.status;
    this.code = opts.code;
    this.requestId = opts.requestId;
    this.aborted = opts.aborted;
    this.timedOut = opts.timedOut;
    this.network = opts.network;
    this.details = opts.details;
  }

  /** Convenience predicates used by callers and tests. */
  get isUnauthorized(): boolean {
    return this.status === 401;
  }
  get isForbidden(): boolean {
    return this.status === 403;
  }
  get isRateLimited(): boolean {
    return this.status === 429;
  }
  get isServiceNotReady(): boolean {
    return this.status === 503 || this.code === "SERVICE_NOT_READY";
  }
  get isNetwork(): boolean {
    return this.network;
  }
}

/** Request options accepted by `request()`. */
export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  /** JSON-serializable request body. */
  json?: unknown;
  /** Query parameters (serialized with URLSearchParams). */
  query?: Record<string, string | number | boolean | undefined | null>;
  /** Optional extra headers. CSRF header is added by callers of writes. */
  headers?: Record<string, string>;
  /** Request timeout in milliseconds. */
  timeoutMs?: number;
  /** External abort signal (in addition to the timeout signal). */
  signal?: AbortSignal;
  /** Override credentials mode (default: include). */
  credentials?: RequestCredentials;
}

/** Internal: compose the abort signal from timeout + caller signal. */
function composeSignal(timeoutMs: number, external?: AbortSignal): {
  signal: AbortSignal;
  timer: ReturnType<typeof setTimeout> | null;
  cleanup: () => void;
} {
  const controller = new AbortController();
  const timer =
    timeoutMs > 0
      ? setTimeout(() => controller.abort(new DOMException("TimeoutError", "TimeoutError")), timeoutMs)
      : null;
  if (external) {
    if (external.aborted) controller.abort(external.reason);
    else external.addEventListener("abort", () => controller.abort(external.reason), { once: true });
  }
  return {
    signal: controller.signal,
    timer,
    cleanup: () => {
      if (timer) clearTimeout(timer);
    },
  };
}

/** Internal: build the URL with query string. */
function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) continue;
    params.append(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

/** Internal: parse an ErrorEnvelope from a Response, defensively. */
async function parseErrorEnvelope(response: Response): Promise<ErrorBody | null> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) return null;
  try {
    const body = (await response.json()) as Partial<ErrorEnvelope>;
    const inner = body?.error;
    if (!inner || typeof inner !== "object") return null;
    return {
      code: typeof inner.code === "string" ? inner.code : "REQUEST_FAILED",
      message: typeof inner.message === "string" ? inner.message : "The request failed.",
      request_id: typeof inner.request_id === "string" ? inner.request_id : "",
      details:
        inner.details && typeof inner.details === "object"
          ? (inner.details as Record<string, unknown>)
          : undefined,
    };
  } catch {
    return null;
  }
}

/**
 * Issue a credentialed JSON request to the PEIARS API.
 *
 * Throws `ApiError` for any non-2xx status, network failure, timeout or
 * abort. Never throws a raw `Error` or `TypeError`.
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    method = "GET",
    json,
    query,
    headers = {},
    timeoutMs = DEFAULT_TIMEOUT_MS,
    signal: externalSignal,
    credentials = "include",
  } = options;

  const url = buildUrl(path, query);
  const { signal, cleanup } = composeSignal(timeoutMs, externalSignal);

  const init: RequestInit = {
    method,
    credentials,
    signal,
    headers: {
      Accept: "application/json",
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
  };
  if (json !== undefined) {
    init.body = JSON.stringify(json);
  }

  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (err: unknown) {
    cleanup();
    const aborted = signal.aborted;
    const timedOut =
      aborted && (signal.reason instanceof DOMException && signal.reason.name === "TimeoutError");
    const externalAborted =
      aborted && !timedOut && (externalSignal?.aborted === true);
    if (timedOut) {
      throw new ApiError({
        status: 0,
        code: "REQUEST_FAILED",
        message: "The request timed out.",
        requestId: null,
        aborted: false,
        timedOut: true,
        network: false,
      });
    }
    if (externalAborted) {
      throw new ApiError({
        status: 0,
        code: "REQUEST_FAILED",
        message: "The request was aborted.",
        requestId: null,
        aborted: true,
        timedOut: false,
        network: false,
      });
    }
    // Network failure (DNS, connection refused, CORS preflight reject, etc.).
    console.warn("[api] network failure", { method, path, name: (err as Error)?.name });
    throw new ApiError({
      status: 0,
      code: "REQUEST_FAILED",
      message: "Cannot reach the API. Check your connection and retry.",
      requestId: null,
      aborted: false,
      timedOut: false,
      network: true,
    });
  }
  cleanup();

  const headerRequestId = response.headers.get(REQUEST_ID_HEADER);

  if (!response.ok) {
    const envelope = await parseErrorEnvelope(response);
    const code = envelope?.code ?? "REQUEST_FAILED";
    const message =
      envelope?.message ?? `The request failed with status ${response.status}.`;
    const requestId = envelope?.request_id || headerRequestId || null;
    throw new ApiError({
      status: response.status,
      code,
      message,
      requestId,
      aborted: false,
      timedOut: false,
      network: false,
      details: envelope?.details,
    });
  }

  // 204 No Content: no body to parse.
  if (response.status === 204) {
    return undefined as T;
  }
  // Empty body: return undefined cast to T (caller knows the shape).
  const text = await response.text();
  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError({
      status: response.status,
      code: "INTERNAL_SERVER_ERROR",
      message: "The API returned a non-JSON response.",
      requestId: headerRequestId,
      aborted: false,
      timedOut: false,
      network: false,
    });
  }
}
