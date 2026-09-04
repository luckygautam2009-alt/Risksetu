"""
Historical landslide inventory models.
"""
from __future__ import annotations

import datetime
from typing import Any
import uuid

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, DateTime, Float, Index, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HistoricalLandslide(Base):
    """Historical Landslide event cataloged by Geological Survey of India (GSI)."""

    __tablename__ = "historical_landslides"
    __table_args__ = (
        CheckConstraint("latitude >= -90.0 AND latitude <= 90.0", name="chk_landslide_latitude"),
        CheckConstraint("longitude >= -180.0 AND longitude <= 180.0", name="chk_landslide_longitude"),
        Index("ix_historical_landslides_state_district", "state", "district"),
        Index("ix_historical_landslides_movement_type", "movement_type"),
        Index("ix_historical_landslides_event_date", "event_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    gsi_slide_no: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    state: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    district: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    slide_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    road_corridor: Mapped[str | None] = mapped_column(String(255), nullable=True)

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom: Mapped[Any] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=True),
        nullable=False,
    )

    material: Mapped[str | None] = mapped_column(String(100), nullable=True)
    movement_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    history_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_date: Mapped[datetime.date | None] = mapped_column(nullable=True)

    source_dataset: Mapped[str] = mapped_column(String(100), default="GSI_NLSM_PDF", nullable=False)
    source_record_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

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
