// Vitest setup — runs before every test file.
//
// Imports jest-dom matchers (toBeInTheDocument, toHaveAttribute, etc.)
// and defines minimal browser-API mocks that jsdom does not provide:
// matchMedia (used by some React libraries) and IntersectionObserver
// (not used by PEIARS today, but cheap to mock for future components).

import "@testing-library/jest-dom/vitest";

// matchMedia mock — jsdom does not implement it.
if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: (query: string): MediaQueryList => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }),
  });
}

// IntersectionObserver mock — jsdom does not implement it.
if (typeof window !== "undefined" && !("IntersectionObserver" in window)) {
  class IntersectionObserverMock implements IntersectionObserver {
    readonly root: Element | Document | null = null;
    readonly rootMargin: string = "0px";
    readonly thresholds: ReadonlyArray<number> = [0];
    constructor(
      _callback: IntersectionObserverCallback,
      _options?: IntersectionObserverInit,
    ) {}
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
    takeRecords(): IntersectionObserverEntry[] {
      return [];
    }
  }
  Object.defineProperty(window, "IntersectionObserver", {
    writable: true,
    configurable: true,
    value: IntersectionObserverMock,
  });
}

// jsdom does not implement Element.scrollTo or window.scrollTo.
if (typeof window !== "undefined" && !window.scrollTo) {
  Object.defineProperty(window, "scrollTo", {
    writable: true,
    configurable: true,
    value: () => undefined,
  });
}
