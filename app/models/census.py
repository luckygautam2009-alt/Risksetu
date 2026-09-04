"""
Census 2011 demographic and administrative reference models.
"""
from __future__ import annotations

import datetime
from typing import Any
import uuid

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CensusVillage(Base):
    """Primary Census Abstract (PCA) 2011 Village and Town demographic registry."""

    __tablename__ = "census_villages"
    __table_args__ = (
        UniqueConstraint(
            "state_code",
            "district_code",
            "subdistrict_code",
            "village_code",
            name="uq_census_hierarchy_code",
        ),
        CheckConstraint("total_population >= 0", name="chk_census_population_positive"),
        CheckConstraint("households >= 0", name="chk_census_households_positive"),
        Index("ix_census_villages_state_dist", "state_code", "district_code"),
        Index("ix_census_villages_name", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    state_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    district_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    subdistrict_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    village_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    level: Mapped[str] = mapped_column(String(50), default="VILLAGE", nullable=False)
    rural_urban: Mapped[str] = mapped_column(String(20), default="Rural", nullable=False)

    total_population: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    male_population: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    female_population: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    households: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    child_population_0_6: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sc_population: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    st_population: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    literate_population: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    illiterate_population: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    working_population: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cultivators: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    agricultural_labourers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    census_year: Mapped[int] = mapped_column(Integer, default=2011, nullable=False)
    geom: Mapped[Any | None] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=True),
        nullable=True,
    )

    source_dataset: Mapped[str] = mapped_column(String(100), default="CENSUS_2011_PCA", nullable=False)
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


class CensusAreaReference(Base):
    """Authoritative administrative area and village count reference from Census Table A-1."""

    __tablename__ = "census_area_reference"
    __table_args__ = (
        UniqueConstraint(
            "state_code",
            "district_code",
            "subdistrict_code",
            "level",
            "rural_urban",
            name="uq_census_a1_hierarchy",
        ),
        Index("ix_census_a1_state_dist", "state_code", "district_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    state_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    district_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    subdistrict_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(50), nullable=False)  # INDIA, STATE, DISTRICT, SUB-DISTRICT
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    rural_urban: Mapped[str] = mapped_column(String(20), default="Total", nullable=False)

    inhabited_villages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uninhabited_villages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    number_of_towns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    households: Mapped[int | None] = mapped_column(Integer, nullable=True)
    population_persons: Mapped[int | None] = mapped_column(Integer, nullable=True)
    area_sq_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    population_density_per_sq_km: Mapped[float | None] = mapped_column(Float, nullable=True)

    source_dataset: Mapped[str] = mapped_column(String(100), default="CENSUS_2011_A1", nullable=False)
    source_record_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
