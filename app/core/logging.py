"""
Structured logging setup.

Constitution rule #2 (auditable state changes) and the hardening checklist
item "No sensitive tokens/passwords in logs" both depend on logging being
structured and correlation-ID aware from day one, rather than retrofitted.
"""
from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

from app.core.config import get_settings


_SENSITIVE_KEY_PATTERNS = {
    "password",
    "passwd",
    "pwd",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "jwt",
    "secret",
    "authorization",
    "auth",
    "api_key",
    "apikey",
    "private_key",
    "cookie",
    "credential",
    "report_content",
    "aadhaar",
    "uidai",
    "otp",
    "biometric",
    "kyc",
    "id_token",
    "identity_raw",
}

_BEARER_REGEX = re.compile(r"^(Bearer\s+)[A-Za-z0-9_\-\.]+$", re.IGNORECASE)
_JWT_REGEX = re.compile(r"^[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+$")
_AADHAAR_REGEX = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")


def _is_sensitive_key(key: str) -> bool:
    key_lower = key.lower()
    return any(p in key_lower for p in _SENSITIVE_KEY_PATTERNS)


def _redact_value(key: str, val: Any) -> Any:
    if isinstance(val, dict):
        return {k: _redact_value(k, v) for k, v in val.items()}
    if isinstance(val, list):
        return [_redact_value(key, item) for item in val]
    if _is_sensitive_key(key):
        return "***REDACTED***"
    if isinstance(val, str):
        if _BEARER_REGEX.match(val) or _JWT_REGEX.match(val):
            return "***REDACTED***"
        if _AADHAAR_REGEX.search(val):
            return _AADHAAR_REGEX.sub("***REDACTED-AADHAAR***", val)
    return val


def _scrub_sensitive(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key in list(event_dict.keys()):
        event_dict[key] = _redact_value(key, event_dict[key])
    return event_dict



def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.log_level,
    )

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _scrub_sensitive,
    ]

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if settings.log_json
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(processor=renderer)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(settings.log_level)


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)

