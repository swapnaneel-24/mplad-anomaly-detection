// PR-07A Workstream A — index-refresh concurrency regression tests.
//
// PR-05B shipped `indexGenRef` so that only the newest index refresh may
// write `records`/`cases`/`indexError` or clear `loadingIndex`. The
// PR-07A Stage-2 audit found the existing tests in this file did not
// actually race: test 1 was sequential (the 503 settled before Retry
// started) and test 2 recorded an abandoned design in its own comments
// (the deferred promise resolved before the second request, so no
// overlap ever existed).
//
// This rewrite proves the guard with genuinely overlapping requests:
// two post-mutation sync refreshes are held pending simultaneously
// (deterministic deferred promises — no sleeps, no StrictMode
// double-effects, no inaccessible buttons), then the older response is
// settled AFTER the newer one. Each test fails if a stale response is
// incorrectly applied.
//
// The overlap is real, not incidental: the test holds the older
// request's resolver and asserts both case-list GETs are in flight
// (started, unresolved) before either settles.

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

function caseDetail(id: string, title: string, version = 1): Record<string, unknown> {
  return {
    id,
    dataset_id: "synthetic-demonstration",
    snapshot_id: "synthetic-v1",
    record_ref: "synth-001",
    status: "not_reviewed",
    title,
    summary: "Test summary",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    version,
    created_by: "user-uuid-1",
  };
}

function caseHistory(caseId: string): Record<string, unknown> {
  return {
    case_id: caseId,
    total: 1,
    items: [
      {
        id: `event-${caseId}`,
        case_id: caseId,
        event_type: "created",
        event_at: "2026-01-01T00:00:00Z",
        actor_ref: "user-uuid-1",
        previous_status: null,
        new_status: "not_reviewed",
        reason: null,
        event_payload: null,
        case_version: 1,
        event_seq: 1,
      },
    ],
  };
}

/**
 * Fetch mock for the index-refresh races.
 *
 * - Case-list call 1 (mount) resolves immediately with [Case A].
 * - Post-mutation sync refreshes (calls 2+) are each held on a fresh
 *   deferred stored in `pendingRefreshes`, so the test decides when
 *   each refresh settles and in which order.
 * - Note POSTs succeed (200) — the production trigger for the
 *   non-blocking sync refreshIndex in handleAddNote.
 */
function buildMock() {
  const pendingRefreshes: Deferred<Response>[] = [];
  let caseListCalls = 0;
  let postCalls = 0;
  const routes: FetchRoute[] = [
    {
      urlContains: "/synthetic/records/synth-001",
      method: "GET",
      status: 200,
      body: {
        record_ref: "synth-001",
        title: "SYNTHETIC DEMONSTRATION RECORD — NOT A RESEARCH FINDING",
        description: "Fictional administrative record.",
        evidence_summary: "Synthetic evidence.",
        administrative_context: "Synthetic context.",
        limitations: "Synthetic; no ML score claimed.",
        dataset_id: "synthetic-demonstration",
        snapshot_id: "synthetic-v1",
        synthetic: true,
      },
    },
    {
      urlContains: `/${CASE_A_ID}/history`,
      method: "GET",
      status: 200,
      body: caseHistory(CASE_A_ID),
    },
    {
      urlContains: `/${CASE_A_ID}`,
      method: "GET",
      status: 200,
      body: caseDetail(CASE_A_ID, "Case A"),
    },
    ...authenticatedRoutes(REVIEWER_USER),
  ];
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();

    // Note POST succeeds — triggers the non-blocking sync refreshIndex.
    if (url.includes("/notes") && method === "POST") {
      postCalls += 1;
      return jsonResponse(caseDetail(CASE_A_ID, "Case A", postCalls + 1));
    }

    if (
      method === "GET" &&
      url.includes("/cases") &&
      !url.includes(CASE_A_ID) &&
      !url.includes(CASE_B_ID) &&
      !url.includes("/history")
    ) {
      caseListCalls += 1;
      if (caseListCalls === 1) {
        // Mount refresh: only Case A exists yet.
        return jsonResponse({
          items: [caseDetail(CASE_A_ID, "Case A")],
          total: 1,
          limit: 50,
          offset: 0,
        });
      }
      // Post-mutation sync refresh: hold on a fresh deferred.
      const d = deferred<Response>();
      pendingRefreshes.push(d);
      return d.promise;
    }

    const route = routes.find(
      (r) => url.includes(r.urlContains) && (r.method ? r.method.toUpperCase() === method : true),
    );
    if (!route) throw new TypeError(`No mock for ${method} ${url}`);
    return jsonResponse(route.body, route.status);
  });
  return {
    mock,
    state: {
      caseListCalls: () => caseListCalls,
      postCalls: () => postCalls,
      pending: () => pendingRefreshes,
    },
  };
}

