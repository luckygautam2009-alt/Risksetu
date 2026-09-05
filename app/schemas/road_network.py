"""
Pydantic v2 schemas for OpenStreetMap (OSM) road network query responses.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RoadEdgeItem(BaseModel):
    """Single routable road segment from PostGIS road network."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    osm_way_id: int
    highway_class: str
    name: str | None = None
    bridge: bool = False
    tunnel: bool = False
    length_m: float = 0.0
    coordinates: list[list[float]] = Field(
        default_factory=list,
        description="LineString coordinates as [[lon, lat], [lon, lat], ...]",
    )


class RoadEdgeListData(BaseModel):
    """Collection of road network segments within queried viewport."""

    total_count: int
    limit: int
    items: list[RoadEdgeItem]


class RoadEdgeListResponse(BaseModel):
    """API response envelope for road network queries."""

    data: RoadEdgeListData
    meta: dict[str, Any] = Field(default_factory=dict)
