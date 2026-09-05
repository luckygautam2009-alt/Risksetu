"""
RISKSETU AI — Weather response cache backed by Redis.

Cache key format:  weather:v1:{lat_5dp}:{lon_5dp}
TTL:               configurable via WEATHER_CACHE_TTL_SECONDS (default 300 s)

The cache stores the serialised WeatherResponse JSON.  On a cache hit the
data_freshness_seconds field is updated to reflect the true age of the
cached data so the frontend can display "Updated X minutes ago."

Cache failures are always silent — if Redis is unavailable the request
falls through to a live fetch. Cache is never the source of truth.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, cast

import redis
import structlog

from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.services.weather.schemas import WeatherResponse

logger = structlog.get_logger("risksetu.weather.cache")

_CACHE_KEY_PREFIX = "weather:v1"


def _cache_key(lat: float, lon: float) -> str:
    """Deterministic cache key rounded to 5 decimal places (~1 m precision)."""
    return f"{_CACHE_KEY_PREFIX}:{lat:.5f}:{lon:.5f}"


def get_cached_weather(lat: float, lon: float) -> WeatherResponse | None:
    """Return a cached WeatherResponse or None if not cached / cache unavailable."""
    key = _cache_key(lat, lon)
    try:
        client = get_redis_client()
        raw = client.get(key)
        if raw is None:
            return None

        data: dict[str, Any] = json.loads(cast(bytes, raw))

        # Calculate true data age
        fetched_at_str: str = data.get("fetched_at", "")
        try:
            fetched_at = datetime.fromisoformat(fetched_at_str)
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            age_seconds = int((datetime.now(timezone.utc) - fetched_at).total_seconds())
        except (ValueError, TypeError):
            age_seconds = 0

        data["data_freshness_seconds"] = max(0, age_seconds)
        data["provider_status"] = "cached"

        response = WeatherResponse.model_validate(data)
        logger.debug("weather_cache_hit", lat=lat, lon=lon, age_seconds=age_seconds)
        return response

    except (redis.RedisError, json.JSONDecodeError, Exception) as exc:  # noqa: BLE001
        logger.warning("weather_cache_get_error", lat=lat, lon=lon, error_type=type(exc).__name__)
        return None


def set_cached_weather(lat: float, lon: float, response: WeatherResponse) -> None:
    """Store a WeatherResponse in Redis. Silently swallows cache errors."""
    settings = get_settings()
    ttl = settings.weather_cache_ttl_seconds
    key = _cache_key(lat, lon)
    try:
        client = get_redis_client()
        payload = json.dumps(response.model_dump(mode="json"))
        client.setex(key, ttl, payload)
        logger.debug("weather_cache_set", lat=lat, lon=lon, ttl_seconds=ttl)
    except (redis.RedisError, Exception) as exc:  # noqa: BLE001
        logger.warning("weather_cache_set_error", lat=lat, lon=lon, error_type=type(exc).__name__)
