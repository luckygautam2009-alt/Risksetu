"""
Unit tests for GSI Landslide PDF parser and validator.
"""
from __future__ import annotations

import datetime

from app.services.ingestion.gsi_parser import GSIPDFParser


def test_gsi_date_parser() -> None:
    """Test parsing various real historical date formats from GSI inventory."""
    parser = GSIPDFParser("dummy_path.pdf")

    # Full date format: DD Month YYYY
    d1 = parser.parse_event_date("17 May 2016")
    assert d1 == datetime.date(2016, 5, 17)

    d2 = parser.parse_event_date("02 June 2020")
    assert d2 == datetime.date(2020, 6, 2)

    # Year only: YYYY
    d3 = parser.parse_event_date("2014")
    assert d3 == datetime.date(2014, 1, 1)

    # Month and Year: Month YYYY
    d4 = parser.parse_event_date("August 2018")
    assert d4 == datetime.date(2018, 8, 1)

    # Null / Missing / NA formats
    assert parser.parse_event_date("NA") is None
    assert parser.parse_event_date("N/A") is None
    assert parser.parse_event_date("UNKNOWN") is None
    assert parser.parse_event_date("") is None
    assert parser.parse_event_date(None) is None


def test_gsi_deterministic_hash() -> None:
    """Verify hash computation is deterministic and changes with coordinates or slide ID."""
    h1 = GSIPDFParser.compute_hash("ASM/HKN/83D07/2020/2", 24.2700, 92.5000, "Assam")
    h2 = GSIPDFParser.compute_hash("ASM/HKN/83D07/2020/2", 24.2700, 92.5000, "Assam")
    assert h1 == h2
    assert len(h1) == 64

    # Change coordinate
    h3 = GSIPDFParser.compute_hash("ASM/HKN/83D07/2020/2", 24.2701, 92.5000, "Assam")
    assert h1 != h3
