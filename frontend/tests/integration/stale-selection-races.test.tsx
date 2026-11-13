// PR-07A Workstream B — stale case-selection response tests (B1/B2/B4)
// and Workstream E extension (E4: no automatic second POST after an
// uncertain network outcome).
//
// All orchestration is deterministic: deferred promises with explicit
// resolution order and microtask flushing. No setTimeout-based race
// orchestration, no React StrictMode double-effects, no real clocks.
//
// Expected classifications (PR-07A A5):
//   - B1: BASELINE GREEN (the selection-load effect is generation-
//     guarded; this is the sleep-free re-implementation required by
//     the audit).
//   - B2: BASELINE GREEN (the nested evidence GET is guarded at
//     InvestigationsPage.tsx:207 — previously untested).
//   - B4: BASELINE GREEN (abort-aware unmount; previously untested).
//   - E4: BASELINE GREEN (client has no retry logic; the explicit
//     no-second-POST assertion was previously implicit).

import { cleanup, screen, waitFor, act, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  REVIEWER_USER,
  type FetchRoute,
  authenticatedRoutes,
  renderApp,
  setCookieJar,
} from "../helpers/renderApp";
import { CSRF_COOKIE_NAME } from "@/api/contracts";

function setWindowWidth(width: number): void {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    writable: true,
    value: width,
  });
  window.dispatchEvent(new Event("resize"));
}

const CASE_A_ID = "00000000-0000-0000-0000-000000000001";
const CASE_B_ID = "00000000-0000-0000-0000-000000000002";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "X-Request-ID": "r" },
  });
}

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (v: T) => void;
  reject: (e: unknown) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

/** Deterministically drain the microtask queue (no wall-clock sleeps). */
async function flushMicrotasks(turns = 12): Promise<void> {
  for (let i = 0; i < turns; i++) {
    await Promise.resolve();
  }
}

function caseDetail(
  id: string,
  title: string,
  version = 1,
  recordRef = "synth-001",
): Record<string, unknown> {
  return {
    id,
    dataset_id: "synthetic-demonstration",
    snapshot_id: "synthetic-v1",
    record_ref: recordRef,
    status: "not_reviewed",
    title,
    summary: "Test summary",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    version,
    created_by: "user-uuid-1",
  };
}

function caseHistory(caseId: string, marker: string): Record<string, unknown> {
  return {
    case_id: caseId,
    total: 1,
    items: [
      {
        id: `event-${caseId}`,
        case_id: caseId,
        event_type: "note_added",
        event_at: "2026-01-01T00:00:00Z",
        actor_ref: "user-uuid-1",
        previous_status: null,
        new_status: "not_reviewed",
        reason: null,
        event_payload: { note_text: marker },
        case_version: 1,
        event_seq: 1,
      },
    ],
  };
}

function evidenceDetail(recordRef: string, description: string): Record<string, unknown> {
  return {
    record_ref: recordRef,
    title: "SYNTHETIC DEMONSTRATION RECORD — NOT A RESEARCH FINDING",
    description,
    evidence_summary: `Evidence summary for ${recordRef}`,
    administrative_context: "Synthetic context.",
    limitations: "Synthetic; no ML score claimed.",
    dataset_id: "synthetic-demonstration",
    snapshot_id: "synthetic-v1",
    synthetic: true,
  };
}

interface MockOptions {
  /** Defer Case A's selection-load detail+history GETs. */
  deferCaseASelection?: boolean;
  /** Defer Case A's nested source-evidence GET. */
  deferCaseAEvidence?: boolean;
  /** Simulate real fetch abort behaviour on deferred promises. */
  abortAware?: boolean;
}

/**
 * Standard two-case mock. Case A's record_ref is synth-001, Case B's is
 * synth-002 so the nested source-evidence GETs are distinguishable.
 */
