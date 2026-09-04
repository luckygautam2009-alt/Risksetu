"""
Meteorological rainfall observation and climatology models.
"""
from __future__ import annotations

import datetime
from typing import Any
import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RainfallSubdivision(Base):
    """India Meteorological Department (IMD) 36 Meteorological Subdivisions."""

    __tablename__ = "rainfall_subdivisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    subdivision_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), default="IMD", nullable=False)

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

    observations: Mapped[list[RainfallObservation]] = relationship(
        "RainfallObservation",
        back_populates="subdivision",
        cascade="all, delete-orphan",
    )
    climatology: Mapped[list[RainfallClimatology]] = relationship(
        "RainfallClimatology",
        back_populates="subdivision",
        cascade="all, delete-orphan",
    )


class RainfallObservation(Base):
    """Canonical long-form monthly rainfall observations."""

    __tablename__ = "rainfall_observations"
    __table_args__ = (
        UniqueConstraint("subdivision_id", "year", "month", name="uq_subdiv_year_month"),
        CheckConstraint("month >= 1 AND month <= 12", name="chk_rainfall_month"),
        CheckConstraint("rainfall_mm >= 0.0 OR rainfall_mm IS NULL", name="chk_rainfall_positive"),
        Index("ix_rainfall_obs_subdiv_year", "subdivision_id", "year"),
        Index("ix_rainfall_obs_year_month", "year", "month"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    subdivision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rainfall_subdivisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 = Jan, 12 = Dec
    rainfall_mm: Mapped[float | None] = mapped_column(Float, nullable=True)

    source_dataset: Mapped[str] = mapped_column(String(100), default="IMD_SUBDIVISION_CSV", nullable=False)
    source_record_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    subdivision: Mapped[RainfallSubdivision] = relationship(
        "RainfallSubdivision",
        back_populates="observations",
    )


class RainfallClimatology(Base):
    """Derived historical climatology baseline per subdivision and month (1901-2017)."""

    __tablename__ = "rainfall_climatology"
    __table_args__ = (
        UniqueConstraint("subdivision_id", "month", "calculation_version", name="uq_climatology_subdiv_month_ver"),
        CheckConstraint("month >= 1 AND month <= 12", name="chk_climatology_month"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    subdivision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rainfall_subdivisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    years_used: Mapped[int] = mapped_column(Integer, nullable=False)
    mean_mm: Mapped[float] = mapped_column(Float, nullable=False)
    stddev_mm: Mapped[float] = mapped_column(Float, nullable=False)
    min_mm: Mapped[float] = mapped_column(Float, nullable=False)
    max_mm: Mapped[float] = mapped_column(Float, nullable=False)
    source_period_start: Mapped[int] = mapped_column(Integer, nullable=False)
    source_period_end: Mapped[int] = mapped_column(Integer, nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(50), default="v1.0", nullable=False)

    calculated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    subdivision: Mapped[RainfallSubdivision] = relationship(
        "RainfallSubdivision",
        back_populates="climatology",
    )
