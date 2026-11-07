# backend/ — PEIARS API application (planned)

Intended responsibility: the **FastAPI application** — HTTP transport,
typed Pydantic API contracts under `/api/v1`, authentication boundaries and
application services. Persistent review-case data lives in its own
PostgreSQL database; research artifacts are consumed strictly read-only
through approved server-side adapters with manifest verification.

**Status (PR-01): directory and conventions only.** The FastAPI application
factory, health/meta endpoints and error envelopes arrive in PR-02.

## Relationship to the research package

- The existing research package `src/mplad/` is imported **without package
  installation**: the repository uses an explicit src layout where
  `tests/conftest.py` (and the research notebook bootstrap) insert
  `<repo>/src` into `sys.path`. There is no `pyproject.toml` or
  `setup.py` today, and PR-01 does not introduce any.
- The backend will reuse this documented adapter approach (a single,
  reviewed `sys.path` bootstrap) or adopt proper packaging via a
  **separately reviewed change** — it must not silently introduce a
  conflicting package root or alter existing import behavior.
- Research dependencies (NumPy, SciPy, scikit-learn, Pandas, ...) are not
  upgraded as part of application work. Backend dependencies will be
  managed separately from PR-02 onward to avoid destabilizing the research
  environment.

## Python

Supported research Python version: **3.12.x** (the PR-01 sandbox validation
used Python 3.12.16). The backend targets the same interpreter line.
