"""
Phase 5 — Cross-Phase End-to-End Integration Test Suite.

Validates the full pipeline:
Ground Report → Trust/Eligibility → Risk Evaluation → Road Impact Simulation → Priority Evaluation → Operational Alert → Decision Support
"""
from __future__ import annotations

import datetime
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
def clean_e2e_db():
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
def e2e_users(clean_e2e_db):
    """Creates citizen and official users with JWT tokens."""
    db = SessionLocal()
    try:
        citizen_id = uuid.uuid4()
        official_id = uuid.uuid4()

        citizen = User(
            id=citizen_id,
            email=f"citizen_{citizen_id.hex[:6]}@testrisksetu.com",
            hashed_password=hash_password("Pass123!"),
            full_name="Citizen Tester",
            role="citizen",
        )
        official = User(
            id=official_id,
            email=f"official_{official_id.hex[:6]}@testrisksetu.com",
            hashed_password=hash_password("Pass123!"),
            full_name="Official Tester",
            role="official",
        )
        db.add_all([citizen, official])
        db.commit()

        citizen_token = create_access_token(str(citizen_id))
        official_token = create_access_token(str(official_id))

        return {
            "citizen": {"headers": {"Authorization": f"Bearer {citizen_token}"}, "id": citizen_id},
            "official": {"headers": {"Authorization": f"Bearer {official_token}"}, "id": official_id},
        }
    finally:
        db.close()


