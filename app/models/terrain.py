"""
Terrain and DEM source architecture models.
"""
from __future__ import annotations

import datetime
from typing import Any
import uuid

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Index,
    JSON,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TerrainSource(Base):
    """Digital Elevation Model (DEM) source raster tile registry."""

    __tablename__ = "terrain_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tile_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    source_agency: Mapped[str] = mapped_column(String(100), default="ISRO_NRSC", nullable=False)
    resolution_m: Mapped[float] = mapped_column(Float, default=30.0, nullable=False)
    crs: Mapped[str] = mapped_column(String(50), default="EPSG:4326", nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tile_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    geom_bbox: Mapped[Any | None] = mapped_column(
        Geometry("POLYGON", srid=4326, spatial_index=True),
        nullable=True,
    )
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


class TerrainCell(Base):
    """Derived terrain morphometry cell (Elevation, Slope, Aspect, Curvature, TWI)."""

    __tablename__ = "terrain_cells"
    __table_args__ = (
        Index("ix_terrain_cells_elevation", "elevation_m"),
        Index("ix_terrain_cells_slope", "slope_deg"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    slope_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    aspect_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    curvature: Mapped[float | None] = mapped_column(Float, nullable=True)
    twi: Mapped[float | None] = mapped_column(Float, nullable=True)

    geom: Mapped[Any] = mapped_column(
        Geometry("POLYGON", srid=4326, spatial_index=True),
        nullable=False,
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
