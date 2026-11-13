// Investigation Workspace — Evidence Casebook (PR-05B hardened).
//
// Three-region functional layout (preserves the PR-05A visual language):
//   Region 1 (left, 280px):   Record + Case Index
//   Region 2 (centre, 1fr):   Evidence Examination (source record + case detail)
//   Region 3 (right, 340px):  Review + History
//
// Hardening fixes (PR-05B bounded hardening):
//   1. Three-column grid: compound CSS selector guarantees grid wins over
//      the .workspace-composition flex default.
//   2. Draft preservation: forms clear entered text ONLY after confirmed
//      server success (Promise<boolean>). On 409/422/503/network error,
//      the draft is retained so the user can retry or reconcile.
//   3. Source evidence display: when a case is opened, the underlying
//      synthetic record's evidence is resolved through the synthetic
//      source adapter and displayed alongside the case metadata.
//   4. Correct source/status semantics: every synthetic record carries
//      the SYNTHETIC banner; PR-03 statuses and event types are exact.

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/auth/AuthContext";
import { ApiError } from "@/api/client";
import {
  addCaseNote,
  createCase,
  getCase,
  getCaseHistory,
  getSyntheticRecord,
  listCases,
  listSyntheticRecords,
  recordCaseDecision,
  transitionCaseStatus,
} from "@/api/endpoints";
import type {
  CaseDetail,
  CaseHistoryResponse,
  CaseListResponse,
  ReviewStatus,
  SyntheticRecordDetail,
  SyntheticRecordListResponse,
} from "@/api/contracts";
import { readCsrfCookie } from "@/auth/csrf";
import { Loading } from "@/components/Loading";
import { ErrorPanel } from "@/components/ErrorPanel";
import { EmptyState } from "@/components/EmptyState";
import {
  EVENT_LABELS,
  LEGAL_TRANSITIONS,
  STATUS_LABELS,
} from "@/pages/case-model";
import { setDocumentTitle } from "@/utils/title";
import "@/pages/InvestigationsPage.css";

type SelectionKind = "record" | "case" | null;

interface Selection {
  kind: SelectionKind;
  recordRef?: string;
  caseId?: string;
}

