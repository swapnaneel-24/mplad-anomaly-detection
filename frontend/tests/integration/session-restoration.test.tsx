// Integration test: session restoration on app load.

import { cleanup, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  authenticatedRoutes,
  mockFetch,
  renderApp,
  setCookieJar,
  type FetchRoute,
} from "../helpers/renderApp";

describe("session restoration", () => {
  let originalFetch: typeof globalThis.fetch;
  let originalCookie: PropertyDescriptor | undefined;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    originalCookie = Object.getOwnPropertyDescriptor(document, "cookie");
    setCookieJar([]);
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    if (originalCookie) {
      Object.defineProperty(document, "cookie", originalCookie);
    }
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows Loading… while /auth/me is pending, then the switcher + context strip on 200", async () => {
    // A fetch that never resolves for /auth/me — keeps the app in `loading`.
    const neverResolve = new Promise<Response>(() => undefined);
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.includes("/auth/me") && method === "GET") {
        return neverResolve;
      }
      // Other routes (health, meta) — return canned responses.
      const route = authenticatedRoutes().find(
        (r) => url.includes(r.urlContains) && (r.method ? r.method.toUpperCase() === method : true),
      );
      if (!route) throw new TypeError(`No mock for ${method} ${url}`);
      return new Response(JSON.stringify(route.body), {
        status: route.status,
        headers: { "content-type": "application/json", "X-Request-ID": "r" },
      });
    });
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/overview"] });
    expect(await screen.findByText("Loading…")).toBeInTheDocument();
    // The workspace switcher should NOT be visible while loading.
    expect(screen.queryByRole("tablist", { name: "Workspaces" })).toBeNull();
  });

  it("shows the switcher + context strip once /auth/me returns 200", async () => {
    globalThis.fetch = mockFetch(authenticatedRoutes()) as unknown as typeof globalThis.fetch;
    renderApp({ initialEntries: ["/overview"] });
    // The horizontal workspace switcher appears after restore resolves.
    expect(await screen.findByRole("tablist", { name: "Workspaces" })).toBeInTheDocument();
    // The context-strip H1 (page title).
    expect(await screen.findByRole("heading", { name: "Study Overview", level: 1 })).toBeInTheDocument();
  });

  it("redirects to /login on 401 from /auth/me", async () => {
    const routes: FetchRoute[] = [
      ...authenticatedRoutes().filter((r) => r.urlContains !== "/auth/me"),
      {
        urlContains: "/auth/me",
        status: 401,
        body: { error: { code: "UNAUTHORIZED", message: "Authentication required.", request_id: "r" } },
      },
    ];
    globalThis.fetch = mockFetch(routes) as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/overview"] });
    // Should land on /login (the LoginPage identity mark).
    expect(await screen.findByText("PEIARS", { selector: "h1" })).toBeInTheDocument();
    // And NOT show the workspace switcher.
    expect(screen.queryByRole("tablist", { name: "Workspaces" })).toBeNull();
  });

  it("shows the connectivity-uncertainty panel (NOT a redirect) on network error from /auth/me", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.includes("/auth/me") && method === "GET") {
        throw new TypeError("Failed to fetch");
      }
      const route = authenticatedRoutes().find(
        (r) => url.includes(r.urlContains) && (r.method ? r.method.toUpperCase() === method : true),
      );
      if (!route) throw new TypeError(`No mock for ${method} ${url}`);
      return new Response(JSON.stringify(route.body), {
        status: route.status,
        headers: { "content-type": "application/json", "X-Request-ID": "r" },
      });
    });
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/overview"] });
    // Should show the connectivity-uncertainty panel with the heading.
    expect(await screen.findByRole("heading", { name: "Cannot reach the API" })).toBeInTheDocument();
    // And NOT redirect to /login (no login identity mark).
    expect(screen.queryByLabelText("Username")).toBeNull();
    // And NOT show the workspace switcher.
    expect(screen.queryByRole("tablist", { name: "Workspaces" })).toBeNull();

    // The hint paragraph should mention the session was not cleared.
    await waitFor(() => {
      expect(screen.getByText(/session has not been cleared/i)).toBeInTheDocument();
    });
  });
});
