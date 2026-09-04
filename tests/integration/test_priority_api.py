"""
Integration tests for Phase 2C Priority API endpoints.

Tests cover:
  - POST /api/v1/priority/evaluate — single candidate priority evaluation
  - POST /api/v1/priority/rank — multi-candidate deterministic ranking
  - Validation error handling (422)
  - Standard response envelope structure
  - Determinism guarantees
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── /evaluate endpoint ───────────────────────────────────────────────────

class TestPriorityEvaluateEndpoint:
    """Integration tests for the priority evaluate API."""

    def test_evaluate_with_presupplied_metrics(self) -> None:
        """Verify evaluation with all metrics pre-supplied (no DB orchestration)."""
        resp = client.post(
            "/api/v1/priority/evaluate",
            json={
                "candidate_id": "test_eval_01",
                "latitude": 30.3165,
                "longitude": 78.0322,
                "risk_score": 65.0,
                "risk_level": "HIGH",
                "risk_confidence": 75.0,
                "isolation_severity": 55.0,
                "component_increase": 2,
                "nodes_affected": 8,
                "edges_in_affected_components": 4,
                "is_bridge_edge": True,
            },
        )
        assert resp.status_code == 200
        res = resp.json()

        # Standard envelope
        assert "data" in res
        assert "meta" in res
        assert "request_id" in res["meta"]

        data = res["data"]
        assert data["candidate_id"] == "test_eval_01"
        assert data["latitude"] == 30.3165
        assert data["longitude"] == 78.0322
        assert 0.0 <= data["priority_score"] <= 100.0
        assert data["priority_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")

        # Verify breakdown
        bd = data["breakdown"]
        assert "risk_contribution" in bd
        assert "impact_contribution" in bd
        assert "urgency_contribution" in bd
        assert bd["priority_score"] == data["priority_score"]
        assert bd["priority_level"] == data["priority_level"]

        # Verify explanation and limitations
        assert len(data["explanation"]) > 0
        assert len(data["limitations"]) >= 5
        assert data["calculation_version"] == "priority-v1"

        # Verify input metrics echo
        assert data["risk_score"] == 65.0
        assert data["isolation_severity"] == 55.0
        assert data["is_bridge_edge"] is True
        assert data["component_increase"] == 2
        assert data["nodes_affected"] == 8

    def test_evaluate_minimal_coordinates_only(self) -> None:
        """Verify evaluation with coordinates only — engine orchestrates Phase 2A/2B."""
        resp = client.post(
            "/api/v1/priority/evaluate",
            json={
                "latitude": 28.6723,
                "longitude": 77.2309,
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert 0.0 <= data["priority_score"] <= 100.0
        assert data["priority_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")
        assert data["calculation_version"] == "priority-v1"

    def test_evaluate_validation_latitude_out_of_range(self) -> None:
        resp = client.post(
            "/api/v1/priority/evaluate",
            json={"latitude": 100.0, "longitude": 78.0},
        )
        assert resp.status_code == 422

    def test_evaluate_validation_longitude_out_of_range(self) -> None:
        resp = client.post(
            "/api/v1/priority/evaluate",
            json={"latitude": 30.0, "longitude": 200.0},
        )
        assert resp.status_code == 422

    def test_evaluate_validation_risk_score_out_of_range(self) -> None:
        resp = client.post(
            "/api/v1/priority/evaluate",
            json={"latitude": 30.0, "longitude": 78.0, "risk_score": 150.0},
        )
        assert resp.status_code == 422

    def test_evaluate_validation_extra_fields_forbidden(self) -> None:
        resp = client.post(
            "/api/v1/priority/evaluate",
            json={"latitude": 30.0, "longitude": 78.0, "unknown_field": "oops"},
        )
        assert resp.status_code == 422

    def test_evaluate_determinism(self) -> None:
        """Same inputs must produce identical outputs."""
        payload = {
            "candidate_id": "det_test",
            "latitude": 30.3165,
            "longitude": 78.0322,
            "risk_score": 70.0,
            "risk_level": "HIGH",
            "risk_confidence": 80.0,
            "isolation_severity": 60.0,
        }
        r1 = client.post("/api/v1/priority/evaluate", json=payload)
        r2 = client.post("/api/v1/priority/evaluate", json=payload)
        assert r1.status_code == 200
        assert r2.status_code == 200
        d1 = r1.json()["data"]
        d2 = r2.json()["data"]
        assert d1["priority_score"] == d2["priority_score"]
        assert d1["priority_level"] == d2["priority_level"]
        assert d1["breakdown"] == d2["breakdown"]
        assert d1["urgency_score"] == d2["urgency_score"]
        assert d1["explanation"] == d2["explanation"]


# ── /rank endpoint ───────────────────────────────────────────────────────

class TestPriorityRankEndpoint:
    """Integration tests for the priority ranking API."""

    def test_rank_multiple_candidates(self) -> None:
        resp = client.post(
            "/api/v1/priority/rank",
            json={
                "candidates": [
                    {
                        "candidate_id": "low_priority",
                        "latitude": 30.0,
                        "longitude": 78.0,
                        "risk_score": 10.0,
                        "risk_level": "LOW",
                        "risk_confidence": 50.0,
                        "isolation_severity": 10.0,
                    },
                    {
                        "candidate_id": "high_priority",
                        "latitude": 30.5,
                        "longitude": 78.5,
                        "risk_score": 90.0,
                        "risk_level": "CRITICAL",
                        "risk_confidence": 90.0,
                        "isolation_severity": 85.0,
                    },
                    {
                        "candidate_id": "mid_priority",
                        "latitude": 30.2,
                        "longitude": 78.2,
                        "risk_score": 50.0,
                        "risk_level": "MODERATE",
                        "risk_confidence": 60.0,
                        "isolation_severity": 50.0,
                    },
                ]
            },
        )
        assert resp.status_code == 200
        res = resp.json()

        assert "data" in res
        assert "meta" in res

        data = res["data"]
        assert data["total_candidates"] == 3
        assert data["calculation_version"] == "priority-v1"
        assert len(data["limitations"]) >= 5

        ranked = data["ranked_candidates"]
        assert len(ranked) == 3
        assert ranked[0]["rank"] == 1
        assert ranked[1]["rank"] == 2
        assert ranked[2]["rank"] == 3

        # High priority should be ranked first
        assert ranked[0]["candidate_id"] == "high_priority"
        # Low priority should be ranked last
        assert ranked[2]["candidate_id"] == "low_priority"

        # All candidates should have explanations and breakdowns
        for item in ranked:
            assert len(item["explanation"]) > 0
            assert "risk_contribution" in item["breakdown"]
            assert 0.0 <= item["priority_score"] <= 100.0

    def test_rank_single_candidate(self) -> None:
        resp = client.post(
            "/api/v1/priority/rank",
            json={
                "candidates": [
                    {
                        "candidate_id": "only_one",
                        "latitude": 30.0,
                        "longitude": 78.0,
                        "risk_score": 50.0,
                        "risk_level": "MODERATE",
                        "isolation_severity": 50.0,
                    },
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_candidates"] == 1
        assert data["ranked_candidates"][0]["rank"] == 1
        assert data["ranked_candidates"][0]["candidate_id"] == "only_one"

    def test_rank_validation_empty_candidates(self) -> None:
        resp = client.post(
            "/api/v1/priority/rank",
            json={"candidates": []},
        )
        assert resp.status_code == 422

    def test_rank_validation_extra_fields_forbidden(self) -> None:
        resp = client.post(
            "/api/v1/priority/rank",
            json={
                "candidates": [
                    {
                        "candidate_id": "x",
                        "latitude": 30.0,
                        "longitude": 78.0,
                        "risk_score": 50.0,
                        "risk_level": "HIGH",
                        "isolation_severity": 50.0,
                        "bad_field": 123,
                    },
                ]
            },
        )
        assert resp.status_code == 422

    def test_rank_determinism(self) -> None:
        payload = {
            "candidates": [
                {
                    "candidate_id": "c1",
                    "latitude": 30.0,
                    "longitude": 78.0,
                    "risk_score": 50.0,
                    "risk_level": "MODERATE",
                    "isolation_severity": 60.0,
                },
                {
                    "candidate_id": "c2",
                    "latitude": 30.5,
                    "longitude": 78.5,
                    "risk_score": 70.0,
                    "risk_level": "HIGH",
                    "isolation_severity": 40.0,
                },
            ]
        }
        r1 = client.post("/api/v1/priority/rank", json=payload)
        r2 = client.post("/api/v1/priority/rank", json=payload)
        assert r1.status_code == 200
        assert r2.status_code == 200
        d1 = r1.json()["data"]["ranked_candidates"]
        d2 = r2.json()["data"]["ranked_candidates"]
        for a, b in zip(d1, d2):
            assert a["candidate_id"] == b["candidate_id"]
            assert a["rank"] == b["rank"]
            assert a["priority_score"] == b["priority_score"]

    def test_rank_tie_breaking_isolation_severity(self) -> None:
        """When priority scores are very close, higher isolation severity should win."""
        resp = client.post(
            "/api/v1/priority/rank",
            json={
                "candidates": [
                    {
                        "candidate_id": "a",
                        "latitude": 30.0,
                        "longitude": 78.0,
                        "risk_score": 50.0,
                        "risk_level": "MODERATE",
                        "risk_confidence": 50.0,
                        "isolation_severity": 50.0,
                    },
                    {
                        "candidate_id": "b",
                        "latitude": 30.0,
                        "longitude": 78.0,
                        "risk_score": 50.0,
                        "risk_level": "MODERATE",
                        "risk_confidence": 50.0,
                        "isolation_severity": 60.0,
                    },
                ]
            },
        )
        assert resp.status_code == 200
        ranked = resp.json()["data"]["ranked_candidates"]
        # b has higher isolation severity AND higher priority score
        assert ranked[0]["candidate_id"] == "b"
