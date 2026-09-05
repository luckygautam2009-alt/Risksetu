"""
Shelter discovery service.

DATA HONESTY:
  No verified shelter dataset is currently loaded.
  All queries will return data_status = "unavailable" until a real dataset
  is ingested.  No placeholder or fabricated shelter records are returned.
"""
from __future__ import annotations

from typing import Any

import structlog
from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.models.shelter import Shelter
from app.schemas.shelter import ShelterItem
from app.services.sos.constants import (
    SHELTER_MAX_RADIUS_M,
    SHELTER_MIN_RADIUS_M,
    SUITABILITY_MAX_DISTANCE_M,
    SUITABILITY_W_ACCESSIBILITY,
    SUITABILITY_W_CAPACITY,
    SUITABILITY_W_DISTANCE,
)

logger = structlog.get_logger("risksetu.sos.shelter_service")

_NO_DATASET_NOTE = (
    "No verified shelter dataset is currently loaded in this deployment. "
    "The shelter schema and query infrastructure are implemented and ready. "
    "Integration with NDMA / State DM Portal data is required before real "
    "shelter records can be returned."
)

_LIMITATIONS = [
    "No verified shelter dataset is loaded. Shelter queries return zero results.",
    "Shelter capacity and accessibility data will only be populated from authoritative sources.",
    "Road connectivity to shelters is derived from the OSM graph and indicates network "
    "connectivity, not a guaranteed safe or passable route.",
    "Suitability score excludes capacity and accessibility components until those fields "
    "are populated from verified sources.",
]


# ---------------------------------------------------------------------------
# Suitability scoring
# ---------------------------------------------------------------------------

def _distance_score(distance_m: float) -> float:
    """Linear decay from 100 (at 0 m) to 0 (at SUITABILITY_MAX_DISTANCE_M)."""
    if distance_m <= 0:
        return 100.0
    if distance_m >= SUITABILITY_MAX_DISTANCE_M:
        return 0.0
    return round(100.0 * (1.0 - distance_m / SUITABILITY_MAX_DISTANCE_M), 1)


def _capacity_score(capacity: int | None) -> float | None:
    if capacity is None:
        return None
    if capacity >= 200:
        return 100.0
    if capacity >= 50:
        return 75.0
    return 50.0


def _accessibility_score(is_accessible: bool | None) -> float | None:
    if is_accessible is None:
        return None
    return 100.0 if is_accessible else 30.0


def compute_suitability(
    distance_m: float,
    capacity: int | None,
    is_accessible: bool | None,
) -> tuple[float, dict[str, Any]]:
    """Deterministic suitability score with weight redistribution for missing data."""
    d_score = _distance_score(distance_m)
    c_score = _capacity_score(capacity)
    a_score = _accessibility_score(is_accessible)

    weights: dict[str, float] = {"distance": SUITABILITY_W_DISTANCE}
    scores: dict[str, float] = {"distance": d_score}

    if c_score is not None:
        weights["capacity"] = SUITABILITY_W_CAPACITY
        scores["capacity"] = c_score
    if a_score is not None:
        weights["accessibility"] = SUITABILITY_W_ACCESSIBILITY
        scores["accessibility"] = a_score

    total_w = sum(weights.values())
    if total_w <= 0:
        return 0.0, {}

    final = sum(scores[k] * weights[k] / total_w for k in weights)
    factors: dict[str, Any] = {
        "distance_m": round(distance_m, 1),
        "distance_score": d_score,
        "capacity_score": c_score,
        "accessibility_score": a_score,
        "weights_used": {k: round(weights[k] / total_w, 4) for k in weights},
        "capacity_available": c_score is not None,
        "accessibility_available": a_score is not None,
    }
    return round(final, 1), factors


# ---------------------------------------------------------------------------
# Connectivity note (conservative — never claims "safe route")
# ---------------------------------------------------------------------------

def _connectivity_note(db: Session, lat: float, lon: float) -> str:
    """Check OSM road edges near shelter. Returns conservative label only."""
    from app.models.road import RoadNetworkEdge

    try:
        target = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
        stmt = (
            select(func.count())
            .select_from(RoadNetworkEdge)
            .where(
                func.ST_DWithin(
                    cast(RoadNetworkEdge.geom, Geography),
                    cast(target, Geography),
                    5000.0,
                )
            )
        )
        count = db.execute(stmt).scalar() or 0
        return "connectivity_available" if count > 0 else "connectivity_uncertain"
    except Exception:  # noqa: BLE001
        return "route_assessment_unavailable"


# ---------------------------------------------------------------------------
# Public query functions
# ---------------------------------------------------------------------------

def has_shelter_data(db: Session) -> bool:
    """Return True if at least one active shelter record exists."""
    count = db.execute(
        select(func.count()).select_from(Shelter).where(Shelter.is_active.is_(True))
    ).scalar() or 0
    return count > 0


def get_nearby_shelters(
    db: Session,
    lat: float,
    lon: float,
    radius_m: float,
    limit: int = 10,
) -> tuple[str, str, list[ShelterItem]]:
    """
    Query PostGIS for shelters within radius_m of (lat, lon).

    Returns (data_status, note, list[ShelterItem]).
      data_status: "available" | "unavailable" | "empty"
    """
    radius_m = max(SHELTER_MIN_RADIUS_M, min(radius_m, SHELTER_MAX_RADIUS_M))

    if not has_shelter_data(db):
        return "unavailable", _NO_DATASET_NOTE, []

    target = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    dist_expr = func.ST_Distance(
        cast(Shelter.geom, Geography),
        cast(target, Geography),
    ).label("distance_m")

    stmt = (
        select(Shelter, dist_expr)
        .where(
            Shelter.is_active.is_(True),
            func.ST_DWithin(
                cast(Shelter.geom, Geography),
                cast(target, Geography),
                radius_m,
            ),
        )
        .order_by(dist_expr)
        .limit(limit)
    )

    rows = db.execute(stmt).all()
    if not rows:
        return (
            "empty",
            f"No active shelters found within {radius_m:.0f} m of the requested location.",
            [],
        )

    items: list[ShelterItem] = []
    for shelter, distance_m in rows:
        suitability, factors = compute_suitability(
            distance_m=distance_m,
            capacity=shelter.capacity_persons,
            is_accessible=shelter.is_accessible,
        )
        conn = _connectivity_note(db, shelter.latitude, shelter.longitude)
        items.append(
            ShelterItem(
                id=str(shelter.id),
                name=shelter.name,
                facility_type=shelter.facility_type,
                latitude=shelter.latitude,
                longitude=shelter.longitude,
                distance_m=round(distance_m, 1),
                capacity_persons=shelter.capacity_persons,
                is_accessible=shelter.is_accessible,
                accessibility_notes=shelter.accessibility_notes,
                district=shelter.district,
                state=shelter.state,
                data_source=shelter.data_source,
                last_verified_at=shelter.last_verified_at,
                suitability_score=suitability,
                suitability_factors=factors,
                connectivity_note=conn,
            )
        )

    return "available", "Verified shelter records found.", items
