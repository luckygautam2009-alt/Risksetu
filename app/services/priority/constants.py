"""
Constants, weights, and categorical thresholds for the Impact-Aware Intervention Priority Engine.
"""
from __future__ import annotations

CALCULATION_VERSION = "priority-v1"

# Priority Composite Weights (must sum to 1.0)
WEIGHT_RISK = 0.45
WEIGHT_IMPACT = 0.40
WEIGHT_URGENCY = 0.15

# Urgency Base Scores by Categorical Risk Level
RISK_LEVEL_URGENCY_MAP: dict[str, float] = {
    "CRITICAL": 100.0,
    "HIGH": 75.0,
    "MODERATE": 50.0,
    "LOW": 25.0,
}

# Priority Categorical Level Thresholds (Standard 4-tier scale)
PRIORITY_LEVEL_LOW_MAX = 24.0
PRIORITY_LEVEL_MODERATE_MAX = 49.0
PRIORITY_LEVEL_HIGH_MAX = 74.0

# Standard Limitations Documentation
STANDARD_PRIORITY_LIMITATIONS: list[str] = [
    "Population impact is unavailable because Census village demographic records lack spatial boundary polygons.",
    "Economic loss estimation is not available.",
    "Traffic flow volume and vehicular congestion data are not available.",
    "Real-time road closure feeds and live emergency signals are not available.",
    "Priority is a deterministic Heuristic V1 decision-support index, not a scientifically calibrated emergency intervention policy.",
    "Connectivity impact is strictly bounded to the extracted Phase 2B local road-network subgraph.",
    "Transportation coverage is limited to the currently ingested 5,000-edge routable subset of the northern-zone OSM extract.",
]
