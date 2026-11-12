// PR-05B Final Reliability Hardening — regression tests.
//
// These tests verify that a confirmed mutation is NOT retroactively
// turned into a failure when a subsequent read (history or index) fails.
//
// The tests use controlled mocked HTTP responses with call counters to
// make ordering deterministic. No arbitrary sleeps.

import { cleanup, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  REVIEWER_USER,
  type FetchRoute,
  authenticatedRoutes,
  renderApp,
  setCookieJar,
  SYNTHETIC_RECORD_DETAIL,
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

const CASE_ID = "00000000-0000-0000-0000-000000000001";

function caseDetail(overrides: Partial<Record<string, unknown>> = {}): Record<string, unknown> {
  return {
    id: CASE_ID,
    dataset_id: "synthetic-demonstration",
    snapshot_id: "synthetic-v1",
    record_ref: "synth-001",
    status: "not_reviewed",
    title: "Test case",
    summary: "Test summary",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    version: 1,
    created_by: "user-uuid-1",
    ...overrides,
  };
}

function caseHistoryWithNote(version: number): Record<string, unknown> {
  return {
    case_id: CASE_ID,
    total: 2,
    items: [
      {
        id: "event-1", case_id: CASE_ID, event_type: "created",
        event_at: "2026-01-01T00:00:00Z", actor_ref: "user-uuid-1",
        previous_status: null, new_status: "not_reviewed",
        reason: null, event_payload: null, case_version: 1, event_seq: 1,
      },
      {
        id: "event-2", case_id: CASE_ID, event_type: "note_added",
        event_at: "2026-01-01T00:00:01Z", actor_ref: "user-uuid-1",
        previous_status: null, new_status: null,
        reason: null, event_payload: { note_text: "Test note" },
        case_version: version, event_seq: 2,
      },
    ],
  };
}

function routesWithCase(): FetchRoute[] {
  return [
    { urlContains: "/synthetic/records/synth-001", method: "GET", status: 200, body: SYNTHETIC_RECORD_DETAIL },
    { urlContains: `/${CASE_ID}/history`, method: "GET", status: 200, body: caseHistoryWithNote(1) },
    { urlContains: `/${CASE_ID}`, method: "GET", status: 200, body: caseDetail() },
    ...authenticatedRoutes(REVIEWER_USER),
  ];
}

/**
 * Build a fetch mock with per-call overrides.
 * `postNoteStatus` / `postNoteBody` control the POST /notes response.
 * `historyFailOnCall` controls which history GET call returns 503.
 * `listFailOnCall` controls which case-list GET call returns 503.
 */
function buildMock(
  routes: FetchRoute[],
  opts: {
    postNoteStatus?: number;
    postNoteBody?: unknown;
    postTransitionStatus?: number;
    postTransitionBody?: unknown;
    postDecisionStatus?: number;
    postDecisionBody?: unknown;
    postCreateStatus?: number;
    postCreateBody?: unknown;
    historyFailOnCall?: number; // 1-indexed; the Nth history GET returns 503
    listFailOnCall?: number; // 1-indexed; the Nth case-list GET returns 503
    postNoteThrow?: boolean; // POST /notes throws TypeError (network)
  } = {},
): ReturnType<typeof vi.fn> & { _callCounts: Record<string, number> } {
  const callCounts: Record<string, number> = {};
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();

    // POST /notes
    if (url.includes("/notes") && method === "POST") {
      callCounts.postNotes = (callCounts.postNotes ?? 0) + 1;
      if (opts.postNoteThrow) throw new TypeError("Failed to fetch");
      return new Response(JSON.stringify(opts.postNoteBody ?? caseDetail({ version: 2 })), {
        status: opts.postNoteStatus ?? 200,
        headers: { "content-type": "application/json", "X-Request-ID": "r" },
      });
    }
    // POST /transitions
    if (url.includes("/transitions") && method === "POST") {
      callCounts.postTransitions = (callCounts.postTransitions ?? 0) + 1;
      return new Response(JSON.stringify(opts.postTransitionBody ?? caseDetail({ status: "under_review", version: 2 })), {
        status: opts.postTransitionStatus ?? 200,
        headers: { "content-type": "application/json", "X-Request-ID": "r" },
      });
    }
    // POST /decisions
    if (url.includes("/decisions") && method === "POST") {
      callCounts.postDecisions = (callCounts.postDecisions ?? 0) + 1;
      return new Response(JSON.stringify(opts.postDecisionBody ?? caseDetail({ status: "explained_deviation", version: 2 })), {
        status: opts.postDecisionStatus ?? 200,
        headers: { "content-type": "application/json", "X-Request-ID": "r" },
      });
    }
    // POST /cases (create)
    if (url.includes("/cases") && !url.includes(CASE_ID) && method === "POST") {
      callCounts.postCreate = (callCounts.postCreate ?? 0) + 1;
      return new Response(JSON.stringify(opts.postCreateBody ?? caseDetail({ title: "New case", version: 1 })), {
        status: opts.postCreateStatus ?? 201,
        headers: { "content-type": "application/json", "X-Request-ID": "r" },
      });
    }
    // GET /cases/{id}/history
    if (url.includes("/history") && method === "GET") {
      callCounts.historyGets = (callCounts.historyGets ?? 0) + 1;
      if (opts.historyFailOnCall && callCounts.historyGets === opts.historyFailOnCall) {
        return new Response(
          JSON.stringify({ error: { code: "SERVICE_NOT_READY", message: "DB unavailable", request_id: "r" } }),
          { status: 503, headers: { "content-type": "application/json", "X-Request-ID": "r" } },
        );
      }
      // After a successful note POST (version 2), return history with version 2.
      const histVersion = (callCounts.postNotes ?? 0) > 0 ? 2 : 1;
      return new Response(JSON.stringify(caseHistoryWithNote(histVersion)), {
        status: 200, headers: { "content-type": "application/json", "X-Request-ID": "r" },
      });
    }
    // GET /cases (list) — must NOT match /cases/{id} or /cases/{id}/history.
    // The list URL ends with "/cases" or "/cases?..." (no path segment after).
    if (url.includes("/cases") && method === "GET" && !url.includes(CASE_ID) && !url.includes("/history")) {
      callCounts.listGets = (callCounts.listGets ?? 0) + 1;
      if (opts.listFailOnCall && callCounts.listGets === opts.listFailOnCall) {
        return new Response(
          JSON.stringify({ error: { code: "SERVICE_NOT_READY", message: "DB unavailable", request_id: "r" } }),
          { status: 503, headers: { "content-type": "application/json", "X-Request-ID": "r" } },
        );
      }
      return new Response(JSON.stringify({ items: [caseDetail()], total: 1, limit: 50, offset: 0 }), {
        status: 200, headers: { "content-type": "application/json", "X-Request-ID": "r" },
      });
    }
    // Fallback: match base routes.
    const route = routes.find(
      (r) => url.includes(r.urlContains) && (r.method ? r.method.toUpperCase() === method : true),
    );
    if (!route) throw new TypeError(`No mock route for ${method} ${url}`);
    return new Response(JSON.stringify(route.body), {
      status: route.status,
      headers: { "content-type": "application/json", "X-Request-ID": "r" },
    });
  });
  return Object.assign(mock, { _callCounts: callCounts });
}

