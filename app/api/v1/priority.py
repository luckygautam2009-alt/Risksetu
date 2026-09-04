"""
Impact-Aware Intervention Priority API routes.

Provides endpoints for evaluating intervention priority scores (single candidate)
and deterministic ranking of multiple intervention candidates.
"""
from __future__ import annotations

from typing import Any
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
import structlog

from app.db.session import get_db
from app.schemas.priority import (
    PriorityBreakdownDetail,
    PriorityEvaluationData,
    PriorityEvaluationRequest,
    PriorityEvaluationResponse,
    PriorityRankingData,
    PriorityRankingRequest,
    PriorityRankingResponse,
    RankedCandidatePayload,
)
from app.services.priority.constants import CALCULATION_VERSION, STANDARD_PRIORITY_LIMITATIONS
from app.services.priority.engine import PriorityEvaluationEngine
from app.services.priority.ranking import PriorityRankingEngine

logger = structlog.get_logger("risksetu.priority_api")

router = APIRouter(prefix="/priority", tags=["priority"])


@router.post(
    "/evaluate",
    response_model=PriorityEvaluationResponse,
    summary="Evaluate intervention priority for a single location",
)
async def evaluate_priority(
    request_body: PriorityEvaluationRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> PriorityEvaluationResponse:
    """Evaluate impact-aware intervention priority for a single candidate scenario.

    Combines Phase 2A hazard risk, Phase 2B connectivity impact, and urgency
    heuristics into a deterministic composite priority score (0-100) with
    weighted contribution breakdown and audit-defensible explanation.

    If risk_score or isolation_severity are omitted, the engine will automatically
    orchestrate Phase 2A (risk evaluation) and Phase 2B (road isolation simulation)
    using the provided coordinates and the live PostgreSQL database.
    """
    engine = PriorityEvaluationEngine(db=db)
    result = engine.evaluate(
        candidate_id=request_body.candidate_id,
        latitude=request_body.latitude,
        longitude=request_body.longitude,
        risk_score=request_body.risk_score,
        risk_level=request_body.risk_level,
        risk_confidence=request_body.risk_confidence,
        isolation_severity=request_body.isolation_severity,
        component_increase=request_body.component_increase,
        nodes_affected=request_body.nodes_affected,
        edges_in_affected_components=request_body.edges_in_affected_components,
        is_bridge_edge=request_body.is_bridge_edge,
        radius_m=request_body.radius_m,
        search_radius_m=request_body.search_radius_m,
    )

    data_payload = PriorityEvaluationData(
        candidate_id=result.candidate_id,
        latitude=result.latitude,
        longitude=result.longitude,
        priority_score=result.priority_score,
        priority_level=result.priority_level,
        breakdown=PriorityBreakdownDetail(
            risk_contribution=result.breakdown.risk_contribution,
            impact_contribution=result.breakdown.impact_contribution,
            urgency_contribution=result.breakdown.urgency_contribution,
            priority_score=result.breakdown.priority_score,
            priority_level=result.breakdown.priority_level,
        ),
        risk_score=result.risk_score,
        risk_level=result.risk_level,
        risk_confidence=result.risk_confidence,
        isolation_severity=result.isolation_severity,
        component_increase=result.component_increase,
        nodes_affected=result.nodes_affected,
        edges_in_affected_components=result.edges_in_affected_components,
        is_bridge_edge=result.is_bridge_edge,
        urgency_score=result.urgency_score,
        calculation_version=result.calculation_version,
        explanation=result.explanation,
        limitations=result.limitations,
    )

    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return PriorityEvaluationResponse(
        data=data_payload,
        meta={"request_id": req_id},
    )


@router.post(
    "/rank",
    response_model=PriorityRankingResponse,
    summary="Rank multiple intervention candidates by priority",
)
async def rank_candidates(
    request_body: PriorityRankingRequest,
    request: Request,
) -> PriorityRankingResponse:
    """Deterministically rank multiple intervention candidates by composite priority score.

    Accepts a list of pre-evaluated candidates with risk and isolation metrics,
    computes urgency and composite priority for each, and returns them sorted
    with 5-tier deterministic tie-breaking:
        1. Priority Score (DESC)
        2. Isolation Severity (DESC)
        3. Risk Score (DESC)
        4. Risk Confidence (DESC)
        5. Candidate ID (ASC, lexicographic)

    This endpoint does NOT orchestrate Phase 2A/2B — all metrics must be pre-computed.
    """
    candidate_dicts: list[dict[str, Any]] = [
        c.model_dump() for c in request_body.candidates
    ]

    ranked_items = PriorityRankingEngine.rank_candidates(candidate_dicts)

    ranked_payloads = [
        RankedCandidatePayload(
            rank=item.rank,
            candidate_id=item.candidate_id,
            latitude=item.latitude,
            longitude=item.longitude,
            priority_score=item.priority_score,
            priority_level=item.priority_level,
            risk_score=item.risk_score,
            risk_level=item.risk_level,
            risk_confidence=item.risk_confidence,
            isolation_severity=item.isolation_severity,
            urgency_score=item.urgency_score,
            is_bridge_edge=item.is_bridge_edge,
            nodes_affected=item.nodes_affected,
            component_increase=item.component_increase,
            breakdown=PriorityBreakdownDetail(
                risk_contribution=item.breakdown.risk_contribution,
                impact_contribution=item.breakdown.impact_contribution,
                urgency_contribution=item.breakdown.urgency_contribution,
                priority_score=item.breakdown.priority_score,
                priority_level=item.breakdown.priority_level,
            ),
            explanation=item.explanation,
        )
        for item in ranked_items
    ]

    data_payload = PriorityRankingData(
        total_candidates=len(ranked_payloads),
        ranked_candidates=ranked_payloads,
        calculation_version=CALCULATION_VERSION,
        limitations=list(STANDARD_PRIORITY_LIMITATIONS),
    )

    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return PriorityRankingResponse(
        data=data_payload,
        meta={"request_id": req_id},
    )
