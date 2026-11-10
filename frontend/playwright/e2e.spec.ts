// PEIARS PR-05A redesign — end-to-end tests.
//
// These tests exercise the real browser → Vite proxy → backend →
// PostgreSQL stack. They require:
//   1. A disposable PostgreSQL instance (via `pgserver`).
//   2. The backend running on :8000 with PEIARS_DATABASE_REQUIRED=true
//      and a synthetic reviewer user created via the helper script.
//   3. The Vite dev server on :5173.
//
// The playwright.config.ts `webServer` array starts both servers. The
// synthetic reviewer user must be created BEFORE the backend starts;
// the helper script `playwright/setup-reviewer.py` does this.
//
// Updated for the PR-05A redesign:
//   - The permanent left sidebar is gone; the workspace switcher is a
//     horizontal tab list with role="tablist" aria-label="Workspaces".
//   - The application is desktop-only; viewport is set to 1440×900 by
//     default. A separate test verifies the DesktopGate below 1280px.

import { expect, test } from "@playwright/test";

const REVIEWER_USERNAME = process.env.PEIARS_E2E_USERNAME ?? "reviewer_e2e";
const REVIEWER_PASSWORD = process.env.PEIARS_E2E_PASSWORD ?? "test-reviewer-password-1234";

test.describe.configure({ mode: "serial" });

