// Shared test helpers for integration tests.
//
// - `mockFetch` builds a `vi.fn()` that dispatches to canned routes based
//   on URL + method. Each route can carry an `after` side-effect (e.g.
//   set the CSRF cookie) so the auth flow works end-to-end in jsdom.
// - `setCookieJar` replaces `document.cookie` with a mutable array-backed
//   jar so tests can read/write cookies without a real browser.
// - `renderApp` mounts the AppRoutes under a MemoryRouter with the
//   AuthProvider + ConnectivityProvider, matching main.tsx.

import type { ReactNode } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { REQUEST_ID_HEADER } from "@/api/contracts";
import { AppRoutes } from "@/routes";
import { AuthProvider } from "@/auth/AuthContext";
import { ConnectivityProvider } from "@/api/ConnectivityContext";

export interface FetchRoute {
  method?: string;
  urlContains: string;
  status: number;
  body: unknown;
  /** Optional side-effect (e.g. set the CSRF cookie). */
  after?: () => void;
}

export type FetchMock = ReturnType<typeof vi.fn>;

export function mockFetch(routes: FetchRoute[]): FetchMock {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();
    const route = routes.find(
      (r) =>
        url.includes(r.urlContains) &&
        (r.method ? r.method.toUpperCase() === method : true),
    );
    if (!route) {
      throw new TypeError(`No mock route for ${method} ${url}`);
    }
    route.after?.();
    return new Response(JSON.stringify(route.body), {
      status: route.status,
      headers: {
        "content-type": "application/json",
        [REQUEST_ID_HEADER]: `req-${Math.random().toString(36).slice(2, 8)}`,
      },
    });
  });
}

export function setCookieJar(cookies: string[]): void {
  Object.defineProperty(document, "cookie", {
    configurable: true,
    get: () => cookies.join("; "),
    set: (value: string) => {
      cookies.push(value.split(";")[0]!);
    },
  });
}

export interface RenderAppOptions {
  initialEntries?: string[];
}

export function renderApp(opts: RenderAppOptions = {}): ReturnType<typeof render> {
  return render(
    <AuthProvider>
      <ConnectivityProvider>
        <MemoryRouter initialEntries={opts.initialEntries ?? ["/overview"]}>
          <AppRoutes />
        </MemoryRouter>
      </ConnectivityProvider>
    </AuthProvider>,
  );
}

/** Render arbitrary children inside the AuthProvider + ConnectivityProvider. */
export function renderWithProviders(
  children: ReactNode,
  opts: RenderAppOptions = {},
): ReturnType<typeof render> {
  return render(
    <AuthProvider>
      <ConnectivityProvider>
        <MemoryRouter initialEntries={opts.initialEntries ?? ["/overview"]}>
          {children}
        </MemoryRouter>
      </ConnectivityProvider>
    </AuthProvider>,
  );
}

/** Standard authenticated user used across integration tests. */
export const REVIEWER_USER = {
  id: "u-reviewer-1",
  username: "reviewer1",
  display_name: "Review One",
  role: "reviewer" as const,
  permissions: ["cases:read", "cases:write"],
};

export const VIEWER_USER = {
  id: "u-viewer-1",
  username: "viewer1",
  display_name: "View One",
  role: "viewer" as const,
  permissions: ["cases:read"],
};

export const ADMIN_USER = {
  id: "u-admin-1",
  username: "admin1",
  display_name: "Admin One",
  role: "admin" as const,
  permissions: ["cases:read", "cases:write", "*"],
};

export type TestUser =
  | typeof REVIEWER_USER
  | typeof VIEWER_USER
  | typeof ADMIN_USER;

/** Common route set: health + meta + auth/me (200 authenticated). */
export function authenticatedRoutes(user: TestUser = REVIEWER_USER): FetchRoute[] {
  return [
    {
      urlContains: "/health/live",
      status: 200,
      body: { status: "alive", service: "peiars", version: "0.4.0" },
    },
    {
      urlContains: "/health/ready",
      status: 200,
      body: { status: "ready", checks: [{ name: "database", status: "ready" }] },
    },
    {
      urlContains: "/meta",
      status: 200,
      body: {
        application: "PEIARS",
        api_version: "v1",
        app_version: "0.4.0",
        git_commit_sha: null,
        environment: "development",
        features: {
          source_registry: "implemented",
          health_endpoints: "implemented",
          openapi_contract: "implemented",
          auth_login: "implemented",
          auth_logout: "implemented",
          auth_session_restore: "implemented",
          auth_throttle: "implemented",
          auth_roles: "implemented",
          research_evidence: "planned",
          case_management: "planned",
        },
        subsystems: {
          source_registry: "empty",
          research_evidence: "not_integrated",
          case_management: "not_integrated",
        },
      },
    },
    {
      urlContains: "/sources",
      status: 200,
      body: { sources: [], count: 0 },
    },
    {
      urlContains: "/auth/me",
      status: 200,
      body: user,
    },
  ];
}
