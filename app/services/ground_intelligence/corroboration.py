"""
Corroboration engine evaluating convergence across independent field observers.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime
import uuid

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.models.ground_report import GroundReport
from app.services.ground_intelligence.constants import (
    COMPATIBLE_REPORT_TYPES,
    CORROBORATION_RADIUS_METERS,
    CORROBORATION_WINDOW_HOURS,
)


@dataclass
class CorroborationResult:
    """Outcome of multi-observer corroboration evaluation."""

    corroboration_score: float
    independent_report_count: int
    corroborating_report_ids: list[str]


class CorroborationEvaluator:
    """Evaluates spatial-temporal convergence from independent reporting sources."""

    @classmethod
    def evaluate_corroboration(
        cls,
        latitude: float,
        longitude: float,
        observed_at: datetime.datetime,
        report_type: str,
        user_id: uuid.UUID,
        db: Session | None = None,
        candidate_report_id: uuid.UUID | None = None,
    ) -> CorroborationResult:
        """Calculate corroboration score [0.0 - 100.0] from independent nearby observations."""
        if db is None:
            return CorroborationResult(
                corroboration_score=0.0,
                independent_report_count=0,
                corroborating_report_ids=[],
            )

        obs_tz = observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=datetime.timezone.utc)
        time_min = obs_tz - datetime.timedelta(hours=CORROBORATION_WINDOW_HOURS)
        time_max = obs_tz + datetime.timedelta(hours=CORROBORATION_WINDOW_HOURS)

        target_geom = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
        target_geog = cast(target_geom, Geography)

        compatible_types = COMPATIBLE_REPORT_TYPES.get(report_type, {report_type})

        # Query candidates: strictly different user, not a duplicate, not rejected
        query = (
            select(GroundReport)
            .where(
                func.ST_DWithin(
                    cast(GroundReport.geom, Geography),
                    target_geog,
                    CORROBORATION_RADIUS_METERS,
                ),
                GroundReport.observed_at >= time_min,
                GroundReport.observed_at <= time_max,
                GroundReport.user_id != user_id,
                GroundReport.is_duplicate.is_(False),
                GroundReport.status.notin_(["REJECTED", "DUPLICATE"]),
                GroundReport.report_type.in_(compatible_types),
            )
        )

        if candidate_report_id:
            query = query.where(GroundReport.id != candidate_report_id)

        candidates = db.execute(query).scalars().all()

        # Aggregate unique independent observers
        corroborating_ids: list[str] = []
        effective_weight = 0.0
        seen_users: set[uuid.UUID] = set()

        for cand in candidates:
            # Enforce at most 1 corroborating signal per independent user
            if cand.user_id in seen_users:
                continue
            seen_users.add(cand.user_id)
            corroborating_ids.append(str(cand.id))

            # Weight by report type compatibility
            weight = 1.0 if cand.report_type == report_type else 0.75
            effective_weight += weight

        # Map effective weight to 0-100 score
        if effective_weight <= 0.0:
            score = 0.0
        elif effective_weight < 1.0:
            score = 40.0
        elif effective_weight < 2.0:
            score = 50.0 + (effective_weight - 1.0) * 30.0  # 50.0 to 80.0
        elif effective_weight < 3.0:
            score = 80.0 + (effective_weight - 2.0) * 20.0  # 80.0 to 100.0
        else:
            score = 100.0

        score = round(max(0.0, min(100.0, score)), 2)
        return CorroborationResult(
            corroboration_score=score,
            independent_report_count=len(seen_users),
            corroborating_report_ids=corroborating_ids,
        )
