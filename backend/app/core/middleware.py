"""Request tracing middleware and structured logging.

Properties implemented here:

* A unique request ID is generated for every incoming request.
* A caller-provided ``X-Request-ID`` is accepted **only** after strict
  validation (``[A-Za-z0-9._-]{1,64}``); anything else is replaced by a
  fresh server-side ID.
* The ID is returned in the ``X-Request-ID`` response header (also on
  error responses — the error handlers attach it independently) and made
  available to handlers via ``request.state.request_id``.
* One structured JSON log line is emitted per request containing only:
  event, request id, method, path, status code and duration. Query
  strings, headers (including ``Authorization`` and ``Cookie``), cookies
  and request bodies are never logged.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"

#: Strict format a caller-supplied request/correlation ID must satisfy.
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

_RESERVED_LOG_RECORD_FIELDS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter for the ``peiars`` logger tree."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_LOG_RECORD_FIELDS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure the ``peiars`` logger tree (idempotent).

    A single stream handler with the JSON formatter is attached once; the
    level can be adjusted per application instance.
    """
    root = logging.getLogger("peiars")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)


def generate_request_id() -> str:
    """Generate a new opaque server-side request ID."""
    return uuid.uuid4().hex


def resolve_request_id(incoming: str | None) -> str:
    """Strictly validate a caller-supplied ID or generate a new one."""
    if incoming and REQUEST_ID_PATTERN.fullmatch(incoming):
        return incoming
    return generate_request_id()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a request ID to every request and response, and log access."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            # The registered exception handlers normally convert errors to
            # responses; this branch covers anything that still escapes.
            logging.getLogger("peiars.api").exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            raise
        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        logging.getLogger("peiars.api").info(
            "http_request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
