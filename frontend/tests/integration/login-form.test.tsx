// Integration test: LoginPage form behaviour.

import { cleanup, screen, waitFor, within } from "@testing-library/react";
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

function publicRoutes(): FetchRoute[] {
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
      urlContains: "/auth/me",
      status: 401,
      body: { error: { code: "UNAUTHORIZED", message: "Authentication required.", request_id: "r" } },
    },
  ];
}

function loginRoutes(): FetchRoute[] {
  return [
    ...publicRoutes(),
    {
      method: "GET",
      urlContains: "/auth/csrf",
      status: 200,
      body: { csrf_token: "nonce:hmac" },
      after: () => {
        // Simulate the Set-Cookie header by writing to the cookie jar.
        document.cookie = `${CSRF_COOKIE_NAME}=nonce:hmac`;
      },
    },
    {
      method: "POST",
      urlContains: "/auth/login",
      status: 200,
      body: {
        id: "u1",
        username: "alice",
        display_name: "Alice",
        role: "reviewer",
        permissions: ["cases:read"],
      },
    },
  ];
}

function fillValid(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  return (async () => {
    const username = await screen.findByLabelText("Username");
    const password = screen.getByLabelText("Password");
    await user.type(username, "alice");
    await user.type(password, "supersecret");
  })();
}

