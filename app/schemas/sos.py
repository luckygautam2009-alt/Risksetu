"""
Pydantic schemas for SOS emergency reporting, evidence linkage, and lifecycle tracking.
"""
from __future__ import annotations

import datetime
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.sos.constants import SOSSeverity


# ---------------------------------------------------------------------------
# SOS creation
# ---------------------------------------------------------------------------

class SOSCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    location_accuracy_meters: float | None = Field(default=None, ge=0.0, description="GPS accuracy in meters")
    severity: SOSSeverity = Field(default=SOSSeverity.MEDIUM)
    description: str | None = Field(default=None, max_length=2000)
    evidence_id: Any | None = Field(default=None, description="Optional verified photographic evidence ID")
    idempotency_key: str | None = Field(default=None, max_length=128, description="Optional client idempotency key")

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def _finite(cls, v: Any) -> float:
        if isinstance(v, (int, float)):
            if math.isnan(v) or math.isinf(v):
                raise ValueError("Coordinate must be a finite number.")
            return float(v)
        raise ValueError("Coordinate must be numeric.")


class SOSActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Risk context embedded in SOS response
# ---------------------------------------------------------------------------

class SOSRiskContext(BaseModel):
    risk_score: float | None = None
    risk_level: str | None = None
    risk_confidence: float | None = None
    weather_status: str | None = None
    live_risk_available: bool = False
    assessment_timestamp: datetime.datetime | None = None


# ---------------------------------------------------------------------------
# Evidence item embedded in SOS response
# ---------------------------------------------------------------------------

class SOSEvidenceItem(BaseModel):
    evidence_id: str
    content_type: str
    size_bytes: int
    sha256: str
    captured_at: datetime.datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    upload_status: str = "STORED"
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# SOS response payload
# ---------------------------------------------------------------------------

class SOSData(BaseModel):
    id: str
    latitude: float
    longitude: float
    location_accuracy_meters: float | None = None
    severity: str
    status: str
    description: str | None = None
    risk_context: SOSRiskContext
    risk_source: str | None = "LIVE_RISK_V1"
    evidence_count: int = 0
    created_by_verified_identity: bool = True
    idempotency_key: str | None = None
    linked_alert_id: str | None = None
    reported_by: str | None = None
    acknowledged_by: str | None = None
    acknowledged_at: datetime.datetime | None = None
    resolved_by: str | None = None
    resolved_at: datetime.datetime | None = None
    cancelled_at: datetime.datetime | None = None
    evidence_items: list[SOSEvidenceItem] = Field(default_factory=list)
    shelter_recommendation: dict[str, Any] | None = None
    request_id: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class SOSResponse(BaseModel):
    data: SOSData
    meta: dict[str, Any] = Field(default_factory=dict)


class SOSListItem(BaseModel):
    id: str
    latitude: float
    longitude: float
    location_accuracy_meters: float | None = None
    severity: str
    status: str
    risk_level: str | None = None
    risk_score: float | None = None
    evidence_count: int = 0
    description: str | None = None
    created_at: datetime.datetime


class SOSListData(BaseModel):
    total_count: int
    limit: int
    offset: int
    items: list[SOSListItem]


class SOSListResponse(BaseModel):
    data: SOSListData
    meta: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# SOS Audit History
# ---------------------------------------------------------------------------

class SOSAuditItem(BaseModel):
    id: int
    sos_id: str
    action: str
    previous_status: str | None = None
    new_status: str | None = None
    reason: str | None = None
    metadata_json: dict[str, Any] | None = None
    user_id: str | None = None
    created_at: datetime.datetime


class SOSAuditListResponse(BaseModel):
    data: list[SOSAuditItem]
    meta: dict[str, Any] = Field(default_factory=dict)
