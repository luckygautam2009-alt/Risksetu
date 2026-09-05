"""
Unit tests for Spatial Viewport Endpoints:
- GET /api/v1/landslides (GSI historical inventory)
- GET /api/v1/roads (OSM road network edges)
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_landslides_without_bbox():
    response = client.get("/api/v1/landslides?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "total_count" in body["data"]
    assert "items" in body["data"]
    assert isinstance(body["data"]["items"], list)
    assert len(body["data"]["items"]) <= 10
    if len(body["data"]["items"]) > 0:
        item = body["data"]["items"][0]
        assert "gsi_slide_no" in item
        assert "latitude" in item
        assert "longitude"
        assert item["source_dataset"] == "GSI_NLSM_PDF"


def test_get_landslides_with_bbox():
    # Uttarakhand Chamoli Bounding Box
    response = client.get("/api/v1/landslides?min_lat=30.0&max_lat=31.0&min_lon=79.0&max_lon=80.0&limit=25")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert body["data"]["total_count"] >= 0
    assert isinstance(body["data"]["items"], list)
    for item in body["data"]["items"]:
        assert 30.0 <= item["latitude"] <= 31.0
        assert 79.0 <= item["longitude"] <= 80.0


def test_get_roads_with_bbox():
    # Northern zone road network bbox
    response = client.get("/api/v1/roads?min_lat=28.0&max_lat=32.0&min_lon=76.0&max_lon=80.0&limit=25")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "items" in body["data"]
    assert isinstance(body["data"]["items"], list)
    if len(body["data"]["items"]) > 0:
        road = body["data"]["items"][0]
        assert "osm_way_id" in road
        assert "highway_class" in road
        assert "coordinates" in road
