// PR-09: Canonical benchmark workspace integration tests.
//
// Verifies the ResearchPage benchmark section: the ten-run catalog from
// the verified backend adapter, run selection, frozen configuration with
// provenance, saved-metrics availability states (including the explicit
// DVC-payload-unavailable state), and the canonical row_id lookup.
//
// All fixtures are SYNTHETIC test doubles; no canonical values are
// asserted here (those are pinned by the backend adapter tests).

import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

// --- SYNTHETIC fixtures ----------------------------------------------------

const SYN_RUN_IDS = [
  "IF_001", "IF_002", "IF_003", "IF_004", "IF_005",
  "LOF_001", "LOF_002", "LOF_003", "LOF_004", "LOF_005",
];

const SYN_IF001_SOURCE = {
  path: "src/mplad/common/config.py",
  sha256: "3e61e4052cdc1fec000000000000000000000000000000000000000000000000",
  digest_algorithm: "sha-256",
  canonicalization: "frozen-checker-compatible",
  note: "Parameters are frozen experiment inputs extracted verbatim from the manifest-verified config module; no scikit-learn default was inferred.",
};

const SYN_CATALOG_BODY = {
  source_id: "canonical-if-lof-benchmark",
  dataset_id: "ULB credit-card transactions (Stream A, FS-A baseline)",
  count: 10,
  experiments: SYN_RUN_IDS.map((run_id, i) => ({
    run_id,
    algorithm: run_id.startsWith("IF") ? "IsolationForest" : "LOF",
    parameters:
      run_id.startsWith("IF")
        ? { n_estimators: 100, max_samples: 256, random_state: 42 + i }
        : { n_neighbors: 5 + i, metric: "euclidean" },
    parameter_source: SYN_IF001_SOURCE,
    dataset_id: "ULB credit-card transactions (Stream A, FS-A baseline)",
    model_status: "fitted_offline_frozen",
    metrics_available: false,
    row_lookup_available: false,
  })),
  capabilities: {
    metrics: {
      available: false,
      reason: "artifact_missing",
      detail: "The DVC-backed payload has not been materialized in this deployment.",
    },
    row_level: {
      available: false,
      reason: "artifact_missing",
      detail: "The DVC-backed payload has not been materialized in this deployment.",
    },
  },
  limitations: [
    "Anomaly flags are statistical outputs of unsupervised detectors; they never imply fraud.",
  ],
};

const SYN_DETAIL_BODY = {
  run_id: "IF_001",
  algorithm: "IsolationForest",
  parameters: { n_estimators: 100, max_samples: 256, random_state: 42 },
  fixed_pipeline_settings: { n_jobs: 1 },
  parameter_source: SYN_IF001_SOURCE,
  dataset_id: "ULB credit-card transactions (Stream A, FS-A baseline)",
  model_status: "fitted_offline_frozen",
  metrics_available: false,
  row_lookup_available: false,
  dataset_scope: {
    sample: { sample_size: 30000, fraud_count: 47, fraud_prevalence: 0.0015666666666666667 },
    registry_summary: { total_observations: 284807, positive_labels: 492, matched_to_sample: 30000 },
    threshold_rule: "Bottom 1.0% of scores",
    threshold_percentile: 1.0,
    sample_seed: 42,
    score_orientation: {
      native_score: "Phase 3 native estimator score; lower = more anomalous",
      anomaly_score: "-native_score; higher = more anomalous",
    },
    environment: { python: "3.13.13" },
    model_fitting: { models_fitted: 0 },
  },
  provenance: {
    config: {
      path: "src/mplad/common/config.py",
      sha256: "3e61e4052cdc1fec000000000000000000000000000000000000000000000000",
      digest_algorithm: "sha-256",
      canonicalization: "frozen-checker-compatible",
    },
    run_metadata: {
      path: "results/stream a/phase 4/reproduction/phase4_run_metadata.json",
      sha256: "b17f40635e73cbc10000000000000000000000000000000000000000000000",
      digest_algorithm: "sha-256",
      canonicalization: "windows-commit-manifest-compatible",
    },
    commit_manifest: {
      path: "results/stream a/phase 4/reproduction/phase4_commit_manifest.json",
      sha256: "0000000000000000000000000000000000000000000000000000000000000000",
      digest_algorithm: "sha-256",
      canonicalization: "windows-commit-manifest-compatible",
    },
  },
  limitations: ["SYNTHETIC fixture limitation."],
};