export function InvestigationsPage(): JSX.Element {
  const { user, hasPermission } = useAuth();
  const canWrite = hasPermission("cases:write");

  // Region 1 state.
  const [records, setRecords] = useState<SyntheticRecordListResponse | null>(null);
  const [cases, setCases] = useState<CaseListResponse | null>(null);
  const [indexError, setIndexError] = useState<ApiError | null>(null);
  const [loadingIndex, setLoadingIndex] = useState(true);
  const [selection, setSelection] = useState<Selection>({ kind: null });

  // Region 2 state.
  const [recordDetail, setRecordDetail] = useState<SyntheticRecordDetail | null>(null);
  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [caseSourceEvidence, setCaseSourceEvidence] = useState<SyntheticRecordDetail | null>(null);
  const [detailError, setDetailError] = useState<ApiError | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Region 3 state.
  const [history, setHistory] = useState<CaseHistoryResponse | null>(null);
  const [mutationError, setMutationError] = useState<ApiError | null>(null);
  const [mutationPending, setMutationPending] = useState(false);
  const [conflictVersion, setConflictVersion] = useState<number | null>(null);
  // PR-05B final hardening: sync warnings are SEPARATE from mutation errors.
  // A sync warning means the write succeeded but a follow-up GET failed.
  const [historySyncWarning, setHistorySyncWarning] = useState(false);
  const [indexSyncWarning, setIndexSyncWarning] = useState(false);
  // Ref-backed generation counter: increments on every selection change.
  // Using a ref (not state) ensures async callbacks read the CURRENT value
  // at callback-execution time, not the value captured by the render closure
  // at useCallback creation time. This is the key fix for the stale-async
  // response guard: a state-based comparison would always compare the same
  // captured value and never detect a selection change.
  const selectionGenRef = useRef(0);

  // Separate ref-backed generation counter for index-refresh requests.
  // Every new refreshIndex call increments this counter. Only the most
  // recent request may update records, cases, indexError, or loadingIndex.
  // Older responses (success or failure) are silently discarded.
  const indexGenRef = useRef(0);

  useEffect(() => {
    setDocumentTitle("Investigation Workspace");
  }, []);

  // --- Region 1: load records + cases on mount ---
  const refreshIndex = useCallback(async () => {
    // Increment the index generation counter. Only the most recent request
    // may update records, cases, indexError, or loadingIndex. Older
    // responses (success or failure) are silently discarded.
    const gen = ++indexGenRef.current;
    setLoadingIndex(true);
    setIndexError(null);
    const controller = new AbortController();
    try {
      const [recs, cs] = await Promise.all([
        listSyntheticRecords(controller.signal),
        listCases({ limit: 50, offset: 0, signal: controller.signal }),
      ]);
      // Stale guard: discard if a newer request has started.
      if (indexGenRef.current !== gen) return;
      setRecords(recs);
      setCases(cs);
    } catch (err) {
      if (err instanceof ApiError && err.aborted) return;
      // Stale guard: discard if a newer request has started.
      if (indexGenRef.current !== gen) return;
      setIndexError(err instanceof ApiError ? err : null);
      // Re-throw so callers (e.g. mutation handlers) can catch and set
      // a sync warning. The indexError state is set for the Region 1
      // error panel; the re-throw lets the mutation handler distinguish
      // "write succeeded, sync failed" from "write failed".
      throw err;
    } finally {
      // Stale guard: only clear loading if this is still the latest request.
      if (indexGenRef.current === gen && !controller.signal.aborted) {
        setLoadingIndex(false);
      }
    }
  }, []);

  useEffect(() => {
    // Fix 2: catch the re-throw from refreshIndex to prevent an unhandled
    // promise rejection on mount. The indexError state is already set
    // inside refreshIndex for the Region 1 error panel.
    refreshIndex().catch(() => {});
  }, [refreshIndex]);

  // --- Region 2: load detail when selection changes ---
  // Bump the ref-backed generation counter on every selection change so
  // that stale async reads from a previous selection can be detected and
  // discarded at callback-execution time (not render-closure time).
  useEffect(() => {
    selectionGenRef.current += 1;
  }, [selection]);

  useEffect(() => {
    // Capture the generation at effect-start. Async callbacks check this
    // against the ref's CURRENT value before applying results, preventing
    // stale responses from a previous selection from overwriting the
    // currently-displayed case.
    const gen = selectionGenRef.current;
    if (selection.kind === "record" && selection.recordRef) {
      const recordRef = selection.recordRef;
      setLoadingDetail(true);
      setDetailError(null);
      setRecordDetail(null);
      setCaseDetail(null);
      setCaseSourceEvidence(null);
      const controller = new AbortController();
      (async () => {
        try {
          const detail = await getSyntheticRecord(recordRef, controller.signal);
          if (selectionGenRef.current !== gen) return; // stale
          setRecordDetail(detail);
        } catch (err) {
          if (err instanceof ApiError && err.aborted) return;
          if (selectionGenRef.current !== gen) return; // stale
          setDetailError(err instanceof ApiError ? err : null);
        } finally {
          if (selectionGenRef.current === gen && !controller.signal.aborted) setLoadingDetail(false);
        }
      })();
      return () => controller.abort();
    }
    if (selection.kind === "case" && selection.caseId) {
      const caseId = selection.caseId;
      setLoadingDetail(true);
      setDetailError(null);
      setRecordDetail(null);
      setCaseDetail(null);
      setCaseSourceEvidence(null);
      setHistory(null);
      const controller = new AbortController();
      (async () => {
        try {
          const [detail, hist] = await Promise.all([
            getCase(caseId, controller.signal),
            getCaseHistory(caseId, controller.signal),
          ]);
          if (selectionGenRef.current !== gen) return; // stale
          setCaseDetail(detail);
          setHistory(hist);
          try {
            const sourceEvidence = await getSyntheticRecord(detail.record_ref, controller.signal);
            if (selectionGenRef.current !== gen) return; // stale
            setCaseSourceEvidence(sourceEvidence);
          } catch {
            if (selectionGenRef.current === gen) setCaseSourceEvidence(null);
          }
        } catch (err) {
          if (err instanceof ApiError && err.aborted) return;
          if (selectionGenRef.current !== gen) return; // stale
          setDetailError(err instanceof ApiError ? err : null);
        } finally {
          if (selectionGenRef.current === gen && !controller.signal.aborted) setLoadingDetail(false);
        }
      })();
      return () => controller.abort();
    }
    setRecordDetail(null);
    setCaseDetail(null);
    setCaseSourceEvidence(null);
    setHistory(null);
  }, [selection]);

  // --- Region 3: mutations (return Promise<boolean> for draft preservation) ---

  const csrfToken = readCsrfCookie();

  const handleCreateCase = useCallback(
    async (title: string, summary: string): Promise<boolean> => {
      if (!recordDetail || !csrfToken) return false;
      setMutationPending(true);
      setMutationError(null);
      setConflictVersion(null);
      try {
        const created = await createCase(
          {
            dataset_id: recordDetail.dataset_id,
            snapshot_id: recordDetail.snapshot_id,
            record_ref: recordDetail.record_ref,
            title,
            summary: summary || undefined,
            created_by: "client",
          },
          csrfToken,
        );
        // POST succeeded — the write is confirmed. Return true immediately
        // so the form clears the draft. Sync operations run independently;
        // their failure sets a sync warning, NOT a mutation error.
        // Sync: refresh the case list (non-blocking).
        refreshIndex().catch(() => {
          setIndexSyncWarning(true);
        });
        setSelection({ kind: "case", caseId: created.id });
        return true;
      } catch (err) {
        if (err instanceof ApiError && err.isNetwork) {
          // Uncertain: the POST may or may not have been committed.
          setMutationError(err);
        } else {
          setMutationError(err instanceof ApiError ? err : null);
        }
        return false;
      } finally {
        setMutationPending(false);
      }
    },
    [recordDetail, csrfToken, refreshIndex],
  );

  const handleAddNote = useCallback(
    async (noteText: string): Promise<boolean> => {
      if (!caseDetail || !csrfToken) return false;
      const currentCaseId = caseDetail.id;
      const currentGen = selectionGenRef.current;
      setMutationPending(true);
      setMutationError(null);
      setConflictVersion(null);
      setHistorySyncWarning(false);
      setIndexSyncWarning(false);
      try {
        const updated = await addCaseNote(
          currentCaseId,
          {
            note_text: noteText,
            actor_ref: "client",
            expected_version: caseDetail.version,
          },
          csrfToken,
        );
        // POST succeeded — the write is confirmed. Update case state from
        // the server response and return true immediately.
        setCaseDetail(updated);
        // Sync: refresh history (non-blocking; failure → sync warning).
        getCaseHistory(updated.id)
          .then((hist) => {
            // Generation guard: don't overwrite if the user switched cases.
            if (selectionGenRef.current === currentGen) {
              setHistory(hist);
              setHistorySyncWarning(false);
            }
          })
          .catch(() => {
            if (selectionGenRef.current === currentGen) {
              setHistorySyncWarning(true);
            }
          });
        // Sync: refresh case list (non-blocking; failure → sync warning).
        refreshIndex().catch(() => {
          if (selectionGenRef.current === currentGen) {
            setIndexSyncWarning(true);
          }
        });
        return true;
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          setConflictVersion(caseDetail.version);
        }
        setMutationError(err instanceof ApiError ? err : null);
        return false;
      } finally {
        setMutationPending(false);
      }
    },
    [caseDetail, csrfToken, refreshIndex],
  );

  const handleTransition = useCallback(
    async (toStatus: ReviewStatus, reason: string): Promise<boolean> => {
      if (!caseDetail || !csrfToken) return false;
      const currentCaseId = caseDetail.id;
      const currentGen = selectionGenRef.current;
      setMutationPending(true);
      setMutationError(null);
      setConflictVersion(null);
      setHistorySyncWarning(false);
      setIndexSyncWarning(false);
      try {
        const updated = await transitionCaseStatus(
          currentCaseId,
          {
            to_status: toStatus,
            reason,
            actor_ref: "client",
            expected_version: caseDetail.version,
          },
          csrfToken,
        );
        setCaseDetail(updated);
        getCaseHistory(updated.id)
          .then((hist) => {
            if (selectionGenRef.current === currentGen) {
              setHistory(hist);
              setHistorySyncWarning(false);
            }
          })
          .catch(() => {
            if (selectionGenRef.current === currentGen) {
              setHistorySyncWarning(true);
            }
          });
        refreshIndex().catch(() => {
          if (selectionGenRef.current === currentGen) {
            setIndexSyncWarning(true);
          }
        });
        return true;
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          setConflictVersion(caseDetail.version);
        }
        setMutationError(err instanceof ApiError ? err : null);
        return false;
      } finally {
        setMutationPending(false);
      }
    },
    [caseDetail, csrfToken, refreshIndex],
  );

  const handleDecision = useCallback(
    async (outcome: ReviewStatus, rationale: string): Promise<boolean> => {
      if (!caseDetail || !csrfToken) return false;
      const currentCaseId = caseDetail.id;
      const currentGen = selectionGenRef.current;
      setMutationPending(true);
      setMutationError(null);
      setConflictVersion(null);
      setHistorySyncWarning(false);
      setIndexSyncWarning(false);
      try {
        const updated = await recordCaseDecision(
          currentCaseId,
          {
            outcome,
            rationale,
            actor_ref: "client",
            expected_version: caseDetail.version,
          },
          csrfToken,
        );
        setCaseDetail(updated);
        getCaseHistory(updated.id)
          .then((hist) => {
            if (selectionGenRef.current === currentGen) {
              setHistory(hist);
              setHistorySyncWarning(false);
            }
          })
          .catch(() => {
            if (selectionGenRef.current === currentGen) {
              setHistorySyncWarning(true);
            }
          });
        refreshIndex().catch(() => {
          if (selectionGenRef.current === currentGen) {
            setIndexSyncWarning(true);
          }
        });
        return true;
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          setConflictVersion(caseDetail.version);
        }
        setMutationError(err instanceof ApiError ? err : null);
        return false;
      } finally {
        setMutationPending(false);
      }
    },
    [caseDetail, csrfToken, refreshIndex],
  );

  // --- Recovery actions (GET-only; never POST) ---

  const handleRefreshHistory = useCallback(async () => {
    if (!caseDetail) return;
    const currentGen = selectionGenRef.current;
    try {
      const hist = await getCaseHistory(caseDetail.id);
      if (selectionGenRef.current === currentGen) {
        setHistory(hist);
        setHistorySyncWarning(false);
      }
    } catch {
      // Warning stays; the user can retry.
    }
  }, [caseDetail]);

  const handleRefreshCaseList = useCallback(async () => {
    try {
      await refreshIndex();
      // If we get here, refreshIndex succeeded (or was aborted — treat as
      // success since the user can retry).
      setIndexSyncWarning(false);
    } catch {
      // Warning stays; the user can retry.
    }
  }, [refreshIndex]);

  const handleReloadAfterConflict = useCallback(async () => {
    if (!caseDetail) return;
    // PR-07A D1: capture the selection generation at handler entry. Every
    // other async read path on this page is guarded by selectionGenRef;
    // the conflict-recovery path must be too — a recovery response that
    // settles after the user selected a different case must not overwrite
    // the new selection's detail/history or clear its loading state.
    const currentGen = selectionGenRef.current;
    setMutationError(null);
    setConflictVersion(null);
    setLoadingDetail(true);
    try {
      const [detail, hist] = await Promise.all([
        getCase(caseDetail.id),
        getCaseHistory(caseDetail.id),
      ]);
      if (selectionGenRef.current !== currentGen) return; // stale selection
      setCaseDetail(detail);
      setHistory(hist);
    } catch (err) {
      if (selectionGenRef.current !== currentGen) return; // stale selection
      setDetailError(err instanceof ApiError ? err : null);
    } finally {
      if (selectionGenRef.current === currentGen) {
        setLoadingDetail(false);
      }
    }
  }, [caseDetail]);

  const noSelection = selection.kind === null;

  return (
    <div className="investigations-page workspace-composition" data-testid="investigations-page">
      <Region1Index
        records={records}
        cases={cases}
        loading={loadingIndex}
        error={indexError}
        selection={selection}
        onSelect={setSelection}
        onRetry={refreshIndex}
      />
      <Region2Evidence
        selection={selection}
        recordDetail={recordDetail}
        caseDetail={caseDetail}
        caseSourceEvidence={caseSourceEvidence}
        loading={loadingDetail}
        error={detailError}
        noSelection={noSelection}
      />
      <Region3Review
        selection={selection}
        caseDetail={caseDetail}
        history={history}
        canWrite={canWrite}
        userRole={user?.role}
        mutationPending={mutationPending}
        mutationError={mutationError}
        conflictVersion={conflictVersion}
        historySyncWarning={historySyncWarning}
        indexSyncWarning={indexSyncWarning}
        onCreateCase={handleCreateCase}
        onAddNote={handleAddNote}
        onTransition={handleTransition}
        onDecision={handleDecision}
        onReloadAfterConflict={handleReloadAfterConflict}
        onRefreshHistory={handleRefreshHistory}
        onRefreshCaseList={handleRefreshCaseList}
      />
    </div>
  );
}

