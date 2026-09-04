"""
Unit tests for strict boundary consistency across Risk, Priority, and Alert classifications.
Tests: 0, 24, 24.99, 25, 49, 49.99, 50, 74, 74.99, 75, 100.
"""
import pytest

from app.services.alerts.constants import AlertSeverity
from app.services.alerts.severity import determine_alert_severity
from app.services.priority.scoring import PriorityScoringEngine
from app.services.risk.scoring import RiskScoringEngine


@pytest.mark.parametrize(
    "score,expected_level",
    [
        (0.0, "LOW"),
        (24.0, "LOW"),
        (24.01, "MODERATE"),
        (25.0, "MODERATE"),
        (49.0, "MODERATE"),
        (49.01, "HIGH"),
        (50.0, "HIGH"),
        (74.0, "HIGH"),
        (74.01, "CRITICAL"),
        (75.0, "CRITICAL"),
        (100.0, "CRITICAL"),
    ],
)
def test_risk_level_boundaries(score: float, expected_level: str):
    assert RiskScoringEngine.determine_risk_level(score) == expected_level


@pytest.mark.parametrize(
    "score,expected_level",
    [
        (0.0, "LOW"),
        (24.0, "LOW"),
        (24.01, "MODERATE"),
        (25.0, "MODERATE"),
        (49.0, "MODERATE"),
        (49.01, "HIGH"),
        (50.0, "HIGH"),
        (74.0, "HIGH"),
        (74.01, "CRITICAL"),
        (75.0, "CRITICAL"),
        (100.0, "CRITICAL"),
    ],
)
def test_priority_level_boundaries(score: float, expected_level: str):
    assert PriorityScoringEngine.determine_priority_level(score) == expected_level


def test_no_impossible_combinations():
    """Ensure risk_score=0 cannot produce CRITICAL and priority_score=20 cannot produce CRITICAL."""
    assert RiskScoringEngine.determine_risk_level(0.0) != "CRITICAL"
    assert PriorityScoringEngine.determine_priority_level(20.0) != "CRITICAL"

    # In severity mapping:
    sev = determine_alert_severity(risk_score=0.0, risk_level="LOW", priority_score=20.0, priority_level="LOW")
    assert sev == AlertSeverity.INFO
    assert sev != AlertSeverity.CRITICAL