describe("LoginPage form", () => {
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

  it("disables the submit button while fields are too short", async () => {
    globalThis.fetch = mockFetch(publicRoutes()) as unknown as typeof globalThis.fetch;
    renderApp({ initialEntries: ["/login"] });
    const submit = await screen.findByRole("button", { name: "Sign in" });
    expect(submit).toBeDisabled();
  });

  it("enables submit once username >= 3 and password >= 8", async () => {
    globalThis.fetch = mockFetch(publicRoutes()) as unknown as typeof globalThis.fetch;
    const user = userEvent.setup();
    renderApp({ initialEntries: ["/login"] });
    await fillValid(user);
    const submit = screen.getByRole("button", { name: "Sign in" });
    await waitFor(() => expect(submit).not.toBeDisabled());
  });

  it("bootstraps CSRF on submit and redirects to /overview on success", async () => {
    const fetchMock = mockFetch([
      ...loginRoutes(),
      // After login, /auth/me (session restore) returns the user.
      ...authenticatedRoutes().filter((r) => r.urlContains === "/auth/me"),
      ...authenticatedRoutes().filter((r) => r.urlContains === "/meta"),
    ]);
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const user = userEvent.setup();
    renderApp({ initialEntries: ["/login"] });
    await fillValid(user);
    const submit = screen.getByRole("button", { name: "Sign in" });
    await user.click(submit);

    // After login, the app should navigate to /overview and show the H1.
    const heading = await screen.findByRole("heading", { name: "Study Overview", level: 1 });
    expect(heading).toBeInTheDocument();

    // Verify CSRF bootstrap happened (GET /auth/csrf).
    const csrfCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        url.toString().includes("/auth/csrf") &&
        (init?.method ?? "GET").toUpperCase() === "GET",
    );
    expect(csrfCall).toBeDefined();

    // Verify login POST carried the X-CSRF-Token header.
    const loginCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        url.toString().includes("/auth/login") && init?.method === "POST",
    );
    expect(loginCall).toBeDefined();
    const loginInit = loginCall![1] as RequestInit;
    const headers = loginInit.headers as Record<string, string>;
    expect(headers["X-CSRF-Token"]).toBe("nonce:hmac");
  });

  it("shows a generic message on 401 (no field-level coloring)", async () => {
    const routes: FetchRoute[] = [
      ...publicRoutes(),
      {
        method: "GET",
        urlContains: "/auth/csrf",
        status: 200,
        body: { csrf_token: "nonce:hmac" },
        after: () => {
          document.cookie = `${CSRF_COOKIE_NAME}=nonce:hmac`;
        },
      },
      {
        method: "POST",
        urlContains: "/auth/login",
        status: 401,
        body: { error: { code: "UNAUTHORIZED", message: "Invalid username or password.", request_id: "r-401" } },
      },
    ];
    globalThis.fetch = mockFetch(routes) as unknown as typeof globalThis.fetch;

    const user = userEvent.setup();
    renderApp({ initialEntries: ["/login"] });
    await fillValid(user);
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Invalid username or password.")).toBeInTheDocument();
    // Should still be on the login page (no overview heading).
    expect(screen.queryByRole("heading", { name: "Study Overview", level: 1 })).toBeNull();
  });

  it("shows a throttled message and disables the form on 429", async () => {
    const routes: FetchRoute[] = [
      ...publicRoutes(),
      {
        method: "GET",
        urlContains: "/auth/csrf",
        status: 200,
        body: { csrf_token: "nonce:hmac" },
        after: () => {
          document.cookie = `${CSRF_COOKIE_NAME}=nonce:hmac`;
        },
      },
      {
        method: "POST",
        urlContains: "/auth/login",
        status: 429,
        body: { error: { code: "RATE_LIMITED", message: "Too many failed attempts.", request_id: "r-429" } },
      },
    ];
    globalThis.fetch = mockFetch(routes) as unknown as typeof globalThis.fetch;

    const user = userEvent.setup();
    renderApp({ initialEntries: ["/login"] });
    await fillValid(user);
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText(/Too many failed attempts/i)).toBeInTheDocument();
    // Submit button should now be disabled (throttled).
    const submit = screen.getByRole("button", { name: "Sign in" });
    expect(submit).toBeDisabled();
  });

  it("shows a network-error message on fetch rejection", async () => {
    const routes: FetchRoute[] = [
      ...publicRoutes(),
      {
        method: "GET",
        urlContains: "/auth/csrf",
        status: 200,
        body: { csrf_token: "nonce:hmac" },
        after: () => {
          document.cookie = `${CSRF_COOKIE_NAME}=nonce:hmac`;
        },
      },
    ];
    // Override: the login POST throws a TypeError (network failure).
    const fetchMock = mockFetch(routes);
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.includes("/auth/login") && method === "POST") {
        throw new TypeError("Failed to fetch");
      }
      // Fall back to the canned routes for everything else.
      const route = routes.find(
        (r) => url.includes(r.urlContains) && (r.method ? r.method.toUpperCase() === method : true),
      );
      if (!route) throw new TypeError(`No mock for ${method} ${url}`);
      route.after?.();
      return new Response(JSON.stringify(route.body), { status: route.status, headers: { "content-type": "application/json" } });
    });
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const user = userEvent.setup();
    renderApp({ initialEntries: ["/login"] });
    await fillValid(user);
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Cannot reach the API. Check your connection and retry.")).toBeInTheDocument();
  });

  it("renders the connectivity hint derived from useConnectivity", async () => {
    globalThis.fetch = mockFetch(publicRoutes()) as unknown as typeof globalThis.fetch;
    renderApp({ initialEntries: ["/login"] });
    // The connectivity hint should appear once health probes succeed.
    await waitFor(() => {
      expect(screen.getByText("API reachable · ready")).toBeInTheDocument();
    });
  });

  it("renders the identity block + editorial lede", async () => {
    globalThis.fetch = mockFetch(publicRoutes()) as unknown as typeof globalThis.fetch;
    renderApp({ initialEntries: ["/login"] });
    const mark = await screen.findByText("PEIARS", { selector: "h1" });
    expect(mark).toBeInTheDocument();
    // The lede mentions the evidence-bound stance.
    const lede = screen.getByText(/anomaly flag/i);
    expect(lede).toBeInTheDocument();
    // The form fields.
    expect(within(document.body).getByLabelText("Username")).toBeInTheDocument();
    expect(within(document.body).getByLabelText("Password")).toBeInTheDocument();
  });
});
