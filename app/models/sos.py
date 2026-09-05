"""
SOS emergency report models.

SOSReport  — the core emergency request entity.
SOSAudit   — immutable lifecycle audit trail (mirrors AlertAudit pattern).
"""
from __future__ import annotations

import datetime
from typing import Any
import uuid

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SOSReport(Base):
    """Emergency SOS report submitted by a citizen or operator."""

    __tablename__ = "sos_reports"
    __table_args__ = (
        CheckConstraint(
            "latitude >= -90.0 AND latitude <= 90.0",
            name="chk_sos_latitude",
        ),
        CheckConstraint(
            "longitude >= -180.0 AND longitude <= 180.0",
            name="chk_sos_longitude",
        ),
        Index("ix_sos_reports_status", "status"),
        Index("ix_sos_reports_severity", "severity"),
        Index("ix_sos_reports_created_at", "created_at"),
        Index("ix_sos_reports_reported_by", "reported_by"),
        Index("ix_sos_reports_idempotency_key", "idempotency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Location — stored as both flat floats (for indexing/filters) and PostGIS point
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom: Mapped[Any] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=True),
        nullable=True,
    )

    # Severity and description
    severity: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="MEDIUM",
        server_default="MEDIUM",
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="ACTIVE",
        server_default="ACTIVE",
        index=True,
    )

    # Risk context snapshot at SOS creation time
    live_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    live_risk_level: Mapped[str | None] = mapped_column(String(30), nullable=True)
    live_risk_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_context: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Alert linkage — populated if an alert was generated from this SOS
    linked_alert_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Operator tracking
    reported_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    acknowledged_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    cancelled_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Location accuracy & evidence telemetry
    location_accuracy_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        default="LIVE_RISK_V1",
        server_default="LIVE_RISK_V1",
    )
    evidence_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    created_by_verified_identity: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )

    # Shelter recommendation snapshot (populated asynchronously)
    shelter_recommendation: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
    )

    # Request/correlation tracing
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

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

    audits: Mapped[list["SOSAudit"]] = relationship(
        "SOSAudit",
        back_populates="sos_report",
        cascade="all, delete-orphan",
    )


class SOSAudit(Base):
    """Immutable audit trail for SOS lifecycle state transitions."""

    __tablename__ = "sos_audits"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True,
    )
    sos_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sos_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    previous_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    sos_report: Mapped[SOSReport] = relationship(
        "SOSReport", back_populates="audits",
    )
