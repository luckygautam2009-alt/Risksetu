"""Open-Meteo adapter for current weather, rainfall accumulation and forecast.
No API key is required for the public forecast endpoint. Missing values remain None.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import HTTPException

from app import config

BASE_URL = os.getenv("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1/forecast").rstrip("/")
CACHE_TTL_SECONDS = int(os.getenv("WEATHER_CACHE_SECONDS", "900"))
STALE_CACHE_SECONDS = int(os.getenv("WEATHER_STALE_CACHE_SECONDS", "3600"))
_cache: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}


def _num(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        v = float(value)
        return v if v == v and abs(v) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _sum(values: list[Any]) -> float | None:
    nums = [_num(v) for v in values]
    good = [v for v in nums if v is not None]
    return round(sum(good), 1) if good else None


def _forecast_windows(times: list[str], rain: list[Any], probability: list[Any], current_index: int) -> list[dict[str, Any]]:
    windows = []
    for start_offset, hours in ((1, 3), (4, 3), (7, 6), (13, 12)):
        start = current_index + start_offset
        end = min(len(times), start + hours)
        if start >= len(times):
            continue
        total = _sum(rain[start:end])
        probs = [_num(x) for x in probability[start:end]]
        probs = [x for x in probs if x is not None]
        max_prob = round(max(probs), 0) if probs else None
        if total is None and max_prob is None:
            continue
        level = "LOW"
        if (total or 0) >= 70:
            level = "CRITICAL"
        elif (total or 0) >= 35:
            level = "HIGH"
        elif (total or 0) >= 12:
            level = "MODERATE"
        windows.append({
            "start": times[start], "end": times[end - 1], "hours": end - start,
            "precipitation_mm": total, "precipitation_probability_pct": max_prob,
            "rain_level": level,
        })
    return windows


async def current(lat: float, lon: float) -> dict[str, Any]:
    key = (round(lat, 3), round(lon, 3))
    now_ts = time.time()
    if key in _cache and now_ts - _cache[key][0] < CACHE_TTL_SECONDS:
        return {**_cache[key][1], "data_mode": "CACHED"}

    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": "UTC",
        "past_days": 3,
        "forecast_days": 3,
        "current": "temperature_2m,relative_humidity_2m,precipitation,rain,weather_code",
        "hourly": "precipitation,precipitation_probability,soil_moisture_0_to_1cm,soil_moisture_1_to_3cm,soil_moisture_3_to_9cm,soil_moisture_9_to_27cm",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(BASE_URL, params=params, headers={"Accept": "application/json"})
            response.raise_for_status()
        data = response.json()
        hourly = data.get("hourly") or {}
        times: list[str] = hourly.get("time") or []
        rain: list[Any] = hourly.get("precipitation") or []
        probs: list[Any] = hourly.get("precipitation_probability") or []
        soil0: list[Any] = hourly.get("soil_moisture_0_to_1cm") or []
        soil1: list[Any] = hourly.get("soil_moisture_1_to_3cm") or []
        soil3: list[Any] = hourly.get("soil_moisture_3_to_9cm") or []
        soil9: list[Any] = hourly.get("soil_moisture_9_to_27cm") or []
        current = data.get("current") or {}
        current_time = current.get("time")
        idx = len(times) - 1
        if current_time and times:
            idx = min(range(len(times)), key=lambda i: abs(datetime.fromisoformat(times[i]).replace(tzinfo=timezone.utc).timestamp() - datetime.fromisoformat(current_time).replace(tzinfo=timezone.utc).timestamp()))
        past24 = rain[max(0, idx - 23): idx + 1] if rain else []
        past72 = rain[max(0, idx - 71): idx + 1] if rain else []
        soil_values=[]
        for series in (soil0,soil1,soil3,soil9):
            value=_num(series[idx]) if idx < len(series) else None
            if value is not None: soil_values.append(value)
        sm = (sum(soil_values)/len(soil_values)) if soil_values else None
        surface_sm = _num(soil0[idx]) if idx < len(soil0) else None
        result = {
            "latitude": float(data.get("latitude", lat)),
            "longitude": float(data.get("longitude", lon)),
            "weather_location": "GPS coordinates",
            "rainfall_1h": _num(current.get("precipitation")),
            "rainfall_24h": _sum(past24),
            "rainfall_72h": _sum(past72),
            "humidity": _num(current.get("relative_humidity_2m")),
            "temperature": _num(current.get("temperature_2m")),
            "soil_moisture_pct": round(sm * 100, 1) if sm is not None else None,
            "surface_soil_moisture_pct": round(surface_sm * 100, 1) if surface_sm is not None else None,
            "soil_moisture_source": "Open-Meteo numerical weather model (0-27 cm proxy; not a field sensor)",
            "weather_code": current.get("weather_code"),
            "rainfall_trend": "forecast available",
            "forecast_windows": _forecast_windows(times, rain, probs, idx),
            "observation_time": current_time or datetime.now(timezone.utc).isoformat(),
            **config.provenance("Open-Meteo Forecast", "LIVE"),
        }
        _cache[key] = (now_ts, result)
        return result
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        if key in _cache and now_ts - _cache[key][0] < STALE_CACHE_SECONDS:
            return {**_cache[key][1], "data_mode": "CACHED", "warning": "Open-Meteo unavailable; last successful weather shown"}
        raise HTTPException(503, "Open-Meteo weather is unavailable") from exc
