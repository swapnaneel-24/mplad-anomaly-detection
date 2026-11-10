// Research & Provenance — Reproducibility Workspace.
// Per SCREEN_DESIGN_NOTES.md §8. Two-column grid:
//   left (1fr):   methodological sections (Phase 3–6) + reproducibility
//   right (320px): artifact index + limitations + cautions (sticky)

import { useEffect, useState } from "react";
import { getMeta } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import type { MetaResponse } from "@/api/contracts";
import { Loading } from "@/components/Loading";
import { ErrorPanel } from "@/components/ErrorPanel";
import "@/pages/ResearchPage.css";

const FROZEN_ARTIFACTS: { path: string; sha256: string }[] = [
  { path: "docs/MPLAD_framework_pipeline.md", sha256: "7d5ad8dabe038c0a" },
  { path: "docs/PHASE3_MIGRATION_GUIDE.md", sha256: "2faf31f099539192" },
  { path: "docs/Phase-0.md", sha256: "3f00ce99a8a5e6e6" },
  { path: "docs/feature_space_manifest.md", sha256: "7606b973c402b53a" },
  { path: "docs/phase4_contract.md", sha256: "791e3b7fd26b886b" },
  { path: "docs/phase5_figure_catalog.md", sha256: "153aa65dfec29777" },
  { path: "docs/phase6_contract.md", sha256: "d1f17d7d0bd2d3ff" },
  { path: "docs/phase7_synthesis.md", sha256: "1030bb312a11b927" },
  { path: "docs/provenance_log.md", sha256: "65557c160cfbdddf" },
  { path: "src/mplad/__init__.py", sha256: "c607b4112c5bfb37" },
  { path: "src/mplad/stream_a/phase3.py", sha256: "c32a335fb2c61e39" },
  { path: "src/mplad/stream_a/phase4.py", sha256: "81cf5c9e357afde6" },
  { path: "src/mplad/stream_a/phase5_analysis.py", sha256: "9fcfd316f13b9fca" },
  { path: "src/mplad/stream_a/phase5_plots.py", sha256: "c036994420584c4c" },
  { path: "src/mplad/stream_a/phase6.py", sha256: "e487bb5b6944dbdc" },
  { path: "tests/test_phase3.py", sha256: "56a0e461ca931a4f" },
  { path: "tests/test_phase4.py", sha256: "94e2018957a131cb" },
  { path: "tests/test_phase5_analysis.py", sha256: "469681ef14b7b564" },
  { path: "tests/test_phase5_plots.py", sha256: "69259b12485d87c0" },
  { path: "tests/test_phase6.py", sha256: "d669b180229ce7cb" },
];

const BACKEND_TEST_COUNT = 445;

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
              <li>No live dataset integration. The source registry is empty.</li>
              <li>No public case API. Review-case reading and writing are deferred to PR-05B.</li>
              <li>No research-evidence service. Phase 3–6 figures are not yet exposed through the API.</li>
              <li>No deployment automation. Docker Compose and CI/CD are deferred to PR-06.</li>
              <li>No administrator-management UI. The bootstrap CLI is the only provisioning path.</li>
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
