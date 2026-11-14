// PR-08: Research workspace integration tests.
//
// Verifies the ResearchPage fetches and displays precomputed research
// results from the backend adapter, with correct provenance labels,
// scientific limitations, and the "not live predictions" / "not proof
// of fraud" cautions.

import { cleanup, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  REVIEWER_USER,
  type FetchRoute,
  authenticatedRoutes,
  renderApp,
  setCookieJar,
} from "../helpers/renderApp";
import { CSRF_COOKIE_NAME } from "@/api/contracts";

function setWindowWidth(width: number): void {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    writable: true,
    value: width,
  });
  window.dispatchEvent(new Event("resize"));
}

const RESEARCH_SOURCE_ID = "phase6-reference-values";

const RESEARCH_SOURCES_BODY = {
  items: [
    {
      source_id: RESEARCH_SOURCE_ID,
      dataset_id: "ulb-credit-card-fraud-2013",
      research_family: "stream-a-anomaly-detection",
      model_methods: ["IsolationForest", "LOF"],
      result_type: "aggregate-reference-values",
      result_granularity: "experiment-level",
      availability: "available",
    },
  ],
  count: 1,
};

const RESEARCH_RESULTS_BODY = {
  source_id: RESEARCH_SOURCE_ID,
  dataset_id: "ulb-credit-card-fraud-2013",
  model_methods: ["IsolationForest", "LOF"],
  results: [
    { metric_name: "sample_size", value: 30000, value_type: "int", description: "Rows in the canonical sample" },
    { metric_name: "fraud_label_count", value: 47, value_type: "int", description: "Positive labels in the sample" },
    { metric_name: "spearman_if003_lof004", value: 0.3666, value_type: "float", description: "Spearman rank correlation" },
  ],
  interpretation_principles: [
    "An anomaly flag is not proof of fraud; flags are detector opinions at a fixed budget, not adjudicated findings.",
    "No universal superiority of LOF or Isolation Forest is claimed.",
  ],
  exploratory_caveat: "Exploratory analysis: the highlighted runs were selected after inspecting label-informed results.",
  provenance: {
    artifact_path: "src/mplad/stream_a/phase6.py",
    artifact_sha256: "2a9e7d7973c48e1305fda6f640b36d327b1a019f55419494de6a2d004f7107b3",
    digest_algorithm: "sha-256",
    canonicalization: "raw-bytes",
  },
  limitations: [
    "ULB benchmark performance must not be assumed to transfer to MPLAD transactions.",
  ],
  is_precomputed: true,
  is_live_prediction: false,
};

function buildResearchFetchMock(routes: FetchRoute[], researchFail = false) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();

    if (url.includes("/research/sources") && method === "GET") {
      if (researchFail) {
        return new Response(
          JSON.stringify({ error: { code: "SERVICE_NOT_READY", message: "Research source unavailable", request_id: "r" } }),
          { status: 503, headers: { "content-type": "application/json", "X-Request-ID": "r" } },
        );
      }
      const pathPart = url.split("?")[0] ?? "";
      if (pathPart.endsWith("/research/sources")) {
        return new Response(JSON.stringify(RESEARCH_SOURCES_BODY), {
          status: 200, headers: { "content-type": "application/json", "X-Request-ID": "r" },
        });
      }
      if (pathPart.endsWith("/results")) {
        return new Response(JSON.stringify(RESEARCH_RESULTS_BODY), {
          status: 200, headers: { "content-type": "application/json", "X-Request-ID": "r" },
        });
      }
      return new Response(JSON.stringify(RESEARCH_SOURCES_BODY.items[0]), {
        status: 200, headers: { "content-type": "application/json", "X-Request-ID": "r" },
      });
    }

    const route = routes.find(
      (r) => url.includes(r.urlContains) && (r.method ? r.method.toUpperCase() === method : true),
    );
    if (!route) throw new TypeError(`No mock route for ${method} ${url}`);
    return new Response(JSON.stringify(route.body), {
      status: route.status,
      headers: { "content-type": "application/json", "X-Request-ID": "r" },
    });
  });
}

describe("research workspace — precomputed results display", () => {
  let originalFetch: typeof globalThis.fetch;
  let originalCookie: PropertyDescriptor | undefined;
  let originalInnerWidth: number;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    originalCookie = Object.getOwnPropertyDescriptor(document, "cookie");
    originalInnerWidth = window.innerWidth;
    setCookieJar([]);
    Object.defineProperty(document, "cookie", {
      configurable: true,
      get: () => `${CSRF_COOKIE_NAME}=test-csrf-token`,
      set: () => {},
    });
    setWindowWidth(1440);
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

  it("renders the precomputed results table with correct values", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildResearchFetchMock(routes) as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    await waitFor(() => {
      expect(screen.getByText("Precomputed Research Results")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText("sample_size")).toBeInTheDocument();
      expect(screen.getByText("30000")).toBeInTheDocument();
      expect(screen.getByText("fraud_label_count")).toBeInTheDocument();
      expect(screen.getByText("47")).toBeInTheDocument();
      expect(screen.getByText("spearman_if003_lof004")).toBeInTheDocument();
      expect(screen.getByText("0.3666")).toBeInTheDocument();
    });
  });

  it("displays the 'not live predictions' and 'not proof of fraud' cautions", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildResearchFetchMock(routes) as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    // Wait for the research results table to appear.
    await waitFor(() => {
      expect(screen.getByText("sample_size")).toBeInTheDocument();
    }, { timeout: 5000 });

    // The intro paragraph contains both cautions as <strong> elements.
    // Use getAllByText to avoid "multiple elements" errors.
    const livePred = screen.getAllByText(/not live predictions/i);
    expect(livePred.length).toBeGreaterThanOrEqual(1);
    const notFraud = screen.getAllByText(/not proof of fraud/i);
    expect(notFraud.length).toBeGreaterThanOrEqual(1);
  });

  it("displays the provenance (artifact path and SHA-256)", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildResearchFetchMock(routes) as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    // Wait for the research results table to appear.
    await waitFor(() => {
      expect(screen.getByText("sample_size")).toBeInTheDocument();
    }, { timeout: 5000 });

    // The provenance is in the source metadata <dd> elements.
    const artifactPath = screen.getAllByText("src/mplad/stream_a/phase6.py");
    expect(artifactPath.length).toBeGreaterThanOrEqual(1);
    const sha256 = screen.getAllByText(/2a9e7d7973c48e13/);
    expect(sha256.length).toBeGreaterThanOrEqual(1);
  });

  it("displays the interpretation principles and exploratory caveat", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildResearchFetchMock(routes) as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    await waitFor(() => {
      expect(screen.getByText("Interpretation principles")).toBeInTheDocument();
      expect(screen.getByText(/anomaly flag is not proof of fraud/i)).toBeInTheDocument();
      expect(screen.getByText(/Exploratory analysis/i)).toBeInTheDocument();
    });
  });

  it("renders the heading even when the research endpoint fails", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildResearchFetchMock(routes, true) as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    await waitFor(() => {
      expect(screen.getByText("Precomputed Research Results")).toBeInTheDocument();
    });
  });
});
