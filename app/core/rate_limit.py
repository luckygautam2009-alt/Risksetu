"""
Redis-backed rate limiting utility with graceful local degradation.
"""
from __future__ import annotations

from typing import cast
import uuid

from fastapi import status
import redis
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog

from app.core.redis import get_redis_client

logger = structlog.get_logger("risksetu.rate_limit")


def check_rate_limit(
    user_id: uuid.UUID | str,
    key_prefix: str = "ground_reports",
    limit: int = 10,
    window_seconds: int = 60,
) -> None:
    """Enforce per-user sliding/fixed window rate limit using Redis.

    Raises HTTP 429 if the request count exceeds `limit` within `window_seconds`.
    Fails open gracefully if Redis is unavailable or times out.
    """
    client = get_redis_client()
    key = f"rate_limit:{key_prefix}:{user_id}"

    try:
        raw_val = client.incr(key)
        current_count = cast(int, raw_val)
        if current_count == 1:
            client.expire(key, window_seconds)

        if current_count > limit:
            logger.warning(
                "rate_limit_exceeded",
                user_id=str(user_id),
                key_prefix=key_prefix,
                count=current_count,
                limit=limit,
            )
            raise StarletteHTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {limit} requests per {window_seconds}s.",
            )
    except (redis.RedisError, TimeoutError, ConnectionError, OSError) as exc:
        # Rule #7: Redis failure degrades gracefully rather than blocking core functionality
        logger.warning(
            "rate_limit_redis_unavailable_bypassed",
            user_id=str(user_id),
            error=str(exc),
        )
