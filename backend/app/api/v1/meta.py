"""Metadata endpoint (``GET /api/v1/meta``).

Returns non-sensitive application metadata: application name, API version,
backend application version, the Git commit SHA **if supplied by the
deployment environment** (never fabricated), the environment name, and the
implemented-versus-planned status of application features and subsystems.

Nothing here exposes secrets, storage credentials, absolute paths,
internal hostnames or private repository details.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.contracts.common import MetaResponse

router = APIRouter(tags=["metadata"])

#: Implemented features (PR-02 + PR-03 + PR-04 + PR-05A + PR-05B scope).
_IMPLEMENTED_FEATURES: dict[str, str] = {
    "health_endpoints": "implemented",
    "metadata_endpoint": "implemented",
    "structured_error_envelope": "implemented",
    "request_id_tracing": "implemented",
    "cors_configuration": "implemented",
    "source_registry_interface": "implemented",
    "openapi_contract_export": "implemented",
    # PR-03: persistence foundation implemented.
    "review_case_persistence": "implemented",
    "append_only_case_history": "implemented",
    "optimistic_concurrency": "implemented",
    "schema_migrations": "implemented",
    "database_readiness_probe": "implemented",
    # PR-04: authentication foundation implemented.
    "local_account_authentication": "implemented",
    "server_side_sessions": "implemented",
    "role_based_authorization": "implemented",
    "csrf_protection": "implemented",
    "login_throttling": "implemented",
    "authenticated_actor_identity": "implemented",
    # PR-05B: authenticated case API + synthetic demonstration source.
    "public_case_api": "implemented",
    "synthetic_demonstration_source": "implemented",
    "investigation_workflow": "implemented",
    # Still planned
    "user_management_api": "planned",
    "research_evidence_access": "planned",
    "record_lookup": "planned",
    "pmgsy_data_observatory": "planned",
    "mplads_reconciliation": "planned",
    "deployment": "planned",
}

#: Availability of major application subsystems (PR-05B state).
_SUBSYSTEM_STATES: dict[str, str] = {
    "api": "available",
    "source_registry": "available",
    # PR-03: persistence layer implemented.
    "review_case_persistence": "available",
    "database": "available",
    # PR-04: authentication implemented.
    "authentication": "available",
    # PR-05B: public case API implemented.
    "public_case_api": "available",
    "synthetic_demonstration_source": "available",
    # Still not integrated
    "research_evidence_service": "not_integrated",
}


@router.get(
    "/meta",
    response_model=MetaResponse,
    summary="Application metadata",
    description="Non-sensitive build and capability metadata. The Git commit "
    "SHA is included only when supplied by the deployment environment.",
)
async def meta(request: Request) -> MetaResponse:
    settings = request.app.state.settings
    return MetaResponse(
        application=settings.app_name,
        api_version="v1",
        app_version=settings.app_version,
        git_commit_sha=settings.git_commit_sha,
        environment=settings.environment,
        features=_IMPLEMENTED_FEATURES,
        subsystems=_SUBSYSTEM_STATES,
    )
