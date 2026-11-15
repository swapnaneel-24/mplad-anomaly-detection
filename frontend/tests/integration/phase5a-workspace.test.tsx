// PR-10: Phase 5A evidence workspace integration tests.
//
// Verifies the ResearchPage Phase 5A section: protocol metadata, per-family
// unavailable states, bootstrap/paired/matrix/hypergeometric/groups/policies/
// thresholds tables when available, bounded discovery-curve paging, and the
// scientific caution labels. All fixtures are SYNTHETIC test doubles.

import { cleanup, screen, waitFor } from "@testing-library/react";
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

const RUN_IDS = [
  "IF_001", "IF_002", "IF_003", "IF_004", "IF_005",
  "LOF_001", "LOF_002", "LOF_003", "LOF_004", "LOF_005",
];

const SYN_PROTOCOL = {
  source_id: "phase5a-uncertainty-agreement-evidence",
  dataset_id: "ULB credit-card transactions (Stream A, FS-A baseline)",
  phase: "5A",
  stream: "A",
  layer: "quantitative_diagnostic_analysis",
  run_mode: "execute",
  models_fitted: 0,
  created_utc: "2026-11-05T14:11:41Z",
  environment: { python: "3.13.13" },
  model_fitting: { models_fitted: 0 },
  analytical_conventions: {},
  bootstrap_protocol: {
    n_replicates: 2000,
    ci_level: 0.95,
    ci_method: "percentile",
    seed: 42,
    runs_evaluated: ["IF_003", "IF_004", "LOF_004"],
    paired_comparison: { definition: "LOF_004 - IF_003", run_a: "IF_003", run_b: "LOF_004" },
  },
  selection_caveat: "Exploratory analysis: highlighted runs were selected post-hoc.",
  sample: { sample_size: 30000, fraud_count: 47, fraud_prevalence: 0.001567 },
  multi_threshold_percents: [0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
  canonical_threshold_pct: 1.0,
  evaluated_run_ids: ["IF_003", "IF_004", "LOF_004"],
  paired_comparison: { definition: "LOF_004 - IF_003" },
  overlap_runs: { run_a: "IF_003", run_b: "LOF_004" },
  capabilities: {
    bootstrap: { available: false, reason: "artifact_missing", detail: null },
    paired: { available: false, reason: "artifact_missing", detail: null },
    spearman: { available: false, reason: "artifact_missing", detail: null },
    jaccard: { available: false, reason: "artifact_missing", detail: null },
    multithreshold: { available: false, reason: "artifact_missing", detail: null },
    hypergeometric: { available: false, reason: "artifact_missing", detail: null },
    groups: { available: false, reason: "artifact_missing", detail: null },
    discovery: { available: false, reason: "artifact_missing", detail: null },
  },
  provenance: {
    phase4_lineage: { verified: true },
  },
  limitations: ["An anomaly flag is not fraud."],
};

const SYN_RESEARCH_SOURCES = {
  items: [{
    source_id: "phase6-reference-values",
    dataset_id: "ulb-credit-card-fraud-2013",
    research_family: "stream-a",
    model_methods: ["IsolationForest", "LOF"],
    result_type: "aggregate-reference-values",
    result_granularity: "experiment-level",
    availability: "available",
  }],
  count: 1,
};

function buildFetchMock(routes: FetchRoute[], mode: "unavailable" | "available" = "unavailable") {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();
    const json = (body: unknown, status = 200) =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json", "X-Request-ID": "r" },
      });

    if (url.includes("/research/phase5a") && method === "GET") {
      const path = url.split("?")[0] ?? "";
      if (path.endsWith("/phase5a") || path.endsWith("/catalog")) {
        if (mode === "available") {
          return json({
            ...SYN_PROTOCOL,
            capabilities: Object.fromEntries(
              Object.entries(SYN_PROTOCOL.capabilities).map(([k]) => [
                k, { available: true, reason: null, detail: null },
              ]),
            ),
          });
        }
        return json(SYN_PROTOCOL);
      }
      if (path.endsWith("/uncertainty")) {
        if (mode === "available") {
          return json({
            bootstrap: { source_id: "x", dataset_id: "x", bootstrap_protocol: { n_replicates: 2000 },
              selection_caveat: "exploratory", metrics: [{
                run_id: "IF_003", metric: "average_precision", point_estimate: 0.5,
                bootstrap_mean: 0.51, bootstrap_std: 0.02, ci_lower: 0.4,
                ci_upper: 0.6, n_replicates: 2000,
              }], provenance: { artifact_path: "x", artifact_md5: "x", artifact_sha256: "x", digest_algorithm: "sha-256", verification: "verified" },
              limitations: [], is_precomputed: true, is_live_prediction: false,
            },
            paired_differences: { source_id: "x", dataset_id: "x", direction: "LOF_004 - IF_003",
              run_a: "IF_003", run_b: "LOF_004", selection_caveat: "exploratory",
              differences: [], provenance: { artifact_path: "x", artifact_md5: "x", artifact_sha256: "x", digest_algorithm: "sha-256", verification: "verified" },
              limitations: [], is_precomputed: true, is_live_prediction: false,
            },
          });
        }
      }
      if (path.endsWith("/agreement")) {
        if (mode === "available") {
          const m = (kind: "spearman" | "jaccard") => ({
            source_id: "x", dataset_id: "x", kind, run_labels: RUN_IDS,
            matrix: RUN_IDS.map((r) => ({ run_id: r, values: Object.fromEntries(RUN_IDS.map((c) => [c, 0.5])) })),
            bounds: { min: kind === "spearman" ? -1 : 0, max: 1 },
            highlighted_pair: { run_a: "IF_003", run_b: "LOF_004" },
            selection_caveat: "exploratory", definition: kind === "spearman"
              ? "Saved rank correlation" : "Intersection over union of saved canonical 1% flags.",
            provenance: { artifact_path: "x", artifact_md5: "x", artifact_sha256: "x", digest_algorithm: "sha-256", verification: "verified" },
            limitations: [], is_precomputed: true, is_live_prediction: false,
          });
          return json({ spearman: m("spearman"), jaccard: m("jaccard") });
        }
      }
      if (path.endsWith("/bootstrap")) {
        if (mode === "available") {
          return json({
            ...SYN_PROTOCOL,
            metrics: [{
              run_id: "IF_003", metric: "average_precision",
              point_estimate: 0.5, bootstrap_mean: 0.51, bootstrap_std: 0.02,
              ci_lower: 0.4, ci_upper: 0.6, n_replicates: 2000,
            }],
            provenance: {
              artifact_path: "phase5_bootstrap_metrics.csv",
              artifact_md5: "abc", artifact_sha256: "def",
              digest_algorithm: "sha-256", verification: "verified",
            },
            limitations: [], is_precomputed: true, is_live_prediction: false,
          });
        }
        return json({ error: { code: "SERVICE_NOT_READY", message: "x", request_id: "r",
          details: { dependency: "phase5a-evidence", reason: "artifact_missing" } } }, 503);
      }
      if (path.endsWith("/agreement/spearman") || path.endsWith("/agreement/jaccard")) {
        const kind = path.endsWith("/agreement/spearman") ? "spearman" : "jaccard";
        if (mode === "available") {
          return json({
            source_id: "x", dataset_id: "x", kind,
            run_labels: RUN_IDS,
            matrix: RUN_IDS.map((r) => ({ run_id: r, values: Object.fromEntries(RUN_IDS.map((c) => [c, 0.5])) })),
            bounds: { min: -1, max: 1 },
            highlighted_pair: { run_a: "IF_003", run_b: "LOF_004" },
            selection_caveat: "exploratory",
            definition: kind === "spearman"
              ? "Pearson correlation of tie-corrected average ranks of anomaly_score vectors (scipy.stats.spearmanr definition)."
              : "Intersection over union of the saved Phase 3 1% flags.",
            provenance: { artifact_path: "x", artifact_md5: "x", artifact_sha256: "x", digest_algorithm: "sha-256", verification: "x" },
            limitations: [], is_precomputed: true, is_live_prediction: false,
          });
        }
        return json({ error: { code: "SERVICE_NOT_READY", message: "x", request_id: "r",
          details: { dependency: "phase5a-evidence", reason: "artifact_missing" } } }, 503);
      }
      if (path.endsWith("/groups") || path.endsWith("/review-policies")) {
        if (mode === "available") {
          return json({
            source_id: "x", dataset_id: "x", run_a: "IF_003", run_b: "LOF_004",
            threshold_pct: 1.0,
            groups: [
              { group: "both", observation_count: 120, fraud_count: 30, non_fraud_count: 90, fraud_proportion: 0.25, recall_contribution: 0.638 },
              { group: "if_only", observation_count: 180, fraud_count: 10, non_fraud_count: 170, fraud_proportion: 0.056, recall_contribution: 0.213 },
              { group: "lof_only", observation_count: 180, fraud_count: 5, non_fraud_count: 175, fraud_proportion: 0.028, recall_contribution: 0.106 },
              { group: "neither", observation_count: 29520, fraud_count: 2, non_fraud_count: 29518, fraud_proportion: 0.0001, recall_contribution: 0.043 },
            ],
            conservation: { total_observations: 30000, total_fraud_count: 47, total_recall_contribution: 1.0 },
            selection_caveat: "exploratory",
            provenance: { artifact_path: "x", artifact_md5: "x", artifact_sha256: "x", digest_algorithm: "sha-256", verification: "x" },
            limitations: [], is_precomputed: true, is_live_prediction: false,
          });
        }
        return json({ error: { code: "SERVICE_NOT_READY", message: "x", request_id: "r",
          details: { dependency: "phase5a-evidence", reason: "artifact_missing" } } }, 503);
      }
      if (path.endsWith("/policies")) {
        if (mode === "available") {
          return json({
            source_id: "x", dataset_id: "x", run_a: "IF_003", run_b: "LOF_004",
            threshold_pct: 1.0, labelled_positive_denominator: 47, sample_size: 30000,
            policies: [
              { policy: "both_only", label: "Both detectors agree", review_count: 120, sample_share: 0.004, labelled_positives_found: 30, precision: 0.25, recall_contribution: 0.638, selection_basis: "both", unequal_budget_note: "not an equal-budget comparison" },
              { policy: "if_003_flags", label: "IF_003 selected flags", review_count: 300, sample_share: 0.01, labelled_positives_found: 40, precision: 0.133, recall_contribution: 0.851, selection_basis: "if", unequal_budget_note: "not an equal-budget comparison" },
              { policy: "lof_004_flags", label: "LOF_004 selected flags", review_count: 300, sample_share: 0.01, labelled_positives_found: 35, precision: 0.117, recall_contribution: 0.745, selection_basis: "lof", unequal_budget_note: "not an equal-budget comparison" },
              { policy: "union", label: "Union of detectors", review_count: 480, sample_share: 0.016, labelled_positives_found: 45, precision: 0.094, recall_contribution: 0.957, selection_basis: "union", unequal_budget_note: "not an equal-budget comparison" },
            ],
            selection_caveat: "exploratory",
            provenance: { artifact_path: "x", artifact_md5: "x", artifact_sha256: "x", digest_algorithm: "sha-256", verification: "x" },
            limitations: [], is_precomputed: true, is_live_prediction: false,
          });
        }
        return json({ error: { code: "SERVICE_NOT_READY", message: "x", request_id: "r",
          details: { dependency: "phase5a-evidence", reason: "artifact_missing" } } }, 503);
      }
      // Default 503 for other Layer-B routes.
      return json({ error: { code: "SERVICE_NOT_READY", message: "x", request_id: "r",
        details: { dependency: "phase5a-evidence", reason: "artifact_missing" } } }, 503);
    }
    if (url.includes("/research/sources") && method === "GET") {
      const path = url.split("?")[0] ?? "";
      if (path.endsWith("/research/sources")) return json(SYN_RESEARCH_SOURCES);
      if (path.endsWith("/results")) {
        return json({
          source_id: "phase6-reference-values",
          dataset_id: "ulb-credit-card-fraud-2013",
          model_methods: ["IsolationForest", "LOF"],
          results: [{ metric_name: "sample_size", value: 30000, value_type: "int", description: "x" }],
          interpretation_principles: ["An anomaly flag is not proof of fraud."],
          exploratory_caveat: "Exploratory.",
          provenance: {
            artifact_path: "src/mplad/stream_a/phase6.py",
            artifact_sha256: "2a9e7d7973c48e13",
            digest_algorithm: "sha-256",
            canonicalization: "raw-bytes",
          },
          limitations: [],
          is_precomputed: true,
          is_live_prediction: false,
        });
      }
      return json(SYN_RESEARCH_SOURCES.items[0]);
    }
    if (url.includes("/research/benchmark") && method === "GET") {
      const path = url.split("?")[0] ?? "";
      if (path.endsWith("/benchmark/experiments")) {
        return json({
          source_id: "canonical-if-lof-benchmark",
          dataset_id: "ULB",
          count: 10,
          experiments: RUN_IDS.map((run_id) => ({
            run_id,
            algorithm: run_id.startsWith("IF") ? "IsolationForest" : "LOF",
            parameters: {},
            parameter_source: { path: "x", sha256: "x", digest_algorithm: "sha-256", canonicalization: "frozen-checker-compatible", note: "x" },
            dataset_id: "ULB",
            model_status: "fitted_offline_frozen",
            metrics_available: false,
            row_lookup_available: false,
          })),
          capabilities: {},
          limitations: [],
        });
      }
      return json({ error: { code: "SERVICE_NOT_READY", message: "x", request_id: "r" } }, 503);
    }

    const route = routes.find(
      (r) => url.includes(r.urlContains) && (r.method ? r.method.toUpperCase() === method : true),
    );
    if (!route) throw new TypeError(`No mock route for ${method} ${url}`);
    return json(route.body, route.status);
  });
}

