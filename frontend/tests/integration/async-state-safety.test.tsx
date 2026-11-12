// PR-05B Final Async-State Safety Patch — regression tests.
//
// Fix 1: Stale async response guard — verify that a delayed history GET
//   for Case A does not overwrite Case B after the user switches.
// Fix 2: Initial-load rejection — verify that a failed initial refreshIndex
//   does not produce an unhandled promise rejection and shows an error.

import { cleanup, screen, waitFor, act, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  REVIEWER_USER,
  type FetchRoute,
  authenticatedRoutes,
  renderApp,
  setCookieJar,
  SYNTHETIC_RECORD_DETAIL,
} from "../helpers/renderApp";
import { CSRF_COOKIE_NAME } from "@/api/contracts";

function setWindowWidth(width: number): void {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    writable: true,
    value: width,
  });
  window.dispatchEvent(new Event("resize"));
}

const CASE_A_ID = "00000000-0000-0000-0000-000000000001";
const CASE_B_ID = "00000000-0000-0000-0000-000000000002";

function caseDetail(id: string, title: string, version: number = 1): Record<string, unknown> {
  return {
    id,
    dataset_id: "synthetic-demonstration",
    snapshot_id: "synthetic-v1",
    record_ref: "synth-001",
    status: "not_reviewed",
    title,
    summary: "Test summary",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    version,
    created_by: "user-uuid-1",
  };
}

function caseHistory(caseId: string, _title?: string): Record<string, unknown> {
  return {
    case_id: caseId,
    total: 1,
    items: [
      {
        id: `event-${caseId}`,
        case_id: caseId,
        event_type: "created",
        event_at: "2026-01-01T00:00:00Z",
        actor_ref: "user-uuid-1",
        previous_status: null,
        new_status: "not_reviewed",
        reason: null,
        event_payload: null,
        case_version: 1,
        event_seq: 1,
      },
    ],
  };
}

function routesWithTwoCases(): FetchRoute[] {
  return [
    {
      urlContains: "/synthetic/records/synth-001",
      method: "GET",
      status: 200,
      body: SYNTHETIC_RECORD_DETAIL,
    },
    {
      urlContains: `/${CASE_A_ID}/history`,
      method: "GET",
      status: 200,
      body: caseHistory(CASE_A_ID, "Case A history"),
    },
    {
      urlContains: `/${CASE_A_ID}`,
      method: "GET",
      status: 200,
      body: caseDetail(CASE_A_ID, "Case A"),
    },
    {
      urlContains: `/${CASE_B_ID}/history`,
      method: "GET",
      status: 200,
      body: caseHistory(CASE_B_ID, "Case B history"),
    },
    {
      urlContains: `/${CASE_B_ID}`,
      method: "GET",
      status: 200,
      body: caseDetail(CASE_B_ID, "Case B"),
    },
    // The case list must return both cases. The mock in the test overrides
    // this to return both cases.
    ...authenticatedRoutes(REVIEWER_USER),
  ];
}

