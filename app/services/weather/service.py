"""
RISKSETU AI — WeatherService: cache-aware orchestrator.

Checks Redis cache first; falls through to the live provider on miss.
Caches successful (OK) responses only — never caches error states.
"""
from __future__ import annotations

import structlog

from app.services.weather.cache import get_cached_weather, set_cached_weather
from app.services.weather.provider import OpenMeteoProvider, WeatherProvider
from app.services.weather.schemas import ProviderStatus, WeatherResponse

logger = structlog.get_logger("risksetu.weather.service")


class WeatherService:
    """Cache-aware weather data service.

    Args:
        provider: WeatherProvider implementation.  Defaults to OpenMeteoProvider.
                  Inject a mock provider in tests.
    """

    def __init__(self, provider: WeatherProvider | None = None) -> None:
        self._provider = provider or OpenMeteoProvider()

    async def get_weather(self, lat: float, lon: float) -> WeatherResponse:
        """Return weather for the given coordinates.

        1. Check Redis cache — return cached response if present.
        2. Fetch from the live provider.
        3. Cache successful responses.
        4. Return the response (successful or error state).
        """
        cached = get_cached_weather(lat, lon)
        if cached is not None:
            logger.debug("weather_serving_from_cache", lat=lat, lon=lon)
            return cached

        response = await self._provider.fetch(lat, lon)

        if response.provider_status == ProviderStatus.OK:
            set_cached_weather(lat, lon, response)

        return response
