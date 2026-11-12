# PEIARS frontend runtime image (PR-06B) — multi-stage.
#
# Stage 1 (build): Node 22 LTS + npm ci + `npm run build` produces a static
#   Vite bundle in /app/dist. This stage contains the full source tree and
#   devDependencies (TypeScript, Vite, ESLint) needed to typecheck and build,
#   but it is DISCARDED.
#
# Stage 2 (runtime): nginx:1.27-alpine serves the built /dist as static
#   assets with SPA fallback and a reverse-proxy of /api/ to the backend
#   Compose service. No source tree, no node_modules, no Python, no backend
#   source, no research datasets, no secrets.
#
# Build context: `frontend/` (see compose.yaml / .dockerignore). The OpenAPI
# drift check (`npm run openapi:check`) reads ../backend/contracts/openapi.json
# and is run in CI, NOT as part of the production build — the committed
# src/api/contracts.gen.ts is bundled as-is.

# ===========================================================================
# Stage 1 — build the static bundle
# ===========================================================================
FROM node:22-bookworm-slim AS build

WORKDIR /app

# Install dependencies from the committed lockfile reproducibly. npm ci
# refuses to run if package.json and package-lock.json are out of sync.
COPY package.json package-lock.json ./
RUN npm ci

# Copy ONLY the build inputs `tsc --noEmit && vite build` actually reads.
# Verified against the repo: tsconfig.json (tsc), vite.config.ts (vite),
# index.html (vite entry), src/ (the application). There is no public/
# directory. eslint.config.js is included so `npm run lint` works if a
# future build step adds it; scripts/ (check-openapi.mjs, run-e2e.sh,
# pgserver helpers) is NOT copied — none of it is needed for the production
# build, and the OpenAPI drift check runs in CI against the host checkout,
# not inside this image. .dockerignore excludes node_modules/dist/.env/tests.
COPY tsconfig.json vite.config.ts eslint.config.js index.html ./
COPY src/ ./src/

# Production build = `tsc --noEmit && vite build`. Emits /app/dist.
# VITE_TARGET / API base: the app uses a relative `/api/v1` base (same-origin
# through the nginx proxy), so no build-time API URL must be baked in.
RUN npm run build

# ===========================================================================
# Stage 2 — minimal static-serving runtime
# ===========================================================================
FROM nginx:1.27-alpine AS runtime

# OCI metadata only; no secrets.
LABEL org.opencontainers.image.title="PEIARS frontend" \
      org.opencontainers.image.description="Static Vite build served by nginx with SPA fallback and /api reverse proxy for the PEIARS local Compose stack." \
      org.opencontainers.image.source="https://github.com/swapnaneel-24/mplad-anomaly-detection" \
      org.opencontainers.image.licenses="UNLICENSED"

# The built bundle only. No source, no node_modules, no maps-only debug data
# beyond what `vite build` emits (sourcemap=true is retained for local
# debugging; strip in production by setting build.sourcemap=false).
COPY --from=build /app/dist /usr/share/nginx/html

# Reverse-proxy + SPA config. See frontend/nginx/default.conf for the exact
# header-forwarding contract (Host, X-Forwarded-For, X-Forwarded-Proto,
# Cookie/Set-Cookie preserved; no path rewriting; no cookie attribute
# stripping).
COPY nginx/default.conf /etc/nginx/conf.d/default.conf

# nginx runs as non-root by default in the official image's unprivileged
# variant only; the standard alpine image listens on 80 as root. To keep the
# local stack simple and documented, we keep the standard image and expose 80.
# A hardened deployment should switch to nginxinc/nginx-unprivileged and port
# 8080 (out of scope for PR-06B's local-development security context).
EXPOSE 80

# Graceful shutdown: nginx handles SIGTERM (sent by `docker compose stop`)
# and closes connections when `daemon off;` is set (the default CMD of the
# official image). No override needed.
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=10 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
