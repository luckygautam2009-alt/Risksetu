"""
Unit tests for OSM PBF parser, varint decoding, and distance calculations.
"""
from __future__ import annotations


from app.services.ingestion.osm_parser import OSMPBFParser


def test_haversine_distance() -> None:
    """Verify haversine distance calculation in meters."""
    # Delhi to Dehradun approx 200 km (200,000 m)
    dist = OSMPBFParser.haversine_distance(77.2090, 28.6139, 78.0322, 30.3165)
    assert 200000 <= dist <= 220000

    # Same point distance is zero
    assert OSMPBFParser.haversine_distance(77.0, 30.0, 77.0, 30.0) == 0.0


def test_varint_decoder() -> None:
    """Verify varint reader properly handles single-byte and multi-byte integers."""
    # 1 byte varint: 0x01 = 1
    val, pos = OSMPBFParser._read_varint(b"\x01", 0)
    assert val == 1
    assert pos == 1

    # 2 byte varint: 300 = 0xAC 0x02
    val, pos = OSMPBFParser._read_varint(b"\xac\x02", 0)
    assert val == 300
    assert pos == 2
