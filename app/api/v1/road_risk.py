"""
RISKSETU AI — Road Blockage Risk endpoint.

POST /api/v1/road-risk/evaluate

Combines LIVE_RISK_V1 (Phase 2A historical + live weather) with
Phase 2B connectivity simulation to produce a predicted blockage risk
score for a specific road segment.

IMPORTANT DISTINCTIONS:
  - predicted_risk_score: susceptibility estimate — NOT a confirmed event
  - closure_status: UNKNOWN — no live road-closure feed is integrated
  - traffic_status: unavailable — no live traffic provider
  - simulation_type: WHAT_IF — Phase 2B is non-destructive

No fabricated data, traffic, closure, terrain, or ML values are returned.
"""
from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import ValidationAppError
from app.db.session import get_db
from app.schemas.road_risk import RoadRiskEvaluationRequest, RoadRiskResponse
from app.services.road_risk.engine import RoadRiskEngine

logger = structlog.get_logger("risksetu.road_risk.api")

router = APIRouter(prefix="/road-risk", tags=["road-risk"])


def _validate_coordinates(lat: float, lon: float) -> None:
    errors: list[dict[str, Any]] = []
    if not (-90.0 <= lat <= 90.0):
        errors.append({"field": "latitude", "message": f"Latitude must be in [-90, 90]; got {lat}"})
    if not (-180.0 <= lon <= 180.0):
        errors.append({"field": "longitude", "message": f"Longitude must be in [-180, 180]; got {lon}"})
    if errors:
        raise ValidationAppError("Invalid coordinates for road risk evaluation.", details=errors)


@router.post("/evaluate", response_model=RoadRiskResponse)
async def evaluate_road_risk(
    request_body: RoadRiskEvaluationRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> RoadRiskResponse:
    """Evaluate predicted blockage risk for a road segment.

    Combines:
    - **Historical landslide risk** (Phase 2A certified deterministic engine)
    - **Live weather trigger** (Open-Meteo, cached 5 min)
    - **Phase 2B connectivity simulation** (what-if, non-destructive)

    The `blockage.predicted_risk_score` is a susceptibility estimate.
    `blockage.closure_status` is always `UNKNOWN` — no live closure feed.
    `blockage.traffic_status` is always `unavailable` — no traffic provider.
    The Phase 2B simulation is always `WHAT_IF`, not a confirmed event.

    **ML susceptibility and terrain are unavailable** and explicitly reported
    as such — no fabricated values are ever returned.
    """
    _validate_coordinates(request_body.latitude, request_body.longitude)

    req_id = getattr(request.state, "request_id", "")
    logger.info(
        "road_risk_request",
        lat=request_body.latitude,
        lon=request_body.longitude,
        request_id=req_id,
    )

    engine = RoadRiskEngine(db=db)
    assessment = await engine.assess(
        lat=request_body.latitude,
        lon=request_body.longitude,
        radius_m=request_body.radius_m,
        search_radius_m=request_body.search_radius_m,
        blocked_edge_id=request_body.blocked_edge_id,
    )

    return RoadRiskResponse(
        data=assessment,
        meta={"request_id": req_id},
    )
