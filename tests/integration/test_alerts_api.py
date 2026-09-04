"""
Integration tests for Phase 4 Operational Alert Generation & Decision Support API.
"""
from __future__ import annotations

import uuid
import pytest
from sqlalchemy import text
from starlette.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User

client = TestClient(app)


@pytest.fixture
def clean_alerts_db():
    """Cleanup test alerts and users before and after test execution."""
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM alert_audits WHERE 1=1;"))
        db.execute(text("DELETE FROM alerts WHERE 1=1;"))
        db.execute(text("DELETE FROM users WHERE email LIKE '%@testrisksetu.com';"))
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM alert_audits WHERE 1=1;"))
        db.execute(text("DELETE FROM alerts WHERE 1=1;"))
        db.execute(text("DELETE FROM users WHERE email LIKE '%@testrisksetu.com';"))
        db.commit()
    finally:
        db.close()


@pytest.fixture
def test_users(clean_alerts_db):
    """Creates citizen, official, and admin users and returns their JWT headers."""
    db = SessionLocal()
    try:
        citizen_id = uuid.uuid4()
        official_id = uuid.uuid4()
        admin_id = uuid.uuid4()

        citizen = User(
            id=citizen_id,
            email="citizen@testrisksetu.com",
            hashed_password=hash_password("Pass123!"),
            full_name="Citizen User",
            role="citizen",
        )
        official = User(
            id=official_id,
            email="official@testrisksetu.com",
            hashed_password=hash_password("Pass123!"),
            full_name="Official User",
            role="official",
        )
        admin = User(
            id=admin_id,
            email="admin@testrisksetu.com",
            hashed_password=hash_password("Pass123!"),
            full_name="Admin User",
            role="admin",
        )
        db.add_all([citizen, official, admin])
        db.commit()

        citizen_token = create_access_token(str(citizen_id))
        official_token = create_access_token(str(official_id))
        admin_token = create_access_token(str(admin_id))

        return {
            "citizen": {"headers": {"Authorization": f"Bearer {citizen_token}"}, "id": citizen_id},
            "official": {"headers": {"Authorization": f"Bearer {official_token}"}, "id": official_id},
            "admin": {"headers": {"Authorization": f"Bearer {admin_token}"}, "id": admin_id},
        }
    finally:
        db.close()


def test_generate_critical_risk_alert(test_users):
    """Generates an operational alert from critical landslide risk parameters."""
    headers = test_users["official"]["headers"]
    payload = {
        "latitude": 30.555,
        "longitude": 79.123,
        "risk_score": 0.85,
        "risk_level": "CRITICAL",
        "risk_confidence": 0.90,
        "isolation_severity": "CRITICAL",
    }
    r = client.post("/api/v1/alerts/generate", json=payload, headers=headers)
    assert r.status_code == 201
    res = r.json()
    data = res["data"]
    meta = res["meta"]

    assert meta["was_created"] is True
    assert data["severity"] == "CRITICAL"
    assert data["status"] == "ACTIVE"
    assert data["risk_score"] == 0.85
    assert len(data["recommended_actions"]) >= 2
    assert "REC_FIELD_VERIFY_URGENT" in [a["action_id"] for a in data["recommended_actions"]]
    assert "explanation" in data
    assert len(data["explanation"]["system_limitations"]) >= 1


def test_generate_alert_risk_not_equal_priority(test_users):
    """Demonstrates RISK != PRIORITY principle: moderate risk with high priority yields HIGH alert."""
    headers = test_users["official"]["headers"]
    payload = {
        "latitude": 30.400,
        "longitude": 79.200,
        "risk_score": 0.35,
        "risk_level": "MODERATE",
        "priority_score": 0.78,
        "priority_level": "CRITICAL",
        "isolation_severity": "HIGH",
    }
    r = client.post("/api/v1/alerts/generate", json=payload, headers=headers)
    assert r.status_code == 201
    data = r.json()["data"]

    # Even though physical risk is MODERATE, alert severity is CRITICAL due to operational priority
    assert data["severity"] == "CRITICAL"
    assert data["alert_type"] == "CRITICAL_PRIORITY"
    assert data["priority_score"] == 0.78


def test_alert_deduplication(test_users):
    """Repeated calls for the same event return the existing active alert without creating duplicates."""
    headers = test_users["official"]["headers"]
    payload = {
        "latitude": 30.650,
        "longitude": 79.350,
        "risk_score": 0.65,
        "risk_level": "HIGH",
    }
    # 1. First creation
    r1 = client.post("/api/v1/alerts/generate", json=payload, headers=headers)
    assert r1.status_code == 201
    alert_id_1 = r1.json()["data"]["id"]
    assert r1.json()["meta"]["was_created"] is True

    # 2. Second creation at slightly shifted coords within 100m bucket
    payload2 = {
        "latitude": 30.6502,
        "longitude": 79.3503,
        "risk_score": 0.65,
        "risk_level": "HIGH",
    }
    r2 = client.post("/api/v1/alerts/generate", json=payload2, headers=headers)
    assert r2.status_code == 201
    alert_id_2 = r2.json()["data"]["id"]
    assert r2.json()["meta"]["was_created"] is False
    assert alert_id_1 == alert_id_2