test.describe("PEIARS E2E (desktop redesign)", () => {
  test.beforeEach(async ({ page }) => {
    // Desktop viewport for all tests (the application is desktop-only).
    await page.setViewportSize({ width: 1440, height: 900 });
  });

  test("1. Open / → redirect to /login", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { name: "PEIARS", level: 1 })).toBeVisible();
  });

  test("2. Direct navigation to /overview while unauthenticated → redirect to /login", async ({ page }) => {
    await page.goto("/overview");
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByLabel("Username")).toBeVisible();
  });

  test("3. Login screen renders identity + lede + form + connectivity hint", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "PEIARS", level: 1 })).toBeVisible();
    await expect(page.getByText(/anomaly flag/i)).toBeVisible();
    await expect(page.getByLabel("Username")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
    await expect(page.getByText(/API reachable|API unreachable|Checking API/i)).toBeVisible({ timeout: 10_000 });
  });

  test("4. Submit login with synthetic reviewer → redirect to /overview", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Username").fill(REVIEWER_USERNAME);
    await page.getByLabel("Password").fill(REVIEWER_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/overview/);
    await expect(page.getByRole("heading", { name: "Study Overview", level: 1 })).toBeVisible();
  });

  test("5. /auth/me called on session restore", async ({ page }) => {
    const mePromise = page.waitForResponse((resp) => resp.url().includes("/api/v1/auth/me"), { timeout: 10_000 });
    await page.goto("/login");
    await page.getByLabel("Username").fill(REVIEWER_USERNAME);
    await page.getByLabel("Password").fill(REVIEWER_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/overview/);
    await mePromise;
  });

  test("6. Horizontal switcher shows 6 workspace tabs; identity bar shows user + role", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Username").fill(REVIEWER_USERNAME);
    await page.getByLabel("Password").fill(REVIEWER_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/overview/);

    const switcher = page.getByRole("tablist", { name: "Workspaces" });
    await expect(switcher).toBeVisible();
    await expect(switcher.getByRole("tab", { name: /Overview/ })).toBeVisible();
    await expect(switcher.getByRole("tab", { name: /Data/ })).toBeVisible();
    await expect(switcher.getByRole("tab", { name: /Analysis/ })).toBeVisible();
    await expect(switcher.getByRole("tab", { name: /Investigations/ })).toBeVisible();
    await expect(switcher.getByRole("tab", { name: /Domains/ })).toBeVisible();
    await expect(switcher.getByRole("tab", { name: /Research/ })).toBeVisible();

    // Identity bar shows the role label (uppercase).
    await expect(page.getByText("REVIEWER", { exact: true })).toBeVisible();
    // No permanent left sidebar.
    await expect(page.getByLabel("Workspace navigation")).toHaveCount(0);
  });

  test("7. Click each workspace tab → H1 and document.title change", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Username").fill(REVIEWER_USERNAME);
    await page.getByLabel("Password").fill(REVIEWER_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/overview/);

    const labels: [string, string][] = [
      ["Overview", "Study Overview"],
      ["Data", "Data Observatory"],
      ["Analysis", "Anomaly Analysis"],
      ["Investigations", "Investigation Workspace"],
      ["Domains", "Cross-Domain Study"],
      ["Research", "Research & Provenance"],
    ];
    for (const [tabLabel, h1] of labels) {
      await page.getByRole("tab", { name: new RegExp(tabLabel) }).click();
      await expect(page.getByRole("heading", { name: h1, level: 1 })).toBeVisible();
      expect(await page.title()).toBe(`${h1} · PEIARS`);
    }
  });

  test("8. Refresh the page → session restored (no redirect to /login)", async ({ page, context }) => {
    await page.goto("/login");
    await page.getByLabel("Username").fill(REVIEWER_USERNAME);
    await page.getByLabel("Password").fill(REVIEWER_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/overview/);

    await page.reload();
    await expect(page).toHaveURL(/\/overview/);
    await expect(page.getByRole("heading", { name: "Study Overview", level: 1 })).toBeVisible();
    const cookies = await context.cookies();
    expect(cookies.some((c) => c.name === "peiars_session")).toBeTruthy();
  });

  test("9. Click logout → redirect to /login", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Username").fill(REVIEWER_USERNAME);
    await page.getByLabel("Password").fill(REVIEWER_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/overview/);

    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByLabel("Username")).toBeVisible();
  });

  test("10. Direct navigation to /overview with revoked session → redirect to /login", async ({ page, context }) => {
    await page.goto("/login");
    await page.getByLabel("Username").fill(REVIEWER_USERNAME);
    await page.getByLabel("Password").fill(REVIEWER_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/overview/);

    const cookiesBefore = await context.cookies();
    const sessionCookie = cookiesBefore.find((c) => c.name === "peiars_session");
    expect(sessionCookie).toBeTruthy();

    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login/);

    if (sessionCookie) {
      await context.addCookies([
        {
          name: "peiars_session",
          value: sessionCookie.value,
          domain: "127.0.0.1",
          path: "/",
          httpOnly: true,
          secure: false,
          sameSite: "Lax",
        },
      ]);
    }

    await page.goto("/overview");
    await expect(page).toHaveURL(/\/login/);
  });

  test("11. DesktopGate appears below 1280px width", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Username").fill(REVIEWER_USERNAME);
    await page.getByLabel("Password").fill(REVIEWER_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/overview/);

    // Narrow the viewport below the desktop minimum.
    await page.setViewportSize({ width: 1024, height: 768 });
    await expect(page.getByText(/Desktop window required/i)).toBeVisible({ timeout: 5_000 });
    // The identity bar and switcher remain visible.
    await expect(page.getByText("PEIARS").first()).toBeVisible();
    await expect(page.getByRole("tablist", { name: "Workspaces" })).toBeVisible();
    // The workspace composition (study title) is hidden.
    await expect(page.getByText(/MPLAD Fund-Utilisation/i)).toHaveCount(0);
  });

  test("12. Capture screenshots at specified resolutions", async ({ browser }) => {
    // Login — 1440×900
    const ctx1440 = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page1440 = await ctx1440.newPage();
    await page1440.goto("/login");
    await page1440.waitForLoadState("networkidle");
    await page1440.screenshot({ path: "screenshots/01-login-1440.png", fullPage: true });

    // Overview — 1440×900
    await page1440.getByLabel("Username").fill(REVIEWER_USERNAME);
    await page1440.getByLabel("Password").fill(REVIEWER_PASSWORD);
    await page1440.getByRole("button", { name: "Sign in" }).click();
    await expect(page1440).toHaveURL(/\/overview/);
    await page1440.waitForLoadState("networkidle");
    await page1440.screenshot({ path: "screenshots/02-overview-1440.png", fullPage: true });

    // Analysis — 1440×900
    await page1440.getByRole("tab", { name: /Analysis/ }).click();
    await page1440.waitForLoadState("networkidle");
    await page1440.screenshot({ path: "screenshots/03-analysis-1440.png", fullPage: true });

    // Investigation — 1440×900
    await page1440.getByRole("tab", { name: /Investigations/ }).click();
    await page1440.waitForLoadState("networkidle");
    await page1440.screenshot({ path: "screenshots/04-investigations-1440.png", fullPage: true });

    // Data Observatory — 1366×768
    const ctx1366 = await browser.newContext({ viewport: { width: 1366, height: 768 } });
    const page1366 = await ctx1366.newPage();
    await page1366.goto("/login");
    await page1366.getByLabel("Username").fill(REVIEWER_USERNAME);
    await page1366.getByLabel("Password").fill(REVIEWER_PASSWORD);
    await page1366.getByRole("button", { name: "Sign in" }).click();
    await expect(page1366).toHaveURL(/\/overview/);
    await page1366.getByRole("tab", { name: /Data/ }).click();
    await page1366.waitForLoadState("networkidle");
    await page1366.screenshot({ path: "screenshots/05-data-1366.png", fullPage: true });

    // Research & Provenance — 1920×1080
    const ctx1920 = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
    const page1920 = await ctx1920.newPage();
    await page1920.goto("/login");
    await page1920.getByLabel("Username").fill(REVIEWER_USERNAME);
    await page1920.getByLabel("Password").fill(REVIEWER_PASSWORD);
    await page1920.getByRole("button", { name: "Sign in" }).click();
    await expect(page1920).toHaveURL(/\/overview/);
    await page1920.getByRole("tab", { name: /Research/ }).click();
    await page1920.waitForLoadState("networkidle");
    await page1920.screenshot({ path: "screenshots/06-research-1920.png", fullPage: true });

    // 1280px width check (minimum supported).
    const ctx1280 = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page1280 = await ctx1280.newPage();
    await page1280.goto("/login");
    await page1280.getByLabel("Username").fill(REVIEWER_USERNAME);
    await page1280.getByLabel("Password").fill(REVIEWER_PASSWORD);
    await page1280.getByRole("button", { name: "Sign in" }).click();
    await expect(page1280).toHaveURL(/\/overview/);
    await page1280.waitForLoadState("networkidle");
    await page1280.screenshot({ path: "screenshots/07-overview-1280.png", fullPage: true });
    // No horizontal scroll at 1280px.
    const scrollWidth = await page1280.evaluate(() => document.documentElement.scrollWidth);
    expect(scrollWidth).toBeLessThanOrEqual(1280);

    await ctx1440.close();
    await ctx1366.close();
    await ctx1920.close();
    await ctx1280.close();
  });
});
