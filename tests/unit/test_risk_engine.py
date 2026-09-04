"""
Comprehensive unit tests for the Explainable Spatial Risk Intelligence Engine.
"""
from __future__ import annotations

import math
from unittest.mock import MagicMock
import uuid

from fastapi.testclient import TestClient
import pytest

from app.core.errors import ValidationAppError
from app.db.session import get_db
from app.main import app
from app.models.rainfall import RainfallClimatology, RainfallSubdivision
from app.schemas.risk import RiskEvaluationRequest
from app.services.risk.constants import (
    CALCULATION_VERSION,
)
from app.services.risk.engine import RiskEvaluationEngine
from app.services.risk.explanation import RiskExplanationGenerator
from app.services.risk.rainfall import RainfallEvidenceResult, RainfallRiskEvaluator
from app.services.risk.scoring import RiskScoringEngine
from app.services.risk.spatial import SpatialEvidenceResult


# -----------------------------------------------------------------------------
# 1. Scoring & Weight Redistribution Tests
# -----------------------------------------------------------------------------

def test_risk_level_boundaries() -> None:
    """Verify deterministic risk level classification on exact boundary thresholds."""
    assert RiskScoringEngine.determine_risk_level(0.0) == "LOW"
    assert RiskScoringEngine.determine_risk_level(24.0) == "LOW"
    assert RiskScoringEngine.determine_risk_level(24.1) == "MODERATE"
    assert RiskScoringEngine.determine_risk_level(49.0) == "MODERATE"
    assert RiskScoringEngine.determine_risk_level(49.1) == "HIGH"
    assert RiskScoringEngine.determine_risk_level(74.0) == "HIGH"
    assert RiskScoringEngine.determine_risk_level(74.1) == "CRITICAL"
    assert RiskScoringEngine.determine_risk_level(100.0) == "CRITICAL"


def test_score_composition_with_all_available_factors() -> None:
    """Verify composite scoring when both spatial and rainfall factors are active."""
    spatial_res = SpatialEvidenceResult(
        score=80.0,
        count_within_5km=5,
        count_within_10km=10,
        count_within_25km=20,
        distance_to_nearest_km=1.5,
        closest_slide_no="GSI_UK_001",
        closest_slide_material="Debris",
        closest_slide_movement="Slide",
        dated_events_count=10,
        undated_inventory_count=10,
        evidence_dict={"within_5km_count": 5},
        explanation="High cluster",
    )

    rainfall_res = RainfallEvidenceResult(
        available=True,
        score=60.0,
        subdivision_name="UTTARAKHAND",
        observed_mm=350.0,
        climatology_mean_mm=250.0,
        climatology_std_mm=50.0,
        z_score=2.0,
        anomaly_mm=100.0,
        evidence_dict={"observed_rainfall_mm": 350.0},
        explanation="Elevated anomaly",
    )

    comp = RiskScoringEngine.compose_score(spatial_res, rainfall_res)

    # Base weights: Hist=0.50, Rain=0.30, Terrain=0.20 (unavailable)
    # Available sum = 0.80 -> Normalized: Hist = 0.50/0.80 = 0.625, Rain = 0.30/0.80 = 0.375
    # Expected score = (80 * 0.625) + (60 * 0.375) = 50.0 + 22.5 = 72.5
    assert math.isclose(comp.risk_score, 72.5, abs_tol=0.1)
    assert comp.risk_level == "HIGH"
    assert comp.weight_redistributed is True
    assert comp.confidence_score > 0.0


def test_score_composition_when_rainfall_unavailable() -> None:
    """Verify weight redistribution when rainfall is unavailable (Historical absorbs 100%)."""
    spatial_res = SpatialEvidenceResult(
        score=80.0,
        count_within_5km=5,
        count_within_10km=10,
        count_within_25km=20,
        distance_to_nearest_km=1.5,
        closest_slide_no="GSI_UK_001",
        closest_slide_material="Debris",
        closest_slide_movement="Slide",
        dated_events_count=5,
        undated_inventory_count=15,
        evidence_dict={},
        explanation="Spatial only",
    )

    rainfall_res = RainfallEvidenceResult(
        available=False,
        score=0.0,
        subdivision_name=None,
        observed_mm=None,
        climatology_mean_mm=None,
        climatology_std_mm=None,
        z_score=None,
        anomaly_mm=None,
        evidence_dict={},
        explanation="Unavailable",
    )

    comp = RiskScoringEngine.compose_score(spatial_res, rainfall_res)

    # Available: Historical only (0.50 / 0.50 = 1.0)
    # Expected score = 80.0 * 1.0 = 80.0
    assert math.isclose(comp.risk_score, 80.0, abs_tol=0.1)
    assert comp.risk_level == "CRITICAL"
    assert comp.weight_redistributed is True


