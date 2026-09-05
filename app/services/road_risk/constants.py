"""
ROAD_RISK_V1 — constants, formula documentation, and thresholds.

FORMULA DOCUMENTATION — PREDICTED BLOCKAGE RISK
================================================

The predicted blockage risk score is a deterministic weighted combination
of available signals.  All weights are documented and justified here.

AVAILABLE SIGNALS (V1):
  A. Live Area Risk (from LIVE_RISK_V1)
       — composite historical + live weather trigger score [0-100]
       — includes Phase 2A historical landslide evidence (GSI + IMD)
       — includes live precipitation trigger adjustment (IMD intensity tiers)
       — this is the strongest available signal: weight = W_LIVE_RISK (0.65)

  B. Phase 2B Isolation Severity (from RoadIsolationSimulator)
       — connectivity impact of this specific segment's removal [0-100]
       — indicates HOW MUCH the road matters to the network
       — not a direct landslide signal; amplifies risk for critical corridors
       — weight = W_ISOLATION (0.20)

  C. Bridge/Critical-Infrastructure Modifier
       — binary: if segment is a graph-theoretic bridge (is_bridge_edge=True)
         or an OSM physical bridge (bridge=True), add BRIDGE_MODIFIER pts
       — bridges are disproportionately vulnerable in landslide zones
       — bounded additive modifier; does not exceed BRIDGE_MODIFIER_CAP

UNAVAILABLE SIGNALS (stated explicitly):
  D. ML susceptibility — EXPERIMENTAL artifact; not used.
  E. Terrain (slope, elevation) — no validated DEM; not fabricated.
  F. Live traffic — no traffic provider; not fabricated.
  G. Confirmed closure — no closure feed; closure_status = UNKNOWN.

FORMULA:
  raw_score = W_LIVE_RISK * live_risk_score
            + W_ISOLATION  * isolation_severity

  bridge_modifier = BRIDGE_MODIFIER if (is_bridge_edge or osm_bridge) else 0.0
  bridge_modifier = min(bridge_modifier, BRIDGE_MODIFIER_CAP)

  predicted_risk_score = clamp(raw_score + bridge_modifier, 0.0, 100.0)

DOUBLE-COUNTING PREVENTION:
  Live Area Risk already incorporates:
    - Phase 2A historical GSI landslide evidence
    - Phase 2A IMD climatological rainfall anomaly
    - Live weather precipitation trigger
  Isolation severity is a TOPOLOGICAL signal (network fragmentation) — it
  is orthogonal to the hazard signal in live_risk_score.
  There is no double-counting between these two signals.

CONFIDENCE:
  confidence = W_CONF_LIVE * live_risk_confidence
             + W_CONF_ISOLATION * (100.0 if isolation_available else 0.0)
  Reduced when:
    - live area risk is unavailable
    - road segment cannot be resolved precisely
    - isolation simulation fails
  Never confused with the risk score itself.

RISK CLASSIFICATION (matches Phase 2A and LIVE_RISK_V1 exactly):
  [0,  24] → LOW
  [25, 49] → MODERATE
  [50, 74] → HIGH
  [75, 100] → CRITICAL
"""
from __future__ import annotations

ENGINE_VERSION = "ROAD_RISK_V1"

# ---------------------------------------------------------------------------
# Formula weights
# ---------------------------------------------------------------------------
W_LIVE_RISK: float = 0.65    # Live area risk (historical + weather trigger) — primary signal
W_ISOLATION: float = 0.20    # Phase 2B isolation severity — topological criticality

# Combined weights must sum to ≤ 1.0 to keep raw_score ≤ 100 before modifier
# 0.65 + 0.20 = 0.85  → leaves room for bridge modifier without exceeding cap

# ---------------------------------------------------------------------------
# Bridge / critical-infrastructure modifier
# ---------------------------------------------------------------------------
BRIDGE_MODIFIER: float = 10.0    # pts added when segment is a bridge (OSM or graph-theoretic)
BRIDGE_MODIFIER_CAP: float = 10.0  # hard cap; prevents modifier from dominating

# ---------------------------------------------------------------------------
# Confidence weights
# ---------------------------------------------------------------------------
W_CONF_LIVE: float = 0.70        # live area risk confidence contributes 70% of road confidence
W_CONF_ISOLATION: float = 0.30   # isolation simulation availability contributes 30%

# If no primary signals available, confidence is floored here
CONF_DATA_LIMITED_MAX: float = 20.0

# ---------------------------------------------------------------------------
# Risk level thresholds — MUST mirror Phase 2A and LIVE_RISK_V1 exactly
# ---------------------------------------------------------------------------
RISK_LEVEL_LOW_MAX: float = 24.0
RISK_LEVEL_MODERATE_MAX: float = 49.0
RISK_LEVEL_HIGH_MAX: float = 74.0
# > 74.0 → CRITICAL
