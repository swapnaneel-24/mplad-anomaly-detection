// Data Observatory — Dataset Examination Workspace (Prompt A structural redesign).
// Wide primary workspace by default; contextual right inspector only when a row is selected.

import { useEffect, useMemo, useState } from "react";
import { listSources } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import type {
  AnalysisStatus,
  DatasetKind,
  IntegrityStatus,
  SourceListResponse,
  SourceSummary,
} from "@/api/contracts";
import { Loading } from "@/components/Loading";
import { ErrorPanel } from "@/components/ErrorPanel";
import { EmptyState } from "@/components/EmptyState";
import "@/pages/DataPage.css";

type DataSubview = "sources" | "snapshots" | "package_records";

interface SnapshotDescriptor {
  snapshot_id: string;
  label: string;
  registration_status: string;
  record_scope: string;
  notes: string;
}

interface PackageRecordDescriptor {
  record_id: string;
  package_uid: string;
  mrl_id: string;
  state: string;
  ims_year: string;
  record_scope: string;
  link_status: string;
}

const LOCAL_SNAPSHOTS: SnapshotDescriptor[] = [
  {
    snapshot_id: "pmgsy3_3state_v1_curated_42",
    label: "Local research snapshot (PMGSY-III curated 42-case import)",
    registration_status: "Not established in global /api/v1/sources registry",
    record_scope: "42 selected case-linked packages (not all 4,361 P packages)",
    notes: "Local research snapshot only; separate from the server-side source registry.",
  },
];

const CURATED_CASE_LINKED_PACKAGES: PackageRecordDescriptor[] = [
  {
    record_id: "PEIARS_PMGSY_001",
    package_uid: "pmgsy3_up_241861",
    mrl_id: "241861",
    state: "UTTAR_PRADESH",
    ims_year: "2020",
    record_scope: "42 selected case-linked packages (subset of 4,361 P packages)",
    link_status: "Case-linked in local research baseline",
  },
];

const DATASET_KINDS: DatasetKind[] = [
  "ulb_benchmark",
  "pmgsy_infrastructure",
  "mplads_administration",
];

const INTEGRITY_STATUSES: IntegrityStatus[] = [
  "verified",
  "unverified_legacy",
  "integrity_failed",
  "unavailable",
];

const ANALYSIS_STATUSES: AnalysisStatus[] = [
  "verified_benchmark",
  "exploratory",
  "restricted",
  "blocked",
  "unavailable",
];

