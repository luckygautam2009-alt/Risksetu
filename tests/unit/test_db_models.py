"""
Unit tests for SQLAlchemy domain models, table mappings, and schema definitions.
"""
from __future__ import annotations

from app.db.base import Base


def test_models_registered_in_metadata() -> None:
    """Verify that all core Phase 1B domain tables are properly registered in Base.metadata."""
    table_names = set(Base.metadata.tables.keys())
    expected_tables = {
        "dataset_sources",
        "ingestion_runs",
        "regions",
        "historical_landslides",
        "rainfall_subdivisions",
        "rainfall_observations",
        "rainfall_climatology",
        "census_villages",
        "census_area_reference",
        "road_network_nodes",
        "road_network_edges",
        "terrain_sources",
        "terrain_cells",
        "admin_name_aliases",
    }
    for expected in expected_tables:
        assert expected in table_names, f"Expected table {expected} not found in Base.metadata"


def test_landslide_model_constraints() -> None:
    """Verify HistoricalLandslide column attributes and constraints."""
    table = Base.metadata.tables["historical_landslides"]
    assert "gsi_slide_no" in table.columns
    assert "latitude" in table.columns
    assert "longitude" in table.columns
    assert "geom" in table.columns
    assert "history_raw" in table.columns
    assert "event_date" in table.columns

    # Check unique constraint on gsi_slide_no
    assert table.columns["gsi_slide_no"].unique or any(
        idx.unique and "gsi_slide_no" in [c.name for c in idx.columns]
        for idx in table.indexes
    )


def test_rainfall_observation_uniqueness() -> None:
    """Verify RainfallObservation composite unique constraint (subdivision_id, year, month)."""
    table = Base.metadata.tables["rainfall_observations"]
    assert "subdivision_id" in table.columns
    assert "year" in table.columns
    assert "month" in table.columns
    assert "rainfall_mm" in table.columns

    # Check uniqueness constraints
    uq_names = [uq.name for uq in table.constraints if hasattr(uq, "columns")]
    assert "uq_subdiv_year_month" in uq_names


def test_census_village_hierarchy_uniqueness() -> None:
    """Verify CensusVillage hierarchy composite constraint."""
    table = Base.metadata.tables["census_villages"]
    assert "state_code" in table.columns
    assert "district_code" in table.columns
    assert "subdistrict_code" in table.columns
    assert "village_code" in table.columns
    assert "total_population" in table.columns
    assert "households" in table.columns

    uq_names = [uq.name for uq in table.constraints if hasattr(uq, "columns")]
    assert "uq_census_hierarchy_code" in uq_names
