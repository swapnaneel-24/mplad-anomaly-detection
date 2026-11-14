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

import { useEffect, useState } from "react";
import {
  getMeta,
  getResearchSources,
  getResearchResults,
  getBenchmarkExperiments,
  getBenchmarkExperiment,
  getBenchmarkMetrics,
  getBenchmarkRecord,
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