describe("async-state safety patch", () => {
  let originalFetch: typeof globalThis.fetch;
  let originalCookie: PropertyDescriptor | undefined;
  let originalInnerWidth: number;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    originalCookie = Object.getOwnPropertyDescriptor(document, "cookie");
    originalInnerWidth = window.innerWidth;
    setCookieJar([]);
    Object.defineProperty(document, "cookie", {
      configurable: true,
      get: () => `${CSRF_COOKIE_NAME}=test-csrf-token`,
      set: () => {},
    });
    setWindowWidth(1440);
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    if (originalCookie) {
      Object.defineProperty(document, "cookie", originalCookie);
    }
    setWindowWidth(originalInnerWidth);
    cleanup();
    vi.restoreAllMocks();
  });

  // === Fix 1: Stale async response guard ===

  it("STALE GUARD: delayed history GET for Case A does not overwrite Case B", async () => {
    // Build a mock where Case A's detail+history GETs are deferred,
    // and Case B's GETs resolve immediately.
    let resolveCaseA!: (v: Response) => void;
    const caseAPromise = new Promise<Response>((r) => { resolveCaseA = r; });

    const baseRoutes = routesWithTwoCases();
    const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = (init?.method ?? "GET").toUpperCase();

      // Any GET involving CASE_A_ID → deferred (both detail and history).
      if (url.includes(CASE_A_ID) && method === "GET") {
        return caseAPromise;
      }
      // Case list → return both cases.
      if (url.includes("/cases") && !url.includes(CASE_A_ID) && !url.includes(CASE_B_ID) && !url.includes("/history") && method === "GET") {
        return new Response(JSON.stringify({
          items: [caseDetail(CASE_A_ID, "Case A"), caseDetail(CASE_B_ID, "Case B")],
          total: 2, limit: 50, offset: 0,
        }), { status: 200, headers: { "content-type": "application/json", "X-Request-ID": "r" } });
      }
      // Fallback: handle Case B and synthetic records.
      const route = baseRoutes.find(
        (r) => url.includes(r.urlContains) && (r.method ? r.method.toUpperCase() === method : true),
      );
      if (!route) throw new TypeError(`No mock for ${method} ${url}`);
      return new Response(JSON.stringify(route.body), {
        status: route.status, headers: { "content-type": "application/json", "X-Request-ID": "r" },
      });
    });
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/investigations"] });
    await screen.findByText("Case A");
    await screen.findByText("Case B");

    const user = userEvent.setup();
    // Select Case A — its GETs are pending (deferred).
    await user.click(screen.getByRole("button", { name: /Case A/i }));
    // Switch to Case B immediately (before Case A's GETs resolve).
    await user.click(screen.getByRole("button", { name: /Case B/i }));
    // Wait for Case B's detail + history to load.
    await waitFor(() => {
      expect(screen.getByText("Case metadata")).toBeInTheDocument();
    }, { timeout: 5_000 });

    // Now resolve Case A's delayed GET with stale data.
    act(() => resolveCaseA(new Response(JSON.stringify(caseDetail(CASE_A_ID, "STALE DETAIL")), {
      status: 200, headers: { "content-type": "application/json", "X-Request-ID": "r" },
    })));

    // Wait a tick for the stale response to be processed.
    await new Promise((r) => setTimeout(r, 50));

    // Case B's detail must still be visible — "STALE DETAIL" must not appear.
    expect(screen.queryByText("STALE DETAIL")).toBeNull();
    // The evidence panel should still show Case B's title.
    const evidencePanel = screen.getByLabelText("Evidence examination");
    expect(within(evidencePanel).getByText("Case B")).toBeInTheDocument();
  });

  it("STALE GUARD: delayed case-detail GET for Case A does not overwrite Case B", async () => {
    let resolveCaseADetail!: (v: Response) => void;
    const caseADetailPromise = new Promise<Response>((r) => { resolveCaseADetail = r; });

    const baseRoutes = routesWithTwoCases();
    const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = (init?.method ?? "GET").toUpperCase();

      // Case A detail (not history) → deferred.
      if (url.includes(`/${CASE_A_ID}`) && !url.includes("/history") && method === "GET") {
        return caseADetailPromise;
      }
      // Case list → both cases.
      if (url.includes("/cases") && !url.includes(CASE_A_ID) && !url.includes(CASE_B_ID) && !url.includes("/history") && method === "GET") {
        return new Response(JSON.stringify({
          items: [caseDetail(CASE_A_ID, "Case A"), caseDetail(CASE_B_ID, "Case B")],
          total: 2, limit: 50, offset: 0,
        }), { status: 200, headers: { "content-type": "application/json", "X-Request-ID": "r" } });
      }
      const route = baseRoutes.find(
        (r) => url.includes(r.urlContains) && (r.method ? r.method.toUpperCase() === method : true),
      );
      if (!route) throw new TypeError(`No mock for ${method} ${url}`);
      return new Response(JSON.stringify(route.body), {
        status: route.status, headers: { "content-type": "application/json", "X-Request-ID": "r" },
      });
    });
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/investigations"] });
    await screen.findByText("Case A");
    const user = userEvent.setup();
    // Select Case A — its detail GET is pending.
    await user.click(screen.getByRole("button", { name: /Case A/i }));
    // Switch to Case B immediately.
    await user.click(screen.getByRole("button", { name: /Case B/i }));
    // Wait for Case B's detail to load.
    await waitFor(() => {
      expect(screen.getByText("Case metadata")).toBeInTheDocument();
    });

    // Now resolve Case A's delayed detail GET with a stale title.
    act(() => resolveCaseADetail(new Response(JSON.stringify(caseDetail(CASE_A_ID, "STALE DETAIL")), {
      status: 200, headers: { "content-type": "application/json", "X-Request-ID": "r" },
    })));

    await new Promise((r) => setTimeout(r, 50));

    // Case B's detail must still be visible — "STALE DETAIL" must not appear.
    expect(screen.queryByText("STALE DETAIL")).toBeNull();
    // The evidence panel should still show Case B's title (in the case heading).
    const evidencePanel = screen.getByLabelText("Evidence examination");
    expect(within(evidencePanel).getByText("Case B")).toBeInTheDocument();
  });

  // === Fix 2: Initial-load rejection handling ===

  it("INITIAL LOAD: failed initial refreshIndex shows error, no unhandled rejection", async () => {
    // Track unhandled rejections.
    const unhandledRejections: unknown[] = [];
    const onUnhandled = (e: PromiseRejectionEvent) => {
      unhandledRejections.push(e.reason);
    };
    window.addEventListener("unhandledrejection", onUnhandled);

    const baseRoutes = routesWithTwoCases();
    const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = (init?.method ?? "GET").toUpperCase();
      // Fail the FIRST case-list GET (initial load).
      if (url.includes("/cases") && !url.includes(CASE_A_ID) && !url.includes(CASE_B_ID) && !url.includes("/history") && method === "GET") {
        return new Response(
          JSON.stringify({ error: { code: "SERVICE_NOT_READY", message: "DB unavailable", request_id: "r" } }),
          { status: 503, headers: { "content-type": "application/json", "X-Request-ID": "r" } },
        );
      }
      const route = baseRoutes.find(
        (r) => url.includes(r.urlContains) && (r.method ? r.method.toUpperCase() === method : true),
      );
      if (!route) throw new TypeError(`No mock for ${method} ${url}`);
      return new Response(JSON.stringify(route.body), {
        status: route.status, headers: { "content-type": "application/json", "X-Request-ID": "r" },
      });
    });
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/investigations"] });

    // The index error panel should appear (not a blank screen).
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    }, { timeout: 5_000 });

    // Wait a moment to let any potential unhandled rejections surface.
    await new Promise((r) => setTimeout(r, 100));
    window.removeEventListener("unhandledrejection", onUnhandled);

    // No unhandled promise rejections.
    expect(unhandledRejections.length).toBe(0);
  });
});
