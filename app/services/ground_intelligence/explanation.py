"""
Deterministic explanation generator for ground intelligence evaluations.
"""
from __future__ import annotations

from app.schemas.ground_report import TrustClass
from app.services.ground_intelligence.trust import TrustScoreResult


class GroundIntelligenceExplanationGenerator:
    """Generates auditable, deterministic narrative explanations for trust evaluations."""

    @staticmethod
    def generate_explanation(
        trust_result: TrustScoreResult,
        trust_class: TrustClass,
        is_duplicate: bool,
        duplicate_match_reason: str | None,
        corroborating_count: int,
        risk_influence_eligible: bool,
        eligibility_reasons: list[str],
    ) -> list[str]:
        """Synthesize human-readable, deterministic audit statements."""
        statements: list[str] = []

        # 1. Overall evaluation statement
        statements.append(
            f"Observation evaluated with a Trust Score of {trust_result.trust_score:.1f}/100 ({trust_class.value} confidence tier)."
        )

        # 2. Component contributions
        statements.append(
            f"Component contributions: Geo-Plausibility: {trust_result.geo_contribution:.1f} pts (score: {trust_result.geo_plausibility:.1f}/100, weight: 25%), "
            f"Temporal Freshness: {trust_result.temporal_contribution:.1f} pts (score: {trust_result.temporal_freshness:.1f}/100, weight: 20%), "
            f"User Reliability: {trust_result.user_contribution:.1f} pts (score: {trust_result.user_reliability:.1f}/100, weight: 25%), "
            f"Corroboration: {trust_result.corroboration_contribution:.1f} pts (score: {trust_result.corroboration:.1f}/100, weight: 30%)."
        )

        # 3. Corroboration details
        if corroborating_count > 0:
            statements.append(
                f"Multi-observer corroboration confirmed across {corroborating_count} independent nearby field report(s) within spatial-temporal convergence bounds."
            )
        else:
            statements.append(
                "No independent corroborating field reports detected in the immediate spatial-temporal vicinity; corroboration contribution is 0.0."
            )

        # 4. Duplicate status
        if is_duplicate:
            statements.append(
                f"DUPLICATE DETECTED: {duplicate_match_reason or 'Observation matches a prior submission.'}"
            )
        else:
            statements.append("Deduplication check: Verified as a distinct, unique observation.")

        # 5. Risk eligibility statement
        if risk_influence_eligible:
            statements.append(
                "Automated Risk Gate: ELIGIBLE. Report meets all multi-signal criteria (trust >= 60.0, non-duplicate, active status, fresh observation, valid geography)."
            )
        else:
            reasons_str = "; ".join(eligibility_reasons) if eligibility_reasons else "Requirements not satisfied."
            statements.append(
                f"Automated Risk Gate: NOT ELIGIBLE. Disqualifying factors: {reasons_str}"
            )

        return statements
