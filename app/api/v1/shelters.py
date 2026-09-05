"""
RISKSETU AI — Shelter discovery API.

GET /api/v1/shelters/nearby?lat={lat}&lon={lon}&radius_m={radius}

Returns nearby verified shelters using PostGIS spatial queries.

DATA STATUS:
  No verified shelter dataset is currently loaded.
  The response includes data_status = "unavailable" until a real dataset
  is ingested from NDMA / State DM Portal or equivalent authoritative source.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.shelter import NearbyShelterdData, NearbyShelterdResponse
from app.services.auth.dependencies import get_current_user
from app.services.sos.constants import (
    SHELTER_DEFAULT_RADIUS_M,
    SHELTER_MAX_RADIUS_M,
    SHELTER_MIN_RADIUS_M,
)
from app.services.sos.shelter_service import _LIMITATIONS, get_nearby_shelters

logger = structlog.get_logger("risksetu.shelters.api")
router = APIRouter(prefix="/shelters", tags=["shelters"])


@router.get("/nearby", response_model=NearbyShelterdResponse)
async def get_nearby_shelters_endpoint(
    request: Request,
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude"),
    radius_m: float = Query(
        default=SHELTER_DEFAULT_RADIUS_M,
        ge=SHELTER_MIN_RADIUS_M,
        le=SHELTER_MAX_RADIUS_M,
        description="Search radius in metres",
    ),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NearbyShelterdResponse:
    """Discover verified shelters near the specified coordinates.

    Returns `data_status = "unavailable"` if no verified shelter dataset
    is loaded. No fabricated records are ever returned.
    """
    rid = getattr(request.state, "request_id", "")

    data_status, note, shelter_items = get_nearby_shelters(
        db=db, lat=lat, lon=lon, radius_m=radius_m, limit=limit,
    )

    limitations = list(_LIMITATIONS) if data_status == "unavailable" else [
        "Shelter capacity/accessibility data only available where verified records exist.",
        "Road connectivity notes indicate OSM network availability, not guaranteed passable routes.",
    ]

    return NearbyShelterdResponse(
        data=NearbyShelterdData(
            data_status=data_status,
            data_source_note=note,
            query_lat=lat,
            query_lon=lon,
            radius_m=radius_m,
            total_found=len(shelter_items),
            shelters=shelter_items,
            limitations=limitations,
        ),
        meta={"request_id": rid},
    )
