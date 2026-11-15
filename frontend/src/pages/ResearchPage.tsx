// Research & Provenance — Reproducibility Workspace.
// Per SCREEN_DESIGN_NOTES.md §8. Two-column grid:
//   left (1fr):   methodological sections (Phase 3–6) + reproducibility
//   right (320px): artifact index + limitations + cautions (sticky)
//
// PR-08: extended with a read-only "Precomputed Research Results" section
// that fetches frozen scientific reference values from the backend
// research adapter (/api/v1/research/*). The results are aggregate-level
// experiment metrics from the ULB credit-card fraud benchmark, served
// read-only with full provenance. No live predictions, no model execution.
//
// PR-09: extended with a "Canonical Benchmark" section that lists the ten
// authentic IF/LOF runs (IF_001..IF_005, LOF_001..LOF_005) from the
// verified catalog, allows selecting one run, shows its exact frozen
// configuration with provenance, shows saved Phase 4 metrics only when the
// admitted DVC payload is available, and offers a canonical row_id lookup
// into the admitted evaluation dataset. Unavailable capabilities render an
// explicit unavailable state (never a synthetic fallback).
//
// PR-10: extended with a "Phase 5A Evidence" section (uncertainty,
// agreement, review-policy and discovery-curve evidence) served read-only
// from the verified Phase 5A adapter. Each family has an independent
// unavailable state; no synthetic metrics are ever shown. Scientific labels
// protect against over-interpretation (anomaly ≠ fraud; CI ≠ probability of
// wrongdoing; unequal-budget policies; post-hoc selection caveat).

import { useEffect, useState } from "react";
import {
  getMeta,
  getResearchSources,
  getResearchResults,
  getBenchmarkExperiments,
  getBenchmarkExperiment,
  getBenchmarkMetrics,
  getBenchmarkRecord,
  getPhase5AProtocol,
  getPhase5ABootstrap,
  getPhase5APairedDifferences,
  getPhase5AAgreementMatrix,
  getPhase5AOverlapNull,
  getPhase5AGroups,
  getPhase5AUncertainty,
  getPhase5AAgreement,
  getPhase5AThresholds,
  getPhase5ADiscoveryCurve,
} from "@/api/endpoints";
import { ApiError } from "@/api/client";
import type {
  MetaResponse,
  ResearchSourceSummary,
  ResearchResultsResponse,
  BenchmarkCatalogResponse,
  BenchmarkExperimentDetail,
  BenchmarkMetricsResponse,
  BenchmarkRecordResponse,
  Phase5AProtocolResponse,
  Phase5ABootstrapMetricsResponse,
  Phase5APairedDifferencesResponse,
  Phase5AAgreementMatrixResponse,
  Phase5AHypergeometricResponse,
  Phase5AAgreementGroupsResponse,
  Phase5AMultithresholdResponse,
  Phase5ADiscoveryCurveResponse,
} from "@/api/contracts";
import { Loading } from "@/components/Loading";
import { ErrorPanel } from "@/components/ErrorPanel";
import "@/pages/ResearchPage.css";

// All 28 frozen research artifacts with their verified SHA-256 prefixes.
// These MUST match ci/frozen_research_manifest.json exactly. A backend
// test (test_research_adapter.py::test_artifact_digest_matches_frozen_manifest)
// verifies that the adapter serves the same digest as the manifest; the
// displayed prefix here is the first 16 hex chars of that digest.
const FROZEN_ARTIFACTS: { path: string; sha256: string }[] = [
  { path: "docs/MPLAD_Project_Inference_and_decision.docx", sha256: "6312c4ed505c27ed" },
  { path: "docs/MPLAD_framework_pipeline.md", sha256: "7d5ad8dabe038c0a" },
  { path: "docs/PHASE3_MIGRATION_GUIDE.md", sha256: "fea14011746b32f0" },
  { path: "docs/Phase-0.md", sha256: "3f00ce99a8a5e6e6" },
  { path: "docs/feature_space_manifest.md", sha256: "bf2ee307ef06a293" },
  { path: "docs/phase4_contract.md", sha256: "3c8034b698d3fed4" },
  { path: "docs/phase5_figure_catalog.md", sha256: "fe24df9d93935f5d" },
  { path: "docs/phase6_contract.md", sha256: "00cc73bcff13b782" },
  { path: "docs/phase7_synthesis.md", sha256: "7436d5ddbfb01994" },
  { path: "docs/provenance_log.md", sha256: "7945c96a1a9af9f6" },
  { path: "src/mplad/__init__.py", sha256: "a9d13b604cb35c72" },
  { path: "src/mplad/common/__init__.py", sha256: "cabb07d57f320de3" },
  { path: "src/mplad/common/config.py", sha256: "3e61e4052cdc1fec" },
  { path: "src/mplad/common/io.py", sha256: "243dc5b8e1e2b5bf" },
  { path: "src/mplad/common/manifest.py", sha256: "b8bbf9f920267c37" },
  { path: "src/mplad/common/validation.py", sha256: "417a5ae6589112b8" },
  { path: "src/mplad/stream_a/__init__.py", sha256: "7c37a2bc6fab8498" },
  { path: "src/mplad/stream_a/phase3.py", sha256: "4ce2d229ff588915" },
  { path: "src/mplad/stream_a/phase4.py", sha256: "fcae730cfe15edb1" },
  { path: "src/mplad/stream_a/phase5.py", sha256: "e3b0c44298fc1c14" },
  { path: "src/mplad/stream_a/phase5_analysis.py", sha256: "8048479c7825bc21" },
  { path: "src/mplad/stream_a/phase5_plots.py", sha256: "473384ae124eec9c" },
  { path: "src/mplad/stream_a/phase6.py", sha256: "2a9e7d7973c48e13" },
  { path: "tests/test_phase3.py", sha256: "c9bc1113c6ddfd90" },
  { path: "tests/test_phase4.py", sha256: "c093b676dff651db" },
  { path: "tests/test_phase5_analysis.py", sha256: "70b2e7a7764e3071" },
  { path: "tests/test_phase5_plots.py", sha256: "a8950526da6347a7" },
  { path: "tests/test_phase6.py", sha256: "f5e9288404f77b42" },
];

