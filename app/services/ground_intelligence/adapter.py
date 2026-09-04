"""
Risk Intelligence Adapter for Ground Observations.

Provides a strictly gated boundary for exposing validated, trust-eligible
ground observations to the Phase 2A hazard risk intelligence engine.
All automated influence is guarded behind a disabled feature flag to
guarantee zero semantic drift or regression in certified risk scores.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime
import uuid

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session
import structlog

from app.models.ground_report import GroundReport

logger = structlog.get_logger("risksetu.ground_intelligence.adapter")

# Feature Flag: Explicitly DISABLED in Phase 3 to protect certified Phase 2A risk calculations
ENABLE_GROUND_REPORT_RISK_INFLUENCE: bool = False


@dataclass
class EligibleGroundReportSummary:
    """Read-only view of a trust-eligible ground observation."""

    report_id: uuid.UUID
    report_type: str
    latitude: float
    longitude: float
    distance_meters: float
    observed_at: datetime.datetime
    trust_score: float
    trust_class: str


class GroundIntelligenceRiskAdapter:
    """Adapter exposing ONLY verified risk-eligible ground intelligence."""

    @staticmethod
    def get_eligible_reports_in_radius(
        db: Session,
        latitude: float,
        longitude: float,
        radius_meters: float = 5000.0,
    ) -> list[EligibleGroundReportSummary]:
        """Retrieve active, trust-eligible reports within a spatial radius.

        Guarantees:
            - `risk_influence_eligible == True`
            - `status != 'REJECTED'` and `status != 'DUPLICATE'`
            - `is_duplicate == False`
        """
        target_geom = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
        target_geog = cast(target_geom, Geography)

        distance_expr = func.ST_Distance(cast(GroundReport.geom, Geography), target_geog)

        query = (
            select(GroundReport, distance_expr.label("distance_m"))
            .where(
                GroundReport.risk_influence_eligible.is_(True),
                GroundReport.status.notin_(["REJECTED", "DUPLICATE"]),
                GroundReport.is_duplicate.is_(False),
                func.ST_DWithin(cast(GroundReport.geom, Geography), target_geog, radius_meters),
            )
            .order_by(distance_expr.asc())
        )

        rows = db.execute(query).all()
        results: list[EligibleGroundReportSummary] = []
        for r, dist in rows:
            results.append(
                EligibleGroundReportSummary(
                    report_id=r.id,
                    report_type=r.report_type,
                    latitude=r.latitude,
                    longitude=r.longitude,
                    distance_meters=round(float(dist), 2),
                    observed_at=r.observed_at,
                    trust_score=r.trust_score,
                    trust_class=r.trust_class,
                )
            )

        logger.info(
            "eligible_ground_reports_queried",
            lat=latitude,
            lon=longitude,
            radius_m=radius_meters,
            eligible_count=len(results),
            feature_flag_active=ENABLE_GROUND_REPORT_RISK_INFLUENCE,
        )

        return results
