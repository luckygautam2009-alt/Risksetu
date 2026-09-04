"""
Integration tests for the Road Blockage Isolation Impact Simulation API.
"""
from __future__ import annotations

import uuid
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_simulation_validation_errors():
    """Verify input validation rejects invalid coordinates and radiuses."""
    # Latitude out of bounds
    resp = client.post(
        "/api/v1/impact/simulate-road-blockage",
        json={"latitude": 105.0, "longitude": 78.0},
    )
    assert resp.status_code == 422

    # Longitude out of bounds
    resp = client.post(
        "/api/v1/impact/simulate-road-blockage",
        json={"latitude": 30.0, "longitude": 200.0},
    )
    assert resp.status_code == 422

    # Negative radius
    resp = client.post(
        "/api/v1/impact/simulate-road-blockage",
        json={"latitude": 30.0, "longitude": 78.0, "radius_m": -50.0},
    )
    assert resp.status_code == 422

    # Extra fields forbidden
    resp = client.post(
        "/api/v1/impact/simulate-road-blockage",
        json={"latitude": 30.0, "longitude": 78.0, "unknown_field": 123},
    )
    assert resp.status_code == 422


def test_simulation_nonexistent_edge_id():
    """Verify requesting a non-existent edge UUID returns 404 NOT_FOUND."""
    random_id = str(uuid.uuid4())
    resp = client.post(
        "/api/v1/impact/simulate-road-blockage",
        json={
            "latitude": 30.3165,
            "longitude": 78.0322,
            "blocked_edge_id": random_id,
        },
    )
    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"


def test_simulation_no_roads_within_search_radius():
    """Verify requesting coordinates with no roads nearby returns 404 NOT_FOUND."""
    resp = client.post(
        "/api/v1/impact/simulate-road-blockage",
        json={
            "latitude": 0.0,
            "longitude": 0.0,
            "search_radius_m": 100.0,
        },
    )
    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"


def test_simulation_success_end_to_end():
    """Verify successful what-if simulation on real road network data."""
    resp = client.post(
        "/api/v1/impact/simulate-road-blockage",
        json={
            "latitude": 28.6723,
            "longitude": 77.2309,
            "radius_m": 3000.0,
            "search_radius_m": 1000.0,
        },
    )
    assert resp.status_code == 200
    res = resp.json()

    # Verify standard envelope structure
    assert "data" in res
    assert "meta" in res
    assert "request_id" in res["meta"]

    data = res["data"]
    assert data["simulation_type"] == "WHAT_IF_SCENARIO"
    assert data["target_location"]["latitude"] == 28.6723
    assert data["target_location"]["longitude"] == 77.2309

    # Verify blocked edge info
    blocked_edge = data["blocked_edge"]
    assert blocked_edge["from_node_id"] > 0
    assert blocked_edge["to_node_id"] > 0
    assert blocked_edge["highway_class"] is not None
    assert blocked_edge["length_m"] > 0.0

    # Verify connectivity impact
    impact = data["connectivity_impact"]
    assert impact["components_before"] >= 1
    assert impact["components_after"] >= 1
    assert isinstance(impact["is_bridge_edge"], bool)

    # Verify severity and limitations
    assert 0.0 <= data["isolation_severity"] <= 100.0
    assert len(data["limitations"]) >= 3
    assert any("WHAT-IF" in lim for lim in data["limitations"])
    assert any("Census" in lim for lim in data["limitations"])


def test_simulation_explicit_edge_uuid_targeting():
    """Verify simulation correctly targets a specific edge UUID."""
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.road import RoadNetworkEdge

    db = SessionLocal()
    try:
        sample_edge = db.scalars(select(RoadNetworkEdge).limit(1)).first()
        assert sample_edge is not None
        edge_id = str(sample_edge.id)
    finally:
        db.close()

    resp = client.post(
        "/api/v1/impact/simulate-road-blockage",
        json={
            "latitude": 28.6723,
            "longitude": 77.2309,
            "radius_m": 3000.0,
            "blocked_edge_id": edge_id,
        },
    )
    assert resp.status_code == 200
    res = resp.json()
    assert res["data"]["blocked_edge"]["edge_db_id"] == edge_id
    assert res["data"]["blocked_edge"]["osm_way_id"] == sample_edge.osm_way_id


def test_simulation_database_immutability():
    """Verify that what-if simulation is strictly non-destructive on PostgreSQL database."""
    from sqlalchemy import func, select
    from app.db.session import SessionLocal
    from app.models.road import RoadNetworkEdge, RoadNetworkNode

    db = SessionLocal()
    try:
        # Pre-simulation state
        edges_before = db.scalar(select(func.count()).select_from(RoadNetworkEdge))
        nodes_before = db.scalar(select(func.count()).select_from(RoadNetworkNode))
        sample_edge = db.scalars(select(RoadNetworkEdge).limit(1)).first()
        assert sample_edge is not None
        edge_id = sample_edge.id
        orig_way_id = sample_edge.osm_way_id
        orig_length = sample_edge.length_m
        orig_name = sample_edge.name
    finally:
        db.close()

    # Execute simulation
    resp = client.post(
        "/api/v1/impact/simulate-road-blockage",
        json={
            "latitude": 28.6723,
            "longitude": 77.2309,
            "radius_m": 3000.0,
            "blocked_edge_id": str(edge_id),
        },
    )
    assert resp.status_code == 200

    # Post-simulation verification
    db = SessionLocal()
    try:
        edges_after = db.scalar(select(func.count()).select_from(RoadNetworkEdge))
        nodes_after = db.scalar(select(func.count()).select_from(RoadNetworkNode))
        edge_after = db.get(RoadNetworkEdge, edge_id)

        assert edges_before == edges_after, "RoadNetworkEdge count must remain strictly unchanged"
        assert nodes_before == nodes_after, "RoadNetworkNode count must remain strictly unchanged"
        assert edge_after is not None, "Targeted edge must still exist in database"
        assert edge_after.osm_way_id == orig_way_id
        assert edge_after.length_m == orig_length
        assert edge_after.name == orig_name
    finally:
        db.close()


def test_simulation_determinism():
    """Verify running the simulation twice yields identical metrics and structure."""
    payload = {
        "latitude": 28.6723,
        "longitude": 77.2309,
        "radius_m": 3000.0,
        "search_radius_m": 1000.0,
    }

    resp1 = client.post("/api/v1/impact/simulate-road-blockage", json=payload)
    resp2 = client.post("/api/v1/impact/simulate-road-blockage", json=payload)

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    d1 = resp1.json()["data"]
    d2 = resp2.json()["data"]

    assert d1["blocked_edge"]["edge_db_id"] == d2["blocked_edge"]["edge_db_id"]
    assert d1["connectivity_impact"] == d2["connectivity_impact"]
    assert d1["isolation_severity"] == d2["isolation_severity"]
    assert d1["isolated_components"] == d2["isolated_components"]
    assert d1["graph_stats_before"] == d2["graph_stats_before"]
    assert d1["graph_stats_after"] == d2["graph_stats_after"]


