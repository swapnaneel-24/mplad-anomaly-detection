// Integration test: desktop minimum-width handling.
//
// PEIARS is desktop-only. At window.innerWidth >= 1280 the workspace
// composition renders normally. Below 1280, the DesktopGate replaces the
// composition area with a width-restriction message.
//
// This test replaces the previous mobile-drawer test. There is no
// hamburger, no drawer, no mobile navigation.

import { cleanup, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  authenticatedRoutes,
  mockFetch,
  renderApp,
  setCookieJar,
} from "../helpers/renderApp";

function setWindowWidth(width: number): void {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    writable: true,
    value: width,
  });
  window.dispatchEvent(new Event("resize"));
}

describe("desktop minimum-width handling", () => {
  let originalFetch: typeof globalThis.fetch;
  let originalCookie: PropertyDescriptor | undefined;
  let originalInnerWidth: number;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    originalCookie = Object.getOwnPropertyDescriptor(document, "cookie");
    originalInnerWidth = window.innerWidth;
    setCookieJar([]);
    globalThis.fetch = mockFetch(authenticatedRoutes()) as unknown as typeof globalThis.fetch;
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

  it("renders the workspace composition at 1440px (no gate)", async () => {
    setWindowWidth(1440);
    renderApp({ initialEntries: ["/overview"] });
    await screen.findByRole("heading", { name: "Study Overview", level: 1 });
    // The Overview study title (rendered inside the composition) is visible.
    expect(await screen.findByText(/MPLAD Fund-Utilisation/i)).toBeInTheDocument();
    // The gate message is NOT shown.
    expect(screen.queryByText(/Desktop window required/i)).toBeNull();
  });

  it("renders the workspace composition at 1280px (minimum supported)", async () => {
    setWindowWidth(1280);
    renderApp({ initialEntries: ["/overview"] });
    await screen.findByRole("heading", { name: "Study Overview", level: 1 });
    expect(await screen.findByText(/MPLAD Fund-Utilisation/i)).toBeInTheDocument();
    expect(screen.queryByText(/Desktop window required/i)).toBeNull();
  });

  it("shows the DesktopGate below 1280px and hides the workspace composition", async () => {
    setWindowWidth(1024);
    renderApp({ initialEntries: ["/overview"] });
    // Wait for auth restore + the gate to appear.
    await waitFor(() => {
      expect(screen.getByText(/Desktop window required/i)).toBeInTheDocument();
    });
    // The workspace study title is NOT rendered (composition is replaced).
    expect(screen.queryByText(/MPLAD Fund-Utilisation/i)).toBeNull();
    // The gate mentions the minimum width.
    expect(screen.getByText(/1280 CSS pixels/i)).toBeInTheDocument();
  });

  it("does not render a hamburger button or mobile drawer at any width", async () => {
    setWindowWidth(1024);
    renderApp({ initialEntries: ["/overview"] });
    await waitFor(() => {
      expect(screen.getByText(/Desktop window required/i)).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /open navigation drawer/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /close navigation drawer/i })).toBeNull();
    expect(screen.queryByLabelText("Workspace navigation")).toBeNull();
  });

  it("the identity bar and switcher remain visible below 1280px (user can still sign out)", async () => {
    setWindowWidth(1024);
    renderApp({ initialEntries: ["/overview"] });
    await waitFor(() => {
      expect(screen.getByText(/Desktop window required/i)).toBeInTheDocument();
    });
    // Identity bar: PEIARS mark visible.
    expect(screen.getByText("PEIARS")).toBeInTheDocument();
    // Switcher: tabs visible.
    expect(screen.getByRole("tablist", { name: "Workspaces" })).toBeInTheDocument();
    // Sign out button visible.
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });
});
