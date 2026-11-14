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

import { useEffect, useState } from "react";
import { getMeta, getResearchSources, getResearchResults } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import type { MetaResponse, ResearchSourceSummary, ResearchResultsResponse } from "@/api/contracts";
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
