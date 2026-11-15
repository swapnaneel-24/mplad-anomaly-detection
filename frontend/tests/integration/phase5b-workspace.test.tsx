// PR-12: Phase 5B figure gallery and traceability integration tests.
//
// Covers the seven F5B acceptance scenarios from the PR-12 implementation
// contract. All fixtures are SYNTHETIC test doubles; no real research payloads
// are embedded. Publication gate is disabled by default; enabling it is a
// per-test override only.

import { cleanup, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  REVIEWER_USER,
  type FetchRoute,
  authenticatedRoutes,
  mockFetch,
  renderApp,
  setCookieJar,
} from "../helpers/renderApp";
import { CSRF_COOKIE_NAME } from "@/api/contracts";

// ---------------------------------------------------------------------------
// Fixture builders
// ---------------------------------------------------------------------------

function makeFigure(
  n: number,
  opts: {
    title?: string | null;
    publicationEnabled?: boolean;
    availabilityAvailable?: boolean;
    availabilityReason?: string | null;
    integrityState?: string;
  } = {},
) {
  const {
    title = `Synthetic figure ${n} title`,
    publicationEnabled = false,
    availabilityAvailable = true,
    availabilityReason = null,
    integrityState = "verified",
  } = opts;
  return {
    figure_no: n,
    filename: `phase5_plot${n}_synthetic.png`,
    title,
    purpose: `Synthetic purpose ${n}`,
    input_artifacts: `Synthetic inputs ${n}`,
    conventions: `Synthetic conventions ${n}`,
    alt_text: `Figure ${n} \u2014 ${title ?? "metadata unavailable"}`,
    integrity: {
      state: integrityState,
      size_bytes: integrityState === "verified" ? 12345 + n : null,
      sha256: integrityState === "verified" ? `synthetic-sha-${n}` : null,
    },
    availability: {
      available: availabilityAvailable,
      reason: availabilityAvailable ? null : availabilityReason,
      detail: null,
    },
    publication: {
      enabled: publicationEnabled,
      reason: publicationEnabled ? null : "publication_not_approved",
      detail: publicationEnabled ? null : "Awaiting licensing verification",
    },
  };
}

const SYN_CATALOG = {
  source_id: "phase5b-figure-gallery",
  dataset_id: "ULB credit-card transactions (Stream A, FS-A baseline)",
  phase: "5B" as const,
  stream: "A" as const,
  models_fitted: 0,
  manifest_status: "verified" as const,
  catalog_metadata_available: true,
  publication_gate: {
    enabled: false,
    reason: "publication_not_approved",
    detail: "Awaiting licensing verification",
  },
  figures: [
    makeFigure(1), makeFigure(2), makeFigure(3), makeFigure(4),
    makeFigure(5), makeFigure(6), makeFigure(7), makeFigure(8),
  ],
  limitations: [
    "All figures are post-hoc, label-informed visualizations of unsupervised detector outputs.",
  ],
};

const SYN_TRACEABILITY = {
  source_identity: {
    document: "docs/provenance_log.md",
    section: "1",
    status: "source_verified",
  },
  objectives: [
    {
      objective_id: "(a)",
      statement: "Data preparation and preprocessing.",
      research_questions: [],
      methodology_sources: ["docs/Phase-0.md \u00A70.3.1"],
      evidence: [],
      limitations: [],
    },
    {
      objective_id: "(b)",
      statement: "Application of Isolation Forest and LOF with comparative evaluation.",
      research_questions: ["RQ1", "RQ3", "RQ4"],
      methodology_sources: ["docs/Phase-0.md \u00A70.4"],
      evidence: [
        {
          type: "canonical_benchmark",
          source_id: "pr-09-benchmark",
          reference: "PR-09 ten-run IF/LOF catalog",
          verification_status: "verified",
        },
      ],
      limitations: [],
    },
    {
      objective_id: "(c)",
      statement: "Assessment of detection consistency, false-positive implications, and ethical considerations.",
      research_questions: ["RQ2", "RQ5", "RQ6"],
      methodology_sources: ["docs/phase6_contract.md \u00A74"],
      evidence: [
        {
          type: "phase6_synthesis",
          source_id: "phase6",
          reference: "Phase 6 five-question consistency report",
          verification_status: "verified",
        },
      ],
      limitations: [],
    },
  ],
  research_questions: [
    { rq_id: "RQ1", statement: "How do iForest and LOF compare in detection performance?", source_reference: "docs/Phase-0.md \u00A70.4", linked_objective: "(b)" },
    { rq_id: "RQ2", statement: "To what extent do the two methods agree?", source_reference: "docs/Phase-0.md \u00A70.4", linked_objective: "(c)" },
    { rq_id: "RQ3", statement: "How sensitive is each method to hyperparameters?", source_reference: "docs/Phase-0.md \u00A70.4", linked_objective: "(b)" },
    { rq_id: "RQ4", statement: "What proportion of variance is captured by PCA?", source_reference: "docs/Phase-0.md \u00A70.4", linked_objective: "(b)" },
    { rq_id: "RQ5", statement: "When applied to government expenditure data, are anomalies interpretable?", source_reference: "docs/Phase-0.md \u00A70.4", linked_objective: "(c)" },
    { rq_id: "RQ6", statement: "At observed false-positive rates, what review volume results?", source_reference: "docs/Phase-0.md \u00A70.4", linked_objective: "(c)" },
  ],
  historical_companion: {
    population: 284807,
    canonical_comparable: false,
    limitations: [
      "The 284,807-row full-dataset run used LOF Novelty Mode fitted on a 50,000-row subsample.",
      "Recall degraded from 80.9% (30k native LOF) to 33.9% (284k Novelty Mode).",
    ],
  },
  reproducibility: {
    source_references: [{ document: "docs/provenance_log.md", purpose: "Per-phase decision trail" }],
    artifact_references: [{ path: "results/stream a/phase 5/figures/reproduction/phase5_plot_commit_manifest.json", kind: "manifest" }],
    limitations: [],
  },
  limitations: [
    "The historical 284,807-row companion is not a canonical comparable population.",
  ],
};

