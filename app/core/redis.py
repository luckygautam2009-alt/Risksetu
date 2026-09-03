"""
Redis connection management and health utilities.

Rule #7 (external dependencies fail gracefully): Redis is an ephemeral cache
and rate-limiting store, NEVER the source of truth for persistent domain state.
"""
from __future__ import annotations

from functools import lru_cache

import redis

import structlog

from app.core.config import get_settings

logger = structlog.get_logger("risksetu.redis")


@lru_cache
def get_redis_pool() -> redis.ConnectionPool:
    """Singleton Redis connection pool; configured from application settings."""
    settings = get_settings()
    return redis.ConnectionPool.from_url(
        settings.redis_url,
        socket_connect_timeout=2.0,
        socket_timeout=2.0,
        retry_on_timeout=True,
        max_connections=20,
    )


def get_redis_client() -> redis.Redis:
    """Return a Redis client bound to the connection pool."""
    return redis.Redis(connection_pool=get_redis_pool())


def check_redis_connection(timeout_seconds: float = 1.0) -> bool:
    """Probe Redis availability without raising exceptions or leaking credentials."""
    settings = get_settings()
    try:
        client = redis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=timeout_seconds,
            socket_timeout=timeout_seconds,
        )
        return bool(client.ping())
    except (redis.RedisError, TimeoutError, ConnectionError, OSError) as exc:
        logger.warning(
            "redis_connection_failed",
            error_type=type(exc).__name__,
        )
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "redis_unexpected_probe_error",
            error_type=type(exc).__name__,
        )
        return False
