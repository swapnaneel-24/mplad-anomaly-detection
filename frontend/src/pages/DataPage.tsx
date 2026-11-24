// Data Observatory ? Dataset Examination Workspace (Prompt B).
// Wide primary workspace by default; contextual right inspector only when a row is selected.

import { useEffect, useMemo, useState } from "react";
import {
  getWorkbenchPmgsyPackage,
  getWorkbenchSnapshot,
  listSources,
  listWorkbenchPmgsyPackages,
  listWorkbenchSnapshots,
} from "@/api/endpoints";
import { ApiError } from "@/api/client";
import type {
  AnalysisStatus,
  DatasetKind,
  IntegrityStatus,
  SourceListResponse,
  SourceSummary,
  WorkbenchPackageDetail,
  WorkbenchPackageSummary,
  WorkbenchSnapshotDetail,
} from "@/api/contracts";
import { Loading } from "@/components/Loading";
import { ErrorPanel } from "@/components/ErrorPanel";
import { EmptyState } from "@/components/EmptyState";
import "@/pages/DataPage.css";

type DataSubview = "sources" | "snapshots" | "package_records";

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

function formatNum(val: number | string | null | undefined, digits = 4): string {
  if (val === null || val === undefined || val === "") return "UNAVAILABLE";
  if (typeof val === "string") return val;
  if (Number.isNaN(val)) return "UNAVAILABLE";
  return val.toFixed(digits);
}

