"""
Central Risk Intelligence Engine Coordinator.
"""
from __future__ import annotations

from sqlalchemy.orm import Session
import structlog

from app.core.errors import ValidationAppError
from app.schemas.risk import RiskEvaluationData, RiskEvaluationRequest
from app.services.risk.constants import CALCULATION_VERSION
from app.services.risk.explanation import RiskExplanationGenerator
from app.services.risk.rainfall import RainfallRiskEvaluator
from app.services.risk.scoring import RiskScoringEngine
from app.services.risk.spatial import SpatialRiskEvaluator

logger = structlog.get_logger("risksetu.risk_engine")


class RiskEvaluationEngine:
    """Coordinator for deterministic, explainable spatial risk evaluation."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.spatial_evaluator = SpatialRiskEvaluator(db)
        self.rainfall_evaluator = RainfallRiskEvaluator(db)

    def evaluate(self, request: RiskEvaluationRequest) -> RiskEvaluationData:
        """Execute end-to-end spatial risk evaluation."""
        # 1. Validation check for rainfall parameters
        if request.observed_rainfall_mm is not None:
            if request.month is None:
                raise ValidationAppError(
                    "When observed_rainfall_mm is provided, month (1-12) must also be specified.",
                    details=[{"loc": ["body", "month"], "msg": "month is required when observed_rainfall_mm is provided"}],
                )

        logger.info(
            "evaluating_spatial_risk",
            latitude=request.latitude,
            longitude=request.longitude,
            subdivision_id=str(request.rainfall_subdivision_id) if request.rainfall_subdivision_id else None,
        )

        # 2. Evaluate Spatial Historical Evidence
        spatial_res = self.spatial_evaluator.evaluate(
            latitude=request.latitude,
            longitude=request.longitude,
        )

        # 3. Evaluate Rainfall Anomaly Evidence
        rainfall_res = self.rainfall_evaluator.evaluate(
            subdivision_id=request.rainfall_subdivision_id,
            observed_rainfall_mm=request.observed_rainfall_mm,
            month=request.month,
            year=request.year,
        )

        # 4. Compose Composite Score & Confidence
        score_comp = RiskScoringEngine.compose_score(
            spatial_res=spatial_res,
            rainfall_res=rainfall_res,
        )

        # 5. Generate Explanation & Limitations
        summary = RiskExplanationGenerator.generate_summary(
            risk_score=score_comp.risk_score,
            risk_level=score_comp.risk_level,
            factors=score_comp.factors,
            redistribution_note=score_comp.redistribution_note,
        )
        limitations = RiskExplanationGenerator.get_limitations()

        return RiskEvaluationData(
            risk_score=score_comp.risk_score,
            risk_level=score_comp.risk_level,
            confidence_score=score_comp.confidence_score,
            calculation_version=CALCULATION_VERSION,
            queried_location={"latitude": request.latitude, "longitude": request.longitude},
            factors=score_comp.factors,
            weight_redistributed=score_comp.weight_redistributed,
            summary_explanation=summary,
            limitations=limitations,
        )
