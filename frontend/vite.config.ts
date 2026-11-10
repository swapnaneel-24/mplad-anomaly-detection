import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

// PR-05A Vite configuration.
//
// Same-origin arrangement: the React dev server proxies /api to the FastAPI
// backend (default http://127.0.0.1:8000). This sidesteps the backend's
// CORS allow_methods (GET, OPTIONS only) and keeps cookies same-origin, so
// the signed double-submit CSRF flow and the HttpOnly session cookie work
// without any backend modification. The proxy is development-only; in
// production the frontend and API are served from the same origin (PR-06+).
//
// Override the backend target with PEIARS_BACKEND_URL if you run uvicorn on
// a different port.
const backendUrl = process.env.PEIARS_BACKEND_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      // All API traffic is same-origin in dev: the browser hits :5173/api
      // and Vite forwards it to :8000. Cookies, CSRF and credentials all
      // stay on localhost:5173 from the browser's perspective.
      "/api": {
        target: backendUrl,
        changeOrigin: false,
        // Cookies carry no Domain attribute (host-only); with changeOrigin
        // false the Host header stays at localhost:5173, which is what the
        // backend's CORS allow_origins expects.
        cookieDomainRewrite: "",
        // Keep the cookie path at "/" (the backend sets path="/"). The
        // previous value "/api/" scoped the CSRF cookie to /api/* which
        // made it invisible to document.cookie on SPA routes — breaking
        // the signed double-submit CSRF flow.
        cookiePathRewrite: "/",
        // X-Forwarded-* are not set; the backend's request-id middleware
        // generates its own ID and the CSRF Origin check compares against
        // request.base_url, which Vite leaves as http://localhost:5173.
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    target: "es2022",
    chunkSizeWarningLimit: 600,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    css: false,
    include: ["tests/unit/**/*.{test,spec}.{ts,tsx}", "tests/integration/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["tests/e2e/**", "node_modules/**", "dist/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/main.tsx", "src/**/*.d.ts"],
    },
  },
});
