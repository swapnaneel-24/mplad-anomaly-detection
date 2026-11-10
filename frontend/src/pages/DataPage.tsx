// Data Observatory — Dataset Examination Workspace.
// Per SCREEN_DESIGN_NOTES.md §4. Three-column grid:
//   left (240px): contextual filter rail
//   centre (1fr): source examination table
//   right (320px): source metadata inspector (deferred)

import { useEffect, useState } from "react";
import { listSources } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import type { DatasetKind, SourceListResponse } from "@/api/contracts";
import { Loading } from "@/components/Loading";
import { ErrorPanel } from "@/components/ErrorPanel";
import { EmptyState } from "@/components/EmptyState";
import { DeferredPanel } from "@/components/DeferredPanel";
import "@/pages/DataPage.css";

export function DataPage(): JSX.Element {
  const [data, setData] = useState<SourceListResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await listSources({ signal: controller.signal });
        setData(result);
      } catch (err) {
        if (err instanceof ApiError && err.aborted) return;
        setError(err instanceof ApiError ? err : null);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, []);

  return (
    <div className="data-page workspace-composition">
      <aside className="data-page__filters panel" aria-label="Filters">
        <div className="panel__header">
          <span className="panel__title">Filters</span>
        </div>
        <div className="panel__body">
          <fieldset className="filter-group" disabled>
            <legend className="filter-group__legend">Dataset kind</legend>
            <label className="filter-radio"><input type="radio" name="dk" defaultChecked /> <span>any</span></label>
            {DATASET_KINDS.map((k) => (
              <label key={k} className="filter-radio">
                <input type="radio" name="dk" /> <span className="mono">{k}</span>
              </label>
            ))}
            <p className="filter-group__note mono">Filtering requires registered sources.</p>
          </fieldset>
          <fieldset className="filter-group" disabled>
            <legend className="filter-group__legend">Integrity status</legend>
            <label className="filter-radio"><input type="radio" name="is" defaultChecked /> <span>any</span></label>
            <p className="filter-group__note mono">Filtering requires registered sources.</p>
          </fieldset>
          <fieldset className="filter-group" disabled>
            <legend className="filter-group__legend">Analysis status</legend>
            <label className="filter-radio"><input type="radio" name="as" defaultChecked /> <span>any</span></label>
            <p className="filter-group__note mono">Filtering requires registered sources.</p>
          </fieldset>
        </div>
      </aside>

      <section className="data-page__table panel" aria-label="Source examination">
        <div className="panel__header">
          <span className="panel__title">Registered sources</span>
          <span className="panel__title mono">{data?.count ?? 0} records</span>
        </div>
        <div className="panel__body panel__body--flush">
          {loading && !data ? (
            <div className="data-page__loading"><Loading label="Loading sources…" /></div>
          ) : error ? (
            <div className="data-page__error"><ErrorPanel error={error} onRetry={() => window.location.reload()} /></div>
          ) : (
            <>
              <p className="table-caption data-page__caption">
                Table 2. Registered data sources (/api/v1/sources).
              </p>
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Source ID</th>
                    <th scope="col">Dataset kind</th>
                    <th scope="col">Integrity</th>
                    <th scope="col">Analysis</th>
                  </tr>
                </thead>
                <tbody>
                  {data && data.count > 0 ? (
                    data.sources.map((s) => (
                      <tr key={s.source_id}>
                        <td className="mono">{s.source_id}</td>
                        <td className="mono">{s.dataset_kind}</td>
                        <td className="mono">{s.integrity_status}</td>
                        <td className="mono">{s.analysis_status}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4}>
                        <EmptyState>No sources registered. The source registry is empty.</EmptyState>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
              <div className="data-page__registry-note">
                <h3 className="section-h4">Registry semantics</h3>
                <p className="editorial-muted">
                  The source registry is server-side. Identifiers are opaque
                  slugs, validated and rejected if path-like. Sources are
                  never discovered by scanning the filesystem, and no DVC or
                  object-storage access is performed by these routes.
                </p>
              </div>
            </>
          )}
        </div>
      </section>

      <aside className="data-page__inspector panel" aria-label="Source metadata inspector">
        <div className="panel__header">
          <span className="panel__title">Source metadata</span>
        </div>
        <div className="panel__body">
          <DeferredPanel
            title="Source metadata inspector (deferred)"
            description="Field definitions, schema provenance and integrity reports will appear here when a source is selected."
            futurePr="PR-05B"
            minHeight={240}
          />
        </div>
      </aside>
    </div>
  );
}

const DATASET_KINDS: DatasetKind[] = [
  "ulb_benchmark",
  "pmgsy_infrastructure",
  "mplads_administration",
];
