"""
Deterministic temporal freshness and time-decay evaluator.
"""
from __future__ import annotations

import datetime
import math

from app.services.ground_intelligence.constants import HALF_LIFE_DAYS


class TimeDecayEvaluator:
    """Calculates temporal freshness score using exponential decay."""

    @staticmethod
    def calculate_temporal_freshness(
        observed_at: datetime.datetime,
        reference_time: datetime.datetime | None = None,
        half_life_days: float = HALF_LIFE_DAYS,
    ) -> float:
        """Calculate temporal freshness score [0.0 - 100.0] via exponential decay.

        Formula:
            decay = exp(-age_days / half_life_days)
            score = round(100.0 * decay, 2)
        """
        ref = reference_time or datetime.datetime.now(datetime.timezone.utc)
        obs = observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=datetime.timezone.utc)

        # Negative age (clock drift) clamped to 0.0
        age_seconds = max(0.0, (ref - obs).total_seconds())
        age_days = age_seconds / 86400.0

        decay = math.exp(-age_days / half_life_days)
        score = round(max(0.0, min(100.0, 100.0 * decay)), 2)
        return score
