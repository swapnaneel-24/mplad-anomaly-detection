// Integration test: role presentation.
//
// Renders <App /> as viewer, reviewer, admin; asserts the user identity
// block shows the correct role label. In PR-05A there is no admin page,
// so we assert the role label is correct and that no role-gated
// placeholder is shown to non-admins.

import { cleanup, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ADMIN_USER,
  authenticatedRoutes,
  mockFetch,
  renderApp,
  REVIEWER_USER,
  setCookieJar,
  VIEWER_USER,
} from "../helpers/renderApp";

describe("role presentation (integration)", () => {
  let originalFetch: typeof globalThis.fetch;
  let originalCookie: PropertyDescriptor | undefined;
  let originalInnerWidth: number;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    originalCookie = Object.getOwnPropertyDescriptor(document, "cookie");
    originalInnerWidth = window.innerWidth;
    setCookieJar([]);
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      writable: true,
      value: 1440,
    });
    window.dispatchEvent(new Event("resize"));
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    if (originalCookie) {
      Object.defineProperty(document, "cookie", originalCookie);
    }
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      writable: true,
      value: originalInnerWidth,
    });
    window.dispatchEvent(new Event("resize"));
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows the viewer role label uppercase in the header", async () => {
    globalThis.fetch = mockFetch(authenticatedRoutes(VIEWER_USER)) as unknown as typeof globalThis.fetch;
    renderApp({ initialEntries: ["/overview"] });
    expect(await screen.findByRole("heading", { name: "Study Overview", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("VIEWER")).toBeInTheDocument();
    expect(screen.getByText("View One")).toBeInTheDocument();
  });

  it("shows the reviewer role label uppercase in the header", async () => {
    globalThis.fetch = mockFetch(authenticatedRoutes(REVIEWER_USER)) as unknown as typeof globalThis.fetch;
    renderApp({ initialEntries: ["/overview"] });
    expect(await screen.findByRole("heading", { name: "Study Overview", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("REVIEWER")).toBeInTheDocument();
    expect(screen.getByText("Review One")).toBeInTheDocument();
  });

  it("shows the admin role label uppercase in the header", async () => {
    globalThis.fetch = mockFetch(authenticatedRoutes(ADMIN_USER)) as unknown as typeof globalThis.fetch;
    renderApp({ initialEntries: ["/overview"] });
    expect(await screen.findByRole("heading", { name: "Study Overview", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("ADMIN")).toBeInTheDocument();
    expect(screen.getByText("Admin One")).toBeInTheDocument();
  });

  it("does not render a manage-users affordance in PR-05A (no admin page exists)", async () => {
    globalThis.fetch = mockFetch(authenticatedRoutes(ADMIN_USER)) as unknown as typeof globalThis.fetch;
    renderApp({ initialEntries: ["/overview"] });
    expect(await screen.findByRole("heading", { name: "Study Overview", level: 1 })).toBeInTheDocument();
    // No "Manage users" link/button anywhere in PR-05A.
    expect(screen.queryByRole("link", { name: /manage users/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /manage users/i })).toBeNull();
  });
});
