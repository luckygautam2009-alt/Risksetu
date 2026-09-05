"""
RISKSETU AI — Regional & Upstream Rainfall Screening Watch endpoints.

Endpoints:
  GET /api/v1/regional-watch          — List active screening watches.
  GET /api/v1/regional-watch/impact   — Filter screening watches relevant to coordinates.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from app.services.regional_watch import filter_by_impact, scan_regional_hazards

router = APIRouter(prefix="/regional-watch", tags=["regional-watch"])


class RegionalHazardWatch(BaseModel):
    id: str
    name: str
    hazard_type: str
    severity: str
    title: str
    message: str
    latitude: float
    longitude: float
    region: str
    country: str
    affected_regions: list[str] = Field(default_factory=list)
    forecast_rain_mm: float
    confidence: str
    verified: bool
    source: str
    data_mode: str
    updated_at: str


class RegionalWatchListResponse(BaseModel):
    data: list[RegionalHazardWatch]
    meta: dict[str, Any] = Field(default_factory=dict)


@router.get("", response_model=RegionalWatchListResponse, summary="List active regional rainfall screening watches")
async def list_regional_watches(
    request: Request,
    force: bool = Query(default=False, description="Force refresh cache"),
) -> RegionalWatchListResponse:
    """Retrieve all regional / upstream screening watches across monitored corridors.

    **Note:** This is an antecedent rainfall screening watch, not a river-flow or flood forecast.
    """
    rid = getattr(request.state, "request_id", "")
    events = await scan_regional_hazards(force=force)
    return RegionalWatchListResponse(
        data=[RegionalHazardWatch(**e) for e in events],
        meta={"request_id": rid, "total_watches": len(events)},
    )


@router.get("/impact", response_model=RegionalWatchListResponse, summary="Get screening watches relevant to coordinates")
async def get_regional_impact(
    request: Request,
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude"),
) -> RegionalWatchListResponse:
    """Retrieve regional screening watches relevant to the requested coordinates."""
    rid = getattr(request.state, "request_id", "")
    all_events = await scan_regional_hazards()
    relevant_events = filter_by_impact(all_events, lat=lat, lon=lon)
    return RegionalWatchListResponse(
        data=[RegionalHazardWatch(**e) for e in relevant_events],
        meta={"request_id": rid, "total_watches": len(relevant_events)},
    )
