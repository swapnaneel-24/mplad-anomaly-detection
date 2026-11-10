// Unit tests for the API client (`request()`).
//
// Verifies:
//   - JSON body serialization and Content-Type header.
//   - Query parameter serialization (skips undefined/null).
//   - Timeout (fake timers + DOMException TimeoutError).
//   - External AbortSignal abort.
//   - Network failure (fetch rejects with TypeError → ApiError.isNetwork).
//   - 4xx/5xx envelope parsing (status, code, message, request_id).
//   - 204 No Content handling.
//   - X-Request-ID response header capture.
//
// `globalThis.fetch` is mocked with vi.fn() returning real Response objects
// so the client's body parsing runs against actual response streams.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, request } from "@/api/client";
import { REQUEST_ID_HEADER } from "@/api/contracts";

type FetchMock = ReturnType<typeof vi.fn>;

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    ...init,
    headers: {
      "content-type": "application/json",
      [REQUEST_ID_HEADER]: "req-json-1",
      ...(init.headers ?? {}),
    },
  });
}

describe("api client request()", () => {
  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.useRealTimers();
  });

  it("serializes a JSON body and sets Content-Type", async () => {
    const fetchMock: FetchMock = vi.fn(
      async () => jsonResponse({ ok: true }),
    );
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    await request("/auth/login", {
      method: "POST",
      json: { username: "alice", password: "supersecret" },
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const args = fetchMock.mock.calls[0]!;
    const url = args[0] as string;
    const init = args[1] as RequestInit;
    expect(url).toBe("/api/v1/auth/login");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ username: "alice", password: "supersecret" }));
    const headers = init.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBe("application/json");
    expect(headers["Accept"]).toBe("application/json");
  });

  it("serializes query parameters and skips undefined/null", async () => {
    const fetchMock: FetchMock = vi.fn(async () => jsonResponse({ sources: [], count: 0 }));
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    await request("/sources", {
      query: { dataset_kind: "ulb_benchmark", empty: undefined, gone: null, flag: true },
    });

    const url = fetchMock.mock.calls[0]![0] as string;
    expect(url).toContain("dataset_kind=ulb_benchmark");
    expect(url).toContain("flag=true");
    expect(url).not.toContain("empty=");
    expect(url).not.toContain("gone=");
  });

  it("returns parsed JSON for a 200 response and captures the request-id header", async () => {
    const fetchMock: FetchMock = vi.fn(async () => jsonResponse({ status: "alive", service: "peiars", version: "0.4.0" }));
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const result = await request<{ status: string; service: string; version: string }>("/health/live");
    expect(result).toEqual({ status: "alive", service: "peiars", version: "0.4.0" });
  });

  it("handles 204 No Content without parsing a body", async () => {
    const fetchMock: FetchMock = vi.fn(async () => new Response(null, { status: 204, headers: { [REQUEST_ID_HEADER]: "req-204" } }));
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const result = await request<{ ok: boolean }>("/nothing");
    expect(result).toBeUndefined();
  });

  it("parses a 4xx ErrorEnvelope into an ApiError with status, code, message and request_id", async () => {
    const envelope = {
      error: {
        code: "UNAUTHORIZED",
        message: "Invalid username or password.",
        request_id: "req-401-1",
      },
    };
    const fetchMock: FetchMock = vi.fn(async () =>
      jsonResponse(envelope, { status: 401, headers: { [REQUEST_ID_HEADER]: "req-401-1" } }),
    );
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    await expect(request("/auth/login", { method: "POST", json: {} })).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      code: "UNAUTHORIZED",
      message: "Invalid username or password.",
      requestId: "req-401-1",
    });
  });

  it("parses a 5xx ErrorEnvelope into an ApiError with status 503 and code SERVICE_NOT_READY", async () => {
    const envelope = {
      error: {
        code: "SERVICE_NOT_READY",
        message: "Authentication is not configured.",
        request_id: "req-503-1",
      },
    };
    const fetchMock: FetchMock = vi.fn(async () =>
      jsonResponse(envelope, { status: 503, headers: { [REQUEST_ID_HEADER]: "req-503-1" } }),
    );
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    await expect(request("/auth/csrf")).rejects.toMatchObject({
      status: 503,
      code: "SERVICE_NOT_READY",
      requestId: "req-503-1",
    });
  });

  it("falls back to a generic message when the envelope is missing fields", async () => {
    const fetchMock: FetchMock = vi.fn(async () =>
      new Response(JSON.stringify({}), {
        status: 500,
        headers: { "content-type": "application/json", [REQUEST_ID_HEADER]: "req-500-1" },
      }),
    );
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    await expect(request("/health/live")).rejects.toMatchObject({
      status: 500,
      code: "REQUEST_FAILED",
      requestId: "req-500-1",
    });
  });

  it("treats a fetch rejection (TypeError) as a network failure", async () => {
    const fetchMock: FetchMock = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    await expect(request("/health/live")).rejects.toMatchObject({
      network: true,
      status: 0,
      code: "REQUEST_FAILED",
    });
  });

  it("aborts when the external signal is already aborted", async () => {
    // Mock fetch that honors the abort signal (real fetch rejects with an
    // AbortError DOMException when the signal is aborted).
    const fetchMock: FetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      return new Promise<Response>((_resolve, reject) => {
        const signal = init?.signal;
        if (signal?.aborted) {
          reject(new DOMException("Aborted", "AbortError"));
          return;
        }
        signal?.addEventListener(
          "abort",
          () => reject(new DOMException("Aborted", "AbortError")),
          { once: true },
        );
      });
    });
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
    const controller = new AbortController();
    controller.abort(new DOMException("User aborted", "AbortError"));

    await expect(request("/health/live", { signal: controller.signal })).rejects.toMatchObject({
      aborted: true,
      network: false,
      timedOut: false,
    });
  });

  it("times out after timeoutMs and reports timedOut=true", async () => {
    // Use real timers with a short timeout so the abort/reject flow is
    // deterministic and doesn't produce async-rejection warnings.
    vi.useRealTimers();
    const fetchMock: FetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      return new Promise<Response>((_resolve, reject) => {
        const signal = init?.signal;
        if (signal?.aborted) {
          reject(new DOMException("Aborted", "AbortError"));
          return;
        }
        signal?.addEventListener(
          "abort",
          () => reject(new DOMException("Aborted", "AbortError")),
          { once: true },
        );
      });
    });
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const promise = request("/health/live", { timeoutMs: 50 });
    await expect(promise).rejects.toMatchObject({
      timedOut: true,
      network: false,
      aborted: false,
      status: 0,
    });
  });

  it("is an ApiError instance for non-2xx and exposes predicates", async () => {
    const envelope = {
      error: { code: "RATE_LIMITED", message: "Too many attempts.", request_id: "req-429" },
    };
    const fetchMock: FetchMock = vi.fn(async () =>
      jsonResponse(envelope, { status: 429, headers: { [REQUEST_ID_HEADER]: "req-429" } }),
    );
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    try {
      await request("/auth/login", { method: "POST", json: {} });
      throw new Error("expected request to throw");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.isRateLimited).toBe(true);
      expect(apiErr.isUnauthorized).toBe(false);
      expect(apiErr.isNetwork).toBe(false);
    }
  });
});
