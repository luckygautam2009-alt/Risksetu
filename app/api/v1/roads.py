"""
RISKSETU AI — OpenStreetMap Road Network Viewport Endpoint.

GET /api/v1/roads?min_lat={}&max_lat={}&min_lon={}&max_lon={}&limit={}

Authoritative endpoint serving OpenStreetMap transportation network graph
edges directly from PostGIS road_network_edges table.
"""
from __future__ import annotations

import json

import structlog
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.road import RoadNetworkEdge
from app.schemas.road_network import (
    RoadEdgeItem,
    RoadEdgeListData,
    RoadEdgeListResponse,
)

logger = structlog.get_logger("risksetu.roads.api")

router = APIRouter(prefix="/roads", tags=["roads"])


@router.get("", response_model=RoadEdgeListResponse)
def get_viewport_roads(
    min_lat: float = Query(..., ge=-90.0, le=90.0, description="South latitude boundary"),
    max_lat: float = Query(..., ge=-90.0, le=90.0, description="North latitude boundary"),
    min_lon: float = Query(..., ge=-180.0, le=180.0, description="West longitude boundary"),
    max_lon: float = Query(..., ge=-180.0, le=180.0, description="East longitude boundary"),
    limit: int = Query(150, ge=1, le=300, description="Maximum road edges to return"),
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
) -> RoadEdgeListResponse:
    """Query real OSM road network segments within map bounding box."""
    rid = getattr(request.state, "request_id", "") if request else ""

    envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
    spatial_filter = func.ST_Intersects(RoadNetworkEdge.geom, envelope)

    stmt = (
        select(
            RoadNetworkEdge.id,
            RoadNetworkEdge.osm_way_id,
            RoadNetworkEdge.highway_class,
            RoadNetworkEdge.name,
            RoadNetworkEdge.bridge,
            RoadNetworkEdge.tunnel,
            RoadNetworkEdge.length_m,
            func.ST_AsGeoJSON(RoadNetworkEdge.geom).label("geojson_geom"),
        )
        .where(spatial_filter)
        .limit(limit)
    )

    count_stmt = select(func.count()).select_from(RoadNetworkEdge).where(spatial_filter)
    total = db.scalar(count_stmt) or 0
    rows = db.execute(stmt).all()

    items: list[RoadEdgeItem] = []
    for r in rows:
        coords: list[list[float]] = []
        if r.geojson_geom:
            try:
                parsed = json.loads(r.geojson_geom)
                if parsed.get("type") == "LineString":
                    coords = parsed.get("coordinates", [])
            except Exception:
                coords = []

        items.append(
            RoadEdgeItem(
                id=str(r.id),
                osm_way_id=r.osm_way_id,
                highway_class=r.highway_class,
                name=r.name,
                bridge=r.bridge,
                tunnel=r.tunnel,
                length_m=r.length_m,
                coordinates=coords,
            )
        )

    return RoadEdgeListResponse(
        data=RoadEdgeListData(total_count=total, limit=limit, items=items),
        meta={"request_id": rid},
    )
