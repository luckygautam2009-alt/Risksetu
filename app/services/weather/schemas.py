"""
RISKSETU AI — Weather service Pydantic schemas.

These schemas are internal to the weather service and also used as the
API response model for the /weather/current endpoint.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProviderStatus(str, Enum):
    """Explicit state of the weather data provider for this response."""
    OK = "ok"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"
    CACHED = "cached"


class CurrentWeather(BaseModel):
    """Observed/current weather conditions at the point of interest."""

    timestamp: datetime = Field(description="Observation timestamp (UTC)")
    temperature_c: float = Field(description="Air temperature at 2 m (°C)")
    relative_humidity_pct: float = Field(description="Relative humidity at 2 m (%)")
    precipitation_mm: float = Field(description="Precipitation in the last hour (mm)")
    wind_speed_kmh: float = Field(description="Wind speed at 10 m (km/h)")
    weather_code: int = Field(description="WMO weather interpretation code")
    weather_description: str = Field(description="Human-readable weather description")


class ForecastDay(BaseModel):
    """Single-day weather forecast."""

    date: datetime = Field(description="Forecast date (UTC midnight)")
    precipitation_sum_mm: float = Field(description="Total precipitation for the day (mm)")
    temperature_max_c: float = Field(description="Maximum temperature (°C)")
    temperature_min_c: float = Field(description="Minimum temperature (°C)")
    weather_code: int = Field(description="WMO weather interpretation code")
    weather_description: str = Field(description="Human-readable weather description")


class WeatherResponse(BaseModel):
    """Full weather response including current observation and short-range forecast.

    When provider_status != 'ok', current and forecast may be None/empty.
    NEVER fabricate data — unavailability is always represented explicitly.
    """

    latitude: float = Field(description="Requested latitude")
    longitude: float = Field(description="Requested longitude")
    provider: str = Field(description="Data provider identifier (e.g. 'open-meteo')")
    provider_status: ProviderStatus = Field(description="Provider availability status")
    fetched_at: datetime = Field(description="UTC timestamp when this response was created")
    current: CurrentWeather | None = Field(
        default=None,
        description="Current weather observation; null when provider is unavailable",
    )
    forecast: list[ForecastDay] = Field(
        default_factory=list,
        description="Short-range forecast (up to 3 days); empty when provider is unavailable",
    )
    data_freshness_seconds: int = Field(
        default=0,
        description="Age of this data in seconds (0 = just fetched; >0 = from cache)",
    )
    error_message: str | None = Field(
        default=None,
        description="Human-readable error description when provider is unavailable",
    )

    model_config = {"arbitrary_types_allowed": True}

    def to_api_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict suitable for the API response envelope."""
        return self.model_dump(mode="json")
