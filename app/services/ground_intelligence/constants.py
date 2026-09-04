"""
Constants, weights, and thresholds for the Ground Intelligence & Trust-Weighted Reporting Engine.
"""
from __future__ import annotations

CALCULATION_VERSION = "trust-v1"

# Trust Score Dimension Weights (must sum to 1.0)
WEIGHT_GEO = 0.25
WEIGHT_TEMPORAL = 0.20
WEIGHT_USER = 0.25
WEIGHT_CORROBORATION = 0.30

# Temporal Freshness Decay
HALF_LIFE_DAYS = 7.0

# User Reliability Parameters
DEFAULT_USER_RELIABILITY_CITIZEN = 50.0
DEFAULT_USER_RELIABILITY_OFFICIAL = 60.0
USER_RELIABILITY_ACCEPTED_BONUS = 5.0
USER_RELIABILITY_REJECTED_PENALTY = 15.0
USER_RELIABILITY_DUPLICATE_PENALTY = 10.0
USER_RELIABILITY_MIN = 5.0
USER_RELIABILITY_MAX = 100.0

# Corroboration Parameters
CORROBORATION_RADIUS_METERS = 2000.0
CORROBORATION_WINDOW_HOURS = 48.0

# Report Type Compatibility Groups for Corroboration
COMPATIBLE_REPORT_TYPES: dict[str, set[str]] = {
    "LANDSLIDE": {"LANDSLIDE", "SLOPE_MOVEMENT", "DEBRIS", "ROCKFALL", "ROAD_BLOCKAGE"},
    "SLOPE_MOVEMENT": {"SLOPE_MOVEMENT", "LANDSLIDE", "CRACK"},
    "CRACK": {"CRACK", "SLOPE_MOVEMENT", "ROAD_BLOCKAGE"},
    "ROCKFALL": {"ROCKFALL", "DEBRIS", "ROAD_BLOCKAGE", "LANDSLIDE"},
    "DEBRIS": {"DEBRIS", "ROCKFALL", "ROAD_BLOCKAGE", "LANDSLIDE"},
    "ROAD_BLOCKAGE": {"ROAD_BLOCKAGE", "DEBRIS", "ROCKFALL", "LANDSLIDE", "DRAINAGE_BLOCKAGE"},
    "DRAINAGE_BLOCKAGE": {"DRAINAGE_BLOCKAGE", "ROAD_BLOCKAGE", "DEBRIS"},
    "OTHER": {"OTHER"},
}

# Deduplication Thresholds
DUPLICATE_RADIUS_METERS = 200.0
DUPLICATE_WINDOW_HOURS = 12.0
DUPLICATE_TEXT_SIMILARITY_THRESHOLD = 0.70

# Trust Categorical Classification Thresholds (0-100 scale)
TRUST_LEVEL_LOW_MAX = 24.0
TRUST_LEVEL_MODERATE_MAX = 49.0
TRUST_LEVEL_HIGH_MAX = 74.0

# Automated Risk Eligibility Policy Thresholds
MIN_TRUST_FOR_RISK_ELIGIBILITY = 60.0
MAX_AGE_DAYS_FOR_RISK_ELIGIBILITY = 14.0
MIN_GEO_PLAUSIBILITY_FOR_RISK_ELIGIBILITY = 40.0

# Rate Limiting
DEFAULT_USER_RATE_LIMIT_PER_MINUTE = 10

# Standard Limitations Documentation
STANDARD_GROUND_INTELLIGENCE_LIMITATIONS: list[str] = [
    "Ground reports are user-submitted field observations and do not constitute verified physical ground truth.",
    "Trust scoring is a deterministic Heuristic V1 decision-support index, not a certified evidentiary truth rating.",
    "No professional on-site engineer verification has been performed on this observation.",
    "User reliability is initially determined by historical reporting records and neutral cold-start priors.",
    "Corroboration measures spatial-temporal convergence between independent observers and does not prove ground truth.",
    "No photo or computer-vision validation has been integrated into this evaluation.",
    "No real-time sensor, seismic, or traffic telemetry has corroborated this observation.",
    "Eligibility for automated risk influence indicates suitability as a model input, not physical hazard verification.",
]
