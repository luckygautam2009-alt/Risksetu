import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.main import app
from app.models.road import RoadNetworkEdge, RoadNetworkNode


def _seed_test_road_network() -> None:
    """Seeds baseline road network nodes and edges if the database is empty."""
    db = SessionLocal()
    try:
        edge_count = db.scalar(select(func.count()).select_from(RoadNetworkEdge)) or 0
        if edge_count > 0:
            return

        test_nodes = [
            # Delhi Cluster (28.6723, 77.2309)
            (10001, "POINT(77.2290 28.6710)"),
            (10002, "POINT(77.2309 28.6723)"),
            (10003, "POINT(77.2320 28.6735)"),
            (10004, "POINT(77.2335 28.6745)"),
            # Ludhiana Cluster (30.8933, 75.8708)
            (20001, "POINT(75.8690 30.8920)"),
            (20002, "POINT(75.8708 30.8933)"),
            (20003, "POINT(75.8720 30.8945)"),
            (20004, "POINT(75.8735 30.8960)"),
            # Chamoli Cluster (30.2936, 79.5603)
            (30001, "POINT(79.5590 30.2920)"),
            (30002, "POINT(79.5603 30.2936)"),
            (30003, "POINT(79.5615 30.2950)"),
        ]

        node_objs = [
            RoadNetworkNode(
                osm_node_id=osm_id,
                geom=WKTElement(wkt, srid=4326),
            )
            for osm_id, wkt in test_nodes
        ]
        db.add_all(node_objs)
        db.commit()

        test_edges = [
            # Delhi Cluster
            (5873630, 10001, 10002, "Mahatma Gandhi Marg", "trunk", 280.0, False, "LINESTRING(77.2290 28.6710, 77.2309 28.6723)"),
            (5873631, 10002, 10003, "Ring Road Arterial", "primary", 310.0, True, "LINESTRING(77.2309 28.6723, 77.2320 28.6735)"),
            (5873632, 10003, 10004, "Yamuna Bypass", "secondary", 240.0, False, "LINESTRING(77.2320 28.6735, 77.2335 28.6745)"),
            # Ludhiana Cluster
            (6873630, 20001, 20002, "Grand Trunk Road", "trunk", 350.0, False, "LINESTRING(75.8690 30.8920, 75.8708 30.8933)"),
            (6873631, 20002, 20003, "Northern Bypass", "primary", 290.0, True, "LINESTRING(75.8708 30.8933, 75.8720 30.8945)"),
            (6873632, 20003, 20004, "Canal Link Road", "secondary", 320.0, False, "LINESTRING(75.8720 30.8945, 75.8735 30.8960)"),
            # Chamoli Cluster
            (14930128, 30001, 30002, "Badrinath National Highway NH-58", "primary", 420.0, False, "LINESTRING(79.5590 30.2920, 79.5603 30.2936)"),
            (14930129, 30002, 30003, "Joshimath Arterial", "primary", 380.0, True, "LINESTRING(79.5603 30.2936, 79.5615 30.2950)"),
        ]

        edge_objs = [
            RoadNetworkEdge(
                osm_way_id=way_id,
                from_node_id=from_id,
                to_node_id=to_id,
                name=name,
                highway_class=hclass,
                length_m=length,
                bridge=bridge,
                geom=WKTElement(wkt, srid=4326),
                source_snapshot="TEST_FIXTURE",
            )
            for way_id, from_id, to_id, name, hclass, length, bridge, wkt in test_edges
        ]
        db.add_all(edge_objs)
        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def run_database_migrations():
    """Ensure database schema is up-to-date and seeded before running tests."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    _seed_test_road_network()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
