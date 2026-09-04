"""
Urgency Evaluator Service.

Computes a deterministic urgency score [0, 100] from categorical hazard risk level
and data confidence.
"""
from __future__ import annotations

from app.services.priority.constants import RISK_LEVEL_URGENCY_MAP


class UrgencyEvaluator:
    """Evaluates intervention urgency using defensible existing signals."""

    @staticmethod
    def calculate_urgency(risk_level: str, confidence: float) -> float:
        """Calculate urgency score based on categorical risk level and data confidence.

        Formula:
            urgency = risk_level_base * (0.5 + 0.5 * (confidence / 100.0))
        Clamped to [0.0, 100.0].

        Args:
            risk_level: Categorical risk level ('CRITICAL', 'HIGH', 'MODERATE', 'LOW').
            confidence: Data completeness confidence percentage [0.0, 100.0].

        Returns:
            Normalized urgency score [0.0, 100.0].
        """
        normalized_level = risk_level.strip().upper()
        base = RISK_LEVEL_URGENCY_MAP.get(normalized_level, 25.0)

        # Normalize and clamp confidence to [0, 100]
        conf_clamped = max(0.0, min(100.0, float(confidence)))
        conf_factor = 0.5 + 0.5 * (conf_clamped / 100.0)

        raw_urgency = base * conf_factor
        return round(max(0.0, min(100.0, raw_urgency)), 2)
