// Unit tests for the role-presentation helpers (useAuth().isRole, hasPermission).
//
// This is a unit test of the role-aware utility, not a full integration
// test. A small test component renders different affordances based on
// the predicate; we verify a viewer sees fewer affordances than an admin.

import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

import { REQUEST_ID_HEADER } from "@/api/contracts";
import { AuthProvider, useAuth } from "@/auth/AuthContext";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", [REQUEST_ID_HEADER]: "r" },
  });
}

interface TestUser {
  username: string;
  role: "viewer" | "reviewer" | "admin";
  permissions: string[];
}

function renderRoleTest(user: TestUser): void {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url.includes("/auth/me")) {
      return jsonResponse({
        id: `u-${user.username}`,
        username: user.username,
        display_name: user.username,
        role: user.role,
        permissions: user.permissions,
      });
    }
    throw new TypeError(`No mock for ${url}`);
  });
  globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

  function Probe(): ReactNode {
    const auth = useAuth();
    if (auth.status !== "authenticated") return null;
    return (
      <div>
        <span data-testid="role-label">{auth.user?.role}</span>
        {auth.isRole("admin") ? (
          <button type="button" data-testid="admin-only">
            Manage users
          </button>
        ) : null}
        {auth.hasPermission("cases:write") ? (
          <button type="button" data-testid="write-only">
            Create case
          </button>
        ) : null}
        {auth.hasPermission("cases:read") ? (
          <button type="button" data-testid="read-only">
            View cases
          </button>
        ) : null}
      </div>
    );
  }

  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
}

describe("role presentation (useAuth predicates)", () => {
  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("viewer sees only read affordances", async () => {
    renderRoleTest({
      username: "viewer1",
      role: "viewer",
      permissions: ["cases:read"],
    });
    expect(await screen.findByTestId("role-label")).toHaveTextContent("viewer");
    expect(screen.queryByTestId("admin-only")).toBeNull();
    expect(screen.queryByTestId("write-only")).toBeNull();
    expect(screen.getByTestId("read-only")).toBeInTheDocument();
  });

  it("reviewer sees read + write affordances, but not admin", async () => {
    renderRoleTest({
      username: "reviewer1",
      role: "reviewer",
      permissions: ["cases:read", "cases:write"],
    });
    expect(await screen.findByTestId("role-label")).toHaveTextContent("reviewer");
    expect(screen.queryByTestId("admin-only")).toBeNull();
    expect(screen.getByTestId("write-only")).toBeInTheDocument();
    expect(screen.getByTestId("read-only")).toBeInTheDocument();
  });

  it("admin sees all affordances (isRole(admin) is true)", async () => {
    renderRoleTest({
      username: "admin1",
      role: "admin",
      permissions: ["cases:read", "cases:write", "*"],
    });
    expect(await screen.findByTestId("role-label")).toHaveTextContent("admin");
    expect(screen.getByTestId("admin-only")).toBeInTheDocument();
    expect(screen.getByTestId("write-only")).toBeInTheDocument();
    expect(screen.getByTestId("read-only")).toBeInTheDocument();
  });
});