// ===========================================================================
// Region 1 — Record + Case Index
// ===========================================================================

interface Region1Props {
  records: SyntheticRecordListResponse | null;
  cases: CaseListResponse | null;
  loading: boolean;
  error: ApiError | null;
  selection: Selection;
  onSelect: (s: Selection) => void;
  onRetry: () => void;
}

function Region1Index(props: Region1Props): JSX.Element {
  return (
    <aside className="inv__index panel" aria-label="Record and case index" data-testid="region-index">
      <div className="panel__header">
        <span className="panel__title">Index</span>
      </div>
      <div className="panel__body panel__body--flush inv__index-body">
        {props.loading && !props.records ? (
          <Loading label="Loading index…" />
        ) : props.error ? (
          <ErrorPanel error={props.error} onRetry={props.onRetry} />
        ) : (
          <>
            <section className="inv__index-section">
              <h3 className="inv__index-heading">Demonstration records</h3>
              {props.records && props.records.items.length > 0 ? (
                <ul className="inv__index-list">
                  {props.records.items.map((r) => {
                    const isActive =
                      props.selection.kind === "record" && props.selection.recordRef === r.record_ref;
                    return (
                      <li key={r.record_ref}>
                        <button
                          type="button"
                          className={`inv__index-item ${isActive ? "is-active" : ""}`}
                          aria-current={isActive ? "true" : undefined}
                          onClick={() => props.onSelect({ kind: "record", recordRef: r.record_ref })}
                        >
                          <span className="inv__index-item-id mono">{r.record_ref}</span>
                          <span className="inv__index-item-label">Synthetic record</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <EmptyState>No demonstration records available.</EmptyState>
              )}
            </section>
            <section className="inv__index-section">
              <h3 className="inv__index-heading">Review cases</h3>
              {props.cases && props.cases.items.length > 0 ? (
                <ul className="inv__index-list">
                  {props.cases.items.map((c) => {
                    const isActive =
                      props.selection.kind === "case" && props.selection.caseId === c.id;
                    return (
                      <li key={c.id}>
                        <button
                          type="button"
                          className={`inv__index-item ${isActive ? "is-active" : ""}`}
                          aria-current={isActive ? "true" : undefined}
                          onClick={() => props.onSelect({ kind: "case", caseId: c.id })}
                        >
                          <span className="inv__index-item-id mono">{c.title}</span>
                          <span className="inv__index-item-label">
                            {STATUS_LABELS[c.status]} · v{c.version}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <EmptyState>No cases yet. Select a record to create one.</EmptyState>
              )}
            </section>
          </>
        )}
      </div>
    </aside>
  );
}

// ===========================================================================
// Region 2 — Evidence Examination
// ===========================================================================

interface Region2Props {
  selection: Selection;
  recordDetail: SyntheticRecordDetail | null;
  caseDetail: CaseDetail | null;
  caseSourceEvidence: SyntheticRecordDetail | null;
  loading: boolean;
  error: ApiError | null;
  noSelection: boolean;
}

function Region2Evidence(props: Region2Props): JSX.Element {
  return (
    <section className="inv__evidence panel" aria-label="Evidence examination" data-testid="region-evidence">
      <div className="panel__header">
        <span className="panel__title">
          {props.selection.kind === "record"
            ? "Record evidence"
            : props.selection.kind === "case"
              ? "Case evidence"
              : "Evidence"}
        </span>
      </div>
      <div className="panel__body inv__evidence-body">
        {props.noSelection ? (
          <EmptyState>
            Select a demonstration record or an existing case from the index to inspect its evidence.
          </EmptyState>
        ) : props.loading ? (
          <Loading label="Loading evidence…" />
        ) : props.error ? (
          <ErrorPanel error={props.error} />
        ) : props.recordDetail ? (
          <RecordEvidenceView record={props.recordDetail} />
        ) : props.caseDetail ? (
          <CaseEvidenceView caseDetail={props.caseDetail} sourceEvidence={props.caseSourceEvidence} />
        ) : (
          <EmptyState>No evidence available.</EmptyState>
        )}
      </div>
    </section>
  );
}

function RecordEvidenceView({ record }: { record: SyntheticRecordDetail }): JSX.Element {
  return (
    <div className="inv__evidence-content">
      <div className="inv__synthetic-banner" role="note">
        {record.title}
      </div>
      <dl className="def-list">
        <dt className="def-list__term">Record ref</dt>
        <dd className="def-list__def mono">{record.record_ref}</dd>
        <dt className="def-list__term">Dataset</dt>
        <dd className="def-list__def mono">{record.dataset_id}</dd>
        <dt className="def-list__term">Snapshot</dt>
        <dd className="def-list__def mono">{record.snapshot_id}</dd>
        <dt className="def-list__term">Synthetic</dt>
        <dd className="def-list__def mono">{record.synthetic ? "true" : "false"}</dd>
      </dl>
      <h3 className="section-h4">Description</h3>
      <p className="editorial-muted">{record.description}</p>
      <h3 className="section-h4">Evidence summary</h3>
      <p className="editorial-muted">{record.evidence_summary}</p>
      <h3 className="section-h4">Administrative context</h3>
      <p className="editorial-muted">{record.administrative_context}</p>
      <h3 className="section-h4">Scientific limitations</h3>
      <p className="editorial-muted">{record.limitations}</p>
    </div>
  );
}

function CaseEvidenceView({
  caseDetail,
  sourceEvidence,
}: {
  caseDetail: CaseDetail;
  sourceEvidence: SyntheticRecordDetail | null;
}): JSX.Element {
  return (
    <div className="inv__evidence-content">
      <h2 className="inv__case-title">{caseDetail.title}</h2>
      <div className="inv__synthetic-banner" role="note">
        The underlying record is a SYNTHETIC DEMONSTRATION RECORD — NOT A RESEARCH FINDING.
      </div>

      <h3 className="section-h4">Case metadata</h3>
      <dl className="def-list">
        <dt className="def-list__term">Case ID</dt>
        <dd className="def-list__def mono">{caseDetail.id}</dd>
        <dt className="def-list__term">Status</dt>
        <dd className="def-list__def">{STATUS_LABELS[caseDetail.status]}</dd>
        <dt className="def-list__term">Version</dt>
        <dd className="def-list__def mono">{caseDetail.version}</dd>
        <dt className="def-list__term">Record ref</dt>
        <dd className="def-list__def mono">{caseDetail.record_ref}</dd>
        <dt className="def-list__term">Dataset</dt>
        <dd className="def-list__def mono">{caseDetail.dataset_id}</dd>
        <dt className="def-list__term">Snapshot</dt>
        <dd className="def-list__def mono">{caseDetail.snapshot_id}</dd>
        <dt className="def-list__term">Created by</dt>
        <dd className="def-list__def mono">{caseDetail.created_by}</dd>
        <dt className="def-list__term">Created at</dt>
        <dd className="def-list__def mono">{caseDetail.created_at}</dd>
        <dt className="def-list__term">Updated at</dt>
        <dd className="def-list__def mono">{caseDetail.updated_at}</dd>
      </dl>
      {caseDetail.summary && (
        <>
          <h3 className="section-h4">Case summary</h3>
          <p className="editorial-muted">{caseDetail.summary}</p>
        </>
      )}

      {/* PR-05B §3: display the underlying source evidence alongside case details.
          Clearly distinguished from case metadata by the "Source evidence" heading
          and the SYNTHETIC banner. If the source evidence is unavailable, display
          an honest message without fabricating it. */}
      {sourceEvidence ? (
        <>
          <h3 className="section-h4">Source evidence (read-only)</h3>
          <dl className="def-list">
            <dt className="def-list__term">Record ref</dt>
            <dd className="def-list__def mono">{sourceEvidence.record_ref}</dd>
          </dl>
          <p className="editorial-muted inv__source-evidence-desc">{sourceEvidence.description}</p>
          <p className="editorial-muted">
            <strong>Evidence summary:</strong> {sourceEvidence.evidence_summary}
          </p>
          <p className="editorial-muted">
            <strong>Administrative context:</strong> {sourceEvidence.administrative_context}
          </p>
          <p className="editorial-muted">
            <strong>Scientific limitations:</strong> {sourceEvidence.limitations}
          </p>
        </>
      ) : (
        <>
          <h3 className="section-h4">Source evidence</h3>
          <p className="editorial-muted inv__source-unavailable">
            The underlying source evidence for this case's record reference is not
            available. This may occur when the demonstration source is disabled or
            the record has been removed. Case metadata and history remain available.
          </p>
        </>
      )}
    </div>
  );
}

// ===========================================================================
// Region 3 — Review + History
// ===========================================================================

interface Region3Props {
  selection: Selection;
  caseDetail: CaseDetail | null;
  history: CaseHistoryResponse | null;
  canWrite: boolean;
  userRole?: string;
  mutationPending: boolean;
  mutationError: ApiError | null;
  conflictVersion: number | null;
  historySyncWarning: boolean;
  indexSyncWarning: boolean;
  onCreateCase: (title: string, summary: string) => Promise<boolean>;
  onAddNote: (noteText: string) => Promise<boolean>;
  onTransition: (toStatus: ReviewStatus, reason: string) => Promise<boolean>;
  onDecision: (outcome: ReviewStatus, rationale: string) => Promise<boolean>;
  onReloadAfterConflict: () => void;
  onRefreshHistory: () => void;
  onRefreshCaseList: () => void;
}

function Region3Review(props: Region3Props): JSX.Element {
  return (
    <aside className="inv__review panel" aria-label="Review and history" data-testid="region-review">
      <div className="panel__header">
        <span className="panel__title">Review &amp; history</span>
        {props.userRole && <span className="panel__title mono">{props.userRole.toUpperCase()}</span>}
      </div>
      <div className="panel__body inv__review-body">
        {props.mutationError && (
          <ErrorPanel
            error={props.mutationError}
            title={
              props.conflictVersion !== null
                ? "Concurrency conflict"
                : props.mutationError.isNetwork
                  ? "Write outcome unknown"
                  : "Operation failed"
            }
          >
            {props.conflictVersion !== null && (
              <button
                type="button"
                className="btn btn-secondary btn-compact"
                onClick={props.onReloadAfterConflict}
                disabled={props.mutationPending}
              >
                Reload latest version
              </button>
            )}
            {props.mutationError.isNetwork && (
              <p className="editorial-muted inv__sync-hint">
                The connection failed before the server confirmed the result.
                Reload the case to reconcile the current state before retrying.
              </p>
            )}
          </ErrorPanel>
        )}

        {/* Sync warnings: the write succeeded, but a follow-up GET failed.
            These are NOT mutation errors — the draft was already cleared. */}
        {props.historySyncWarning && (
          <div className="inv__sync-warning" role="alert" aria-live="polite">
            <p className="inv__sync-warning-text">
              Saved successfully, but history could not refresh.
            </p>
            <button
              type="button"
              className="btn btn-secondary btn-compact"
              onClick={props.onRefreshHistory}
              disabled={props.mutationPending}
            >
              Refresh history
            </button>
          </div>
        )}
        {props.indexSyncWarning && (
          <div className="inv__sync-warning" role="alert" aria-live="polite">
            <p className="inv__sync-warning-text">
              Saved successfully, but case list could not refresh.
            </p>
            <button
              type="button"
              className="btn btn-secondary btn-compact"
              onClick={props.onRefreshCaseList}
              disabled={props.mutationPending}
            >
              Refresh case list
            </button>
          </div>
        )}

        {props.selection.kind === "record" && props.canWrite && (
          <CreateCaseForm pending={props.mutationPending} onCreate={props.onCreateCase} />
        )}

        {props.selection.kind === "record" && !props.canWrite && (
          <div className="inv__readonly-note">
            <p className="editorial-muted">
              You do not have permission to create cases. A reviewer or admin role is required.
            </p>
          </div>
        )}

        {props.selection.kind === "case" && props.caseDetail && (
          <>
            {props.canWrite ? (
              <>
                <NoteForm
                  pending={props.mutationPending}
                  onAdd={props.onAddNote}
                  currentVersion={props.caseDetail.version}
                />
                <TransitionForm
                  currentStatus={props.caseDetail.status}
                  pending={props.mutationPending}
                  onTransition={props.onTransition}
                />
                <DecisionForm
                  currentStatus={props.caseDetail.status}
                  pending={props.mutationPending}
                  onDecision={props.onDecision}
                />
              </>
            ) : (
              <div className="inv__readonly-note">
                <p className="editorial-muted">
                  You have read-only access. Mutations require the reviewer or admin role.
                </p>
              </div>
            )}
            <CaseHistoryView history={props.history} />
          </>
        )}

        {props.selection.kind === null && (
          <EmptyState>Select a record or case to begin.</EmptyState>
        )}
      </div>
    </aside>
  );
}

// --- Sub-forms (draft preservation: clear only on confirmed success) ---

function CreateCaseForm({
  pending,
  onCreate,
}: {
  pending: boolean;
  onCreate: (title: string, summary: string) => Promise<boolean>;
}): JSX.Element {
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const canSubmit = title.trim().length >= 1 && !pending;
  return (
    <form
      className="inv__form"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!canSubmit) return;
        const success = await onCreate(title.trim(), summary.trim());
        // Clear the draft ONLY on confirmed server success.
        if (success) {
          setTitle("");
          setSummary("");
        }
      }}
    >
      <h3 className="section-h4">Create review case</h3>
      <div className="field">
        <label className="field__label" htmlFor="case-title">Title</label>
        <input
          id="case-title"
          type="text"
          className="field__input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={240}
          required
          disabled={pending}
        />
      </div>
      <div className="field">
        <label className="field__label" htmlFor="case-summary">Summary (optional)</label>
        <textarea
          id="case-summary"
          className="field__input field__input--textarea"
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          maxLength={4000}
          rows={3}
          disabled={pending}
        />
      </div>
      <button type="submit" className="btn btn-primary btn-compact" disabled={!canSubmit}>
        {pending ? "Working…" : "Create case"}
      </button>
    </form>
  );
}

function NoteForm({
  pending,
  onAdd,
  currentVersion,
}: {
  pending: boolean;
  onAdd: (noteText: string) => Promise<boolean>;
  currentVersion: number;
}): JSX.Element {
  const [note, setNote] = useState("");
  const canSubmit = note.trim().length >= 1 && !pending;
  return (
    <form
      className="inv__form"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!canSubmit) return;
        const success = await onAdd(note.trim());
        if (success) {
          setNote("");
        }
      }}
    >
      <h3 className="section-h4">Add note (v{currentVersion})</h3>
      <div className="field">
        <label className="field__label" htmlFor="note-text">Note</label>
        <textarea
          id="note-text"
          className="field__input field__input--textarea"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={4000}
          rows={3}
          required
          disabled={pending}
        />
      </div>
      <button type="submit" className="btn btn-primary btn-compact" disabled={!canSubmit}>
        {pending ? "Working…" : "Add note"}
      </button>
    </form>
  );
}

function TransitionForm({
  currentStatus,
  pending,
  onTransition,
}: {
  currentStatus: ReviewStatus;
  pending: boolean;
  onTransition: (toStatus: ReviewStatus, reason: string) => Promise<boolean>;
}): JSX.Element {
  const targets = LEGAL_TRANSITIONS[currentStatus] ?? [];
  const [target, setTarget] = useState<ReviewStatus>(targets[0] ?? "under_review");
  const [reason, setReason] = useState("");
  const canSubmit = targets.length > 0 && reason.trim().length >= 1 && !pending;

  useEffect(() => {
    setTarget(targets[0] ?? "under_review");
  }, [currentStatus]); // eslint-disable-line react-hooks/exhaustive-deps

  if (targets.length === 0) {
    return (
      <div className="inv__form inv__form--disabled">
        <h3 className="section-h4">Transition status</h3>
        <p className="editorial-muted">No legal forward transitions from {STATUS_LABELS[currentStatus]}.</p>
      </div>
    );
  }

  return (
    <form
      className="inv__form"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!canSubmit) return;
        const success = await onTransition(target, reason.trim());
        if (success) {
          setReason("");
        }
      }}
    >
      <h3 className="section-h4">Transition status</h3>
      <div className="field">
        <label className="field__label" htmlFor="transition-target">Target status</label>
        <select
          id="transition-target"
          className="field__input"
          value={target}
          onChange={(e) => setTarget(e.target.value as ReviewStatus)}
          disabled={pending}
        >
          {targets.map((t) => (
            <option key={t} value={t}>{STATUS_LABELS[t]}</option>
          ))}
        </select>
      </div>
      <div className="field">
        <label className="field__label" htmlFor="transition-reason">Reason</label>
        <input
          id="transition-reason"
          type="text"
          className="field__input"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={1000}
          required
          disabled={pending}
        />
      </div>
      <button type="submit" className="btn btn-primary btn-compact" disabled={!canSubmit}>
        {pending ? "Working…" : "Apply transition"}
      </button>
    </form>
  );
}

