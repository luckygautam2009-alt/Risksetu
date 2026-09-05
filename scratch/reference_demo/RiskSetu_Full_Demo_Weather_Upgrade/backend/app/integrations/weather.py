"""Weather provider chain: Open-Meteo first, IndianAPI fallback."""
from fastapi import HTTPException
from app.integrations import openmeteo, indianapi, imerg

async def current(lat: float, lon: float):
    errors = []
    try:
        result = await openmeteo.current(lat, lon)
        satellite = await imerg.accumulation(lat, lon, "1day")
        if satellite:
            result = {**result, "satellite_rainfall_24h": satellite.get("precipitation_mm"), "satellite_source": satellite.get("source"), "satellite_latency_note": satellite.get("latency_note")}
        return result
    except HTTPException as exc:
        errors.append(f"Open-Meteo: {exc.detail}")
    try:
        result = await indianapi.current(lat, lon)
        return {**result, "fallback_provider": True}
    except HTTPException as exc:
        errors.append(f"IndianAPI: {exc.detail}")
    raise HTTPException(503, "Weather unavailable. " + " | ".join(errors))
