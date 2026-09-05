"""Phase 5 — SOS emergency reports, SOS audit trail, and shelter facilities tables.

Revision ID: 0005_sos_shelters
Revises: 0004_phase4_alerts
Create Date: 2026-09-04 21:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql


revision: str = "0005_sos_shelters"
down_revision: Union[str, None] = "0004_phase4_alerts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. sos_reports
    # ------------------------------------------------------------------
    op.create_table(
        "sos_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "geom",
            Geometry("POINT", srid=4326, spatial_index=True),
            nullable=True,
        ),
        sa.Column("severity", sa.String(30), nullable=False, server_default="MEDIUM"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="ACTIVE"),
        sa.Column("live_risk_score", sa.Float(), nullable=True),
        sa.Column("live_risk_level", sa.String(30), nullable=True),
        sa.Column("live_risk_confidence", sa.Float(), nullable=True),
        sa.Column("risk_context", postgresql.JSON(none_as_null=True), nullable=True),
        sa.Column(
            "linked_alert_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alerts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "reported_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "acknowledged_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "resolved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "shelter_recommendation",
            postgresql.JSON(none_as_null=True),
            nullable=True,
        ),
        sa.Column("request_id", sa.String(128), nullable=True),
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
        sa.CheckConstraint(
            "latitude >= -90.0 AND latitude <= 90.0",
            name="chk_sos_latitude",
        ),
        sa.CheckConstraint(
            "longitude >= -180.0 AND longitude <= 180.0",
            name="chk_sos_longitude",
        ),
    )
    op.create_index("ix_sos_reports_status", "sos_reports", ["status"])
    op.create_index("ix_sos_reports_severity", "sos_reports", ["severity"])
    op.create_index("ix_sos_reports_created_at", "sos_reports", ["created_at"])
    op.create_index("ix_sos_reports_reported_by", "sos_reports", ["reported_by"])
    op.create_index("ix_sos_reports_linked_alert_id", "sos_reports", ["linked_alert_id"])

    # ------------------------------------------------------------------
    # 2. sos_audits
    # ------------------------------------------------------------------
    op.create_table(
        "sos_audits",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "sos_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sos_reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("previous_status", sa.String(30), nullable=True),
        sa.Column("new_status", sa.String(30), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSON(none_as_null=True),
            nullable=True,
        ),
        sa.Column("request_id", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_sos_audits_sos_id", "sos_audits", ["sos_id"])
    op.create_index("ix_sos_audits_action", "sos_audits", ["action"])

    # ------------------------------------------------------------------
    # 3. shelters
    # ------------------------------------------------------------------
    op.create_table(
        "shelters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("facility_type", sa.String(100), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "geom",
            Geometry("POINT", srid=4326, spatial_index=True),
            nullable=False,
        ),
        sa.Column("capacity_persons", sa.Integer(), nullable=True),
        sa.Column("is_accessible", sa.Boolean(), nullable=True),
        sa.Column("accessibility_notes", sa.Text(), nullable=True),
        sa.Column("district", sa.String(200), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("data_source", sa.String(300), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "extra_metadata",
            postgresql.JSON(none_as_null=True),
            nullable=True,
        ),
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
    op.create_index("ix_shelters_is_active", "shelters", ["is_active"])
    op.create_index("ix_shelters_facility_type", "shelters", ["facility_type"])


def downgrade() -> None:
    op.drop_table("shelters")
    op.drop_table("sos_audits")
    op.drop_table("sos_reports")
