import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "@/api/client";
import {
  appendWorkbenchInvestigationNote,
  getWorkbenchInvestigation,
  getWorkbenchInvestigationHistory,
  listWorkbenchInvestigations,
} from "@/api/endpoints";
import type {
  InvestigationDetail,
  InvestigationHistoryEvent,
  InvestigationHistoryResponse,
  InvestigationSummary,
} from "@/api/contracts";
import { Loading } from "@/components/Loading";
import { ErrorPanel } from "@/components/ErrorPanel";
import { EmptyState } from "@/components/EmptyState";
import "./PmgsyInvestigationsWorkbench.css";

function formatMetric(value: number | string | null | undefined, digits = 3): string {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toFixed(digits) : "N/A";
  }
  return String(value);
}

function shortenHash(hash: string | null | undefined, expanded: boolean): string {
  if (!hash) {
    return "N/A";
  }
  if (expanded || hash.length <= 18) {
    return hash;
  }
  return `${hash.slice(0, 8)}...${hash.slice(-8)}`;
}

export function PmgsyInvestigationsWorkbench(): JSX.Element {
  const navigate = useNavigate();

  const [items, setItems] = useState<InvestigationSummary[]>([]);
  const [loadingList, setLoadingList] = useState<boolean>(true);
  const [listError, setListError] = useState<ApiError | null>(null);

  const [selectedCaseId, setSelectedCaseId] = useState<string>("PEIARS_PMGSY_001");
  const [detail, setDetail] = useState<InvestigationDetail | null>(null);
  const [history, setHistory] = useState<InvestigationHistoryResponse | null>(null);
  const [loadingCase, setLoadingCase] = useState<boolean>(false);
  const [caseError, setCaseError] = useState<ApiError | null>(null);

  // Filters: state, IMS year, queue (P0/P1/P2), disposition, verification, text search.
  // Strictly no LOF/IF or anomaly-score filters.
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [stateFilter, setStateFilter] = useState<string>("");
  const [yearFilter, setYearFilter] = useState<string>("");
  const [queueFilter, setQueueFilter] = useState<string>("");
  const [dispositionFilter, setDispositionFilter] = useState<string>("");
  const [verificationFilter, setVerificationFilter] = useState<string>("");

  // Note form & provenance toggles
  const [reviewerIdInput, setReviewerIdInput] = useState<string>("reviewer_desk_01");
  const [noteInput, setNoteInput] = useState<string>("");
  const [submittingNote, setSubmittingNote] = useState<boolean>(false);
  const [writeError, setWriteError] = useState<string | null>(null);
  const [writeNotice, setWriteNotice] = useState<string | null>(null);
  const [showFullHashes, setShowFullHashes] = useState<boolean>(false);
  const [showRawSummary, setShowRawSummary] = useState<boolean>(false);

  const loadList = useCallback(async (signal?: AbortSignal) => {
    setLoadingList(true);
    setListError(null);
    try {
      const res = await listWorkbenchInvestigations(signal);
      setItems(res.investigations);
      if (res.investigations.length > 0) {
        setSelectedCaseId((prev) =>
          res.investigations.some((c) => c.case_id === prev)
            ? prev
            : res.investigations[0]?.case_id ?? "",
        );
      }
    } catch (err) {
      if ((err as { name?: string })?.name === "AbortError") {
        return;
      }
      setListError(
        err instanceof ApiError
          ? err
          : new ApiError({ status: 500, code: "INTERNAL_ERROR", message: "Unable to load PMGSY investigations.", requestId: null, aborted: false, timedOut: false, network: false }),
      );
    } finally {
      setLoadingList(false);
    }
  }, []);

  const loadCaseBundle = useCallback(async (caseId: string, signal?: AbortSignal) => {
    if (!caseId) {
      return;
    }
    setLoadingCase(true);
    setCaseError(null);
    setWriteError(null);
    try {
      const [det, hist] = await Promise.all([
        getWorkbenchInvestigation(caseId, signal),
        getWorkbenchInvestigationHistory(caseId, signal),
      ]);
      setDetail(det);
      setHistory(hist);
    } catch (err) {
      if ((err as { name?: string })?.name === "AbortError") {
        return;
      }
      setCaseError(
        err instanceof ApiError
          ? err
          : new ApiError({ status: 500, code: "INTERNAL_ERROR", message: "Unable to load investigation case.", requestId: null, aborted: false, timedOut: false, network: false }),
      );
    } finally {
      setLoadingCase(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadList(controller.signal);
    return () => controller.abort();
  }, [loadList]);

  useEffect(() => {
    if (!selectedCaseId) {
      return;
    }
    const controller = new AbortController();
    void loadCaseBundle(selectedCaseId, controller.signal);
    return () => controller.abort();
  }, [selectedCaseId, loadCaseBundle]);

  const stateOptions = useMemo(() => {
    return Array.from(new Set(items.map((x) => x.state).filter(Boolean))).sort();
  }, [items]);

  const yearOptions = useMemo(() => {
    return Array.from(new Set(items.map((x) => x.ims_year).filter(Boolean))).sort();
  }, [items]);

  const dispositionOptions = useMemo(() => {
    return Array.from(new Set(items.map((x) => x.disposition).filter(Boolean))).sort();
  }, [items]);

  const verificationOptions = useMemo(() => {
    return Array.from(new Set(items.map((x) => x.verification_status).filter(Boolean))).sort();
  }, [items]);

  const filteredItems = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return items.filter((row) => {
      if (stateFilter && row.state !== stateFilter) {
        return false;
      }
      if (yearFilter && row.ims_year !== yearFilter) {
        return false;
      }
      if (dispositionFilter && row.disposition !== dispositionFilter) {
        return false;
      }
      if (verificationFilter && row.verification_status !== verificationFilter) {
        return false;
      }
      if (queueFilter) {
        const matchesQueue = row.queues.some((ql) =>
          ql.toUpperCase().startsWith(queueFilter.toUpperCase()),
        );
        if (!matchesQueue) {
          return false;
        }
      }
      if (q) {
        const hay = `${row.case_id} ${row.package_uid} ${row.mrl_id} ${row.state}`.toLowerCase();
        if (!hay.includes(q)) {
          return false;
        }
      }
      return true;
    });
  }, [items, searchQuery, stateFilter, yearFilter, queueFilter, dispositionFilter, verificationFilter]);

  const mergedTimeline = useMemo<InvestigationHistoryEvent[]>(() => {
    if (!history) {
      return [];
    }
    const combined: Array<{ ev: InvestigationHistoryEvent; order: number }> = [];
    history.baseline.events.forEach((ev, idx) => {
      combined.push({ ev, order: idx });
    });
    history.app_stream.events.forEach((ev, idx) => {
      combined.push({ ev, order: 100000 + idx });
    });
    combined.sort((a, b) => {
      const ta = a.ev.timestamp_utc ? Date.parse(a.ev.timestamp_utc) : Number.NaN;
      const tb = b.ev.timestamp_utc ? Date.parse(b.ev.timestamp_utc) : Number.NaN;
      if (!Number.isNaN(ta) && !Number.isNaN(tb) && ta !== tb) {
        return ta - tb;
      }
      return a.order - b.order;
    });
    return combined.map((entry) => entry.ev);
  }, [history]);

  const writesBlockedByIntegrity = useMemo(() => {
    if (!history) {
      return true;
    }
    return (
      !history.writes_allowed ||
      Boolean(history.integrity_error) ||
      !history.baseline.replay_valid ||
      !history.app_stream.replay_valid
    );
  }, [history]);

  const handleClearFilters = (): void => {
    setSearchQuery("");
    setStateFilter("");
    setYearFilter("");
    setQueueFilter("");
    setDispositionFilter("");
    setVerificationFilter("");
  };

  const handleOpenInDataPage = (caseId: string): void => {
    navigate(`/data?case_id=${encodeURIComponent(caseId)}`);
  };

  const handleAppendNote = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setWriteError(null);
    setWriteNotice(null);

    if (!selectedCaseId) {
      return;
    }
    const trimmed = noteInput.trim();
    if (!trimmed) {
      setWriteError("Enter a non-empty reviewer note before appending.");
      return;
    }
    if (writesBlockedByIntegrity) {
      setWriteError(
        history?.integrity_error ||
          "Provenance integrity check failed; writes are disabled until integrity is verified.",
      );
      return;
    }

    setSubmittingNote(true);
    try {
      const res = await appendWorkbenchInvestigationNote(selectedCaseId, {
        note: trimmed,
        reviewer_id: reviewerIdInput.trim() || null,
        expected_app_head_hash: history?.app_stream.current_head ?? null,
        expected_app_event_count: history?.app_stream.event_count ?? null,
      });
      setNoteInput("");
      setWriteNotice(
        `Appended ${res.event.event_id} to separate application stream without altering frozen baseline.`,
      );
      await Promise.all([loadCaseBundle(selectedCaseId), loadList()]);
    } catch (err) {
      if (err instanceof ApiError) {
        setWriteError(`${err.code} (${err.status}): ${err.message}`);
      } else {
        setWriteError("Failed to append reviewer note.");
      }
    } finally {
      setSubmittingNote(false);
    }
  };

  if (loadingList) {
    return <Loading label="Loading PMGSY investigations..." />;
  }

  if (listError) {
    return <ErrorPanel error={listError} onRetry={() => void loadList()} />;
  }

  return (
    <section className="pmgsy-inv-shell" aria-label="PMGSY Case Investigations">
      <div className="pmgsy-inv-header">
        <div>
          <h3>PMGSY-III Case Investigations (42 Curated Cases)</h3>
          <p className="pmgsy-inv-row-meta">
            Screening reasons, evidence-backed disposition, verification status, frozen 162-event baseline, and separate app stream.
          </p>
        </div>
        <div className="pmgsy-action-row">
          <span className="pmgsy-badge">
            Showing {filteredItems.length} of {items.length} cases
          </span>
          <button
            type="button"
            className="pmgsy-btn pmgsy-btn-secondary"
            onClick={() => setShowFullHashes((v) => !v)}
          >
            {showFullHashes ? "Shorten Hashes" : "Expand Full Hashes"}
          </button>
        </div>
      </div>

      <div className="pmgsy-inv-filters" role="region" aria-label="Investigation filters">
        <input
          type="search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search case ID, MRL ID, package UID..."
          aria-label="Search case ID, MRL ID, or package UID"
        />
        <select
          value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value)}
          aria-label="Filter by state"
        >
          <option value="">All states</option>
          {stateOptions.map((st) => (
            <option key={st} value={st}>
              {st}
            </option>
          ))}
        </select>
        <select
          value={yearFilter}
          onChange={(e) => setYearFilter(e.target.value)}
          aria-label="Filter by IMS year"
        >
          <option value="">All IMS years</option>
          {yearOptions.map((yr) => (
            <option key={yr} value={yr}>
              {yr}
            </option>
          ))}
        </select>
        <select
          value={queueFilter}
          onChange={(e) => setQueueFilter(e.target.value)}
          aria-label="Filter by priority queue"
        >
          <option value="">All queues</option>
          <option value="P0">P0</option>
          <option value="P1">P1</option>
          <option value="P2">P2</option>
        </select>
        <select
          value={dispositionFilter}
          onChange={(e) => setDispositionFilter(e.target.value)}
          aria-label="Filter by disposition"
        >
          <option value="">All dispositions</option>
          {dispositionOptions.map((dp) => (
            <option key={dp} value={dp}>
              {dp}
            </option>
          ))}
        </select>
        <select
          value={verificationFilter}
          onChange={(e) => setVerificationFilter(e.target.value)}
          aria-label="Filter by verification status"
        >
          <option value="">All verification statuses</option>
          {verificationOptions.map((vs) => (
            <option key={vs} value={vs}>
              {vs}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="pmgsy-btn pmgsy-btn-secondary"
          onClick={handleClearFilters}
        >
          Clear Filters
        </button>
      </div>

      <div className="pmgsy-inv-grid">
        <div className="pmgsy-inv-list" role="listbox" aria-label="Investigation cases">
          {filteredItems.length === 0 ? (
            <EmptyState>
              No matching cases ? no PMGSY investigation cases match the active filter criteria.
            </EmptyState>
          ) : (
            filteredItems.map((row) => {
              const isSelected = row.case_id === selectedCaseId;
              return (
                <button
                  key={row.case_id}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  className={`pmgsy-inv-row ${isSelected ? "is-selected" : ""}`}
                  onClick={() => setSelectedCaseId(row.case_id)}
                >
                  <div className="pmgsy-inv-row-top">
                    <span>{row.case_id}</span>
                    <span>{row.state || "N/A"}</span>
                  </div>
                  <div className="pmgsy-inv-row-meta">
                    MRL {row.mrl_id || "N/A"} ? IMS {row.ims_year || "N/A"} ? App events: {row.app_event_count}
                  </div>
                  <div className="pmgsy-inv-badges">
                    <span className="pmgsy-badge">Disposition: {row.disposition}</span>
                    <span className="pmgsy-badge">Verification: {row.verification_status}</span>
                  </div>
                </button>
              );
            })
          )}
        </div>

        <div className="pmgsy-inv-card">
          {loadingCase ? (
            <Loading label={`Loading ${selectedCaseId}...`} />
          ) : caseError ? (
            <ErrorPanel error={caseError} onRetry={() => void loadCaseBundle(selectedCaseId)} />
          ) : !detail ? (
            <EmptyState>
              Select a case from the register to inspect screening evidence, disposition, verification, and event history.
            </EmptyState>
          ) : (
            <>
              <div className="pmgsy-inv-header">
                <div>
                  <h4>
                    {detail.identity.case_id} ? MRL {detail.identity.mrl_id || "N/A"}
                  </h4>
                  <p className="pmgsy-inv-row-meta pmgsy-mono">
                    Package UID: {detail.identity.package_uid} ? State: {detail.identity.state} ? IMS Year: {detail.identity.ims_year}
                  </p>
                </div>
                <button
                  type="button"
                  className="pmgsy-btn"
                  onClick={() => handleOpenInDataPage(detail.identity.case_id)}
                >
                  Open source/package record ?
                </button>
              </div>

              <div className="pmgsy-inv-columns">
                <div className="pmgsy-subpanel">
                  <strong>1. Screening (Why it entered review)</strong>
                  <p className="pmgsy-inv-row-meta">
                    Queues: {detail.selection.queues.length > 0 ? detail.selection.queues.join(", ") : "None recorded"}
                  </p>
                  <p className="pmgsy-inv-row-meta">
                    Reasons: {detail.selection.screening_reasons.length > 0 ? detail.selection.screening_reasons.join("; ") : "Recorded in case package"}
                  </p>
                </div>

                <div className="pmgsy-subpanel">
                  <strong>2. Disposition (Evidence-backed outcome)</strong>
                  <p className="pmgsy-inv-row-meta">
                    Baseline disposition: <strong>{detail.review.baseline_disposition}</strong>
                  </p>
                  <p className="pmgsy-inv-row-meta">
                    Baseline case status: {detail.review.baseline_case_status} ? App stream state: {detail.review.current_app_review_state}
                  </p>
                </div>

                <div className="pmgsy-subpanel">
                  <strong>3. Verification (Independent corroboration)</strong>
                  <p className="pmgsy-inv-row-meta">
                    Status: <strong>{detail.verification.verification_status}</strong>
                  </p>
                  <p className="pmgsy-inv-row-meta">
                    Independent of canonical GIS: {detail.verification.independent_of_canonical_gis ? "Yes" : "No"}
                  </p>
                  {detail.verification.verification_status === "VERIFICATION_BLOCKED" && (
                    <div className="pmgsy-blocker-box">
                      <strong>Independent corroboration unavailable</strong>
                      <div>
                        Reason: {detail.verification.blocker_reason || "Required external PMGSY/OMMAS records are absent from the local snapshot."}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="pmgsy-inv-columns">
                <div className="pmgsy-subpanel">
                  <strong>Measurements & Zero-Denominator Rule</strong>
                  <p className="pmgsy-inv-row-meta">
                    Proposed length: {formatMetric(detail.measurements.proposed_l_km)} km
                  </p>
                  <p className="pmgsy-inv-row-meta">
                    Mapped geometry length: {formatMetric(detail.measurements.sum_geom_len_km)} km
                  </p>
                  <p className="pmgsy-inv-row-meta">
                    Signed difference: {formatMetric(detail.measurements.signed_diff_km)} km
                  </p>
                  <p className="pmgsy-inv-row-meta">
                    Relative diff: {formatMetric(detail.measurements.relative_diff)} ({detail.measurements.relative_diff_status})
                  </p>
                </div>

                <div className="pmgsy-subpanel">
                  <strong>Topology & Provenance</strong>
                  <p className="pmgsy-inv-row-meta">
                    Exact duplicate: {detail.topology.exact_geometry_duplicate ? "Yes" : "No"} ? Linear overlap: {detail.topology.linear_overlap ? "Yes" : "No"} ? Invalid geometry: {detail.topology.invalid_geometry ? "Yes" : "No"}
                  </p>
                  <p className="pmgsy-inv-row-meta">
                    Snapshot: <span className="pmgsy-mono">{detail.provenance.snapshot_id}</span> ? Manifest: <span className="pmgsy-mono">{detail.provenance.manifest_reference}</span>
                  </p>
                  <p className="pmgsy-inv-row-meta">
                    Frozen head: <span className="pmgsy-mono">{shortenHash(detail.provenance.frozen_head_hash, showFullHashes)}</span>
                  </p>
                  <button
                    type="button"
                    className="pmgsy-btn pmgsy-btn-secondary"
                    onClick={() => setShowRawSummary((v) => !v)}
                  >
                    {showRawSummary ? "Hide Structured Summary" : "Inspect Structured Summary"}
                  </button>
                  {showRawSummary && (
                    <pre className="pmgsy-mono">
                      {JSON.stringify(
                        {
                          identity: detail.identity,
                          selection: detail.selection,
                          measurements: detail.measurements,
                          topology: detail.topology,
                          verification: detail.verification,
                          provenance: detail.provenance,
                        },
                        null,
                        2,
                      )}
                    </pre>
                  )}
                </div>
              </div>

              {history && (
                <>
                  <div className="pmgsy-integrity-bar">
                    <div>
                      <strong>Frozen baseline</strong>
                      <div>
                        {history.baseline.event_count} events globally ({history.baseline.case_event_count} for case) ? Replay:{" "}
                        {history.baseline.replay_valid ? "PASS" : "FAIL"}
                      </div>
                      <div className="pmgsy-mono">
                        Head: {shortenHash(history.baseline.head_hash, showFullHashes)}
                      </div>
                    </div>
                    <div>
                      <strong>Application stream</strong>
                      <div>
                        {history.app_stream.event_count} case events ? Parent: frozen baseline head ? Replay:{" "}
                        {history.app_stream.replay_valid ? "PASS" : "FAIL"}
                      </div>
                      <div className="pmgsy-mono">
                        Current head: {shortenHash(history.app_stream.current_head, showFullHashes)}
                      </div>
                    </div>
                    <div>
                      <strong>Integrity scope</strong>
                      <div>{history.integrity_note}</div>
                    </div>
                  </div>

                  {writesBlockedByIntegrity && (
                    <div className="pmgsy-integrity-error" role="alert">
                      Provenance integrity failure: {history.integrity_error || "Event chain verification failed"}. Reviewer writes are disabled.
                    </div>
                  )}

                  <h5>Chronological Event History (Frozen Baseline + App Stream)</h5>
                  <ul className="pmgsy-timeline">
                    {mergedTimeline.map((ev) => {
                      const isApp = ev.stream_type === "APPENDED_APP_EVENT";
                      return (
                        <li
                          key={`${ev.stream_type}-${ev.event_id}`}
                          className={`pmgsy-timeline-item ${isApp ? "is-app-event" : "is-baseline-event"}`}
                        >
                          <div className="pmgsy-inv-row-top">
                            <span>
                              {ev.event_type} ? <span className="pmgsy-mono">{ev.event_id}</span>
                            </span>
                            <span
                              className={`pmgsy-badge ${isApp ? "pmgsy-badge-app" : "pmgsy-badge-baseline"}`}
                            >
                              {isApp ? "APPENDED APP EVENT" : "FROZEN BASELINE"}
                            </span>
                          </div>
                          <div className="pmgsy-inv-row-meta">
                            Time: {ev.timestamp_utc || "N/A"} ? Actor: {ev.actor || "N/A"}
                            {(ev.previous_state || ev.new_state) &&
                              ` ? State: ${ev.previous_state || "?"} ? ${ev.new_state || "?"}`}
                          </div>
                          {ev.rationale && (
                            <p className="pmgsy-inv-row-meta">Note / Rationale: {ev.rationale}</p>
                          )}
                          <div className="pmgsy-inv-row-meta pmgsy-mono">
                            Hash: {shortenHash(ev.event_hash, showFullHashes)} ? Prev: {shortenHash(ev.previous_event_hash, showFullHashes)}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </>
              )}

              <form className="pmgsy-note-form" onSubmit={(e) => void handleAppendNote(e)}>
                <strong>Append Reviewer Note (App Stream Only)</strong>
                <input
                  type="text"
                  value={reviewerIdInput}
                  onChange={(e) => setReviewerIdInput(e.target.value)}
                  placeholder="Reviewer identifier"
                  aria-label="Reviewer identifier"
                  disabled={writesBlockedByIntegrity || submittingNote}
                />
                <textarea
                  value={noteInput}
                  onChange={(e) => setNoteInput(e.target.value)}
                  placeholder="Record case-specific review note (appended to separate app event stream)..."
                  aria-label="Reviewer note"
                  disabled={writesBlockedByIntegrity || submittingNote}
                />
                {writeError && (
                  <div className="pmgsy-integrity-error" role="alert">
                    {writeError}
                  </div>
                )}
                {writeNotice && (
                  <div className="pmgsy-badge pmgsy-badge-app" role="status">
                    {writeNotice}
                  </div>
                )}
                <div className="pmgsy-action-row">
                  <button
                    type="submit"
                    className="pmgsy-btn"
                    disabled={writesBlockedByIntegrity || submittingNote}
                  >
                    {submittingNote ? "Appending..." : "Append Reviewer Note"}
                  </button>
                </div>
              </form>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
