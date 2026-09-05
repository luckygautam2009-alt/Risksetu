"""
RISKSETU AI — Regional & Upstream Rainfall Screening Watch.

Monitors regional / upstream catchment screening points across the Himalayan
and North-East corridor to detect antecedent rainfall anomalies.

CRITICAL SCIENTIFIC RULES:
  - This is intentionally a REGIONAL RAINFALL WATCH, not a deterministic river-flow
    or hydrological flood prediction.
  - Data is sourced from Open-Meteo point forecasts.
  - Absence of watch does not imply low risk at local unmonitored streams.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import structlog

from app.services.weather.service import WeatherService

logger = structlog.get_logger("risksetu.regional_watch")

DEFAULT_SCREENING_POINTS = [
    {
        "id": "pt-chamoli-upper",
        "name": "Alaknanda / Upper Chamoli Catchment",
        "country": "India",
        "region": "Uttarakhand",
        "latitude": 30.35,
        "longitude": 79.62,
        "affected_regions": ["Chamoli", "Joshimath", "Alaknanda Basin", "NH-58"],
    },
    {
        "id": "pt-rudraprayag-basin",
        "name": "Mandakini / Rudraprayag Upper Basin",
        "country": "India",
        "region": "Uttarakhand",
        "latitude": 30.48,
        "longitude": 79.15,
        "affected_regions": ["Rudraprayag", "Kedarnath Corridor", "Mandakini Basin"],
    },
    {
        "id": "pt-meghalaya-south",
        "name": "Sohra / East Khasi Hills Catchment",
        "country": "India",
        "region": "Meghalaya",
        "latitude": 25.27,
        "longitude": 91.73,
        "affected_regions": ["East Khasi Hills", "Shillong Corridor", "Southern Slopes"],
    },
    {
        "id": "pt-upper-siang",
        "name": "Upper Siang Screening Point",
        "country": "India",
        "region": "Arunachal Pradesh",
        "latitude": 28.75,
        "longitude": 94.98,
        "affected_regions": ["Arunachal Pradesh", "Upper Assam", "Siang Basin"],
    },
    {
        "id": "pt-sikkim-teesta",
        "name": "Teesta River Upper Catchment",
        "country": "India",
        "region": "Sikkim",
        "latitude": 27.53,
        "longitude": 88.51,
        "affected_regions": ["North Sikkim", "Gangtok", "Teesta Basin"],
    },
]

_cache: tuple[float, list[dict[str, Any]]] | None = None
_CACHE_TTL_SECONDS = 1800  # 30 minutes
_weather_service = WeatherService()


def _classify_severity(rain_24h: float, forecast_rain: float) -> str | None:
    peak = max(rain_24h, forecast_rain)
    if peak >= 120.0:
        return "EMERGENCY"
    if peak >= 65.0:
        return "WARNING"
    if peak >= 35.0:
        return "WATCH"
    return None


async def scan_regional_hazards(force: bool = False) -> list[dict[str, Any]]:
    global _cache
    now = time.time()
    if _cache and not force and (now - _cache[0]) < _CACHE_TTL_SECONDS:
        return _cache[1]

    events: list[dict[str, Any]] = []
    for pt in DEFAULT_SCREENING_POINTS:
        lat = float(pt["latitude"])
        lon = float(pt["longitude"])
        try:
            w = await _weather_service.get_weather(lat, lon)
            current_precip = w.current.precipitation_mm if w.current else 0.0
            fc_precip = w.forecast[0].precipitation_sum_mm if w.forecast else 0.0

            sev = _classify_severity(current_precip * 6.0, fc_precip)  # Estimate 24h trend
            if not sev:
                continue

            events.append({
                "id": pt["id"],
                "name": pt["name"],
                "hazard_type": "HEAVY_RAINFALL_WATCH",
                "severity": sev,
                "title": f"Regional Rainfall {sev.capitalize()}: {pt['name']}",
                "message": (
                    f"Elevated antecedent / forecast rainfall ({round(fc_precip, 1)} mm) detected at screening point. "
                    "Possible downstream corridor impacts warrant heightened monitoring. This is not a river-flow prediction."
                ),
                "latitude": lat,
                "longitude": lon,
                "region": pt["region"],
                "country": pt["country"],
                "affected_regions": pt["affected_regions"],
                "forecast_rain_mm": round(fc_precip, 1),
                "confidence": "SCREENING",
                "verified": False,
                "source": "Open-Meteo Regional Screening Point",
                "data_mode": "LIVE",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as exc:  # noqa: BLE001
            logger.debug("regional_scan_point_failed", point=pt["id"], error=str(exc))
            continue

    _cache = (now, events)
    return events


def filter_by_impact(events: list[dict[str, Any]], lat: float, lon: float, radius_deg: float = 3.0) -> list[dict[str, Any]]:
    """Return screening watches that geographically overlap with the corridor sector."""
    return [
        e for e in events
        if abs(e["latitude"] - lat) <= radius_deg and abs(e["longitude"] - lon) <= radius_deg
    ]
