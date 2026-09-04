"""
Integration tests for Ground Intelligence & Trust-Weighted Reporting API.
"""
from __future__ import annotations

import datetime
import uuid

import pytest
from sqlalchemy import text
from starlette.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.ground_report import GroundReport

client = TestClient(app)


@pytest.fixture
def clean_ground_reports():
    """Cleanup test ground reports and users before/after tests."""
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM ground_report_audits WHERE 1=1;"))
        db.execute(text("DELETE FROM ground_reports WHERE 1=1;"))
        db.execute(text("DELETE FROM users WHERE email LIKE '%@testrisksetu.com';"))
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM ground_report_audits WHERE 1=1;"))
        db.execute(text("DELETE FROM ground_reports WHERE 1=1;"))
        db.execute(text("DELETE FROM users WHERE email LIKE '%@testrisksetu.com';"))
        db.commit()
    finally:
        db.close()


def test_auth_registration_and_login(clean_ground_reports):
    """Test user registration, duplicate email conflict, and login flow."""
    # 1. Register new citizen
    reg_payload = {
        "email": "citizen1@testrisksetu.com",
        "password": "SecurePassword123!",
        "full_name": "Citizen One",
        "role": "citizen",
    }
    r = client.post("/api/v1/auth/register", json=reg_payload)
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["email"] == "citizen1@testrisksetu.com"
    assert data["role"] == "citizen"
    assert "access_token" in data["tokens"]

    # 2. Duplicate registration rejected with 409
    r_dup = client.post("/api/v1/auth/register", json=reg_payload)
    assert r_dup.status_code == 409
    assert r_dup.json()["error"]["code"] == "CONFLICT"

    # 3. Login with wrong password rejected with 401
    r_bad_pw = client.post(
        "/api/v1/auth/login",
        json={"email": "citizen1@testrisksetu.com", "password": "WrongPassword!"},
    )
    assert r_bad_pw.status_code == 401
    assert r_bad_pw.json()["error"]["code"] == "UNAUTHORIZED"

    # 4. Login with correct password succeeds
    r_login = client.post(
        "/api/v1/auth/login",
        json={"email": "citizen1@testrisksetu.com", "password": "SecurePassword123!"},
    )
    assert r_login.status_code == 200
    assert "access_token" in r_login.json()["data"]["tokens"]


def test_ground_report_submission_requires_auth(clean_ground_reports):
    """Submitting report without token must fail with 401 or 403."""
    payload = {
        "latitude": 30.3165,
        "longitude": 78.0322,
        "report_type": "LANDSLIDE",
        "description": "Debris and mud blocking lower road corridor",
        "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    r = client.post("/api/v1/ground-reports", json=payload)
    # FastAPI HTTPBearer returns 403 or 401 when header is missing
    assert r.status_code in (401, 403)


def test_ground_report_submission_and_persistence(clean_ground_reports):
    """Submit fresh report with valid auth, verify envelope, trust breakdown, and DB persistence."""
    # Register citizen
    r_reg = client.post(
        "/api/v1/auth/register",
        json={"email": "observer@testrisksetu.com", "password": "Password123!"},
    )
    token = r_reg.json()["data"]["tokens"]["access_token"]
    user_id = r_reg.json()["data"]["user_id"]

    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "latitude": 30.3165,
        "longitude": 78.0322,
        "report_type": "ROCKFALL",
        "description": "Multiple large boulders rolling onto highway shoulder",
        "observed_at": now.isoformat(),
        "source_metadata": {"device": "mobile_app", "accuracy_m": 8.5},
    }

    resp = client.post(
        "/api/v1/ground-reports",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "data" in body
    data = body["data"]

    assert data["report_type"] == "ROCKFALL"
    assert data["user_id"] == user_id
    assert data["is_duplicate"] is False
    assert 0.0 <= data["trust"]["trust_score"] <= 100.0
    assert data["trust"]["trust_class"] in ("LOW", "MODERATE", "HIGH", "VERY_HIGH")
    assert len(data["explanation"]) > 0
    assert len(data["limitations"]) > 0

    # Verify DB persistence
    report_id = uuid.UUID(data["report_id"])
    db = SessionLocal()
    try:
        db_report = db.query(GroundReport).filter(GroundReport.id == report_id).first()
        assert db_report is not None
        assert db_report.description == "Multiple large boulders rolling onto highway shoulder"
        assert db_report.status == "SUBMITTED"
    finally:
        db.close()


def test_idempotency_key_replay(clean_ground_reports):
    """Submitting with identical Idempotency-Key returns cached response without duplicate DB insert."""
    r_reg = client.post(
        "/api/v1/auth/register",
        json={"email": "idem_user@testrisksetu.com", "password": "Password123!"},
    )
    token = r_reg.json()["data"]["tokens"]["access_token"]

    idempotency_key = f"key-{uuid.uuid4().hex}"
    payload = {
        "latitude": 30.35,
        "longitude": 78.05,
        "report_type": "CRACK",
        "description": "Longitudinal tension crack expanding on pavement surface",
        "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    # First request
    r1 = client.post(
        "/api/v1/ground-reports",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key},
    )
    assert r1.status_code == 201
    rep1_id = r1.json()["data"]["report_id"]

    # Second request with same idempotency key
    r2 = client.post(
        "/api/v1/ground-reports",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key},
    )
    assert r2.status_code in (200, 201)
    assert r2.json()["data"]["report_id"] == rep1_id


