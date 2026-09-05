"""
Incident evidence models for verified photographic evidence uploads.
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IncidentEvidence(Base):
    """Authoritative metadata record for verified incident and SOS photographic evidence."""

    __tablename__ = "incident_evidence"
    __table_args__ = (
        Index("ix_incident_evidence_owner_user_id", "owner_user_id"),
        Index("ix_incident_evidence_incident_id", "incident_id"),
        Index("ix_incident_evidence_sos_id", "sos_id"),
        Index("ix_incident_evidence_sha256", "sha256"),
        Index("ix_incident_evidence_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ground_reports.id", ondelete="SET NULL"),
        nullable=True,
    )
    sos_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sos_reports.id", ondelete="SET NULL"),
        nullable=True,
    )
    storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    content_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    captured_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    upload_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="STORED",
        server_default="STORED",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
