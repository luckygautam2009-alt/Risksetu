"""Phase 4 — Operational alerts and alert audit trail tables.

Revision ID: 0004_phase4_alerts
Revises: 0003_gr_idempotency
Create Date: 2026-09-04 13:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0004_phase4_alerts"
down_revision: Union[str, None] = "0003_gr_idempotency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create alerts table
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="ACTIVE"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("risk_level", sa.String(50), nullable=True),
        sa.Column("risk_confidence", sa.Float(), nullable=True),
        sa.Column("isolation_severity", sa.String(50), nullable=True),
        sa.Column("priority_score", sa.Float(), nullable=True),
        sa.Column("priority_level", sa.String(50), nullable=True),
        sa.Column("ground_intelligence_summary", sa.JSON(), nullable=True),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("source_reference", sa.JSON(), nullable=True),
        sa.Column("recommended_actions", sa.JSON(), nullable=True),
        sa.Column("explanation", sa.JSON(), nullable=True),
        sa.Column("data_freshness", sa.JSON(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "acknowledged_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resolved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("calculation_version", sa.String(50), nullable=False, server_default="v1.0.0"),
        sa.Column("audit_metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("latitude >= -90.0 AND latitude <= 90.0", name="chk_alert_latitude"),
        sa.CheckConstraint("longitude >= -180.0 AND longitude <= 180.0", name="chk_alert_longitude"),
    )

    # 2. Alerts indexes
    op.create_index("ix_alerts_alert_type", "alerts", ["alert_type"])
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_fingerprint", "alerts", ["fingerprint"])
    op.create_index("ix_alerts_status_severity", "alerts", ["status", "severity"])
    op.create_index("ix_alerts_type_status", "alerts", ["alert_type", "status"])
    op.create_index("ix_alerts_created_at_desc", "alerts", ["created_at"])
    op.create_index(
        "uix_alerts_active_fingerprint",
        "alerts",
        ["fingerprint"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    # 3. Create alert_audits table
    op.create_table(
        "alert_audits",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "alert_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alerts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("previous_state", sa.JSON(), nullable=True),
        sa.Column("new_state", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # 4. Alert_audits indexes
    op.create_index("ix_alert_audits_alert_id", "alert_audits", ["alert_id"])
    op.create_index("ix_alert_audits_action", "alert_audits", ["action"])


def downgrade() -> None:
    op.drop_index("ix_alert_audits_action", table_name="alert_audits")
    op.drop_index("ix_alert_audits_alert_id", table_name="alert_audits")
    op.drop_table("alert_audits")

    op.drop_index("uix_alerts_active_fingerprint", table_name="alerts")
    op.drop_index("ix_alerts_created_at_desc", table_name="alerts")
    op.drop_index("ix_alerts_type_status", table_name="alerts")
    op.drop_index("ix_alerts_status_severity", table_name="alerts")
    op.drop_index("ix_alerts_fingerprint", table_name="alerts")
    op.drop_index("ix_alerts_status", table_name="alerts")
    op.drop_index("ix_alerts_severity", table_name="alerts")
    op.drop_index("ix_alerts_alert_type", table_name="alerts")
    op.drop_table("alerts")