def test_full_cross_phase_pipeline(e2e_users):
    """
    Executes the entire end-to-end multi-phase intelligence and decision-support flow:
    1. Citizen submits a field observation (Phase 3)
    2. Trust score & risk eligibility are evaluated (Phase 3)
    3. Official computes spatial physical risk for the area (Phase 2A)
    4. Official simulates road blockage and topological isolation impact (Phase 2B)
    5. Official computes multivariate intervention priority (Phase 2C)
    6. System generates an operational alert with recommended actions (Phase 4)
    7. Official acknowledges the alert, initiating response (Phase 4)
    """
    citizen_headers = e2e_users["citizen"]["headers"]
    official_headers = e2e_users["official"]["headers"]

    # Northern zone routable network coordinates (Ludhiana/Northern corridor)
    lat = 30.8933
    lon = 75.8708

    # =========================================================================
    # Step 1 & 2: Ground Report Submission & Trust Scoring (Phase 3)
    # =========================================================================
    report_payload = {
        "report_type": "LANDSLIDE",
        "description": "Massive slope displacement observed across main road corridor near Chamoli.",
        "latitude": lat,
        "longitude": lon,
        "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    r_gr = client.post("/api/v1/ground-reports", json=report_payload, headers=citizen_headers)
    assert r_gr.status_code == 201
    gr_data = r_gr.json()["data"]
    assert gr_data["status"] == "SUBMITTED"
    assert gr_data["trust"]["trust_score"] > 0.0
    assert gr_data["trust"]["trust_class"] in ("LOW", "MODERATE", "HIGH", "VERY_HIGH")
    ground_report_id = gr_data["report_id"]

    # =========================================================================
    # Step 3: Spatial Landslide Risk Evaluation (Phase 2A)
    # =========================================================================
    risk_payload = {
        "latitude": lat,
        "longitude": lon,
        "observed_rainfall_mm": 120.0,
        "month": 7,
        "year": 2020,
    }
    r_risk = client.post("/api/v1/risk/evaluate", json=risk_payload, headers=official_headers)
    assert r_risk.status_code == 200
    risk_data = r_risk.json()["data"]
    assert 0.0 <= risk_data["risk_score"] <= 100.0
    assert risk_data["risk_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")
    assert 0.0 <= risk_data["confidence_score"] <= 100.0

    # =========================================================================
    # Step 4: Road Network Isolation Simulation (Phase 2B)
    # =========================================================================
    impact_payload = {
        "latitude": lat,
        "longitude": lon,
        "radius_m": 5000.0,
    }
    r_impact = client.post("/api/v1/impact/simulate-road-blockage", json=impact_payload, headers=official_headers)
    assert r_impact.status_code == 200
    impact_data = r_impact.json()["data"]
    assert 0.0 <= impact_data["isolation_severity"] <= 100.0
    assert impact_data["connectivity_impact"]["nodes_affected"] >= 0

    # =========================================================================
    # Step 5: Multivariate Intervention Priority Engine (Phase 2C)
    # =========================================================================
    priority_payload = {
        "candidate_id": "CHAMOLI_HOTSPOT_01",
        "latitude": lat,
        "longitude": lon,
        "risk_score": risk_data["risk_score"],
        "risk_level": risk_data["risk_level"],
        "risk_confidence": risk_data["confidence_score"],
        "isolation_severity": impact_data["isolation_severity"],
        "component_increase": impact_data["connectivity_impact"]["component_increase"],
        "nodes_affected": impact_data["connectivity_impact"]["nodes_affected"],
        "edges_in_affected_components": impact_data["connectivity_impact"]["edges_in_affected_components"],
        "is_bridge_edge": impact_data["connectivity_impact"]["is_bridge_edge"],
    }
    r_prio = client.post("/api/v1/priority/evaluate", json=priority_payload, headers=official_headers)
    assert r_prio.status_code == 200
    prio_data = r_prio.json()["data"]
    assert 0.0 <= prio_data["priority_score"] <= 100.0
    assert prio_data["priority_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")
    assert prio_data["breakdown"]["risk_contribution"] >= 0.0
    assert prio_data["breakdown"]["impact_contribution"] >= 0.0

    # =========================================================================
    # Step 6: Operational Alert Generation & Decision Support (Phase 4)
    # =========================================================================
    alert_payload = {
        "latitude": lat,
        "longitude": lon,
        "risk_score": risk_data["risk_score"] / 100.0,
        "risk_level": risk_data["risk_level"],
        "risk_confidence": risk_data["confidence_score"] / 100.0,
        "isolation_severity": "HIGH" if impact_data["isolation_severity"] >= 50.0 else "MODERATE",
        "priority_score": prio_data["priority_score"],
        "priority_level": prio_data["priority_level"],
        "ground_intelligence_summary": {
            "trust_class": gr_data["trust"]["trust_class"],
            "trust_score": gr_data["trust"]["trust_score"],
            "report_count": 1,
            "report_id": ground_report_id,
        },
        "source_reference": {"candidate_id": "CHAMOLI_HOTSPOT_01"},
    }
    r_alert = client.post("/api/v1/alerts/generate", json=alert_payload, headers=official_headers)
    assert r_alert.status_code == 201
    alert_res = r_alert.json()
    alert_data = alert_res["data"]
    alert_meta = alert_res["meta"]

    assert alert_meta["was_created"] is True
    assert alert_data["status"] == "ACTIVE"
    assert alert_data["severity"] in ("INFO", "WARNING", "HIGH", "CRITICAL")
    assert len(alert_data["recommended_actions"]) >= 1
    assert "explanation" in alert_data
    assert len(alert_data["explanation"]["system_limitations"]) >= 1
    alert_id = alert_data["id"]

    # =========================================================================
    # Step 7: Official Acknowledgment & Lifecycle (Phase 4)
    # =========================================================================
    r_ack = client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        json={"reason": "Field team and excavator units mobilized to Chamoli corridor."},
        headers=official_headers,
    )
    assert r_ack.status_code == 200
    ack_data = r_ack.json()["data"]
    assert ack_data["status"] == "ACKNOWLEDGED"
    assert ack_data["acknowledged_at"] is not None
    assert ack_data["acknowledged_by"] == str(e2e_users["official"]["id"])


