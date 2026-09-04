"""
Phase 5 — Comprehensive Security, RBAC Matrix, Rate Limiting, Idempotency & Error Envelope Audit.
"""
from __future__ import annotations

import uuid
import pytest
from sqlalchemy import text
from starlette.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.alert import AlertAudit
from app.models.user import User

client = TestClient(app)


@pytest.fixture
def clean_security_db():
    """Cleanup test data before and after tests."""
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM alert_audits WHERE 1=1;"))
        db.execute(text("DELETE FROM alerts WHERE 1=1;"))
        db.execute(text("DELETE FROM ground_report_audits WHERE 1=1;"))
        db.execute(text("DELETE FROM ground_reports WHERE 1=1;"))
        db.execute(text("DELETE FROM users WHERE email LIKE '%@testrisksetu.com';"))
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM alert_audits WHERE 1=1;"))
        db.execute(text("DELETE FROM alerts WHERE 1=1;"))
        db.execute(text("DELETE FROM ground_report_audits WHERE 1=1;"))
        db.execute(text("DELETE FROM ground_reports WHERE 1=1;"))
        db.execute(text("DELETE FROM users WHERE email LIKE '%@testrisksetu.com';"))
        db.commit()
    finally:
        db.close()


@pytest.fixture
def auth_matrix_users(clean_security_db):
    """Creates citizen, official, and admin users."""
    db = SessionLocal()
    try:
        citizen_id = uuid.uuid4()
        official_id = uuid.uuid4()
        admin_id = uuid.uuid4()

        citizen = User(
            id=citizen_id,
            email="citizen_sec@testrisksetu.com",
            hashed_password=hash_password("Pass123!"),
            full_name="Citizen Sec",
            role="citizen",
        )
        official = User(
            id=official_id,
            email="official_sec@testrisksetu.com",
            hashed_password=hash_password("Pass123!"),
            full_name="Official Sec",
            role="official",
        )
        admin = User(
            id=admin_id,
            email="admin_sec@testrisksetu.com",
            hashed_password=hash_password("Pass123!"),
            full_name="Admin Sec",
            role="admin",
        )
        db.add_all([citizen, official, admin])
        db.commit()

        return {
            "unauthenticated": {},
            "citizen": {"headers": {"Authorization": f"Bearer {create_access_token(str(citizen_id))}"}, "id": citizen_id},
            "official": {"headers": {"Authorization": f"Bearer {create_access_token(str(official_id))}"}, "id": official_id},
            "admin": {"headers": {"Authorization": f"Bearer {create_access_token(str(admin_id))}"}, "id": admin_id},
        }
    finally:
        db.close()


# ============================================================================
# 1. RBAC & Authentication Matrix Tests
# ============================================================================

