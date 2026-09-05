"""Phase 1 — Identity verifications, identity audits, and incident evidence tables.

Revision ID: 0006_identity_and_evidence
Revises: 0005_sos_shelters
Create Date: 2026-09-05 11:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0006_identity_and_evidence"
down_revision: Union[str, None] = "0005_sos_shelters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. identity_verifications
    # ------------------------------------------------------------------
    op.create_table(
        "identity_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="UNVERIFIED"),
        sa.Column("provider_transaction_id", sa.String(255), nullable=True),
        sa.Column("provider_reference_hash", sa.String(255), nullable=True),
        sa.Column("consent_obtained", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("consent_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(50), nullable=True),
        sa.Column("failure_message_safe", sa.String(255), nullable=True),
        sa.Column("identity_name_hash_or_minimal_reference", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_identity_verifications_user_provider",
        "identity_verifications",
        ["user_id", "provider"],
        unique=True,
    )
    op.create_index(
        "ix_identity_verifications_status",
        "identity_verifications",
        ["status"],
    )
    op.create_index(
        "ix_identity_verifications_tx_id",
        "identity_verifications",
        ["provider_transaction_id"],
    )

    # ------------------------------------------------------------------
    # 2. identity_verification_audits
    # ------------------------------------------------------------------
    op.create_table(
        "identity_verification_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "verification_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("identity_verifications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("details_safe", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_identity_audit_verification_id",
        "identity_verification_audits",
        ["verification_id"],
    )
    op.create_index(
        "ix_identity_audit_user_id",
        "identity_verification_audits",
        ["user_id"],
    )
    op.create_index(
        "ix_identity_audit_event_type",
        "identity_verification_audits",
        ["event_type"],
    )
    op.create_index(
        "ix_identity_audit_created_at",
        "identity_verification_audits",
        ["created_at"],
    )

    # ------------------------------------------------------------------
    # 3. incident_evidence
    # ------------------------------------------------------------------
    op.create_table(
        "incident_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "incident_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ground_reports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "sos_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sos_reports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("upload_status", sa.String(50), nullable=False, server_default="STORED"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_incident_evidence_owner_user_id", "incident_evidence", ["owner_user_id"])
    op.create_index("ix_incident_evidence_incident_id", "incident_evidence", ["incident_id"])
    op.create_index("ix_incident_evidence_sos_id", "incident_evidence", ["sos_id"])
    op.create_index("ix_incident_evidence_sha256", "incident_evidence", ["sha256"])
    op.create_index("ix_incident_evidence_created_at", "incident_evidence", ["created_at"])


def downgrade() -> None:
    op.drop_table("incident_evidence")
    op.drop_table("identity_verification_audits")
    op.drop_table("identity_verifications")
