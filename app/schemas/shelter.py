"""
Pydantic schemas for shelter discovery and recommendation.
"""
from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Individual shelter record
# ---------------------------------------------------------------------------

class ShelterItem(BaseModel):
    id: str
    name: str
    facility_type: str | None = None
    latitude: float
    longitude: float
    distance_m: float = Field(description="Distance from the query point in metres.")
    capacity_persons: int | None = Field(
        default=None,
        description="Verified capacity; null if not in dataset.",
    )
    is_accessible: bool | None = Field(
        default=None,
        description="Verified accessibility; null if not in dataset.",
    )
    accessibility_notes: str | None = None
    district: str | None = None
    state: str | None = None
    data_source: str = Field(description="Authoritative source of this record.")
    last_verified_at: datetime.datetime | None = None
    suitability_score: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Deterministic suitability score [0-100]. Null if insufficient data.",
    )
    suitability_factors: dict[str, Any] = Field(default_factory=dict)
    connectivity_note: str = Field(
        default="route_assessment_unavailable",
        description=(
            "connectivity_available | connectivity_uncertain | "
            "route_assessment_unavailable"
        ),
    )


# ---------------------------------------------------------------------------
# Nearby shelter list
# ---------------------------------------------------------------------------

class NearbyShelterdData(BaseModel):
    data_status: str = Field(
        description=(
            "available — verified shelters found. "
            "unavailable — no verified shelter dataset loaded. "
            "empty — dataset exists but no shelters in radius."
        )
    )
    data_source_note: str
    query_lat: float
    query_lon: float
    radius_m: float
    total_found: int
    shelters: list[ShelterItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class NearbyShelterdResponse(BaseModel):
    data: NearbyShelterdData
    meta: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Shelter recommendation (embedded in SOS recommendation endpoint)
# ---------------------------------------------------------------------------

class ShelterRecommendationItem(BaseModel):
    rank: int
    shelter: ShelterItem
    recommendation_reason: str


class SOSRecommendationData(BaseModel):
    sos_id: str
    query_lat: float
    query_lon: float
    risk_score: float | None = None
    risk_level: str | None = None
    risk_confidence: float | None = None
    shelter_data_status: str
    shelter_data_note: str
    recommended_shelters: list[ShelterRecommendationItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    engine_version: str = "SOS_SHELTER_V1"


class SOSRecommendationResponse(BaseModel):
    data: SOSRecommendationData
    meta: dict[str, Any] = Field(default_factory=dict)