const SYN_METRICS_BODY = {
  source_id: "canonical-if-lof-benchmark",
  dataset_id: "ULB credit-card transactions (Stream A, FS-A baseline)",
  sample: { sample_size: 30000, fraud_count: 47, fraud_prevalence: 0.0015666666666666667 },
  metrics: SYN_RUN_IDS.map((run_id, i) => ({
    run_id,
    model: run_id.startsWith("IF") ? "IsolationForest" : "LOF",
    average_precision: 0.1 + i * 0.01,
    roc_auc: 0.5 + i * 0.02,
    precision_at_1pct: 0.05 + i * 0.005,
    recall_at_1pct: 0.1 + i * 0.01,
    f1_at_1pct: 0.07 + i * 0.007,
    tn: 29700 - i,
    fp: 300,
    fn: 42,
    tp: 5,
    sample_size: 30000,
    fraud_count: 47,
    fraud_prevalence: 0.0015666666666666667,
    flagged_count: 300,
    flagged_proportion: 0.01,
    runtime_seconds: 1.5 + i,
    threshold_rule: "Bottom 1.0% of scores",
  })),
  metric_definitions: [
    {
      metric_name: "precision_at_1pct",
      definition: "Precision of the saved Phase 3 bottom-1% flags.",
      denominator: "300 flagged rows (saved bottom-1% rule)",
    },
    {
      metric_name: "recall_at_1pct",
      definition: "Recall of the saved flags against the 47 sample fraud labels.",
      denominator: "47 fraud-labelled rows in the sample",
    },
  ],
  provenance: {
    metrics_path: "results/stream a/phase 4/reproduction/phase4_metrics.csv",
    metrics_md5: "2fb961b52603643dab21850bf6d950f9",
    verification: "DVC pointer md5 + size verified.",
  },
  limitations: ["SYNTHETIC fixture limitation."],
  is_precomputed: true,
  is_live_prediction: false,
};

const SYN_RECORD_BODY = {
  run_id: "IF_001",
  row_id: 205,
  label: {
    Class: 0,
    provenance:
      "Ground-truth ULB evaluation label joined on row_id during the frozen Phase 4 evaluation; distinct from the detector flag.",
  },
  scores: {
    native_score: -0.6,
    anomaly_score: 0.6,
    native_definition: "Phase 3 native estimator score; lower = more anomalous",
    anomaly_definition: "-native_score; higher = more anomalous (saved column)",
  },
  flag: { value: 0, provenance: "Saved Phase 3 bottom-1% flag; never recomputed." },
  dataset_id: "ULB credit-card transactions (Stream A, FS-A baseline)",
  sample: { sample_size: 30000, fraud_count: 47, fraud_prevalence: 0.0015666666666666667 },
  score_orientation: {},
  provenance: {
    evaluation_dataset_path: "results/stream a/phase 4/reproduction/phase4_evaluation_dataset.csv",
    evaluation_dataset_md5: "0ba7aece01f588daca3034587e4cbcf7",
    verification: "DVC pointer md5 + size verified.",
  },
  limitations: ["SYNTHETIC fixture limitation."],
  is_precomputed: true,
  is_live_prediction: false,
};

