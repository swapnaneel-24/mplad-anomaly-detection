// PR-07A Workstream B3 — conflict-recovery race regression tests.
//
// `handleReloadAfterConflict` (InvestigationsPage.tsx) issues GET
// case + GET history after a 409 and reapplies them. Every other async
// read path on this page is guarded by the `selectionGenRef` generation
// counter; this handler historically was not. These tests hold the
// recovery GETs pending across a selection change (deterministic
// deferred promises — no sleeps, no StrictMode double-effects) and
// assert that the newly selected case remains authoritative in its
// detail, history, evidence, error and loading states.
//
// Classification contract (PR-07A A5):
//   - B3-1/B3-2/B3-3 were written against the unmodified baseline and
//     are expected RED there (suspected defect PR07A-D1). Exact RED
//     evidence is recorded in PR07A_DEFECT_LOG.md before any fix.
//   - B3-4 (GET-only recovery) is expected BASELINE GREEN.

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

const CONFLICT_409 = {
  error: {
    code: "CONFLICT",
    message: "The case was modified by another reviewer.",
    request_id: "r",
    details: { expected_version: 1, current_version: 2 },
  },
};

/**
 * Build the fetch mock for the B3 scenario.
 *
 * - Case A's FIRST detail/history GETs (selection load) resolve
 *   immediately.
 * - Case A's SECOND detail/history GETs (conflict recovery) are held
 *   on the provided deferreds so the test controls when the stale
 *   recovery responses arrive.
 * - Case B's GETs resolve immediately.
 * - POST /notes returns 409.
 */
function buildMock(opts: {
  recoveryDetail: Deferred<Response>;
  recoveryHistory: Deferred<Response>;
}) {
  let aDetailCalls = 0;
  let aHistoryCalls = 0;
  let postCalls = 0;
  const routes: FetchRoute[] = authenticatedRoutes(REVIEWER_USER);
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();

    // POST note → 409 conflict.
    if (url.includes("/notes") && method === "POST") {
      postCalls += 1;
      return jsonResponse(CONFLICT_409, 409);
    }

    // Case A detail: 1st call = selection load; 2nd+ = recovery (held).
    if (
      method === "GET" &&
      url.includes(`/${CASE_A_ID}`) &&
      !url.includes("/history")
    ) {
      aDetailCalls += 1;
      if (aDetailCalls === 1) {
        return jsonResponse(caseDetail(CASE_A_ID, "Case A", 1));
      }
      return opts.recoveryDetail.promise;
    }

    // Case A history: 1st call = selection load; 2nd+ = recovery (held).
    if (method === "GET" && url.includes(`/${CASE_A_ID}/history`)) {
      aHistoryCalls += 1;
      if (aHistoryCalls === 1) {
        return jsonResponse(caseHistory(CASE_A_ID, "A-HISTORY-MARKER"));
      }
      return opts.recoveryHistory.promise;
    }

    // Case B detail + history resolve immediately.
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

    // Source evidence for each record ref resolves immediately.
    if (method === "GET" && url.includes("/synthetic/records/synth-001")) {
      return jsonResponse(evidenceDetail("synth-001", "A SOURCE EVIDENCE"));
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
    counts: {
      aDetail: () => aDetailCalls,
      aHistory: () => aHistoryCalls,
      post: () => postCalls,
    },
  };
}

