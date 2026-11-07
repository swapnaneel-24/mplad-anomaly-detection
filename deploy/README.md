# deploy/ — deployment configuration (planned)

Intended responsibility: Docker and deployment configuration introduced in
later pull requests — `compose.yaml` for local integration (API, PostgreSQL
and frontend/proxy with health checks), environment wiring, and eventually
the CI/CD workflow definitions (PR-06).

**Status (PR-01): intentionally free of configuration.** No Dockerfiles,
Compose files or CI workflows are included in this pull request. The
placeholders in the repository-root `.env.example` anticipate the
environment variables these files will consume. No Backblaze B2 or other
object-storage access is required or configured at this stage.