function buildMock(opts: MockOptions = {}) {
  const aSelectionDetail = deferred<Response>();
  const aSelectionHistory = deferred<Response>();
  const aEvidence = deferred<Response>();
  let postCalls = 0;
  const routes: FetchRoute[] = authenticatedRoutes(REVIEWER_USER);

  const maybeAbortAware = (
    d: Deferred<Response>,
    init?: RequestInit,
  ): Promise<Response> => {
    if (opts.abortAware && init?.signal) {
      const signal = init.signal as AbortSignal;
      signal.addEventListener("abort", () => {
        d.reject(new DOMException("Aborted", "AbortError"));
      });
    }
    return d.promise;
  };

  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();

    if (url.includes("/notes") && method === "POST") {
      postCalls += 1;
      throw new TypeError("Network error (simulated)");
    }

    // Case A selection detail.
    if (
      method === "GET" &&
      url.includes(`/${CASE_A_ID}`) &&
      !url.includes("/history")
    ) {
      if (opts.deferCaseASelection) return maybeAbortAware(aSelectionDetail, init);
      return jsonResponse(caseDetail(CASE_A_ID, "Case A"));
    }
    // Case A selection history.
    if (method === "GET" && url.includes(`/${CASE_A_ID}/history`)) {
      if (opts.deferCaseASelection) return maybeAbortAware(aSelectionHistory, init);
      return jsonResponse(caseHistory(CASE_A_ID, "A-HISTORY-MARKER"));
    }
    // Case A nested evidence (record_ref synth-001).
    if (method === "GET" && url.includes("/synthetic/records/synth-001")) {
      if (opts.deferCaseAEvidence) return maybeAbortAware(aEvidence, init);
      return jsonResponse(evidenceDetail("synth-001", "A SOURCE EVIDENCE"));
    }
    // Case B resolves everything immediately.
    if (
      method === "GET" &&
      url.includes(`/${CASE_B_ID}`) &&
      !url.includes("/history")
    ) {
      return jsonResponse(caseDetail(CASE_B_ID, "Case B", 1, "synth-002"));
    }
    if (method === "GET" && url.includes(`/${CASE_B_ID}/history`)) {
      return jsonResponse(caseHistory(CASE_B_ID, "B-HISTORY-MARKER"));
    }
    if (method === "GET" && url.includes("/synthetic/records/synth-002")) {
      return jsonResponse(evidenceDetail("synth-002", "B SOURCE EVIDENCE"));
    }

    // Case list: both cases.
    if (
      method === "GET" &&
      url.includes("/cases") &&
      !url.includes(CASE_A_ID) &&
      !url.includes(CASE_B_ID) &&
      !url.includes("/history")
    ) {
      return jsonResponse({
        items: [caseDetail(CASE_A_ID, "Case A"), caseDetail(CASE_B_ID, "Case B", 1, "synth-002")],
        total: 2,
        limit: 50,
        offset: 0,
      });
    }

    // Synthetic records list.
    if (method === "GET" && url.includes("/synthetic/records")) {
      return jsonResponse({
        items: [
          { record_ref: "synth-001", title: "SYNTHETIC DEMONSTRATION RECORD", dataset_id: "synthetic-demonstration", snapshot_id: "synthetic-v1", synthetic: true },
          { record_ref: "synth-002", title: "SYNTHETIC DEMONSTRATION RECORD", dataset_id: "synthetic-demonstration", snapshot_id: "synthetic-v1", synthetic: true },
        ],
        total: 2,
        dataset_id: "synthetic-demonstration",
        snapshot_id: "synthetic-v1",
      });
    }

    const route = routes.find(
      (r) => url.includes(r.urlContains) && (r.method ? r.method.toUpperCase() === method : true),
    );
    if (!route) throw new TypeError(`No mock for ${method} ${url}`);
    return jsonResponse(route.body, route.status);
  });

  return {
    mock,
    aSelectionDetail,
    aSelectionHistory,
    aEvidence,
    postCalls: () => postCalls,
  };
}

