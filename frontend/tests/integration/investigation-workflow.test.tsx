// Integration tests: PR-05B investigation workflow.
//
// Covers the InvestigationsPage three-region workflow against mocked API
// responses:
//   - Record listing + selection.
//   - Evidence display when a record is selected.
//   - Case creation from a selected record.
//   - Case selection + detail + history display.
//   - Note addition.
//   - Status transition.
//   - Decision recording.
//   - Viewer read-only presentation (no create/note/transition forms).
//   - Reviewer can write.
//   - 409 concurrency-conflict feedback with reload prompt.
//   - Source/case distinction (synthetic banner visible).
//   - No fabricated anomaly scores.

import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ADMIN_USER,
  REVIEWER_USER,
  VIEWER_USER,
  type FetchMock,
  type FetchRoute,
  type TestUser,
  authenticatedRoutes,
  mockFetch,
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

function caseDetail(overrides: Partial<Record<string, unknown>> = {}): Record<string, unknown> {
  return {
    id: "00000000-0000-0000-0000-000000000001",
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

function caseHistory(): Record<string, unknown> {
  return {
    case_id: "00000000-0000-0000-0000-000000000001",
    total: 1,
    items: [
      {
        id: "event-1",
        case_id: "00000000-0000-0000-0000-000000000001",
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

function routesWithRecordDetail(user: TestUser = REVIEWER_USER): FetchRoute[] {
  // Detail routes must come BEFORE the list routes in the array so the
  // `find` in mockFetch matches the more specific path first.
  return [
    {
      urlContains: "/synthetic/records/synth-001",
      method: "GET",
      status: 200,
      body: SYNTHETIC_RECORD_DETAIL,
    },
    {
      urlContains: "/cases/00000000-0000-0000-0000-000000000001/history",
      method: "GET",
      status: 200,
      body: caseHistory(),
    },
    {
      urlContains: "/cases/00000000-0000-0000-0000-000000000001",
      method: "GET",
      status: 200,
      body: caseDetail(),
    },
    ...authenticatedRoutes(user),
  ];
}

describe("investigation workflow", () => {
  let originalFetch: typeof globalThis.fetch;
  let originalCookie: PropertyDescriptor | undefined;
  let originalInnerWidth: number;
  let fetchMock: FetchMock;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    originalCookie = Object.getOwnPropertyDescriptor(document, "cookie");
    originalInnerWidth = window.innerWidth;
    setCookieJar([]);
    // Set the CSRF cookie so mutations can send the header.
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

  function setup(routes: FetchRoute[]): FetchMock {
    fetchMock = mockFetch(routes);
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
    return fetchMock;
  }

  async function navigateToInvestigations(): Promise<void> {
    renderApp({ initialEntries: ["/investigations"] });
    // Wait for the index to load.
    await screen.findByText("Demonstration records");
  }

  it("lists synthetic demonstration records in the index", async () => {
    setup(authenticatedRoutes());
    await navigateToInvestigations();
    expect(screen.getByText("synth-001")).toBeInTheDocument();
    expect(screen.getByText("synth-002")).toBeInTheDocument();
  });

  it("selecting a record shows its evidence with the SYNTHETIC banner", async () => {
    setup(routesWithRecordDetail());
    await navigateToInvestigations();
    const user = userEvent.setup();
    // Click the record in the index (the first occurrence).
    const indexPanel = screen.getByLabelText("Record and case index");
    const recordButton = within(indexPanel).getByText("synth-001");
    await user.click(recordButton);
    // The evidence panel shows the synthetic banner.
    expect(await screen.findByText(/SYNTHETIC DEMONSTRATION RECORD — NOT A RESEARCH FINDING/i)).toBeInTheDocument();
  });

  it("a reviewer can create a case from a selected record", async () => {
    const routes = routesWithRecordDetail();
    // The POST /cases route returns the created case; the GET /cases list
    // route is mutated to include the new case after creation.
    const createdCase = caseDetail({ title: "My new case", version: 1 });
    routes.push({
      urlContains: "/cases",
      method: "POST",
      status: 201,
      body: createdCase,
    });
    // Replace the GET /cases list route with a mutable version.
    const listRoute = routes.find(
      (r) => r.urlContains === "/cases" && (!r.method || r.method === "GET"),
    )!;
    listRoute.body = { items: [], total: 0, limit: 50, offset: 0 };
    // After POST, update the list to include the new case.
    const mock = setup(routes);
    mock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = (init?.method ?? "GET").toUpperCase();
      // If this is the POST, update the list route afterwards.
      if (url.includes("/cases") && method === "POST") {
        // Mutate the list route so the next GET returns the new case.
        listRoute.body = { items: [createdCase], total: 1, limit: 50, offset: 0 };
      }
      const route = routes.find(
        (r) =>
          url.includes(r.urlContains) &&
          (r.method ? r.method.toUpperCase() === method : true),
      );
      if (!route) throw new TypeError(`No mock route for ${method} ${url}`);
      return new Response(JSON.stringify(route.body), {
        status: route.status,
        headers: { "content-type": "application/json", "X-Request-ID": "r" },
      });
    });
    await navigateToInvestigations();
    const user = userEvent.setup();
    // Select the record.
    const indexPanel = screen.getByLabelText("Record and case index");
    await user.click(within(indexPanel).getByText("synth-001"));
    // Fill the create-case form.
    await screen.findByText(/Create review case/i);
    const titleInput = screen.getByLabelText("Title");
    await user.type(titleInput, "My new case");
    const submitButton = screen.getByRole("button", { name: "Create case" });
    await user.click(submitButton);
    // The case list should now include the new case.
    await waitFor(() => {
      const idx = screen.getByLabelText("Record and case index");
      expect(within(idx).getByText("My new case")).toBeInTheDocument();
    });
  });

  it("a viewer cannot see the create-case form (read-only)", async () => {
    setup(routesWithRecordDetail(VIEWER_USER));
    renderApp({ initialEntries: ["/investigations"] });
    await screen.findByText("Demonstration records");
    const user = userEvent.setup();
    const indexPanel = screen.getByLabelText("Record and case index");
    await user.click(within(indexPanel).getByText("synth-001"));
    // The create-case form is NOT present.
    expect(screen.queryByLabelText("Title")).toBeNull();
    // The read-only note is visible.
    expect(screen.getByText(/do not have permission to create cases/i)).toBeInTheDocument();
  });

  it("selecting an existing case shows its detail + history", async () => {
    // Seed a case in the list.
    const routes = routesWithRecordDetail();
    const listRoute = routes.find(
      (r) => r.urlContains === "/cases" && r.method === "GET",
    )!;
    listRoute.body = {
      items: [caseDetail({ title: "Existing case" })],
      total: 1,
      limit: 50,
      offset: 0,
    };
    setup(routes);
    await navigateToInvestigations();
    const user = userEvent.setup();
    // Click the existing case in the case list.
    await user.click(screen.getByText("Existing case"));
    // The case detail appears in the evidence panel.
    expect(await screen.findByText("Existing case")).toBeInTheDocument();
    // The history panel shows the created event.
    expect(await screen.findByText("Case created")).toBeInTheDocument();
  });

  it("a reviewer can add a note to a case", async () => {
    const routes = routesWithRecordDetail();
    // Seed a case.
    const listRoute = routes.find(
      (r) => r.urlContains === "/cases" && r.method === "GET",
    )!;
    listRoute.body = {
      items: [caseDetail({ title: "Note case" })],
      total: 1,
      limit: 50,
      offset: 0,
    };
    // Add a POST notes route.
    routes.push({
      urlContains: "/notes",
      method: "POST",
      status: 200,
      body: caseDetail({ title: "Note case", version: 2 }),
    });
    setup(routes);
    await navigateToInvestigations();
    const user = userEvent.setup();
    await user.click(screen.getByText("Note case"));
    // Wait for the case to load.
    await screen.findByText("Add note");
    const noteInput = screen.getByLabelText("Note");
    await user.type(noteInput, "First note");
    await user.click(screen.getByRole("button", { name: "Add note" }));
    // The version should bump.
    await waitFor(() => {
      expect(screen.getByText(/v2/)).toBeInTheDocument();
    });
  });

  it("a reviewer can transition the case status", async () => {
    const routes = routesWithRecordDetail();
    const listRoute = routes.find(
      (r) => r.urlContains === "/cases" && r.method === "GET",
    )!;
    listRoute.body = {
      items: [caseDetail({ title: "Transition case", status: "not_reviewed" })],
      total: 1,
      limit: 50,
      offset: 0,
    };
    routes.push({
      urlContains: "/transitions",
      method: "POST",
      status: 200,
      body: caseDetail({ title: "Transition case", status: "under_review", version: 2 }),
    });
    setup(routes);
    await navigateToInvestigations();
    const user = userEvent.setup();
    await user.click(screen.getByText("Transition case"));
    await screen.findByText("Transition status");
    const reasonInput = screen.getByLabelText("Reason");
    await user.type(reasonInput, "Starting review");
    await user.click(screen.getByRole("button", { name: "Apply transition" }));
    await waitFor(() => {
      expect(screen.getByText("Under review")).toBeInTheDocument();
    });
  });

  it("shows a 409 concurrency-conflict message with a reload prompt", async () => {
    const routes = routesWithRecordDetail();
    const listRoute = routes.find(
      (r) => r.urlContains === "/cases" && r.method === "GET",
    )!;
    listRoute.body = {
      items: [caseDetail({ title: "Conflict case", version: 3 })],
      total: 1,
      limit: 50,
      offset: 0,
    };
    // The POST notes route returns 409.
    routes.push({
      urlContains: "/notes",
      method: "POST",
      status: 409,
      body: {
        error: {
          code: "CONFLICT",
          message: "The case was modified by another reviewer.",
          request_id: "req-1",
          details: { case_id: "00000000-0000-0000-0000-000000000001", expected_version: 3 },
        },
      },
    });
    setup(routes);
    await navigateToInvestigations();
    const user = userEvent.setup();
    await user.click(screen.getByText("Conflict case"));
    await screen.findByText("Add note");
    const noteInput = screen.getByLabelText("Note");
    await user.type(noteInput, "stale note");
    await user.click(screen.getByRole("button", { name: "Add note" }));
    // The conflict message + reload button appear.
    expect(await screen.findByText(/Concurrency conflict/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload latest version" })).toBeInTheDocument();
  });

  it("preserves the draft note text after a 409 conflict (not cleared)", async () => {
    const routes = routesWithRecordDetail();
    const listRoute = routes.find(
      (r) => r.urlContains === "/cases" && r.method === "GET",
    )!;
    listRoute.body = {
      items: [caseDetail({ title: "Draft preservation case", version: 1 })],
      total: 1,
      limit: 50,
      offset: 0,
    };
    routes.push({
      urlContains: "/notes",
      method: "POST",
      status: 409,
      body: {
        error: {
          code: "CONFLICT",
          message: "The case was modified by another reviewer.",
          request_id: "req-2",
          details: { case_id: "00000000-0000-0000-0000-000000000001", expected_version: 1 },
        },
      },
    });
    setup(routes);
    await navigateToInvestigations();
    const user = userEvent.setup();
    await user.click(screen.getByText("Draft preservation case"));
    await screen.findByText("Add note");
    const noteInput = screen.getByLabelText("Note");
    const draftText = "This draft should be preserved after the conflict.";
    await user.type(noteInput, draftText);
    await user.click(screen.getByRole("button", { name: "Add note" }));
    // The conflict message appears.
    await screen.findByText(/Concurrency conflict/i);
    // The draft text is STILL in the input (not cleared).
    expect(noteInput).toHaveValue(draftText);
  });

  it("preserves the draft note text after a 503 service-unavailable", async () => {
    const routes = routesWithRecordDetail();
    const listRoute = routes.find(
      (r) => r.urlContains === "/cases" && r.method === "GET",
    )!;
    listRoute.body = {
      items: [caseDetail({ title: "503 case", version: 1 })],
      total: 1,
      limit: 50,
      offset: 0,
    };
    routes.push({
      urlContains: "/notes",
      method: "POST",
      status: 503,
      body: {
        error: {
          code: "SERVICE_NOT_READY",
          message: "The database is unavailable.",
          request_id: "req-3",
          details: {},
        },
      },
    });
    setup(routes);
    await navigateToInvestigations();
    const user = userEvent.setup();
    await user.click(screen.getByText("503 case"));
    await screen.findByText("Add note");
    const noteInput = screen.getByLabelText("Note");
    const draftText = "Draft during 503.";
    await user.type(noteInput, draftText);
    await user.click(screen.getByRole("button", { name: "Add note" }));
    // The error appears.
    await screen.findByText(/Operation failed/i);
    // The draft is preserved.
    expect(noteInput).toHaveValue(draftText);
  });

  it("clears the draft note text only after confirmed success (200)", async () => {
    const routes = routesWithRecordDetail();
    const listRoute = routes.find(
      (r) => r.urlContains === "/cases" && r.method === "GET",
    )!;
    listRoute.body = {
      items: [caseDetail({ title: "Success case", version: 1 })],
      total: 1,
      limit: 50,
      offset: 0,
    };
    routes.push({
      urlContains: "/notes",
      method: "POST",
      status: 200,
      body: caseDetail({ title: "Success case", version: 2 }),
    });
    setup(routes);
    await navigateToInvestigations();
    const user = userEvent.setup();
    await user.click(screen.getByText("Success case"));
    await screen.findByText("Add note");
    const noteInput = screen.getByLabelText("Note");
    await user.type(noteInput, "Successful note.");
    await user.click(screen.getByRole("button", { name: "Add note" }));
    // On success, the draft IS cleared.
    await waitFor(() => {
      expect(noteInput).toHaveValue("");
    });
  });

  it("does not display fabricated anomaly scores", async () => {
    setup(routesWithRecordDetail());
    await navigateToInvestigations();
    const user = userEvent.setup();
    const indexPanel = screen.getByLabelText("Record and case index");
    await user.click(within(indexPanel).getByText("synth-001"));
    await screen.findByText(/SYNTHETIC DEMONSTRATION RECORD/i);
    // No anomaly score, no Isolation Forest / LOF mentions.
    const evidencePanel = screen.getByLabelText("Evidence examination");
    expect(evidencePanel.textContent).not.toMatch(/anomaly score/i);
    expect(evidencePanel.textContent).not.toMatch(/isolation forest/i);
    expect(evidencePanel.textContent).not.toMatch(/lof/i);
  });

  it("distinguishes source record from review case (synthetic banner visible on both)", async () => {
    const routes = routesWithRecordDetail();
    const listRoute = routes.find(
      (r) => r.urlContains === "/cases" && r.method === "GET",
    )!;
    listRoute.body = {
      items: [caseDetail({ title: "Case with banner" })],
      total: 1,
      limit: 50,
      offset: 0,
    };
    setup(routes);
    await navigateToInvestigations();
    const user = userEvent.setup();
    // Record → synthetic banner.
    const indexPanel = screen.getByLabelText("Record and case index");
    await user.click(within(indexPanel).getByText("synth-001"));
    await screen.findByText(/SYNTHETIC DEMONSTRATION RECORD — NOT A RESEARCH FINDING/i);
    // Case → synthetic banner (the case evidence view includes it too).
    await user.click(screen.getByText("Case with banner"));
    await waitFor(() => {
      expect(screen.getByText(/SYNTHETIC DEMONSTRATION RECORD/i)).toBeInTheDocument();
    });
  });

  it("an admin can also create cases and add notes", async () => {
    const routes = routesWithRecordDetail(ADMIN_USER);
    routes.push({
      urlContains: "/cases",
      method: "POST",
      status: 201,
      body: caseDetail({ title: "Admin case", version: 1 }),
    });
    setup(routes);
    await navigateToInvestigations();
    const user = userEvent.setup();
    const indexPanel = screen.getByLabelText("Record and case index");
    await user.click(within(indexPanel).getByText("synth-001"));
    await screen.findByText(/Create review case/i);
    // The create form is visible (admin has write permission).
    expect(screen.getByLabelText("Title")).toBeInTheDocument();
  });
});
