"""
Explainability generator for the Risk Intelligence Engine.
"""
from __future__ import annotations

from app.schemas.risk import RiskFactorDetail
from app.services.risk.constants import STANDARD_LIMITATIONS


class RiskExplanationGenerator:
    """Generates structured summaries and plain-language risk rationales."""

    @staticmethod
    def generate_summary(
        risk_score: float,
        risk_level: str,
        factors: list[RiskFactorDetail],
        redistribution_note: str | None = None,
    ) -> str:
        """Generate a concise, transparent summary of primary risk drivers."""
        available_factors = [f for f in factors if f.available]
        available_factors.sort(key=lambda x: x.score * x.effective_weight, reverse=True)

        parts: list[str] = [
            f"Evaluated Risk Score: {risk_score:.1f}/100 ({risk_level}).",
        ]

        if available_factors:
            top_factor = available_factors[0]
            parts.append(
                f"Primary driver is {top_factor.display_name} (Score: {top_factor.score:.1f}, "
                f"Effective Weight: {top_factor.effective_weight * 100:.1f}%)."
            )

        if redistribution_note:
            parts.append(redistribution_note)

        return " ".join(parts)

    @staticmethod
    def get_limitations() -> list[str]:
        """Return standardized data honesty and limitations notice."""
        return list(STANDARD_LIMITATIONS)