describe("stale selection responses (PR-07A B1/B2/B4) and uncertain outcome (E4)", () => {
  let originalFetch: typeof globalThis.fetch;
  let originalCookie: PropertyDescriptor | undefined;
  let originalInnerWidth: number;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    originalCookie = Object.getOwnPropertyDescriptor(document, "cookie");
    originalInnerWidth = window.innerWidth;
    setCookieJar([]);
    Object.defineProperty(document, "cookie", {
      configurable: true,
      get: () => `${CSRF_COOKIE_NAME}=test-csrf-token`,
      set: () => {},
    });
    setWindowWidth(1440);
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    if (originalCookie) {
      Object.defineProperty(document, "cookie", originalCookie);
    }
    setWindowWidth(originalInnerWidth);
    cleanup();
    vi.restoreAllMocks();
  });

  it("B1: stale detail+history for a prior selection never overwrite the current case (no sleeps)", async () => {
    const m = buildMock({ deferCaseASelection: true });
    globalThis.fetch = m.mock as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/investigations"] });
    const user = userEvent.setup();

    await screen.findByRole("button", { name: /Case A/i });
    // Select Case A — its GETs stay pending.
    await user.click(screen.getByRole("button", { name: /Case A/i }));
    // Select Case B — its GETs resolve immediately.
    await user.click(screen.getByRole("button", { name: /Case B/i }));
    await screen.findByText("Case metadata");
    const evidencePanel = screen.getByLabelText("Evidence examination");
    expect(within(evidencePanel).getByText("Case B")).toBeInTheDocument();
    expect(screen.getByText("B-HISTORY-MARKER")).toBeInTheDocument();

    // Case A's stale selection responses settle afterwards.
    await act(async () => {
      m.aSelectionDetail.resolve(jsonResponse(caseDetail(CASE_A_ID, "STALE DETAIL")));
      m.aSelectionHistory.resolve(jsonResponse(caseHistory(CASE_A_ID, "A-STALE-HISTORY")));
      await flushMicrotasks();
    });

    expect(screen.queryByText("STALE DETAIL")).toBeNull();
    expect(screen.queryByText("A-STALE-HISTORY")).toBeNull();
    expect(within(evidencePanel).getByText("Case B")).toBeInTheDocument();
    expect(screen.getByText("B-HISTORY-MARKER")).toBeInTheDocument();
  });

  it("B2: stale nested source-evidence response never overwrites the current case's evidence", async () => {
    const m = buildMock({ deferCaseAEvidence: true });
    globalThis.fetch = m.mock as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/investigations"] });
    const user = userEvent.setup();

    // Select Case A — detail+history resolve; its evidence GET is held.
    await screen.findByRole("button", { name: /Case A/i });
    await user.click(screen.getByRole("button", { name: /Case A/i }));
    // History (Region 3) is already applied, but the evidence panel
    // (Region 2) is still loading: the selection effect clears
    // loadingDetail only after the nested evidence GET settles.
    await screen.findByText("A-HISTORY-MARKER");
    await waitFor(() => {
      expect(screen.getByText("Loading evidence…")).toBeInTheDocument();
    });

    // Select Case B — everything resolves, including B's evidence.
    await user.click(screen.getByRole("button", { name: /Case B/i }));
    await screen.findByText("B SOURCE EVIDENCE");
    const evidencePanel = screen.getByLabelText("Evidence examination");
    expect(within(evidencePanel).getByText("Case B")).toBeInTheDocument();

    // Case A's stale evidence response settles afterwards.
    await act(async () => {
      m.aEvidence.resolve(jsonResponse(evidenceDetail("synth-001", "A STALE EVIDENCE")));
      await flushMicrotasks();
    });

    expect(screen.queryByText("A STALE EVIDENCE")).toBeNull();
    expect(screen.getByText("B SOURCE EVIDENCE")).toBeInTheDocument();
    // The evidence shown belongs to Case B's record_ref (it appears in
    // both the case metadata and the source-evidence section).
    expect(screen.getAllByText("synth-002").length).toBeGreaterThanOrEqual(1);
  });

  it("B4: unmount with pending requests produces no unhandled rejection and no cross-selection corruption", async () => {
    const unhandledRejections: unknown[] = [];
    const onUnhandled = (e: PromiseRejectionEvent) => {
      unhandledRejections.push(e.reason);
    };
    window.addEventListener("unhandledrejection", onUnhandled);

    const m = buildMock({ deferCaseASelection: true, abortAware: true });
    globalThis.fetch = m.mock as unknown as typeof globalThis.fetch;

    const { unmount } = renderApp({ initialEntries: ["/investigations"] });
    const user = userEvent.setup();

    await screen.findByRole("button", { name: /Case A/i });
    // Select Case A — its GETs stay pending (abort-aware deferreds).
    await user.click(screen.getByRole("button", { name: /Case A/i }));
    await waitFor(() => {
      expect(screen.getByText("Loading evidence…")).toBeInTheDocument();
    });

    // Unmount while requests are pending (abort fires on cleanup).
    unmount();
    await act(async () => {
      await flushMicrotasks();
    });

    expect(unhandledRejections.length).toBe(0);
    window.removeEventListener("unhandledrejection", onUnhandled);

    // A fresh mount selects Case B cleanly — no stale state survives.
    const m2 = buildMock();
    globalThis.fetch = m2.mock as unknown as typeof globalThis.fetch;
    renderApp({ initialEntries: ["/investigations"] });
    const user2 = userEvent.setup();
    await screen.findByRole("button", { name: /Case B/i });
    await user2.click(screen.getByRole("button", { name: /Case B/i }));
    await screen.findByText("Case metadata");
    const evidencePanel = screen.getByLabelText("Evidence examination");
    expect(within(evidencePanel).getByText("Case B")).toBeInTheDocument();
    expect(screen.getByText("B-HISTORY-MARKER")).toBeInTheDocument();
  });

  it("E4: uncertain network outcome is never auto-retried and the copy does not claim rejection", async () => {
    const m = buildMock();
    globalThis.fetch = m.mock as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/investigations"] });
    const user = userEvent.setup();

    await screen.findByRole("button", { name: /Case A/i });
    await user.click(screen.getByRole("button", { name: /Case A/i }));
    await screen.findByText("Case metadata");

    // Submit a note; the POST fails at the transport layer.
    await user.type(screen.getByLabelText("Note"), "uncertain note");
    await user.click(screen.getByRole("button", { name: "Add note" }));

    // The distinct uncertain-outcome panel appears.
    await screen.findByText(/Write outcome unknown/i);
    // The copy does NOT claim the server rejected the write.
    expect(screen.queryByText(/Operation failed/i)).toBeNull();

    // The draft is preserved (uncertain outcome — user reconciles).
    expect(screen.getByLabelText("Note")).toHaveValue("uncertain note");

    // Give any potential automatic retry ample microtask turns to fire.
    await act(async () => {
      await flushMicrotasks(30);
    });

    // No second POST was issued by any recovery behaviour.
    expect(m.postCalls()).toBe(1);
  });
});