function DecisionForm({
  currentStatus,
  pending,
  onDecision,
}: {
  currentStatus: ReviewStatus;
  pending: boolean;
  onDecision: (outcome: ReviewStatus, rationale: string) => Promise<boolean>;
}): JSX.Element {
  const targets = LEGAL_TRANSITIONS[currentStatus] ?? [];
  const [outcome, setOutcome] = useState<ReviewStatus>(targets[0] ?? "under_review");
  const [rationale, setRationale] = useState("");
  const canSubmit = targets.length > 0 && rationale.trim().length >= 1 && !pending;

  useEffect(() => {
    setOutcome(targets[0] ?? "under_review");
  }, [currentStatus]); // eslint-disable-line react-hooks/exhaustive-deps

  if (targets.length === 0) {
    return <></>;
  }

  return (
    <form
      className="inv__form"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!canSubmit) return;
        const success = await onDecision(outcome, rationale.trim());
        if (success) {
          setRationale("");
        }
      }}
    >
      <h3 className="section-h4">Record decision</h3>
      <div className="field">
        <label className="field__label" htmlFor="decision-outcome">Outcome</label>
        <select
          id="decision-outcome"
          className="field__input"
          value={outcome}
          onChange={(e) => setOutcome(e.target.value as ReviewStatus)}
          disabled={pending}
        >
          {targets.map((t) => (
            <option key={t} value={t}>{STATUS_LABELS[t]}</option>
          ))}
        </select>
      </div>
      <div className="field">
        <label className="field__label" htmlFor="decision-rationale">Rationale</label>
        <textarea
          id="decision-rationale"
          className="field__input field__input--textarea"
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          maxLength={4000}
          rows={3}
          required
          disabled={pending}
        />
      </div>
      <button type="submit" className="btn btn-primary btn-compact" disabled={!canSubmit}>
        {pending ? "Working…" : "Record decision"}
      </button>
    </form>
  );
}

