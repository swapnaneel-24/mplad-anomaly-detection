// Integration test: desktop minimum-width handling (PR-06A contract).
//
// The minimum supported viewport width is exactly 1024 CSS pixels.
// At >= 1024 the workspace composition renders normally. Below 1024,
// the DesktopGate replaces the composition area.
//
// Tested widths: 1023 (gate), 1024 (minimum supported), 1280, 1366,
// 1440, 1920 (all supported). There is no hamburger, no drawer, no
// mobile navigation.

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

describe("desktop minimum-width handling (PR-06A: 1024px contract)", () => {
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

  // --- Supported widths (no gate) ---

  it("renders the workspace composition at 1920px", async () => {
    setWindowWidth(1920);
    renderApp({ initialEntries: ["/overview"] });
    await screen.findByRole("heading", { name: "Study Overview", level: 1 });
    expect(await screen.findByText(/MPLAD Fund-Utilisation/i)).toBeInTheDocument();
    expect(screen.queryByText(/Desktop window required/i)).toBeNull();
  });

  it("renders the workspace composition at 1440px", async () => {
    setWindowWidth(1440);
    renderApp({ initialEntries: ["/overview"] });
    await screen.findByRole("heading", { name: "Study Overview", level: 1 });
    expect(await screen.findByText(/MPLAD Fund-Utilisation/i)).toBeInTheDocument();
    expect(screen.queryByText(/Desktop window required/i)).toBeNull();
  });

  it("renders the workspace composition at 1366px", async () => {
    setWindowWidth(1366);
    renderApp({ initialEntries: ["/overview"] });
    await screen.findByRole("heading", { name: "Study Overview", level: 1 });
    expect(await screen.findByText(/MPLAD Fund-Utilisation/i)).toBeInTheDocument();
    expect(screen.queryByText(/Desktop window required/i)).toBeNull();
  });

  it("renders the workspace composition at 1280px", async () => {
    setWindowWidth(1280);
    renderApp({ initialEntries: ["/overview"] });
    await screen.findByRole("heading", { name: "Study Overview", level: 1 });
    expect(await screen.findByText(/MPLAD Fund-Utilisation/i)).toBeInTheDocument();
    expect(screen.queryByText(/Desktop window required/i)).toBeNull();
  });

  it("renders the workspace composition at 1024px (PR-06A minimum)", async () => {
    setWindowWidth(1024);
    renderApp({ initialEntries: ["/overview"] });
    await screen.findByRole("heading", { name: "Study Overview", level: 1 });
    expect(await screen.findByText(/MPLAD Fund-Utilisation/i)).toBeInTheDocument();
    expect(screen.queryByText(/Desktop window required/i)).toBeNull();
  });

  // --- Unsupported width (gate) ---

  it("shows the DesktopGate at 1023px and hides the workspace composition", async () => {
    setWindowWidth(1023);
    renderApp({ initialEntries: ["/overview"] });
    await waitFor(() => {
      expect(screen.getByText(/Desktop window required/i)).toBeInTheDocument();
    });
    // The workspace study title is NOT rendered (composition is replaced).
    expect(screen.queryByText(/MPLAD Fund-Utilisation/i)).toBeNull();
    // The gate mentions the minimum width (1024).
    expect(screen.getByText(/1024 CSS pixels/i)).toBeInTheDocument();
  });

  it("does not render a hamburger button or mobile drawer at any width", async () => {
    setWindowWidth(1023);
    renderApp({ initialEntries: ["/overview"] });
    await waitFor(() => {
      expect(screen.getByText(/Desktop window required/i)).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /open navigation drawer/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /close navigation drawer/i })).toBeNull();
    expect(screen.queryByLabelText("Workspace navigation")).toBeNull();
  });

  it("the identity bar and switcher remain visible below 1024px (user can still sign out)", async () => {
    setWindowWidth(1023);
    renderApp({ initialEntries: ["/overview"] });
    await waitFor(() => {
      expect(screen.getByText(/Desktop window required/i)).toBeInTheDocument();
    });
    expect(screen.getByText("PEIARS")).toBeInTheDocument();
    expect(screen.getByRole("tablist", { name: "Workspaces" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });
});
