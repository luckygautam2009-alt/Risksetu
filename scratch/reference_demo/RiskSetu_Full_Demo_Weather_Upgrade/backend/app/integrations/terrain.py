"""Free terrain adapter using Open-Meteo's Copernicus GLO-90 elevation API.

Slope is estimated from a small elevation stencil around the requested point.
It is a screening-grade terrain feature, not a geotechnical site survey.
No API key is required for normal non-commercial use.
"""
from __future__ import annotations

import math
import os
import time
from typing import Any

import httpx

ELEVATION_URL = os.getenv("OPEN_METEO_ELEVATION_URL", "https://api.open-meteo.com/v1/elevation")
CACHE_SECONDS = int(os.getenv("TERRAIN_CACHE_SECONDS", "86400"))
_cache: dict[tuple[float, float], tuple[float, dict[str, Any] | None]] = {}


def _offset(lat: float, lon: float, north_m: float, east_m: float) -> tuple[float, float]:
    dlat = north_m / 111_320.0
    cos_lat = max(0.15, math.cos(math.radians(lat)))
    dlon = east_m / (111_320.0 * cos_lat)
    return lat + dlat, lon + dlon


async def terrain(lat: float, lon: float) -> dict[str, Any] | None:
    key = (round(lat, 4), round(lon, 4))
    now = time.time()
    if key in _cache and now - _cache[key][0] < CACHE_SECONDS:
        cached = _cache[key][1]
        return None if cached is None else {**cached, "data_mode": "CACHED"}

    # Four cardinal samples ~270 m from the centre plus centre point.
    spacing_m = 270.0
    pts = [
        (lat, lon),
        _offset(lat, lon, spacing_m, 0),
        _offset(lat, lon, -spacing_m, 0),
        _offset(lat, lon, 0, spacing_m),
        _offset(lat, lon, 0, -spacing_m),
    ]
    params = {
        "latitude": ",".join(f"{p[0]:.6f}" for p in pts),
        "longitude": ",".join(f"{p[1]:.6f}" for p in pts),
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(ELEVATION_URL, params=params, headers={"Accept": "application/json"})
            r.raise_for_status()
        values = (r.json() or {}).get("elevation") or []
        if len(values) < 5 or any(v is None for v in values[:5]):
            _cache[key] = (now, None)
            return None
        c, n, s, e, w = [float(v) for v in values[:5]]
        dz_dy = (n - s) / (2 * spacing_m)
        dz_dx = (e - w) / (2 * spacing_m)
        gradient = math.sqrt(dz_dx * dz_dx + dz_dy * dz_dy)
        slope_deg = round(math.degrees(math.atan(gradient)), 1)
        relief_m = round(max(n, s, e, w, c) - min(n, s, e, w, c), 1)
        result = {
            "latitude": lat,
            "longitude": lon,
            "elevation_m": round(c, 1),
            "slope_deg": slope_deg,
            "local_relief_m": relief_m,
            "sample_spacing_m": spacing_m,
            "source": "Open-Meteo Elevation · Copernicus DEM GLO-90",
            "data_mode": "LIVE",
            "method_note": "Slope is estimated from a 5-point ~270 m elevation stencil; screening use only.",
        }
        _cache[key] = (now, result)
        return result
    except Exception:
        if key in _cache:
            cached = _cache[key][1]
            return None if cached is None else {**cached, "data_mode": "STALE"}
        return None