def test_untrusted_ground_report_cannot_force_critical_alert(e2e_users):
    """
    Verifies trust boundary invariant: an uncorroborated, low-trust ground report
    cannot directly force a CRITICAL alert.
    """
    citizen_headers = e2e_users["citizen"]["headers"]
    official_headers = e2e_users["official"]["headers"]

    # Low-reliability coordinate with extreme text
    report_payload = {
        "report_type": "OTHER",
        "description": "CRITICAL EMERGENCY CATASTROPHIC COLLAPSE EVERYWHERE",
        "latitude": 20.0,  # non-landslide zone
        "longitude": 75.0,
        "observed_at": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=10)).isoformat(),
    }
    r_gr = client.post("/api/v1/ground-reports", json=report_payload, headers=citizen_headers)
    assert r_gr.status_code == 201
    gr_data = r_gr.json()["data"]

    # Trust score is LOW and not eligible for automated risk influence
    assert gr_data["trust"]["trust_class"] in ("LOW", "MODERATE")
    assert gr_data["risk_influence_eligible"] is False

    # Attempting to generate alert from this alone yields INFO or WARNING, never CRITICAL
    alert_payload = {
        "latitude": 20.0,
        "longitude": 75.0,
        "ground_intelligence_summary": {
            "trust_class": gr_data["trust"]["trust_class"],
            "trust_score": gr_data["trust"]["trust_score"],
            "report_count": 1,
        },
    }
    r_alert = client.post("/api/v1/alerts/generate", json=alert_payload, headers=official_headers)
    assert r_alert.status_code == 201
    alert_data = r_alert.json()["data"]
    assert alert_data["severity"] in ("INFO", "WARNING")
    assert alert_data["severity"] != "CRITICAL"


def test_risk_not_equal_priority_ranking_e2e(e2e_users):
    """
    Demonstrates that a candidate with lower physical risk but critical isolation impact
    outranks a candidate with higher physical risk but zero isolation impact.
    """
    official_headers = e2e_users["official"]["headers"]

    ranking_payload = {
        "candidates": [
            {
                "candidate_id": "HIGH_RISK_LOW_IMPACT",
                "latitude": 30.1,
                "longitude": 79.1,
                "risk_score": 85.0,
                "risk_level": "CRITICAL",
                "risk_confidence": 90.0,
                "isolation_severity": 0.0,
                "component_increase": 0,
                "nodes_affected": 0,
                "edges_in_affected_components": 0,
                "is_bridge_edge": False,
            },
            {
                "candidate_id": "MODERATE_RISK_CRITICAL_IMPACT",
                "latitude": 30.2,
                "longitude": 79.2,
                "risk_score": 40.0,
                "risk_level": "MODERATE",
                "risk_confidence": 70.0,
                "isolation_severity": 95.0,
                "component_increase": 4,
                "nodes_affected": 25,
                "edges_in_affected_components": 30,
                "is_bridge_edge": True,
            },
        ]
    }
    r_rank = client.post("/api/v1/priority/rank", json=ranking_payload, headers=official_headers)
    assert r_rank.status_code == 200
    ranked = r_rank.json()["data"]["ranked_candidates"]
    assert len(ranked) == 2
    # Candidate with critical isolation outranks candidate with zero isolation
    assert ranked[0]["candidate_id"] == "MODERATE_RISK_CRITICAL_IMPACT"
    assert ranked[0]["rank"] == 1


def test_simulation_labeling_and_disclaimers_e2e(e2e_users):
    """Verifies that all simulation outputs include explicit WHAT_IF labeling and limitations."""
    official_headers = e2e_users["official"]["headers"]

    impact_payload = {
        "latitude": 30.8933,
        "longitude": 75.8708,
        "radius_m": 3000.0,
    }
    r_impact = client.post("/api/v1/impact/simulate-road-blockage", json=impact_payload, headers=official_headers)
    assert r_impact.status_code == 200
    impact_data = r_impact.json()["data"]
    assert impact_data["simulation_type"] == "WHAT_IF_SCENARIO"
    assert len(impact_data["limitations"]) >= 1
    assert any("simulation" in lim.lower() for lim in impact_data["limitations"])