/** Select Case A and submit a note so a sync refresh starts (held). */
async function addNote(
  user: ReturnType<typeof userEvent.setup>,
  state: { postCalls: () => number },
): Promise<void> {
  const before = state.postCalls();
  await user.type(screen.getByLabelText("Note"), "sync note");
  await user.click(screen.getByRole("button", { name: "Add note" }));
  // Wait until the POST has resolved (draft cleared by confirmed success)
  // and the non-blocking sync refreshIndex has been issued.
  await waitFor(() => {
    expect(state.postCalls()).toBe(before + 1);
    expect(screen.getByLabelText("Note")).toHaveValue("");
  });
}

describe("index-refresh race (PR-07A A1/A2/A3)", () => {
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

  it("A1: older SUCCESSFUL index refresh settles after a newer one — newer list stays", async () => {
    const { mock, state } = buildMock();
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/investigations"] });
    const user = userEvent.setup();

    // Mount refresh resolves with [Case A].
    await screen.findByRole("button", { name: /Case A/i });
    await user.click(screen.getByRole("button", { name: /Case A/i }));
    await screen.findByText("Case metadata");

    // Two mutations → two sync refreshes, both held pending.
    await addNote(user, state);
    await addNote(user, state);
    const pending = state.pending();
    expect(pending.length).toBe(2);
    expect(state.caseListCalls()).toBe(3);
    // Both refreshes are genuinely in flight simultaneously: neither
    // has settled (their resolvers are still ours to call).

    // The NEWER refresh (call 3) settles first with the newer list.
    await act(async () => {
      pending[1]!.resolve(
        jsonResponse({
          items: [caseDetail(CASE_A_ID, "Case A", 3), caseDetail(CASE_B_ID, "Case B", 1)],
          total: 2,
          limit: 50,
          offset: 0,
        }),
      );
      await flushMicrotasks();
    });
    await screen.findByRole("button", { name: /Case B/i });

    // The OLDER refresh (call 2) settles afterwards with the older list
    // (no Case B). It must be discarded.
    await act(async () => {
      pending[0]!.resolve(
        jsonResponse({
          items: [caseDetail(CASE_A_ID, "Case A", 2)],
          total: 1,
          limit: 50,
          offset: 0,
        }),
      );
      await flushMicrotasks();
    });

    // Newer list stays; no stale loading or error state.
    expect(screen.getByRole("button", { name: /Case B/i })).toBeInTheDocument();
    expect(screen.queryByText("Loading index…")).toBeNull();
    const indexPanel = screen.getByLabelText("Record and case index");
    expect(within(indexPanel).queryByRole("alert")).toBeNull();
  });

  it("A2: older FAILED index refresh settles after a newer success — no error, newer list stays", async () => {
    const { mock, state } = buildMock();
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/investigations"] });
    const user = userEvent.setup();

    await screen.findByRole("button", { name: /Case A/i });
    await user.click(screen.getByRole("button", { name: /Case A/i }));
    await screen.findByText("Case metadata");

    await addNote(user, state);
    await addNote(user, state);
    const pending = state.pending();
    expect(pending.length).toBe(2);
    expect(state.caseListCalls()).toBe(3);

    // Newer refresh succeeds with Case B.
    await act(async () => {
      pending[1]!.resolve(
        jsonResponse({
          items: [caseDetail(CASE_A_ID, "Case A", 3), caseDetail(CASE_B_ID, "Case B", 1)],
          total: 2,
          limit: 50,
          offset: 0,
        }),
      );
      await flushMicrotasks();
    });
    await screen.findByRole("button", { name: /Case B/i });

    // Older refresh FAILS (503) after the newer success settled.
    await act(async () => {
      pending[0]!.resolve(
        jsonResponse(
          { error: { code: "SERVICE_NOT_READY", message: "DB unavailable", request_id: "r" } },
          503,
        ),
      );
      await flushMicrotasks();
    });

    // The stale failure is discarded: no error panel, no sync warning,
    // the newer list stays, loading is not stuck.
    expect(screen.getByRole("button", { name: /Case B/i })).toBeInTheDocument();
    const indexPanel = screen.getByLabelText("Record and case index");
    expect(within(indexPanel).queryByRole("alert")).toBeNull();
    expect(screen.queryByText(/Saved successfully, but case list could not refresh/i)).toBeNull();
    expect(screen.queryByText("Loading index…")).toBeNull();
  });

  it("A3 (i): superseded sync refresh that fails sets NO index sync warning", async () => {
    const { mock, state } = buildMock();
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/investigations"] });
    const user = userEvent.setup();

    await screen.findByRole("button", { name: /Case A/i });
    await user.click(screen.getByRole("button", { name: /Case A/i }));
    await screen.findByText("Case metadata");

    await addNote(user, state);
    await addNote(user, state);
    const pending = state.pending();
    expect(pending.length).toBe(2);

    // Newer refresh succeeds.
    await act(async () => {
      pending[1]!.resolve(
        jsonResponse({
          items: [caseDetail(CASE_A_ID, "Case A", 3), caseDetail(CASE_B_ID, "Case B", 1)],
          total: 2,
          limit: 50,
          offset: 0,
        }),
      );
      await flushMicrotasks();
    });
    await screen.findByRole("button", { name: /Case B/i });

    // The superseded (older) refresh fails — the failure is discarded
    // before the re-throw, so the mutation handler's catch never fires
    // and no sync warning may appear.
    await act(async () => {
      pending[0]!.resolve(
        jsonResponse(
          { error: { code: "SERVICE_NOT_READY", message: "DB unavailable", request_id: "r" } },
          503,
        ),
      );
      await flushMicrotasks();
    });

    expect(screen.queryByText(/Saved successfully, but case list could not refresh/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /Refresh case list/i })).toBeNull();
    expect(screen.getByRole("button", { name: /Case B/i })).toBeInTheDocument();
  });

  it("A3 (ii): non-superseded sync refresh failure sets the warning; successful retry clears it", async () => {
    const { mock, state } = buildMock();
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;

    renderApp({ initialEntries: ["/investigations"] });
    const user = userEvent.setup();

    await screen.findByRole("button", { name: /Case A/i });
    await user.click(screen.getByRole("button", { name: /Case A/i }));
    await screen.findByText("Case metadata");

    // One mutation; its (only, therefore non-superseded) sync refresh fails.
    await addNote(user, state);
    const pending = state.pending();
    expect(pending.length).toBe(1);
    await act(async () => {
      pending[0]!.resolve(
        jsonResponse(
          { error: { code: "SERVICE_NOT_READY", message: "DB unavailable", request_id: "r" } },
          503,
        ),
      );
      await flushMicrotasks();
    });

    // The sync warning appears (write succeeded; follow-up GET failed).
    await screen.findByText(/Saved successfully, but case list could not refresh/i);
    const retryButton = screen.getByRole("button", { name: /Refresh case list/i });

    // Manual retry succeeds with the newer list.
    await user.click(retryButton);
    const retryPending = state.pending();
    expect(retryPending.length).toBe(2);
    await act(async () => {
      retryPending[1]!.resolve(
        jsonResponse({
          items: [caseDetail(CASE_A_ID, "Case A", 2), caseDetail(CASE_B_ID, "Case B", 1)],
          total: 2,
          limit: 50,
          offset: 0,
        }),
      );
      await flushMicrotasks();
    });
    await screen.findByRole("button", { name: /Case B/i });

    // Warning cleared; new list rendered.
    expect(screen.queryByText(/Saved successfully, but case list could not refresh/i)).toBeNull();
    expect(screen.getByRole("button", { name: /Case B/i })).toBeInTheDocument();
  });
});
