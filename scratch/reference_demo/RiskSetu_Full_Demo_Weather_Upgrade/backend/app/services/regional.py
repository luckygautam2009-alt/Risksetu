"""Regional rainfall screening.

This is intentionally a rainfall watch, not a hydrological forecast. Default
monitor points can be replaced with REGIONAL_MONITOR_POINTS_JSON in production.
"""
from __future__ import annotations
import asyncio
import json
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Any

from app import config
from app.integrations import openmeteo

DEFAULT_POINTS = [
    {"id":"tibet-yarlung","name":"Yarlung Tsangpo / Tibet screening point","country":"China","region":"Tibet","latitude":29.45,"longitude":94.75,"affected_regions":["Arunachal Pradesh","Assam","Brahmaputra corridor"]},
    {"id":"upper-si-ang","name":"Upper Siang screening point","country":"India","region":"Arunachal Pradesh","latitude":28.75,"longitude":94.98,"affected_regions":["Arunachal Pradesh","Assam"]},
    {"id":"bhutan-west","name":"Bhutan western catchment screening point","country":"Bhutan","region":"Western Bhutan","latitude":27.47,"longitude":89.64,"affected_regions":["Assam","West Bengal","Bhutan"]},
    {"id":"bhutan-east","name":"Bhutan eastern catchment screening point","country":"Bhutan","region":"Eastern Bhutan","latitude":27.25,"longitude":91.35,"affected_regions":["Assam","Arunachal Pradesh","Bhutan"]},
    {"id":"nepal-east","name":"Eastern Nepal screening point","country":"Nepal","region":"Koshi region","latitude":27.35,"longitude":87.25,"affected_regions":["Nepal","Bihar","Sikkim"]},
    {"id":"meghalaya","name":"Meghalaya rainfall screening point","country":"India","region":"Meghalaya","latitude":25.27,"longitude":91.73,"affected_regions":["Meghalaya","Assam","Bangladesh"]},
]
_cache: tuple[float, list[dict[str, Any]]] | None = None
CACHE_SECONDS = int(os.getenv("REGIONAL_CACHE_SECONDS", "1800"))


def points():
    raw = os.getenv("REGIONAL_MONITOR_POINTS_JSON", "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list) and parsed:
                return parsed
        except Exception:
            pass
    return DEFAULT_POINTS


def severity(r24: float | None, forecast: float | None) -> str | None:
    peak = max(r24 or 0, forecast or 0)
    if peak >= 180: return "EMERGENCY"
    if peak >= 100: return "WARNING"
    if peak >= 50: return "WATCH"
    return None


async def scan(force: bool = False):
    global _cache
    now = time.time()
    if _cache and not force and now - _cache[0] < CACHE_SECONDS:
        return _cache[1]

    async def one(point):
        try:
            w = await openmeteo.current(float(point["latitude"]), float(point["longitude"]))
            forecast = sum((x.get("precipitation_mm") or 0) for x in w.get("forecast_windows", [])[:3])
            sev = severity(w.get("rainfall_24h"), forecast)
            if not sev: return None
            return {
                "id": point.get("id") or point["name"], "hazard_type": "HEAVY_RAIN",
                "severity": sev, "title": f"Regional rainfall {sev.lower()}",
                "message": "Elevated rainfall is detected at a regional screening point. Possible downstream impact requires monitoring; this is not a river-flow forecast.",
                "latitude": point["latitude"], "longitude": point["longitude"],
                "region": point.get("region"), "country": point.get("country"),
                "affected_regions": point.get("affected_regions", []),
                "rainfall_24h_mm": w.get("rainfall_24h"), "forecast_rain_mm": round(forecast, 1),
                "confidence": "SCREENING", "verified": False,
                "observed_at": w.get("observation_time"),
                "expires_at": (datetime.now(timezone.utc)+timedelta(hours=6)).isoformat(),
                **config.provenance("Open-Meteo regional rainfall screening", w.get("data_mode", "LIVE")),
            }
        except Exception:
            return None

    rows = [x for x in await asyncio.gather(*(one(p) for p in points())) if x]
    _cache = (now, rows)
    return rows


def relevant(events, lat: float, lon: float):
    # Conservative regional screening for the NER + eastern Himalayan corridor.
    # This does not claim basin connectivity; affected_regions are operator-configured.
    if 20 <= lat <= 31.5 and 85 <= lon <= 98.5:
        return events
    return []
