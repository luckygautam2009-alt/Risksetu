"""
RISKSETU AI — Current Live Area Risk endpoint.

GET /api/v1/live-risk?lat={lat}&lon={lon}

Combines certified Phase 2A deterministic historical risk with live
Open-Meteo weather context. ML and terrain are explicitly unavailable
and reported as such — no fabricated values are returned.
"""
from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.errors import ValidationAppError
from app.db.session import get_db
from app.schemas.live_risk import LiveRiskResponse
from app.services.live_risk.engine import LiveRiskEngine

logger = structlog.get_logger("risksetu.live_risk.api")

router = APIRouter(prefix="/live-risk", tags=["live-risk"])


def _validate_coordinates(lat: float, lon: float) -> None:
    errors: list[dict[str, Any]] = []
    if not (-90.0 <= lat <= 90.0):
        errors.append({"field": "lat", "message": f"Latitude must be in [-90, 90]; got {lat}"})
    if not (-180.0 <= lon <= 180.0):
        errors.append({"field": "lon", "message": f"Longitude must be in [-180, 180]; got {lon}"})
    if errors:
        raise ValidationAppError("Invalid coordinates for live risk assessment.", details=errors)


@router.get("", response_model=LiveRiskResponse)
async def get_live_risk(
    request: Request,
    lat: float = Query(..., description="Latitude in decimal degrees [-90, 90]"),
    lon: float = Query(..., description="Longitude in decimal degrees [-180, 180]"),
    db: Session = Depends(get_db),
) -> LiveRiskResponse:
    """Return a current operational risk assessment for the given coordinates.

    Combines:
    - **Historical risk** (Phase 2A certified deterministic engine — unchanged)
    - **Live weather** (Open-Meteo, cached 5 min)
    - **ML susceptibility** — explicitly unavailable (experimental artifact)
    - **Terrain** — explicitly unavailable (no validated DEM)

    Provider failures, missing data, and unavailable inputs are always reported
    explicitly. No fabricated values are ever returned.

    The `data.risk.score` incorporates the historical baseline plus a bounded
    live weather trigger adjustment (max ±15 points). Risk classification
    thresholds are identical to Phase 2A: LOW ≤24, MODERATE ≤49, HIGH ≤74,
    CRITICAL >74.
    """
    _validate_coordinates(lat, lon)
    req_id = getattr(request.state, "request_id", "")

    logger.info("live_risk_request", lat=lat, lon=lon, request_id=req_id)

    engine = LiveRiskEngine(db=db)
    assessment = await engine.assess(lat, lon)

    return LiveRiskResponse(
        data=assessment,
        meta={"request_id": req_id},
    )
