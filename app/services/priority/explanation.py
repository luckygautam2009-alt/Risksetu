"""
Priority Explanation Generator.

Produces plain-language, audit-defensible explanations of intervention priority scores,
highlighting trade-offs between hazard risk, network disruption, and data confidence.
"""
from __future__ import annotations

from app.services.priority.constants import STANDARD_PRIORITY_LIMITATIONS


class PriorityExplanationGenerator:
    """Generates explainable rationale for intervention priority classifications."""

    @staticmethod
    def generate_summary(
        priority_score: float,
        priority_level: str,
        risk_score: float,
        isolation_severity: float,
        urgency_score: float,
        is_bridge_edge: bool,
        nodes_affected: int,
    ) -> str:
        """Synthesize a plain-language summary of the priority evaluation findings."""
        # Core driver analysis
        is_impact_driven = isolation_severity > risk_score + 10.0
        is_risk_driven = risk_score > isolation_severity + 10.0
        bridge_str = "is a graph-theoretic bridge" if is_bridge_edge else "has alternate bypass paths"

        if is_impact_driven:
            driver_text = (
                f"Intervention priority is heavily elevated by severe connectivity disruption "
                f"(isolation severity: {isolation_severity:.1f}/100) across {nodes_affected} newly isolated nodes, "
                f"despite moderate hazard risk ({risk_score:.1f}/100). The local access route {bridge_str}."
            )
        elif is_risk_driven:
            driver_text = (
                f"Intervention priority is primarily driven by high hazard risk ({risk_score:.1f}/100), "
                f"while network isolation impact remains relatively lower ({isolation_severity:.1f}/100)."
            )
        else:
            driver_text = (
                f"Intervention priority reflects balanced contributions from hazard risk ({risk_score:.1f}/100) "
                f"and potential connectivity disruption ({isolation_severity:.1f}/100)."
            )

        urgency_text = f"Urgency is evaluated at {urgency_score:.1f}/100 based on categorical risk and data completeness."

        return (
            f"Candidate evaluated at {priority_level} priority ({priority_score:.1f}/100). "
            f"{driver_text} {urgency_text}"
        )

    @staticmethod
    def get_limitations() -> list[str]:
        """Return standard honesty limitations."""
        return list(STANDARD_PRIORITY_LIMITATIONS)
