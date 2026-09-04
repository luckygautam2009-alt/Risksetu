"""
Unit tests for Census 2011 streaming parser and hash calculations.
"""
from __future__ import annotations

from app.services.ingestion.census_parser import CensusA1Parser, CensusPCAParser


def test_census_pca_hash_computation() -> None:
    """Verify deterministic hashing for census village records."""
    h1 = CensusPCAParser.compute_hash("01", "001", "00001", "000001", 130, 130)
    h2 = CensusPCAParser.compute_hash("01", "001", "00001", "000001", 130, 130)
    assert h1 == h2
    assert len(h1) == 64

    # Different population
    h3 = CensusPCAParser.compute_hash("01", "001", "00001", "000001", 131, 130)
    assert h1 != h3


def test_census_a1_hash_computation() -> None:
    """Verify deterministic hashing for Table A-1 records."""
    h1 = CensusA1Parser.compute_hash("01", "001", "00000", "DISTRICT", "Total")
    h2 = CensusA1Parser.compute_hash("01", "001", "00000", "DISTRICT", "Total")
    assert h1 == h2
    assert len(h1) == 64