describe("mutation reliability — confirmed write vs failed sync", () => {
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

  async function selectCase(): Promise<void> {
    renderApp({ initialEntries: ["/investigations"] });
    await screen.findByText("Test case");
    await userEvent.setup().click(screen.getByText("Test case"));
    await screen.findByText("Add note");
  }

  // === NOTE ADDITION ===

  it("NOTE: POST 200 + history GET 503 → draft cleared, sync warning shown", async () => {
    const mock = buildMock(routesWithCase(), { historyFailOnCall: 2 });
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;
    await selectCase();
    const user = userEvent.setup();
    const noteInput = screen.getByLabelText("Note");
    await user.type(noteInput, "Reliability test note");
    await user.click(screen.getByRole("button", { name: "Add note" }));
    // Draft cleared (POST succeeded).
    await waitFor(() => { expect(noteInput).toHaveValue(""); });
    // Sync warning visible (not "Operation failed").
    await waitFor(() => {
      expect(screen.getByText(/could not refresh/i)).toBeInTheDocument();
    });
    // Case version updated to 2.
    expect(screen.getByText(/v2/)).toBeInTheDocument();
  });

  it("NOTE: POST 409 → draft preserved, conflict message shown", async () => {
    const mock = buildMock(routesWithCase(), {
      postNoteStatus: 409,
      postNoteBody: { error: { code: "CONFLICT", message: "Stale.", request_id: "r", details: { expected_version: 1 } } },
    });
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;
    await selectCase();
    const user = userEvent.setup();
    const noteInput = screen.getByLabelText("Note");
    await user.type(noteInput, "Stale note");
    await user.click(screen.getByRole("button", { name: "Add note" }));
    await screen.findByText(/Concurrency conflict/i);
    expect(noteInput).toHaveValue("Stale note");
  });

  it("NOTE: POST timeout → draft preserved, uncertain message shown", async () => {
    const mock = buildMock(routesWithCase(), { postNoteThrow: true });
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;
    await selectCase();
    const user = userEvent.setup();
    const noteInput = screen.getByLabelText("Note");
    await user.type(noteInput, "Uncertain note");
    await user.click(screen.getByRole("button", { name: "Add note" }));
    // The error panel heading says "Write outcome unknown".
    await screen.findByRole("heading", { name: /Write outcome unknown/i });
    expect(noteInput).toHaveValue("Uncertain note");
  });

  it("NOTE: repeated clicks while pending → only one POST", async () => {
    // Use a deferred promise for the POST so it stays pending.
    let resolvePost!: (v: Response) => void;
    const pendingPost = new Promise<Response>((r) => { resolvePost = r; });
    const baseRoutes = routesWithCase();
    const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.includes("/notes") && method === "POST") return pendingPost;
      // Handle case list, case detail, history, synthetic records.
      if (url.includes("/cases") && !url.includes(CASE_ID) && !url.includes("/history") && method === "GET") {
        return new Response(JSON.stringify({ items: [caseDetail()], total: 1, limit: 50, offset: 0 }), {
          status: 200, headers: { "content-type": "application/json", "X-Request-ID": "r" },
        });
      }
      const route = baseRoutes.find(
        (r) => url.includes(r.urlContains) && (r.method ? r.method.toUpperCase() === method : true),
      );
      if (!route) throw new TypeError(`No mock for ${method} ${url}`);
      return new Response(JSON.stringify(route.body), {
        status: route.status, headers: { "content-type": "application/json", "X-Request-ID": "r" },
      });
    });
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;
    await selectCase();
    const user = userEvent.setup();
    const noteInput = screen.getByLabelText("Note");
    await user.type(noteInput, "Only one POST");
    const btn = screen.getByRole("button", { name: "Add note" });
    await user.click(btn);
    await user.click(btn);
    await user.click(btn);
    // Resolve the POST.
    act(() => resolvePost(new Response(JSON.stringify(caseDetail({ version: 2 })), {
      status: 200, headers: { "content-type": "application/json", "X-Request-ID": "r" },
    })));
    await waitFor(() => {
      const postCalls = mock.mock.calls.filter(([u, i]) => {
        const url = typeof u === "string" ? u : u.toString();
        return url.includes("/notes") && (i?.method ?? "GET").toUpperCase() === "POST";
      });
      expect(postCalls.length).toBe(1);
    });
  });

  // === STATUS TRANSITION ===

  it("TRANSITION: POST 200 + history GET 503 → draft cleared, sync warning shown", async () => {
    const mock = buildMock(routesWithCase(), { historyFailOnCall: 2 });
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;
    await selectCase();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Reason"), "Starting review");
    await user.click(screen.getByRole("button", { name: "Apply transition" }));
    await waitFor(() => { expect(screen.getByLabelText("Reason")).toHaveValue(""); });
    await waitFor(() => { expect(screen.getByText(/could not refresh/i)).toBeInTheDocument(); });
  });

  it("TRANSITION: POST 422 → draft preserved, validation error shown", async () => {
    const mock = buildMock(routesWithCase(), {
      postTransitionStatus: 422,
      postTransitionBody: { error: { code: "INVALID_TRANSITION", message: "Illegal transition.", request_id: "r", details: {} } },
    });
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;
    await selectCase();
    const user = userEvent.setup();
    const reasonInput = screen.getByLabelText("Reason");
    await user.type(reasonInput, "Illegal attempt");
    await user.click(screen.getByRole("button", { name: "Apply transition" }));
    // The error panel heading says "Operation failed".
    await screen.findByRole("heading", { name: /Operation failed/i });
    expect(reasonInput).toHaveValue("Illegal attempt");
  });

  // === DECISION ===

  it("DECISION: POST 200 + index GET 503 → draft cleared, sync warning shown", async () => {
    const mock = buildMock(routesWithCase(), { listFailOnCall: 2 });
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;
    await selectCase();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Rationale"), "Explained by data correction");
    await user.click(screen.getByRole("button", { name: "Record decision" }));
    await waitFor(() => { expect(screen.getByLabelText("Rationale")).toHaveValue(""); });
    await waitFor(() => { expect(screen.getByText(/could not refresh/i)).toBeInTheDocument(); });
  });

  it("DECISION: POST 403 → draft preserved, permission error shown", async () => {
    const mock = buildMock(routesWithCase(), {
      postDecisionStatus: 403,
      postDecisionBody: { error: { code: "FORBIDDEN", message: "Insufficient role.", request_id: "r", details: {} } },
    });
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;
    await selectCase();
    const user = userEvent.setup();
    const rationaleInput = screen.getByLabelText("Rationale");
    await user.type(rationaleInput, "Should be forbidden");
    await user.click(screen.getByRole("button", { name: "Record decision" }));
    await screen.findByText(/Operation failed|permission/i);
    expect(rationaleInput).toHaveValue("Should be forbidden");
  });

  // === CASE CREATION ===

  it("CREATE: POST 201 + index GET 503 → draft cleared, sync warning shown", async () => {
    const mock = buildMock(routesWithCase(), { listFailOnCall: 2 });
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;
    renderApp({ initialEntries: ["/investigations"] });
    await screen.findByText("synth-001");
    const user = userEvent.setup();
    await user.click(screen.getByText("synth-001"));
    await screen.findByText(/Create review case/i);
    const titleInput = screen.getByLabelText("Title");
    await user.type(titleInput, "New case");
    await user.click(screen.getByRole("button", { name: "Create case" }));
    // After confirmed creation, the selection switches to the new case
    // (the CreateCaseForm unmounts and the NoteForm appears). This is the
    // indicator that the POST succeeded and the draft was consumed.
    await waitFor(() => {
      expect(screen.getByLabelText("Note")).toBeInTheDocument();
    });
    // Sync warning visible (case list could not refresh).
    await waitFor(() => {
      expect(screen.getByText(/could not refresh/i)).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  // === SYNC RETRY — NO DUPLICATE POST ===

  it("SYNC RETRY: refreshing history after sync failure does not send a second POST", async () => {
    const mock = buildMock(routesWithCase(), { historyFailOnCall: 2 });
    globalThis.fetch = mock as unknown as typeof globalThis.fetch;
    await selectCase();
    const user = userEvent.setup();
    const noteInput = screen.getByLabelText("Note");
    await user.type(noteInput, "Sync retry test");
    await user.click(screen.getByRole("button", { name: "Add note" }));
    await waitFor(() => { expect(noteInput).toHaveValue(""); });
    await screen.findByText(/could not refresh/i);
    // Click "Refresh history".
    await user.click(screen.getByRole("button", { name: /refresh history/i }));
    // Sync warning dismissed.
    await waitFor(() => {
      expect(screen.queryByText(/could not refresh/i)).toBeNull();
    });
    // Only one POST was ever sent.
    expect(mock._callCounts.postNotes ?? 0).toBe(1);
  });
});
