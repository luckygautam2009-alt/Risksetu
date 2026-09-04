"""
Automated risk influence eligibility policy evaluator.
"""
from __future__ import annotations

import datetime

from app.services.ground_intelligence.constants import (
    MAX_AGE_DAYS_FOR_RISK_ELIGIBILITY,
    MIN_GEO_PLAUSIBILITY_FOR_RISK_ELIGIBILITY,
    MIN_TRUST_FOR_RISK_ELIGIBILITY,
)


class RiskEligibilityEvaluator:
    """Evaluates whether a field observation is eligible to influence risk models."""

    @staticmethod
    def is_eligible(
        trust_score: float,
        is_duplicate: bool,
        status: str,
        observed_at: datetime.datetime,
        geo_plausibility_score: float,
        reference_time: datetime.datetime | None = None,
    ) -> tuple[bool, list[str]]:
        """Evaluate multi-signal eligibility criteria for automated risk influence.

        Returns:
            Tuple of (is_eligible: bool, reasons: list[str])
        """
        reasons: list[str] = []
        now = reference_time or datetime.datetime.now(datetime.timezone.utc)
        obs = observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=datetime.timezone.utc)
        age_days = (now - obs).total_seconds() / 86400.0

        if trust_score < MIN_TRUST_FOR_RISK_ELIGIBILITY:
            reasons.append(
                f"Trust score ({trust_score:.1f}) is below minimum threshold ({MIN_TRUST_FOR_RISK_ELIGIBILITY:.1f})."
            )

        if is_duplicate:
            reasons.append("Report is flagged as a probable or exact duplicate.")

        if status in ("REJECTED", "DUPLICATE"):
            reasons.append(f"Report status is '{status}'.")

        if age_days > MAX_AGE_DAYS_FOR_RISK_ELIGIBILITY:
            reasons.append(
                f"Observation age ({age_days:.1f} days) exceeds operational horizon ({MAX_AGE_DAYS_FOR_RISK_ELIGIBILITY:.0f} days)."
            )

        if geo_plausibility_score < MIN_GEO_PLAUSIBILITY_FOR_RISK_ELIGIBILITY:
            reasons.append(
                f"Geo-plausibility ({geo_plausibility_score:.1f}) is below geographic consistency baseline ({MIN_GEO_PLAUSIBILITY_FOR_RISK_ELIGIBILITY:.1f})."
            )

        eligible = len(reasons) == 0
        return eligible, reasons