function CaseHistoryView({ history }: { history: CaseHistoryResponse | null }): JSX.Element {
  if (!history) {
    return (
      <div className="inv__history">
        <h3 className="section-h4">Event history</h3>
        <Loading label="Loading history…" />
      </div>
    );
  }
  return (
    <div className="inv__history">
      <h3 className="section-h4">Event history ({history.total})</h3>
      {history.items.length === 0 ? (
        <EmptyState>No events.</EmptyState>
      ) : (
        <ol className="inv__history-list">
          {history.items.map((e) => (
            <li key={e.id} className="inv__history-item">
              <div className="inv__history-row">
                <span className="inv__history-event mono">{EVENT_LABELS[e.event_type]}</span>
                <span className="inv__history-version mono">v{e.case_version}</span>
              </div>
              <div className="inv__history-meta">
                <span className="mono">{e.event_at}</span>
                <span className="mono">actor: {e.actor_ref}</span>
              </div>
              {e.previous_status && e.new_status && (
                <div className="inv__history-transition mono">
                  {STATUS_LABELS[e.previous_status]} → {STATUS_LABELS[e.new_status]}
                </div>
              )}
              {e.reason && <div className="inv__history-reason">{e.reason}</div>}
              {e.event_payload && typeof e.event_payload.note_text === "string" && (
                <div className="inv__history-note">{e.event_payload.note_text}</div>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
