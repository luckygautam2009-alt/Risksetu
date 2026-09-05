"""Free/open routing adapter backed by OSRM + OpenStreetMap road data.

No Google Maps key is required. Set OSRM_BASE_URL to your own OSRM instance for
production scale; the default public endpoint is suitable for prototype use.
"""
import os

import httpx
from fastapi import HTTPException

from app import config
from app.services.geo import distance

OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org").rstrip("/")


async def alternatives(origin, destination):
    length = distance(origin, destination)
    if length < 100 or length > 200000:
        raise HTTPException(422, "Choose locations between 100 m and 200 km apart for this prototype")

    coordinates = (
        f"{origin['longitude']},{origin['latitude']};"
        f"{destination['longitude']},{destination['latitude']}"
    )
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                f"{OSRM_BASE_URL}/route/v1/driving/{coordinates}",
                params={
                    "alternatives": "3",
                    "steps": "false",
                    "geometries": "geojson",
                    "overview": "full",
                },
                headers={"User-Agent": "RiskSetu/1.0 (routing prototype)"},
            )
            r.raise_for_status()
        payload = r.json()
        if payload.get("code") != "Ok":
            raise ValueError(payload.get("message") or payload.get("code") or "OSRM route error")
        routes = payload.get("routes") or []
        if not routes:
            raise ValueError("No route returned")
        return [
            {
                "id": f"route-{i+1}",
                "name": "Primary road route" if i == 0 else f"Alternative {i}",
                "coordinates": route["geometry"]["coordinates"],
                "distance_m": round(float(route["distance"])),
                "duration_seconds": round(float(route["duration"])),
                **config.provenance("OSRM / OpenStreetMap routing", "LIVE"),
            }
            for i, route in enumerate(routes)
        ]
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        if config.DATA_MODE == "mock":
            # Offline/test fallback: still no Google dependency. Geometry is clearly
            # labelled synthetic and must not be used as road navigation.
            a = [origin["longitude"], origin["latitude"]]
            b = [destination["longitude"], destination["latitude"]]
            fallback = []
            for i, offset in enumerate([0, .018, -.024]):
                midpoint = [(a[0] + b[0]) / 2 + offset, (a[1] + b[1]) / 2 - offset]
                coords = [a, midpoint, b]
                meters = sum(
                    distance({"latitude": x[1], "longitude": x[0]}, {"latitude": y[1], "longitude": y[0]})
                    for x, y in zip(coords, coords[1:])
                )
                fallback.append({
                    "id": f"route-{i+1}",
                    "name": f"Fallback alternative {chr(65+i)}",
                    "coordinates": coords,
                    "distance_m": round(meters),
                    "duration_seconds": round(meters / 8),
                    **config.provenance("Synthetic route fallback — OSRM unavailable", "MOCK"),
                })
            return fallback
        raise HTTPException(503, "OpenStreetMap routing provider unavailable or returned invalid data")