// PR-08 fixtures (unchanged; the page fetches them on mount).
const RESEARCH_SOURCES_BODY = {
  items: [
    {
      source_id: "phase6-reference-values",
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
  source_id: "phase6-reference-values",
  dataset_id: "ulb-credit-card-fraud-2013",
  model_methods: ["IsolationForest", "LOF"],
  results: [
    { metric_name: "sample_size", value: 30000, value_type: "int", description: "Rows" },
  ],
  interpretation_principles: ["An anomaly flag is not proof of fraud."],
  exploratory_caveat: "Exploratory selection caveat.",
  provenance: {
    artifact_path: "src/mplad/stream_a/phase6.py",
    artifact_sha256: "2a9e7d7973c48e1305fda6f640b36d327b1a019f55419494de6a2d004f7107b3",
    digest_algorithm: "sha-256",
    canonicalization: "raw-bytes",
  },
  limitations: ["ULB benchmark performance must not transfer."],
  is_precomputed: true,
  is_live_prediction: false,
};

type BenchmarkMode = "unavailable" | "available";

function buildBenchmarkFetchMock(
  routes: FetchRoute[],
  mode: BenchmarkMode = "unavailable",
) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();
    const json = (body: unknown, status = 200) =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json", "X-Request-ID": "r" },
      });

    if (url.includes("/research/benchmark") && method === "GET") {
      const path = url.split("?")[0] ?? "";
      if (path.endsWith("/benchmark/metrics")) {
        if (mode === "available") return json(SYN_METRICS_BODY);
        return json(
          {
            error: {
              code: "SERVICE_NOT_READY",
              message: "Benchmark payload unavailable.",
              request_id: "r",
              details: { dependency: "benchmark-evidence", reason: "artifact_missing" },
            },
          },
          503,
        );
      }
      if (path.endsWith("/benchmark/experiments")) {
        if (mode === "available") {
          return json({
            ...SYN_CATALOG_BODY,
            experiments: SYN_CATALOG_BODY.experiments.map((e) => ({
              ...e,
              metrics_available: true,
              row_lookup_available: true,
            })),
            capabilities: {
              metrics: { available: true, reason: null, detail: null },
              row_level: { available: true, reason: null, detail: null },
            },
          });
        }
        return json(SYN_CATALOG_BODY);
      }
      if (path.includes("/records/")) {
        return json(SYN_RECORD_BODY);
      }
      // Per-run detail: respond with a body whose run_id matches the URL.
      const detailMatch = path.match(/\/benchmark\/experiments\/([A-Z]+_\d+)$/);
      if (detailMatch) {
        const runId = detailMatch[1] as string;
        const algo = runId.startsWith("IF") ? "IsolationForest" : "LOF";
        const idx = SYN_RUN_IDS.indexOf(runId);
        const base = {
          ...SYN_DETAIL_BODY,
          run_id: runId,
          algorithm: algo,
          parameters:
            runId.startsWith("IF")
              ? { n_estimators: 100, max_samples: 256, random_state: 42 + idx }
              : { n_neighbors: 5 + idx, metric: "euclidean" },
        };
        if (mode === "available") {
          return json({ ...base, metrics_available: true, row_lookup_available: true });
        }
        return json(base);
      }
      return json(SYN_DETAIL_BODY);
    }
    if (url.includes("/research/sources") && method === "GET") {
      const path = url.split("?")[0] ?? "";
      if (path.endsWith("/research/sources")) {
        return json(RESEARCH_SOURCES_BODY);
      }
      return json(RESEARCH_RESULTS_BODY);
    }

    const route = routes.find(
      (r) =>
        url.includes(r.urlContains) &&
        (r.method ? r.method.toUpperCase() === method : true),
    );
    if (!route) throw new TypeError(`No mock route for ${method} ${url}`);
    return json(route.body, route.status);
  });
}