def test_near_duplicate_detection(clean_ground_reports):
    """Submitting repeated report near same location and time flags duplicate status."""
    r_reg = client.post(
        "/api/v1/auth/register",
        json={"email": "dup_tester@testrisksetu.com", "password": "Password123!"},
    )
    token = r_reg.json()["data"]["tokens"]["access_token"]

    now = datetime.datetime.now(datetime.timezone.utc)
    payload1 = {
        "latitude": 30.4000,
        "longitude": 78.1000,
        "report_type": "ROAD_BLOCKAGE",
        "description": "Landslide completely blocking road corridor near milestone 12",
        "observed_at": now.isoformat(),
    }
    r1 = client.post(
        "/api/v1/ground-reports",
        json=payload1,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 201
    assert r1.json()["data"]["is_duplicate"] is False

    # Second submission by same user 50 meters away within same hour
    payload2 = {
        "latitude": 30.4003,
        "longitude": 78.1002,
        "report_type": "ROAD_BLOCKAGE",
        "description": "Landslide completely blocking road corridor near milestone 12 again",
        "observed_at": (now - datetime.timedelta(minutes=15)).isoformat(),
    }
    r2 = client.post(
        "/api/v1/ground-reports",
        json=payload2,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 201
    data2 = r2.json()["data"]
    assert data2["is_duplicate"] is True
    assert data2["status"] == "DUPLICATE"
    assert data2["risk_influence_eligible"] is False
    assert data2["duplicate_of_id"] == r1.json()["data"]["report_id"]


def test_multi_observer_corroboration(clean_ground_reports):
    """Independent nearby reports by different users raise corroboration score."""
    # User 1
    r_u1 = client.post(
        "/api/v1/auth/register",
        json={"email": "user1_corrob@testrisksetu.com", "password": "Password123!"},
    )
    token1 = r_u1.json()["data"]["tokens"]["access_token"]

    # User 2
    r_u2 = client.post(
        "/api/v1/auth/register",
        json={"email": "user2_corrob@testrisksetu.com", "password": "Password123!"},
    )
    token2 = r_u2.json()["data"]["tokens"]["access_token"]

    now = datetime.datetime.now(datetime.timezone.utc)

    # User 1 submits report
    payload1 = {
        "latitude": 30.5000,
        "longitude": 78.2000,
        "report_type": "LANDSLIDE",
        "description": "Slope movement observed after continuous rainfall on north ridge",
        "observed_at": now.isoformat(),
    }
    r1 = client.post(
        "/api/v1/ground-reports",
        json=payload1,
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert r1.status_code == 201
    rep1_id = r1.json()["data"]["report_id"]
    initial_corrob = r1.json()["data"]["trust"]["components"]["corroboration"]
    assert initial_corrob == 0.0  # 0 initial observers

    # User 2 submits compatible report 500m away
    payload2 = {
        "latitude": 30.5030,
        "longitude": 78.2020,
        "report_type": "SLOPE_MOVEMENT",
        "description": "Fresh mudslide and rolling rocks downhill on adjacent road",
        "observed_at": (now - datetime.timedelta(hours=1)).isoformat(),
    }
    r2 = client.post(
        "/api/v1/ground-reports",
        json=payload2,
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert r2.status_code == 201
    # User 2 gets corroboration from User 1
    user2_corrob = r2.json()["data"]["trust"]["components"]["corroboration"]
    assert user2_corrob > 0.0

    # Recalculate User 1's report to reflect new corroboration
    r_recalc = client.post(
        f"/api/v1/ground-reports/{rep1_id}/recalculate-trust",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert r_recalc.status_code == 200
    recalc_corrob = r_recalc.json()["data"]["trust"]["components"]["corroboration"]
    assert recalc_corrob > 0.0
    assert recalc_corrob > initial_corrob


def test_get_report_and_pagination(clean_ground_reports):
    """Test single report retrieval, 404 handling, and paginated listing with filters."""
    r_reg = client.post(
        "/api/v1/auth/register",
        json={"email": "list_user@testrisksetu.com", "password": "Password123!"},
    )
    token = r_reg.json()["data"]["tokens"]["access_token"]

    # Submit 3 reports
    for i in range(3):
        client.post(
            "/api/v1/ground-reports",
            json={
                "latitude": 30.1 + i * 0.1,
                "longitude": 78.1 + i * 0.1,
                "report_type": "DEBRIS",
                "description": f"Debris accumulation on road section {i} after rains",
                "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    # 1. Paginated list
    r_list = client.get(
        "/api/v1/ground-reports?limit=2&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_list.status_code == 200
    list_data = r_list.json()["data"]
    assert list_data["total_count"] >= 3
    assert len(list_data["reports"]) == 2

    # 2. Filter by report type
    r_filt = client.get(
        "/api/v1/ground-reports?report_type=DEBRIS",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_filt.status_code == 200
    assert all(item["report_type"] == "DEBRIS" for item in r_filt.json()["data"]["reports"])

    # 3. Get single report
    rep_id = list_data["reports"][0]["report_id"]
    r_single = client.get(
        f"/api/v1/ground-reports/{rep_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_single.status_code == 200
    assert r_single.json()["data"]["report_id"] == rep_id

    # 4. Nonexistent report -> 404
    bad_id = uuid.uuid4()
    r_404 = client.get(
        f"/api/v1/ground-reports/{bad_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_404.status_code == 404
    assert r_404.json()["error"]["code"] == "NOT_FOUND"


def test_status_moderation_rbac(clean_ground_reports):
    """Officials/admins can update status; regular citizens are forbidden."""
    # Register regular citizen
    r_cit = client.post(
        "/api/v1/auth/register",
        json={"email": "plain_citizen@testrisksetu.com", "password": "Password123!", "role": "citizen"},
    )
    cit_token = r_cit.json()["data"]["tokens"]["access_token"]

    # Register official
    r_off = client.post(
        "/api/v1/auth/register",
        json={"email": "dm_official@testrisksetu.com", "password": "Password123!", "role": "official"},
    )
    off_token = r_off.json()["data"]["tokens"]["access_token"]

    # Citizen submits report
    r_rep = client.post(
        "/api/v1/ground-reports",
        json={
            "latitude": 30.6000,
            "longitude": 78.3000,
            "report_type": "DRAINAGE_BLOCKAGE",
            "description": "Culvert blocked by gravel and timber debris causing water overflow",
            "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        headers={"Authorization": f"Bearer {cit_token}"},
    )
    rep_id = r_rep.json()["data"]["report_id"]

    # Citizen attempts to moderate -> 403 Forbidden
    r_cit_mod = client.patch(
        f"/api/v1/ground-reports/{rep_id}/status",
        json={"status": "ACCEPTED", "reason": "Self-validating report"},
        headers={"Authorization": f"Bearer {cit_token}"},
    )
    assert r_cit_mod.status_code == 403
    assert r_cit_mod.json()["error"]["code"] == "FORBIDDEN"

    # Official moderates -> 200 OK
    r_off_mod = client.patch(
        f"/api/v1/ground-reports/{rep_id}/status",
        json={"status": "ACCEPTED", "reason": "Field inspection by local engineer confirmed"},
        headers={"Authorization": f"Bearer {off_token}"},
    )
    assert r_off_mod.status_code == 200
    assert r_off_mod.json()["data"]["status"] == "ACCEPTED"


def test_database_immutability_of_prior_phases(clean_ground_reports):
    """Verify that Phase 1B/2A tables remain completely unchanged during ground report operations."""
    db = SessionLocal()
    try:
        edges_before = db.execute(text("SELECT count(*) FROM road_network_edges")).scalar()
        nodes_before = db.execute(text("SELECT count(*) FROM road_network_nodes")).scalar()
        slides_before = db.execute(text("SELECT count(*) FROM historical_landslides")).scalar()
    finally:
        db.close()

    # Submit and retrieve multiple reports
    r_reg = client.post(
        "/api/v1/auth/register",
        json={"email": "immutability_user@testrisksetu.com", "password": "Password123!"},
    )
    token = r_reg.json()["data"]["tokens"]["access_token"]

    for i in range(3):
        client.post(
            "/api/v1/ground-reports",
            json={
                "latitude": 30.1 + i * 0.05,
                "longitude": 78.1 + i * 0.05,
                "report_type": "SLOPE_MOVEMENT",
                "description": f"Minor slope shifting along terrace line number {i}",
                "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    db = SessionLocal()
    try:
        edges_after = db.execute(text("SELECT count(*) FROM road_network_edges")).scalar()
        nodes_after = db.execute(text("SELECT count(*) FROM road_network_nodes")).scalar()
        slides_after = db.execute(text("SELECT count(*) FROM historical_landslides")).scalar()

        assert edges_before == edges_after
        assert nodes_before == nodes_after
        assert slides_before == slides_after
    finally:
        db.close()
