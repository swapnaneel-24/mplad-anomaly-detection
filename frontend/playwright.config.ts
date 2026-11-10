// Playwright configuration for PEIARS PR-05A E2E.
//
// Starts both the backend (port 8000) and the Vite dev server (port 5173)
// via the `webServer` array. The backend requires PostgreSQL — for E2E
// we point it at a disposable `pgserver`-backed database and create a
// synthetic reviewer user before the run begins.
//
// NOTE: genuine E2E execution in this sandbox requires `pgserver` to be
// installed in the Python environment and a backend process that can
// reach it. The test file (`playwright/e2e.spec.ts`) is a real Playwright
// test; if the backend cannot be started, the test is skipped with a
// documented reason in TEST_REPORT.md.

import { defineConfig, devices } from "@playwright/test";

const FRONTEND_URL = "http://127.0.0.1:5173";
const BACKEND_URL = "http://127.0.0.1:8000";

export default defineConfig({
  testDir: "./playwright",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  timeout: 30_000,
  expect: { timeout: 5_000 },
  use: {
    baseURL: FRONTEND_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: "cd ../backend && PEIARS_DATABASE_URL=${PEIARS_DATABASE_URL:-postgresql+psycopg://peiars:peiars@127.0.0.1:5433/peiars_e2e} PEIARS_DATABASE_REQUIRED=true PEIARS_SESSION_SECRET=${PEIARS_SESSION_SECRET:-0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef} PEIARS_SESSION_COOKIE_SECURE=false PEIARS_CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173 python scripts/serve.py --host 127.0.0.1 --port 8000",
      url: `${BACKEND_URL}/api/v1/health/live`,
      reuseExistingServer: true,
      timeout: 60_000,
      env: {
        // The synthetic reviewer user is created by a startup script (see
        // playwright/setup-reviewer.py) before the backend is started.
      },
    },
    {
      command: "npm run dev",
      url: FRONTEND_URL,
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
