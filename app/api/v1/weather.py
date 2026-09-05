"""
RISKSETU AI — Live weather API endpoint.

GET /api/v1/weather/current?lat={lat}&lon={lon}

Returns real-time weather and short-range forecast from Open-Meteo.
This endpoint is strictly separate from the IMD historical climatology
used by the deterministic risk engine — it does NOT modify risk scores.

Design:
  - Input validated: lat in [-90, 90], lon in [-180, 180].
  - Cache checked before provider fetch.
  - Provider failures return explicit unavailable/error status — no
    fabricated data is ever returned.
  - Response includes data_freshness_seconds so the frontend can display
    "Updated X minutes ago."
"""
from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Query, Request

from app.core.errors import ValidationAppError
from app.services.weather.service import WeatherService

logger = structlog.get_logger("risksetu.weather.api")

router = APIRouter(prefix="/weather", tags=["weather"])

# Module-level service instance (provider created once; safe because
# OpenMeteoProvider is stateless).
_weather_service = WeatherService()


def _validate_coordinates(lat: float, lon: float) -> None:
    """Raise ValidationAppError if lat/lon are outside valid ranges."""
    errors: list[dict[str, Any]] = []
    if not (-90.0 <= lat <= 90.0):
        errors.append({"field": "lat", "message": f"Latitude must be in [-90, 90]; got {lat}"})
    if not (-180.0 <= lon <= 180.0):
        errors.append({"field": "lon", "message": f"Longitude must be in [-180, 180]; got {lon}"})
    if errors:
        raise ValidationAppError(
            "Invalid coordinates for weather request.",
            details=errors,
        )


@router.get("/current")
async def get_current_weather(
    request: Request,
    lat: float = Query(..., description="Latitude in decimal degrees [-90, 90]"),
    lon: float = Query(..., description="Longitude in decimal degrees [-180, 180]"),
) -> dict[str, Any]:
    """Retrieve real-time weather conditions and short-range forecast.

    Data is sourced from Open-Meteo (no API key required).
    Responses are cached for up to 5 minutes per coordinate.

    When the provider is unavailable, the response will include
    `provider_status: "unavailable"` or `"provider_error"` and
    `error_message` will explain why. `current` will be null.

    **This endpoint does not affect risk scores or the deterministic engine.**
    """
    _validate_coordinates(lat, lon)

    req_id = getattr(request.state, "request_id", "")
    logger.info("weather_request", lat=lat, lon=lon, request_id=req_id)

    weather = await _weather_service.get_weather(lat, lon)

    return {
        "data": weather.to_api_dict(),
        "meta": {"request_id": req_id},
    }
