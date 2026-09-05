"""
RISKSETU AI — LIVE_RISK_V1 orchestration engine.

Architecture:
  ┌─────────────────────────────────────────────────────────────────┐
  │                       LiveRiskEngine                           │
  │                                                                 │
  │  Input: (lat, lon, db_session)                                  │
  │                                                                 │
  │  1. Call Phase 2A RiskEvaluationEngine (certified, unchanged)   │
  │     → historical risk score [0-100], level, confidence         │
  │                                                                 │
  │  2. Call WeatherService (Open-Meteo, cached)                    │
  │     → live precipitation, humidity, weather code, forecast     │
  │                                                                 │
  │  3. Check ML status (probe artifact metadata)                   │
  │     → currently UNAVAILABLE (experimental artifact)            │
  │                                                                 │
  │  4. Check terrain status                                        │
  │     → currently UNAVAILABLE (no validated DEM)                 │
  │                                                                 │
  │  5. Compute weather trigger adjustment                          │
  │     Adjustment = f(live precipitation, humidity)                │
  │     Bounded: max ±WEATHER_TRIGGER_CAP_POINTS (15 pts)           │
  │     NOT applied when weather is unavailable.                    │
  │     Does NOT re-use historical rainfall signal.                 │
  │                                                                 │
  │  6. Compute final score                                         │
  │     final_score = clamp(historical_score + trigger_adj, 0, 100) │
  │                                                                 │
  │  7. Compute confidence                                          │
  │     Weighted by input availability + weather freshness          │
  │                                                                 │
  │  8. Build contributing factors (only from actual observations)  │
  │                                                                 │
  │  9. Build recommended actions (from final level + factors)      │
  │                                                                 │
  │ 10. Return LiveRiskData                                         │
  └─────────────────────────────────────────────────────────────────┘

DOUBLE-COUNTING PREVENTION:
  The Phase 2A engine uses IMD historical monthly climatology to compute
  a rainfall anomaly score. This is a BASELINE measure over 117 years.
  The live weather adjustment uses CURRENT hourly precipitation — a completely
  different signal that answers "is it raining right now?"
  These are orthogonal signals. The adjustment is additive and capped at
  15 points to prevent any single-factor dominance.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.schemas.live_risk import (
    ContributingFactor,
    DataFreshness,
    HistoricalRiskLayer,
    LiveRiskData,
    LiveRiskLocation,
    LiveRiskSummary,
    MLLayer,
    RecommendedAction,
    TerrainLayer,
    WeatherLayer,
)
from app.schemas.risk import RiskEvaluationData, RiskEvaluationRequest
from app.services.live_risk.constants import (
    CONF_DATA_LIMITED_MAX,
    CONF_WEIGHT_HISTORICAL,
    CONF_WEIGHT_ML,
    CONF_WEIGHT_TERRAIN,
    CONF_WEIGHT_WEATHER,
    ENGINE_VERSION,
    HUMIDITY_ADJUSTMENT,
    HUMIDITY_HIGH_THRESHOLD_PCT,
    PRECIP_EXTREME_ADJUSTMENT,
    PRECIP_EXTREME_MM_PER_H,
    PRECIP_HIGH_ADJUSTMENT,
    PRECIP_HIGH_MM_PER_H,
    PRECIP_MODERATE_ADJUSTMENT,
    PRECIP_MODERATE_MM_PER_H,
    RISK_LEVEL_HIGH_MAX,
    RISK_LEVEL_LOW_MAX,
    RISK_LEVEL_MODERATE_MAX,
    WEATHER_CONFIDENCE_PENALTY_PER_S,
    WEATHER_STALE_THRESHOLD_S,
    WEATHER_TRIGGER_CAP_POINTS,
)
from app.services.live_risk.ml_status import get_ml_status
from app.services.risk.engine import RiskEvaluationEngine
from app.services.weather.schemas import ProviderStatus, WeatherResponse
from app.services.weather.service import WeatherService

logger = structlog.get_logger("risksetu.live_risk.engine")


# ---------------------------------------------------------------------------
# Terrain status — always unavailable until DEM integration
# ---------------------------------------------------------------------------

_TERRAIN_UNAVAILABLE_REASON = (
    "No validated DEM-derived terrain data (elevation, slope, aspect, curvature) "
    "is available in the current deployment. Terrain integration is scheduled "
    "for a future phase after Bhoonidhi/CartoDEM raster ingestion."
)


def _determine_risk_level(score: float) -> str:
    """Mirror Phase 2A thresholds exactly — no deviation."""
    if score <= RISK_LEVEL_LOW_MAX:
        return "LOW"
    elif score <= RISK_LEVEL_MODERATE_MAX:
        return "MODERATE"
    elif score <= RISK_LEVEL_HIGH_MAX:
        return "HIGH"
    return "CRITICAL"


# ---------------------------------------------------------------------------
# Weather trigger adjustment
# ---------------------------------------------------------------------------

def _compute_weather_trigger_adjustment(
    precipitation_mm: float,
    humidity_pct: float,
) -> tuple[float, list[ContributingFactor]]:
    """Compute bounded live weather trigger adjustment.

    Rationale:
      The Phase 2A engine uses historical IMD climatology (monthly means and
      standard deviations over 1901–2017) to evaluate anomaly.  The live
      precipitation signal is CURRENT (hourly observation) — a different,
      orthogonal signal.

      Trigger tiers (IMD rainfall intensity classification):
        ≥ 35.5 mm/h (very heavy) → +15 pts (capped)
        ≥  7.5 mm/h (heavy)      → +10 pts
        ≥  2.5 mm/h (moderate)   → + 5 pts
        < 2.5 mm/h               → + 0 pts

      High humidity (≥ 80%) adds +3 pts as a soil saturation proxy.

    Returns:
        (adjustment_points, list_of_contributing_factors)
    """
    adjustment = 0.0
    factors: list[ContributingFactor] = []

    # Precipitation tier
    if precipitation_mm >= PRECIP_EXTREME_MM_PER_H:
        adjustment += PRECIP_EXTREME_ADJUSTMENT
        factors.append(ContributingFactor(
            factor="live_precipitation_extreme",
            description=(
                f"Current precipitation {precipitation_mm:.1f} mm/h exceeds IMD very-heavy "
                f"threshold ({PRECIP_EXTREME_MM_PER_H} mm/h). Extreme rainfall trigger active."
            ),
            value=precipitation_mm,
            source="weather",
        ))
    elif precipitation_mm >= PRECIP_HIGH_MM_PER_H:
        adjustment += PRECIP_HIGH_ADJUSTMENT
        factors.append(ContributingFactor(
            factor="live_precipitation_heavy",
            description=(
                f"Current precipitation {precipitation_mm:.1f} mm/h exceeds IMD heavy "
                f"threshold ({PRECIP_HIGH_MM_PER_H} mm/h)."
            ),
            value=precipitation_mm,
            source="weather",
        ))
    elif precipitation_mm >= PRECIP_MODERATE_MM_PER_H:
        adjustment += PRECIP_MODERATE_ADJUSTMENT
        factors.append(ContributingFactor(
            factor="live_precipitation_moderate",
            description=(
                f"Current precipitation {precipitation_mm:.1f} mm/h is in the moderate "
                f"range ({PRECIP_MODERATE_MM_PER_H}–{PRECIP_HIGH_MM_PER_H} mm/h)."
            ),
            value=precipitation_mm,
            source="weather",
        ))

    # Humidity proxy for antecedent saturation
    if humidity_pct >= HUMIDITY_HIGH_THRESHOLD_PCT:
        adjustment += HUMIDITY_ADJUSTMENT
        factors.append(ContributingFactor(
            factor="high_relative_humidity",
            description=(
                f"Relative humidity {humidity_pct:.0f}% ≥ {HUMIDITY_HIGH_THRESHOLD_PCT}%. "
                "High humidity is a proxy for antecedent soil moisture saturation."
            ),
            value=humidity_pct,
            source="weather",
        ))

    # Apply cap
    adjustment = min(adjustment, WEATHER_TRIGGER_CAP_POINTS)
    return adjustment, factors


# ---------------------------------------------------------------------------
# Confidence calculation
# ---------------------------------------------------------------------------

def _compute_confidence(
    historical_available: bool,
    historical_confidence: float,
    weather_available: bool,
    weather_freshness_seconds: int,
    ml_available: bool,
    terrain_available: bool,
) -> float:
    """Weighted confidence score [0-100].

    Components:
      historical (60%): passes through Phase 2A confidence if available;
                        0 if unavailable.
      weather    (25%): full if available and fresh; reduced for stale data.
      ml         (10%): reserved; 0 until validated model exists.
      terrain    ( 5%): reserved; 0 until DEM integration.

    If no inputs are available, caps at CONF_DATA_LIMITED_MAX (30) to
    signal that the assessment is data-limited.
    """
    if not historical_available and not weather_available:
        return CONF_DATA_LIMITED_MAX

    hist_contrib = 0.0
    if historical_available:
        hist_contrib = historical_confidence * CONF_WEIGHT_HISTORICAL

    weather_contrib = 0.0
    if weather_available:
        weather_contrib = 100.0 * CONF_WEIGHT_WEATHER
        # Apply freshness penalty for stale data
        stale_seconds = max(0, weather_freshness_seconds - WEATHER_STALE_THRESHOLD_S)
        penalty = stale_seconds * WEATHER_CONFIDENCE_PENALTY_PER_S
        weather_contrib = max(0.0, weather_contrib - penalty)

    ml_contrib = 100.0 * CONF_WEIGHT_ML if ml_available else 0.0
    terrain_contrib = 100.0 * CONF_WEIGHT_TERRAIN if terrain_available else 0.0

    total = hist_contrib + weather_contrib + ml_contrib + terrain_contrib
    return round(max(0.0, min(100.0, total)), 1)


# ---------------------------------------------------------------------------
# Recommended actions
# ---------------------------------------------------------------------------

_BASE_ACTIONS: dict[str, list[dict[str, str]]] = {
    "LOW": [
        {"action_id": "MONITOR_ROUTINE", "description": "Continue routine monitoring.", "priority": "low"},
    ],
    "MODERATE": [
        {"action_id": "MONITOR_INCREASED", "description": "Increase monitoring frequency.", "priority": "moderate"},
        {"action_id": "REVIEW_VULNERABLE", "description": "Review vulnerable locations and access routes.", "priority": "moderate"},
    ],
    "HIGH": [
        {"action_id": "INSPECT_CORRIDORS", "description": "Inspect vulnerable road corridors for signs of instability.", "priority": "high"},
        {"action_id": "PREP_RESOURCES", "description": "Prepare emergency response resources for rapid deployment.", "priority": "high"},
        {"action_id": "MONITOR_ROADS", "description": "Monitor critical road connectivity and bridge points.", "priority": "high"},
    ],
    "CRITICAL": [
        {"action_id": "INITIATE_MONITORING", "description": "Initiate continuous operational monitoring.", "priority": "immediate"},
        {"action_id": "INSPECT_INFRASTRUCTURE", "description": "Inspect critical infrastructure (bridges, culverts, cuttings).", "priority": "immediate"},
        {"action_id": "PREP_EMERGENCY", "description": "Prepare emergency response and coordination.", "priority": "immediate"},
        {"action_id": "WARN_VULNERABLE", "description": "Consider issuing advisories to vulnerable communities.", "priority": "immediate"},
    ],
}

_WEATHER_ACTIONS: dict[str, dict[str, str]] = {
    "live_precipitation_extreme": {
        "action_id": "ACTIVE_RAINFALL_EXTREME",
        "description": "Active extreme rainfall event detected. Heighten monitoring; assess evacuation routes.",
        "priority": "immediate",
    },
    "live_precipitation_heavy": {
        "action_id": "ACTIVE_RAINFALL_HEAVY",
        "description": "Active heavy rainfall event. Monitor slope drainage and road conditions.",
        "priority": "high",
    },
    "live_precipitation_moderate": {
        "action_id": "ACTIVE_RAINFALL_MODERATE",
        "description": "Active moderate rainfall. Review conditions in known susceptible zones.",
        "priority": "moderate",
    },
}


def _build_recommended_actions(
    final_level: str,
    contributing_factors: list[ContributingFactor],
) -> list[RecommendedAction]:
    actions: list[RecommendedAction] = []
    seen_ids: set[str] = set()

    for a in _BASE_ACTIONS.get(final_level, []):
        if a["action_id"] not in seen_ids:
            actions.append(RecommendedAction(**a))  # type: ignore[arg-type]
            seen_ids.add(a["action_id"])

    # Add weather-specific actions for observed precipitation factors
    for factor in contributing_factors:
        if factor.factor in _WEATHER_ACTIONS:
            action_dict = _WEATHER_ACTIONS[factor.factor]
            if action_dict["action_id"] not in seen_ids:
                actions.append(RecommendedAction(**action_dict))  # type: ignore[arg-type]
                seen_ids.add(action_dict["action_id"])

    return actions


# ---------------------------------------------------------------------------
# Helper: build layers from raw outputs
# ---------------------------------------------------------------------------

def _build_historical_layer(hist: RiskEvaluationData | None, error: str | None) -> HistoricalRiskLayer:
    if hist is None:
        return HistoricalRiskLayer(
            status="unavailable" if error is None else "error",
            score=None, level=None, confidence=None,
            calculation_version=None, factors=[], weight_redistributed=False,
            summary=error or "Historical risk data unavailable.", limitations=[],
        )
    return HistoricalRiskLayer(
        status="available",
        score=hist.risk_score,
        level=hist.risk_level,
        confidence=hist.confidence_score,
        calculation_version=hist.calculation_version,
        factors=[f.model_dump() for f in hist.factors],
        weight_redistributed=hist.weight_redistributed,
        summary=hist.summary_explanation,
        limitations=hist.limitations,
    )


def _build_weather_layer(weather: WeatherResponse | None) -> WeatherLayer:
    if weather is None:
        return WeatherLayer(
            status="unavailable",
            error_message="Weather service returned no data.",
        )

    status_map = {
        ProviderStatus.OK: "available",
        ProviderStatus.CACHED: "cached",
        ProviderStatus.UNAVAILABLE: "unavailable",
        ProviderStatus.TIMEOUT: "timeout",
        ProviderStatus.PROVIDER_ERROR: "provider_error",
    }
    layer_status = status_map.get(weather.provider_status, "unavailable")

    if weather.current is None:
        return WeatherLayer(
            status=layer_status,
            provider=weather.provider,
            fetched_at=weather.fetched_at,
            freshness_seconds=weather.data_freshness_seconds,
            error_message=weather.error_message,
        )

    return WeatherLayer(
        status=layer_status,
        provider=weather.provider,
        precipitation_mm=weather.current.precipitation_mm,
        temperature_c=weather.current.temperature_c,
        humidity_pct=weather.current.relative_humidity_pct,
        wind_speed_kmh=weather.current.wind_speed_kmh,
        weather_code=weather.current.weather_code,
        description=weather.current.weather_description,
        observation_time=weather.current.timestamp,
        fetched_at=weather.fetched_at,
        freshness_seconds=weather.data_freshness_seconds,
        forecast_3day_precip_mm=[d.precipitation_sum_mm for d in weather.forecast],
        error_message=weather.error_message,
    )


# ---------------------------------------------------------------------------
# Main orchestration engine
# ---------------------------------------------------------------------------

class LiveRiskEngine:
    """LIVE_RISK_V1 orchestration engine.

    Combines Phase 2A certified historical risk with live weather context.
    Does not modify or replicate any certified component.
    """

    def __init__(
        self,
        db: Session,
        weather_service: WeatherService | None = None,
    ) -> None:
        self._db = db
        self._weather_service = weather_service or WeatherService()
        self._risk_engine = RiskEvaluationEngine(db)

    async def assess(self, lat: float, lon: float) -> LiveRiskData:
        """Perform a full LIVE_RISK_V1 assessment for the given coordinate."""
        now = datetime.now(timezone.utc)
        logger.info("live_risk_assessment_start", lat=lat, lon=lon)

        # ── 1. Historical risk (certified Phase 2A, sync call in executor) ───
        hist_data: RiskEvaluationData | None = None
        hist_error: str | None = None
        try:
            loop = asyncio.get_event_loop()
            request = RiskEvaluationRequest(latitude=lat, longitude=lon)
            hist_data = await loop.run_in_executor(
                None, self._risk_engine.evaluate, request
            )
        except Exception as exc:  # noqa: BLE001
            hist_error = f"Historical risk engine error: {type(exc).__name__}"
            logger.warning("live_risk_historical_error", lat=lat, lon=lon, error=str(exc))

        historical_layer = _build_historical_layer(hist_data, hist_error)

        # ── 2. Live weather (async, already cached) ────────────────────────
        weather_resp: WeatherResponse | None = None
        try:
            weather_resp = await self._weather_service.get_weather(lat, lon)
        except Exception as exc:  # noqa: BLE001
            logger.warning("live_risk_weather_error", lat=lat, lon=lon, error=str(exc))

        weather_layer = _build_weather_layer(weather_resp)

        # ── 3. ML status ───────────────────────────────────────────────────
        ml_info = get_ml_status()
        ml_layer = MLLayer(
            status=ml_info.get("status") or "unavailable",
            susceptibility_score=None,
            model_version=ml_info.get("model_version"),
            reason=ml_info.get("reason"),
        )

        # ── 4. Terrain status ──────────────────────────────────────────────
        terrain_layer = TerrainLayer(
            status="unavailable",
            reason=_TERRAIN_UNAVAILABLE_REASON,
        )

        # ── 5. Weather trigger adjustment ─────────────────────────────────
        weather_available = weather_layer.status in ("available", "cached")
        trigger_adjustment = 0.0
        weather_factors: list[ContributingFactor] = []

        if weather_available and weather_layer.precipitation_mm is not None:
            trigger_adjustment, weather_factors = _compute_weather_trigger_adjustment(
                precipitation_mm=weather_layer.precipitation_mm,
                humidity_pct=weather_layer.humidity_pct or 0.0,
            )

        # ── 6. Final score ─────────────────────────────────────────────────
        historical_available = historical_layer.status == "available"
        hist_score = historical_layer.score or 0.0

        if not historical_available:
            # Cannot produce a meaningful score without the certified baseline
            final_score = 0.0
            final_level = "LOW"
            data_limited = True
        else:
            final_score = round(
                max(0.0, min(100.0, hist_score + trigger_adjustment)), 1
            )
            final_level = _determine_risk_level(final_score)
            data_limited = False

        # ── 7. Confidence ──────────────────────────────────────────────────
        confidence = _compute_confidence(
            historical_available=historical_available,
            historical_confidence=historical_layer.confidence or 0.0,
            weather_available=weather_available,
            weather_freshness_seconds=weather_layer.freshness_seconds or 0,
            ml_available=ml_layer.status == "available",
            terrain_available=terrain_layer.status == "available",
        )

        # ── 8. Contributing factors (historical + weather) ─────────────────
        contributing_factors: list[ContributingFactor] = []

        if historical_available and hist_data is not None:
            for factor in hist_data.factors:
                if factor.available and factor.score > 0:
                    contributing_factors.append(ContributingFactor(
                        factor=factor.name,
                        description=factor.explanation,
                        value=round(factor.score, 1),
                        source="historical",
                    ))

        contributing_factors.extend(weather_factors)

        # Weather description as context factor (always present when available)
        if weather_available and weather_layer.description:
            contributing_factors.append(ContributingFactor(
                factor="current_weather_conditions",
                description=(
                    f"Current weather: {weather_layer.description}. "
                    f"Temperature {weather_layer.temperature_c}°C, "
                    f"wind {weather_layer.wind_speed_kmh} km/h."
                ),
                value=weather_layer.description,
                source="weather",
            ))

        # ── 9. Unavailable inputs ──────────────────────────────────────────
        unavailable_inputs: list[str] = []
        if not historical_available:
            unavailable_inputs.append("historical_risk")
        if not weather_available:
            unavailable_inputs.append("live_weather")
        if ml_layer.status != "available":
            unavailable_inputs.append("ml_susceptibility")
        if terrain_layer.status != "available":
            unavailable_inputs.append("terrain")
        if data_limited:
            unavailable_inputs.append("assessment_data_limited")

        # ── 10. Recommended actions ────────────────────────────────────────
        actions = _build_recommended_actions(final_level, contributing_factors)

        # ── 11. Data freshness ─────────────────────────────────────────────
        data_freshness = DataFreshness(
            assessment_generated_at=now,
            historical_data_version=hist_data.calculation_version if hist_data else None,
            weather_observation_time=weather_layer.observation_time,
            weather_fetched_at=weather_layer.fetched_at,
            weather_freshness_seconds=weather_layer.freshness_seconds,
            ml_artifact_version=ml_layer.model_version if ml_layer.status == "available" else None,
            terrain_dataset_version=None,
        )

        logger.info(
            "live_risk_assessment_complete",
            lat=lat,
            lon=lon,
            final_score=final_score,
            final_level=final_level,
            weather_status=weather_layer.status,
            trigger_adj=trigger_adjustment,
        )

        return LiveRiskData(
            location=LiveRiskLocation(latitude=lat, longitude=lon),
            timestamp=now,
            risk=LiveRiskSummary(
                score=final_score,
                level=final_level,
                confidence=confidence,
            ),
            historical=historical_layer,
            weather=weather_layer,
            ml=ml_layer,
            terrain=terrain_layer,
            contributing_factors=contributing_factors,
            unavailable_inputs=unavailable_inputs,
            recommended_actions=actions,
            data_freshness=data_freshness,
            engine_version=ENGINE_VERSION,
        )
