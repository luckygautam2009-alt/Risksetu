"""
LIVE_RISK_V1 — constants and configuration.

All weights, caps, and thresholds are documented and justified here.
"""
from __future__ import annotations

ENGINE_VERSION = "LIVE_RISK_V1"

# ---------------------------------------------------------------------------
# Live weather trigger adjustment — DOCUMENTATION
#
# The Phase 2A engine already encodes historical/climatological rainfall
# evidence via the RainfallRiskEvaluator (IMD subdivision climatology).
# The live weather component adds a CURRENT TRIGGER adjustment — it answers
# the question "Is it actively raining / likely to rain now?" rather than
# duplicating the historical anomaly signal.
#
# To avoid double-counting the rainfall signal, the trigger adjustment is:
#   1. Additive on top of the historical baseline score.
#   2. Bounded: maximum absolute adjustment = WEATHER_TRIGGER_CAP_POINTS.
#   3. Only applied when weather data is available (status OK or CACHED).
#   4. Driven by live precipitation thresholds, not climatological baselines.
#
# Weather trigger thresholds (live precipitation_mm per hour):
#   ≥ PRECIP_MODERATE_MM_PER_H  → MODERATE trigger
#   ≥ PRECIP_HIGH_MM_PER_H      → HIGH trigger
#   ≥ PRECIP_EXTREME_MM_PER_H   → EXTREME trigger
#
# These thresholds are based on IMD rainfall intensity classification:
#   Light rain:   < 2.5 mm/h
#   Moderate rain: 2.5–7.5 mm/h
#   Heavy rain:   7.5–35.5 mm/h
#   Very heavy:   35.5–124.4 mm/h
#   Extreme:      ≥ 124.4 mm/h
# Source: IMD Rainfall Intensity Classification (operational standard)
# ---------------------------------------------------------------------------

PRECIP_MODERATE_MM_PER_H: float = 2.5    # IMD light/moderate boundary
PRECIP_HIGH_MM_PER_H: float = 7.5        # IMD moderate/heavy boundary
PRECIP_EXTREME_MM_PER_H: float = 35.5    # IMD heavy/very-heavy boundary

# Points added per trigger tier (bounded by cap)
PRECIP_MODERATE_ADJUSTMENT: float = 5.0
PRECIP_HIGH_ADJUSTMENT: float = 10.0
PRECIP_EXTREME_ADJUSTMENT: float = 15.0

# Additional humidity contribution (high humidity = antecedent saturation proxy)
HUMIDITY_HIGH_THRESHOLD_PCT: float = 80.0
HUMIDITY_ADJUSTMENT: float = 3.0

# Maximum total weather trigger adjustment regardless of conditions
WEATHER_TRIGGER_CAP_POINTS: float = 15.0

# ---------------------------------------------------------------------------
# Risk level thresholds — MUST match Phase 2A constants exactly
# ---------------------------------------------------------------------------
RISK_LEVEL_LOW_MAX: float = 24.0
RISK_LEVEL_MODERATE_MAX: float = 49.0
RISK_LEVEL_HIGH_MAX: float = 74.0
# > 74.0 → CRITICAL

# ---------------------------------------------------------------------------
# Confidence component weights
# ---------------------------------------------------------------------------
CONF_WEIGHT_HISTORICAL: float = 0.60   # historical is the primary certified input
CONF_WEIGHT_WEATHER: float = 0.25      # live weather adds significant situational value
CONF_WEIGHT_ML: float = 0.10           # reserved for future validated ML
CONF_WEIGHT_TERRAIN: float = 0.05      # reserved for future DEM integration

# Max confidence when all inputs are unavailable (data-limited floor)
CONF_DATA_LIMITED_MAX: float = 30.0

# Freshness penalty — reduce confidence for stale weather data
WEATHER_STALE_THRESHOLD_S: int = 600          # 10 minutes → start reducing
WEATHER_CONFIDENCE_PENALTY_PER_S: float = 0.002  # 0.12 pts/min (negligible, caps at ~0.5% per hour)
