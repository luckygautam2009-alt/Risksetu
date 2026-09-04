"""
Spatial proximity and historical landslide density evaluator.

Uses PostGIS spatial indexing (GIST) and distance calculations to measure
historical landslide clusters and distance to the closest recorded mass movement.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.landslide import HistoricalLandslide
from app.services.risk.constants import (
    DENSITY_WEIGHT_INNER,
    DENSITY_WEIGHT_MID,
    DENSITY_WEIGHT_OUTER,
    RADIUS_INNER_METERS,
    RADIUS_MID_METERS,
    RADIUS_OUTER_METERS,
)


@dataclass
class SpatialEvidenceResult:
    score: float  # [0-100]
    count_within_5km: int
    count_within_10km: int
    count_within_25km: int
    distance_to_nearest_km: float | None
    closest_slide_no: str | None
    closest_slide_material: str | None
    closest_slide_movement: str | None
    dated_events_count: int
    undated_inventory_count: int
    evidence_dict: dict[str, Any]
    explanation: str


class SpatialRiskEvaluator:
    """Evaluates spatial landslide risk based on GSI historical inventory."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def evaluate(self, latitude: float, longitude: float) -> SpatialEvidenceResult:
        """Perform PostGIS spatial proximity and density queries around the queried point."""
        query_point_geom = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
        query_point_geog = func.ST_GeogFromWKB(func.ST_AsBinary(query_point_geom))

        # Query all historical landslides within outer radius (25 km = 25,000 meters)
        # Using ST_DWithin with geography for accurate metric calculations on Earth's ellipsoid
        stmt = (
            select(
                HistoricalLandslide.id,
                HistoricalLandslide.gsi_slide_no,
                HistoricalLandslide.material,
                HistoricalLandslide.movement_type,
                HistoricalLandslide.event_date,
                func.ST_Distance(
                    func.ST_GeogFromWKB(func.ST_AsBinary(HistoricalLandslide.geom)),
                    query_point_geog,
                ).label("distance_meters"),
            )
            .where(
                func.ST_DWithin(
                    func.ST_GeogFromWKB(func.ST_AsBinary(HistoricalLandslide.geom)),
                    query_point_geog,
                    RADIUS_OUTER_METERS,
                )
            )
            .order_by("distance_meters")
        )

        rows = self.db.execute(stmt).all()

        count_inner = 0
        count_mid = 0
        count_outer = 0
        dated_count = 0
        undated_count = 0

        distance_nearest_km: float | None = None
        closest_slide_no: str | None = None
        closest_material: str | None = None
        closest_movement: str | None = None

        if rows:
            nearest_row = rows[0]
            distance_nearest_km = round(nearest_row.distance_meters / 1000.0, 2)
            closest_slide_no = nearest_row.gsi_slide_no
            closest_material = nearest_row.material
            closest_movement = nearest_row.movement_type

            for r in rows:
                dist_m = r.distance_meters
                if dist_m <= RADIUS_INNER_METERS:
                    count_inner += 1
                elif dist_m <= RADIUS_MID_METERS:
                    count_mid += 1
                elif dist_m <= RADIUS_OUTER_METERS:
                    count_outer += 1

                if r.event_date is not None:
                    dated_count += 1
                else:
                    undated_count += 1

        total_within_25km = count_inner + count_mid + count_outer

        # Deterministic Score Formula:
        # 1. Density Component (up to 70 points):
        #    Inner (<=5km) count weighted 8.0 pts each
        #    Mid (5-10km) count weighted 3.0 pts each
        #    Outer (10-25km) count weighted 1.0 pt each
        density_score = min(
            70.0,
            (count_inner * 8.0 * DENSITY_WEIGHT_INNER)
            + (count_mid * 6.0 * DENSITY_WEIGHT_MID)
            + (count_outer * 5.0 * DENSITY_WEIGHT_OUTER),
        )

        # 2. Proximity Component (up to 30 points):
        #    Full 30 pts if distance = 0 km, tapering linearly to 0 pts at 25 km
        proximity_score = 0.0
        if distance_nearest_km is not None and distance_nearest_km <= 25.0:
            proximity_score = max(0.0, 30.0 * (1.0 - (distance_nearest_km / 25.0)))

        composite_score = round(min(100.0, density_score + proximity_score), 1)

        # Build qualitative explanation
        if total_within_25km == 0:
            explanation = (
                "No historical landslide events recorded within a 25 km radius in the GSI National Landslide Inventory."
            )
        elif count_inner >= 3:
            explanation = (
                f"High local concentration: {count_inner} historical landslides within 5 km "
                f"(closest at {distance_nearest_km} km, ID {closest_slide_no})."
            )
        elif count_inner >= 1:
            explanation = (
                f"Direct proximity: {count_inner} historical landslide within 5 km "
                f"(closest at {distance_nearest_km} km) and {total_within_25km} total within 25 km."
            )
        else:
            explanation = (
                f"Regional footprint: No landslides within 5 km, but {count_mid} within 10 km "
                f"and {total_within_25km} within 25 km (closest at {distance_nearest_km} km)."
            )

        evidence_dict = {
            "within_5km_count": count_inner,
            "within_10km_count": count_mid + count_inner,
            "within_25km_count": total_within_25km,
            "distance_to_nearest_km": distance_nearest_km,
            "closest_slide_id": closest_slide_no,
            "closest_slide_material": closest_material,
            "closest_slide_movement": closest_movement,
            "dated_events_count": dated_count,
            "undated_inventory_count": undated_count,
        }

        return SpatialEvidenceResult(
            score=composite_score,
            count_within_5km=count_inner,
            count_within_10km=count_mid + count_inner,
            count_within_25km=total_within_25km,
            distance_to_nearest_km=distance_nearest_km,
            closest_slide_no=closest_slide_no,
            closest_slide_material=closest_material,
            closest_slide_movement=closest_movement,
            dated_events_count=dated_count,
            undated_inventory_count=undated_count,
            evidence_dict=evidence_dict,
            explanation=explanation,
        )
