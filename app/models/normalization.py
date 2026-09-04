"""
Controlled administrative name normalization registry.
"""
from __future__ import annotations

import datetime
from typing import Any
import uuid

from sqlalchemy import DateTime, Index, JSON, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdminNameAlias(Base):
    """Controlled multi-source administrative alias lookup."""

    __tablename__ = "admin_name_aliases"
    __table_args__ = (
        UniqueConstraint("source_name", "source_dataset", "administrative_level", name="uq_source_alias_level"),
        Index("ix_admin_aliases_norm_level", "normalized_name", "administrative_level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    source_dataset: Mapped[str] = mapped_column(String(50), nullable=False)  # GSI, IMD, CENSUS, OSM
    administrative_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # state, district, subdistrict, village

    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
