"""Structured error contract and exception handlers.

Every error response uses a single machine-readable envelope::

    {
      "error": {
        "code": "SERVICE_NOT_READY",
        "message": "A required application dependency is unavailable.",
        "request_id": "<request id>",
        "details": {}
      }
    }

Rules enforced here:

* Stable machine-readable ``code`` values (see :class:`ErrorCode`).
* Human-readable, sanitized ``message`` values; never a traceback, an
  absolute path, an internal hostname or a credential.
* The request ID is included in the body **and** the ``X-Request-ID``
  header of every error response.
* Pydantic/FastAPI validation failures are reformatted into the same
  envelope, and the raw request input is never echoed back.

Reserved-but-not-implemented codes (documented for later pull requests;
they must not be wired up before the corresponding subsystem exists):
``UNAUTHORIZED`` and ``FORBIDDEN`` (PR-04 authentication),
``CONFLICT`` (PR-03 optimistic case versioning),
``CASE_NOT_FOUND`` (PR-03), ``ARTIFACT_INTEGRITY_FAILED`` and
``ARTIFACT_UNAVAILABLE`` (M2 research-evidence access), and
``RATE_LIMITED`` (hardening).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.contracts.common import ErrorEnvelope, REQUEST_ID_HEADER

logger = logging.getLogger("peiars.api.errors")


class ErrorCode:
    """Stable machine-readable error codes (implemented in PR-02)."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    BAD_REQUEST = "BAD_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    INVALID_SOURCE_ID = "INVALID_SOURCE_ID"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    SERVICE_NOT_READY = "SERVICE_NOT_READY"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    REQUEST_FAILED = "REQUEST_FAILED"


_STATUS_CODE_MAP: dict[int, str] = {
    400: ErrorCode.BAD_REQUEST,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    422: ErrorCode.VALIDATION_ERROR,
    503: ErrorCode.SERVICE_NOT_READY,
}

_DEFAULT_MESSAGES: dict[str, str] = {
    ErrorCode.VALIDATION_ERROR: "The request failed validation.",
    ErrorCode.BAD_REQUEST: "The request could not be understood.",
    ErrorCode.NOT_FOUND: "The requested resource was not found.",
    ErrorCode.METHOD_NOT_ALLOWED: "The request method is not allowed for this resource.",
    ErrorCode.INVALID_SOURCE_ID: "The supplied source identifier is not valid.",
    ErrorCode.SOURCE_NOT_FOUND: "The requested source is not registered.",
    ErrorCode.SERVICE_NOT_READY: "A required application dependency is unavailable.",
    ErrorCode.INTERNAL_SERVER_ERROR: "An unexpected internal error occurred.",
    ErrorCode.REQUEST_FAILED: "The request could not be completed.",
}


class ApiError(Exception):
    """Domain error carrying an HTTP status, a stable code and details.

    Raised by services and endpoints; converted into the structured error
    envelope by :func:`register_exception_handlers`.
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message or _DEFAULT_MESSAGES.get(code, "The request could not be completed.")
        self.details = details or {}
        super().__init__(self.message)


def _request_id(request: Request) -> str:
    """Best-effort request ID (middleware normally sets ``request.state``)."""
    return getattr(request.state, "request_id", None) or request.headers.get(REQUEST_ID_HEADER, "unavailable")


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build the envelope response with the request-ID header attached."""
    envelope = ErrorEnvelope.model_validate(
        {
            "error": {
                "code": code,
                "message": message,
                "request_id": _request_id(request),
                "details": details or {},
            }
        }
    )
    response = JSONResponse(status_code=status_code, content=envelope.model_dump())
    response.headers[REQUEST_ID_HEADER] = envelope.error.request_id
    return response


def _sanitized_validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    """Validation errors without the raw input value or context objects.

    FastAPI includes the submitted ``input`` (and sometimes ``ctx``) in its
    error payloads; both are dropped so request bodies are never echoed
    back into a response.
    """
    sanitized: list[dict[str, Any]] = []
    for item in exc.errors():
        sanitized.append(
            {
                "loc": [str(part) for part in item.get("loc", ())],
                "msg": str(item.get("msg", "")),
                "type": str(item.get("type", "")),
            }
        )
    return sanitized


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the structured error handlers to the application."""

    @app.exception_handler(ApiError)
    async def _api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return _error_response(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(
            request,
            422,
            ErrorCode.VALIDATION_ERROR,
            _DEFAULT_MESSAGES[ErrorCode.VALIDATION_ERROR],
            {"errors": _sanitized_validation_errors(exc)},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODE_MAP.get(exc.status_code, ErrorCode.REQUEST_FAILED)
        return _error_response(request, exc.status_code, code, _DEFAULT_MESSAGES[code])

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Full traceback goes to the server log only, keyed by request ID.
        logger.error(
            "unhandled_exception",
            extra={
                "request_id": _request_id(request),
                "path": request.url.path,
                "method": request.method,
                "exception_type": type(exc).__name__,
            },
            exc_info=True,
        )
        return _error_response(
            request,
            500,
            ErrorCode.INTERNAL_SERVER_ERROR,
            _DEFAULT_MESSAGES[ErrorCode.INTERNAL_SERVER_ERROR],
        )
