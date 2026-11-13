// Integration test: keyboard interaction with the horizontal workspace switcher.
//
// - Tab enters the switcher; the active tab is focusable (tabindex=0).
// - Arrow Right/Left moves focus between tabs (WAI-ARIA tabs pattern).
// - Enter/Space activates the focused tab.
// - No mobile drawer / hamburger / Escape-to-close behavior.

import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

describe("keyboard interaction (horizontal switcher)", () => {
  let originalFetch: typeof globalThis.fetch;
  let originalCookie: PropertyDescriptor | undefined;
  let originalInnerWidth: number;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    originalCookie = Object.getOwnPropertyDescriptor(document, "cookie");
    originalInnerWidth = window.innerWidth;
    setCookieJar([]);
    setWindowWidth(1440);
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

  it("Arrow Right moves focus to the next tab and Enter activates it", async () => {
    const user = userEvent.setup();
    renderApp({ initialEntries: ["/overview"] });
    const heading = await screen.findByRole("heading", { name: "Study Overview", level: 1 });
    await waitFor(() => expect(heading).toHaveFocus());
    const switcher = screen.getByRole("tablist", { name: "Workspaces" });
    const overviewTab = within(switcher).getByRole("tab", { name: /Overview/ });
    overviewTab.focus();
    expect(overviewTab).toHaveFocus();

    // Arrow Right → Data tab receives focus.
    await user.keyboard("{ArrowRight}");
    const dataTab = within(switcher).getByRole("tab", { name: /Data/ });
    expect(dataTab).toHaveFocus();

    // Enter activates the Data tab.
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("heading", { name: "Data Observatory", level: 1 })).toBeInTheDocument();
  });

  it("Arrow Left wraps to the last tab from the first tab", async () => {
    const user = userEvent.setup();
    renderApp({ initialEntries: ["/overview"] });
    const heading = await screen.findByRole("heading", { name: "Study Overview", level: 1 });
    await waitFor(() => expect(heading).toHaveFocus());
    const switcher = screen.getByRole("tablist", { name: "Workspaces" });
    const overviewTab = within(switcher).getByRole("tab", { name: /Overview/ });
    overviewTab.focus();

    // Arrow Left from the first tab wraps to the last (Research).
    await user.keyboard("{ArrowLeft}");
    const researchTab = within(switcher).getByRole("tab", { name: /Research/ });
    expect(researchTab).toHaveFocus();
  });

  it("Home moves focus to the first tab; End to the last", async () => {
    const user = userEvent.setup();
    renderApp({ initialEntries: ["/overview"] });
    await screen.findByRole("heading", { name: "Study Overview", level: 1 });

    const switcher = screen.getByRole("tablist", { name: "Workspaces" });
    // End → Research (last)
    const overviewTab = within(switcher).getByRole("tab", { name: /Overview/ });
    overviewTab.focus();
    await user.keyboard("{End}");
    const researchTab = within(switcher).getByRole("tab", { name: /Research/ });
    expect(researchTab).toHaveFocus();

    // Home → Overview (first)
    await user.keyboard("{Home}");
    expect(overviewTab).toHaveFocus();
  });

  it("the active tab is in the tab order (tabindex=0) and inactive tabs are not", async () => {
    renderApp({ initialEntries: ["/overview"] });
    await screen.findByRole("heading", { name: "Study Overview", level: 1 });

    const switcher = screen.getByRole("tablist", { name: "Workspaces" });
    const overviewTab = within(switcher).getByRole("tab", { name: /Overview/ });
    const dataTab = within(switcher).getByRole("tab", { name: /Data/ });

    expect(overviewTab).toHaveAttribute("tabindex", "0");
    // Inactive tabs have tabindex=-1 (roving tabindex).
    expect(dataTab).toHaveAttribute("tabindex", "-1");
  });
});
