"""
Pydantic v2 validation schemas for Phase 4 Alert Generation & Decision Support.
"""
from __future__ import annotations

import datetime
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.alerts.constants import AlertSeverity, AlertStatus, AlertType


class AlertGenerateRequest(BaseModel):
    """Payload to trigger deterministic alert generation from multi-phase intelligence."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS-84 latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS-84 longitude")

    # Optional pre-computed Phase 2A/2B/2C/3 inputs (supports 0.0-1.0)
    risk_score: float | None = Field(None, ge=0.0, le=1.0, description="Phase 2A physical risk score")
    risk_level: str | None = Field(None, max_length=50, description="Phase 2A risk category")
    risk_confidence: float | None = Field(None, ge=0.0, le=1.0, description="Phase 2A risk confidence")
    isolation_severity: str | None = Field(None, max_length=50, description="Phase 2B network isolation severity")
    priority_score: float | None = Field(None, ge=0.0, le=100.0, description="Phase 2C operational priority score")
    priority_level: str | None = Field(None, max_length=50, description="Phase 2C priority category")
    ground_intelligence_summary: dict[str, Any] | None = Field(None, description="Phase 3 ground observation summary")
    source_reference: dict[str, Any] | None = Field(None, description="Tracking IDs from prior computation runs")
    data_freshness: dict[str, Any] | None = Field(None, description="Input data timestamp and staleness markers")

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def validate_finite_floats(cls, v: Any) -> float:
        if isinstance(v, (int, float)):
            if math.isnan(v) or math.isinf(v):
                raise ValueError("Coordinate must be a finite number")
            return float(v)
        raise ValueError("Coordinate must be a numeric float")


class AlertActionRequest(BaseModel):
    """Payload for operational alert state transition requests."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(None, max_length=500, description="Reason for status modification")


class AlertData(BaseModel):
    """Detailed operational alert payload."""

    id: str
    alert_type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    title: str
    message: str
    latitude: float
    longitude: float
    risk_score: float | None = None
    risk_level: str | None = None
    risk_confidence: float | None = None
    isolation_severity: str | None = None
    priority_score: float | None = None
    priority_level: str | None = None
    ground_intelligence_summary: dict[str, Any] | None = None
    fingerprint: str
    source_reference: dict[str, Any] | None = None
    recommended_actions: list[dict[str, Any]] | None = None
    explanation: dict[str, Any] | None = None
    data_freshness: dict[str, Any] | None = None
    acknowledged_at: datetime.datetime | None = None
    acknowledged_by: str | None = None
    resolved_at: datetime.datetime | None = None
    resolved_by: str | None = None
    calculation_version: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


class AlertResponse(BaseModel):
    """Standard envelope for a single alert response."""

    data: AlertData
    meta: dict[str, Any] = Field(default_factory=dict)


class AlertListItem(BaseModel):
    """Concise representation of an alert for paginated dashboards."""

    id: str
    alert_type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    title: str
    latitude: float
    longitude: float
    risk_score: float | None = None
    priority_score: float | None = None
    isolation_severity: str | None = None
    created_at: datetime.datetime


class AlertListData(BaseModel):
    """Paginated collection of operational alerts."""

    total_count: int
    limit: int
    offset: int
    alerts: list[AlertListItem]


class AlertListResponse(BaseModel):
    """Standard envelope for paginated alerts query."""

    data: AlertListData
    meta: dict[str, Any] = Field(default_factory=dict)
