"""
User reliability evaluator based on authentication provenance and reporting history.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ground_report import GroundReport
from app.models.user import User
from app.services.ground_intelligence.constants import (
    DEFAULT_USER_RELIABILITY_CITIZEN,
    DEFAULT_USER_RELIABILITY_OFFICIAL,
    USER_RELIABILITY_ACCEPTED_BONUS,
    USER_RELIABILITY_DUPLICATE_PENALTY,
    USER_RELIABILITY_MAX,
    USER_RELIABILITY_MIN,
    USER_RELIABILITY_REJECTED_PENALTY,
)


class UserReliabilityEvaluator:
    """Calculates deterministic user reliability score."""

    @staticmethod
    def calculate_reliability(
        user_id: uuid.UUID,
        db: Session | None = None,
        role: str = "citizen",
    ) -> float:
        """Evaluate user reliability from authenticated role and historical reporting outcomes.

        Cold-start users receive a neutral prior (50.0 for citizen, 60.0 for official).
        Historical outcomes adjust the baseline score with bounded clamping in [5.0, 100.0].
        """
        # Baseline prior
        if role in ("official", "admin"):
            prior = DEFAULT_USER_RELIABILITY_OFFICIAL
        else:
            prior = DEFAULT_USER_RELIABILITY_CITIZEN

        if db is None:
            return round(prior, 2)

        # Query user role directly if user exists in DB
        user_record = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if user_record and user_record.role in ("official", "admin"):
            prior = DEFAULT_USER_RELIABILITY_OFFICIAL

        # Aggregate historical report outcomes for this user
        accepted_count = (
            db.execute(
                select(func.count(GroundReport.id)).where(
                    GroundReport.user_id == user_id,
                    GroundReport.status == "ACCEPTED",
                )
            ).scalar()
            or 0
        )

        rejected_count = (
            db.execute(
                select(func.count(GroundReport.id)).where(
                    GroundReport.user_id == user_id,
                    GroundReport.status == "REJECTED",
                )
            ).scalar()
            or 0
        )

        duplicate_count = (
            db.execute(
                select(func.count(GroundReport.id)).where(
                    GroundReport.user_id == user_id,
                    GroundReport.is_duplicate.is_(True),
                )
            ).scalar()
            or 0
        )

        # Compute deterministic modifier
        bonus = accepted_count * USER_RELIABILITY_ACCEPTED_BONUS
        penalties = (rejected_count * USER_RELIABILITY_REJECTED_PENALTY) + (
            duplicate_count * USER_RELIABILITY_DUPLICATE_PENALTY
        )

        raw_score = prior + bonus - penalties
        clamped = max(USER_RELIABILITY_MIN, min(USER_RELIABILITY_MAX, raw_score))
        return round(clamped, 2)