describe("phase5a evidence workspace", () => {
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
    if (originalCookie) Object.defineProperty(document, "cookie", originalCookie);
    setWindowWidth(originalInnerWidth);
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows the protocol metadata and per-family unavailable states", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildFetchMock(routes, "unavailable") as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    await waitFor(() => {
      expect(screen.getByText("Phase 5A Evidence — Uncertainty, Agreement, Review Policies")).toBeInTheDocument();
    });
    // Protocol metadata.
    expect(screen.getByText(/5A \/ A \/ quantitative_diagnostic_analysis/)).toBeInTheDocument();
    expect(screen.getAllByText(/2000 replicates/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/LOF_004 - IF_003/)).toBeInTheDocument();
    // Per-family unavailable states.
    expect(screen.getAllByText(/DVC-backed bootstrap payload has not been provisioned/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/discovery-curve payload has not been provisioned/i)).toBeInTheDocument();
    // Selection caveat.
    expect(screen.getAllByText(/Exploratory analysis/i).length).toBeGreaterThanOrEqual(1);
  });

  it("shows saved evidence tables when payloads are available", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildFetchMock(routes, "available") as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    await waitFor(() => {
      expect(screen.getByText("Phase 5A Evidence — Uncertainty, Agreement, Review Policies")).toBeInTheDocument();
    });
    // Bootstrap table renders a synthetic row.
    await waitFor(() => {
      expect(screen.getAllByText("average_precision").length).toBeGreaterThanOrEqual(1);
    }, { timeout: 5000 });
    // Review policies section renders (the four-policy table with
    // unequal-budget notes). Use the section heading as the anchor since
    // the per-policy note text is identical across rows.
    await waitFor(() => {
      expect(screen.getByText("Review policies (unequal review costs)")).toBeInTheDocument();
    }, { timeout: 5000 });
    // Agreement groups table renders.
    expect(screen.getByText("Four-way agreement groups (IF_003 vs LOF_004, 1%)")).toBeInTheDocument();
  });

  it("switches between Spearman and Jaccard matrix tabs", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildFetchMock(routes, "available") as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    await waitFor(() => {
      expect(screen.getByText("Phase 5A Evidence — Uncertainty, Agreement, Review Policies")).toBeInTheDocument();
    });
    const spearmanTab = screen.getByRole("tab", { name: "Spearman rank" });
    const jaccardTab = screen.getByRole("tab", { name: "Jaccard 1%" });
    expect(spearmanTab).toBeInTheDocument();
    expect(jaccardTab).toBeInTheDocument();
    await userEvent.click(jaccardTab);
    // The matrix re-fetches for jaccard and renders its definition.
    await waitFor(() => {
      expect(screen.getByText(/Intersection over union/i)).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it("renders the bounded discovery-curve viewer when available", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildFetchMock(routes, "available") as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    await waitFor(() => {
      expect(screen.getByText("Fraud-discovery curve (bounded)")).toBeInTheDocument();
    });
    expect(screen.getByLabelText("Run")).toBeInTheDocument();
  });

  it("preserves the PR-08 and PR-09 sections alongside Phase 5A", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildFetchMock(routes, "unavailable") as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    await waitFor(() => {
      expect(screen.getByText("Precomputed Research Results")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("Canonical Benchmark — Ten IF/LOF Runs")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("Phase 5A Evidence — Uncertainty, Agreement, Review Policies")).toBeInTheDocument();
    });
  });

  it("does not overflow horizontally at 1024px", async () => {
    const routes = authenticatedRoutes(REVIEWER_USER);
    globalThis.fetch = buildFetchMock(routes, "available") as unknown as typeof globalThis.fetch;

    setWindowWidth(1024);
    renderApp({ initialEntries: ["/research"] });

    await waitFor(() => {
      expect(screen.getByText("Phase 5A Evidence — Uncertainty, Agreement, Review Policies")).toBeInTheDocument();
    });
    expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(window.innerWidth + 1);
  });
});
