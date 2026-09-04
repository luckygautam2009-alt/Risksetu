"""
Performance sanity benchmark script for all RiskSetu AI endpoints.
Measures median (p50) and 95th percentile (p95) execution latencies.
"""
import datetime
import statistics
import time
import uuid
from starlette.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User

client = TestClient(app)

def benchmark():
    db = SessionLocal()
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email=f"bench_{user_id.hex[:6]}@testrisksetu.com",
        hashed_password=hash_password("Pass123!"),
        full_name="Benchmarker",
        role="official",
    )
    db.add(user)
    db.commit()
    token = create_access_token(str(user_id))
    headers = {"Authorization": f"Bearer {token}"}
    db.close()

    endpoints = {
        "1. Risk Evaluation": (
            "/api/v1/risk/evaluate",
            "POST",
            {"latitude": 30.555, "longitude": 79.123, "observed_rainfall_mm": 150.0, "month": 7, "year": 2020},
        ),
        "2. Road Blockage Simulation": (
            "/api/v1/impact/simulate-road-blockage",
            "POST",
            {"latitude": 30.8933, "longitude": 75.8708, "radius_m": 3000.0},
        ),
        "3. Priority Evaluation": (
            "/api/v1/priority/evaluate",
            "POST",
            {
                "candidate_id": "BENCH_01",
                "latitude": 30.8933,
                "longitude": 75.8708,
                "risk_score": 65.0,
                "risk_level": "HIGH",
                "risk_confidence": 80.0,
                "isolation_severity": 50.0,
            },
        ),
        "4. Priority Multi-Candidate Ranking (5 items)": (
            "/api/v1/priority/rank",
            "POST",
            {
                "candidates": [
                    {
                        "candidate_id": f"C_{i}",
                        "latitude": 30.1 + i * 0.05,
                        "longitude": 79.1 + i * 0.05,
                        "risk_score": 30.0 + i * 12.0,
                        "risk_level": "MODERATE",
                        "risk_confidence": 75.0,
                        "isolation_severity": 20.0 + i * 15.0,
                    }
                    for i in range(5)
                ]
            },
        ),
        "5. Ground Report Submission": (
            "/api/v1/ground-reports",
            "POST",
            {
                "report_type": "ROCKFALL",
                "description": "Debris on slope section",
                "latitude": 30.555,
                "longitude": 79.123,
                "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
        ),
        "6. Alert Generation": (
            "/api/v1/alerts/generate",
            "POST",
            {
                "latitude": 30.555,
                "longitude": 79.123,
                "risk_score": 80.0,
                "risk_level": "CRITICAL",
                "priority_score": 85.0,
            },
        ),
        "7. Alert Listing (Paginated)": (
            "/api/v1/alerts?limit=20&offset=0",
            "GET",
            None,
        ),
    }

    print("\n=======================================================")
    print("       RISKSETU AI — LATENCY BENCHMARK RESULTS         ")
    print("=======================================================")
    print(f"{'Endpoint':<45} | {'p50 (ms)':<10} | {'p95 (ms)':<10} | {'Status':<6}")
    print("-" * 78)

    iterations = 25
    results_summary = {}

    for name, (path, method, payload) in endpoints.items():
        durations = []
        for _ in range(iterations):
            start = time.perf_counter()
            if method == "POST":
                r = client.post(path, json=payload, headers=headers)
            else:
                r = client.get(path, headers=headers)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            assert r.status_code in (200, 201), f"Failed {name}: {r.status_code} - {r.text}"
            durations.append(elapsed_ms)

        durations.sort()
        p50 = durations[len(durations) // 2]
        p95_idx = int(len(durations) * 0.95)
        p95 = durations[min(p95_idx, len(durations) - 1)]
        results_summary[name] = {"p50": round(p50, 2), "p95": round(p95, 2)}
        print(f"{name:<45} | {p50:8.2f} ms | {p95:8.2f} ms | PASS")

    print("=======================================================\n")
    return results_summary

if __name__ == "__main__":
    benchmark()
