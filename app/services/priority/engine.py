"""
Intervention Priority Evaluation Engine Coordinator.

Coordinates hazard risk (Phase 2A) and connectivity impact (Phase 2B) outputs
to calculate impact-aware intervention priority scores, contribution breakdowns,
and audit-defensible explanations.
"""
from __future__ import annotations

from dataclasses import dataclass
import uuid

from sqlalchemy.orm import Session
import structlog

from app.schemas.risk import RiskEvaluationRequest
from app.services.graph.builder import RoadGraphBuilder
from app.services.impact.isolation import RoadIsolationSimulator
from app.services.priority.constants import CALCULATION_VERSION, STANDARD_PRIORITY_LIMITATIONS
from app.services.priority.explanation import PriorityExplanationGenerator
from app.services.priority.scoring import PriorityBreakdown, PriorityScoringEngine
from app.services.priority.urgency import UrgencyEvaluator
from app.services.risk.engine import RiskEvaluationEngine

logger = structlog.get_logger("risksetu.priority_engine")


@dataclass
class PriorityEvaluationResult:
    """Complete result of an intervention priority evaluation."""

    candidate_id: str
    latitude: float
    longitude: float
    priority_score: float
    priority_level: str
    breakdown: PriorityBreakdown
    risk_score: float
    risk_level: str
    risk_confidence: float
    isolation_severity: float
    component_increase: int
    nodes_affected: int
    edges_in_affected_components: int
    is_bridge_edge: bool
    urgency_score: float
    calculation_version: str
    explanation: str
    limitations: list[str]


class PriorityEvaluationEngine:
    """Coordinates risk and impact intelligence to evaluate intervention priority."""

    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def evaluate(
        self,
        candidate_id: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        risk_score: float | None = None,
        risk_level: str | None = None,
        risk_confidence: float | None = None,
        isolation_severity: float | None = None,
        component_increase: int = 0,
        nodes_affected: int = 0,
        edges_in_affected_components: int = 0,
        is_bridge_edge: bool = False,
        radius_m: float = 3000.0,
        search_radius_m: float = 1000.0,
    ) -> PriorityEvaluationResult:
        """Evaluate intervention priority score for a scenario.

        If risk or isolation metrics are omitted and DB session is present, automatically
        orchestrates Phase 2A and Phase 2B engines to retrieve live ground-truth values.
        """
        cid = candidate_id or f"cand_{uuid.uuid4().hex[:8]}"
        lat = latitude if latitude is not None else 0.0
        lon = longitude if longitude is not None else 0.0

        # 1. Resolve Hazard Risk metrics (Phase 2A composition)
        if risk_score is None and self.db is not None and latitude is not None and longitude is not None:
            logger.info("orchestrating_phase_2a_risk", lat=latitude, lon=longitude)
            risk_engine = RiskEvaluationEngine(self.db)
            risk_res = risk_engine.evaluate(RiskEvaluationRequest(latitude=latitude, longitude=longitude))
            risk_score = risk_res.risk_score
            risk_level = risk_res.risk_level
            risk_confidence = risk_res.confidence_score
        else:
            risk_score = risk_score if risk_score is not None else 0.0
            risk_level = risk_level if risk_level is not None else "LOW"
            risk_confidence = risk_confidence if risk_confidence is not None else 50.0

        # 2. Resolve Connectivity Impact metrics (Phase 2B composition)
        if isolation_severity is None and self.db is not None and latitude is not None and longitude is not None:
            logger.info("orchestrating_phase_2b_impact", lat=latitude, lon=longitude)
            builder = RoadGraphBuilder(self.db)
            edge_match = builder.find_nearest_edge(latitude, longitude, search_radius_m=search_radius_m)
            if edge_match:
                G = builder.build_local_subgraph(latitude, longitude, radius_m=radius_m)
                u = edge_match["from_node_id"]
                v = edge_match["to_node_id"]
                key = edge_match.get("edge_db_id")
                if key is not None and not G.has_edge(u, v, key=key):
                    G.add_edge(u, v, key=key, **edge_match)
                sim_res = RoadIsolationSimulator.simulate_blockage(
                    G, [(u, v, key) if key else (u, v)], subgraph_radius_m=radius_m
                )
                isolation_severity = sim_res.isolation_severity
                component_increase = sim_res.component_increase
                nodes_affected = sim_res.nodes_affected
                edges_in_affected_components = sim_res.edges_in_affected_components
                is_bridge_edge = sim_res.is_bridge_edge
            else:
                isolation_severity = 0.0
        else:
            isolation_severity = isolation_severity if isolation_severity is not None else 0.0

        # 3. Calculate Urgency Score
        urgency = UrgencyEvaluator.calculate_urgency(risk_level, risk_confidence)

        # 4. Calculate Priority Score & Component Breakdown
        breakdown = PriorityScoringEngine.calculate_priority(
            risk_score=risk_score,
            isolation_severity=isolation_severity,
            urgency_score=urgency,
        )

        # 5. Generate Audit-Defensible Explanation
        explanation = PriorityExplanationGenerator.generate_summary(
            priority_score=breakdown.priority_score,
            priority_level=breakdown.priority_level,
            risk_score=risk_score,
            isolation_severity=isolation_severity,
            urgency_score=urgency,
            is_bridge_edge=is_bridge_edge,
            nodes_affected=nodes_affected,
        )

        return PriorityEvaluationResult(
            candidate_id=cid,
            latitude=lat,
            longitude=lon,
            priority_score=breakdown.priority_score,
            priority_level=breakdown.priority_level,
            breakdown=breakdown,
            risk_score=risk_score,
            risk_level=risk_level,
            risk_confidence=risk_confidence,
            isolation_severity=isolation_severity,
            component_increase=component_increase,
            nodes_affected=nodes_affected,
            edges_in_affected_components=edges_in_affected_components,
            is_bridge_edge=is_bridge_edge,
            urgency_score=urgency,
            calculation_version=CALCULATION_VERSION,
            explanation=explanation,
            limitations=list(STANDARD_PRIORITY_LIMITATIONS),
        )
