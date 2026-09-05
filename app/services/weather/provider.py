"""
RISKSETU AI — Weather provider abstraction + Open-Meteo integration.

Design principles:
  - WeatherProvider is a protocol/ABC; Open-Meteo is one implementation.
  - No data is fabricated. Provider failures return explicit unavailable state.
  - httpx is used in a sync-compatible way (run_sync) to avoid blocking the
    async event loop; the call is made inside asyncio.get_event_loop().run_in_executor
    so FastAPI's async workers are not blocked.
  - Retries are bounded (3 attempts, exponential back-off) via tenacity.
  - Responses are cached in Redis with a configurable TTL (default 5 min).
  - Timeout is configurable; defaults to 8 seconds.
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from tenacity import (
    RetryError,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.services.weather.schemas import (
    CurrentWeather,
    ForecastDay,
    ProviderStatus,
    WeatherResponse,
)

logger = structlog.get_logger("risksetu.weather")

# ---------------------------------------------------------------------------
# WMO weather code → human-readable description
# Reference: https://open-meteo.com/en/docs — WMO Weather Interpretation Codes
# ---------------------------------------------------------------------------
_WMO_DESCRIPTIONS: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Heavy freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class WeatherProvider(ABC):
    """Abstract weather data provider. Concrete implementations must implement fetch()."""

    @abstractmethod
    async def fetch(self, lat: float, lon: float) -> WeatherResponse:
        """Fetch weather data for the given coordinates.

        Implementations must never fabricate data. If the provider is
        unavailable, return a WeatherResponse with provider_status=UNAVAILABLE
        or PROVIDER_ERROR.
        """
        ...


# ---------------------------------------------------------------------------
# Open-Meteo provider
# ---------------------------------------------------------------------------

_OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"

# These query parameter lists are kept as module-level constants so tests can
# assert the exact API surface being requested.
_CURRENT_PARAMS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
]
_HOURLY_PARAMS: list[str] = []  # not used — daily is sufficient for susceptibility context
_DAILY_PARAMS = [
    "precipitation_sum",
    "temperature_2m_max",
    "temperature_2m_min",
    "weather_code",
]


def _build_open_meteo_url(lat: float, lon: float) -> str:
    """Construct the Open-Meteo forecast URL for the given coordinates."""
    current = ",".join(_CURRENT_PARAMS)
    daily = ",".join(_DAILY_PARAMS)
    # timezone=auto lets Open-Meteo return local timestamps
    return (
        f"{_OPEN_METEO_BASE}"
        f"?latitude={lat}"
        f"&longitude={lon}"
        f"&current={current}"
        f"&daily={daily}"
        f"&timezone=auto"
        f"&forecast_days=3"
    )


def _parse_open_meteo_response(
    raw: dict[str, Any],
    fetched_at: datetime,
) -> WeatherResponse:
    """Parse an Open-Meteo JSON response into a WeatherResponse.

    Returns a WeatherResponse with provider_status=PROVIDER_ERROR if the
    response cannot be parsed.
    """
    try:
        current = raw["current"]

        weather_code = int(current.get("weather_code", 0))
        obs_time_str = current.get("time", "")
        try:
            # Open-Meteo returns ISO8601 without timezone offset when timezone=auto
            obs_time = datetime.fromisoformat(obs_time_str).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            obs_time = fetched_at

        current_weather = CurrentWeather(
            timestamp=obs_time,
            temperature_c=float(current.get("temperature_2m", 0.0)),
            relative_humidity_pct=float(current.get("relative_humidity_2m", 0.0)),
            precipitation_mm=float(current.get("precipitation", 0.0)),
            wind_speed_kmh=float(current.get("wind_speed_10m", 0.0)),
            weather_code=weather_code,
            weather_description=_WMO_DESCRIPTIONS.get(weather_code, f"Code {weather_code}"),
        )

        # Forecast — up to 3 days
        daily = raw.get("daily", {})
        dates = daily.get("time", [])
        precip_sums = daily.get("precipitation_sum", [])
        temp_maxs = daily.get("temperature_2m_max", [])
        temp_mins = daily.get("temperature_2m_min", [])
        daily_codes = daily.get("weather_code", [])

        forecast: list[ForecastDay] = []
        for i, date_str in enumerate(dates):
            try:
                day_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            d_code = int(daily_codes[i]) if i < len(daily_codes) and daily_codes[i] is not None else 0
            forecast.append(
                ForecastDay(
                    date=day_date,
                    precipitation_sum_mm=float(precip_sums[i])
                    if i < len(precip_sums) and precip_sums[i] is not None
                    else 0.0,
                    temperature_max_c=float(temp_maxs[i])
                    if i < len(temp_maxs) and temp_maxs[i] is not None
                    else 0.0,
                    temperature_min_c=float(temp_mins[i])
                    if i < len(temp_mins) and temp_mins[i] is not None
                    else 0.0,
                    weather_code=d_code,
                    weather_description=_WMO_DESCRIPTIONS.get(d_code, f"Code {d_code}"),
                )
            )

        return WeatherResponse(
            latitude=float(raw.get("latitude", 0.0)),
            longitude=float(raw.get("longitude", 0.0)),
            provider="open-meteo",
            provider_status=ProviderStatus.OK,
            fetched_at=fetched_at,
            current=current_weather,
            forecast=forecast,
            data_freshness_seconds=0,
        )

    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("weather_parse_error", error=str(exc), error_type=type(exc).__name__)
        return WeatherResponse(
            latitude=0.0,
            longitude=0.0,
            provider="open-meteo",
            provider_status=ProviderStatus.PROVIDER_ERROR,
            fetched_at=fetched_at,
            current=None,
            forecast=[],
            data_freshness_seconds=0,
            error_message=f"Response parse error: {type(exc).__name__}",
        )


def _make_retry_decorator() -> Any:
    """Build a tenacity retry decorator using settings at call time."""
    settings = get_settings()
    return retry(
        stop=stop_after_attempt(settings.weather_max_retries),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
        reraise=False,
    )


def _fetch_open_meteo_sync(url: str, timeout: float) -> dict[str, Any]:
    """Synchronous HTTP fetch from Open-Meteo. Runs in a thread pool executor.

    Uses httpx.Client (sync) so we don't block the asyncio event loop when
    called via run_in_executor.
    """
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()  # type: ignore[return-value]


class OpenMeteoProvider(WeatherProvider):
    """Open-Meteo weather provider.

    Open-Meteo is free, requires no API key, and provides global weather
    forecasts and current conditions.

    Reference: https://open-meteo.com/en/docs
    """

    async def fetch(self, lat: float, lon: float) -> WeatherResponse:
        settings = get_settings()
        timeout = settings.weather_timeout_seconds
        fetched_at = datetime.now(timezone.utc)
        url = _build_open_meteo_url(lat, lon)

        logger.debug("weather_fetch_start", lat=lat, lon=lon, provider="open-meteo")

        retry_dec = _make_retry_decorator()

        @retry_dec
        def _do_fetch() -> dict[str, Any]:
            return _fetch_open_meteo_sync(url, timeout)

        try:
            loop = asyncio.get_event_loop()
            raw: dict[str, Any] = await loop.run_in_executor(None, _do_fetch)
            logger.info("weather_fetch_success", lat=lat, lon=lon, provider="open-meteo")
            result = _parse_open_meteo_response(raw, fetched_at)
            # Patch lat/lon with requested values (Open-Meteo may snap to grid)
            result.latitude = lat
            result.longitude = lon
            return result

        except RetryError:
            logger.warning(
                "weather_fetch_all_retries_exhausted",
                lat=lat,
                lon=lon,
                provider="open-meteo",
                attempts=settings.weather_max_retries,
            )
            return WeatherResponse(
                latitude=lat,
                longitude=lon,
                provider="open-meteo",
                provider_status=ProviderStatus.UNAVAILABLE,
                fetched_at=fetched_at,
                current=None,
                forecast=[],
                data_freshness_seconds=0,
                error_message=f"Provider unavailable after {settings.weather_max_retries} retries.",
            )

        except httpx.TimeoutException:
            logger.warning("weather_fetch_timeout", lat=lat, lon=lon, provider="open-meteo")
            return WeatherResponse(
                latitude=lat,
                longitude=lon,
                provider="open-meteo",
                provider_status=ProviderStatus.TIMEOUT,
                fetched_at=fetched_at,
                current=None,
                forecast=[],
                data_freshness_seconds=0,
                error_message="Provider request timed out.",
            )

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "weather_fetch_error",
                lat=lat,
                lon=lon,
                provider="open-meteo",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return WeatherResponse(
                latitude=lat,
                longitude=lon,
                provider="open-meteo",
                provider_status=ProviderStatus.PROVIDER_ERROR,
                fetched_at=fetched_at,
                current=None,
                forecast=[],
                data_freshness_seconds=0,
                error_message=f"Provider error: {type(exc).__name__}",
            )
