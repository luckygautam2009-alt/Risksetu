"""
Audience Alert Subscriptions and Emergency Dispatch Tracking Models.

AlertSubscription  — User preferences for real-time and push notification categories.
EmergencyDispatch  — Delivery state record for emergency alert channels (WebSocket, SMS, Push, Siren).
"""
from __future__ import annotations

import datetime
from typing import Any
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AlertSubscription(Base):
    """User audience subscription for emergency categories and geographic geofencing."""

    __tablename__ = "alert_subscriptions"
    __table_args__ = (
        Index("uix_alert_subscriptions_user_type", "user_id", "notification_type", unique=True),
        Index("ix_alert_subscriptions_user_id", "user_id"),
        Index("ix_alert_subscriptions_type", "notification_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    notification_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="EMERGENCY_ALERTS",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    geofence_radius_km: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[Any] = relationship("User", backref="alert_subscriptions")


class EmergencyDispatch(Base):
    """Auditable delivery state record for operational notifications and alerts."""

    __tablename__ = "emergency_dispatches"
    __table_args__ = (
        Index("ix_emergency_dispatches_alert_id", "alert_id"),
        Index("ix_emergency_dispatches_sos_id", "sos_id"),
        Index("ix_emergency_dispatches_status", "status"),
        Index("ix_emergency_dispatches_channel", "channel"),
        Index("ix_emergency_dispatches_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
    )
    sos_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sos_reports.id", ondelete="CASCADE"),
        nullable=True,
    )
    channel: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    recipient_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="QUEUED",
        server_default="QUEUED",
    )
    provider_response: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
