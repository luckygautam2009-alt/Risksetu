"""Initial migration: PostGIS extension, staging schema, and core real data domain tables.

Revision ID: 0001_phase1b_core_tables
Revises: 
Create Date: 2026-09-04 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = "0001_phase1b_core_tables"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable PostGIS spatial extension if not present
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    
    # 2. Create staging schema for temporary ingestion workflows
    op.execute("CREATE SCHEMA IF NOT EXISTS staging;")

    # 3. Dataset Sources registry
    op.create_table(
        "dataset_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset_name", sa.String(100), nullable=False),
        sa.Column("source_agency", sa.String(100), nullable=False),
        sa.Column("source_file", sa.String(255), nullable=False),
        sa.Column("source_version", sa.String(50), nullable=True),
        sa.Column("source_snapshot_date", sa.Date(), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("ingestion_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_dataset_sources_name", "dataset_sources", ["dataset_name"], unique=True)

    # 4. Ingestion Runs audit table
    op.create_table(
        "ingestion_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset_source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dataset_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="running"),
        sa.Column("records_read", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ingestion_runs_run_id", "ingestion_runs", ["run_id"], unique=True)
    op.create_index("ix_ingestion_runs_source_id", "ingestion_runs", ["dataset_source_id"])

    # 5. Regions
    op.create_table(
        "regions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("district", sa.String(100), nullable=True),
        sa.Column("region_type", sa.String(50), nullable=False, server_default="district"),
        sa.Column("source", sa.String(100), nullable=False, server_default="official"),
        sa.Column("geom", geoalchemy2.Geometry("MULTIPOLYGON", srid=4326), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_regions_name", "regions", ["name"])
    op.create_index("ix_regions_state", "regions", ["state"])
    op.create_index("ix_regions_district", "regions", ["district"])

    # 6. Historical Landslides (GSI)
    op.create_table(
        "historical_landslides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("gsi_slide_no", sa.String(100), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("district", sa.String(100), nullable=False),
        sa.Column("slide_name", sa.String(255), nullable=True),
        sa.Column("location_description", sa.Text(), nullable=True),
        sa.Column("road_corridor", sa.String(255), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("geom", geoalchemy2.Geometry("POINT", srid=4326), nullable=False),
        sa.Column("material", sa.String(100), nullable=True),
        sa.Column("movement_type", sa.String(100), nullable=True),
        sa.Column("history_raw", sa.String(255), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("source_dataset", sa.String(100), nullable=False, server_default="GSI_NLSM_PDF"),
        sa.Column("source_record_hash", sa.String(64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("latitude >= -90.0 AND latitude <= 90.0", name="chk_landslide_latitude"),
        sa.CheckConstraint("longitude >= -180.0 AND longitude <= 180.0", name="chk_landslide_longitude"),
    )
    op.create_index("ix_historical_landslides_gsi_slide_no", "historical_landslides", ["gsi_slide_no"], unique=True)
    op.create_index("ix_historical_landslides_state", "historical_landslides", ["state"])
    op.create_index("ix_historical_landslides_district", "historical_landslides", ["district"])
    op.create_index("ix_historical_landslides_state_district", "historical_landslides", ["state", "district"])
    op.create_index("ix_historical_landslides_movement_type", "historical_landslides", ["movement_type"])
    op.create_index("ix_historical_landslides_event_date", "historical_landslides", ["event_date"])
    op.create_index("ix_historical_landslides_record_hash", "historical_landslides", ["source_record_hash"])

    # 7. Rainfall Subdivisions (IMD)
    op.create_table(
        "rainfall_subdivisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subdivision_name", sa.String(100), nullable=False),
        sa.Column("normalized_name", sa.String(100), nullable=False),
        sa.Column("source", sa.String(100), nullable=False, server_default="IMD"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_rainfall_subdiv_name", "rainfall_subdivisions", ["subdivision_name"], unique=True)
    op.create_index("ix_rainfall_subdiv_norm", "rainfall_subdivisions", ["normalized_name"], unique=True)

    # 8. Rainfall Observations (IMD long-form)
    op.create_table(
        "rainfall_observations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("subdivision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rainfall_subdivisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("rainfall_mm", sa.Float(), nullable=True),
        sa.Column("source_dataset", sa.String(100), nullable=False, server_default="IMD_SUBDIVISION_CSV"),
        sa.Column("source_record_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("subdivision_id", "year", "month", name="uq_subdiv_year_month"),
        sa.CheckConstraint("month >= 1 AND month <= 12", name="chk_rainfall_month"),
        sa.CheckConstraint("rainfall_mm >= 0.0 OR rainfall_mm IS NULL", name="chk_rainfall_positive"),
    )
    op.create_index("ix_rainfall_obs_subdiv_year", "rainfall_observations", ["subdivision_id", "year"])
    op.create_index("ix_rainfall_obs_year_month", "rainfall_observations", ["year", "month"])
    op.create_index("ix_rainfall_obs_record_hash", "rainfall_observations", ["source_record_hash"])

    # 9. Rainfall Climatology Baseline
    op.create_table(
        "rainfall_climatology",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subdivision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rainfall_subdivisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("years_used", sa.Integer(), nullable=False),
        sa.Column("mean_mm", sa.Float(), nullable=False),
        sa.Column("stddev_mm", sa.Float(), nullable=False),
        sa.Column("min_mm", sa.Float(), nullable=False),
        sa.Column("max_mm", sa.Float(), nullable=False),
        sa.Column("source_period_start", sa.Integer(), nullable=False),
        sa.Column("source_period_end", sa.Integer(), nullable=False),
        sa.Column("calculation_version", sa.String(50), nullable=False, server_default="v1.0"),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.UniqueConstraint("subdivision_id", "month", "calculation_version", name="uq_climatology_subdiv_month_ver"),
        sa.CheckConstraint("month >= 1 AND month <= 12", name="chk_climatology_month"),
    )
    op.create_index("ix_rainfall_climatology_subdiv_month", "rainfall_climatology", ["subdivision_id", "month"])

    # 10. Census Villages (PCA 2011)
    op.create_table(
        "census_villages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("state_code", sa.String(10), nullable=False),
        sa.Column("district_code", sa.String(10), nullable=False),
        sa.Column("subdistrict_code", sa.String(10), nullable=False),
        sa.Column("village_code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("level", sa.String(50), nullable=False, server_default="VILLAGE"),
        sa.Column("rural_urban", sa.String(20), nullable=False, server_default="Rural"),
        sa.Column("total_population", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("male_population", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("female_population", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("households", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("child_population_0_6", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sc_population", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("st_population", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("literate_population", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("illiterate_population", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("working_population", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cultivators", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("agricultural_labourers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("census_year", sa.Integer(), nullable=False, server_default="2011"),
        sa.Column("geom", geoalchemy2.Geometry("POINT", srid=4326), nullable=True),
        sa.Column("source_dataset", sa.String(100), nullable=False, server_default="CENSUS_2011_PCA"),
        sa.Column("source_record_hash", sa.String(64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("state_code", "district_code", "subdistrict_code", "village_code", name="uq_census_hierarchy_code"),
        sa.CheckConstraint("total_population >= 0", name="chk_census_population_positive"),
        sa.CheckConstraint("households >= 0", name="chk_census_households_positive"),
    )
    op.create_index("ix_census_villages_state_dist", "census_villages", ["state_code", "district_code"])
    op.create_index("ix_census_villages_name", "census_villages", ["name"])
    op.create_index("ix_census_villages_record_hash", "census_villages", ["source_record_hash"])

    # 11. Census Area Reference (Table A-1)
    op.create_table(
        "census_area_reference",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("state_code", sa.String(10), nullable=False),
        sa.Column("district_code", sa.String(10), nullable=False),
        sa.Column("subdistrict_code", sa.String(10), nullable=False),
        sa.Column("level", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("rural_urban", sa.String(20), nullable=False, server_default="Total"),
        sa.Column("inhabited_villages", sa.Integer(), nullable=True),
        sa.Column("uninhabited_villages", sa.Integer(), nullable=True),
        sa.Column("number_of_towns", sa.Integer(), nullable=True),
        sa.Column("households", sa.Integer(), nullable=True),
        sa.Column("population_persons", sa.Integer(), nullable=True),
        sa.Column("area_sq_km", sa.Float(), nullable=True),
        sa.Column("population_density_per_sq_km", sa.Float(), nullable=True),
        sa.Column("source_dataset", sa.String(100), nullable=False, server_default="CENSUS_2011_A1"),
        sa.Column("source_record_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("state_code", "district_code", "subdistrict_code", "level", "rural_urban", name="uq_census_a1_hierarchy"),
    )
    op.create_index("ix_census_a1_state_dist", "census_area_reference", ["state_code", "district_code"])
    op.create_index("ix_census_a1_record_hash", "census_area_reference", ["source_record_hash"])

    # 12. Road Network Nodes (OSM)
    op.create_table(
        "road_network_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("osm_node_id", sa.BigInteger(), nullable=False),
        sa.Column("geom", geoalchemy2.Geometry("POINT", srid=4326), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_road_network_nodes_osm_node_id", "road_network_nodes", ["osm_node_id"], unique=True)

    # 13. Road Network Edges (OSM)
    op.create_table(
        "road_network_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("osm_way_id", sa.BigInteger(), nullable=False),
        sa.Column("from_node_id", sa.BigInteger(), nullable=False),
        sa.Column("to_node_id", sa.BigInteger(), nullable=False),
        sa.Column("highway_class", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("oneway", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("maxspeed", sa.Integer(), nullable=True),
        sa.Column("bridge", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("tunnel", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("layer", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("surface", sa.String(50), nullable=True),
        sa.Column("access", sa.String(50), nullable=True),
        sa.Column("length_m", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("geom", geoalchemy2.Geometry("LINESTRING", srid=4326), nullable=False),
        sa.Column("source_snapshot", sa.String(100), nullable=False, server_default="OSM_NORTHERN_ZONE_260903"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_road_edges_osm_way_id", "road_network_edges", ["osm_way_id"])
    op.create_index("ix_road_edges_from_to", "road_network_edges", ["from_node_id", "to_node_id"])
    op.create_index("ix_road_edges_highway_class", "road_network_edges", ["highway_class"])

    # 14. Terrain Sources (Future DEM readiness)
    op.create_table(
        "terrain_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tile_name", sa.String(100), nullable=False),
        sa.Column("source_agency", sa.String(100), nullable=False, server_default="ISRO_NRSC"),
        sa.Column("resolution_m", sa.Float(), nullable=False, server_default="30.0"),
        sa.Column("crs", sa.String(50), nullable=False, server_default="EPSG:4326"),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("tile_path", sa.String(255), nullable=True),
        sa.Column("geom_bbox", geoalchemy2.Geometry("POLYGON", srid=4326), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_terrain_sources_tile_name", "terrain_sources", ["tile_name"], unique=True)

    # 15. Terrain Cells (Future DEM readiness)
    op.create_table(
        "terrain_cells",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("terrain_sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("elevation_m", sa.Float(), nullable=True),
        sa.Column("slope_deg", sa.Float(), nullable=True),
        sa.Column("aspect_deg", sa.Float(), nullable=True),
        sa.Column("curvature", sa.Float(), nullable=True),
        sa.Column("twi", sa.Float(), nullable=True),
        sa.Column("geom", geoalchemy2.Geometry("POLYGON", srid=4326), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_terrain_cells_elevation", "terrain_cells", ["elevation_m"])
    op.create_index("ix_terrain_cells_slope", "terrain_cells", ["slope_deg"])

    # 16. Admin Name Aliases
    op.create_table(
        "admin_name_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_name", sa.String(150), nullable=False),
        sa.Column("normalized_name", sa.String(150), nullable=False),
        sa.Column("source_dataset", sa.String(50), nullable=False),
        sa.Column("administrative_level", sa.String(50), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_name", "source_dataset", "administrative_level", name="uq_source_alias_level"),
    )
    op.create_index("ix_admin_aliases_source_name", "admin_name_aliases", ["source_name"])
    op.create_index("ix_admin_aliases_norm_level", "admin_name_aliases", ["normalized_name", "administrative_level"])


def downgrade() -> None:
    op.drop_table("admin_name_aliases")
    op.drop_table("terrain_cells")
    op.drop_table("terrain_sources")
    op.drop_table("road_network_edges")
    op.drop_table("road_network_nodes")
    op.drop_table("census_area_reference")
    op.drop_table("census_villages")
    op.drop_table("rainfall_climatology")
    op.drop_table("rainfall_observations")
    op.drop_table("rainfall_subdivisions")
    op.drop_table("historical_landslides")
    op.drop_table("regions")
    op.drop_table("ingestion_runs")
    op.drop_table("dataset_sources")
    op.execute("DROP SCHEMA IF EXISTS staging CASCADE;")
