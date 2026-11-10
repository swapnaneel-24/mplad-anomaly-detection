// Overview — Research Index.
// Per SCREEN_DESIGN_NOTES.md §3. Asymmetric editorial composition with a
// research workflow map, research streams, verified status, subsystem
// table, and workspace entry points.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getHealthLive, getHealthReady, getMeta } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import type {
  HealthLiveResponse,
  MetaResponse,
  ReadinessResponse,
} from "@/api/contracts";
import { Loading } from "@/components/Loading";
import { ErrorPanel } from "@/components/ErrorPanel";
import { StatusPill } from "@/components/StatusPill";
import { WORKSPACES } from "@/layout/workspaces";
import "@/pages/OverviewPage.css";

interface OverviewData {
  meta: MetaResponse;
  live: HealthLiveResponse;
  ready: ReadinessResponse;
}

export function OverviewPage(): JSX.Element {
  const [data, setData] = useState<OverviewData | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [meta, live, ready] = await Promise.all([
          getMeta(controller.signal),
          getHealthLive(controller.signal),
          getHealthReady(controller.signal),
        ]);
        setData({ meta, live, ready });
      } catch (err) {
        if (err instanceof ApiError && err.aborted) return;
        setError(err instanceof ApiError ? err : null);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, []);

  if (loading && !data) {
    return <div className="overview overview--loading" aria-busy="true"><Loading label="Loading system status…" /></div>;
  }
  if (error && !data) {
    return <div className="overview"><ErrorPanel error={error} onRetry={() => window.location.reload()} /></div>;
  }
  if (!data) {
    return <div className="overview" aria-busy="true"><Loading /></div>;
  }

  const { meta, live, ready } = data;
  const implementedFeatures = Object.entries(meta.features).filter(([, v]) => v === "implemented");
  const plannedFeatures = Object.entries(meta.features).filter(([, v]) => v === "planned");

  return (
    <div className="overview workspace-composition" aria-busy={loading ? "true" : "false"}>
      <div className="overview__scroll">
        <header className="overview__heading">
          <h2 className="overview__study-title">MPLAD Fund-Utilisation Anomaly Pattern Detection</h2>
          <p className="overview__study-subtitle editorial">Using Unsupervised Learning</p>
        </header>

        <section className="overview__problem">
          <p className="editorial">
            PEIARS — the Public Expenditure &amp; Infrastructure Anomaly Review
            System — surfaces statistical anomalies in public-development
            datasets for human review. The research pipeline is frozen; its
            results are manifest-verified. The frontend renders stored
            evidence only and never recomputes thresholds or refits models.
          </p>
          <p className="editorial-muted">
            An anomaly flag is a prompt for examination, not a conclusion.
            Every analytical finding carries the boundaries of its method,
            its data and its assumptions.
          </p>
        </section>

        <section className="overview__workflow-map" aria-label="Research workflow map">
          <div className="workflow-map__phase">
            <span className="workflow-map__label mono">Phase 3 · feature engineering</span>
            <span className="workflow-map__state mono">frozen · tests green</span>
          </div>
          <span className="workflow-map__arrow" aria-hidden="true">→</span>
          <div className="workflow-map__phase">
            <span className="workflow-map__label mono">Phase 4 · model fitting</span>
            <span className="workflow-map__state mono">frozen · tests green</span>
          </div>
          <span className="workflow-map__arrow" aria-hidden="true">→</span>
          <div className="workflow-map__phase">
            <span className="workflow-map__label mono">Phase 5 · analysis</span>
            <span className="workflow-map__state mono">frozen · tests green</span>
          </div>
          <span className="workflow-map__arrow" aria-hidden="true">→</span>
          <div className="workflow-map__phase">
            <span className="workflow-map__label mono">Phase 6 · synthesis</span>
            <span className="workflow-map__state mono">frozen · tests green</span>
          </div>
        </section>

        <section className="overview__streams">
          <article className="overview__stream">
            <h3 className="section-h3">Stream A — ULB benchmark</h3>
            <p className="editorial-muted">
              Verified benchmark dataset. Primary unit of analysis for
              Phase 3–5 of the research pipeline. Anomaly detection via
              Isolation Forest and Local Outlier Factor.
            </p>
          </article>
          <article className="overview__stream">
            <h3 className="section-h3">Stream B — Cross-domain feasibility</h3>
            <p className="editorial-muted">
              Exploratory assessment of PMGSY road-connectivity and MPLADS
              fund-utilisation records. Not yet integrated; cross-domain
              synthesis is a research question, not a UI affordance.
            </p>
          </article>
        </section>

        <section className="overview__section">
          <h3 className="section-h2">Application status</h3>
          <dl className="def-list">
            <dt className="def-list__term">Application</dt>
            <dd className="def-list__def mono">{meta.application}</dd>
            <dt className="def-list__term">API version</dt>
            <dd className="def-list__def mono">{meta.app_version}</dd>
            <dt className="def-list__term">Git commit</dt>
            <dd className="def-list__def mono">{meta.git_commit_sha ?? "not supplied"}</dd>
            <dt className="def-list__term">Environment</dt>
            <dd className="def-list__def mono">{meta.environment}</dd>
            <dt className="def-list__term">Liveness</dt>
            <dd className="def-list__def">
              <StatusPill status={live.status === "alive" ? "ready" : "unknown"} label="Alive" />
            </dd>
            <dt className="def-list__term">Readiness</dt>
            <dd className="def-list__def">
              <StatusPill status="ready" label="Ready" />
              {ready.checks.length > 0 && (
                <span className="overview__checks">
                  {ready.checks.map((c) => (
                    <span key={c.name} className="overview__check mono">
                      {c.name}: {c.status}
                    </span>
                  ))}
                </span>
              )}
            </dd>
          </dl>
        </section>

        <section className="overview__section">
          <h3 className="section-h2">Subsystem availability</h3>
          <p className="table-caption">Table 1. Subsystem state as reported by /api/v1/meta.</p>
          <table className="data-table">
            <thead>
              <tr><th scope="col">Subsystem</th><th scope="col">State</th></tr>
            </thead>
            <tbody>
              {Object.entries(meta.subsystems).map(([name, state]) => (
                <tr key={name}>
                  <td className="mono">{name}</td>
                  <td>
                    <StatusPill
                      status={state === "available" ? "ready" : state === "empty" ? "unknown" : "not_ready"}
                      label={state}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="overview__section">
          <h3 className="section-h2">Workspaces</h3>
          <div className="overview__entry-grid">
            {WORKSPACES.map((ws) => (
              <Link key={ws.path} to={ws.path} className="overview__entry">
                <span className="overview__entry-number mono">{ws.number}</span>
                <span className="overview__entry-title">{ws.shortTitle}</span>
                <span className="overview__entry-purpose">
                  {WORKSPACE_PURPOSES[ws.path] ?? ""}
                </span>
              </Link>
            ))}
          </div>
        </section>

        <section className="overview__section overview__capabilities">
          <div>
            <h3 className="section-h3">Implemented capabilities</h3>
            <ul className="list-clean">
              {implementedFeatures.map(([key]) => (
                <li key={key}><span className="mono">{key}</span></li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="section-h3">Deferred capabilities</h3>
            <ul className="list-clean">
              {plannedFeatures.map(([key]) => (
                <li key={key}><span className="mono">{key}</span></li>
              ))}
            </ul>
          </div>
        </section>
      </div>
    </div>
  );
}

const WORKSPACE_PURPOSES: Record<string, string> = {
  "/overview": "Scientific purpose, dataset and application context.",
  "/data": "Dataset exploration and provenance.",
  "/analysis": "Model behavior, comparisons, exploratory analysis.",
  "/investigations": "Human review and case management.",
  "/domains": "ULB, PMGSY and MPLADS distinctions and feasibility.",
  "/research": "Methods, reproducibility, limitations and artifacts.",
};
