"""
Unit tests for IMD Rainfall parser, normalizer, and climatology calculations.
"""
from __future__ import annotations

import math

from app.services.ingestion.imd_parser import IMDObservationRecord, IMDRainfallParser


def test_subdivision_name_normalization() -> None:
    """Verify subdivision name normalization standardizes ampersands and whitespace."""
    assert IMDRainfallParser.normalize_subdivision_name("Andaman & Nicobar Islands") == "ANDAMAN AND NICOBAR ISLANDS"
    assert IMDRainfallParser.normalize_subdivision_name("Assam & Meghalaya") == "ASSAM AND MEGHALAYA"
    assert IMDRainfallParser.normalize_subdivision_name("  Uttarakhand  ") == "UTTARAKHAND"


def test_climatology_calculation() -> None:
    """Verify statistical mean and standard deviation computation for rainfall observations."""
    parser = IMDRainfallParser("dummy.csv")

    obs = [
        IMDObservationRecord(subdivision_name="Uttarakhand", year=2000, month=7, rainfall_mm=200.0, source_record_hash="h1"),
        IMDObservationRecord(subdivision_name="Uttarakhand", year=2001, month=7, rainfall_mm=300.0, source_record_hash="h2"),
        IMDObservationRecord(subdivision_name="Uttarakhand", year=2002, month=7, rainfall_mm=400.0, source_record_hash="h3"),
        IMDObservationRecord(subdivision_name="Uttarakhand", year=2003, month=7, rainfall_mm=None, source_record_hash="h4"),  # Null reading
    ]

    clim = parser.calculate_climatology(obs, version="v1.0")
    assert len(clim) == 1
    c = clim[0]
    assert c.subdivision_name == "Uttarakhand"
    assert c.month == 7
    assert c.years_used == 3
    assert c.mean_mm == 300.0
    assert math.isclose(c.stddev_mm, 81.65, abs_tol=0.1)
    assert c.min_mm == 200.0
    assert c.max_mm == 400.0
