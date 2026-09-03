"""
Health and readiness endpoints.

/health  — liveness: process is up. No dependency checks.
/readiness — dependency checks (DB, Redis). Used by orchestrators and by the
             judging-day demo checklist ("Health and readiness endpoints
             tested" in §27).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import text
import structlog

from app.core.redis import check_redis_connection
from app.db.session import engine

logger = structlog.get_logger("risksetu.health")

router = APIRouter(tags=["operations"])


@router.get("/health")
async def health() -> dict[str, Any]:
    """Liveness probe: returns ok as long as the Python application process is running."""
    return {"data": {"status": "ok"}, "meta": {}}


@router.get("/readiness")
async def readiness(response: Response) -> dict[str, Any]:
    """Dependency readiness probe: checks critical operational dependencies.

    Returns HTTP 200 if all dependencies are healthy.
    Returns HTTP 503 if any required dependency (PostgreSQL or Redis) is unavailable.
    Diagnostic details are strictly high-level and safe; no credentials or hostnames are leaked.
    """
    checks: dict[str, str] = {"database": "unknown", "redis": "unknown"}

    # 1. Probe database connectivity with a lightweight query
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness_db_failure", error_type=type(exc).__name__)
        checks["database"] = "error"

    # 2. Probe Redis connectivity via pooled health check
    if check_redis_connection(timeout_seconds=1.0):
        checks["redis"] = "ok"
    else:
        logger.warning("readiness_redis_failure")
        checks["redis"] = "error"

    # 3. Determine overall readiness status and HTTP response code
    if checks["database"] != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        overall_status = "unhealthy"
    elif checks["redis"] != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        overall_status = "degraded"
    else:
        response.status_code = status.HTTP_200_OK
        overall_status = "ok"

    return {
        "data": {
            "status": overall_status,
            "checks": checks,
        },
        "meta": {},
    }

