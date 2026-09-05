"""
RISKSETU AI — Landslide Susceptibility Prediction Service.

This module provides the ML-based landslide susceptibility prediction
engine. It is a SEPARATE intelligence layer that does NOT replace
the existing Phase 2A deterministic risk engine.

Model: risksetu-landslide-susceptibility-v1
Target: Binary landslide susceptibility (presence/background)
Training Data: GSI Bhukosh NLSM + IMD Climatology
Validation: Spatial Group Cross-Validation (GroupKFold)
"""
from __future__ import annotations
