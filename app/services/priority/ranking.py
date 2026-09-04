"""
Priority Ranking Engine Service.

Ranks multiple intervention candidates by composite priority score with
multi-tier deterministic tie-breaking.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.priority.scoring import PriorityBreakdown, PriorityScoringEngine
from app.services.priority.urgency import UrgencyEvaluator


@dataclass
class RankedCandidateItem:
    """Evaluated and ranked intervention candidate item."""

    rank: int
    candidate_id: str
    latitude: float
    longitude: float
    priority_score: float
    priority_level: str
    risk_score: float
    risk_level: str
    risk_confidence: float
    isolation_severity: float
    urgency_score: float
    is_bridge_edge: bool
    nodes_affected: int
    component_increase: int
    breakdown: PriorityBreakdown
    explanation: str


class PriorityRankingEngine:
    """Engine for sorting and deterministically ranking priority candidates."""

    @staticmethod
    def rank_candidates(
        candidates: list[dict[str, Any]],
    ) -> list[RankedCandidateItem]:
        """Rank candidates in descending priority with multi-tier deterministic tie-breaking.

        Tie-breaking hierarchy:
            1. Higher isolation severity (DESC)
            2. Higher risk score (DESC)
            3. Higher risk confidence (DESC)
            4. Stable candidate ID (ASC, lexicographical)

        Args:
            candidates: List of candidate dicts or models containing risk and impact metrics.

        Returns:
            List of RankedCandidateItem ordered by rank ascending (1, 2, 3, ...).
        """
        if not candidates:
            return []

        evaluated_items: list[dict[str, Any]] = []

        for c in candidates:
            candidate_id = str(c.get("candidate_id", ""))
            lat = float(c.get("latitude", 0.0))
            lon = float(c.get("longitude", 0.0))
            risk_score = float(c.get("risk_score", 0.0))
            risk_level = str(c.get("risk_level", "LOW"))
            confidence = float(c.get("risk_confidence", 50.0))
            isolation_severity = float(c.get("isolation_severity", 0.0))
            component_increase = int(c.get("component_increase", 0))
            nodes_affected = int(c.get("nodes_affected", 0))
            edges_affected = int(c.get("edges_in_affected_components", 0))
            is_bridge = bool(c.get("is_bridge_edge", False))

            # Compute urgency and priority
            urgency = UrgencyEvaluator.calculate_urgency(risk_level, confidence)
            breakdown = PriorityScoringEngine.calculate_priority(
                risk_score=risk_score,
                isolation_severity=isolation_severity,
                urgency_score=urgency,
            )

            # Generate concise candidate explanation
            from app.services.priority.explanation import PriorityExplanationGenerator

            explanation = PriorityExplanationGenerator.generate_summary(
                priority_score=breakdown.priority_score,
                priority_level=breakdown.priority_level,
                risk_score=risk_score,
                isolation_severity=isolation_severity,
                urgency_score=urgency,
                is_bridge_edge=is_bridge,
                nodes_affected=nodes_affected,
            )

            evaluated_items.append({
                "candidate_id": candidate_id,
                "latitude": lat,
                "longitude": lon,
                "priority_score": breakdown.priority_score,
                "priority_level": breakdown.priority_level,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "risk_confidence": confidence,
                "isolation_severity": isolation_severity,
                "urgency_score": urgency,
                "is_bridge_edge": is_bridge,
                "nodes_affected": nodes_affected,
                "component_increase": component_increase,
                "edges_in_affected_components": edges_affected,
                "breakdown": breakdown,
                "explanation": explanation,
            })

        # Deterministic multi-tier sort:
        # 1. priority_score DESC (-x)
        # 2. isolation_severity DESC (-x)
        # 3. risk_score DESC (-x)
        # 4. risk_confidence DESC (-x)
        # 5. candidate_id ASC (string)
        evaluated_items.sort(
            key=lambda x: (
                -x["priority_score"],
                -x["isolation_severity"],
                -x["risk_score"],
                -x["risk_confidence"],
                x["candidate_id"],
            )
        )

        ranked_results: list[RankedCandidateItem] = []
        for idx, item in enumerate(evaluated_items, start=1):
            ranked_results.append(
                RankedCandidateItem(
                    rank=idx,
                    candidate_id=item["candidate_id"],
                    latitude=item["latitude"],
                    longitude=item["longitude"],
                    priority_score=item["priority_score"],
                    priority_level=item["priority_level"],
                    risk_score=item["risk_score"],
                    risk_level=item["risk_level"],
                    risk_confidence=item["risk_confidence"],
                    isolation_severity=item["isolation_severity"],
                    urgency_score=item["urgency_score"],
                    is_bridge_edge=item["is_bridge_edge"],
                    nodes_affected=item["nodes_affected"],
                    component_increase=item["component_increase"],
                    breakdown=item["breakdown"],
                    explanation=item["explanation"],
                )
            )

        return ranked_results
