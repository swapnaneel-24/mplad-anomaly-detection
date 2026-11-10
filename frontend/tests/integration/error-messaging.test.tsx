// Integration test: error messaging.
//
// Renders <OverviewPage /> with getMeta() failing 500; asserts the
// <ErrorPanel> shows the sanitized message + request ID and NO raw
// stack trace.

import { cleanup, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  authenticatedRoutes,
  mockFetch,
  renderApp,
  setCookieJar,
  type FetchRoute,
} from "../helpers/renderApp";

describe("error messaging (integration)", () => {
  let originalFetch: typeof globalThis.fetch;
  let originalCookie: PropertyDescriptor | undefined;
  let originalInnerWidth: number;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    originalCookie = Object.getOwnPropertyDescriptor(document, "cookie");
    originalInnerWidth = window.innerWidth;
    setCookieJar([]);
    // Desktop width so the DesktopGate does not replace the composition.
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

  it("shows a sanitized ErrorPanel with the request id when /meta returns 500", async () => {
    const routes: FetchRoute[] = [
      ...authenticatedRoutes().filter((r) => r.urlContains !== "/meta"),
      {
        urlContains: "/meta",
        status: 500,
        body: {
          error: {
            code: "INTERNAL_SERVER_ERROR",
            message: "The API encountered an internal error.",
            request_id: "req-meta-500",
          },
        },
      },
    ];
    globalThis.fetch = mockFetch(routes) as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/overview"] });
    // The ErrorPanel heading.
    expect(await screen.findByRole("heading", { name: "Error" })).toBeInTheDocument();
    // Sanitized message.
    expect(screen.getByText("The API encountered an internal error.")).toBeInTheDocument();
    // Request ID in mono.
    expect(screen.getByText("req-meta-500")).toBeInTheDocument();
    // Retry button.
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    // No raw stack trace text (no "at Object." or "TypeError" lines).
    expect(screen.queryByText(/at\s+\w+/i)).toBeNull();
  });
});