export function DataPage(): JSX.Element {
  const [sourceResp, setSourceResp] = useState<SourceListResponse | null>(null);
  const [snapshots, setSnapshots] = useState<WorkbenchSnapshotDetail[]>([]);
  const [packages, setPackages] = useState<WorkbenchPackageSummary[]>([]);

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

  const [snapshotDetail, setSnapshotDetail] = useState<WorkbenchSnapshotDetail | null>(null);
  const [snapshotDetailLoading, setSnapshotDetailLoading] = useState(false);

  const [packageDetail, setPackageDetail] = useState<WorkbenchPackageDetail | null>(null);
  const [packageDetailLoading, setPackageDetailLoading] = useState(false);
  const [packageDetailError, setPackageDetailError] = useState<string | null>(null);

  const [measurementsOpen, setMeasurementsOpen] = useState(true);
  const [provenanceOpen, setProvenanceOpen] = useState(false);
  const [rawJsonOpen, setRawJsonOpen] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      setLoading(true);
      setError(null);
      try {
        if (subview === "sources") {
          const result = await listSources({ signal: controller.signal });
          setSourceResp(result);
        } else if (subview === "snapshots") {
          const result = await listWorkbenchSnapshots(controller.signal);
          setSnapshots(result.snapshots);
        } else {
          const result = await listWorkbenchPmgsyPackages(controller.signal);
          setPackages(result.packages);
        }
      } catch (err) {
        if (err instanceof ApiError && err.aborted) return;
        setError(err instanceof ApiError ? err : null);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [subview]);

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
    return snapshots.filter((sn) => {
      if (!q) return true;
      return (
        sn.snapshot_id.toLowerCase().includes(q) ||
        sn.label.toLowerCase().includes(q) ||
        sn.record_scope.toLowerCase().includes(q) ||
        sn.dataset_version.toLowerCase().includes(q)
      );
    });
  }, [snapshots, searchQuery]);

  const filteredPackages = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return packages.filter((pkg) => {
      if (!q) return true;
      return (
        pkg.case_id.toLowerCase().includes(q) ||
        pkg.package_uid.toLowerCase().includes(q) ||
        pkg.mrl_id.toLowerCase().includes(q) ||
        pkg.state.toLowerCase().includes(q) ||
        pkg.ims_year.toLowerCase().includes(q) ||
        pkg.disposition.toLowerCase().includes(q) ||
        pkg.verification_status.toLowerCase().includes(q)
      );
    });
  }, [packages, searchQuery]);

  useEffect(() => {
    if (!inspectorOpen || !selectedId) {
      setSnapshotDetail(null);
      setPackageDetail(null);
      setPackageDetailError(null);
      return;
    }

    const controller = new AbortController();
    if (subview === "snapshots") {
      setSnapshotDetailLoading(true);
      const cached = snapshots.find((s) => s.snapshot_id === selectedId) ?? null;
      setSnapshotDetail(cached);
      getWorkbenchSnapshot(selectedId, controller.signal)
        .then((detail) => {
          if (!controller.signal.aborted) setSnapshotDetail(detail);
        })
        .catch((err) => {
          if (err instanceof ApiError && err.aborted) return;
        })
        .finally(() => {
          if (!controller.signal.aborted) setSnapshotDetailLoading(false);
        });
    } else if (subview === "package_records") {
      setPackageDetailLoading(true);
      setPackageDetailError(null);
      setPackageDetail(null);
      setProvenanceOpen(false);
      setRawJsonOpen(false);
      getWorkbenchPmgsyPackage(selectedId, controller.signal)
        .then((detail) => {
          if (!controller.signal.aborted) {
            setPackageDetail(detail);
          }
        })
        .catch((err) => {
          if (err instanceof ApiError && err.aborted) return;
          if (!controller.signal.aborted) {
            setPackageDetailError(
              err instanceof ApiError ? err.message : "Failed to load package detail.",
            );
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) setPackageDetailLoading(false);
        });
    }
    return () => controller.abort();
  }, [inspectorOpen, selectedId, subview, snapshots]);

  const handleSubviewChange = (next: DataSubview) => {
    setSubview(next);
    setSelectedId(null);
    setInspectorOpen(false);
    setSnapshotDetail(null);
    setPackageDetail(null);
    setPackageDetailError(null);
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
    subview === "sources" && selectedId
      ? sources.find((s) => s.source_id === selectedId) ?? null
      : null;

  const selectedSnapshotSummary =
    subview === "snapshots" && selectedId
      ? snapshots.find((sn) => sn.snapshot_id === selectedId) ?? null
      : null;

  const selectedPackageSummary =
    subview === "package_records" && selectedId
      ? packages.find((pkg) => pkg.case_id === selectedId) ?? null
      : null;

  const hasSelection = Boolean(
    inspectorOpen &&
      selectedId &&
      ((subview === "sources" && selectedSource) ||
        (subview === "snapshots" && (snapshotDetail || selectedSnapshotSummary)) ||
        (subview === "package_records" && selectedPackageSummary)),
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
        ? snapshots.length
        : packages.length;

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
              ?
            </button>
          </div>
          <div className="panel__body data-page__help-body">
            <p>
              Registered sources come from <code>/api/v1/sources</code> using opaque slugs and do
              not scan the filesystem or turn a local snapshot into an admitted source.
            </p>
            <p>
              The 42 case-linked PMGSY package records are a selected subset of the 4,361 scored P
              packages and are distinct from 03 Analysis, 04 Investigations, and 06 Research.
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
                ? "Search snapshot ID, dataset version, or scope..."
                : "Search case ID, package UID, MRL ID, state, year, or status..."
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
                  : "Case-linked PMGSY package records (42-case subset)"}
            </span>
            <span className="panel__title mono">{visibleCount} shown</span>
          </div>

          <div className="panel__body panel__body--flush">
            {loading ? (
              <div className="data-page__state-pad">
                <Loading label="Loading workbench records?" />
              </div>
            ) : error ? (
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
                    <th scope="col">Label</th>
                    <th scope="col">Record scope</th>
                    <th scope="col">Registry status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredSnapshots.length > 0 ? (
                    filteredSnapshots.map((sn) => {
                      const active = hasSelection && selectedId === sn.snapshot_id;
                      return (
                        <tr
                          key={sn.snapshot_id}
                          className={active ? "is-selected" : undefined}
                          onClick={() => handleSelectRow(sn.snapshot_id)}
                        >
                          <td className="mono">{sn.snapshot_id}</td>
                          <td>{sn.label}</td>
                          <td>{sn.record_scope}</td>
                          <td>
                            <span className="badge badge--integrity mono">
                              {sn.registration_status}
                            </span>
                          </td>
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
                    <th scope="col">Case ID</th>
                    <th scope="col">Package UID</th>
                    <th scope="col">MRL ID</th>
                    <th scope="col">State</th>
                    <th scope="col">IMS Year</th>
                    <th scope="col">Disposition</th>
                    <th scope="col">Verification</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPackages.length > 0 ? (
                    filteredPackages.map((pkg) => {
                      const active = hasSelection && selectedId === pkg.case_id;
                      return (
                        <tr
                          key={pkg.case_id}
                          className={active ? "is-selected" : undefined}
                          onClick={() => handleSelectRow(pkg.case_id)}
                        >
                          <td className="mono">{pkg.case_id}</td>
                          <td className="mono">{pkg.package_uid}</td>
                          <td className="mono">{pkg.mrl_id}</td>
                          <td className="mono">{pkg.state}</td>
                          <td className="mono">{pkg.ims_year}</td>
                          <td>
                            <span className="badge badge--disposition mono">
                              {pkg.disposition}
                            </span>
                          </td>
                          <td>
                            <span className="badge badge--verification mono">
                              {pkg.verification_status}
                            </span>
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={7}>
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
            <div className="panel__header inspector__header">
              <span className="panel__title">Inspector</span>
              <button
                type="button"
                className="data-page__close-btn"
                onClick={handleCloseInspector}
                aria-label="Close inspector"
              >
                ?
              </button>
            </div>

            <div className="panel__body data-page__inspector-body inspector__body">
              {subview === "sources" && selectedSource && (
                <section className="inspector__section" aria-label="Source metadata">
                  <div className="inspector__identity">
                    <div className="inspector__title mono">{selectedSource.source_id}</div>
                    <div className="inspector__subtitle">
                      Admitted source registry record (/api/v1/sources)
                    </div>
                  </div>
                  <dl className="data-page__dl">
                    <dt>Source ID</dt>
                    <dd className="mono">{selectedSource.source_id}</dd>
                    <dt>Dataset kind</dt>
                    <dd className="mono">{selectedSource.dataset_kind}</dd>
                    <dt>Integrity</dt>
                    <dd>
                      <span className="badge badge--integrity mono">
                        {selectedSource.integrity_status}
                      </span>
                    </dd>
                    <dt>Analysis</dt>
                    <dd className="mono">{selectedSource.analysis_status}</dd>
                    <dt>Additional provenance</dt>
                    <dd>Unavailable from SourceSummary registry contract.</dd>
                  </dl>
                </section>
              )}

              {subview === "snapshots" && (snapshotDetail || selectedSnapshotSummary) && (
                <section className="inspector__section" aria-label="Snapshot metadata">
                  {(() => {
                    const snap = snapshotDetail ?? selectedSnapshotSummary!;
                    return (
                      <>
                        <div className="inspector__identity">
                          <div className="inspector__title mono">{snap.snapshot_id}</div>
                          <div className="inspector__subtitle">{snap.label}</div>
                        </div>

                        <div className="inspector__status-pair">
                          <div className="inspector__status-cell">
                            <span className="inspector__meta-label">Registry linkage</span>
                            <span className="badge badge--integrity mono">
                              {snap.registration_status}
                            </span>
                          </div>
                          <div className="inspector__status-cell">
                            <span className="inspector__meta-label">Dataset version</span>
                            <span className="badge badge--screening mono">
                              {snap.dataset_version}
                            </span>
                          </div>
                        </div>

                        <dl className="data-page__dl">
                          <dt>Record scope</dt>
                          <dd>{snap.record_scope}</dd>
                          <dt>Population note</dt>
                          <dd>
                            Contains {snap.case_linked_count} case-linked records; not all 4,361
                            scored P packages and not an admitted /api/v1/sources registry source.
                          </dd>
                          <dt>Case-linked count</dt>
                          <dd className="mono">{snap.case_linked_count}</dd>
                          <dt>Baseline events</dt>
                          <dd className="mono">{snap.baseline_event_count}</dd>
                          <dt>Disposition counts</dt>
                          <dd className="mono">
                            {Object.entries(snap.disposition_counts ?? {})
                              .map(([k, v]) => `${k}: ${v}`)
                              .join(" ? ") || "Unavailable"}
                          </dd>
                          <dt>Verification counts</dt>
                          <dd className="mono">
                            {Object.entries(snap.verification_status_counts ?? {})
                              .map(([k, v]) => `${k}: ${v}`)
                              .join(" ? ") || "Unavailable"}
                          </dd>
                          <dt>Manifest reference</dt>
                          <dd className="mono">{snap.manifest_reference || "Unavailable"}</dd>
                          <dt>Manifest hash</dt>
                          <dd className="mono">{snap.manifest_sha256 || "Unavailable"}</dd>
                          <dt>Notes</dt>
                          <dd>{snap.notes}</dd>
                        </dl>
                        {snapshotDetailLoading && (
                          <div className="inspector__muted mono">Refreshing snapshot details?</div>
                        )}
                      </>
                    );
                  })()}
                </section>
              )}

              {subview === "package_records" && selectedPackageSummary && (
                <>
                  {/* Level 1 ? Immediate context */}
                  <section className="inspector__section inspector__identity" aria-label="Record identity">
                    <div className="inspector__title mono">{selectedPackageSummary.case_id}</div>
                    <dl className="data-page__dl">
                      <dt>MRL ID</dt>
                      <dd className="mono">
                        {packageDetail?.identity.mrl_id || selectedPackageSummary.mrl_id || "UNAVAILABLE"}
                      </dd>
                      <dt>State</dt>
                      <dd className="mono">
                        {packageDetail?.identity.state || selectedPackageSummary.state || "UNAVAILABLE"}
                      </dd>
                      <dt>IMS Year</dt>
                      <dd className="mono">
                        {packageDetail?.identity.ims_year || selectedPackageSummary.ims_year || "UNAVAILABLE"}
                      </dd>
                    </dl>

                    <div className="inspector__observation">
                      <span className="inspector__meta-label">Observation</span>
                      <p className="inspector__observation-text">
                        {selectedPackageSummary.observation_summary}
                      </p>
                    </div>

                    <div className="inspector__status-pair">
                      <div className="inspector__status-cell">
                        <span className="inspector__meta-label">Disposition</span>
                        <span className="badge badge--disposition mono">
                          {packageDetail?.review.disposition || selectedPackageSummary.disposition}
                        </span>
                      </div>
                      <div className="inspector__status-cell">
                        <span className="inspector__meta-label">Verification</span>
                        <span className="badge badge--verification mono">
                          {packageDetail?.verification.verification_status ||
                            selectedPackageSummary.verification_status}
                        </span>
                      </div>
                    </div>

                    <div className="inspector__nav-link-row">
                      <a
                        className="inspector__nav-link"
                        href={`#investigations?case=${encodeURIComponent(selectedPackageSummary.case_id)}`}
                        data-case-id={selectedPackageSummary.case_id}
                      >
                        Open related investigation ?
                      </a>
                    </div>
                  </section>

                  {packageDetailLoading && (
                    <div className="inspector__muted mono">Loading record detail &amp; provenance?</div>
                  )}
                  {packageDetailError && (
                    <div className="inspector__error">{packageDetailError}</div>
                  )}

                  {/* Level 2 ? Evidence & Measurements */}
                  {packageDetail && (
                    <section className="inspector__section" aria-label="Evidence and measurements">
                      <button
                        type="button"
                        className="inspector__disclosure-btn"
                        aria-expanded={measurementsOpen}
                        onClick={() => setMeasurementsOpen((prev) => !prev)}
                      >
                        <span>Evidence &amp; Measurements</span>
                        <span className="mono">{measurementsOpen ? "?" : "+"}</span>
                      </button>

                      {measurementsOpen && (
                        <dl className="data-page__dl inspector__group-body">
                          <dt>Proposed length</dt>
                          <dd className="mono">
                            {formatNum(packageDetail.measurements.proposed_l_km)} km
                          </dd>
                          <dt>Mapped geometry length</dt>
                          <dd className="mono">
                            {formatNum(packageDetail.measurements.sum_geom_len_km)} km
                          </dd>
                          <dt>Signed diff (geom ? proposed)</dt>
                          <dd className="mono">
                            {formatNum(packageDetail.measurements.length_diff_km)} km
                          </dd>
                          <dt>Relative length diff</dt>
                          <dd className="mono">
                            {packageDetail.measurements.length_rel_diff_status ===
                            "UNDEFINED_ZERO_DENOMINATOR"
                              ? "UNDEFINED_ZERO_DENOMINATOR"
                              : formatNum(packageDetail.measurements.length_rel_diff)}
                          </dd>
                          <dt>Segment count</dt>
                          <dd className="mono">
                            {packageDetail.topology.segment_count !== null &&
                            packageDetail.topology.segment_count !== undefined
                              ? String(packageDetail.topology.segment_count)
                              : "UNAVAILABLE"}
                          </dd>
                          <dt>Exact geometry duplicate</dt>
                          <dd className="mono">
                            {String(packageDetail.topology.exact_geometry_duplicate)}
                          </dd>
                          <dt>Linear overlap</dt>
                          <dd className="mono">
                            {String(packageDetail.topology.linear_overlap)}
                          </dd>
                          <dt>Invalid geometry</dt>
                          <dd className="mono">
                            {String(packageDetail.topology.invalid_geometry)}
                          </dd>
                          <dt>Queues</dt>
                          <dd className="mono">
                            {packageDetail.screening.queues.length > 0
                              ? packageDetail.screening.queues.join(", ")
                              : "None listed"}
                          </dd>
                          <dt>Screening reasons</dt>
                          <dd>
                            {packageDetail.screening.screening_reasons.length > 0
                              ? packageDetail.screening.screening_reasons.join("; ")
                              : "None recorded"}
                          </dd>
                          <dt>Review status</dt>
                          <dd className="mono">{packageDetail.review.review_status}</dd>
                          <dt>Independent of canonical GIS</dt>
                          <dd className="mono">
                            {String(packageDetail.verification.independent_of_canonical_gis)}
                          </dd>
                          <dt>Verification blocker</dt>
                          <dd>
                            {packageDetail.verification.blocker_reason || "None recorded"}
                          </dd>
                        </dl>
                      )}
                    </section>
                  )}

                  {/* Level 3 ? Technical Provenance (collapsed by default) */}
                  {packageDetail && (
                    <section className="inspector__section" aria-label="Technical provenance">
                      <button
                        type="button"
                        className="inspector__disclosure-btn"
                        aria-expanded={provenanceOpen}
                        onClick={() => setProvenanceOpen((prev) => !prev)}
                      >
                        <span>Technical Provenance</span>
                        <span className="mono">{provenanceOpen ? "?" : "+"}</span>
                      </button>

                      {provenanceOpen && (
                        <div className="inspector__group-body">
                          <dl className="data-page__dl">
                            <dt>Package UID</dt>
                            <dd className="mono">{packageDetail.identity.package_uid}</dd>
                            <dt>Case ID</dt>
                            <dd className="mono">{packageDetail.identity.case_id}</dd>
                            <dt>Snapshot ID</dt>
                            <dd className="mono">{packageDetail.scope.snapshot_id}</dd>
                            <dt>Record scope</dt>
                            <dd>{packageDetail.scope.record_scope}</dd>
                            <dt>Registry status</dt>
                            <dd className="mono">
                              {packageDetail.scope.source_registration_status}
                            </dd>
                            <dt>Baseline events (case)</dt>
                            <dd className="mono">
                              {packageDetail.provenance.baseline_event_count_for_case}
                            </dd>
                            <dt>Frozen baseline head</dt>
                            <dd className="mono">
                              {packageDetail.provenance.frozen_baseline_head}
                            </dd>
                            <dt>Manifest reference</dt>
                            <dd className="mono">
                              {packageDetail.provenance.manifest_reference}
                            </dd>
                            <dt>Verified manifest hash</dt>
                            <dd className="mono">
                              {packageDetail.provenance.verified_manifest_hash || "UNAVAILABLE"}
                            </dd>
                          </dl>

                          <div className="inspector__raw-disclosure">
                            <button
                              type="button"
                              className="btn btn--secondary btn--compact"
                              aria-expanded={rawJsonOpen}
                              onClick={() => setRawJsonOpen((prev) => !prev)}
                            >
                              {rawJsonOpen ? "Hide structured detail JSON" : "Show structured detail JSON"}
                            </button>
                            {rawJsonOpen && (
                              <pre className="inspector__json mono">
                                {JSON.stringify(packageDetail, null, 2)}
                              </pre>
                            )}
                          </div>
                        </div>
                      )}
                    </section>
                  )}
                </>
              )}
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
