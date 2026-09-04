"""Phase 3 — Add idempotency_key to ground_reports for DB-level exactly-once semantics.

Revision ID: 0003_ground_report_idempotency_key
Revises: 0002_phase3_ground_reports
Create Date: 2026-09-04 13:07:00.000000

Rationale:
    Idempotency was originally Redis-only. In environments where Redis is
    unavailable (test suites, offline, degraded) there was no durable fallback,
    causing duplicate reports on retried requests.  This migration adds a
    nullable `idempotency_key` column and a partial unique index
    (user_id, idempotency_key) WHERE idempotency_key IS NOT NULL, providing
    exactly-once guarantees at the database layer.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003_gr_idempotency"
down_revision: Union[str, None] = "0002_phase3_ground_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add idempotency_key column (nullable — existing rows get NULL, which is excluded from the unique index)
    op.add_column(
        "ground_reports",
        sa.Column("idempotency_key", sa.String(255), nullable=True),
    )

    # Non-unique index for fast single-column lookups
    op.create_index(
        "ix_ground_reports_idempotency_key",
        "ground_reports",
        ["idempotency_key"],
    )

    # Partial unique index: (user_id, idempotency_key) WHERE idempotency_key IS NOT NULL
    # This enforces exactly-once semantics per user while allowing NULL idempotency_key (reports without a key).
    op.create_index(
        "uix_ground_reports_user_idempotency",
        "ground_reports",
        ["user_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uix_ground_reports_user_idempotency", table_name="ground_reports")
    op.drop_index("ix_ground_reports_idempotency_key", table_name="ground_reports")
    op.drop_column("ground_reports", "idempotency_key")
