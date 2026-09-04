"""
Priority Scoring Engine Service.

Calculates the composite intervention priority score and categorical level
using deterministic weights: 45% hazard risk, 40% isolation impact, 15% urgency.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.priority.constants import (
    PRIORITY_LEVEL_HIGH_MAX,
    PRIORITY_LEVEL_LOW_MAX,
    PRIORITY_LEVEL_MODERATE_MAX,
    WEIGHT_IMPACT,
    WEIGHT_RISK,
    WEIGHT_URGENCY,
)


@dataclass
class PriorityBreakdown:
    """Quantitative contribution breakdown of the composite priority score."""

    risk_contribution: float
    impact_contribution: float
    urgency_contribution: float
    priority_score: float
    priority_level: str


class PriorityScoringEngine:
    """Deterministic composite priority scoring engine."""

    @staticmethod
    def calculate_priority(
        risk_score: float,
        isolation_severity: float,
        urgency_score: float,
    ) -> PriorityBreakdown:
        """Compute composite priority score and weighted contribution components.

        Formula:
            priority = 0.45 * risk_score + 0.40 * isolation_severity + 0.15 * urgency_score
        Strictly bounded in [0.0, 100.0].

        Args:
            risk_score: Normalized hazard risk score [0.0, 100.0].
            isolation_severity: Normalized isolation severity score [0.0, 100.0].
            urgency_score: Normalized urgency score [0.0, 100.0].

        Returns:
            PriorityBreakdown with exact component contributions and categorical level.
        """
        r_clamped = max(0.0, min(100.0, float(risk_score)))
        i_clamped = max(0.0, min(100.0, float(isolation_severity)))
        u_clamped = max(0.0, min(100.0, float(urgency_score)))

        risk_contrib = round(WEIGHT_RISK * r_clamped, 2)
        impact_contrib = round(WEIGHT_IMPACT * i_clamped, 2)
        urgency_contrib = round(WEIGHT_URGENCY * u_clamped, 2)

        raw_score = (
            WEIGHT_RISK * r_clamped
            + WEIGHT_IMPACT * i_clamped
            + WEIGHT_URGENCY * u_clamped
        )
        priority_score = round(max(0.0, min(100.0, raw_score)), 2)
        priority_level = PriorityScoringEngine.determine_priority_level(priority_score)

        return PriorityBreakdown(
            risk_contribution=risk_contrib,
            impact_contribution=impact_contrib,
            urgency_contribution=urgency_contrib,
            priority_score=priority_score,
            priority_level=priority_level,
        )

    @staticmethod
    def determine_priority_level(score: float) -> str:
        """Map numerical priority score to standard categorical level."""
        if score <= PRIORITY_LEVEL_LOW_MAX:
            return "LOW"
        elif score <= PRIORITY_LEVEL_MODERATE_MAX:
            return "MODERATE"
        elif score <= PRIORITY_LEVEL_HIGH_MAX:
            return "HIGH"
        else:
            return "CRITICAL"
