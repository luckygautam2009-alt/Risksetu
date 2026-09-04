"""
Constants, default weights, and threshold definitions for the Risk Intelligence Engine.
"""
from __future__ import annotations

CALCULATION_VERSION = "risk-v1"

# Base Factor Weights (must sum to 1.0)
BASE_WEIGHT_HISTORICAL = 0.50
BASE_WEIGHT_RAINFALL = 0.30
BASE_WEIGHT_SPATIAL_CONTEXT = 0.20

# Search Radii for Historical Landslides (in kilometers and meters)
RADIUS_INNER_KM = 5.0
RADIUS_MID_KM = 10.0
RADIUS_OUTER_KM = 25.0

RADIUS_INNER_METERS = RADIUS_INNER_KM * 1000.0
RADIUS_MID_METERS = RADIUS_MID_KM * 1000.0
RADIUS_OUTER_METERS = RADIUS_OUTER_KM * 1000.0

# Density Scoring Multipliers
DENSITY_WEIGHT_INNER = 1.0
DENSITY_WEIGHT_MID = 0.5
DENSITY_WEIGHT_OUTER = 0.2

# Risk Level Boundaries
RISK_LEVEL_LOW_MAX = 24.0
RISK_LEVEL_MODERATE_MAX = 49.0
RISK_LEVEL_HIGH_MAX = 74.0

# Standard Limitations Documentation
STANDARD_LIMITATIONS = [
    "No Digital Elevation Model (DEM) derived terrain layers (slope, aspect, curvature, TWI) are currently present in the dataset repository.",
    "IMD precipitation data is sourced from historical sub-divisional monthly records rather than real-time telemetry or Doppler weather radar.",
    "GSI landslide inventory provides robust spatial footprint evidence, but 68.7% of historical inventory records lack precise calendar trigger timestamps.",
    "Calculations are deterministic evidence-based risk evaluations (Version 1), not probabilistic machine-learning predictions.",
]
