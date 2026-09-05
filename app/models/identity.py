"""
Authoritative identity verification models.

IdentityVerification      — User identity verification state (Aadhaar / DigiLocker).
IdentityVerificationAudit — Immutable audit trail of identity verification lifecycle events.
"""
from __future__ import annotations

import datetime
from typing import Any
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IdentityVerification(Base):
    """Authoritative identity verification state record for a citizen or operator."""

    __tablename__ = "identity_verifications"
    __table_args__ = (
        Index("ix_identity_verifications_user_provider", "user_id", "provider", unique=True),
        Index("ix_identity_verifications_status", "status"),
        Index("ix_identity_verifications_tx_id", "provider_transaction_id"),
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
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="UNVERIFIED",
        server_default="UNVERIFIED",
        index=True,
    )
    provider_transaction_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    provider_reference_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    consent_obtained: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    consent_timestamp: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    verified_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    failure_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    failure_message_safe: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    identity_name_hash_or_minimal_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
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

    # Audits
    audits: Mapped[list[IdentityVerificationAudit]] = relationship(
        "IdentityVerificationAudit",
        back_populates="verification",
        cascade="all, delete-orphan",
    )


class IdentityVerificationAudit(Base):
    """Immutable audit trail of identity verification lifecycle transitions."""

    __tablename__ = "identity_verification_audits"
    __table_args__ = (
        Index("ix_identity_audit_verification_id", "verification_id"),
        Index("ix_identity_audit_user_id", "user_id"),
        Index("ix_identity_audit_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    verification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("identity_verifications.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    details_safe: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship
    verification: Mapped[IdentityVerification] = relationship(
        "IdentityVerification",
        back_populates="audits",
    )
