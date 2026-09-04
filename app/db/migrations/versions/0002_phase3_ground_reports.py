"""Phase 3: Ground intelligence, trust scoring, and user accounts migration.

Revision ID: 0002_phase3_ground_reports
Revises: 0001_phase1b_core_tables
Create Date: 2026-09-04 12:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = "0002_phase3_ground_reports"
down_revision: Union[str, None] = "0001_phase1b_core_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="citizen"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    # 2. Ground Reports table
    op.create_table(
        "ground_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("geom", geoalchemy2.Geometry("POINT", srid=4326), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="SUBMITTED"),
        sa.Column("trust_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("trust_class", sa.String(50), nullable=False, server_default="LOW"),
        sa.Column("geo_plausibility_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("temporal_freshness_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("user_reliability_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("corroboration_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("duplicate_of_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ground_reports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("duplicate_group_id", sa.String(64), nullable=True),
        sa.Column("risk_influence_eligible", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("source_metadata", sa.JSON(), nullable=True),
        sa.Column("audit_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("latitude >= -90.0 AND latitude <= 90.0", name="chk_ground_report_latitude"),
        sa.CheckConstraint("longitude >= -180.0 AND longitude <= 180.0", name="chk_ground_report_longitude"),
        sa.CheckConstraint("trust_score >= 0.0 AND trust_score <= 100.0", name="chk_ground_report_trust_score"),
    )
    op.create_index("ix_ground_reports_user_id", "ground_reports", ["user_id"])
    op.create_index("ix_ground_reports_type", "ground_reports", ["report_type"])
    op.create_index("ix_ground_reports_status", "ground_reports", ["status"])
    op.create_index("ix_ground_reports_observed_at", "ground_reports", ["observed_at"])
    op.create_index("ix_ground_reports_trust_class", "ground_reports", ["trust_class"])
    op.create_index("ix_ground_reports_duplicate", "ground_reports", ["is_duplicate"])
    op.create_index("ix_ground_reports_duplicate_group", "ground_reports", ["duplicate_group_id"])
    op.create_index("ix_ground_reports_risk_eligible", "ground_reports", ["risk_influence_eligible", "status"])
    op.create_index("ix_ground_reports_type_status", "ground_reports", ["report_type", "status"])

    # 3. Ground Report Audits table
    op.create_table(
        "ground_report_audits",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ground_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("previous_state", sa.JSON(), nullable=True),
        sa.Column("new_state", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ground_report_audits_report_id", "ground_report_audits", ["report_id"])
    op.create_index("ix_ground_report_audits_action", "ground_report_audits", ["action"])


def downgrade() -> None:
    op.drop_table("ground_report_audits")
    op.drop_table("ground_reports")
    op.drop_table("users")
