"""
Geo-plausibility evaluator for ground observation coordinates.
"""
from __future__ import annotations

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.models.landslide import HistoricalLandslide
from app.models.road import RoadNetworkEdge


class GeoPlausibilityEvaluator:
    """Evaluates spatial plausibility against authentic PostGIS datasets."""

    @staticmethod
    def calculate_geo_plausibility(
        latitude: float,
        longitude: float,
        report_type: str,
        db: Session | None = None,
    ) -> float:
        """Evaluate spatial plausibility [0.0 - 100.0] against road and historical landslide datasets."""
        # 1. Base terrestrial bounds check (India regional envelope)
        in_india_bounds = (6.0 <= latitude <= 38.0) and (68.0 <= longitude <= 98.0)
        base_score = 40.0 if in_india_bounds else 20.0

        if db is None:
            return round(base_score, 2)

        target_geom = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
        target_geog = cast(target_geom, Geography)

        # 2. Proximity to Historical Landslide Evidence (GSI catalog)
        # Check within 10km (high hazard context) and 25km (moderate hazard context)
        landslide_bonus = 0.0
        has_slide_10km = db.execute(
            select(HistoricalLandslide.id)
            .where(
                func.ST_DWithin(
                    cast(HistoricalLandslide.geom, Geography),
                    target_geog,
                    10000.0,
                )
            )
            .limit(1)
        ).scalar_one_or_none()

        if has_slide_10km is not None:
            landslide_bonus = 30.0
        else:
            has_slide_25km = db.execute(
                select(HistoricalLandslide.id)
                .where(
                    func.ST_DWithin(
                        cast(HistoricalLandslide.geom, Geography),
                        target_geog,
                        25000.0,
                    )
                )
                .limit(1)
            ).scalar_one_or_none()
            if has_slide_25km is not None:
                landslide_bonus = 15.0

        # 3. Proximity to Routable Transportation Infrastructure (OSM network)
        road_bonus = 0.0
        is_road_centric = report_type in ("ROAD_BLOCKAGE", "ROCKFALL", "DEBRIS", "CRACK")

        has_road_1km = db.execute(
            select(RoadNetworkEdge.id)
            .where(
                func.ST_DWithin(
                    cast(RoadNetworkEdge.geom, Geography),
                    target_geog,
                    1000.0,
                )
            )
            .limit(1)
        ).scalar_one_or_none()

        if has_road_1km is not None:
            road_bonus = 30.0
        else:
            has_road_5km = db.execute(
                select(RoadNetworkEdge.id)
                .where(
                    func.ST_DWithin(
                        cast(RoadNetworkEdge.geom, Geography),
                        target_geog,
                        5000.0,
                    )
                )
                .limit(1)
            ).scalar_one_or_none()
            if has_road_5km is not None:
                road_bonus = 15.0
            elif not is_road_centric and landslide_bonus > 0:
                # Off-road landslide / slope movement in active hazard terrain
                road_bonus = 15.0

        raw_score = base_score + landslide_bonus + road_bonus
        clamped = max(0.0, min(100.0, raw_score))
        return round(clamped, 2)
