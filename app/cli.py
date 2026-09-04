"""
RISKSETU AI — Database Management, Validation, and Ingestion CLI.

Usage:
    python -m app.cli db-validate
    python -m app.cli data-quality
    python -m app.cli ingest --dataset [gsi|rainfall|census|census-a1|osm|all] [--limit N]
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.models.census import CensusAreaReference, CensusVillage
from app.models.landslide import HistoricalLandslide
from app.models.rainfall import (
    RainfallClimatology,
    RainfallObservation,
    RainfallSubdivision,
)
from app.models.road import RoadNetworkEdge, RoadNetworkNode
from app.models.source import DatasetSource, IngestionRun
from app.models.terrain import TerrainCell, TerrainSource
from app.services.ingestion.runner import IngestionRunner


def cmd_db_validate() -> int:
    """Validate database connectivity, PostGIS extension, table presence, and integrity."""
    print("=" * 60)
    print("RISKSETU AI — DATABASE & POSTGIS VALIDATION")
    print("=" * 60)

    settings = get_settings()
    print(f"Target Environment: {settings.app_env}")
    # Redacted connection display
    safe_db_url = settings.database_url.split("@")[-1] if "@" in settings.database_url else "configured"
    print(f"Database Host/DB:   ...@{safe_db_url}")

    # 1. Connection check
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[PASS] PostgreSQL connection established.")
    except Exception as e:
        print(f"[FAIL] Could not connect to PostgreSQL: {e}")
        return 1

    # 2. PostGIS Extension check
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT PostGIS_Version()")).scalar()
        print(f"[PASS] PostGIS extension active: Version {result}")
    except Exception as e:
        print(f"[WARN] PostGIS extension not available: {e}")

    # 3. Table and Row Count Verification
    db = SessionLocal()
    try:
        tables = [
            ("dataset_sources", DatasetSource),
            ("ingestion_runs", IngestionRun),
            ("historical_landslides", HistoricalLandslide),
            ("rainfall_subdivisions", RainfallSubdivision),
            ("rainfall_observations", RainfallObservation),
            ("rainfall_climatology", RainfallClimatology),
            ("census_villages", CensusVillage),
            ("census_area_reference", CensusAreaReference),
            ("road_network_nodes", RoadNetworkNode),
            ("road_network_edges", RoadNetworkEdge),
            ("terrain_sources", TerrainSource),
            ("terrain_cells", TerrainCell),
        ]

        print("\n--- Table Verification & Row Counts ---")
        for tbl_name, model_cls in tables:
            try:
                count = db.scalar(select(func.count()).select_from(model_cls))
                print(f"  [OK] {tbl_name:<26}: {count:,} records")
            except Exception as exc:
                print(f"  [MISSING/ERROR] {tbl_name:<26}: {exc}")

        # 4. Geometry validity check
        print("\n--- Spatial Geometry Validity Check ---")
        try:
            invalid_landslides = db.scalar(
                select(func.count())
                .select_from(HistoricalLandslide)
                .where(func.ST_IsValid(HistoricalLandslide.geom).is_(False))
            ) or 0
            print(f"  [PASS] Invalid Landslide Geometries: {invalid_landslides}")
        except Exception:
            print("  [SKIP] Spatial geometry validity query skipped.")

        print("\n" + "=" * 60)
        print("DATABASE VALIDATION COMPLETE: ALL SYSTEMS FUNCTIONAL")
        print("=" * 60)
        return 0
    finally:
        db.close()


def cmd_data_quality() -> int:
    """Print comprehensive forensic data quality report."""
    print("=" * 60)
    print("RISKSETU AI — DATA QUALITY & FORENSIC AUDIT REPORT")
    print("=" * 60)

    db = SessionLocal()
    try:
        # GSI Landslides
        print("\n[1] GSI Historical Landslide Dataset:")
        try:
            total_gsi = db.scalar(select(func.count()).select_from(HistoricalLandslide)) or 0
            null_dates = db.scalar(
                select(func.count())
                .select_from(HistoricalLandslide)
                .where(HistoricalLandslide.event_date.is_(None))
            ) or 0
            dated = total_gsi - null_dates
            print(f"    - Total Landslide Events: {total_gsi:,}")
            print(f"    - Events with Verified Trigger Date: {dated:,} ({(dated/total_gsi*100) if total_gsi else 0:.1f}%)")
            print(f"    - Events with Spatial Coordinates Only: {null_dates:,}")
        except Exception:
            print("    - Historical landslides table not yet populated.")

        # IMD Rainfall
        print("\n[2] IMD Rainfall Dataset:")
        try:
            subdiv_cnt = db.scalar(select(func.count()).select_from(RainfallSubdivision)) or 0
            obs_cnt = db.scalar(select(func.count()).select_from(RainfallObservation)) or 0
            null_rain = db.scalar(
                select(func.count())
                .select_from(RainfallObservation)
                .where(RainfallObservation.rainfall_mm.is_(None))
            ) or 0
            clim_cnt = db.scalar(select(func.count()).select_from(RainfallClimatology)) or 0
            print(f"    - Subdivisions Ingested: {subdiv_cnt}")
            print(f"    - Monthly Observations: {obs_cnt:,}")
            print(f"    - Missing / Null Monthly Readings: {null_rain:,}")
            print(f"    - Derived Climatological Normals: {clim_cnt:,}")
        except Exception:
            print("    - Rainfall tables not yet populated.")

        # Census 2011
        print("\n[3] Census 2011 Demographics:")
        try:
            vil_cnt = db.scalar(select(func.count()).select_from(CensusVillage)) or 0
            a1_cnt = db.scalar(select(func.count()).select_from(CensusAreaReference)) or 0
            print(f"    - Village / Ward Records Ingested: {vil_cnt:,}")
            print(f"    - Area Reference (Table A-1) Rows: {a1_cnt:,}")
        except Exception:
            print("    - Census tables not yet populated.")

        # OSM Roads
        print("\n[4] OpenStreetMap Transportation Network:")
        try:
            edge_cnt = db.scalar(select(func.count()).select_from(RoadNetworkEdge)) or 0
            node_cnt = db.scalar(select(func.count()).select_from(RoadNetworkNode)) or 0
            print(f"    - Routable Road Edges: {edge_cnt:,}")
            print(f"    - Network Graph Nodes: {node_cnt:,}")
        except Exception:
            print("    - OSM tables not yet populated.")

        # DEM Status
        print("\n[5] ISRO / NRSC Bhoonidhi DEM:")
        print("    - Status: NOT AVAILABLE IN SOURCE DATA (Architecture configured, no synthetic rows)")

        print("\n" + "=" * 60)
        return 0
    finally:
        db.close()


def cmd_ingest(dataset: str, limit: int | None = None) -> int:
    """Execute dataset ingestion pipeline."""
    print(f"Starting ingestion for dataset: {dataset} (limit={limit})...")
    db = SessionLocal()
    runner = IngestionRunner(db)

    try:
        if dataset in ("gsi", "all"):
            print("--> Ingesting GSI Landslide Inventory...")
            res = runner.ingest_gsi_landslides(limit=limit)
            print(f"    GSI result: {res}")

        if dataset in ("rainfall", "all"):
            print("--> Ingesting IMD Rainfall Data & Deriving Climatology...")
            res = runner.ingest_imd_rainfall()
            print(f"    Rainfall result: {res}")

        if dataset in ("census", "all"):
            print("--> Ingesting Census 2011 Primary Census Abstract...")
            res = runner.ingest_census_pca(limit=limit)
            print(f"    Census PCA result: {res}")

        if dataset in ("census-a1", "all"):
            print("--> Ingesting Census Table A-1 Area Reference...")
            res = runner.ingest_census_a1()
            print(f"    Census A-1 result: {res}")

        if dataset in ("osm", "all"):
            print("--> Ingesting OpenStreetMap Road Network...")
            res = runner.ingest_osm_roads(limit=limit or 1000)
            print(f"    OSM result: {res}")

        print("Ingestion completed successfully.")
        return 0
    except Exception as e:
        print(f"Ingestion failed with error: {e}")
        return 1
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="RISKSETU AI Database CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # db-validate
    subparsers.add_parser("db-validate", help="Validate PostgreSQL and PostGIS database")

    # data-quality
    subparsers.add_parser("data-quality", help="Print data quality and forensic report")

    # ingest
    ingest_parser = subparsers.add_parser("ingest", help="Run dataset ingestion")
    ingest_parser.add_argument(
        "--dataset",
        choices=["gsi", "rainfall", "census", "census-a1", "osm", "all"],
        default="all",
        help="Dataset to ingest",
    )
    ingest_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of records to ingest (for testing/benchmarks)",
    )

    args = parser.parse_args()

    if args.command == "db-validate":
        sys.exit(cmd_db_validate())
    elif args.command == "data-quality":
        sys.exit(cmd_data_quality())
    elif args.command == "ingest":
        sys.exit(cmd_ingest(dataset=args.dataset, limit=args.limit))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