# -----------------------------------------------------------------------------
# 2. Spatial Risk Evaluator Direct Tests
# -----------------------------------------------------------------------------

def test_spatial_evaluator_direct_queries() -> None:
    """Verify SpatialRiskEvaluator calculates density and proximity accurately."""
    from collections import namedtuple
    from app.services.risk.spatial import SpatialRiskEvaluator

    Row = namedtuple("Row", ["gsi_slide_no", "material", "movement_type", "event_date", "distance_meters"])
    mock_rows = [
        Row(gsi_slide_no="SLIDE_A", material="Rock", movement_type="Slide", event_date="2021-08-01", distance_meters=2000.0),
        Row(gsi_slide_no="SLIDE_B", material="Debris", movement_type="Flow", event_date=None, distance_meters=7000.0),
        Row(gsi_slide_no="SLIDE_C", material="Soil", movement_type="Fall", event_date=None, distance_meters=15000.0),
    ]
    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = mock_rows

    evaluator = SpatialRiskEvaluator(mock_db)
    res = evaluator.evaluate(30.3165, 78.0322)

    assert res.count_within_5km == 1
    assert res.count_within_10km == 2
    assert res.count_within_25km == 3
    assert res.dated_events_count == 1
    assert res.undated_inventory_count == 2
    assert res.distance_to_nearest_km == 2.0
    assert res.closest_slide_no == "SLIDE_A"
    assert res.score > 0.0


def test_spatial_evaluator_empty_results() -> None:
    """Verify SpatialRiskEvaluator handles areas with 0 historical landslides safely."""
    from app.services.risk.spatial import SpatialRiskEvaluator

    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = []

    evaluator = SpatialRiskEvaluator(mock_db)
    res = evaluator.evaluate(20.0, 75.0)

    assert res.score == 0.0
    assert res.count_within_5km == 0
    assert res.count_within_10km == 0
    assert res.count_within_25km == 0
    assert res.distance_to_nearest_km is None
    assert res.closest_slide_no is None


# -----------------------------------------------------------------------------
# 3. Rainfall Anomaly & Climatology Evaluator Tests
# -----------------------------------------------------------------------------

def test_rainfall_evaluator_anomaly_calculation() -> None:
    """Verify z-score anomaly scoring with mocked DB climatology baseline."""
    mock_db = MagicMock()
    mock_subdiv = RainfallSubdivision(
        id=uuid.uuid4(),
        subdivision_name="Uttarakhand",
        normalized_name="UTTARAKHAND",
    )
    mock_clim = RainfallClimatology(
        subdivision_id=mock_subdiv.id,
        month=7,
        years_used=117,
        mean_mm=300.0,
        stddev_mm=50.0,
        min_mm=100.0,
        max_mm=500.0,
        source_period_start=1901,
        source_period_end=2017,
    )

    mock_db.get.return_value = mock_subdiv
    mock_db.scalars.return_value.first.return_value = mock_clim

    evaluator = RainfallRiskEvaluator(mock_db)

    # Test 1: Exactly at mean (z = 0.0 -> score = 0.0)
    res1 = evaluator.evaluate(mock_subdiv.id, 300.0, month=7, year=2020)
    assert res1.available is True
    assert res1.z_score == 0.0
    assert res1.score == 0.0

    # Test 2: +1 sigma anomaly (z = +1.0 -> score approx 33.3)
    res2 = evaluator.evaluate(mock_subdiv.id, 350.0, month=7, year=2020)
    assert res2.z_score == 1.0
    assert math.isclose(res2.score, 33.3, abs_tol=0.2)

    # Test 3: +3 sigma anomaly (z = +3.0 -> score approx 100.0)
    res3 = evaluator.evaluate(mock_subdiv.id, 450.0, month=7, year=2020)
    assert res3.z_score == 3.0
    assert math.isclose(res3.score, 100.0, abs_tol=0.2)

    # Test 4: Extreme outlier (>3 sigma -> score capped at 100.0)
    res4 = evaluator.evaluate(mock_subdiv.id, 600.0, month=7, year=2020)
    assert res4.z_score == 6.0
    assert res4.score == 100.0


def test_rainfall_evaluator_missing_parameters() -> None:
    """Verify graceful handling when rainfall parameters are missing or subdivision not found."""
    mock_db = MagicMock()
    mock_db.get.return_value = None
    evaluator = RainfallRiskEvaluator(mock_db)

    # Missing parameters
    res1 = evaluator.evaluate(None, None, None)
    assert res1.available is False
    assert res1.score == 0.0

    # Subdivision ID not in DB
    res2 = evaluator.evaluate(uuid.uuid4(), 200.0, 7)
    assert res2.available is False


# -----------------------------------------------------------------------------
# 3. Confidence & Explanation Tests
# -----------------------------------------------------------------------------

