"""
RISKSETU AI — ROAD_RISK_V1 orchestration package.

Combines:
  - Phase 2A certified deterministic historical risk (read-only)
  - Phase 2B certified road connectivity simulation (read-only, what-if)
  - Open-Meteo live weather service
  - ML susceptibility (currently unavailable — experimental artifact)
  - Terrain (currently unavailable — no validated DEM)

Neither Phase 2A nor Phase 2B is modified in any way.
"""
from __future__ import annotations