const SYN_PHASE5A_PROTOCOL_UNAVAILABLE = {
  source_id: "phase5a-uncertainty-agreement-evidence",
  dataset_id: "ULB credit-card transactions (Stream A, FS-A baseline)",
  phase: "5A",
  stream: "A",
  layer: "quantitative_diagnostic_analysis",
  run_mode: "execute",
  models_fitted: 0,
  created_utc: "2026-11-05T14:11:41Z",
  environment: {},
  model_fitting: {},
  analytical_conventions: {},
  bootstrap_protocol: {
    n_replicates: 2000,
    ci_level: 0.95,
    ci_method: "percentile",
    seed: 42,
    runs_evaluated: [],
    paired_comparison: { definition: "LOF_004 - IF_003", run_a: "IF_003", run_b: "LOF_004" },
  },
  selection_caveat: "Exploratory analysis.",
  sample: { sample_size: 30000, fraud_count: 47 },
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
  provenance: { phase4_lineage: { verified: true } },
  limitations: [],
};

const SYN_BENCHMARK_CATALOG_UNAVAILABLE = {
  experiments: [],
  capabilities: {
    metrics: { available: false, reason: "artifact_missing", detail: null },
    row_level: { available: false, reason: "artifact_missing", detail: null },
  },
};

function buildRoutes(
  overrides: {
    catalogBody?: unknown;
    catalogStatus?: number;
    traceabilityBody?: unknown;
    traceabilityStatus?: number;
  } = {},
): FetchRoute[] {
  // Specific routes first — before generic matchers in authenticatedRoutes
  // (which includes urlContains: "/sources" that would otherwise match
  // "/research/sources").
  return [
    { urlContains: "/auth/csrf", status: 200, body: { csrf_token: "test-csrf-token" } },
    {
      urlContains: "/research/phase5b/catalog",
      status: overrides.catalogStatus ?? 200,
      body: overrides.catalogBody ?? SYN_CATALOG,
    },
    {
      urlContains: "/research/phase5b/traceability",
      status: overrides.traceabilityStatus ?? 200,
      body: overrides.traceabilityBody ?? SYN_TRACEABILITY,
    },
    { urlContains: "/research/phase5a", status: 200, body: SYN_PHASE5A_PROTOCOL_UNAVAILABLE },
    { urlContains: "/research/benchmark/experiments", status: 200, body: SYN_BENCHMARK_CATALOG_UNAVAILABLE },
    { urlContains: "/research/sources", status: 200, body: { items: [], count: 0 } },
    ...authenticatedRoutes(REVIEWER_USER),
  ];
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("phase5b figure gallery and traceability", () => {
  beforeEach(() => {
    setCookieJar([`${CSRF_COOKIE_NAME}=synthetic-csrf-token`]);
  });

  afterEach(() => {
    cleanup();
  });

  it("F5B-01: renders exactly eight canonical figure entries", async () => {
    globalThis.fetch = mockFetch(buildRoutes()) as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    await waitFor(() => {
      expect(screen.getAllByRole("figure")).toHaveLength(8);
    });

    // Each figure caption carries "Figure N"
    for (let n = 1; n <= 8; n++) {
      expect(screen.getByText(`Figure ${n}`)).toBeInTheDocument();
    }

    // Section heading confirms Phase 5B presence
    expect(screen.getByText(/Phase 5B.*Figure Gallery/)).toBeInTheDocument();
  });

  it("F5B-02: publication disabled shows withheld state without image elements", async () => {
    globalThis.fetch = mockFetch(buildRoutes()) as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    await waitFor(() => {
      expect(screen.getAllByText(/Binary withheld/).length).toBe(8);
    });

    // Publication notice is present and says disabled
    const notice = screen.getByText((_content, element) =>
      element !== null && element.classList.contains("research-page__phase5b-notice"),
    );
    expect(notice).toBeInTheDocument();
    expect(notice.textContent).toContain("disabled");

    // No image element exists in any figure
    const figures = screen.getAllByRole("figure");
    for (const fig of figures) {
      expect(within(fig).queryByRole("img")).toBeNull();
    }
  });

  it("F5B-03: artifact_missing and integrity_failed produce unavailable states", async () => {
    const catalog = JSON.parse(JSON.stringify(SYN_CATALOG));
    catalog.figures[1].availability = { available: false, reason: "artifact_missing", detail: null };
    catalog.figures[1].integrity = { state: "artifact_missing", size_bytes: null, sha256: null };
    catalog.figures[2].availability = { available: false, reason: "integrity_failed", detail: null };
    catalog.figures[2].integrity = { state: "integrity_failed", size_bytes: null, sha256: null };

    globalThis.fetch = mockFetch(buildRoutes({ catalogBody: catalog })) as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    await waitFor(() => {
      expect(screen.getAllByText(/artifact_missing/).length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText(/integrity_failed/).length).toBeGreaterThan(0);

    // Exactly one figure with artifact_missing, one with integrity_failed
    const figures = screen.getAllByRole("figure");
    let artifactMissingCount = 0;
    let integrityFailedCount = 0;
    for (const fig of figures) {
      const text = fig.textContent ?? "";
      if (text.includes("artifact_missing")) artifactMissingCount++;
      if (text.includes("integrity_failed")) integrityFailedCount++;
    }
    expect(artifactMissingCount).toBe(1);
    expect(integrityFailedCount).toBe(1);
  });

  it("F5B-04: publication enabled with available figure uses controlled image URL", async () => {
    const catalog = JSON.parse(JSON.stringify(SYN_CATALOG));
    catalog.publication_gate.enabled = true;
    catalog.publication_gate.reason = null;
    catalog.publication_gate.detail = null;
    for (const fig of catalog.figures) {
      fig.publication = { enabled: true, reason: null, detail: null };
    }

    globalThis.fetch = mockFetch(buildRoutes({ catalogBody: catalog })) as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    await waitFor(() => {
      expect(screen.getAllByRole("img")).toHaveLength(8);
    });

    const images = screen.getAllByRole("img");
    for (let i = 0; i < 8; i++) {
      expect(images[i]).toHaveAttribute(
        "src",
        `/api/v1/research/phase5b/figures/${i + 1}/image`,
      );
    }

    // No withheld placeholders remain
    expect(screen.queryByText(/Binary withheld/)).toBeNull();
  });

  it("F5B-05: objectives (a)/(b)/(c) and RQ1-RQ6 render correctly", async () => {
    globalThis.fetch = mockFetch(buildRoutes()) as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    await waitFor(() => {
      expect(screen.getByText(/Methodology and Original Objectives/)).toBeInTheDocument();
    });

    // Objectives rendered as h4 headings
    expect(screen.getByText(/Objective \(a\)/)).toBeInTheDocument();
    expect(screen.getByText(/Objective \(b\)/)).toBeInTheDocument();
    expect(screen.getByText(/Objective \(c\)/)).toBeInTheDocument();

    // Research questions section + all six RQ labels
    expect(screen.getByText(/Research questions RQ1/)).toBeInTheDocument();
    for (const rq of ["RQ1", "RQ2", "RQ3", "RQ4", "RQ5", "RQ6"]) {
      expect(screen.getByText(rq)).toBeInTheDocument();
    }
  });

  it("F5B-06: historical 284,807-row companion is distinct from 30,000-row canonical", async () => {
    globalThis.fetch = mockFetch(buildRoutes()) as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    await waitFor(() => {
      expect(screen.getByText(/Historical companion/)).toBeInTheDocument();
    });

    // Historical population and canonical population are both mentioned,
    // and the companion is explicitly declared not comparable.
    // getAllByText because each term may appear in both the hardcoded
    // paragraph and in the fixture-provided limitations list.
    expect(screen.getAllByText(/284,807/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/not comparable/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/canonical 30,000-row/).length).toBeGreaterThan(0);
  });

  it("F5B-07: API failure produces error state without fabricated content", async () => {
    const errBody = {
      error: {
        code: "SERVICE_NOT_READY",
        message: "A required application dependency is unavailable.",
        request_id: "req-f5b07",
        details: { dependency: "phase5b-evidence", reason: "artifact_missing" },
      },
    };
    globalThis.fetch = mockFetch(buildRoutes({
      catalogStatus: 503,
      catalogBody: errBody,
      traceabilityStatus: 503,
      traceabilityBody: errBody,
    })) as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/research"] });

    // Wait for the page to actually render. The section heading is emitted
    // unconditionally (outside any data-gated conditional), so its
    // appearance implies the outer meta/auth gates have resolved and the
    // phase5b fetch lifecycle has settled.
    await screen.findByText(/Phase 5B.*Figure Gallery/);

    // No figures, no objectives, no RQ table — no fabricated content
    expect(screen.queryByText(/^Figure 1$/)).toBeNull();
    expect(screen.queryByText(/Objective \(a\)/)).toBeNull();
    expect(screen.queryByText(/Research questions RQ1/)).toBeNull();
    expect(screen.queryByText(/Binary withheld/)).toBeNull();
  });
});