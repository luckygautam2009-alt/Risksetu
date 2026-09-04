"""
Deterministic trust score calculation engine.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.ground_intelligence.constants import (
    CALCULATION_VERSION,
    WEIGHT_CORROBORATION,
    WEIGHT_GEO,
    WEIGHT_TEMPORAL,
    WEIGHT_USER,
)


@dataclass
class TrustScoreResult:
    """Comprehensive trust score evaluation output."""

    trust_score: float
    geo_plausibility: float
    temporal_freshness: float
    user_reliability: float
    corroboration: float
    geo_contribution: float
    temporal_contribution: float
    user_contribution: float
    corroboration_contribution: float
    calculation_version: str = CALCULATION_VERSION


class TrustScoringEngine:
    """Deterministic composite trust calculation engine."""

    @staticmethod
    def calculate_trust(
        geo_plausibility: float,
        temporal_freshness: float,
        user_reliability: float,
        corroboration: float,
    ) -> TrustScoreResult:
        """Calculate composite trust score [0.0 - 100.0] using deterministic weights.

        Formula:
            trust_score = 0.25 * geo + 0.20 * temporal + 0.25 * user + 0.30 * corroboration
        """
        g_clamped = max(0.0, min(100.0, float(geo_plausibility)))
        t_clamped = max(0.0, min(100.0, float(temporal_freshness)))
        u_clamped = max(0.0, min(100.0, float(user_reliability)))
        c_clamped = max(0.0, min(100.0, float(corroboration)))

        geo_contrib = round(WEIGHT_GEO * g_clamped, 2)
        temp_contrib = round(WEIGHT_TEMPORAL * t_clamped, 2)
        user_contrib = round(WEIGHT_USER * u_clamped, 2)
        corrob_contrib = round(WEIGHT_CORROBORATION * c_clamped, 2)

        raw_score = (
            WEIGHT_GEO * g_clamped
            + WEIGHT_TEMPORAL * t_clamped
            + WEIGHT_USER * u_clamped
            + WEIGHT_CORROBORATION * c_clamped
        )
        trust_score = round(max(0.0, min(100.0, raw_score)), 2)

        return TrustScoreResult(
            trust_score=trust_score,
            geo_plausibility=g_clamped,
            temporal_freshness=t_clamped,
            user_reliability=u_clamped,
            corroboration=c_clamped,
            geo_contribution=geo_contrib,
            temporal_contribution=temp_contrib,
            user_contribution=user_contrib,
            corroboration_contribution=corrob_contrib,
        )
