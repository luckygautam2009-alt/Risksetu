"""
Spatial risk evaluation API routes.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.risk import RiskEvaluationRequest, RiskEvaluationResponse
from app.services.risk.engine import RiskEvaluationEngine

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/evaluate", response_model=RiskEvaluationResponse)
async def evaluate_risk(
    request_body: RiskEvaluationRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> RiskEvaluationResponse:
    """Evaluate explainable spatial landslide risk for a target coordinate.

    Combines GSI historical landslide spatial density/proximity evidence and
    IMD historical rainfall climatological anomaly calculations.
    """
    engine = RiskEvaluationEngine(db)
    result_data = engine.evaluate(request_body)

    req_id = getattr(request.state, "request_id", "")
    return RiskEvaluationResponse(
        data=result_data,
        meta={"request_id": req_id},
    )