describe("conflict-recovery race (PR-07A B3 / PR07A-D1)", () => {
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

  it("B3-1: stale conflict-recovery SUCCESS does not overwrite the newly selected case", async () => {
    const recoveryDetail = deferred<Response>();
    const recoveryHistory = deferred<Response>();
    const { mock } = buildMock({ recoveryDetail, recoveryHistory });
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/investigations"] });
    const user = userEvent.setup();

    // 1. Select Case A — its selection GETs resolve immediately.
    await screen.findByRole("button", { name: /Case A/i });
    await user.click(screen.getByRole("button", { name: /Case A/i }));
    await screen.findByText("Case metadata");
    const evidencePanel = screen.getByLabelText("Evidence examination");
    expect(within(evidencePanel).getByText("Case A")).toBeInTheDocument();
    expect(screen.getByText("A-HISTORY-MARKER")).toBeInTheDocument();

    // 2. Trigger HTTP 409 on a note POST.
    await user.type(screen.getByLabelText("Note"), "note that conflicts");
    await user.click(screen.getByRole("button", { name: "Add note" }));
    await screen.findByText(/Concurrency conflict/i);

    // 3. Start the conflict recovery; its GETs stay unresolved.
    await user.click(screen.getByRole("button", { name: /Reload latest version/i }));
    await waitFor(() => {
      // The banner clears and the recovery GETs have been issued.
      expect(screen.queryByText(/Concurrency conflict/i)).toBeNull();
    });

    // 4. Select Case B before the recovery GETs resolve.
    await user.click(screen.getByRole("button", { name: /Case B/i }));

    // 5. Case B's detail + history resolve successfully.
    await screen.findByText("Case metadata");
    expect(within(evidencePanel).getByText("Case B")).toBeInTheDocument();
    expect(screen.getByText("B-HISTORY-MARKER")).toBeInTheDocument();
    expect(screen.getByText("B SOURCE EVIDENCE")).toBeInTheDocument();

    // 6. Case A's stale recovery responses arrive afterwards.
    await act(async () => {
      recoveryDetail.resolve(
        jsonResponse(caseDetail(CASE_A_ID, "STALE RECOVERED DETAIL", 9)),
      );
      recoveryHistory.resolve(
        jsonResponse(caseHistory(CASE_A_ID, "A-RECOVERY-MARKER")),
      );
      await flushMicrotasks();
    });

    // 7. Case B remains authoritative.
    expect(screen.queryByText("STALE RECOVERED DETAIL")).toBeNull();
    expect(screen.queryByText("A-RECOVERY-MARKER")).toBeNull();
    expect(within(evidencePanel).getByText("Case B")).toBeInTheDocument();
    expect(screen.getByText("B-HISTORY-MARKER")).toBeInTheDocument();
    expect(screen.getByText("B SOURCE EVIDENCE")).toBeInTheDocument();
    // No error state leaked from the stale recovery.
    expect(within(evidencePanel).queryByRole("alert")).toBeNull();
    // Loading state is settled (not stuck).
    expect(screen.queryByText("Loading evidence…")).toBeNull();
  });

  it("B3-2: stale conflict-recovery FAILURE does not raise an error over the newly selected case", async () => {
    const recoveryDetail = deferred<Response>();
    const recoveryHistory = deferred<Response>();
    const { mock } = buildMock({ recoveryDetail, recoveryHistory });
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/investigations"] });
    const user = userEvent.setup();

    await screen.findByRole("button", { name: /Case A/i });
    await user.click(screen.getByRole("button", { name: /Case A/i }));
    await screen.findByText("Case metadata");
    const evidencePanel = screen.getByLabelText("Evidence examination");

    await user.type(screen.getByLabelText("Note"), "note that conflicts");
    await user.click(screen.getByRole("button", { name: "Add note" }));
    await screen.findByText(/Concurrency conflict/i);

    await user.click(screen.getByRole("button", { name: /Reload latest version/i }));
    await waitFor(() => {
      expect(screen.queryByText(/Concurrency conflict/i)).toBeNull();
    });

    await user.click(screen.getByRole("button", { name: /Case B/i }));
    await screen.findByText("Case metadata");
    expect(within(evidencePanel).getByText("Case B")).toBeInTheDocument();
    expect(screen.getByText("B-HISTORY-MARKER")).toBeInTheDocument();

    // The stale recovery GETs FAIL after Case B is displayed.
    await act(async () => {
      recoveryDetail.resolve(
        jsonResponse(
          { error: { code: "SERVICE_NOT_READY", message: "DB unavailable", request_id: "r" } },
          503,
        ),
      );
      recoveryHistory.resolve(
        jsonResponse(
          { error: { code: "SERVICE_NOT_READY", message: "DB unavailable", request_id: "r" } },
          503,
        ),
      );
      await flushMicrotasks();
    });

    // Case B remains authoritative; the stale failure raises no error panel.
    expect(within(evidencePanel).getByText("Case B")).toBeInTheDocument();
    expect(screen.getByText("B-HISTORY-MARKER")).toBeInTheDocument();
    expect(within(evidencePanel).queryByRole("alert")).toBeNull();
    expect(screen.queryByText(/DB unavailable/i)).toBeNull();
  });

  it("B3-3: stale conflict-recovery finally-path does not clear the loading state of the newly selected case", async () => {
    const recoveryDetail = deferred<Response>();
    const recoveryHistory = deferred<Response>();
    const { mock } = buildMock({ recoveryDetail, recoveryHistory });

    // Case B's GETs are also deferred so its load is still in flight
    // when the stale recovery settles.
    let bDetailDeferred: Deferred<Response> | null = null;
    let bHistoryDeferred: Deferred<Response> | null = null;
    const wrappedMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = (init?.method ?? "GET").toUpperCase();
      if (
        method === "GET" &&
        url.includes("/00000000-0000-0000-0000-000000000002") &&
        !url.includes("/history")
      ) {
        bDetailDeferred = deferred<Response>();
        return bDetailDeferred.promise;
      }
      if (method === "GET" && url.includes("/00000000-0000-0000-0000-000000000002/history")) {
        bHistoryDeferred = deferred<Response>();
        return bHistoryDeferred.promise;
      }
      return (mock as unknown as (i: RequestInfo | URL, o?: RequestInit) => Promise<Response>)(
        input,
        init,
      );
    });
    globalThis.fetch = wrappedMock as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/investigations"] });
    const user = userEvent.setup();

    await screen.findByRole("button", { name: /Case A/i });
    await user.click(screen.getByRole("button", { name: /Case A/i }));
    await screen.findByText("Case metadata");

    await user.type(screen.getByLabelText("Note"), "note that conflicts");
    await user.click(screen.getByRole("button", { name: "Add note" }));
    await screen.findByText(/Concurrency conflict/i);

    await user.click(screen.getByRole("button", { name: /Reload latest version/i }));
    await waitFor(() => {
      expect(screen.queryByText(/Concurrency conflict/i)).toBeNull();
    });

    // Select Case B; its GETs remain pending.
    await user.click(screen.getByRole("button", { name: /Case B/i }));
    await waitFor(() => {
      expect(screen.getByText("Loading evidence…")).toBeInTheDocument();
    });

    // The stale recovery for Case A settles while Case B is still loading.
    await act(async () => {
      recoveryDetail.resolve(
        jsonResponse(caseDetail(CASE_A_ID, "STALE RECOVERED DETAIL", 9)),
      );
      recoveryHistory.resolve(
        jsonResponse(caseHistory(CASE_A_ID, "A-RECOVERY-MARKER")),
      );
      await flushMicrotasks();
    });

    // Case B is still loading — the stale recovery must not clear it,
    // and must not paint Case A's data over the pending selection.
    expect(screen.getByText("Loading evidence…")).toBeInTheDocument();
    expect(screen.queryByText("STALE RECOVERED DETAIL")).toBeNull();

    // Case B's responses arrive; B displays normally.
    const bDetail = bDetailDeferred!;
    const bHistory = bHistoryDeferred!;
    await act(async () => {
      bDetail.resolve(
        jsonResponse(caseDetail(CASE_B_ID, "Case B", 1, "synth-002")),
      );
      bHistory.resolve(jsonResponse(caseHistory(CASE_B_ID, "B-HISTORY-MARKER")));
      await flushMicrotasks();
    });
    await screen.findByText("Case metadata");
    const evidencePanel = screen.getByLabelText("Evidence examination");
    expect(within(evidencePanel).getByText("Case B")).toBeInTheDocument();
    expect(screen.getByText("B-HISTORY-MARKER")).toBeInTheDocument();
    expect(screen.queryByText("Loading evidence…")).toBeNull();
  });

  it("B3-4 (C2): conflict recovery issues GETs only — no second POST", async () => {
    const recoveryDetail = deferred<Response>();
    const recoveryHistory = deferred<Response>();
    const { mock, counts } = buildMock({ recoveryDetail, recoveryHistory });
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/investigations"] });
    const user = userEvent.setup();

    await screen.findByRole("button", { name: /Case A/i });
    await user.click(screen.getByRole("button", { name: /Case A/i }));
    await screen.findByText("Case metadata");

    await user.type(screen.getByLabelText("Note"), "note that conflicts");
    await user.click(screen.getByRole("button", { name: "Add note" }));
    await screen.findByText(/Concurrency conflict/i);
    expect(counts.post()).toBe(1);

    await user.click(screen.getByRole("button", { name: /Reload latest version/i }));

    // The recovery issued the two GETs...
    await waitFor(() => {
      expect(counts.aDetail()).toBeGreaterThanOrEqual(2);
      expect(counts.aHistory()).toBeGreaterThanOrEqual(2);
    });

    // Let the recovery complete.
    await act(async () => {
      recoveryDetail.resolve(jsonResponse(caseDetail(CASE_A_ID, "Case A", 2)));
      recoveryHistory.resolve(jsonResponse(caseHistory(CASE_A_ID, "A-HISTORY-MARKER")));
      await flushMicrotasks();
    });
    await screen.findByText("Case metadata");

    // ...and no recovery action issued another POST.
    expect(counts.post()).toBe(1);
  });
});