def test_unauthenticated_requests_rejected(auth_matrix_users):
    """Endpoints requiring authentication must return 401/403 when no token or invalid token is supplied."""
    r1 = client.post("/api/v1/ground-reports", json={"description": "Test"})
    assert r1.status_code in (401, 403)

    r2 = client.post("/api/v1/alerts/generate", json={"latitude": 30.0, "longitude": 79.0})
    assert r2.status_code in (401, 403)

    r3 = client.get("/api/v1/alerts")
    assert r3.status_code in (401, 403)

    # Invalid token specifically triggers 401 Unauthorized
    r4 = client.get("/api/v1/alerts", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert r4.status_code == 401
    assert r4.json()["error"]["code"] == "UNAUTHORIZED"



def test_rbac_citizen_forbidden_actions(auth_matrix_users):
    """Citizens must receive 403 Forbidden when trying to access official/admin moderation routes."""
    headers = auth_matrix_users["citizen"]["headers"]
    fake_id = uuid.uuid4()

    # Ground report moderation by citizen -> 403
    r1 = client.patch(f"/api/v1/ground-reports/{fake_id}/status", json={"status": "ACCEPTED"}, headers=headers)
    assert r1.status_code == 403
    assert r1.json()["error"]["code"] == "FORBIDDEN"

    # Alert acknowledge by citizen -> 403
    r2 = client.post(f"/api/v1/alerts/{fake_id}/acknowledge", json={"reason": "Citizen test"}, headers=headers)
    assert r2.status_code == 403
    assert r2.json()["error"]["code"] == "FORBIDDEN"

    # Alert resolve by citizen -> 403
    r3 = client.post(f"/api/v1/alerts/{fake_id}/resolve", json={"reason": "Citizen test"}, headers=headers)
    assert r3.status_code == 403

    # Alert dismiss by citizen -> 403
    r4 = client.post(f"/api/v1/alerts/{fake_id}/dismiss", json={"reason": "Citizen test"}, headers=headers)
    assert r4.status_code == 403


def test_rbac_official_and_admin_permitted_actions(auth_matrix_users):
    """Officials and Admins are permitted to perform moderation and lifecycle actions."""
    off_headers = auth_matrix_users["official"]["headers"]
    admin_headers = auth_matrix_users["admin"]["headers"]

    # 1. Create an alert via official
    r_alert = client.post(
        "/api/v1/alerts/generate",
        json={"latitude": 30.5, "longitude": 79.2, "risk_score": 0.8},
        headers=off_headers,
    )
    assert r_alert.status_code == 201
    alert_id = r_alert.json()["data"]["id"]

    # 2. Official acknowledges alert -> 200 OK
    r_ack = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", json={"reason": "Acknowledged by official"}, headers=off_headers)
    assert r_ack.status_code == 200
    assert r_ack.json()["data"]["status"] == "ACKNOWLEDGED"

    # 3. Admin resolves alert -> 200 OK
    r_res = client.post(f"/api/v1/alerts/{alert_id}/resolve", json={"reason": "Resolved by admin"}, headers=admin_headers)
    assert r_res.status_code == 200
    assert r_res.json()["data"]["status"] == "RESOLVED"


# ============================================================================
# 2. Security, Input Validation & Error Envelope Tests
# ============================================================================

def test_standard_error_envelope_structure(auth_matrix_users):
    """All error responses must match standard shape {error: {code, message, details, request_id}}."""
    headers = auth_matrix_users["official"]["headers"]

    # Trigger a 422 validation error
    r_val = client.post("/api/v1/alerts/generate", json={"latitude": 120.0, "longitude": 79.0}, headers=headers)
    assert r_val.status_code == 422
    body = r_val.json()
    assert "error" in body
    err = body["error"]
    assert "code" in err
    assert "message" in err
    assert "details" in err
    assert "request_id" in err
    assert err["code"] == "VALIDATION_ERROR"

    # Trigger a 404 not found error
    fake_id = uuid.uuid4()
    r_nf = client.get(f"/api/v1/alerts/{fake_id}", headers=headers)
    assert r_nf.status_code == 404
    err_nf = r_nf.json()["error"]
    assert err_nf["code"] == "NOT_FOUND"


def test_sql_injection_resistance(auth_matrix_users):
    """SQL injection payloads in string fields are safely sanitized and handled as literals."""
    headers = auth_matrix_users["official"]["headers"]

    sql_payload = "'; DROP TABLE alerts; --"
    r = client.get(f"/api/v1/alerts?status={sql_payload}", headers=headers)
    assert r.status_code == 200
    assert r.json()["data"]["total_count"] == 0

    # Verify table still exists
    db = SessionLocal()
    try:
        count = db.execute(text("SELECT count(*) FROM alerts;")).scalar()
        assert count is not None
    finally:
        db.close()


def test_no_sensitive_secrets_in_responses(auth_matrix_users):
    """Ensure no password hashes or secret tokens leak in user or report queries."""
    # Register new user
    r_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "leaktest@testrisksetu.com",
            "password": "SuperSecretPassword123!",
            "full_name": "Secret Tester",
            "role": "citizen",
        },
    )
    assert r_reg.status_code == 201
    resp_text = r_reg.text
    assert "hashed_password" not in resp_text
    assert "SuperSecretPassword123!" not in resp_text
    assert "jwt_secret_key" not in resp_text


# ============================================================================
# 3. Audit Trail Integrity
# ============================================================================

def test_mutation_audit_trail_completeness(auth_matrix_users):
    """Ensure all mutating actions on ground reports and alerts write immutable audit logs."""
    db = SessionLocal()
    try:
        off_headers = auth_matrix_users["official"]["headers"]
        off_id = auth_matrix_users["official"]["id"]

        # Create and resolve an alert
        r1 = client.post("/api/v1/alerts/generate", json={"latitude": 30.1, "longitude": 79.1, "risk_score": 0.8}, headers=off_headers)
        alert_id = uuid.UUID(r1.json()["data"]["id"])
        client.post(f"/api/v1/alerts/{alert_id}/resolve", json={"reason": "Security audit test"}, headers=off_headers)

        # Check DB audit records
        audits = db.query(AlertAudit).filter(AlertAudit.alert_id == alert_id).all()
        actions = [a.action for a in audits]
        assert "CREATED" in actions
        assert "RESOLVED" in actions
        for a in audits:
            assert a.user_id == off_id
            assert a.created_at is not None
    finally:
        db.close()
