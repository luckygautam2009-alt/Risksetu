"""
Pydantic v2 validation schemas for Ground Intelligence and Trust-Weighted Reporting.
"""
from __future__ import annotations

import datetime
from enum import Enum
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReportType(str, Enum):
    """Controlled hazard and disturbance observation types."""

    LANDSLIDE = "LANDSLIDE"
    CRACK = "CRACK"
    ROCKFALL = "ROCKFALL"
    DEBRIS = "DEBRIS"
    ROAD_BLOCKAGE = "ROAD_BLOCKAGE"
    DRAINAGE_BLOCKAGE = "DRAINAGE_BLOCKAGE"
    SLOPE_MOVEMENT = "SLOPE_MOVEMENT"
    OTHER = "OTHER"


class ReportStatus(str, Enum):
    """Lifecycle status of a ground observation."""

    SUBMITTED = "SUBMITTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"


class TrustClass(str, Enum):
    """Deterministic trust category tier."""

    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


EMAIL_PATTERN = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"


class UserRegisterRequest(BaseModel):
    """Payload to register a new user account."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., pattern=EMAIL_PATTERN, description="User email address")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=150)
    role: str = Field("citizen", pattern=r"^(citizen|official|admin)$")


class UserLoginRequest(BaseModel):
    """Payload to authenticate and obtain an access token."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., pattern=EMAIL_PATTERN, description="User email address")
    password: str = Field(..., max_length=128)


class TokenResponse(BaseModel):
    """Standard token response envelope."""

    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str


# --- Ground Report Schemas ---


class GroundReportCreateRequest(BaseModel):
    """User submission payload for field observations."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS84 latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 longitude")
    report_type: ReportType = Field(..., description="Hazard observation classification")
    description: str = Field(..., min_length=10, max_length=2000, description="Descriptive text of observed hazard")
    observed_at: datetime.datetime = Field(..., description="Timestamp when observation was made")
    source_metadata: dict[str, Any] | None = Field(None, description="Optional telemetry or device provenance")

    @field_validator("latitude", "longitude")
    @classmethod
    def validate_finite_coordinates(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Coordinates must be finite real numbers.")
        return v

    @field_validator("description")
    @classmethod
    def validate_non_empty_description(cls, v: str) -> str:
        clean = v.strip()
        if len(clean) < 10:
            raise ValueError("Description must contain at least 10 non-whitespace characters.")
        return clean

    @field_validator("observed_at")
    @classmethod
    def validate_observation_time(cls, v: datetime.datetime) -> datetime.datetime:
        now = datetime.datetime.now(datetime.timezone.utc)
        target = v if v.tzinfo else v.replace(tzinfo=datetime.timezone.utc)

        # Allow 5-minute clock drift into future
        if target > now + datetime.timedelta(minutes=5):
            raise ValueError("Observation timestamp cannot be in the future.")

        # Reject observations older than 365 days
        if target < now - datetime.timedelta(days=365):
            raise ValueError("Observation timestamp is too old (> 365 days).")

        return target


class TrustComponents(BaseModel):
    """Quantitative evaluation breakdown across the 4 trust dimensions."""

    geo_plausibility: float = Field(..., ge=0.0, le=100.0)
    temporal_freshness: float = Field(..., ge=0.0, le=100.0)
    user_reliability: float = Field(..., ge=0.0, le=100.0)
    corroboration: float = Field(..., ge=0.0, le=100.0)


class TrustBreakdown(BaseModel):
    """Complete trust evaluation results and component weights."""

    trust_score: float = Field(..., ge=0.0, le=100.0)
    trust_class: TrustClass
    components: TrustComponents
    weights: dict[str, float]
    calculation_version: str


class GroundReportData(BaseModel):
    """Complete representation of a ground report with intelligence metrics."""

    report_id: str
    user_id: str
    report_type: ReportType
    description: str
    latitude: float
    longitude: float
    observed_at: datetime.datetime
    status: ReportStatus
    trust: TrustBreakdown
    is_duplicate: bool
    duplicate_of_id: str | None = None
    duplicate_group_id: str | None = None
    risk_influence_eligible: bool
    explanation: list[str]
    limitations: list[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime


class GroundReportResponse(BaseModel):
    """Standard envelope for a single ground report response."""

    data: GroundReportData
    meta: dict[str, Any] = Field(default_factory=dict)


class GroundReportListItem(BaseModel):
    """Concise representation of a ground report for paginated lists."""

    report_id: str
    user_id: str
    report_type: ReportType
    latitude: float
    longitude: float
    observed_at: datetime.datetime
    status: ReportStatus
    trust_score: float
    trust_class: TrustClass
    is_duplicate: bool
    risk_influence_eligible: bool
    created_at: datetime.datetime


class GroundReportListData(BaseModel):
    """Paginated collection of ground reports."""

    total_count: int
    limit: int
    offset: int
    reports: list[GroundReportListItem]


class GroundReportListResponse(BaseModel):
    """Standard envelope for paginated ground report lists."""

    data: GroundReportListData
    meta: dict[str, Any] = Field(default_factory=dict)


class GroundReportStatusUpdateRequest(BaseModel):
    """Payload for officials/admins to moderate a report."""

    model_config = ConfigDict(extra="forbid")

    status: ReportStatus
    reason: str | None = Field(None, max_length=500)


class TrustRecalculateResponse(BaseModel):
    """Response envelope for trust recalculation."""

    data: GroundReportData
    meta: dict[str, Any] = Field(default_factory=dict)
