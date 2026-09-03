"""
Standard error envelope and exception handling.

Enforces spec §6 ("Standard error") and Constitution rule #8: no raw
exception/stack trace ever reaches the client. Every error response has the
shape:

{
  "error": {
    "code": "...",
    "message": "...",
    "details": [...],
    "request_id": "..."
  }
}
"""
from __future__ import annotations

from typing import Any
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import structlog
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger("risksetu.errors")

_HTTP_STATUS_CODE_MAP = {
    status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
    status.HTTP_408_REQUEST_TIMEOUT: "REQUEST_TIMEOUT",
    status.HTTP_409_CONFLICT: "CONFLICT",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "VALIDATION_ERROR",
    status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_ERROR",
    status.HTTP_502_BAD_GATEWAY: "BAD_GATEWAY",
    status.HTTP_503_SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
    status.HTTP_504_GATEWAY_TIMEOUT: "GATEWAY_TIMEOUT",
}


class AppError(Exception):
    """Base class for domain/application errors with a stable machine code.

    Services should raise subclasses of this (e.g. NotFoundError,
    ConflictError, ForbiddenError) instead of generic exceptions, so the
    error contract stays predictable across all phases.
    """

    code: str = "APPLICATION_ERROR"
    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str, details: list[Any] | None = None) -> None:
        self.message = message
        self.details = details or []
        super().__init__(message)


class NotFoundError(AppError):
    code = "NOT_FOUND"
    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(AppError):
    code = "CONFLICT"
    status_code = status.HTTP_409_CONFLICT


class ForbiddenError(AppError):
    code = "FORBIDDEN"
    status_code = status.HTTP_403_FORBIDDEN


class UnauthorizedError(AppError):
    code = "UNAUTHORIZED"
    status_code = status.HTTP_401_UNAUTHORIZED


class ValidationAppError(AppError):
    code = "VALIDATION_ERROR"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


def _request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if isinstance(rid, str) and rid:
        return rid
    return str(uuid.uuid4())


def _envelope(code: str, message: str, details: list[Any], request_id: str) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id,
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        rid = _request_id(request)
        logger.warning(
            "app_error",
            code=exc.code,
            request_id=rid,
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details, rid),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        rid = _request_id(request)
        # Pydantic error details are safe to return (field-level, no internals).
        details = [
            {"loc": err.get("loc"), "msg": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        logger.warning(
            "validation_error",
            request_id=rid,
            path=request.url.path,
            method=request.method,
            details_count=len(details),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                "VALIDATION_ERROR", "Request validation failed.", details, rid
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        rid = _request_id(request)
        code = _HTTP_STATUS_CODE_MAP.get(exc.status_code, f"HTTP_{exc.status_code}")
        logger.warning(
            "http_exception",
            code=code,
            status_code=exc.status_code,
            request_id=rid,
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, str(exc.detail), [], rid),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        rid = _request_id(request)
        # Full traceback goes to server logs only — NEVER to the client.
        logger.exception(
            "unhandled_exception",
            request_id=rid,
            path=request.url.path,
            method=request.method,
            error_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope(
                "INTERNAL_ERROR",
                "An unexpected error occurred. Please try again.",
                [],
                rid,
            ),
        )

