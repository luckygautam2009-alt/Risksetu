"""
Deduplication and near-duplicate detection service for field observations.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime
import re
import uuid

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.models.ground_report import GroundReport
from app.services.ground_intelligence.constants import (
    DUPLICATE_RADIUS_METERS,
    DUPLICATE_TEXT_SIMILARITY_THRESHOLD,
    DUPLICATE_WINDOW_HOURS,
)


@dataclass
class DeduplicationResult:
    """Outcome of duplicate evaluation for a ground observation."""

    is_duplicate: bool
    duplicate_of_id: uuid.UUID | None
    duplicate_group_id: str
    match_reason: str | None = None


class ReportDeduplicator:
    """Geospatial, temporal, and textual near-duplicate detection engine."""

    @staticmethod
    def calculate_text_similarity(text1: str, text2: str) -> float:
        """Calculate token-set Jaccard similarity between two text descriptions."""
        tokens1 = set(re.findall(r"\w+", text1.lower()))
        tokens2 = set(re.findall(r"\w+", text2.lower()))

        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1.intersection(tokens2))
        union = len(tokens1.union(tokens2))
        return intersection / union if union > 0 else 0.0

    @classmethod
    def evaluate_duplicate(
        cls,
        latitude: float,
        longitude: float,
        observed_at: datetime.datetime,
        report_type: str,
        description: str,
        user_id: uuid.UUID,
        db: Session | None = None,
        candidate_report_id: uuid.UUID | None = None,
    ) -> DeduplicationResult:
        """Scan existing reports for potential duplicates or repeated submissions."""
        default_group_id = str(candidate_report_id or uuid.uuid4())

        if db is None:
            return DeduplicationResult(
                is_duplicate=False,
                duplicate_of_id=None,
                duplicate_group_id=default_group_id,
            )

        obs_tz = observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=datetime.timezone.utc)
        time_min = obs_tz - datetime.timedelta(hours=DUPLICATE_WINDOW_HOURS)
        time_max = obs_tz + datetime.timedelta(hours=DUPLICATE_WINDOW_HOURS)

        target_geom = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
        target_geog = cast(target_geom, Geography)

        # Query candidates within duplicate spatial and temporal radius
        query = (
            select(GroundReport)
            .where(
                func.ST_DWithin(
                    cast(GroundReport.geom, Geography),
                    target_geog,
                    DUPLICATE_RADIUS_METERS,
                ),
                GroundReport.observed_at >= time_min,
                GroundReport.observed_at <= time_max,
                GroundReport.report_type == report_type,
            )
            .order_by(GroundReport.created_at.asc())
        )

        if candidate_report_id:
            query = query.where(GroundReport.id != candidate_report_id)

        candidates = db.execute(query).scalars().all()

        for cand in candidates:
            # Case 1: Same user submitting same hazard within window & radius -> duplicate
            if cand.user_id == user_id:
                group_id = cand.duplicate_group_id or str(cand.id)
                return DeduplicationResult(
                    is_duplicate=True,
                    duplicate_of_id=cand.id,
                    duplicate_group_id=group_id,
                    match_reason=f"Repeated submission by same user within {DUPLICATE_RADIUS_METERS:.0f}m and {DUPLICATE_WINDOW_HOURS:.0f}h.",
                )

            # Case 2: Different user with high textual description similarity
            sim = cls.calculate_text_similarity(description, cand.description)
            if sim >= DUPLICATE_TEXT_SIMILARITY_THRESHOLD:
                group_id = cand.duplicate_group_id or str(cand.id)
                return DeduplicationResult(
                    is_duplicate=True,
                    duplicate_of_id=cand.id,
                    duplicate_group_id=group_id,
                    match_reason=f"Near-duplicate text description ({sim:.1%} match) within {DUPLICATE_RADIUS_METERS:.0f}m.",
                )

        return DeduplicationResult(
            is_duplicate=False,
            duplicate_of_id=None,
            duplicate_group_id=default_group_id,
        )
