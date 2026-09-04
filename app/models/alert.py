"""
Alert and AlertAudit domain models for operational decision-support layer.
"""
from __future__ import annotations

import datetime
from typing import Any, TYPE_CHECKING
import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    pass


class Alert(Base):
    """Operational alert representing elevated risk, priority, connectivity disruption, or ground intelligence."""

    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("latitude >= -90.0 AND latitude <= 90.0", name="chk_alert_latitude"),
        CheckConstraint("longitude >= -180.0 AND longitude <= 180.0", name="chk_alert_longitude"),
        Index("ix_alerts_status_severity", "status", "severity"),
        Index("ix_alerts_type_status", "alert_type", "status"),
        Index("ix_alerts_created_at_desc", "created_at"),
        # Partial unique index: ensure one ACTIVE alert per fingerprint
        Index(
            "uix_alerts_active_fingerprint",
            "fingerprint",
            unique=True,
            postgresql_where="status = 'ACTIVE'",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    alert_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ACTIVE",
        server_default="ACTIVE",
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    # Pre-computed metrics from Phase 2A/2B/2C/3
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    isolation_severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    priority_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ground_intelligence_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Operational & deduplication metadata
    fingerprint: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    source_reference: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    recommended_actions: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    explanation: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    data_freshness: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Lifecycle tracking
    acknowledged_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    calculation_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="v1.0.0",
        server_default="v1.0.0",
    )
    audit_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

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

    audits: Mapped[list["AlertAudit"]] = relationship(
        "AlertAudit",
        back_populates="alert",
        cascade="all, delete-orphan",
    )


class AlertAudit(Base):
    """Immutable audit trail for alert lifecycle state transitions."""

    __tablename__ = "alert_audits"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    previous_state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    new_state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    alert: Mapped[Alert] = relationship(
        "Alert",
        back_populates="audits",
    )
