"""Deterministic OpenAPI schema generation with a normalized 422 contract.

FastAPI auto-registers a ``HTTPValidationError`` / ``ValidationError`` model
for every route that carries Pydantic query, path or body parameters and
documents the automatic 422 response against that model.  PEIARS replaces
every 422 response at runtime with the shared :class:`ErrorEnvelope`
(see :mod:`app.core.errors`), so the published schema must agree: **every
422 response references ``ErrorEnvelope`` and the stale FastAPI validation
models are absent from the components.**

This module post-processes FastAPI's generated schema so the published
contract always matches the runtime contract, even for routes that do not
declare an explicit ``responses={422: ...}`` override.  The per-route
overrides remain the primary mechanism; this is the safety net that keeps
the contract honest as routes are added.

The post-processing is deterministic and side-effect free: the same code
version always produces byte-identical output.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

#: The FastAPI-generated model names that must never appear in the published
#: schema once normalization has run.
_LEGACY_VALIDATION_MODELS = ("HTTPValidationError", "ValidationError")

#: The ref fragment that points at the legacy 422 model.
_LEGACY_REF_FRAGMENT = "HTTPValidationError"

#: The ref fragment that points at the shared error envelope.
_ENVELOPE_REF_FRAGMENT = "ErrorEnvelope"


def _normalize_refs(node: Any) -> Any:
    """Recursively rewrite ``HTTPValidationError`` refs to ``ErrorEnvelope``.

    Returns the node with every ``$ref`` whose fragment is
    ``HTTPValidationError`` rewritten to point at ``ErrorEnvelope``.
    Dicts and lists are rebuilt so the replacement propagates to the
    parent container.
    """
    if isinstance(node, dict):
        rewritten: dict[str, Any] = {}
        for key, value in node.items():
            if (
                key == "$ref"
                and isinstance(value, str)
                and value.endswith(f"/{_LEGACY_REF_FRAGMENT}")
            ):
                rewritten[key] = value[: -len(_LEGACY_REF_FRAGMENT)] + _ENVELOPE_REF_FRAGMENT
            else:
                rewritten[key] = _normalize_refs(value)
        return rewritten
    if isinstance(node, list):
        return [_normalize_refs(item) for item in node]
    return node


def _drop_legacy_validation_models(components: dict[str, Any]) -> None:
    """Remove the unused validation-error component schemas in place."""
    schemas = components.get("schemas")
    if not isinstance(schemas, dict):
        return
    for name in _LEGACY_VALIDATION_MODELS:
        schemas.pop(name, None)


def _normalize_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Rewrite 422 refs to ``ErrorEnvelope`` and drop stale component schemas."""
    schema = _normalize_refs(schema)
    components = schema.get("components")
    if isinstance(components, dict):
        _drop_legacy_validation_models(components)
    return schema


def build_openapi_schema(app: FastAPI) -> dict[str, Any]:
    """Generate and normalize the OpenAPI schema for ``app``.

    The schema is generated through FastAPI's standard utility and then
    post-processed so the published 422 contract matches the runtime
    :class:`ErrorEnvelope`.  No timestamps or random identifiers are
    introduced; the output is reproducible for a given code version.
    """
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        openapi_version=app.openapi_version,
    )
    return _normalize_schema(schema)
