"""
OpenStreetMap transportation network and routable road graph models.
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
    Integer,
    JSON,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RoadNetworkNode(Base):
    """OSM Intersection and Endpoint graph nodes."""

    __tablename__ = "road_network_nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    osm_node_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    geom: Mapped[Any] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=True),
        nullable=False,
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


class RoadNetworkEdge(Base):
    """Routable road segments and corridors derived from OSM Ways."""

    __tablename__ = "road_network_edges"
    __table_args__ = (
        Index("ix_road_edges_from_to", "from_node_id", "to_node_id"),
        Index("ix_road_edges_highway_class", "highway_class"),
        Index("ix_road_edges_osm_way_id", "osm_way_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    osm_way_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    from_node_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    to_node_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    highway_class: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oneway: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    maxspeed: Mapped[int | None] = mapped_column(Integer, nullable=True)

    bridge: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tunnel: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    layer: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    surface: Mapped[str | None] = mapped_column(String(50), nullable=True)
    access: Mapped[str | None] = mapped_column(String(50), nullable=True)

    length_m: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    geom: Mapped[Any] = mapped_column(
        Geometry("LINESTRING", srid=4326, spatial_index=True),
        nullable=False,
    )

    source_snapshot: Mapped[str] = mapped_column(String(100), default="OSM_NORTHERN_ZONE_260903", nullable=False)
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
