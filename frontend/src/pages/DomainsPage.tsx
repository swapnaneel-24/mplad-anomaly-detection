// Cross-Domain Study — Comparative Research Workspace.
// Per SCREEN_DESIGN_NOTES.md §7. Comparison axis strip + three-column
// structured domain panels + full-width comparability matrix table.

import { useEffect, useState } from "react";
import { listSources, getMeta } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import type { DatasetKind, MetaResponse, SourceListResponse } from "@/api/contracts";
import { Loading } from "@/components/Loading";
import { ErrorPanel } from "@/components/ErrorPanel";
import "@/pages/DomainsPage.css";

interface DomainColumn {
  kind: DatasetKind;
  name: string;
  methodologicalStatus: string;
  limitations: string[];
  pipelinePhase: string;
}

const DOMAINS: DomainColumn[] = [
  {
    kind: "ulb_benchmark",
    name: "ULB benchmark",
    methodologicalStatus:
      "Verified benchmark dataset. Primary unit of analysis for Phase 3–5 of the research pipeline. Anomaly detection via Isolation Forest and Local Outlier Factor.",
    limitations: [
      "Single-year snapshot; longitudinal analysis not yet integrated.",
      "Feature engineering assumes the published ULB schema.",
    ],
    pipelinePhase: "Phase 3–5 (frozen)",
  },
  {
    kind: "pmgsy_infrastructure",
    name: "PMGSY infrastructure",
    methodologicalStatus:
      "Exploratory. Road connectivity records are not yet integrated. Future work would require distinct feature engineering for spatial coverage.",
    limitations: [
      "No registered sources; integrity not verified.",
      "Spatial coverage semantics differ from ULB financial features.",
    ],
    pipelinePhase: "not integrated",
  },
  {
    kind: "mplads_administration",
    name: "MPLADS administration",
    methodologicalStatus:
      "Exploratory. Fund-utilisation records are not yet integrated. The academic title targets this dataset; integration is a future milestone.",
    limitations: [
      "No registered sources; integrity not verified.",
      "Fund-release semantics differ from ULB expenditure features.",
    ],
    pipelinePhase: "not integrated",
  },
];

const COMPARABILITY_ROWS: { dimension: string; ulb: string; pmgsy: string; mplads: string }[] = [
  { dimension: "Unit of analysis", ulb: "Urban local body", pmgsy: "Road reach", mplads: "Fund release" },
  { dimension: "Coverage", ulb: "National (cities)", pmgsy: "Rural roads", mplads: "Constituency" },
  { dimension: "Anomaly semantics", ulb: "Expenditure deviation", pmgsy: "Connectivity deficit", mplads: "Utilisation gap" },
  { dimension: "Feature comparability", ulb: "Financial ratios", pmgsy: "Spatial features", mplads: "Temporal features" },
  { dimension: "Transfer constraints", ulb: "Schema-specific", pmgsy: "Requires re-engineering", mplads: "Requires re-engineering" },
];

export function DomainsPage(): JSX.Element {
  const [sources, setSources] = useState<SourceListResponse | null>(null);
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [srcs, m] = await Promise.all([
          listSources({ signal: controller.signal }),
          getMeta(controller.signal),
        ]);
        setSources(srcs);
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

  if (loading && !sources) {
    return <div className="domains-page workspace-composition" aria-busy="true"><Loading label="Loading domains…" /></div>;
  }
  if (error && !sources) {
    return <div className="domains-page workspace-composition"><div className="domains-page__error"><ErrorPanel error={error} onRetry={() => window.location.reload()} /></div></div>;
  }

  return (
    <div className="domains-page workspace-composition">
      <div className="domains-page__scroll">
        <section className="domains-page__axis" aria-label="Comparison axis">
          {DOMAINS.map((d) => (
            <div key={d.kind} className="domains-page__axis-cell">
              <span className="domains-page__axis-name">{d.name}</span>
              <span className="domains-page__axis-slug mono">{d.kind}</span>
            </div>
          ))}
        </section>

        <section className="domains-page__columns" aria-label="Domain comparison">
          {DOMAINS.map((d) => {
            const count = sources?.sources.filter((s) => s.dataset_kind === d.kind).length ?? 0;
            const subsystemKey = `${d.kind}_data_observatory`;
            const subsystemState = meta?.subsystems[subsystemKey] ?? "not_integrated";
            return (
              <article key={d.kind} className="domain-card">
                <h3 className="domain-card__title">{d.name}</h3>
                <dl className="def-list">
                  <dt className="def-list__term">Dataset kind</dt>
                  <dd className="def-list__def mono">{d.kind}</dd>
                  <dt className="def-list__term">Registered sources</dt>
                  <dd className="def-list__def mono numeric">{count}</dd>
                  <dt className="def-list__term">Subsystem state</dt>
                  <dd className="def-list__def mono">{subsystemState}</dd>
                  <dt className="def-list__term">Pipeline phase</dt>
                  <dd className="def-list__def mono">{d.pipelinePhase}</dd>
                </dl>
                <h4 className="section-h4">Methodological status</h4>
                <p className="editorial-muted">{d.methodologicalStatus}</p>
                <h4 className="section-h4">Known limitations</h4>
                <ul className="list-clean">
                  {d.limitations.map((l) => <li key={l}>{l}</li>)}
                </ul>
              </article>
            );
          })}
        </section>

        <section className="domains-page__matrix">
          <h3 className="section-h3">Comparability matrix</h3>
          <p className="table-caption">Table 4. Cross-domain comparability matrix.</p>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Dimension</th>
                <th scope="col">ULB</th>
                <th scope="col">PMGSY</th>
                <th scope="col">MPLADS</th>
              </tr>
            </thead>
            <tbody>
              {COMPARABILITY_ROWS.map((row) => (
                <tr key={row.dimension}>
                  <td className="mono">{row.dimension}</td>
                  <td>{row.ulb}</td>
                  <td>{row.pmgsy}</td>
                  <td>{row.mplads}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="editorial-muted domains-page__comparability-note">
            Direct numeric comparison across dataset kinds is methodologically
            unsound. Each dataset has different units, coverage and anomaly
            semantics. The workbench presents each domain on its own terms;
            cross-domain synthesis is a research question, not a UI affordance.
          </p>
        </section>
      </div>
    </div>
  );
}
