"""
Pydantic schemas for Audience Alert Subscriptions and Emergency Dispatches.
"""
from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AlertSubscriptionItem(BaseModel):
    id: str
    user_id: str
    notification_type: str
    enabled: bool
    geofence_radius_km: float | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class AlertSubscriptionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notification_type: str = Field(..., description="Notification category name")
    enabled: bool = Field(..., description="Whether subscription is enabled")
    geofence_radius_km: float | None = Field(None, ge=0.5, le=500.0, description="Optional geofencing filter radius")


class AlertSubscriptionListResponse(BaseModel):
    data: list[AlertSubscriptionItem]
    meta: dict[str, Any] = Field(default_factory=dict)


class EmergencyDispatchData(BaseModel):
    id: str
    alert_id: str
    sos_id: str | None = None
    channel: str
    recipient_count: int
    status: str
    provider_response: dict[str, Any] | None = None
    created_at: datetime.datetime
