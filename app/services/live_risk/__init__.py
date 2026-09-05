"""
RISKSETU AI — LIVE_RISK_V1 orchestration package.

This package is the decision-support layer that combines:
  - Phase 2A certified deterministic historical risk engine (read-only)
  - Open-Meteo live weather service
  - ML susceptibility status (currently unavailable — experimental artifact)
  - Terrain status (currently unavailable — no validated DEM)

It does NOT modify or replicate any certified component. It consumes their
outputs and produces a coherent, explainable operational assessment.
"""
from __future__ import annotations