export function DataPage(): JSX.Element {
  const [sourceResp, setSourceResp] = useState<SourceListResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  const [subview, setSubview] = useState<DataSubview>("sources");
  const [searchQuery, setSearchQuery] = useState("");
  const [kindFilter, setKindFilter] = useState<string>("all");
  const [integrityFilter, setIntegrityFilter] = useState<string>("all");
  const [analysisFilter, setAnalysisFilter] = useState<string>("all");
  const [moreFiltersOpen, setMoreFiltersOpen] = useState(false);
  const [aboutRegistryOpen, setAboutRegistryOpen] = useState(false);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await listSources({ signal: controller.signal });
        setSourceResp(result);
      } catch (err) {
        if (err instanceof ApiError && err.aborted) return;
        setError(err instanceof ApiError ? err : null);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, []);

  const sources: SourceSummary[] = useMemo(
    () => sourceResp?.sources ?? [],
    [sourceResp],
  );

  const filteredSources = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return sources.filter((s) => {
      if (kindFilter !== "all" && s.dataset_kind !== kindFilter) return false;
      if (integrityFilter !== "all" && s.integrity_status !== integrityFilter) return false;
      if (analysisFilter !== "all" && s.analysis_status !== analysisFilter) return false;
      if (!q) return true;
      return (
        s.source_id.toLowerCase().includes(q) ||
        s.dataset_kind.toLowerCase().includes(q) ||
        s.integrity_status.toLowerCase().includes(q) ||
        s.analysis_status.toLowerCase().includes(q)
      );
    });
  }, [sources, searchQuery, kindFilter, integrityFilter, analysisFilter]);

  const filteredSnapshots = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return LOCAL_SNAPSHOTS.filter((sn) => {
      if (!q) return true;
      return (
        sn.snapshot_id.toLowerCase().includes(q) ||
        sn.label.toLowerCase().includes(q) ||
        sn.record_scope.toLowerCase().includes(q)
      );
    });
  }, [searchQuery]);

  const filteredPackages = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return CURATED_CASE_LINKED_PACKAGES.filter((pkg) => {
      if (!q) return true;
      return (
        pkg.record_id.toLowerCase().includes(q) ||
        pkg.package_uid.toLowerCase().includes(q) ||
        pkg.mrl_id.toLowerCase().includes(q) ||
        pkg.state.toLowerCase().includes(q) ||
        pkg.ims_year.toLowerCase().includes(q)
      );
    });
  }, [searchQuery]);

  const handleSubviewChange = (next: DataSubview) => {
    setSubview(next);
    setSelectedId(null);
    setInspectorOpen(false);
    setKindFilter("all");
    setIntegrityFilter("all");
    setAnalysisFilter("all");
  };

  const handleClearFilters = () => {
    setSearchQuery("");
    setKindFilter("all");
    setIntegrityFilter("all");
    setAnalysisFilter("all");
  };

  const handleSelectRow = (id: string) => {
    setSelectedId(id);
    setInspectorOpen(true);
  };

  const handleCloseInspector = () => {
    setInspectorOpen(false);
  };

  const selectedSource =
    subview === "sources"
      ? filteredSources.find((s) => s.source_id === selectedId) ?? null
      : null;
  const selectedSnapshot =
    subview === "snapshots"
      ? filteredSnapshots.find((sn) => sn.snapshot_id === selectedId) ?? null
      : null;
  const selectedPackage =
    subview === "package_records"
      ? filteredPackages.find((pkg) => pkg.record_id === selectedId) ?? null
      : null;

  const hasSelection = Boolean(
    inspectorOpen && (selectedSource || selectedSnapshot || selectedPackage),
  );

  const visibleCount =
    subview === "sources"
      ? filteredSources.length
      : subview === "snapshots"
        ? filteredSnapshots.length
        : filteredPackages.length;

  const totalCount =
    subview === "sources"
      ? sources.length
      : subview === "snapshots"
        ? LOCAL_SNAPSHOTS.length
        : CURATED_CASE_LINKED_PACKAGES.length;

  return (
    <div className="data-page workspace-composition">
      <div className="data-page__top">
        <div className="data-page__subnav" role="tablist" aria-label="Data Observatory views">
          <button
            type="button"
            role="tab"
            aria-selected={subview === "sources"}
            className={`data-page__subtab ${subview === "sources" ? "is-active" : ""}`}
            onClick={() => handleSubviewChange("sources")}
          >
            Sources
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={subview === "snapshots"}
            className={`data-page__subtab ${subview === "snapshots" ? "is-active" : ""}`}
            onClick={() => handleSubviewChange("snapshots")}
          >
            Snapshots
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={subview === "package_records"}
            className={`data-page__subtab ${subview === "package_records" ? "is-active" : ""}`}
            onClick={() => handleSubviewChange("package_records")}
          >
            Package Records
          </button>
        </div>

        <button
          type="button"
          className="btn btn--secondary btn--compact"
          aria-expanded={aboutRegistryOpen}
          onClick={() => setAboutRegistryOpen((prev) => !prev)}
        >
          About registry
        </button>
      </div>

      {aboutRegistryOpen && (
        <div className="data-page__help-drawer panel" role="region" aria-label="About registry">
          <div className="panel__header">
            <span className="panel__title">Registry &amp; Snapshot Boundaries</span>
            <button
              type="button"
              className="data-page__close-btn"
              onClick={() => setAboutRegistryOpen(false)}
              aria-label="Close registry notes"
            >
              ×
            </button>
          </div>
          <div className="panel__body data-page__help-body">
            <p>
              Registered sources come from <code>/api/v1/sources</code> using opaque slugs and do
              not scan the filesystem or turn a synthetic demonstration source into PMGSY.
            </p>
            <p>
              Local research snapshots and curated case-linked package sets (such as the 42-case
              research baseline) are distinct entities from the global source registry and do not
              represent all 4,361 P packages.
            </p>
          </div>
        </div>
      )}

      <div className="data-page__toolbar" role="region" aria-label="Data filters">
        <input
          type="search"
          className="data-page__search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder={
            subview === "sources"
              ? "Search source ID, dataset kind, integrity, or analysis..."
              : subview === "snapshots"
                ? "Search snapshot ID or scope..."
                : "Search case ID, package UID, MRL ID, state, or year..."
          }
          aria-label="Search records"
        />

        {subview === "sources" ? (
          <>
            <select
              className="data-page__select"
              value={kindFilter}
              onChange={(e) => setKindFilter(e.target.value)}
              aria-label="Filter by dataset kind"
            >
              <option value="all">All dataset kinds</option>
              {DATASET_KINDS.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>

            <select
              className="data-page__select"
              value={integrityFilter}
              onChange={(e) => setIntegrityFilter(e.target.value)}
              aria-label="Filter by integrity status"
            >
              <option value="all">All integrity statuses</option>
              {INTEGRITY_STATUSES.map((st) => (
                <option key={st} value={st}>
                  {st}
                </option>
              ))}
            </select>

            <button
              type="button"
              className="btn btn--secondary btn--compact"
              aria-expanded={moreFiltersOpen}
              onClick={() => setMoreFiltersOpen((prev) => !prev)}
            >
              More filters
            </button>
          </>
        ) : (
          <span className="data-page__filter-note mono">
            Dataset/integrity filters apply to registered /api/v1/sources only.
          </span>
        )}

        <button
          type="button"
          className="btn btn--secondary btn--compact"
          onClick={handleClearFilters}
        >
          Clear
        </button>

        <span className="data-page__count mono">
          {visibleCount}/{totalCount}
        </span>
      </div>

      {moreFiltersOpen && subview === "sources" && (
        <div className="data-page__more-filters">
          <label className="data-page__inline-field">
            <span className="data-page__inline-label">Analysis status</span>
            <select
              className="data-page__select"
              value={analysisFilter}
              onChange={(e) => setAnalysisFilter(e.target.value)}
            >
              <option value="all">All analysis statuses</option>
              {ANALYSIS_STATUSES.map((st) => (
                <option key={st} value={st}>
                  {st}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      <div className={`data-page__body ${hasSelection ? "has-inspector" : "is-full-width"}`}>
        <section className="data-page__table panel" aria-label="Data table">
          <div className="panel__header">
            <span className="panel__title">
              {subview === "sources"
                ? "Registered sources (/api/v1/sources)"
                : subview === "snapshots"
                  ? "Local research snapshots"
                  : "Curated case-linked package records"}
            </span>
            <span className="panel__title mono">{visibleCount} shown</span>
          </div>

          <div className="panel__body panel__body--flush">
            {subview === "sources" && loading && !sourceResp ? (
              <div className="data-page__state-pad">
                <Loading label="Loading sources…" />
              </div>
            ) : subview === "sources" && error ? (
              <div className="data-page__state-pad">
                <ErrorPanel error={error} onRetry={() => window.location.reload()} />
              </div>
            ) : subview === "sources" ? (
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
                  {filteredSources.length > 0 ? (
                    filteredSources.map((s) => {
                      const active = hasSelection && selectedSource?.source_id === s.source_id;
                      return (
                        <tr
                          key={s.source_id}
                          className={active ? "is-selected" : undefined}
                          onClick={() => handleSelectRow(s.source_id)}
                        >
                          <td className="mono">{s.source_id}</td>
                          <td className="mono">{s.dataset_kind}</td>
                          <td className="mono">{s.integrity_status}</td>
                          <td className="mono">{s.analysis_status}</td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={4}>
                        <EmptyState>
                          {sources.length === 0
                            ? "No sources registered. The source registry is empty."
                            : "No registered sources match the current filters."}
                        </EmptyState>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            ) : subview === "snapshots" ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Snapshot ID</th>
                    <th scope="col">Description</th>
                    <th scope="col">Record scope</th>
                    <th scope="col">Registry linkage</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredSnapshots.length > 0 ? (
                    filteredSnapshots.map((sn) => {
                      const active = hasSelection && selectedSnapshot?.snapshot_id === sn.snapshot_id;
                      return (
                        <tr
                          key={sn.snapshot_id}
                          className={active ? "is-selected" : undefined}
                          onClick={() => handleSelectRow(sn.snapshot_id)}
                        >
                          <td className="mono">{sn.snapshot_id}</td>
                          <td>{sn.label}</td>
                          <td>{sn.record_scope}</td>
                          <td>{sn.registration_status}</td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={4}>
                        <EmptyState>No local snapshots match the current search.</EmptyState>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Case Ref</th>
                    <th scope="col">Package UID</th>
                    <th scope="col">MRL ID</th>
                    <th scope="col">State</th>
                    <th scope="col">IMS Year</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPackages.length > 0 ? (
                    filteredPackages.map((pkg) => {
                      const active = hasSelection && selectedPackage?.record_id === pkg.record_id;
                      return (
                        <tr
                          key={pkg.record_id}
                          className={active ? "is-selected" : undefined}
                          onClick={() => handleSelectRow(pkg.record_id)}
                        >
                          <td className="mono">{pkg.record_id}</td>
                          <td className="mono">{pkg.package_uid}</td>
                          <td className="mono">{pkg.mrl_id}</td>
                          <td className="mono">{pkg.state}</td>
                          <td className="mono">{pkg.ims_year}</td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={5}>
                        <EmptyState>No case-linked package records match the current search.</EmptyState>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
        </section>

        {hasSelection && (
          <aside className="data-page__inspector panel" aria-label="Selected item inspector">
            <div className="panel__header">
              <span className="panel__title">Inspector</span>
              <button
                type="button"
                className="data-page__close-btn"
                onClick={handleCloseInspector}
                aria-label="Close inspector"
              >
                ×
              </button>
            </div>
            <div className="panel__body data-page__inspector-body">
              {selectedSource && (
                <dl className="data-page__dl">
                  <dt>Source ID</dt>
                  <dd className="mono">{selectedSource.source_id}</dd>
                  <dt>Dataset kind</dt>
                  <dd className="mono">{selectedSource.dataset_kind}</dd>
                  <dt>Integrity</dt>
                  <dd className="mono">{selectedSource.integrity_status}</dd>
                  <dt>Analysis</dt>
                  <dd className="mono">{selectedSource.analysis_status}</dd>
                </dl>
              )}
              {selectedSnapshot && (
                <dl className="data-page__dl">
                  <dt>Snapshot ID</dt>
                  <dd className="mono">{selectedSnapshot.snapshot_id}</dd>
                  <dt>Scope</dt>
                  <dd>{selectedSnapshot.record_scope}</dd>
                  <dt>Registry status</dt>
                  <dd>{selectedSnapshot.registration_status}</dd>
                  <dt>Notes</dt>
                  <dd>{selectedSnapshot.notes}</dd>
                </dl>
              )}
              {selectedPackage && (
                <dl className="data-page__dl">
                  <dt>Case Ref</dt>
                  <dd className="mono">{selectedPackage.record_id}</dd>
                  <dt>Package UID</dt>
                  <dd className="mono">{selectedPackage.package_uid}</dd>
                  <dt>MRL ID</dt>
                  <dd className="mono">{selectedPackage.mrl_id}</dd>
                  <dt>State / Year</dt>
                  <dd className="mono">
                    {selectedPackage.state} · {selectedPackage.ims_year}
                  </dd>
                  <dt>Scope</dt>
                  <dd>{selectedPackage.record_scope}</dd>
                </dl>
              )}
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
