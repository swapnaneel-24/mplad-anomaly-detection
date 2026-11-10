// Integration test: route navigation via the horizontal workspace switcher.
//
// Asserts:
//   - All six workspace tabs are present in the switcher.
//   - Clicking each changes the context-strip H1 and document.title.
//   - The active tab carries aria-current="page".
//   - No permanent left sidebar exists; no hamburger/drawer controls.

import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  authenticatedRoutes,
  mockFetch,
  renderApp,
  setCookieJar,
} from "../helpers/renderApp";

const WORKSPACE_LABELS = [
  "Overview",
  "Data",
  "Analysis",
  "Investigations",
  "Domains",
  "Research",
] as const;

const WORKSPACE_TITLES = [
  "Study Overview",
  "Data Observatory",
  "Anomaly Analysis",
  "Investigation Workspace",
  "Cross-Domain Study",
  "Research & Provenance",
] as const;

describe("routes: horizontal switcher navigation and document.title", () => {
  let originalFetch: typeof globalThis.fetch;
  let originalCookie: PropertyDescriptor | undefined;
  let originalInnerWidth: number;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    originalCookie = Object.getOwnPropertyDescriptor(document, "cookie");
    originalInnerWidth = window.innerWidth;
    setCookieJar([]);
    // Desktop width so the DesktopGate does not appear.
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      writable: true,
      value: 1440,
    });
    window.dispatchEvent(new Event("resize"));
    globalThis.fetch = mockFetch(authenticatedRoutes()) as unknown as typeof globalThis.fetch;
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

  it("renders all six workspace tabs in the horizontal switcher", async () => {
    renderApp({ initialEntries: ["/overview"] });
    const switcher = await screen.findByRole("tablist", { name: "Workspaces" });
    for (const label of WORKSPACE_LABELS) {
      const tab = within(switcher).getByRole("tab", { name: new RegExp(label) });
      expect(tab).toBeInTheDocument();
    }
  });

  it("clicking each workspace tab changes the context-strip H1 and document.title", async () => {
    const user = userEvent.setup();
    renderApp({ initialEntries: ["/overview"] });
    // Wait for initial restore + Overview to render.
    await screen.findByRole("heading", { name: "Study Overview", level: 1 });

    for (let i = 0; i < WORKSPACE_LABELS.length; i++) {
      const label = WORKSPACE_LABELS[i]!;
      const title = WORKSPACE_TITLES[i]!;
      const tab = await screen.findByRole("tab", { name: new RegExp(label) });
      await user.click(tab);
      const h1 = await screen.findByRole("heading", { name: title, level: 1 });
      expect(h1).toBeInTheDocument();
      expect(document.title).toBe(`${title} · PEIARS`);
    }
  });

  it("marks the active workspace tab with aria-current=page", async () => {
    renderApp({ initialEntries: ["/data"] });
    await screen.findByRole("heading", { name: "Data Observatory", level: 1 });
    const switcher = screen.getByRole("tablist", { name: "Workspaces" });
    const dataTab = within(switcher).getByRole("tab", { name: /Data/ });
    expect(dataTab).toHaveAttribute("aria-current", "page");
    expect(dataTab).toHaveAttribute("aria-selected", "true");
  });

  it("does not render a permanent left sidebar or mobile hamburger", async () => {
    renderApp({ initialEntries: ["/overview"] });
    await screen.findByRole("heading", { name: "Study Overview", level: 1 });
    // No sidebar landmark (the old aria-label was "Workspace navigation").
    expect(screen.queryByLabelText("Workspace navigation")).toBeNull();
    // No hamburger / drawer-open controls.
    expect(screen.queryByRole("button", { name: /open navigation drawer/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /close navigation drawer/i })).toBeNull();
  });
});
