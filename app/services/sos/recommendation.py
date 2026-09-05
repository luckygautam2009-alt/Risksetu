"""
SOS recommendation service — combines live risk + nearby shelters.

Produces a deterministic, explainable recommendation:
  - current risk level at SOS location
  - ranked candidate shelters (by suitability)
  - road connectivity note per shelter
  - explicit limitations on unavailable data

DOES NOT:
  - claim safe routes (no routing engine)
  - fabricate shelter records
  - fabricate terrain, traffic, or closure data
"""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy.orm import Session

from app.schemas.shelter import (
    ShelterRecommendationItem,
    SOSRecommendationData,
)
from app.services.sos.constants import (
    MODULE_VERSION,
    SHELTER_DEFAULT_RADIUS_M,
)
from app.services.sos.service import get_sos_by_id
from app.services.sos.shelter_service import get_nearby_shelters, _LIMITATIONS

logger = structlog.get_logger("risksetu.sos.recommendation")

_BASE_LIMITATIONS = [
    "Shelter recommendations are based on distance and available verified data only.",
    "Road connectivity notes indicate OSM graph connectivity, not a guaranteed passable route.",
    "Capacity and accessibility scores are only populated from verified authoritative sources.",
    "Live risk context is computed at SOS creation time and may not reflect real-time changes.",
]


def get_sos_recommendations(
    db: Session,
    sos_id: uuid.UUID,
    radius_m: float = SHELTER_DEFAULT_RADIUS_M,
    max_results: int = 5,
) -> SOSRecommendationData:
    """
    Build a ranked shelter recommendation for a given SOS report.

    Ranking: suitability_score descending (higher = better candidate).
    Ties broken by distance ascending.
    """
    from app.core.errors import NotFoundError

    sos = get_sos_by_id(db, sos_id)
    if not sos:
        raise NotFoundError(f"SOS report '{sos_id}' not found.")

    shelter_status, shelter_note, shelters = get_nearby_shelters(
        db=db,
        lat=sos.latitude,
        lon=sos.longitude,
        radius_m=radius_m,
        limit=max_results * 2,  # fetch extra for re-ranking
    )

    # Sort by suitability_score desc, then distance asc
    sorted_shelters = sorted(
        shelters,
        key=lambda s: (-(s.suitability_score or 0.0), s.distance_m),
    )[:max_results]

    recommendations = [
        ShelterRecommendationItem(
            rank=i + 1,
            shelter=s,
            recommendation_reason=_build_reason(s),
        )
        for i, s in enumerate(sorted_shelters)
    ]

    limitations = list(_BASE_LIMITATIONS)
    if shelter_status == "unavailable":
        limitations = list(_LIMITATIONS)

    return SOSRecommendationData(
        sos_id=str(sos_id),
        query_lat=sos.latitude,
        query_lon=sos.longitude,
        risk_score=sos.live_risk_score,
        risk_level=sos.live_risk_level,
        risk_confidence=sos.live_risk_confidence,
        shelter_data_status=shelter_status,
        shelter_data_note=shelter_note,
        recommended_shelters=recommendations,
        limitations=limitations,
        engine_version=MODULE_VERSION,
    )


def _build_reason(shelter: object) -> str:  # type: ignore[type-arg]
    """
    Build a plain-language recommendation reason from observed data.
    Never claims unverified properties.
    """
    from app.schemas.shelter import ShelterItem
    s: ShelterItem = shelter  # type: ignore[assignment]

    parts: list[str] = []
    parts.append(f"Distance: {s.distance_m:.0f} m.")

    if s.suitability_score is not None:
        parts.append(f"Suitability score: {s.suitability_score:.0f}/100.")

    if s.capacity_persons is not None:
        parts.append(f"Capacity: {s.capacity_persons} persons (verified).")
    else:
        parts.append("Capacity: not in dataset.")

    if s.is_accessible is True:
        parts.append("Accessible: yes (verified).")
    elif s.is_accessible is False:
        parts.append("Accessible: no (verified).")
    else:
        parts.append("Accessibility: not in dataset.")

    if s.connectivity_note == "connectivity_available":
        parts.append("Road network connectivity available near shelter.")
    elif s.connectivity_note == "connectivity_uncertain":
        parts.append("Road network connectivity uncertain near shelter.")
    else:
        parts.append("Route assessment unavailable.")

    return " ".join(parts)
