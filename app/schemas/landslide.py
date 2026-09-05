"""
Pydantic v2 schemas for Geological Survey of India (GSI) historical landslide records.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LandslideItem(BaseModel):
    """Single GSI historical landslide catalog record."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    gsi_slide_no: str
    slide_name: str | None = None
    state: str
    district: str
    location_description: str | None = None
    road_corridor: str | None = None
    latitude: float
    longitude: float
    movement_type: str | None = None
    material: str | None = None
    event_date: str | None = None
    source_dataset: str = "GSI_NLSM_PDF"


class LandslideListData(BaseModel):
    """Paginated collection of historical landslide catalog records."""

    total_count: int = Field(..., description="Total records matching spatial filter")
    limit: int
    offset: int
    items: list[LandslideItem]


class LandslideListResponse(BaseModel):
    """API response envelope for historical landslide records."""

    data: LandslideListData
    meta: dict[str, Any] = Field(default_factory=dict)
