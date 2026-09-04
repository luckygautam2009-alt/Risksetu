"""
Categorical trust classification mapper.
"""
from __future__ import annotations

from app.schemas.ground_report import TrustClass
from app.services.ground_intelligence.constants import (
    TRUST_LEVEL_HIGH_MAX,
    TRUST_LEVEL_LOW_MAX,
    TRUST_LEVEL_MODERATE_MAX,
)


class TrustClassifier:
    """Classifies numerical trust score into standard 4-tier categorical ratings."""

    @staticmethod
    def classify(score: float) -> TrustClass:
        """Map trust score [0.0 - 100.0] to TrustClass tier."""
        if score <= TRUST_LEVEL_LOW_MAX:
            return TrustClass.LOW
        if score <= TRUST_LEVEL_MODERATE_MAX:
            return TrustClass.MODERATE
        if score <= TRUST_LEVEL_HIGH_MAX:
            return TrustClass.HIGH
        return TrustClass.VERY_HIGH
