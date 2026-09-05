"""
Shelter model for disaster-management facilities.

IMPORTANT — DATA HONESTY:
  No verified shelter dataset is currently loaded in this deployment.
  The table schema is ready; queries will return data_status = "unavailable"
  until a verified dataset is ingested.

  The `data_source` and `last_verified_at` fields are mandatory on any
  ingested record so provenance is always traceable.
"""
from __future__ import annotations

import datetime
from typing import Any
import uuid

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Shelter(Base):
    """Disaster-management shelter / evacuation centre record."""

    __tablename__ = "shelters"
    __table_args__ = (
        Index("ix_shelters_is_active", "is_active"),
        Index("ix_shelters_facility_type", "facility_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    facility_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True,
        comment="e.g. SCHOOL, COMMUNITY_HALL, RELIEF_CAMP, GOVT_BUILDING",
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom: Mapped[Any] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=True),
        nullable=False,
    )

    # Capacity — only stored if verified; null means unknown
    capacity_persons: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Accessibility — only stored if verified
    is_accessible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    accessibility_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Administrative information
    district: Mapped[str | None] = mapped_column(String(200), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Data provenance — mandatory for any real record
    data_source: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        comment="Authoritative source of this shelter record (e.g. 'NDMA 2024', 'State DM Portal')",
    )
    last_verified_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true",
    )

    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

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