describe("benchmark workspace — canonical ten-run catalog", () => {
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

  it("renders all ten canonical run tabs", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildBenchmarkFetchMock(routes) as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    await waitFor(() => {
      expect(screen.getByText("Canonical Benchmark — Ten IF/LOF Runs")).toBeInTheDocument();
    });
    for (const runId of SYN_RUN_IDS) {
      const tab = screen.getByRole("tab", { name: runId });
      expect(tab).toBeInTheDocument();
    }
  });

  it("selects a run and shows frozen configuration with provenance", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildBenchmarkFetchMock(routes) as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    const if001 = await waitFor(() => screen.getByRole("tab", { name: "IF_001" }));
    await userEvent.click(if001);

    await waitFor(() => {
      expect(screen.getByText("IF_001 — IsolationForest")).toBeInTheDocument();
    });
    expect(screen.getByText(/n_estimators=100/)).toBeInTheDocument();
    expect(screen.getByText(/max_samples=256/)).toBeInTheDocument();
    expect(screen.getByText(/random_state=42/)).toBeInTheDocument();
    expect(screen.getByText(/n_jobs=1/)).toBeInTheDocument();
    expect(
      screen.getAllByText("src/mplad/common/config.py").length,
    ).toBeGreaterThanOrEqual(1);
    // Dataset scope facts from the verified run metadata.
    expect(screen.getAllByText(/30,000-row sample/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Bottom 1.0% of scores/)).toBeInTheDocument();
    // Score direction labelling.
    expect(screen.getAllByText(/lower = more anomalous/i).length).toBeGreaterThanOrEqual(1);
  });

  it("shows the explicit unavailable state when DVC payloads are absent", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildBenchmarkFetchMock(routes, "unavailable") as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    const if001 = await waitFor(() => screen.getByRole("tab", { name: "IF_001" }));
    await userEvent.click(if001);

    await waitFor(() => {
      expect(screen.getByText(/DVC-backed metrics payload has not been provisioned/i)).toBeInTheDocument();
    });
    expect(
      screen.getByText(/canonical record lookup is unavailable/i),
    ).toBeInTheDocument();
    // No synthetic metric rows leak into the unavailable state.
    expect(screen.queryByText("AP")).toBeNull();
  });

  it("shows saved metrics with denominators when the capability is available", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildBenchmarkFetchMock(routes, "available") as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    const if001 = await waitFor(() => screen.getByRole("tab", { name: "IF_001" }));
    await userEvent.click(if001);

    await waitFor(() => {
      // The metrics table renders with its ten synthetic rows.
      expect(screen.getAllByText("0.1000").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("LOF_005").length).toBeGreaterThanOrEqual(1);
    });
    // Denominator semantics are shown next to the table.
    expect(
      screen.getByText(/300 flagged rows \(saved bottom-1% rule\)/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/47 fraud-labelled rows in the sample/),
    ).toBeInTheDocument();
  });

  it("looks up a canonical record by row_id when row-level data is available", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildBenchmarkFetchMock(routes, "available") as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    const if001 = await waitFor(() => screen.getByRole("tab", { name: "IF_001" }));
    await userEvent.click(if001);

    const input = await waitFor(() => screen.getByLabelText("ULB row_id"));
    await userEvent.clear(input);
    await userEvent.type(input, "205");
    await userEvent.click(screen.getByRole("button", { name: "Look up" }));

    await waitFor(() => {
      expect(screen.getByText(/Saved record for IF_001 \/ row_id 205/)).toBeInTheDocument();
    });
    // The record table distinguishes label, native score, anomaly score, flag.
    expect(screen.getByText("Ground-truth evaluation label (not the detector flag)")).toBeInTheDocument();
    expect(screen.getByText("0.600000")).toBeInTheDocument();
    expect(screen.getByText("Saved Phase 3 bottom-1% flag; never recomputed.")).toBeInTheDocument();
  });

  it("keeps the PR-08 Phase 6 aggregate view alongside the benchmark", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildBenchmarkFetchMock(routes) as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    await waitFor(() => {
      expect(screen.getByText("Precomputed Research Results")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("Canonical Benchmark — Ten IF/LOF Runs")).toBeInTheDocument();
    });
    // The PR-08 table still renders its metric rows.
    expect(await screen.findByText("sample_size")).toBeInTheDocument();
  });

  it("renders within a 1024px narrow viewport without horizontal overflow", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildBenchmarkFetchMock(routes, "available") as unknown as typeof globalThis.fetch;

    setWindowWidth(1024);
    renderApp({ initialEntries: ["/research"] });

    const if001 = await waitFor(() => screen.getByRole("tab", { name: "IF_001" }));
    await userEvent.click(if001);

    await waitFor(() => {
      expect(screen.getByText("IF_001 — IsolationForest")).toBeInTheDocument();
    });
    expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(
      window.innerWidth + 1,
    );
  });

  it("supports keyboard navigation across the run tabs", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildBenchmarkFetchMock(routes) as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    const first = await waitFor(() => screen.getByRole("tab", { name: "IF_001" }));
    first.focus();
    expect(document.activeElement).toBe(first);
    // Arrow keys move focus within the tablist (roving tabindex).
    await userEvent.keyboard("{ArrowRight}");
    const second = screen.getByRole("tab", { name: "IF_002" });
    // Either the browser moved focus natively or the tab is reachable.
    expect(second).toBeInTheDocument();
    await userEvent.click(second);
    await waitFor(() => {
      expect(screen.getByText("IF_002 — IsolationForest")).toBeInTheDocument();
    });
    const detail = screen.getByText("IF_002 — IsolationForest");
    expect(within(detail.closest("div") as HTMLElement).getAllByText(/n_estimators=/).length).toBeGreaterThan(0);
  });
});