def test_list_and_get_alerts_api(test_users):
    """Tests query filtering, pagination, and single alert retrieval."""
    headers = test_users["official"]["headers"]

    # Create two alerts
    client.post("/api/v1/alerts/generate", json={"latitude": 30.1, "longitude": 79.1, "risk_score": 0.8}, headers=headers)
    client.post("/api/v1/alerts/generate", json={"latitude": 30.2, "longitude": 79.2, "risk_score": 0.5}, headers=headers)

    # List alerts
    r_list = client.get("/api/v1/alerts?limit=10&offset=0", headers=headers)
    assert r_list.status_code == 200
    list_data = r_list.json()["data"]
    assert list_data["total_count"] >= 2
    assert len(list_data["alerts"]) >= 2

    # Get single alert
    alert_id = list_data["alerts"][0]["id"]
    r_single = client.get(f"/api/v1/alerts/{alert_id}", headers=headers)
    assert r_single.status_code == 200
    assert r_single.json()["data"]["id"] == alert_id


def test_alert_lifecycle_rbac_and_transitions(test_users):
    """Tests complete lifecycle workflow, RBAC permissions, and audit logging."""
    citizen_headers = test_users["citizen"]["headers"]
    official_headers = test_users["official"]["headers"]

    # 1. Create alert
    r = client.post("/api/v1/alerts/generate", json={"latitude": 30.8, "longitude": 79.5, "risk_score": 0.8}, headers=official_headers)
    alert_id = r.json()["data"]["id"]

    # 2. Citizen attempt to acknowledge -> 403 Forbidden
    r_cit_ack = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", json={"reason": "Citizen attempt"}, headers=citizen_headers)
    assert r_cit_ack.status_code == 403

    # 3. Official acknowledges -> 200 OK
    r_off_ack = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", json={"reason": "Dispatched response unit"}, headers=official_headers)
    assert r_off_ack.status_code == 200
    assert r_off_ack.json()["data"]["status"] == "ACKNOWLEDGED"
    assert r_off_ack.json()["data"]["acknowledged_by"] is not None

    # 4. Official resolves -> 200 OK
    r_off_res = client.post(f"/api/v1/alerts/{alert_id}/resolve", json={"reason": "Slope stabilization mesh installed"}, headers=official_headers)
    assert r_off_res.status_code == 200
    assert r_off_res.json()["data"]["status"] == "RESOLVED"
    assert r_off_res.json()["data"]["resolved_by"] is not None

    # 5. Resolving already resolved alert -> 409 Conflict
    r_dup_res = client.post(f"/api/v1/alerts/{alert_id}/resolve", json={"reason": "Again"}, headers=official_headers)
    assert r_dup_res.status_code == 409

    # 6. Create another alert and test dismiss
    r_new = client.post("/api/v1/alerts/generate", json={"latitude": 30.85, "longitude": 79.55, "risk_score": 0.8}, headers=official_headers)
    new_alert_id = r_new.json()["data"]["id"]
    r_dis = client.post(f"/api/v1/alerts/{new_alert_id}/dismiss", json={"reason": "False alarm confirmed by drone"}, headers=official_headers)
    assert r_dis.status_code == 200
    assert r_dis.json()["data"]["status"] == "DISMISSED"
    assert r_dis.json()["data"]["resolved_by"] is not None


def test_alert_not_found(test_users):
    """Retrieving non-existent alert returns 404."""
    headers = test_users["official"]["headers"]
    fake_id = uuid.uuid4()
    r = client.get(f"/api/v1/alerts/{fake_id}", headers=headers)
    assert r.status_code == 404


def test_alert_filters(test_users):
    """Test status, severity, and type filters."""
    headers = test_users["official"]["headers"]
    client.post("/api/v1/alerts/generate", json={"latitude": 30.11, "longitude": 79.11, "risk_score": 0.85}, headers=headers)
    client.post("/api/v1/alerts/generate", json={"latitude": 30.12, "longitude": 79.12, "isolation_severity": "HIGH"}, headers=headers)

    r_crit = client.get("/api/v1/alerts?severity=CRITICAL", headers=headers)
    assert r_crit.status_code == 200
    assert all(a["severity"] == "CRITICAL" for a in r_crit.json()["data"]["alerts"])

    r_act = client.get("/api/v1/alerts?status=ACTIVE", headers=headers)
    assert r_act.status_code == 200
    assert all(a["status"] == "ACTIVE" for a in r_act.json()["data"]["alerts"])


def test_alert_input_validation(test_users):
    """Tests invalid inputs produce 422 Unprocessable Entity."""
    headers = test_users["official"]["headers"]

    # Latitude out of range
    r1 = client.post("/api/v1/alerts/generate", json={"latitude": 100.0, "longitude": 79.0}, headers=headers)
    assert r1.status_code == 422

    # Risk score > 1.0
    r2 = client.post("/api/v1/alerts/generate", json={"latitude": 30.0, "longitude": 79.0, "risk_score": 1.5}, headers=headers)
    assert r2.status_code == 422