def test_confidence_score_calculation() -> None:
    """Verify confidence score rewards data richness and reflects missing terrain."""
    spatial_rich = SpatialEvidenceResult(
        score=70.0, count_within_5km=4, count_within_10km=8, count_within_25km=15,
        distance_to_nearest_km=1.2, closest_slide_no="S1", closest_slide_material="Rock",
        closest_slide_movement="Slide", dated_events_count=10, undated_inventory_count=5,
        evidence_dict={}, explanation="",
    )
    rain_avail = RainfallEvidenceResult(
        available=True, score=50.0, subdivision_name="UK", observed_mm=200.0,
        climatology_mean_mm=150.0, climatology_std_mm=30.0, z_score=1.67, anomaly_mm=50.0,
        evidence_dict={}, explanation="",
    )

    conf = RiskScoringEngine.calculate_confidence(spatial_rich, rain_avail)
    # Spatial: 20 (density) + (10/15 * 20 = 13.3) = 33.3
    # Rainfall: 30
    # Total = 63.3 (out of 100, remaining ~36.7 missing due to no DEM)
    assert 60.0 <= conf <= 70.0


def test_explanation_generator_summary() -> None:
    """Verify transparent plain-language summary generation."""
    factors = [
        RiskScoringEngine.compose_score(
            SpatialEvidenceResult(
                score=80.0, count_within_5km=2, count_within_10km=4, count_within_25km=6,
                distance_to_nearest_km=2.0, closest_slide_no="S1", closest_slide_material="Debris",
                closest_slide_movement="Slide", dated_events_count=2, undated_inventory_count=4,
                evidence_dict={}, explanation="Spatial",
            ),
            RainfallEvidenceResult(
                available=False, score=0.0, subdivision_name=None, observed_mm=None,
                climatology_mean_mm=None, climatology_std_mm=None, z_score=None, anomaly_mm=None,
                evidence_dict={}, explanation="Rainfall",
            ),
        ).factors
    ][0]

    summary = RiskExplanationGenerator.generate_summary(
        risk_score=80.0,
        risk_level="CRITICAL",
        factors=factors,
        redistribution_note="Weights redistributed.",
    )
    assert "CRITICAL" in summary
    assert "80.0/100" in summary
    assert "Historical Landslide Spatial Density" in summary


# -----------------------------------------------------------------------------
# 4. Engine & API Integration Tests
# -----------------------------------------------------------------------------

def test_engine_rejects_rainfall_without_month() -> None:
    """Verify engine raises ValidationAppError if observed_rainfall_mm is given without month."""
    mock_db = MagicMock()
    engine = RiskEvaluationEngine(mock_db)

    req = RiskEvaluationRequest(
        latitude=30.3165,
        longitude=78.0322,
        observed_rainfall_mm=250.0,
        month=None,  # missing month
    )

    with pytest.raises(ValidationAppError):
        engine.evaluate(req)


def test_api_risk_evaluate_success_envelope() -> None:
    """Verify POST /api/v1/risk/evaluate returns the standard success envelope."""
    from collections import namedtuple

    Row = namedtuple("Row", ["gsi_slide_no", "material", "movement_type", "event_date", "distance_meters"])
    mock_rows = [
        Row(gsi_slide_no="TEST_001", material="Rock", movement_type="Slide", event_date="2020-07-15", distance_meters=1500.0),
        Row(gsi_slide_no="TEST_002", material="Debris", movement_type="Fall", event_date=None, distance_meters=4200.0),
        Row(gsi_slide_no="TEST_003", material="Soil", movement_type="Flow", event_date=None, distance_meters=8500.0),
        Row(gsi_slide_no="TEST_004", material="Rock", movement_type="Slide", event_date="2018-08-10", distance_meters=18000.0),
    ]
    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = mock_rows

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(app)
        payload = {
            "latitude": 30.3165,
            "longitude": 78.0322,
        }

        response = client.post("/api/v1/risk/evaluate", json=payload)
        assert response.status_code == 200
        body = response.json()

        assert "data" in body
        assert "meta" in body
        data = body["data"]

        assert "risk_score" in data
        assert "risk_level" in data
        assert "confidence_score" in data
        assert data["calculation_version"] == CALCULATION_VERSION
        assert "factors" in data
        assert len(data["factors"]) == 3
        assert "limitations" in data
        assert len(data["limitations"]) > 0
    finally:
        app.dependency_overrides.clear()


def test_api_risk_evaluate_invalid_coordinates() -> None:
    """Verify API returns 422 for invalid latitude/longitude outside standard range."""
    client = TestClient(app)

    # Latitude out of bounds (> 90.0)
    resp = client.post("/api/v1/risk/evaluate", json={"latitude": 95.0, "longitude": 78.0})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
