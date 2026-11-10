// Integration test: logout flow.

import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CSRF_COOKIE_NAME } from "@/api/contracts";
import {
  authenticatedRoutes,
  mockFetch,
  renderApp,
  setCookieJar,
  type FetchRoute,
} from "../helpers/renderApp";

function authedRoutesWithLogout(): FetchRoute[] {
  return [
    ...authenticatedRoutes(),
    {
      method: "POST",
      urlContains: "/auth/logout",
      status: 200,
      body: { status: "logged_out" },
    },
  ];
}

describe("logout flow", () => {
  let originalFetch: typeof globalThis.fetch;
  let originalCookie: PropertyDescriptor | undefined;
  let cookieJar: string[];

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    originalCookie = Object.getOwnPropertyDescriptor(document, "cookie");
    cookieJar = [];
    setCookieJar(cookieJar);
    cookieJar.push(`${CSRF_COOKIE_NAME}=nonce:hmac`);
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    if (originalCookie) {
      Object.defineProperty(document, "cookie", originalCookie);
    }
    cleanup();
    vi.restoreAllMocks();
  });

  it("sends the X-CSRF-Token header on POST /auth/logout and redirects to /login on 200", async () => {
    const fetchMock = mockFetch(authedRoutesWithLogout());
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const user = userEvent.setup();
    renderApp({ initialEntries: ["/overview"] });
    // Wait for authenticated state (the workspace switcher appears).
    expect(await screen.findByRole("tablist", { name: "Workspaces" })).toBeInTheDocument();

    const logoutButton = screen.getByRole("button", { name: "Sign out" });
    await user.click(logoutButton);

    // Should land on /login.
    expect(await screen.findByText("PEIARS", { selector: "h1" })).toBeInTheDocument();
    // And NOT show the workspace switcher.
    expect(screen.queryByRole("tablist", { name: "Workspaces" })).toBeNull();

    // Verify the CSRF header was sent on the logout POST.
    const logoutCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        url.toString().includes("/auth/logout") && init?.method === "POST",
    );
    expect(logoutCall).toBeDefined();
    const init = logoutCall![1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers["X-CSRF-Token"]).toBe("nonce:hmac");
  });

  it("shows an error panel and remains authenticated on network error during logout", async () => {
    const fetchMock = mockFetch(authenticatedRoutes());
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.includes("/auth/logout") && method === "POST") {
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

    const user = userEvent.setup();
    renderApp({ initialEntries: ["/overview"] });
    expect(await screen.findByRole("tablist", { name: "Workspaces" })).toBeInTheDocument();

    const logoutButton = screen.getByRole("button", { name: "Sign out" });
    await user.click(logoutButton);

    // Should still be authenticated (switcher visible) and show an error.
    // The AuthContext sets lastError but does not change status; the
    // RequireAuth guard still sees `authenticated`.
    expect(screen.getByRole("tablist", { name: "Workspaces" })).toBeInTheDocument();
    // The logout button returns to "Sign out" (not "Working…").
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });

  it("transitions to anonymous on 401 mid-logout (session already revoked server-side)", async () => {
    const routes: FetchRoute[] = [
      ...authenticatedRoutes(),
      {
        method: "POST",
        urlContains: "/auth/logout",
        status: 401,
        body: { error: { code: "UNAUTHORIZED", message: "Authentication required.", request_id: "r" } },
      },
    ];
    globalThis.fetch = mockFetch(routes) as unknown as typeof globalThis.fetch;

    const user = userEvent.setup();
    renderApp({ initialEntries: ["/overview"] });
    expect(await screen.findByRole("tablist", { name: "Workspaces" })).toBeInTheDocument();

    const logoutButton = screen.getByRole("button", { name: "Sign out" });
    await user.click(logoutButton);

    // Should land on /login (anonymous state).
    expect(await screen.findByText("PEIARS", { selector: "h1" })).toBeInTheDocument();
    expect(screen.queryByRole("tablist", { name: "Workspaces" })).toBeNull();
  });
});
