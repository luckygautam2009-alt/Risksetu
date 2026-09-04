"""
Phase 5 — Complete Demo Scenarios A–G Verification Script against Live Database.
"""
from __future__ import annotations

import datetime
import uuid
from starlette.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User

client = TestClient(app)


def run_demo_scenarios():
    print("================================================================")
    print("        RISKSETU AI — DEMO SCENARIOS A–G RUNTIME PROOF          ")
    print("================================================================")

    db = SessionLocal()
    citizen_id = uuid.uuid4()
    official_id = uuid.uuid4()

    citizen = User(
        id=citizen_id,
        email=f"demo_citizen_{citizen_id.hex[:6]}@testrisksetu.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Demo Citizen",
        role="citizen",
    )
    official = User(
        id=official_id,
        email=f"demo_official_{official_id.hex[:6]}@testrisksetu.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Demo Official",
        role="official",
    )
    db.add_all([citizen, official])
    db.commit()

    citizen_token = create_access_token(str(citizen_id))
    official_token = create_access_token(str(official_id))
    citizen_headers = {"Authorization": f"Bearer {citizen_token}"}
    official_headers = {"Authorization": f"Bearer {official_token}"}

    # =========================================================================
    # Scenario A: Low-Risk Location (Plains / Delhi)
    # =========================================================================
    print("\n[Scenario A] Low-Risk Location Evaluation")
    r_a = client.post(
        "/api/v1/risk/evaluate",
        json={"latitude": 28.6139, "longitude": 77.2090, "observed_rainfall_mm": 20.0, "month": 1, "year": 2020},
        headers=official_headers,
    )
    assert r_a.status_code == 200
    res_a = r_a.json()["data"]
    print(f"  ✓ Location: Delhi Plains (28.6139, 77.2090)")
    print(f"  ✓ Risk Score: {res_a['risk_score']} / 100.0 (Level: {res_a['risk_level']})")
    print(f"  ✓ Confidence Score: {res_a['confidence_score']} / 100.0")
    assert res_a["risk_level"] == "LOW"

    # =========================================================================
    # Scenario B: Historical Landslide Hotspot (Chamoli / Uttarakhand)
    # =========================================================================
    print("\n[Scenario B] Historical Landslide Hotspot Evaluation")
    r_b = client.post(
        "/api/v1/risk/evaluate",
        json={"latitude": 30.555, "longitude": 79.123, "observed_rainfall_mm": 250.0, "month": 7, "year": 2020},
        headers=official_headers,
    )
    assert r_b.status_code == 200
    res_b = r_b.json()["data"]
    print(f"  ✓ Location: Chamoli GSI Cluster (30.555, 79.123)")
    print(f"  ✓ Risk Score: {res_b['risk_score']} / 100.0 (Level: {res_b['risk_level']})")
    print(f"  ✓ Factors Evaluated: {len(res_b['factors'])}")
    assert res_b["risk_score"] >= 50.0 or res_b["risk_level"] in ("HIGH", "CRITICAL")

    # =========================================================================
    # Scenario C: High-Impact Road Disruption Simulation
    # =========================================================================
    print("\n[Scenario C] High-Impact Road Disruption Simulation")
    r_c = client.post(
        "/api/v1/impact/simulate-road-blockage",
        json={"latitude": 30.8933, "longitude": 75.8708, "radius_m": 5000.0},
        headers=official_headers,
    )
    assert r_c.status_code == 200
    res_c = r_c.json()["data"]
    print(f"  ✓ Target Road Segment: Way ID {res_c['blocked_edge']['osm_way_id']} ({res_c['blocked_edge']['highway_class']})")
    print(f"  ✓ Isolation Severity Score: {res_c['isolation_severity']:.1f} / 100.0")
    print(f"  ✓ Newly Disconnected Components: {res_c['connectivity_impact']['component_increase']}")
    print(f"  ✓ Nodes Affected: {res_c['connectivity_impact']['nodes_affected']}")

    # =========================================================================
    # Scenario D: RISK ≠ PRIORITY Principle
    # =========================================================================
    print("\n[Scenario D] RISK ≠ PRIORITY Ranking Demonstration")
    cand1 = {
        "candidate_id": "HIGH_HAZARD_ISOLATED_ROAD",
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
    }
    cand2 = {
        "candidate_id": "MODERATE_HAZARD_CRITICAL_CORRIDOR",
        "latitude": 30.2,
        "longitude": 79.2,
        "risk_score": 40.0,
        "risk_level": "MODERATE",
        "risk_confidence": 70.0,
        "isolation_severity": 95.0,
        "component_increase": 4,
        "nodes_affected": 30,
        "edges_in_affected_components": 35,
        "is_bridge_edge": True,
    }
    r_d = client.post("/api/v1/priority/rank", json={"candidates": [cand1, cand2]}, headers=official_headers)
    assert r_d.status_code == 200
    ranked_d = r_d.json()["data"]["ranked_candidates"]
    print(f"  ✓ Rank 1: {ranked_d[0]['candidate_id']} (Priority Score: {ranked_d[0]['priority_score']:.2f}, Level: {ranked_d[0]['priority_level']})")
    print(f"  ✓ Rank 2: {ranked_d[1]['candidate_id']} (Priority Score: {ranked_d[1]['priority_score']:.2f}, Level: {ranked_d[1]['priority_level']})")
    assert ranked_d[0]["candidate_id"] == "MODERATE_HAZARD_CRITICAL_CORRIDOR"

    # =========================================================================
    # Scenario E: Ground Intelligence & Trust Scoring
    # =========================================================================
    print("\n[Scenario E] Ground Intelligence & Trust Scoring")
    gr_payload = {
        "report_type": "SLOPE_MOVEMENT",
        "description": "Continuous ground fissure widening observed along road embankment after heavy rain.",
        "latitude": 30.555,
        "longitude": 79.123,
        "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    r_e = client.post("/api/v1/ground-reports", json=gr_payload, headers=citizen_headers)
    assert r_e.status_code == 201
    res_e = r_e.json()["data"]
    print(f"  ✓ Report ID: {res_e['report_id']}")
    print(f"  ✓ Trust Score: {res_e['trust']['trust_score']:.2f} / 100.0 (Class: {res_e['trust']['trust_class']})")
    print(f"  ✓ Deduplicated: {res_e['is_duplicate']}")
    print(f"  ✓ Risk Influence Eligible: {res_e['risk_influence_eligible']}")

    # =========================================================================
    # Scenario F: Operational Alert Generation & Decision Support
    # =========================================================================
    print("\n[Scenario F] Operational Alert Generation & Decision Support")
    alert_payload = {
        "latitude": 30.555,
        "longitude": 79.123,
        "risk_score": 0.88,
        "risk_level": "CRITICAL",
        "priority_score": 92.0,
        "priority_level": "CRITICAL",
        "isolation_severity": "HIGH",
    }
    r_f = client.post("/api/v1/alerts/generate", json=alert_payload, headers=official_headers)
    assert r_f.status_code == 201
    res_f = r_f.json()["data"]
    print(f"  ✓ Generated Alert ID: {res_f['id']}")
    print(f"  ✓ Alert Severity: {res_f['severity']}, Type: {res_f['alert_type']}")
    print(f"  ✓ Recommended Actions Count: {len(res_f['recommended_actions'])}")
    for a in res_f["recommended_actions"][:2]:
        print(f"    - [{a['urgency']}] {a['title']}")

    # =========================================================================
    # Scenario G: RBAC Lifecycle Permissions
    # =========================================================================
    print("\n[Scenario G] RBAC Lifecycle Enforcement")
    alert_id = res_f["id"]
    r_g_cit = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", json={"reason": "Citizen attempt"}, headers=citizen_headers)
    print(f"  ✓ Citizen Acknowledge: {r_g_cit.status_code} Forbidden (Blocked)")
    assert r_g_cit.status_code == 403

    r_g_off = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", json={"reason": "Official confirmed deployment"}, headers=official_headers)
    print(f"  ✓ Official Acknowledge: {r_g_off.status_code} OK (Permitted, Status: {r_g_off.json()['data']['status']})")
    assert r_g_off.status_code == 200

    print("\n================================================================")
    print("   ALL DEMO SCENARIOS A–G COMPLETED & CERTIFIED SUCCESSFULLY    ")
    print("================================================================\n")
    db.close()


if __name__ == "__main__":
    run_demo_scenarios()
