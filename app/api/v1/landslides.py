"""
RISKSETU AI — Historical GSI Landslides Viewport & Inventory Endpoint.

GET /api/v1/landslides?min_lat={}&max_lat={}&min_lon={}&max_lon={}&limit={}&offset={}

Authoritative endpoint serving verified Geological Survey of India (GSI)
historical landslide catalog records directly from PostgreSQL/PostGIS.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.landslide import HistoricalLandslide
from app.schemas.landslide import (
    LandslideItem,
    LandslideListData,
    LandslideListResponse,
)

logger = structlog.get_logger("risksetu.landslides.api")

router = APIRouter(prefix="/landslides", tags=["landslides"])


@router.get("", response_model=LandslideListResponse)
def get_historical_landslides(
    min_lat: float | None = Query(None, ge=-90.0, le=90.0, description="South latitude boundary"),
    max_lat: float | None = Query(None, ge=-90.0, le=90.0, description="North latitude boundary"),
    min_lon: float | None = Query(None, ge=-180.0, le=180.0, description="West longitude boundary"),
    max_lon: float | None = Query(None, ge=-180.0, le=180.0, description="East longitude boundary"),
    limit: int = Query(150, ge=1, le=500, description="Maximum number of points to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
) -> LandslideListResponse:
    """Query verified GSI historical landslide records within a map bounding box."""
    rid = getattr(request.state, "request_id", "") if request else ""

    stmt = select(HistoricalLandslide)
    count_stmt = select(func.count()).select_from(HistoricalLandslide)

    has_bbox = (
        min_lat is not None
        and max_lat is not None
        and min_lon is not None
        and max_lon is not None
    )

    if has_bbox:
        envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
        spatial_filter = func.ST_Intersects(HistoricalLandslide.geom, envelope)
        stmt = stmt.where(spatial_filter)
        count_stmt = count_stmt.where(spatial_filter)

    total = db.scalar(count_stmt) or 0
    records = db.execute(stmt.offset(offset).limit(limit)).scalars().all()

    items = [
        LandslideItem(
            id=str(r.id),
            gsi_slide_no=r.gsi_slide_no,
            slide_name=r.slide_name,
            state=r.state,
            district=r.district,
            location_description=r.location_description,
            road_corridor=r.road_corridor,
            latitude=r.latitude,
            longitude=r.longitude,
            movement_type=r.movement_type,
            material=r.material,
            event_date=r.event_date.isoformat() if r.event_date else None,
            source_dataset=r.source_dataset or "GSI_NLSM_PDF",
        )
        for r in records
    ]

    return LandslideListResponse(
        data=LandslideListData(total_count=total, limit=limit, offset=offset, items=items),
        meta={"request_id": rid},
    )
