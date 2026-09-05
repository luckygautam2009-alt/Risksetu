"""
RISKSETU AI — Live Risk (LIVE_RISK_V1) Pydantic schemas.

These schemas define the complete response envelope for GET /api/v1/live-risk.
They deliberately mirror the structure documented in the task specification
while following the project's existing schema conventions.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-schemas — one per intelligence layer
# ---------------------------------------------------------------------------


class LiveRiskLocation(BaseModel):
    """The queried geographic coordinate."""
    latitude: float
    longitude: float


class LiveRiskSummary(BaseModel):
    """Final operational risk verdict after combining all available inputs."""
    score: float = Field(ge=0.0, le=100.0, description="Composite risk score [0-100].")
    level: str = Field(description="LOW / MODERATE / HIGH / CRITICAL")
    confidence: float = Field(ge=0.0, le=100.0, description="Evidence coverage confidence [0-100].")


class HistoricalRiskLayer(BaseModel):
    """Output from the certified Phase 2A deterministic risk engine."""
    status: str = Field(description="available | unavailable | error")
    score: float | None = Field(default=None, description="Historical risk score [0-100].")
    level: str | None = Field(default=None, description="Historical risk level.")
    confidence: float | None = Field(default=None, description="Historical confidence [0-100].")
    calculation_version: str | None = Field(default=None)
    factors: list[dict[str, Any]] = Field(default_factory=list)
    weight_redistributed: bool = Field(default=False)
    summary: str | None = Field(default=None)
    limitations: list[str] = Field(default_factory=list)


class WeatherLayer(BaseModel):
    """Live weather data from Open-Meteo (or unavailability state)."""
    status: str = Field(description="available | unavailable | timeout | provider_error | cached")
    provider: str = Field(default="open-meteo")
    precipitation_mm: float | None = Field(default=None)
    temperature_c: float | None = Field(default=None)
    humidity_pct: float | None = Field(default=None)
    wind_speed_kmh: float | None = Field(default=None)
    weather_code: int | None = Field(default=None)
    description: str | None = Field(default=None)
    observation_time: datetime | None = Field(
        default=None,
        description="Timestamp of the weather observation (from provider).",
    )
    fetched_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when this response was retrieved.",
    )
    freshness_seconds: int | None = Field(
        default=None,
        description="Age of weather data in seconds; >0 means served from cache.",
    )
    forecast_3day_precip_mm: list[float] = Field(
        default_factory=list,
        description="Precipitation sums for the next 3 forecast days (mm).",
    )
    error_message: str | None = Field(default=None)


class MLLayer(BaseModel):
    """ML susceptibility layer — unavailable until a scientifically validated model is present."""
    status: str = Field(description="unavailable | available")
    susceptibility_score: float | None = Field(default=None)
    model_version: str | None = Field(default=None)
    reason: str | None = Field(
        default=None,
        description="Why ML is unavailable; populated when status='unavailable'.",
    )


class TerrainLayer(BaseModel):
    """DEM-derived terrain layer — unavailable until validated DEM integration exists."""
    status: str = Field(description="unavailable | available")
    elevation_m: float | None = Field(default=None)
    slope_degrees: float | None = Field(default=None)
    aspect: str | None = Field(default=None)
    reason: str | None = Field(
        default=None,
        description="Why terrain is unavailable; populated when status='unavailable'.",
    )


class ContributingFactor(BaseModel):
    """A single observed, explainable factor that drove the final risk assessment."""
    factor: str = Field(description="Machine-readable factor ID.")
    description: str = Field(description="Human-readable explanation.")
    value: Any = Field(default=None, description="Observed value, if applicable.")
    source: str = Field(description="Which layer this came from: historical | weather | ml | terrain")


class RecommendedAction(BaseModel):
    """A deterministic operational recommendation driven by risk level and factors."""
    action_id: str
    description: str
    priority: str = Field(description="immediate | high | moderate | low")


class DataFreshness(BaseModel):
    """Timestamps and ages for each data source actually used."""
    assessment_generated_at: datetime
    historical_data_version: str | None = Field(default=None)
    weather_observation_time: datetime | None = Field(default=None)
    weather_fetched_at: datetime | None = Field(default=None)
    weather_freshness_seconds: int | None = Field(default=None)
    ml_artifact_version: str | None = Field(default=None)
    terrain_dataset_version: str | None = Field(default=None)


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------


class LiveRiskData(BaseModel):
    """LIVE_RISK_V1 full assessment payload."""
    location: LiveRiskLocation
    timestamp: datetime = Field(description="UTC time this assessment was generated.")
    risk: LiveRiskSummary
    historical: HistoricalRiskLayer
    weather: WeatherLayer
    ml: MLLayer
    terrain: TerrainLayer
    contributing_factors: list[ContributingFactor] = Field(default_factory=list)
    unavailable_inputs: list[str] = Field(
        default_factory=list,
        description="Inputs that were requested but unavailable; listed explicitly.",
    )
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    data_freshness: DataFreshness
    engine_version: str = Field(default="LIVE_RISK_V1")


class LiveRiskResponse(BaseModel):
    """Standard API success envelope for the live risk endpoint."""
    data: LiveRiskData
    meta: dict[str, Any] = Field(default_factory=dict)
