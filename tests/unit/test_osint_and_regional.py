"""
Unit tests for isolated OSINT and Regional Watch endpoints.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_osint_leads():
    response = client.get("/api/v1/osint")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "meta" in data
    assert isinstance(data["data"], list)
    if len(data["data"]) >= 1:
        first = data["data"][0]
        assert "area" in first
        assert "hazard" in first
        assert "corroboration_score" in first
        assert "recommended_action" in first
        assert first["recommended_action"] in ("OFFICER_REVIEW", "PREPARE_EVACUATION_REVIEW")


def test_trigger_osint_scan():
    response = client.post("/api/v1/osint/scan")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["meta"]["scanned"] is True


def test_get_regional_watches():
    response = client.get("/api/v1/regional-watch")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "meta" in data
    assert isinstance(data["data"], list)


def test_get_regional_impact():
    response = client.get("/api/v1/regional-watch/impact?lat=30.2936&lon=79.5603")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "meta" in data
    assert isinstance(data["data"], list)
