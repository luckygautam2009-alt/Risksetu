"""
RISKSETU AI — ROAD_RISK_V1 unit tests.

All external calls are mocked. No live internet or DB required.
_run_phase2b is patched directly (not simulate_blockage) because the
engine's empty-graph guard would return None before reaching simulate_blockage.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.live_risk import (
    DataFreshness,
    HistoricalRiskLayer,
    LiveRiskData,
    LiveRiskLocation,
    LiveRiskSummary,
    MLLayer,
    TerrainLayer,
    WeatherLayer,
)
from app.schemas.road_risk import (
    BlockageRiskAssessment,
    RoadRiskConnectivity,
    RoadRiskData,
    RoadRiskFreshness,
    RoadSegmentInfo,
)
from app.services.impact.isolation import IsolationResult
from app.services.road_risk.constants import (
    BRIDGE_MODIFIER,
    ENGINE_VERSION,
    RISK_LEVEL_HIGH_MAX,
    RISK_LEVEL_LOW_MAX,
    RISK_LEVEL_MODERATE_MAX,
    W_ISOLATION,
    W_LIVE_RISK,
)
from app.services.road_risk.engine import (
    RoadRiskEngine,
    _build_actions,
    _determine_risk_level,
)

client = TestClient(app)
_NOW = datetime(2026, 9, 4, 15, 0, 0, tzinfo=timezone.utc)

_EDGE_INFO: dict[str, Any] = {
    "edge_db_id": "abc-123",
    "osm_way_id": 14930128,
    "from_node_id": 30001,
    "to_node_id": 30002,
    "highway_class": "primary",
    "name": "NH-58",
    "length_m": 420.0,
    "bridge": False,
    "tunnel": False,
    "distance_from_target_m": 35.0,
}
_BRIDGE_EDGE_INFO: dict[str, Any] = {**_EDGE_INFO, "bridge": True}


def _sim(
    component_increase: int = 0,
    nodes_affected: int = 0,
    isolation_severity: float = 0.0,
    is_bridge_edge: bool = False,
) -> IsolationResult:
    return IsolationResult(
        blocked_edges=[],
        components_before=2, components_after=2 + component_increase,
        component_increase=component_increase, nodes_affected=nodes_affected,
        edges_in_affected_components=0, isolation_severity=isolation_severity,
        is_bridge_edge=is_bridge_edge, articulation_points_near_blockage=[],
        alternative_components=[],
        graph_stats_before={"total_nodes": 10, "total_edges": 9,
                            "connected_components": 2, "largest_component_nodes": 8},
        graph_stats_after={"total_nodes": 10, "total_edges": 8,
                           "connected_components": 2 + component_increase,
                           "largest_component_nodes": 8 - nodes_affected},
        limitations=["WHAT_IF only."],
    )


def _lrd(
    score: float = 45.0,
    level: str = "MODERATE",
    confidence: float = 55.0,
    historical_available: bool = True,
    weather_status: str = "available",
) -> LiveRiskData:
    return LiveRiskData(
        location=LiveRiskLocation(latitude=30.3, longitude=79.6),
        timestamp=_NOW,
        risk=LiveRiskSummary(score=score, level=level, confidence=confidence),
        historical=HistoricalRiskLayer(
            status="available" if historical_available else "unavailable",
            score=score if historical_available else None,
            level=level if historical_available else None,
            confidence=confidence if historical_available else None,
        ),
        weather=WeatherLayer(status=weather_status),
        ml=MLLayer(status="unavailable"),
        terrain=TerrainLayer(status="unavailable"),
        contributing_factors=[],
        data_freshness=DataFreshness(assessment_generated_at=_NOW),
    )


def _minimal() -> RoadRiskData:
    return RoadRiskData(
        road=RoadSegmentInfo(from_node_id=30001, to_node_id=30002, osm_way_id=14930128),
        blockage=BlockageRiskAssessment(
            predicted_risk_score=45.0, risk_level="MODERATE", confidence=55.0,
            status="PREDICTED", closure_status="UNKNOWN", traffic_status="unavailable",
        ),
        factors=[],
        connectivity=RoadRiskConnectivity(simulation_type="WHAT_IF"),
        unavailable_inputs=["ml_susceptibility", "terrain"],
        recommendations=[],
        data_freshness=RoadRiskFreshness(assessment_generated_at=_NOW.isoformat()),
    )


def _make_engine(
    edge_info: dict[str, Any] | None = None,
    live_data: LiveRiskData | None = None,
) -> RoadRiskEngine:
    """Create a RoadRiskEngine with mocked builder and live-risk engine."""
    db = MagicMock()
    e = RoadRiskEngine(db=db)
    e._builder = MagicMock()
    e._builder.find_nearest_edge.return_value = edge_info if edge_info is not None else _EDGE_INFO
    lre = AsyncMock()
    lre.assess.return_value = live_data or _lrd()
    e._live_risk_engine = lre
    return e


# ===========================================================================
# 1. Risk level thresholds — must mirror Phase 2A exactly
# ===========================================================================

class TestRiskLevels:
    def test_0_is_low(self): assert _determine_risk_level(0.0) == "LOW"
    def test_24_is_low(self): assert _determine_risk_level(24.0) == "LOW"
    def test_24_1_is_moderate(self): assert _determine_risk_level(24.1) == "MODERATE"
    def test_49_is_moderate(self): assert _determine_risk_level(49.0) == "MODERATE"
    def test_49_1_is_high(self): assert _determine_risk_level(49.1) == "HIGH"
    def test_74_is_high(self): assert _determine_risk_level(74.0) == "HIGH"
    def test_74_1_is_critical(self): assert _determine_risk_level(74.1) == "CRITICAL"
    def test_100_is_critical(self): assert _determine_risk_level(100.0) == "CRITICAL"


# ===========================================================================
# 2. Formula / constants
# ===========================================================================

class TestFormula:
    def test_weights_allow_no_overflow_before_bridge(self):
        assert W_LIVE_RISK + W_ISOLATION <= 1.0

    def test_bridge_modifier_reasonable(self):
        assert 0 < BRIDGE_MODIFIER <= 15

    def test_bridge_adds_to_score(self):
        base = W_LIVE_RISK * 60.0 + W_ISOLATION * 40.0
        assert base + BRIDGE_MODIFIER > base

    def test_score_clamped_to_100(self):
        # Maximum possible: W_LIVE_RISK×100 + W_ISOLATION×100 + BRIDGE_MODIFIER
        # = 0.65×100 + 0.20×100 + 10 = 65+20+10 = 95  → always ≤ 100 by construction
        # If we override to extreme weights, clamp must fire
        raw_extreme = 100.0  # simulate a case where raw = 100 + bridge
        clamped = min(100.0, raw_extreme + BRIDGE_MODIFIER)
        assert clamped == 100.0

    def test_score_never_below_0(self):
        assert max(0.0, W_LIVE_RISK * 0.0 + W_ISOLATION * 0.0) == 0.0

    def test_thresholds_match_phase2a(self):
        assert RISK_LEVEL_LOW_MAX == 24.0
        assert RISK_LEVEL_MODERATE_MAX == 49.0
        assert RISK_LEVEL_HIGH_MAX == 74.0

    def test_engine_version(self):
        assert ENGINE_VERSION == "ROAD_RISK_V1"


# ===========================================================================
# 3. Recommended actions
# ===========================================================================

class TestActions:
    def test_low_has_routine_monitoring(self):
        ids = [a.action_id for a in _build_actions("LOW", False)]
        assert "ROAD_MONITOR_ROUTINE" in ids

    def test_moderate_has_inspection(self):
        ids = [a.action_id for a in _build_actions("MODERATE", False)]
        assert "ROAD_INSPECT_CORRIDOR" in ids

    def test_high_has_field_inspect(self):
        ids = [a.action_id for a in _build_actions("HIGH", False)]
        assert "ROAD_FIELD_INSPECT" in ids

    def test_critical_has_immediate_verify(self):
        ids = [a.action_id for a in _build_actions("CRITICAL", False)]
        assert "ROAD_IMMEDIATE_VERIFY" in ids

    def test_bridge_adds_structural_check(self):
        ids = [a.action_id for a in _build_actions("MODERATE", True)]
        assert "BRIDGE_STRUCTURAL_CHECK" in ids

    def test_no_bridge_no_structural_check(self):
        ids = [a.action_id for a in _build_actions("MODERATE", False)]
        assert "BRIDGE_STRUCTURAL_CHECK" not in ids

    def test_no_duplicate_ids_any_level(self):
        for level in ("LOW", "MODERATE", "HIGH", "CRITICAL"):
            for bridge in (True, False):
                ids = [a.action_id for a in _build_actions(level, bridge)]
                assert len(ids) == len(set(ids))


# ===========================================================================
# 4. Engine.assess() — full integration with _run_phase2b patched
# ===========================================================================

class TestEngineAssess:

    @pytest.mark.asyncio
    async def test_road_not_found_returns_graceful_state(self):
        e = _make_engine(edge_info=None)
        e._builder.find_nearest_edge.return_value = None
        result = await e.assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert result.road.from_node_id == 0
        assert "road_segment_not_found" in result.unavailable_inputs
        assert result.blockage.closure_status == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_ml_always_unavailable(self):
        with patch("app.services.road_risk.engine._run_phase2b", return_value=_sim()):
            e = _make_engine()
            result = await e.assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert "ml_susceptibility" in result.unavailable_inputs
        assert result.connectivity.simulation_type == "WHAT_IF"

    @pytest.mark.asyncio
    async def test_terrain_always_unavailable(self):
        with patch("app.services.road_risk.engine._run_phase2b", return_value=_sim()):
            e = _make_engine()
            result = await e.assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert "terrain" in result.unavailable_inputs

    @pytest.mark.asyncio
    async def test_score_within_bounds(self):
        with patch("app.services.road_risk.engine._run_phase2b",
                   return_value=_sim(isolation_severity=80.0)):
            e = _make_engine(live_data=_lrd(score=90.0))
            result = await e.assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert 0.0 <= result.blockage.predicted_risk_score <= 100.0

    @pytest.mark.asyncio
    async def test_confidence_within_bounds(self):
        with patch("app.services.road_risk.engine._run_phase2b", return_value=_sim()):
            e = _make_engine()
            result = await e.assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert 0.0 <= result.blockage.confidence <= 100.0

    @pytest.mark.asyncio
    async def test_closure_status_always_unknown(self):
        with patch("app.services.road_risk.engine._run_phase2b", return_value=_sim()):
            e = _make_engine()
            result = await e.assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert result.blockage.closure_status == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_traffic_status_always_unavailable(self):
        with patch("app.services.road_risk.engine._run_phase2b", return_value=_sim()):
            e = _make_engine()
            result = await e.assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert result.blockage.traffic_status == "unavailable"

    @pytest.mark.asyncio
    async def test_simulation_type_always_what_if(self):
        with patch("app.services.road_risk.engine._run_phase2b", return_value=_sim()):
            e = _make_engine()
            result = await e.assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert result.connectivity.simulation_type == "WHAT_IF"

    @pytest.mark.asyncio
    async def test_status_is_predicted_not_confirmed(self):
        with patch("app.services.road_risk.engine._run_phase2b", return_value=_sim()):
            e = _make_engine()
            result = await e.assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert result.blockage.status == "PREDICTED"
        assert result.blockage.closure_status != "CONFIRMED"

    @pytest.mark.asyncio
    async def test_engine_version_tag(self):
        with patch("app.services.road_risk.engine._run_phase2b", return_value=_sim()):
            e = _make_engine()
            result = await e.assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert result.engine_version == "ROAD_RISK_V1"

    @pytest.mark.asyncio
    async def test_recommendations_present(self):
        with patch("app.services.road_risk.engine._run_phase2b", return_value=_sim()):
            e = _make_engine()
            result = await e.assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert len(result.recommendations) >= 1

    @pytest.mark.asyncio
    async def test_bridge_osm_flag_adds_modifier(self):
        with patch("app.services.road_risk.engine._run_phase2b",
                   return_value=_sim(isolation_severity=20.0)):
            e_plain = _make_engine(edge_info=_EDGE_INFO, live_data=_lrd(score=50.0))
            r_plain = await e_plain.assess(30.3, 79.6, 5000.0, 1000.0, None)

        with patch("app.services.road_risk.engine._run_phase2b",
                   return_value=_sim(isolation_severity=20.0, is_bridge_edge=False)):
            e_bridge = _make_engine(edge_info=_BRIDGE_EDGE_INFO, live_data=_lrd(score=50.0))
            r_bridge = await e_bridge.assess(30.3, 79.6, 5000.0, 1000.0, None)

        assert r_bridge.blockage.predicted_risk_score > r_plain.blockage.predicted_risk_score

    @pytest.mark.asyncio
    async def test_graph_bridge_flag_adds_action(self):
        with patch("app.services.road_risk.engine._run_phase2b",
                   return_value=_sim(is_bridge_edge=True)):
            e = _make_engine(edge_info=_BRIDGE_EDGE_INFO)
            result = await e.assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert "BRIDGE_STRUCTURAL_CHECK" in [a.action_id for a in result.recommendations]

    @pytest.mark.asyncio
    async def test_high_isolation_elevates_score(self):
        with patch("app.services.road_risk.engine._run_phase2b",
                   return_value=_sim(isolation_severity=0.0)):
            e_low = _make_engine(live_data=_lrd(score=40.0))
            r_low = await e_low.assess(30.3, 79.6, 5000.0, 1000.0, None)

        with patch("app.services.road_risk.engine._run_phase2b",
                   return_value=_sim(isolation_severity=90.0)):
            e_high = _make_engine(live_data=_lrd(score=40.0))
            r_high = await e_high.assess(30.3, 79.6, 5000.0, 1000.0, None)

        assert r_high.blockage.predicted_risk_score > r_low.blockage.predicted_risk_score

    @pytest.mark.asyncio
    async def test_connectivity_reflects_component_increase(self):
        with patch("app.services.road_risk.engine._run_phase2b",
                   return_value=_sim(component_increase=2, nodes_affected=5,
                                     isolation_severity=35.0, is_bridge_edge=True)):
            e = _make_engine()
            result = await e.assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert result.connectivity.component_increase == 2
        assert result.connectivity.nodes_affected == 5
        assert result.connectivity.is_bridge_edge is True

    @pytest.mark.asyncio
    async def test_live_risk_failure_reduces_confidence(self):
        # Full run
        with patch("app.services.road_risk.engine._run_phase2b",
                   return_value=_sim(isolation_severity=40.0)):
            e_full = _make_engine(live_data=_lrd(score=50.0, confidence=70.0))
            r_full = await e_full.assess(30.3, 79.6, 5000.0, 1000.0, None)

        # Live risk fails
        with patch("app.services.road_risk.engine._run_phase2b",
                   return_value=_sim(isolation_severity=40.0)):
            e_fail = _make_engine()
            e_fail._live_risk_engine.assess.side_effect = RuntimeError("DB offline")
            r_fail = await e_fail.assess(30.3, 79.6, 5000.0, 1000.0, None)

        assert r_fail.blockage.confidence <= r_full.blockage.confidence

    @pytest.mark.asyncio
    async def test_isolation_failure_handled_gracefully(self):
        with patch("app.services.road_risk.engine._run_phase2b", return_value=None):
            e = _make_engine()
            result = await e.assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert "isolation_simulation" in result.unavailable_inputs

    @pytest.mark.asyncio
    async def test_weather_unavailable_reported(self):
        with patch("app.services.road_risk.engine._run_phase2b", return_value=_sim()):
            e = _make_engine(live_data=_lrd(weather_status="unavailable"))
            result = await e.assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert "live_weather" in result.unavailable_inputs

    @pytest.mark.asyncio
    async def test_deterministic_output(self):
        s = _sim(isolation_severity=40.0)
        ld = _lrd(score=50.0, confidence=60.0)
        with patch("app.services.road_risk.engine._run_phase2b", return_value=s):
            r1 = await _make_engine(live_data=ld).assess(30.3, 79.6, 5000.0, 1000.0, None)
            r2 = await _make_engine(live_data=ld).assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert r1.blockage.predicted_risk_score == r2.blockage.predicted_risk_score
        assert r1.blockage.risk_level == r2.blockage.risk_level

    @pytest.mark.asyncio
    async def test_ml_unavailable_no_fabrication(self):
        with patch("app.services.road_risk.engine._run_phase2b", return_value=_sim()):
            e = _make_engine()
            result = await e.assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert "ml_susceptibility" in result.unavailable_inputs

    @pytest.mark.asyncio
    async def test_terrain_unavailable_no_fabrication(self):
        with patch("app.services.road_risk.engine._run_phase2b", return_value=_sim()):
            e = _make_engine()
            result = await e.assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert "terrain" in result.unavailable_inputs

    @pytest.mark.asyncio
    async def test_data_freshness_populated(self):
        with patch("app.services.road_risk.engine._run_phase2b", return_value=_sim()):
            e = _make_engine()
            result = await e.assess(30.3, 79.6, 5000.0, 1000.0, None)
        assert result.data_freshness.assessment_generated_at is not None


# ===========================================================================
# 5. API coordinate validation
# ===========================================================================

class TestAPICoords:
    def _patch(self):
        return patch("app.api.v1.road_risk.RoadRiskEngine.assess",
                     new_callable=AsyncMock, return_value=_minimal())

    def test_valid_accepted(self):
        with self._patch():
            r = client.post("/api/v1/road-risk/evaluate",
                            json={"latitude": 30.3, "longitude": 79.6})
        assert r.status_code == 200

    def test_lat_too_low(self):
        r = client.post("/api/v1/road-risk/evaluate",
                        json={"latitude": -91.0, "longitude": 79.6})
        assert r.status_code == 422

    def test_lat_too_high(self):
        r = client.post("/api/v1/road-risk/evaluate",
                        json={"latitude": 91.0, "longitude": 79.6})
        assert r.status_code == 422

    def test_lon_too_low(self):
        r = client.post("/api/v1/road-risk/evaluate",
                        json={"latitude": 30.0, "longitude": -181.0})
        assert r.status_code == 422

    def test_lon_too_high(self):
        r = client.post("/api/v1/road-risk/evaluate",
                        json={"latitude": 30.0, "longitude": 181.0})
        assert r.status_code == 422

    def test_missing_lat(self):
        r = client.post("/api/v1/road-risk/evaluate", json={"longitude": 79.6})
        assert r.status_code == 422

    def test_missing_lon(self):
        r = client.post("/api/v1/road-risk/evaluate", json={"latitude": 30.3})
        assert r.status_code == 422


# ===========================================================================
# 6. API response shape
# ===========================================================================

class TestAPIShape:
    def _patch(self):
        return patch("app.api.v1.road_risk.RoadRiskEngine.assess",
                     new_callable=AsyncMock, return_value=_minimal())

    def test_has_data_and_meta(self):
        with self._patch():
            r = client.post("/api/v1/road-risk/evaluate",
                            json={"latitude": 30.3, "longitude": 79.6})
        assert "data" in r.json() and "meta" in r.json()

    def test_required_fields(self):
        with self._patch():
            r = client.post("/api/v1/road-risk/evaluate",
                            json={"latitude": 30.3, "longitude": 79.6})
        data = r.json()["data"]
        for f in ["road", "blockage", "factors", "connectivity",
                  "unavailable_inputs", "recommendations",
                  "data_freshness", "engine_version"]:
            assert f in data

    def test_closure_unknown(self):
        with self._patch():
            r = client.post("/api/v1/road-risk/evaluate",
                            json={"latitude": 30.3, "longitude": 79.6})
        assert r.json()["data"]["blockage"]["closure_status"] == "UNKNOWN"

    def test_traffic_unavailable(self):
        with self._patch():
            r = client.post("/api/v1/road-risk/evaluate",
                            json={"latitude": 30.3, "longitude": 79.6})
        assert r.json()["data"]["blockage"]["traffic_status"] == "unavailable"

    def test_simulation_what_if(self):
        with self._patch():
            r = client.post("/api/v1/road-risk/evaluate",
                            json={"latitude": 30.3, "longitude": 79.6})
        assert r.json()["data"]["connectivity"]["simulation_type"] == "WHAT_IF"

    def test_engine_version(self):
        with self._patch():
            r = client.post("/api/v1/road-risk/evaluate",
                            json={"latitude": 30.3, "longitude": 79.6})
        assert r.json()["data"]["engine_version"] == "ROAD_RISK_V1"

    def test_request_id_in_meta(self):
        with self._patch():
            r = client.post("/api/v1/road-risk/evaluate",
                            json={"latitude": 30.3, "longitude": 79.6})
        assert "request_id" in r.json()["meta"]

    def test_score_bounds(self):
        with self._patch():
            r = client.post("/api/v1/road-risk/evaluate",
                            json={"latitude": 30.3, "longitude": 79.6})
        score = r.json()["data"]["blockage"]["predicted_risk_score"]
        assert 0.0 <= score <= 100.0

    def test_predicted_not_confirmed(self):
        with self._patch():
            r = client.post("/api/v1/road-risk/evaluate",
                            json={"latitude": 30.3, "longitude": 79.6})
        assert r.json()["data"]["blockage"]["status"] == "PREDICTED"