const BACKEND_TEST_COUNT = 592;

const METHODOLOGY_PHASES: { phase: string; title: string; summary: string; docRef: string }[] = [
  {
    phase: "Phase 3",
    title: "Feature engineering",
    summary:
      "Construction of the ULB benchmark feature space from the verified dataset. Feature definitions are documented in the feature-space manifest; the phase is frozen and its tests are green.",
    docRef: "docs/feature_space_manifest.md",
  },
  {
    phase: "Phase 4",
    title: "Model fitting",
    summary:
      "Unsupervised anomaly-detection model fitting (Isolation Forest, Local Outlier Factor). The fitting contract is documented in the phase-4 contract; the phase is frozen.",
    docRef: "docs/phase4_contract.md",
  },
  {
    phase: "Phase 5",
    title: "Analysis",
    summary:
      "Anomaly-score analysis and figure generation. The figure catalog documents every figure produced; the phase is frozen and its tests are green.",
    docRef: "docs/phase5_figure_catalog.md",
  },
  {
    phase: "Phase 6",
    title: "Synthesis",
    summary:
      "Cross-cutting synthesis of the anomaly-detection results. The phase-6 contract documents the synthesis outputs; the phase is frozen.",
    docRef: "docs/phase6_contract.md",
  },
];

export function ResearchPage(): JSX.Element {
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [researchSources, setResearchSources] = useState<ResearchSourceSummary[] | null>(null);
  const [researchResults, setResearchResults] = useState<ResearchResultsResponse | null>(null);
  const [researchError, setResearchError] = useState<ApiError | null>(null);
  const [researchLoading, setResearchLoading] = useState(false);

  // PR-09: canonical benchmark state.
  const [benchmarkCatalog, setBenchmarkCatalog] = useState<BenchmarkCatalogResponse | null>(null);
  const [benchmarkError, setBenchmarkError] = useState<ApiError | null>(null);
  const [benchmarkLoading, setBenchmarkLoading] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [experimentDetail, setExperimentDetail] = useState<BenchmarkExperimentDetail | null>(null);
  const [experimentError, setExperimentError] = useState<ApiError | null>(null);
  const [metrics, setMetrics] = useState<BenchmarkMetricsResponse | null>(null);
  const [metricsError, setMetricsError] = useState<ApiError | null>(null);
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [recordInput, setRecordInput] = useState("");
  const [record, setRecord] = useState<BenchmarkRecordResponse | null>(null);
  const [recordError, setRecordError] = useState<ApiError | null>(null);
  const [recordLoading, setRecordLoading] = useState(false);

  // PR-10: Phase 5A evidence state.
  const [phase5aProtocol, setPhase5aProtocol] = useState<Phase5AProtocolResponse | null>(null);
  const [phase5aError, setPhase5aError] = useState<ApiError | null>(null);
  const [phase5aLoading, setPhase5aLoading] = useState(false);
  const [matrixKind, setMatrixKind] = useState<"spearman" | "jaccard">("spearman");
  const [bootstrap, setBootstrap] = useState<Phase5ABootstrapMetricsResponse | null>(null);
  const [paired, setPaired] = useState<Phase5APairedDifferencesResponse | null>(null);
  const [matrix, setMatrix] = useState<Phase5AAgreementMatrixResponse | null>(null);
  const [hypergeom, setHypergeom] = useState<Phase5AHypergeometricResponse | null>(null);
  const [groups, setGroups] = useState<Phase5AAgreementGroupsResponse | null>(null);
  const [thresholds, setThresholds] = useState<Phase5AMultithresholdResponse | null>(null);
  const [discovery, setDiscovery] = useState<Phase5ADiscoveryCurveResponse | null>(null);
  const [discoveryRunId, setDiscoveryRunId] = useState("IF_001");
  const [discoveryPage, setDiscoveryPage] = useState(0);
  const PAGE_SIZE = 100;

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const m = await getMeta(controller.signal);
        setMeta(m);
      } catch (err) {
        if (err instanceof ApiError && err.aborted) return;
        setError(err instanceof ApiError ? err : null);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, []);

  // PR-08: fetch research sources and results on mount.
  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      setResearchLoading(true);
      setResearchError(null);
      try {
        const sourcesResp = await getResearchSources(controller.signal);
        setResearchSources(sourcesResp.items);
        if (sourcesResp.items.length > 0 && sourcesResp.items[0]) {
          const results = await getResearchResults(sourcesResp.items[0].source_id, controller.signal);
          setResearchResults(results);
        }
      } catch (err) {
        if (err instanceof ApiError && err.aborted) return;
        setResearchError(err instanceof ApiError ? err : null);
      } finally {
        if (!controller.signal.aborted) setResearchLoading(false);
      }
    })();
    return () => controller.abort();
  }, []);

  // PR-09: fetch the benchmark catalog on mount (Layer A; works without
  // DVC payloads). Saved metrics are fetched only when the catalog reports
  // the metrics capability as available.
  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      setBenchmarkLoading(true);
      setBenchmarkError(null);
      try {
        const catalog = await getBenchmarkExperiments(controller.signal);
        setBenchmarkCatalog(catalog);
      } catch (err) {
        if (err instanceof ApiError && err.aborted) return;
        setBenchmarkError(err instanceof ApiError ? err : null);
      } finally {
        if (!controller.signal.aborted) setBenchmarkLoading(false);
      }
    })();
    return () => controller.abort();
  }, []);

  // PR-09: fetch the selected experiment's detail.
  useEffect(() => {
    if (!selectedRunId) return;
    const controller = new AbortController();
    (async () => {
      setExperimentError(null);
      setExperimentDetail(null);
      setRecord(null);
      setRecordError(null);
      try {
        const detail = await getBenchmarkExperiment(selectedRunId, controller.signal);
        setExperimentDetail(detail);
      } catch (err) {
        if (err instanceof ApiError && err.aborted) return;
        setExperimentError(err instanceof ApiError ? err : null);
      }
    })();
    return () => controller.abort();
  }, [selectedRunId]);

  // PR-09: fetch saved metrics once when the capability is available.
  useEffect(() => {
    const available = benchmarkCatalog?.capabilities?.metrics?.available;
    if (!available) return;
    const controller = new AbortController();
    (async () => {
      setMetricsLoading(true);
      setMetricsError(null);
      try {
        const resp = await getBenchmarkMetrics(controller.signal);
        setMetrics(resp);
      } catch (err) {
        if (err instanceof ApiError && err.aborted) return;
        setMetricsError(err instanceof ApiError ? err : null);
      } finally {
        if (!controller.signal.aborted) setMetricsLoading(false);
      }
    })();
    return () => controller.abort();
  }, [benchmarkCatalog?.capabilities?.metrics?.available]);

  // PR-10: fetch the Phase 5A protocol (Layer A; always works on a clean checkout).
  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      setPhase5aLoading(true);
      setPhase5aError(null);
      try {
        const p = await getPhase5AProtocol(controller.signal);
        setPhase5aProtocol(p);
      } catch (err) {
        if (err instanceof ApiError && err.aborted) return;
        setPhase5aError(err instanceof ApiError ? err : null);
      } finally {
        if (!controller.signal.aborted) setPhase5aLoading(false);
      }
    })();
    return () => controller.abort();
  }, []);

  // PR-10: fetch a Phase 5A family when its capability becomes available.
  const fetchFamily = async <T,>(
    fetcher: (signal: AbortSignal) => Promise<T>,
    setter: (v: T | null) => void,
    family: string,
  ): Promise<void> => {
    const available = phase5aProtocol?.capabilities?.[family]?.available;
    if (!available) return;
    const controller = new AbortController();
    try {
      const resp = await fetcher(controller.signal);
      setter(resp);
    } catch (err) {
      if (err instanceof ApiError && err.aborted) return;
      setter(null);
    }
  };
  useEffect(() => {
    // Composite routes provide the compact PR-10 API. When one dependent
    // artifact is missing, retain independent fallback to the admitted one.
    if (phase5aProtocol?.capabilities.bootstrap?.available &&
        phase5aProtocol?.capabilities.paired?.available) {
      void getPhase5AUncertainty().then((v) => {
        setBootstrap(v.bootstrap);
        setPaired(v.paired_differences);
      }).catch(() => { setBootstrap(null); setPaired(null); });
    } else {
      void fetchFamily(getPhase5ABootstrap, setBootstrap, "bootstrap");
      void fetchFamily(getPhase5APairedDifferences, setPaired, "paired");
    }
    if (phase5aProtocol?.capabilities.spearman?.available &&
        phase5aProtocol?.capabilities.jaccard?.available) {
      void getPhase5AAgreement().then((v) => {
        setMatrix(matrixKind === "spearman" ? v.spearman : v.jaccard);
      }).catch(() => setMatrix(null));
    } else {
      void fetchFamily((signal) => getPhase5AAgreementMatrix(matrixKind, signal), setMatrix, matrixKind);
    }
    void fetchFamily(getPhase5AOverlapNull, setHypergeom, "hypergeometric");
    void fetchFamily(getPhase5AGroups, setGroups, "groups");
    void fetchFamily(getPhase5AThresholds, setThresholds, "multithreshold");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase5aProtocol, matrixKind]);

  // PR-10: fetch the discovery-curve page (bounded).
  useEffect(() => {
    if (!phase5aProtocol?.capabilities?.discovery?.available) return;
    const controller = new AbortController();
    (async () => {
      try {
        const resp = await getPhase5ADiscoveryCurve(discoveryRunId, {
          limit: PAGE_SIZE,
          offset: discoveryPage * PAGE_SIZE,
          signal: controller.signal,
        });
        setDiscovery(resp);
      } catch (err) {
        if (err instanceof ApiError && err.aborted) return;
        setDiscovery(null);
      }
    })();
    return () => controller.abort();
  }, [phase5aProtocol?.capabilities?.discovery?.available, discoveryRunId, discoveryPage]);

  if (loading && !meta) {
    return <div className="research-page workspace-composition" aria-busy="true"><Loading label="Loading metadata…" /></div>;
  }
  if (error && !meta) {
    return <div className="research-page workspace-composition"><div className="research-page__error"><ErrorPanel error={error} onRetry={() => window.location.reload()} /></div></div>;
  }

  return (
    <div className="research-page workspace-composition">
      <div className="research-page__grid">
        <section className="research-page__methodology" aria-label="Methodology">
          <h2 className="section-h2">Methodology</h2>
          <p className="editorial">
            The MPLAD anomaly-detection research pipeline runs in four
            frozen phases. Each phase is documented under{" "}
            <code className="mono">docs/</code> and its source lives under{" "}
            <code className="mono">src/mplad/</code>. The frontend renders
            stored, manifest-verified evidence only; it does not re-run the
            pipeline.
          </p>
          {METHODOLOGY_PHASES.map((p) => (
            <article key={p.phase} className="research-page__phase">
              <h3 className="section-h3">{p.phase} — {p.title}</h3>
              <p className="editorial-muted">{p.summary}</p>
              <p className="research-page__docref mono">see {p.docRef}</p>
            </article>
          ))}

          <h2 className="section-h2">Reproducibility</h2>
          <dl className="def-list">
            <dt className="def-list__term">Research pipeline</dt>
            <dd className="def-list__def mono">mplad-anomaly-detection/src/mplad (frozen)</dd>
            <dt className="def-list__term">Phase 3–6 tests</dt>
            <dd className="def-list__def mono">tests/test_phase*.py (frozen, green)</dd>
            <dt className="def-list__term">Backend regression suite</dt>
            <dd className="def-list__def mono">{BACKEND_TEST_COUNT} tests</dd>
            <dt className="def-list__term">Backend app version</dt>
            <dd className="def-list__def mono">{meta?.app_version ?? "—"}</dd>
            <dt className="def-list__term">API version</dt>
            <dd className="def-list__def mono">{meta?.api_version ?? "v1"}</dd>
            <dt className="def-list__term">Git commit</dt>
            <dd className="def-list__def mono">{meta?.git_commit_sha ?? "not supplied"}</dd>
          </dl>

          {/* PR-08: Precomputed Research Results */}
          <h2 className="section-h2">Precomputed Research Results</h2>
          <p className="editorial">
            These are <strong>precomputed aggregate reference values</strong> from
            the ULB credit-card fraud benchmark experiment (Stream A). They were
            computed offline by the frozen research pipeline and are served
            read-only through the backend research adapter.{" "}
            <strong>These are not live predictions.</strong> An anomalous
            observation is <strong>not proof of fraud</strong>.
          </p>
          {researchLoading && (
            <Loading label="Loading research results…" />
          )}
          {researchError && !researchResults && (
            <ErrorPanel error={researchError} onRetry={() => window.location.reload()} />
          )}
          {researchResults && (
            <div className="research-page__results">
              <div className="research-page__source-meta">
                <dl className="def-list">
                  <dt className="def-list__term">Dataset</dt>
                  <dd className="def-list__def">{researchResults.dataset_id}</dd>
                  <dt className="def-list__term">Models</dt>
                  <dd className="def-list__def">{researchResults.model_methods.join(", ")}</dd>
                  <dt className="def-list__term">Source artifact</dt>
                  <dd className="def-list__def mono">{researchResults.provenance.artifact_path}</dd>
                  <dt className="def-list__term">Artifact SHA-256</dt>
                  <dd className="def-list__def mono">{researchResults.provenance.artifact_sha256.slice(0, 16)}…</dd>
                  <dt className="def-list__term">Precomputed</dt>
                  <dd className="def-list__def">{researchResults.is_precomputed ? "Yes" : "No"}</dd>
                  <dt className="def-list__term">Live prediction</dt>
                  <dd className="def-list__def">{researchResults.is_live_prediction ? "Yes" : "No"}</dd>
                </dl>
              </div>

              <p className="table-caption">
                Table: Frozen reference values from the canonical experiment
                (30,000-row sample, 47 fraud labels, bottom-1% threshold).
              </p>
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Metric</th>
                    <th scope="col">Value</th>
                    <th scope="col">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {researchResults.results.map((r) => (
                    <tr key={r.metric_name}>
                      <td className="mono">{r.metric_name}</td>
                      <td className="mono">{String(r.value)}</td>
                      <td>{r.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="research-page__caveats">
                <h3 className="section-h3">Interpretation principles</h3>
                <ul className="list-clean">
                  {researchResults.interpretation_principles.map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
                <p className="editorial-muted research-page__caveat">
                  {researchResults.exploratory_caveat}
                </p>
                <h3 className="section-h3">Limitations</h3>
                <ul className="list-clean">
                  {researchResults.limitations.map((l, i) => (
                    <li key={i}>{l}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
          {researchSources && researchSources.length === 0 && !researchError && (
            <p className="editorial-muted">
              No eligible research sources are currently available.
            </p>
          )}

          {/* PR-09: Canonical Benchmark (ten IF/LOF runs) */}
          <h2 className="section-h2">Canonical Benchmark — Ten IF/LOF Runs</h2>
          <p className="editorial">
            The canonical Stream A benchmark comprises ten unsupervised runs:
            five Isolation Forest and five Local Outlier Factor
            configurations, fitted offline on a 30,000-row ULB credit-card
            sample (47 fraud labels, bottom-1% saved flags). Parameters are
            frozen experiment inputs served from the manifest-verified
            configuration; nothing below is recomputed at request time.{" "}
            <strong>Saved metrics and record lookup require the DVC-backed
            evidence payloads; when they are not provisioned the catalog
            still shows the verified configuration.</strong>
          </p>
          {benchmarkLoading && <Loading label="Loading benchmark catalog…" />}
          {benchmarkError && (
            <ErrorPanel error={benchmarkError} onRetry={() => window.location.reload()} />
          )}
          {benchmarkCatalog && (
            <div className="research-page__benchmark">
              <div
                className="research-page__benchmark-run-tabs"
                role="tablist"
                aria-label="Canonical benchmark runs"
              >
                {benchmarkCatalog.experiments.map((e) => (
                  <button
                    key={e.run_id}
                    type="button"
                    role="tab"
                    aria-selected={selectedRunId === e.run_id}
                    className="research-page__benchmark-run-tab"
                    onClick={() => setSelectedRunId(e.run_id)}
                  >
                    {e.run_id}
                  </button>
                ))}
              </div>

              {!selectedRunId && (
                <p className="editorial-muted">
                  Select a run to inspect its frozen configuration and
                  provenance.
                </p>
              )}
              {experimentError && (
                <ErrorPanel error={experimentError} onRetry={() => setSelectedRunId(selectedRunId)} />
              )}
              {experimentDetail && (
                <div className="research-page__benchmark-detail">
                  <h3 className="section-h3">
                    {experimentDetail.run_id} — {experimentDetail.algorithm}
                  </h3>
                  <dl className="def-list">
                    <dt className="def-list__term">Parameters (frozen)</dt>
                    <dd className="def-list__def mono">
                      {Object.entries(experimentDetail.parameters)
                        .map(([k, v]) => `${k}=${String(v)}`)
                        .join(", ")}
                    </dd>
                    <dt className="def-list__term">Fixed pipeline settings</dt>
                    <dd className="def-list__def mono">
                      {Object.keys(experimentDetail.fixed_pipeline_settings).length > 0
                        ? Object.entries(experimentDetail.fixed_pipeline_settings)
                            .map(([k, v]) => `${k}=${String(v)}`)
                            .join(", ")
                        : "—"}
                    </dd>
                    <dt className="def-list__term">Parameter source</dt>
                    <dd className="def-list__def mono">
                      {experimentDetail.parameter_source.path} (SHA-256{" "}
                      {experimentDetail.parameter_source.sha256.slice(0, 16)}…)
                    </dd>
                    <dt className="def-list__term">Dataset scope</dt>
                    <dd className="def-list__def">
                      30,000-row sample, {String(experimentDetail.dataset_scope.sample.fraud_count)} fraud labels,{" "}
                      {experimentDetail.dataset_scope.threshold_rule}
                    </dd>
                    <dt className="def-list__term">Score direction</dt>
                    <dd className="def-list__def">
                      {String(experimentDetail.dataset_scope.score_orientation.native_score ?? "")}{" "}
                      anomaly_score = −native_score (higher = more anomalous).
                    </dd>
                    <dt className="def-list__term">Run status</dt>
                    <dd className="def-list__def">
                      Fitted offline by the frozen pipeline; no refitting at request time.
                    </dd>
                  </dl>

                  <h4 className="section-h3">Saved metrics (Phase 4 evaluation)</h4>
                  {metricsLoading && <Loading label="Loading saved metrics…" />}
                  {metricsError && (
                    <div className="research-page__benchmark-unavailable">
                      <p className="editorial-muted">
                        Saved metrics are currently unavailable
                        {metricsError.details && typeof metricsError.details.reason === "string"
                          ? ` (reason: ${metricsError.details.reason})`
                          : ""}.
                        The verified configuration above remains available.
                      </p>
                    </div>
                  )}
                  {!metrics && !metricsError && !metricsLoading && (
                    <div className="research-page__benchmark-unavailable">
                      <p className="editorial-muted">
                        The DVC-backed metrics payload has not been
                        provisioned in this deployment, so saved metrics are
                        not shown. This is a deliberate unavailable state —
                        no synthetic or substitute values are displayed.
                      </p>
                    </div>
                  )}
                  {metrics && (
                    <>
                      <p className="table-caption">
                        Table: saved Phase 4 metrics per run (exact stored
                        values; ranking metrics use anomaly_score, threshold
                        metrics use saved bottom-1% flags; denominators are
                        listed below the table).
                      </p>
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th scope="col">Run</th>
                            <th scope="col">AP</th>
                            <th scope="col">ROC-AUC</th>
                            <th scope="col">P@1%</th>
                            <th scope="col">R@1%</th>
                            <th scope="col">F1@1%</th>
                            <th scope="col">TP / FP</th>
                            <th scope="col">Flags</th>
                          </tr>
                        </thead>
                        <tbody>
                          {metrics.metrics.map((m) => (
                            <tr
                              key={m.run_id}
                              className={m.run_id === selectedRunId ? "is-selected" : undefined}
                            >
                              <td className="mono">{m.run_id}</td>
                              <td className="mono">{m.average_precision.toFixed(4)}</td>
                              <td className="mono">{m.roc_auc.toFixed(4)}</td>
                              <td className="mono">{m.precision_at_1pct.toFixed(4)}</td>
                              <td className="mono">{m.recall_at_1pct.toFixed(4)}</td>
                              <td className="mono">{m.f1_at_1pct.toFixed(4)}</td>
                              <td className="mono">{m.tp} / {m.fp}</td>
                              <td className="mono">{m.flagged_count}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <p className="research-page__metric-defs">
                        {metrics.metric_definitions
                          .map((d) => `${d.metric_name}: ${d.definition} (denominator: ${d.denominator})`)
                          .join(" · ")}
                      </p>
                    </>
                  )}

                  <h4 className="section-h3">Canonical record lookup (by row_id)</h4>
                  {experimentDetail.row_lookup_available ? (
                    <form
                      className="research-page__record-lookup"
                      onSubmit={(ev) => {
                        ev.preventDefault();
                        const parsed = Number.parseInt(recordInput, 10);
                        if (!Number.isInteger(parsed) || parsed < 0) {
                          setRecord(null);
                          setRecordError(null);
                          return;
                        }
                        const controller = new AbortController();
                        (async () => {
                          setRecordLoading(true);
                          setRecordError(null);
                          try {
                            const resp = await getBenchmarkRecord(selectedRunId!, parsed, controller.signal);
                            setRecord(resp);
                          } catch (err) {
                            if (err instanceof ApiError && err.aborted) return;
                            setRecord(null);
                            setRecordError(err instanceof ApiError ? err : null);
                          } finally {
                            setRecordLoading(false);
                          }
                        })();
                      }}
                    >
                      <div className="research-page__record-form">
                        <label className="def-list__term" htmlFor="benchmark-row-id">
                          ULB row_id
                        </label>
                        <input
                          id="benchmark-row-id"
                          className="research-page__record-input"
                          type="text"
                          inputMode="numeric"
                          pattern="[0-9]*"
                          value={recordInput}
                          onChange={(ev) => setRecordInput(ev.target.value)}
                          placeholder="e.g. 12345"
                        />
                        <button type="submit">Look up</button>
                      </div>
                      {recordLoading && <Loading label="Looking up record…" />}
                      {recordError && <ErrorPanel error={recordError} onRetry={() => setRecordInput(recordInput)} />}
                      {record && (
                        <table className="data-table">
                          <caption className="table-caption">
                            Saved record for {record.run_id} / row_id {record.row_id}
                          </caption>
                          <thead>
                            <tr>
                              <th scope="col">Field</th>
                              <th scope="col">Value</th>
                              <th scope="col">Meaning</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr>
                              <td className="mono">Class</td>
                              <td className="mono">{record.label.Class}</td>
                              <td>Ground-truth evaluation label (not the detector flag)</td>
                            </tr>
                            <tr>
                              <td className="mono">native_score</td>
                              <td className="mono">{record.scores.native_score.toFixed(6)}</td>
                              <td>{record.scores.native_definition}</td>
                            </tr>
                            <tr>
                              <td className="mono">anomaly_score</td>
                              <td className="mono">{record.scores.anomaly_score.toFixed(6)}</td>
                              <td>{record.scores.anomaly_definition}</td>
                            </tr>
                            <tr>
                              <td className="mono">flag</td>
                              <td className="mono">{record.flag.value}</td>
                              <td>{record.flag.provenance}</td>
                            </tr>
                          </tbody>
                        </table>
                      )}
                    </form>
                  ) : (
                    <div className="research-page__benchmark-unavailable">
                      <p className="editorial-muted">
                        The DVC-backed evaluation dataset has not been
                        provisioned in this deployment, so the canonical
                        record lookup is unavailable. No substitute or
                        synthetic records are shown.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* PR-10: Phase 5A Uncertainty, Agreement & Review-Policy Evidence */}
          <h2 className="section-h2">Phase 5A Evidence — Uncertainty, Agreement, Review Policies</h2>
          <p className="editorial">
            The frozen Phase 5A layer reports saved bootstrap uncertainty, pairwise
            rank/flag agreement, a hypergeometric overlap null, four-way agreement
            groups, four review policies, multi-threshold sensitivity and a
            fraud-discovery curve for the ULB 30,000-row benchmark.{" "}
            <strong>IF_003, IF_004, LOF_004 and the IF_003/LOF_004 pair were
            selected post-hoc</strong>; comparisons are exploratory, not
            confirmatory. A confidence interval is not a calibrated probability
            of wrongdoing; a hypergeometric p-value describes the stated overlap
            null only. Saved DVC payloads are absent in this deployment, so each
            family shows an explicit unavailable state — no synthetic values.
          </p>
          {phase5aLoading && <Loading label="Loading Phase 5A protocol…" />}
          {phase5aError && (
            <ErrorPanel error={phase5aError} onRetry={() => window.location.reload()} />
          )}
          {phase5aProtocol && (
            <div className="research-page__phase5a">
              <div className="research-page__phase5a-family">
                <h3 className="section-h3">Verified protocol</h3>
                <dl className="def-list">
                  <dt className="def-list__term">Phase / stream / layer</dt>
                  <dd className="def-list__def mono">
                    {phase5aProtocol.phase} / {phase5aProtocol.stream} / {phase5aProtocol.layer}
                  </dd>
                  <dt className="def-list__term">Models fitted</dt>
                  <dd className="def-list__def">{phase5aProtocol.models_fitted} (analysis-only)</dd>
                  <dt className="def-list__term">Bootstrap</dt>
                  <dd className="def-list__def mono">
                    {String(phase5aProtocol.bootstrap_protocol?.n_replicates ?? 2000)} replicates ·{" "}
                    CI {String(phase5aProtocol.bootstrap_protocol?.ci_level ?? 0.95)} ·{" "}
                    {String(phase5aProtocol.bootstrap_protocol?.ci_method ?? "percentile")} · seed{" "}
                    {String(phase5aProtocol.bootstrap_protocol?.seed ?? 42)}
                  </dd>
                  <dt className="def-list__term">Paired comparison</dt>
                  <dd className="def-list__def mono">
                    {String(phase5aProtocol.paired_comparison?.definition ?? "LOF_004 - IF_003")}
                    {" "}
                    (direction frozen; never inverted)
                  </dd>
                  <dt className="def-list__term">Sample</dt>
                  <dd className="def-list__def">
                    {String(phase5aProtocol.sample?.sample_size ?? 30000)} rows ·{" "}
                    {String(phase5aProtocol.sample?.fraud_count ?? 47)} fraud labels
                  </dd>
                </dl>
                <p className="research-page__phase5a-caution">
                  {phase5aProtocol.selection_caveat}
                </p>
                <table className="data-table">
                  <caption className="table-caption">Per-family availability (DVC-backed)</caption>
                  <thead>
                    <tr><th scope="col">Family</th><th scope="col">Available</th><th scope="col">Reason</th></tr>
                  </thead>
                  <tbody>
                    {Object.entries(phase5aProtocol.capabilities).map(([fam, cap]) => (
                      <tr key={fam}>
                        <td className="mono">{fam}</td>
                        <td>{cap.available ? "yes" : "no"}</td>
                        <td className="mono">{cap.reason ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Bootstrap uncertainty */}
              <div className="research-page__phase5a-family">
                <h3 className="section-h3">Bootstrap uncertainty</h3>
                {bootstrap ? (
                  <>
                    <table className="data-table">
                      <thead>
                        <tr><th scope="col">Run</th><th scope="col">Metric</th><th scope="col">Point</th><th scope="col">CI lower</th><th scope="col">CI upper</th><th scope="col">Replicates</th></tr>
                      </thead>
                      <tbody>
                        {bootstrap.metrics.map((m) => (
                          <tr key={`${m.run_id}-${m.metric}`}>
                            <td className="mono">{m.run_id}</td><td className="mono">{m.metric}</td>
                            <td className="mono">{m.point_estimate.toFixed(4)}</td>
                            <td className="mono">{m.ci_lower.toFixed(4)}</td>
                            <td className="mono">{m.ci_upper.toFixed(4)}</td>
                            <td className="mono">{m.n_replicates}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p className="research-page__phase5a-caution">
                      Intervals are NOT calibrated fraud probabilities; overlapping/non-overlapping intervals do not by themselves establish significance.
                    </p>
                  </>
                ) : (
                  <p className="research-page__phase5a-unavailable">
                    The DVC-backed bootstrap payload has not been provisioned in this deployment; saved bootstrap intervals are unavailable.
                  </p>
                )}
              </div>

              {/* Paired differences */}
              <div className="research-page__phase5a-family">
                <h3 className="section-h3">Paired bootstrap differences (LOF_004 − IF_003)</h3>
                {paired ? (
                  <table className="data-table">
                    <thead>
                      <tr><th scope="col">Metric</th><th scope="col">Point Δ</th><th scope="col">CI lower</th><th scope="col">CI upper</th></tr>
                    </thead>
                    <tbody>
                      {paired.differences.map((d) => (
                        <tr key={d.metric}>
                          <td className="mono">{d.metric}</td>
                          <td className="mono">{d.point_estimate.toFixed(4)}</td>
                          <td className="mono">{d.ci_lower.toFixed(4)}</td>
                          <td className="mono">{d.ci_upper.toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="research-page__phase5a-unavailable">
                    The paired-differences payload is unavailable; no paired comparison is shown.
                  </p>
                )}
              </div>

              {/* Agreement matrices */}
              <div className="research-page__phase5a-family">
                <h3 className="section-h3">Pairwise agreement matrix</h3>
                <div className="research-page__phase5a-matrix-tabs" role="tablist" aria-label="Agreement matrix kind">
                  {(["spearman", "jaccard"] as const).map((k) => (
                    <button
                      key={k}
                      type="button"
                      role="tab"
                      aria-selected={matrixKind === k}
                      className="research-page__phase5a-matrix-tab"
                      onClick={() => setMatrixKind(k)}
                    >
                      {k === "spearman" ? "Spearman rank" : "Jaccard 1%"}
                    </button>
                  ))}
                </div>
                {matrix ? (
                  <>
                    <table className="data-table">
                      <caption className="table-caption">{matrix.definition}</caption>
                      <thead>
                        <tr><th scope="col">run_id</th>{matrix.run_labels.map((r) => (<th key={r} scope="col" className="mono">{r}</th>))}</tr>
                      </thead>
                      <tbody>
                        {matrix.matrix.map((row) => (
                          <tr key={row.run_id}>
                            <td className="mono">{row.run_id}</td>
                            {matrix.run_labels.map((col) => (
                              <td key={col} className="mono">{(row.values[col] ?? 0).toFixed(3)}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p className="research-page__phase5a-caution">
                      {matrix.kind === "spearman"
                        ? "Rank agreement ≠ fraud-detection correctness."
                        : "Flag overlap ≠ rank agreement and ≠ labelled recovery."}
                    </p>
                  </>
                ) : (
                  <p className="research-page__phase5a-unavailable">
                    The {matrixKind} matrix payload is unavailable.
                  </p>
                )}
              </div>

              {/* Hypergeometric */}
              <div className="research-page__phase5a-family">
                <h3 className="section-h3">Hypergeometric overlap (IF_003 vs LOF_004, 1%)</h3>
                {hypergeom ? (
                  <dl className="def-list">
                    <dt className="def-list__term">Observed / expected</dt>
                    <dd className="def-list__def mono">
                      {hypergeom.observed_intersection} / {hypergeom.expected_intersection.toFixed(2)}
                      {" "}(enrichment {hypergeom.enrichment_observed_over_expected.toFixed(2)}×)
                    </dd>
                    <dt className="def-list__term">log_survival / log10_survival</dt>
                    <dd className="def-list__def mono">
                      {hypergeom.log_survival.toFixed(4)} / {hypergeom.log10_survival.toFixed(4)}
                      {" "}(preserved; not exponentiated)
                    </dd>
                    <dt className="def-list__term">Null model</dt>
                    <dd className="def-list__def">{hypergeom.null_model}</dd>
                  </dl>
                ) : (
                  <p className="research-page__phase5a-unavailable">
                    The hypergeometric-overlap payload is unavailable.
                  </p>
                )}
                <p className="research-page__phase5a-caution">
                  The p-value describes the stated overlap null only — not the probability that flagged records are fraudulent or that any detector is correct.
                </p>
              </div>

              {/* Review policies */}
              <div className="research-page__phase5a-family">
                <h3 className="section-h3">Review policies (unequal review costs)</h3>
                {groups && (
                  <table className="data-table">
                    <caption className="table-caption">Four-way agreement groups (IF_003 vs LOF_004, 1%)</caption>
                    <thead>
                      <tr><th scope="col">Group</th><th scope="col">Observations</th><th scope="col">Fraud</th><th scope="col">Recall contribution</th></tr>
                    </thead>
                    <tbody>
                      {groups.groups.map((g) => (
                        <tr key={g.group}>
                          <td className="mono">{g.group}</td>
                          <td className="mono">{g.observation_count}</td>
                          <td className="mono">{g.fraud_count}</td>
                          <td className="mono">{g.recall_contribution.toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                <p className="research-page__phase5a-caution">
                  Only saved disjoint agreement groups are displayed. Counts,
                  fraud proportions and recall contributions come directly from
                  frozen Phase 5A records; no new per-policy precision, recall
                  or overlap ratios are calculated during API requests.
                </p>
              </div>

              {/* Multi-threshold sensitivity */}
              <div className="research-page__phase5a-family">
                <h3 className="section-h3">Multi-threshold sensitivity</h3>
                {thresholds ? (
                  <table className="data-table">
                    <thead>
                      <tr><th scope="col">Threshold %</th><th scope="col">k</th><th scope="col">Source</th><th scope="col">Canonical</th><th scope="col">n_methods</th></tr>
                    </thead>
                    <tbody>
                      {thresholds.thresholds.map((t) => (
                        <tr key={t.threshold_pct}>
                          <td className="mono">{t.threshold_pct}%</td>
                          <td className="mono">{t.k_nominal}</td>
                          <td className="mono">{t.selection_source}</td>
                          <td>{t.is_canonical ? "yes" : "no"}</td>
                          <td className="mono">{t.n_methods}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="research-page__phase5a-unavailable">
                    The multi-threshold payload is unavailable.
                  </p>
                )}
              </div>

              {/* Discovery curve (bounded) */}
              <div className="research-page__phase5a-family">
                <h3 className="section-h3">Fraud-discovery curve (bounded)</h3>
                {phase5aProtocol.capabilities.discovery?.available ? (
                  <>
                    <div className="research-page__record-form">
                      <label className="def-list__term" htmlFor="phase5a-discovery-run">Run</label>
                      <select
                        id="phase5a-discovery-run"
                        className="research-page__record-input"
                        value={discoveryRunId}
                        onChange={(e) => { setDiscoveryRunId(e.target.value); setDiscoveryPage(0); }}
                      >
                        {["IF_001","IF_002","IF_003","IF_004","IF_005","LOF_001","LOF_002","LOF_003","LOF_004","LOF_005"].map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                      <button type="button" disabled={discoveryPage === 0} onClick={() => setDiscoveryPage((p) => Math.max(0, p - 1))}>Prev</button>
                      <button type="button" disabled={!discovery?.has_more} onClick={() => setDiscoveryPage((p) => p + 1)}>Next</button>
                      <span className="editorial-muted">
                        page {discoveryPage + 1} · {discovery ? `${discovery.offset}–${discovery.offset + discovery.rows.length} of ${discovery.total}` : "…"}
                      </span>
                    </div>
                    {discovery && (
                      <table className="data-table">
                        <thead>
                          <tr><th scope="col">Budget</th><th scope="col">Fraud found</th><th scope="col">Precision</th><th scope="col">Recall</th></tr>
                        </thead>
                        <tbody>
                          {discovery.rows.map((r, i) => (
                            <tr key={`${r.budget}-${i}`}>
                              <td className="mono">{String(r.budget)}</td>
                              <td className="mono">{r.fraud_found}</td>
                              <td className="mono">{r.precision.toFixed(4)}</td>
                              <td className="mono">{r.recall.toFixed(4)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </>
                ) : (
                  <p className="research-page__phase5a-unavailable">
                    The discovery-curve payload has not been provisioned; the bounded viewer is unavailable.
                  </p>
                )}
              </div>
            </div>
          )}
        </section>

        <aside className="research-page__sidebar" aria-label="Artifacts, limitations, cautions">
          <section className="research-page__sidebar-section panel">
            <div className="panel__header">
              <span className="panel__title">Artifact index</span>
            </div>
            <div className="panel__body panel__body--flush">
              <p className="table-caption">Table 5. Frozen research artifacts (SHA-256 prefix).</p>
              <table className="data-table">
                <thead>
                  <tr><th scope="col">Path</th><th scope="col">SHA-256</th></tr>
                </thead>
                <tbody>
                  {FROZEN_ARTIFACTS.map((a) => (
                    <tr key={a.path}>
                      <td className="mono">{a.path}</td>
                      <td className="mono">{a.sha256}…</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="research-page__sidebar-section">
            <h3 className="section-h3">Limitations</h3>
            <ul className="list-clean">
              <li>No live dataset integration. Precomputed results are served read-only from frozen artifacts.</li>
              <li>No live model inference. Isolation Forest, LOF and PCA are not executed at runtime.</li>
              <li>No automatic research-to-case linking. Scientific results and review cases remain separate.</li>
              <li>No deployment automation for research artifacts in containers. See PR07B_COMPOSE_RUNBOOK.md.</li>
              <li>ULB benchmark results must not be assumed to transfer to MPLAD transactions.</li>
            </ul>
          </section>

          <section className="research-page__sidebar-section">
            <h3 className="section-h3">Scientific cautions</h3>
            <ul className="list-clean">
              <li>An anomaly flag is statistical, not legal. It never implies fraud or misconduct.</li>
              <li>Cross-domain numeric comparison is methodologically unsound; each dataset has distinct units and semantics.</li>
              <li>Research results are manifest-verified, not live. They reflect the frozen pipeline state.</li>
            </ul>
          </section>
        </aside>
      </div>
    </div>
  );
}
