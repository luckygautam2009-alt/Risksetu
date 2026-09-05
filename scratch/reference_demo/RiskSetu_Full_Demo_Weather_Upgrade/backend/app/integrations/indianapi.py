"""IndianAPI weather adapter.

Uses IndianAPI's documented weather API and keeps the API key server-side.
The adapter deliberately leaves rainfall accumulations as null when the
provider does not return measured rainfall instead of treating missing data as
zero rain.
"""
import math
import os
import time
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException

from app import config
from app.services.geo import nearby
from app.store import repo

BASE_URL = os.getenv("INDIANAPI_WEATHER_BASE_URL", "https://weather.indianapi.in").rstrip("/")
CACHE_TTL_SECONDS = int(os.getenv("WEATHER_CACHE_SECONDS", "900"))
STALE_CACHE_SECONDS = int(os.getenv("WEATHER_STALE_CACHE_SECONDS", "3600"))

# The UI currently focuses on North-East India. IndianAPI's /india/weather
# endpoint accepts city names with fuzzy matching, so coordinates are mapped to
# the nearest supported regional city without needing a paid geocoding API.
NER_CITIES = {
    "Shillong": (25.5788, 91.8933),
    "Sohra": (25.2700, 91.7300),
    "Guwahati": (26.1445, 91.7362),
    "Gangtok": (27.3314, 88.6138),
    "Aizawl": (23.7271, 92.7176),
    "Itanagar": (27.0844, 93.6053),
    "Kohima": (25.6751, 94.1086),
    "Imphal": (24.8170, 93.9368),
    "Agartala": (23.8315, 91.2868),
}

cache: dict[tuple[float, float], tuple[float, dict]] = {}


def _haversine_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = math.radians(b_lat - a_lat)
    dl = math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _nearest_city(lat: float, lon: float) -> str:
    return min(NER_CITIES, key=lambda name: _haversine_km(lat, lon, *NER_CITIES[name]))


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, str):
        cleaned = value.strip().lower().replace("mm", "").replace("°c", "").replace("c", "")
        try:
            parsed = float(cleaned)
            return parsed if math.isfinite(parsed) else None
        except ValueError:
            return None
    return None


def _rainfall_mm(value):
    """Best-effort normalization of IndianAPI's current.rainfall field."""
    direct = _number(value)
    if direct is not None:
        return max(0.0, direct)
    if isinstance(value, dict):
        for key in ("value", "amount", "mm", "rainfall", "24h", "last_24_hours"):
            parsed = _number(value.get(key))
            if parsed is not None:
                return max(0.0, parsed)
    return None


def _temperature(current: dict):
    temp = current.get("temperature")
    direct = _number(temp)
    if direct is not None:
        return direct
    if isinstance(temp, dict):
        max_v = _number((temp.get("max") or {}).get("value") if isinstance(temp.get("max"), dict) else temp.get("max"))
        min_v = _number((temp.get("min") or {}).get("value") if isinstance(temp.get("min"), dict) else temp.get("min"))
        vals = [v for v in (max_v, min_v) if v is not None]
        if vals:
            return round(sum(vals) / len(vals), 1)
    return None


def _humidity(current: dict):
    value = current.get("humidity")
    direct = _number(value)
    if direct is not None:
        return min(100.0, max(0.0, direct))
    if isinstance(value, dict):
        vals = [_number(value.get(k)) for k in ("morning", "evening")]
        vals = [v for v in vals if v is not None]
        if vals:
            return round(min(100.0, max(0.0, sum(vals) / len(vals))), 1)
    return None


def _mock_weather(lat: float, lon: float):
    zones = nearby(repo.all("risk_zones"), {"latitude": lat, "longitude": lon}, 100000)
    if not zones:
        raise HTTPException(404, "No demo weather coverage for this location")
    f = zones[0]["features"]
    return {
        "latitude": lat,
        "longitude": lon,
        "weather_location": zones[0].get("name", "Demo area"),
        "rainfall_1h": round(f["rainfall_24h_mm"] / 18, 1),
        "rainfall_24h": f["rainfall_24h_mm"],
        "rainfall_72h": f["rainfall_72h_mm"],
        "humidity": 88,
        "temperature": 19,
        "rainfall_trend": "rising",
        "observation_time": datetime.now(timezone.utc).isoformat(),
        **config.provenance("Synthetic weather scenario", "MOCK"),
    }


async def current(lat: float, lon: float):
    key = (round(lat, 3), round(lon, 3))
    now = time.time()
    if key in cache and now - cache[key][0] < CACHE_TTL_SECONDS:
        return {**cache[key][1], "data_mode": "CACHED"}

    api_key = os.getenv("INDIANAPI_KEY", "").strip()
    if not api_key:
        if config.DATA_MODE == "mock":
            return _mock_weather(lat, lon)
        raise HTTPException(503, "IndianAPI weather key is not configured")

    city = _nearest_city(lat, lon)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{BASE_URL}/india/weather",
                params={"city": city},
                headers={"x-api-key": api_key, "Accept": "application/json"},
            )
            r.raise_for_status()
        payload = r.json()
        current_data = (payload.get("weather") or {}).get("current") or {}
        rain24 = _rainfall_mm(current_data.get("rainfall"))
        temp = _temperature(current_data)
        humidity = _humidity(current_data)

        result = {
            "latitude": lat,
            "longitude": lon,
            "weather_location": payload.get("city") or city,
            # IndianAPI's documented India response may return rainfall=null and
            # does not document 1h/72h accumulations. Missing means unknown, not 0.
            "rainfall_1h": None,
            "rainfall_24h": rain24,
            "rainfall_72h": None,
            "humidity": humidity,
            "temperature": temp,
            "rainfall_trend": "unknown",
            "observation_time": datetime.now(timezone.utc).isoformat(),
            **config.provenance("IndianAPI Weather", "LIVE"),
        }
        cache[key] = (now, result)
        # The DB schema may require numeric rainfall columns in some deployments;
        # only persist a normalized observation when all accumulations exist.
        if all(result[k] is not None for k in ("rainfall_1h", "rainfall_24h", "rainfall_72h", "humidity", "temperature")):
            repo.insert("weather_observations", {k: v for k, v in result.items() if k not in {"rainfall_trend", "weather_location"}})
        return result
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        if key in cache and now - cache[key][0] < STALE_CACHE_SECONDS:
            return {**cache[key][1], "data_mode": "CACHED", "warning": "IndianAPI unavailable; last successful weather shown"}
        if config.DATA_MODE == "mock":
            fallback = _mock_weather(lat, lon)
            return {**fallback, "warning": "IndianAPI unavailable; demo weather fallback shown"}
        raise HTTPException(503, "IndianAPI weather unavailable; no fallback in live mode")
