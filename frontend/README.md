# frontend/ — PEIARS web client (planned)

Intended responsibility: the **React + TypeScript single-page application**
built with Vite — UI components, routing for the six PEIARS workspaces
(Overview, Data Observatory, Anomaly Analysis, Investigation, Cross-Domain
Study, Research & Provenance), and the typed API client that talks to the
backend exclusively through the versioned `/api/v1` JSON API.

**Status (PR-01): directory and conventions only.** No application code, no
dependencies and no build configuration exist yet. The React application is
introduced from PR-05 onward, after the API contracts exist.

## Node.js / npm

- Selected baseline: **Node.js 22 LTS**, recorded in `.nvmrc`.
- The delivery sandbox validated the toolchain with Node v24.22.2 /
  npm 11.19.1; both the 22 LTS and 24 LTS lines are supported targets.
- The final pin is confirmed on the maintainer machine when the first
  frontend dependencies are introduced (ADR-001 version gate), together
  with a committed lockfile so `npm ci` reproduces installs exactly.

## Rules

- The frontend never performs model fitting, thresholding or recalculation
  of research results; it renders stored, manifest-backed data only.
- The frontend never receives filesystem paths, object-storage keys or
  unrestricted dataset exports from the API.
- See `docs/architecture/workspace-conventions.md` for the allowed
  dependency directions and testing conventions.
