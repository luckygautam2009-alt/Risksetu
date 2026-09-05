"""Phase 2 — SOS Emergency Network, audience subscriptions, and dispatch tracking tables.

Revision ID: 0007_phase2_sos_alert_network
Revises: 0006_identity_and_evidence
Create Date: 2026-09-05 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0007_phase2_sos_alert_network"
down_revision: Union[str, None] = "0006_identity_and_evidence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Extend sos_reports with Phase 2 fields
    # ------------------------------------------------------------------
    op.add_column("sos_reports", sa.Column("location_accuracy_meters", sa.Float(), nullable=True))
    op.add_column("sos_reports", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "sos_reports",
        sa.Column("risk_source", sa.String(50), nullable=True, server_default="LIVE_RISK_V1"),
    )
    op.add_column(
        "sos_reports",
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "sos_reports",
        sa.Column("created_by_verified_identity", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column("sos_reports", sa.Column("idempotency_key", sa.String(128), nullable=True))
    op.create_index("ix_sos_reports_idempotency_key", "sos_reports", ["idempotency_key"])

    # ------------------------------------------------------------------
    # 2. alert_subscriptions
    # ------------------------------------------------------------------
    op.create_table(
        "alert_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "notification_type",
            sa.String(50),
            nullable=False,
            server_default="EMERGENCY_ALERTS",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("geofence_radius_km", sa.Float(), nullable=True),
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
        "uix_alert_subscriptions_user_type",
        "alert_subscriptions",
        ["user_id", "notification_type"],
        unique=True,
    )
    op.create_index("ix_alert_subscriptions_user_id", "alert_subscriptions", ["user_id"])
    op.create_index("ix_alert_subscriptions_type", "alert_subscriptions", ["notification_type"])

    # ------------------------------------------------------------------
    # 3. emergency_dispatches
    # ------------------------------------------------------------------
    op.create_table(
        "emergency_dispatches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "alert_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alerts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sos_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sos_reports.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(50), nullable=False, server_default="QUEUED"),
        sa.Column("provider_response", postgresql.JSON(none_as_null=True), nullable=True),
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
    op.create_index("ix_emergency_dispatches_alert_id", "emergency_dispatches", ["alert_id"])
    op.create_index("ix_emergency_dispatches_sos_id", "emergency_dispatches", ["sos_id"])
    op.create_index("ix_emergency_dispatches_status", "emergency_dispatches", ["status"])
    op.create_index("ix_emergency_dispatches_channel", "emergency_dispatches", ["channel"])
    op.create_index("ix_emergency_dispatches_created_at", "emergency_dispatches", ["created_at"])


def downgrade() -> None:
    # ------------------------------------------------------------------
    # 3. emergency_dispatches
    # ------------------------------------------------------------------
    op.drop_index("ix_emergency_dispatches_created_at", table_name="emergency_dispatches")
    op.drop_index("ix_emergency_dispatches_channel", table_name="emergency_dispatches")
    op.drop_index("ix_emergency_dispatches_status", table_name="emergency_dispatches")
    op.drop_index("ix_emergency_dispatches_sos_id", table_name="emergency_dispatches")
    op.drop_index("ix_emergency_dispatches_alert_id", table_name="emergency_dispatches")
    op.drop_table("emergency_dispatches")

    # ------------------------------------------------------------------
    # 2. alert_subscriptions
    # ------------------------------------------------------------------
    op.drop_index("ix_alert_subscriptions_type", table_name="alert_subscriptions")
    op.drop_index("ix_alert_subscriptions_user_id", table_name="alert_subscriptions")
    op.drop_index("uix_alert_subscriptions_user_type", table_name="alert_subscriptions")
    op.drop_table("alert_subscriptions")

    # ------------------------------------------------------------------
    # 1. sos_reports extensions
    # ------------------------------------------------------------------
    op.drop_index("ix_sos_reports_idempotency_key", table_name="sos_reports")
    op.drop_column("sos_reports", "idempotency_key")
    op.drop_column("sos_reports", "created_by_verified_identity")
    op.drop_column("sos_reports", "evidence_count")
    op.drop_column("sos_reports", "risk_source")
    op.drop_column("sos_reports", "cancelled_at")
    op.drop_column("sos_reports", "location_accuracy_meters")
