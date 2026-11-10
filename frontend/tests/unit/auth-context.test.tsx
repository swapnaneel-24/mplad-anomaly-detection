// Unit tests for the AuthProvider state machine.

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

import { CSRF_COOKIE_NAME, REQUEST_ID_HEADER } from "@/api/contracts";
import { ApiError } from "@/api/client";
import { AuthProvider, useAuth } from "@/auth/AuthContext";

type FetchMock = ReturnType<typeof vi.fn>;

interface RouteSpec {
  method?: string;
  urlContains: string;
  status: number;
  body: unknown;
  /** Optional side-effect to invoke (e.g. set document.cookie). */
  after?: () => void;
}

function makeFetch(routes: RouteSpec[]): FetchMock {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();
    const route = routes.find(
      (r) => url.includes(r.urlContains) && (r.method ? r.method.toUpperCase() === method : true),
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

function setCookieJar(cookies: string[]): void {
  Object.defineProperty(document, "cookie", {
    configurable: true,
    get: () => cookies.join("; "),
    set: (value: string) => {
      cookies.push(value.split(";")[0]!);
    },
  });
}

function wrapper({ children }: { children: ReactNode }): ReactNode {
  return <AuthProvider>{children}</AuthProvider>;
}

describe("AuthProvider state machine", () => {
  let originalFetch: typeof globalThis.fetch;
  let cookieJar: string[];
  let originalCookieDescriptor: PropertyDescriptor | undefined;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    cookieJar = [];
    originalCookieDescriptor = Object.getOwnPropertyDescriptor(document, "cookie");
    setCookieJar(cookieJar);
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    if (originalCookieDescriptor) {
      Object.defineProperty(document, "cookie", originalCookieDescriptor);
    }
  });

  it("initial state is loading, then authenticated on 200 from /auth/me", async () => {
    const fetchMock = makeFetch([
      {
        urlContains: "/auth/me",
        status: 200,
        body: {
          id: "u1",
          username: "alice",
          display_name: "Alice",
          role: "reviewer",
          permissions: ["cases:read"],
        },
      },
    ]);
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(result.current.status).toBe("loading");

    await waitFor(() => expect(result.current.status).toBe("authenticated"));
    expect(result.current.user?.username).toBe("alice");
    expect(result.current.user?.role).toBe("reviewer");
  });

  it("becomes anonymous on 401 from /auth/me", async () => {
    const fetchMock = makeFetch([
      {
        urlContains: "/auth/me",
        status: 401,
        body: { error: { code: "UNAUTHORIZED", message: "Authentication required.", request_id: "r1" } },
      },
    ]);
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe("anonymous"));
    expect(result.current.user).toBeNull();
  });

  it("becomes unknown (NOT anonymous) on network error from /auth/me", async () => {
    const fetchMock: FetchMock = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe("unknown"));
    expect(result.current.user).toBeNull();
    expect(result.current.lastError).toBeInstanceOf(ApiError);
  });

  it("login() bootstraps CSRF when the cookie is missing, then sends X-CSRF-Token", async () => {
    // First /auth/me → 401 (anonymous). Then login flow:
    //   GET /auth/csrf → 200 + sets cookie
    //   POST /auth/login → 200
    const fetchMock = makeFetch([
      {
        urlContains: "/auth/me",
        status: 401,
        body: { error: { code: "UNAUTHORIZED", message: "Authentication required.", request_id: "r1" } },
      },
      {
        method: "GET",
        urlContains: "/auth/csrf",
        status: 200,
        body: { csrf_token: "nonce1:hmac1" },
        after: () => {
          cookieJar.push(`${CSRF_COOKIE_NAME}=nonce1:hmac1`);
        },
      },
      {
        method: "POST",
        urlContains: "/auth/login",
        status: 200,
        body: {
          id: "u2",
          username: "bob",
          display_name: "Bob",
          role: "admin",
          permissions: ["*"],
        },
      },
    ]);
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe("anonymous"));

    await act(async () => {
      await result.current.login({ username: "bob", password: "supersecret" });
    });

    expect(result.current.status).toBe("authenticated");
    expect(result.current.user?.username).toBe("bob");

    // Verify the CSRF bootstrap GET happened and the login POST carried the header.
    const csrfCall = fetchMock.mock.calls.find(
      ([url, init]) => url.toString().includes("/auth/csrf") && (init?.method ?? "GET").toUpperCase() === "GET",
    );
    expect(csrfCall).toBeDefined();
    const loginCall = fetchMock.mock.calls.find(
      ([url, init]) => url.toString().includes("/auth/login") && init?.method === "POST",
    );
    expect(loginCall).toBeDefined();
    const loginInit = loginCall![1] as RequestInit;
    const headers = loginInit.headers as Record<string, string>;
    expect(headers["X-CSRF-Token"]).toBe("nonce1:hmac1");
  });

  it("login() throws when CSRF bootstrap succeeds but the cookie is still missing", async () => {
    const fetchMock = makeFetch([
      {
        urlContains: "/auth/me",
        status: 401,
        body: { error: { code: "UNAUTHORIZED", message: "Authentication required.", request_id: "r1" } },
      },
      {
        method: "GET",
        urlContains: "/auth/csrf",
        status: 200,
        body: { csrf_token: "nonce2:hmac2" },
        // Deliberately do NOT set the cookie → readCsrfCookie returns null.
      },
    ]);
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe("anonymous"));

    await expect(
      act(async () => {
        await result.current.login({ username: "carol", password: "supersecret" });
      }),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it("logout() clears state on 200 from /auth/logout", async () => {
    // Start authenticated, then logout.
    const fetchMock = makeFetch([
      {
        urlContains: "/auth/me",
        status: 200,
        body: { id: "u3", username: "dave", display_name: "Dave", role: "viewer", permissions: [] },
      },
      {
        method: "POST",
        urlContains: "/auth/logout",
        status: 200,
        body: { status: "logged_out" },
      },
    ]);
    cookieJar.push(`${CSRF_COOKIE_NAME}=nonce3:hmac3`);
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe("authenticated"));

    await act(async () => {
      await result.current.logout();
    });

    expect(result.current.status).toBe("anonymous");
    expect(result.current.user).toBeNull();
  });

  it("logout() on 401 mid-logout transitions to anonymous (server already revoked)", async () => {
    const fetchMock = makeFetch([
      {
        urlContains: "/auth/me",
        status: 200,
        body: { id: "u4", username: "eve", display_name: "Eve", role: "reviewer", permissions: [] },
      },
      {
        method: "POST",
        urlContains: "/auth/logout",
        status: 401,
        body: { error: { code: "UNAUTHORIZED", message: "Authentication required.", request_id: "r" } },
      },
    ]);
    cookieJar.push(`${CSRF_COOKIE_NAME}=nonce4:hmac4`);
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe("authenticated"));

    await act(async () => {
      await result.current.logout();
    });

    expect(result.current.status).toBe("anonymous");
  });

  it("logout() does NOT clear state on network error (remains authenticated)", async () => {
    // /auth/me → 200 (authenticated). The POST /auth/logout fetch rejects.
    let logoutAttempted = false;
    const fetchMock: FetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.includes("/auth/me") && method === "GET") {
        return new Response(
          JSON.stringify({ id: "u5", username: "frank", display_name: "Frank", role: "admin", permissions: [] }),
          { status: 200, headers: { "content-type": "application/json", [REQUEST_ID_HEADER]: "r" } },
        );
      }
      if (url.includes("/auth/logout") && method === "POST") {
        logoutAttempted = true;
        throw new TypeError("Failed to fetch");
      }
      throw new TypeError(`No mock for ${method} ${url}`);
    });
    cookieJar.push(`${CSRF_COOKIE_NAME}=nonce5:hmac5`);
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe("authenticated"));

    await act(async () => {
      await result.current.logout();
    });

    expect(logoutAttempted).toBe(true);
    expect(result.current.status).toBe("authenticated");
    expect(result.current.user?.username).toBe("frank");
    expect(result.current.lastError).toBeInstanceOf(ApiError);
  });

  it("isRole and hasPermission reflect the authenticated user", async () => {
    const fetchMock = makeFetch([
      {
        urlContains: "/auth/me",
        status: 200,
        body: { id: "u6", username: "grace", display_name: "Grace", role: "reviewer", permissions: ["cases:read", "cases:write"] },
      },
    ]);
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe("authenticated"));

    expect(result.current.isRole("viewer")).toBe(true); // reviewer >= viewer
    expect(result.current.isRole("reviewer")).toBe(true);
    expect(result.current.isRole("admin")).toBe(false); // reviewer < admin
    expect(result.current.hasPermission("cases:read")).toBe(true);
    expect(result.current.hasPermission("cases:delete")).toBe(false);
  });
});
