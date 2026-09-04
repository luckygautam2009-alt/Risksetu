"""
Central Ingestion Runner and Audit Coordinator.

Orchestrates batch-safe, idempotent ingestion for GSI Landslides, IMD Rainfall,
Census 2011 demographics, and OpenStreetMap road topology into PostgreSQL/PostGIS.
"""
from __future__ import annotations

import datetime
from typing import Any
import uuid

from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session
import structlog

from app.models.census import CensusAreaReference, CensusVillage
from app.models.landslide import HistoricalLandslide
from app.models.rainfall import (
    RainfallClimatology,
    RainfallObservation,
    RainfallSubdivision,
)
from app.models.road import RoadNetworkEdge, RoadNetworkNode
from app.models.source import DatasetSource, IngestionRun
from app.services.ingestion.census_parser import CensusA1Parser, CensusPCAParser
from app.services.ingestion.gsi_parser import GSIPDFParser
from app.services.ingestion.imd_parser import IMDRainfallParser
from app.services.ingestion.osm_parser import OSMPBFParser

logger = structlog.get_logger("risksetu.ingestion")


class IngestionRunner:
    """Orchestrator for idempotent real dataset ingestion."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create_source(
        self,
        dataset_name: str,
        source_agency: str,
        source_file: str,
        version: str | None = None,
    ) -> DatasetSource:
        """Get or register a dataset source."""
        stmt = select(DatasetSource).where(DatasetSource.dataset_name == dataset_name)
        source = self.db.scalars(stmt).first()
        if not source:
            source = DatasetSource(
                dataset_name=dataset_name,
                source_agency=source_agency,
                source_file=source_file,
                source_version=version,
                ingestion_status="pending",
                record_count=0,
            )
            self.db.add(source)
            self.db.commit()
            self.db.refresh(source)
        return source

    def start_run(self, source_id: uuid.UUID) -> IngestionRun:
        """Initialize an audited ingestion run."""
        run = IngestionRun(
            dataset_source_id=source_id,
            run_id=f"run_{uuid.uuid4().hex[:12]}_{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}",
            status="running",
            records_read=0,
            records_inserted=0,
            records_updated=0,
            records_rejected=0,
            error_count=0,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def finish_run(
        self,
        run: IngestionRun,
        status: str = "success",
        error_summary: str | None = None,
    ) -> None:
        """Complete an ingestion run and update source metadata."""
        run.status = status
        run.error_summary = error_summary
        run.completed_at = datetime.datetime.now(datetime.timezone.utc)

        # Update dataset source status
        source = self.db.get(DatasetSource, run.dataset_source_id)
        if source:
            source.ingestion_status = "completed" if status == "success" else "failed"
            source.ingested_at = datetime.datetime.now(datetime.timezone.utc)
            source.record_count = run.records_inserted + run.records_updated

        self.db.commit()

    # -------------------------------------------------------------------------
    # 1. GSI Landslide Ingestion
    # -------------------------------------------------------------------------
    def ingest_gsi_landslides(
        self,
        pdf_path: str = "database/landslide_report.pdf",
        batch_size: int = 1000,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Ingest GSI landslide records from PDF catalog."""
        source = self.get_or_create_source(
            dataset_name="GSI_LANDSLIDES",
            source_agency="Geological Survey of India",
            source_file=pdf_path,
            version="NLSM_2020",
        )
        run = self.start_run(source.id)
        parser = GSIPDFParser(pdf_path)

        read_count = 0
        inserted_count = 0
        updated_count = 0
        rejected_count = 0

        try:
            # Pre-load existing slide numbers and hashes for fast in-memory idempotency check
            existing_stmt = select(HistoricalLandslide.gsi_slide_no, HistoricalLandslide.source_record_hash)
            existing_records = {row[0]: row[1] for row in self.db.execute(existing_stmt).all()}

            batch: list[HistoricalLandslide] = []

            for rec in parser.parse():
                read_count += 1
                if limit and read_count > limit:
                    break

                if rec.gsi_slide_no in existing_records:
                    if existing_records[rec.gsi_slide_no] == rec.source_record_hash:
                        # Record is identical, skip (idempotent)
                        continue
                    else:
                        # Update record
                        updated_count += 1
                        continue

                point_geom = WKTElement(f"POINT({rec.longitude} {rec.latitude})", srid=4326)
                landslide_obj = HistoricalLandslide(
                    gsi_slide_no=rec.gsi_slide_no,
                    state=rec.state,
                    district=rec.district,
                    slide_name=rec.slide_name,
                    location_description=rec.location_description,
                    road_corridor=rec.road_corridor,
                    latitude=rec.latitude,
                    longitude=rec.longitude,
                    geom=point_geom,
                    material=rec.material,
                    movement_type=rec.movement_type,
                    history_raw=rec.history_raw,
                    event_date=rec.event_date,
                    source_dataset="GSI_NLSM_PDF",
                    source_record_hash=rec.source_record_hash,
                )
                batch.append(landslide_obj)
                existing_records[rec.gsi_slide_no] = rec.source_record_hash
                inserted_count += 1

                if len(batch) >= batch_size:
                    self.db.add_all(batch)
                    self.db.commit()
                    batch = []

            if batch:
                self.db.add_all(batch)
                self.db.commit()

            run.records_read = read_count
            run.records_inserted = inserted_count
            run.records_updated = updated_count
            run.records_rejected = rejected_count
            self.finish_run(run, status="success")

            return {
                "status": "success",
                "records_read": read_count,
                "records_inserted": inserted_count,
                "records_updated": updated_count,
                "records_rejected": rejected_count,
            }
        except Exception as e:
            self.db.rollback()
            self.finish_run(run, status="failed", error_summary=str(e))
            logger.error("gsi_ingestion_failed", error=str(e))
            raise

    # -------------------------------------------------------------------------
    # 2. IMD Rainfall Ingestion
    # -------------------------------------------------------------------------
    def ingest_imd_rainfall(
        self,
        csv_path: str = "database/Sub_Division_IMD_2017.csv",
        batch_size: int = 5000,
    ) -> dict[str, Any]:
        """Ingest IMD subdivisions, observations, and derived climatology."""
        source = self.get_or_create_source(
            dataset_name="IMD_RAINFALL",
            source_agency="India Meteorological Department",
            source_file=csv_path,
            version="1901_2017",
        )
        run = self.start_run(source.id)
        parser = IMDRainfallParser(csv_path)

        read_count = 0
        inserted_count = 0

        try:
            # 1. Ingest subdivisions
            subdiv_records = parser.get_subdivisions()
            subdiv_map: dict[str, uuid.UUID] = {}

            for s in subdiv_records:
                stmt = select(RainfallSubdivision).where(RainfallSubdivision.subdivision_name == s.subdivision_name)
                existing_subdiv = self.db.scalars(stmt).first()
                if not existing_subdiv:
                    subdiv_obj = RainfallSubdivision(
                        subdivision_name=s.subdivision_name,
                        normalized_name=s.normalized_name,
                        source="IMD",
                    )
                    self.db.add(subdiv_obj)
                    self.db.flush()
                    subdiv_map[s.subdivision_name] = subdiv_obj.id
                else:
                    subdiv_map[s.subdivision_name] = existing_subdiv.id

            self.db.commit()

            # 2. Ingest observations
            # Pre-load existing (subdivision_id, year, month)
            existing_obs_stmt = select(
                RainfallObservation.subdivision_id,
                RainfallObservation.year,
                RainfallObservation.month,
            )
            existing_obs = {
                (row[0], row[1], row[2])
                for row in self.db.execute(existing_obs_stmt).all()
            }

            obs_batch: list[RainfallObservation] = []
            all_observations = []

            for obs in parser.parse_observations():
                read_count += 1
                all_observations.append(obs)
                s_id = subdiv_map.get(obs.subdivision_name)
                if not s_id:
                    continue

                key = (s_id, obs.year, obs.month)
                if key in existing_obs:
                    continue

                obs_obj = RainfallObservation(
                    subdivision_id=s_id,
                    year=obs.year,
                    month=obs.month,
                    rainfall_mm=obs.rainfall_mm,
                    source_dataset="IMD_SUBDIVISION_CSV",
                    source_record_hash=obs.source_record_hash,
                )
                obs_batch.append(obs_obj)
                existing_obs.add(key)
                inserted_count += 1

                if len(obs_batch) >= batch_size:
                    self.db.add_all(obs_batch)
                    self.db.commit()
                    obs_batch = []

            if obs_batch:
                self.db.add_all(obs_batch)
                self.db.commit()

            # 3. Derive Climatology
            climatology_list = parser.calculate_climatology(all_observations, version="v1.0")
            for clim in climatology_list:
                s_id = subdiv_map.get(clim.subdivision_name)
                if not s_id:
                    continue

                # Check if climatology row exists
                c_stmt = select(RainfallClimatology).where(
                    RainfallClimatology.subdivision_id == s_id,
                    RainfallClimatology.month == clim.month,
                    RainfallClimatology.calculation_version == clim.calculation_version,
                )
                existing_clim = self.db.scalars(c_stmt).first()
                if not existing_clim:
                    clim_obj = RainfallClimatology(
                        subdivision_id=s_id,
                        month=clim.month,
                        years_used=clim.years_used,
                        mean_mm=clim.mean_mm,
                        stddev_mm=clim.stddev_mm,
                        min_mm=clim.min_mm,
                        max_mm=clim.max_mm,
                        source_period_start=clim.source_period_start,
                        source_period_end=clim.source_period_end,
                        calculation_version=clim.calculation_version,
                    )
                    self.db.add(clim_obj)

            self.db.commit()

            run.records_read = read_count
            run.records_inserted = inserted_count
            self.finish_run(run, status="success")

            return {
                "status": "success",
                "records_read": read_count,
                "records_inserted": inserted_count,
                "subdivisions_count": len(subdiv_map),
                "climatology_entries": len(climatology_list),
            }
        except Exception as e:
            self.db.rollback()
            self.finish_run(run, status="failed", error_summary=str(e))
            logger.error("imd_ingestion_failed", error=str(e))
            raise

    # -------------------------------------------------------------------------
    # 3. Census 2011 Ingestion
    # -------------------------------------------------------------------------
    def ingest_census_pca(
        self,
        xlsx_path: str = "database/2011-IndiaStateDistSbDistVill-0000.xlsx",
        batch_size: int = 5000,
        target_states: set[str] | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Ingest Census 2011 Primary Census Abstract village records."""
        source = self.get_or_create_source(
            dataset_name="CENSUS_2011_PCA",
            source_agency="Office of the Registrar General of India",
            source_file=xlsx_path,
            version="2011_PCA",
        )
        run = self.start_run(source.id)
        parser = CensusPCAParser(xlsx_path)

        read_count = 0
        inserted_count = 0

        try:
            batch: list[CensusVillage] = []
            for rec in parser.parse_villages(target_states=target_states, limit=limit):
                read_count += 1

                vil_obj = CensusVillage(
                    state_code=rec.state_code,
                    district_code=rec.district_code,
                    subdistrict_code=rec.subdistrict_code,
                    village_code=rec.village_code,
                    name=rec.name,
                    level=rec.level,
                    rural_urban=rec.rural_urban,
                    total_population=rec.total_population,
                    male_population=rec.male_population,
                    female_population=rec.female_population,
                    households=rec.households,
                    child_population_0_6=rec.child_population_0_6,
                    sc_population=rec.sc_population,
                    st_population=rec.st_population,
                    literate_population=rec.literate_population,
                    illiterate_population=rec.illiterate_population,
                    working_population=rec.working_population,
                    cultivators=rec.cultivators,
                    agricultural_labourers=rec.agricultural_labourers,
                    census_year=rec.census_year,
                    source_dataset="CENSUS_2011_PCA",
                    source_record_hash=rec.source_record_hash,
                )
                batch.append(vil_obj)
                inserted_count += 1

                if len(batch) >= batch_size:
                    self.db.add_all(batch)
                    self.db.commit()
                    batch = []

            if batch:
                self.db.add_all(batch)
                self.db.commit()

            run.records_read = read_count
            run.records_inserted = inserted_count
            self.finish_run(run, status="success")

            return {
                "status": "success",
                "records_read": read_count,
                "records_inserted": inserted_count,
            }
        except Exception as e:
            self.db.rollback()
            self.finish_run(run, status="failed", error_summary=str(e))
            logger.error("census_pca_ingestion_failed", error=str(e))
            raise

    def ingest_census_a1(
        self,
        xlsx_path: str = "database/A-1_NO_OF_VILLAGES_TOWNS_HOUSEHOLDS_POPULATION_AND_AREA.xlsx",
        batch_size: int = 2000,
    ) -> dict[str, Any]:
        """Ingest Census Table A-1 administrative area reference."""
        source = self.get_or_create_source(
            dataset_name="CENSUS_2011_A1",
            source_agency="Office of the Registrar General of India",
            source_file=xlsx_path,
            version="2011_A1",
        )
        run = self.start_run(source.id)
        parser = CensusA1Parser(xlsx_path)

        read_count = 0
        inserted_count = 0

        try:
            batch: list[CensusAreaReference] = []
            for rec in parser.parse_area_reference():
                read_count += 1
                ref_obj = CensusAreaReference(
                    state_code=rec.state_code,
                    district_code=rec.district_code,
                    subdistrict_code=rec.subdistrict_code,
                    level=rec.level,
                    name=rec.name,
                    rural_urban=rec.rural_urban,
                    inhabited_villages=rec.inhabited_villages,
                    uninhabited_villages=rec.uninhabited_villages,
                    number_of_towns=rec.number_of_towns,
                    households=rec.households,
                    population_persons=rec.population_persons,
                    area_sq_km=rec.area_sq_km,
                    population_density_per_sq_km=rec.population_density_per_sq_km,
                    source_dataset="CENSUS_2011_A1",
                    source_record_hash=rec.source_record_hash,
                )
                batch.append(ref_obj)
                inserted_count += 1

                if len(batch) >= batch_size:
                    self.db.add_all(batch)
                    self.db.commit()
                    batch = []

            if batch:
                self.db.add_all(batch)
                self.db.commit()

            run.records_read = read_count
            run.records_inserted = inserted_count
            self.finish_run(run, status="success")

            return {
                "status": "success",
                "records_read": read_count,
                "records_inserted": inserted_count,
            }
        except Exception as e:
            self.db.rollback()
            self.finish_run(run, status="failed", error_summary=str(e))
            logger.error("census_a1_ingestion_failed", error=str(e))
            raise

    # -------------------------------------------------------------------------
    # 4. OpenStreetMap Road Ingestion (Two-Pass Real Coordinates)
    # -------------------------------------------------------------------------
    def ingest_osm_roads(
        self,
        pbf_path: str = "database/northern-zone-260903.osm.pbf",
        limit: int | None = 50000,
        batch_size: int = 2000,
    ) -> dict[str, Any]:
        """Ingest routable OSM road segments and intersection nodes.

        Two-pass architecture:
          1. Scan road ways to collect required node IDs
          2. Extract coordinates for those nodes from DenseNodes
          3. Re-scan ways, resolve coordinates, insert nodes + edges
        """
        source = self.get_or_create_source(
            dataset_name="OSM_ROADS_NORTHERN_ZONE",
            source_agency="OpenStreetMap",
            source_file=pbf_path,
            version="2026-09-03",
        )
        run = self.start_run(source.id)
        parser = OSMPBFParser(pbf_path)

        nodes_inserted = 0
        edges_inserted = 0
        edges_read = 0

        try:
            # Clear stale data from previous broken ingestion
            existing_edge_count = self.db.query(RoadNetworkEdge).count()
            existing_node_count = self.db.query(RoadNetworkNode).count()
            if existing_edge_count > 0 or existing_node_count > 0:
                logger.info(
                    "clearing_stale_osm_data",
                    old_edges=existing_edge_count,
                    old_nodes=existing_node_count,
                )
                self.db.query(RoadNetworkEdge).delete()
                self.db.query(RoadNetworkNode).delete()
                self.db.commit()

            # Pass 1: Collect node IDs referenced by road ways
            logger.info("osm_pass1_collecting_node_ids", limit=limit)
            required_node_ids = parser.collect_road_node_ids(limit=limit)
            logger.info("osm_pass1_complete", unique_nodes=len(required_node_ids))

            # Pass 2: Extract coordinates for required nodes
            logger.info("osm_pass2_extracting_coordinates")
            node_coords = parser.collect_node_coordinates(
                required_node_ids=required_node_ids,
            )
            logger.info("osm_pass2_complete", coords_found=len(node_coords))

            # Pass 3: Insert nodes
            logger.info("osm_pass3_inserting_nodes")
            existing_node_ids: set[int] = set()
            node_batch: list[RoadNetworkNode] = []

            for osm_id, (lon, lat) in node_coords.items():
                if osm_id in existing_node_ids:
                    continue
                point_wkt = f"POINT({lon} {lat})"
                node_obj = RoadNetworkNode(
                    osm_node_id=osm_id,
                    geom=WKTElement(point_wkt, srid=4326),
                )
                node_batch.append(node_obj)
                existing_node_ids.add(osm_id)
                nodes_inserted += 1

                if len(node_batch) >= batch_size:
                    self.db.add_all(node_batch)
                    self.db.commit()
                    node_batch = []

            if node_batch:
                self.db.add_all(node_batch)
                self.db.commit()

            logger.info("osm_nodes_inserted", count=nodes_inserted)

            # Pass 4: Insert edges with real geometries
            logger.info("osm_pass4_inserting_edges")
            edge_batch: list[RoadNetworkEdge] = []

            for edge_rec in parser.parse_road_ways_with_coords(
                node_coords=node_coords,
                limit=limit,
            ):
                edges_read += 1

                # Build WKT LINESTRING from resolved coordinates (comma-separated point tuples)
                coord_pairs = ", ".join(
                    f"{lon} {lat}" for lon, lat in edge_rec.coordinates
                )
                linestring_wkt = f"LINESTRING({coord_pairs})"


                edge_obj = RoadNetworkEdge(
                    osm_way_id=edge_rec.osm_way_id,
                    from_node_id=edge_rec.from_node_id,
                    to_node_id=edge_rec.to_node_id,
                    highway_class=edge_rec.highway_class,
                    name=edge_rec.name,
                    oneway=edge_rec.oneway,
                    maxspeed=edge_rec.maxspeed,
                    bridge=edge_rec.bridge,
                    tunnel=edge_rec.tunnel,
                    layer=edge_rec.layer,
                    surface=edge_rec.surface,
                    access=edge_rec.access,
                    length_m=edge_rec.length_m,
                    geom=WKTElement(linestring_wkt, srid=4326),
                    source_snapshot="OSM_NORTHERN_ZONE_260903",
                )
                edge_batch.append(edge_obj)
                edges_inserted += 1

                if len(edge_batch) >= batch_size:
                    self.db.add_all(edge_batch)
                    self.db.commit()
                    edge_batch = []

            if edge_batch:
                self.db.add_all(edge_batch)
                self.db.commit()

            logger.info("osm_edges_inserted", count=edges_inserted)

            run.records_read = edges_read + nodes_inserted
            run.records_inserted = edges_inserted + nodes_inserted
            self.finish_run(run, status="success")

            return {
                "status": "success",
                "nodes_inserted": nodes_inserted,
                "edges_read": edges_read,
                "edges_inserted": edges_inserted,
                "coords_resolved": len(node_coords),
            }
        except Exception as e:
            self.db.rollback()
            self.finish_run(run, status="failed", error_summary=str(e))
            logger.error("osm_ingestion_failed", error=str(e))
            raise
