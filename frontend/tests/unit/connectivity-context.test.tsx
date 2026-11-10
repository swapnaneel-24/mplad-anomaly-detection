// Unit tests for the ConnectivityProvider state machine.

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

import { REQUEST_ID_HEADER } from "@/api/contracts";
import { ApiError } from "@/api/client";
import { ConnectivityProvider, useConnectivity } from "@/api/ConnectivityContext";

type FetchMock = ReturnType<typeof vi.fn>;

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", [REQUEST_ID_HEADER]: "r" },
  });
}

function wrapper({ children }: { children: ReactNode }): ReactNode {
  return <ConnectivityProvider>{children}</ConnectivityProvider>;
}

function setWindowListenersStub(): () => void {
  // The ConnectivityProvider adds a `focus` listener; jsdom dispatches fine.
  // No-op stub retained for symmetry with other test files.
  return () => undefined;
}

describe("ConnectivityProvider", () => {
  let originalFetch: typeof globalThis.fetch;
  let restore: () => void;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    restore = setWindowListenersStub();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    restore();
  });

  it("reports `ready` when /health/live returns 200 and /health/ready returns 200 with all checks ready", async () => {
    const fetchMock: FetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/health/live")) {
        return jsonResponse({ status: "alive", service: "peiars", version: "0.4.0" });
      }
      if (url.includes("/health/ready")) {
        return jsonResponse({ status: "ready", checks: [{ name: "database", status: "ready" }] });
      }
      throw new TypeError(`No mock for ${url}`);
    });
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const { result } = renderHook(() => useConnectivity(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.version).toBe("0.4.0");
    expect(result.current.checks).toEqual([{ name: "database", status: "ready" }]);
  });

  it("reports `not_ready` when /health/ready returns 503", async () => {
    const fetchMock: FetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/health/live")) {
        return jsonResponse({ status: "alive", service: "peiars", version: "0.4.0" });
      }
      if (url.includes("/health/ready")) {
        return jsonResponse(
          {
            error: {
              code: "SERVICE_NOT_READY",
              message: "Readiness check failed.",
              request_id: "r",
              details: { failed_checks: [{ name: "database", status: "unavailable" }] },
            },
          },
          503,
        );
      }
      throw new TypeError(`No mock for ${url}`);
    });
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const { result } = renderHook(() => useConnectivity(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe("not_ready"));
    expect(result.current.checks).toEqual([{ name: "database", status: "unavailable" }]);
  });

  it("reports `unreachable` when /health/live fails with a network error", async () => {
    const fetchMock: FetchMock = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const { result } = renderHook(() => useConnectivity(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe("unreachable"));
    expect(result.current.version).toBeNull();
    expect(result.current.lastError).toBeInstanceOf(ApiError);
  });

  it("starts as `unknown` while checking", () => {
    // A fetch that never resolves; the initial state must be `unknown`.
    const fetchMock: FetchMock = vi.fn(() => new Promise<Response>(() => undefined));
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const { result } = renderHook(() => useConnectivity(), { wrapper });
    expect(result.current.status).toBe("unknown");
    expect(result.current.checking).toBe(true);
  });

  it("refresh() re-probes and updates state", async () => {
    let liveOk = false;
    const fetchMock: FetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/health/live")) {
        if (!liveOk) throw new TypeError("Failed to fetch");
        return jsonResponse({ status: "alive", service: "peiars", version: "0.4.0" });
      }
      if (url.includes("/health/ready")) {
        return jsonResponse({ status: "ready", checks: [] });
      }
      throw new TypeError(`No mock for ${url}`);
    });
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const { result } = renderHook(() => useConnectivity(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe("unreachable"));

    liveOk = true;
    await act(async () => {
      result.current.refresh();
    });
    await waitFor(() => expect(result.current.status).toBe("ready"));
  });
});
