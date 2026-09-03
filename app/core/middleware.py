"""
Correlation-ID middleware.

Every request gets a request_id, either propagated from an incoming
X-Request-ID header or freshly generated. This ID flows into: the error
envelope (§6), structured logs, and — from Phase 1 onward — the audit_log
table (Constitution rule #2: every state change stores a request/correlation
ID).
"""
from __future__ import annotations

import re
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger("risksetu.request")

_REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


def _is_safe_request_id(request_id: str | None) -> bool:
    """Validate client-supplied request ID length and character set."""
    if not request_id:
        return False
    return bool(_REQUEST_ID_REGEX.fullmatch(request_id.strip()))


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        client_request_id = request.headers.get("X-Request-ID")
        if _is_safe_request_id(client_request_id):
            request_id = client_request_id.strip()  # type: ignore[union-attr]
        else:
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response

