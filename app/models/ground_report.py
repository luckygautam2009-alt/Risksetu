"""
Ground intelligence reporting and audit domain models.
"""
from __future__ import annotations

import datetime
from typing import Any, TYPE_CHECKING
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
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class GroundReport(Base):
    """Field observation submitted by citizens or officials."""

    __tablename__ = "ground_reports"
    __table_args__ = (
        CheckConstraint("latitude >= -90.0 AND latitude <= 90.0", name="chk_ground_report_latitude"),
        CheckConstraint("longitude >= -180.0 AND longitude <= 180.0", name="chk_ground_report_longitude"),
        CheckConstraint("trust_score >= 0.0 AND trust_score <= 100.0", name="chk_ground_report_trust_score"),
        Index("ix_ground_reports_type_status", "report_type", "status"),
        Index("ix_ground_reports_risk_eligible", "risk_influence_eligible", "status"),
        # Partial unique index: idempotency key is unique per user, NULLs excluded
        Index(
            "uix_ground_reports_user_idempotency",
            "user_id",
            "idempotency_key",
            unique=True,
            postgresql_where="idempotency_key IS NOT NULL",
        ),
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
        index=True,
    )
    report_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom: Mapped[Any] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    observed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="SUBMITTED",
        server_default="SUBMITTED",
        index=True,
    )

    # Trust Scoring Breakdown Metrics [0.0 - 100.0]
    trust_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0.0",
    )
    trust_class: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="LOW",
        server_default="LOW",
        index=True,
    )
    geo_plausibility_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0.0",
    )
    temporal_freshness_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0.0",
    )
    user_reliability_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0.0",
    )
    corroboration_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0.0",
    )

    # Deduplication
    is_duplicate: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ground_reports.id", ondelete="SET NULL"),
        nullable=True,
    )
    duplicate_group_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    # Automated Risk Gate
    risk_influence_eligible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )

    # Idempotency key for exactly-once submission semantics (DB-level fallback when Redis unavailable)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    source_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
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

    user: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="ground_reports",
    )
    audits: Mapped[list["GroundReportAudit"]] = relationship(
        "GroundReportAudit",
        back_populates="report",
        cascade="all, delete-orphan",
    )


class GroundReportAudit(Base):
    """Immutable audit trail for ground report lifecycle and trust evaluations."""

    __tablename__ = "ground_report_audits"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ground_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
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

    report: Mapped[GroundReport] = relationship(
        "GroundReport",
        back_populates="audits",
    )
