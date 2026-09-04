"""
Ground Intelligence Engine Coordinator.

Coordinates validation, deduplication, spatial plausibility, time decay,
user reliability, corroboration, trust scoring, and automated risk eligibility.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime
from typing import Any
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session
import structlog

from app.core.errors import NotFoundError
from app.models.ground_report import GroundReport, GroundReportAudit
from app.schemas.ground_report import (
    GroundReportCreateRequest,
    GroundReportData,
    ReportStatus,
    ReportType,
    TrustBreakdown,
    TrustClass,
    TrustComponents,
)
from app.services.ground_intelligence.classification import TrustClassifier
from app.services.ground_intelligence.constants import (
    CALCULATION_VERSION,
    STANDARD_GROUND_INTELLIGENCE_LIMITATIONS,
    WEIGHT_CORROBORATION,
    WEIGHT_GEO,
    WEIGHT_TEMPORAL,
    WEIGHT_USER,
)
from app.services.ground_intelligence.corroboration import CorroborationEvaluator
from app.services.ground_intelligence.deduplication import ReportDeduplicator
from app.services.ground_intelligence.eligibility import RiskEligibilityEvaluator
from app.services.ground_intelligence.explanation import GroundIntelligenceExplanationGenerator
from app.services.ground_intelligence.geo_plausibility import GeoPlausibilityEvaluator
from app.services.ground_intelligence.time_decay import TimeDecayEvaluator
from app.services.ground_intelligence.trust import TrustScoreResult, TrustScoringEngine
from app.services.ground_intelligence.user_reliability import UserReliabilityEvaluator
from app.services.ground_intelligence.validation import GroundReportValidator

logger = structlog.get_logger("risksetu.ground_intelligence.engine")


@dataclass
class EvaluationPipelineResult:
    """Internal container for evaluated report fields."""

    report_id: uuid.UUID
    user_id: uuid.UUID
    report_type: ReportType
    description: str
    latitude: float
    longitude: float
    observed_at: datetime.datetime
    status: ReportStatus
    trust_result: TrustScoreResult
    trust_class: TrustClass
    is_duplicate: bool
    duplicate_of_id: uuid.UUID | None
    duplicate_group_id: str
    corroborating_count: int
    risk_influence_eligible: bool
    explanation: list[str]
    source_metadata: dict[str, Any] | None
    audit_metadata: dict[str, Any]


class GroundIntelligenceEngine:
    """Coordinator engine for ground report processing and trust evaluation."""

    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def submit_report(
        self,
        request: GroundReportCreateRequest,
        user_id: uuid.UUID,
        user_role: str = "citizen",
        report_id: uuid.UUID | None = None,
        idempotency_key: str | None = None,
    ) -> GroundReportData:
        """Process, score, and persist a new field observation report."""
        rid = report_id or uuid.uuid4()
        lat, lon = GroundReportValidator.validate_coordinates(request.latitude, request.longitude)
        obs_at = GroundReportValidator.validate_observation_time(request.observed_at)
        desc = GroundReportValidator.validate_description(request.description)

        # 1. Deduplication evaluation
        dedup_res = ReportDeduplicator.evaluate_duplicate(
            latitude=lat,
            longitude=lon,
            observed_at=obs_at,
            report_type=request.report_type.value,
            description=desc,
            user_id=user_id,
            db=self.db,
            candidate_report_id=rid,
        )

        initial_status = ReportStatus.DUPLICATE if dedup_res.is_duplicate else ReportStatus.SUBMITTED

        # 2. Geo-Plausibility Evaluation
        geo_score = GeoPlausibilityEvaluator.calculate_geo_plausibility(
            latitude=lat,
            longitude=lon,
            report_type=request.report_type.value,
            db=self.db,
        )

        # 3. Temporal Freshness Evaluation
        temporal_score = TimeDecayEvaluator.calculate_temporal_freshness(observed_at=obs_at)

        # 4. User Reliability Evaluation
        user_score = UserReliabilityEvaluator.calculate_reliability(
            user_id=user_id,
            db=self.db,
            role=user_role,
        )

        # 5. Corroboration Evaluation (strictly independent non-duplicates)
        corrob_res = CorroborationEvaluator.evaluate_corroboration(
            latitude=lat,
            longitude=lon,
            observed_at=obs_at,
            report_type=request.report_type.value,
            user_id=user_id,
            db=self.db,
            candidate_report_id=rid,
        )

        # 6. Composite Trust Calculation
        trust_res = TrustScoringEngine.calculate_trust(
            geo_plausibility=geo_score,
            temporal_freshness=temporal_score,
            user_reliability=user_score,
            corroboration=corrob_res.corroboration_score,
        )

        # 7. Trust Classification
        trust_class = TrustClassifier.classify(trust_res.trust_score)

        # 8. Automated Risk Influence Eligibility Policy
        eligible, disqualifications = RiskEligibilityEvaluator.is_eligible(
            trust_score=trust_res.trust_score,
            is_duplicate=dedup_res.is_duplicate,
            status=initial_status.value,
            observed_at=obs_at,
            geo_plausibility_score=geo_score,
        )

        # 9. Audit-Defensible Explanation
        explanation = GroundIntelligenceExplanationGenerator.generate_explanation(
            trust_result=trust_res,
            trust_class=trust_class,
            is_duplicate=dedup_res.is_duplicate,
            duplicate_match_reason=dedup_res.match_reason,
            corroborating_count=corrob_res.independent_report_count,
            risk_influence_eligible=eligible,
            eligibility_reasons=disqualifications,
        )

        audit_meta = {
            "calculation_version": CALCULATION_VERSION,
            "weights": {
                "geo": WEIGHT_GEO,
                "temporal": WEIGHT_TEMPORAL,
                "user": WEIGHT_USER,
                "corroboration": WEIGHT_CORROBORATION,
            },
            "corroborating_report_ids": corrob_res.corroborating_report_ids,
            "duplicate_match_reason": dedup_res.match_reason,
            "disqualifications": disqualifications,
        }

        # 10. Database Persistence
        now = datetime.datetime.now(datetime.timezone.utc)
        if self.db is not None:
            point_geom = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
            report_orm = GroundReport(
                id=rid,
                user_id=user_id,
                report_type=request.report_type.value,
                description=desc,
                latitude=lat,
                longitude=lon,
                geom=point_geom,
                observed_at=obs_at,
                status=initial_status.value,
                trust_score=trust_res.trust_score,
                trust_class=trust_class.value,
                geo_plausibility_score=geo_score,
                temporal_freshness_score=temporal_score,
                user_reliability_score=user_score,
                corroboration_score=corrob_res.corroboration_score,
                is_duplicate=dedup_res.is_duplicate,
                duplicate_of_id=dedup_res.duplicate_of_id,
                duplicate_group_id=dedup_res.duplicate_group_id,
                risk_influence_eligible=eligible,
                source_metadata=request.source_metadata,
                audit_metadata=audit_meta,
                idempotency_key=idempotency_key,
            )
            self.db.add(report_orm)

            # Audit record
            audit_orm = GroundReportAudit(
                report_id=rid,
                user_id=user_id,
                action="CREATED",
                previous_state=None,
                new_state={
                    "status": initial_status.value,
                    "trust_score": trust_res.trust_score,
                    "trust_class": trust_class.value,
                    "risk_influence_eligible": eligible,
                },
                reason="Initial observation submission and trust evaluation.",
            )
            self.db.add(audit_orm)
            self.db.commit()
            self.db.refresh(report_orm)

        logger.info(
            "ground_report_evaluated",
            report_id=str(rid),
            user_id=str(user_id),
            trust_score=trust_res.trust_score,
            trust_class=trust_class.value,
            eligible=eligible,
            is_duplicate=dedup_res.is_duplicate,
        )

        return GroundReportData(
            report_id=str(rid),
            user_id=str(user_id),
            report_type=request.report_type,
            description=desc,
            latitude=lat,
            longitude=lon,
            observed_at=obs_at,
            status=initial_status,
            trust=TrustBreakdown(
                trust_score=trust_res.trust_score,
                trust_class=trust_class,
                components=TrustComponents(
                    geo_plausibility=geo_score,
                    temporal_freshness=temporal_score,
                    user_reliability=user_score,
                    corroboration=corrob_res.corroboration_score,
                ),
                weights={
                    "geo": WEIGHT_GEO,
                    "temporal": WEIGHT_TEMPORAL,
                    "user": WEIGHT_USER,
                    "corroboration": WEIGHT_CORROBORATION,
                },
                calculation_version=CALCULATION_VERSION,
            ),
            is_duplicate=dedup_res.is_duplicate,
            duplicate_of_id=str(dedup_res.duplicate_of_id) if dedup_res.duplicate_of_id else None,
            duplicate_group_id=dedup_res.duplicate_group_id,
            risk_influence_eligible=eligible,
            explanation=explanation,
            limitations=STANDARD_GROUND_INTELLIGENCE_LIMITATIONS,
            created_at=now,
            updated_at=now,
        )

    def recalculate_trust(self, report_id: uuid.UUID) -> GroundReportData:
        """Recalculate deterministic trust score and corroboration for an existing report."""
        if self.db is None:
            raise NotFoundError(f"Database session unavailable to recalculate report {report_id}.")

        report = self.db.execute(select(GroundReport).where(GroundReport.id == report_id)).scalar_one_or_none()
        if not report:
            raise NotFoundError(f"Ground report {report_id} not found.")

        # Re-evaluate components
        geo_score = GeoPlausibilityEvaluator.calculate_geo_plausibility(
            latitude=report.latitude,
            longitude=report.longitude,
            report_type=report.report_type,
            db=self.db,
        )
        temporal_score = TimeDecayEvaluator.calculate_temporal_freshness(observed_at=report.observed_at)
        user_score = UserReliabilityEvaluator.calculate_reliability(user_id=report.user_id, db=self.db)
        corrob_res = CorroborationEvaluator.evaluate_corroboration(
            latitude=report.latitude,
            longitude=report.longitude,
            observed_at=report.observed_at,
            report_type=report.report_type,
            user_id=report.user_id,
            db=self.db,
            candidate_report_id=report.id,
        )

        trust_res = TrustScoringEngine.calculate_trust(
            geo_plausibility=geo_score,
            temporal_freshness=temporal_score,
            user_reliability=user_score,
            corroboration=corrob_res.corroboration_score,
        )
        trust_class = TrustClassifier.classify(trust_res.trust_score)

        eligible, disqualifications = RiskEligibilityEvaluator.is_eligible(
            trust_score=trust_res.trust_score,
            is_duplicate=report.is_duplicate,
            status=report.status,
            observed_at=report.observed_at,
            geo_plausibility_score=geo_score,
        )

        previous_trust = report.trust_score
        previous_status = report.status

        # Update ORM entity
        report.geo_plausibility_score = geo_score
        report.temporal_freshness_score = temporal_score
        report.user_reliability_score = user_score
        report.corroboration_score = corrob_res.corroboration_score
        report.trust_score = trust_res.trust_score
        report.trust_class = trust_class.value
        report.risk_influence_eligible = eligible

        audit_meta = report.audit_metadata or {}
        audit_meta.update({
            "calculation_version": CALCULATION_VERSION,
            "corroborating_report_ids": corrob_res.corroborating_report_ids,
            "recalculated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
        report.audit_metadata = audit_meta

        # Add audit entry
        audit = GroundReportAudit(
            report_id=report.id,
            user_id=report.user_id,
            action="TRUST_RECALCULATED",
            previous_state={"trust_score": previous_trust, "status": previous_status},
            new_state={"trust_score": trust_res.trust_score, "risk_influence_eligible": eligible},
            reason="Idempotent trust re-evaluation based on updated corroborating reports and time decay.",
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(report)

        explanation = GroundIntelligenceExplanationGenerator.generate_explanation(
            trust_result=trust_res,
            trust_class=trust_class,
            is_duplicate=report.is_duplicate,
            duplicate_match_reason=audit_meta.get("duplicate_match_reason"),
            corroborating_count=corrob_res.independent_report_count,
            risk_influence_eligible=eligible,
            eligibility_reasons=disqualifications,
        )

        return GroundReportData(
            report_id=str(report.id),
            user_id=str(report.user_id),
            report_type=ReportType(report.report_type),
            description=report.description,
            latitude=report.latitude,
            longitude=report.longitude,
            observed_at=report.observed_at,
            status=ReportStatus(report.status),
            trust=TrustBreakdown(
                trust_score=trust_res.trust_score,
                trust_class=trust_class,
                components=TrustComponents(
                    geo_plausibility=geo_score,
                    temporal_freshness=temporal_score,
                    user_reliability=user_score,
                    corroboration=corrob_res.corroboration_score,
                ),
                weights={
                    "geo": WEIGHT_GEO,
                    "temporal": WEIGHT_TEMPORAL,
                    "user": WEIGHT_USER,
                    "corroboration": WEIGHT_CORROBORATION,
                },
                calculation_version=CALCULATION_VERSION,
            ),
            is_duplicate=report.is_duplicate,
            duplicate_of_id=str(report.duplicate_of_id) if report.duplicate_of_id else None,
            duplicate_group_id=report.duplicate_group_id,
            risk_influence_eligible=eligible,
            explanation=explanation,
            limitations=STANDARD_GROUND_INTELLIGENCE_LIMITATIONS,
            created_at=report.created_at,
            updated_at=report.updated_at,
        )
