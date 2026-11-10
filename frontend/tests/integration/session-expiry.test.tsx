// Integration test: session expiry.
//
// Verifies the redirect behaviour when the session is already expired
// at mount time. The mid-session expiry flow (authenticated → 401 on
// refresh → anonymous) is covered at the unit level in
// `auth-context.test.tsx` (the `refresh()` path), which is the
// authoritative place to test the AuthProvider state machine.

import { cleanup, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  authenticatedRoutes,
  mockFetch,
  renderApp,
  setCookieJar,
  type FetchRoute,
} from "../helpers/renderApp";

describe("session expiry (integration)", () => {
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

  it("redirects to /login when the session is expired on mount (401 from /auth/me)", async () => {
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
    // Should land on the login page.
    expect(await screen.findByText("PEIARS", { selector: "h1" })).toBeInTheDocument();
    // And NOT show the workspace switcher.
    expect(screen.queryByRole("tablist", { name: "Workspaces" })).toBeNull();
    // And NOT show the connectivity-uncertainty panel.
    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: "Cannot reach the API" })).toBeNull();
    });
  });
});
