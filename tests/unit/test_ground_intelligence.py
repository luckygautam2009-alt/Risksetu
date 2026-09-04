"""
Unit test suite for Ground Intelligence & Trust-Weighted Reporting Engine.
"""
from __future__ import annotations

import datetime
import uuid

import pytest

from app.core.errors import ValidationAppError
from app.schemas.ground_report import TrustClass
from app.services.ground_intelligence.classification import TrustClassifier
from app.services.ground_intelligence.constants import (
    DEFAULT_USER_RELIABILITY_CITIZEN,
    DEFAULT_USER_RELIABILITY_OFFICIAL,
    HALF_LIFE_DAYS,
)
from app.services.ground_intelligence.deduplication import ReportDeduplicator
from app.services.ground_intelligence.eligibility import RiskEligibilityEvaluator
from app.services.ground_intelligence.explanation import GroundIntelligenceExplanationGenerator
from app.services.ground_intelligence.geo_plausibility import GeoPlausibilityEvaluator
from app.services.ground_intelligence.time_decay import TimeDecayEvaluator
from app.services.ground_intelligence.trust import TrustScoreResult, TrustScoringEngine
from app.services.ground_intelligence.user_reliability import UserReliabilityEvaluator
from app.services.ground_intelligence.validation import GroundReportValidator


class TestGroundReportValidation:
    """Validation unit tests for input boundaries and formats."""

    def test_valid_coordinates(self):
        lat, lon = GroundReportValidator.validate_coordinates(30.5, 78.2)
        assert lat == 30.5
        assert lon == 78.2

    def test_boundary_coordinates(self):
        assert GroundReportValidator.validate_coordinates(-90.0, -180.0) == (-90.0, -180.0)
        assert GroundReportValidator.validate_coordinates(90.0, 180.0) == (90.0, 180.0)

    def test_nan_coordinate_rejected(self):
        with pytest.raises(ValidationAppError, match="Latitude must be a finite real number"):
            GroundReportValidator.validate_coordinates(float("nan"), 78.0)

        with pytest.raises(ValidationAppError, match="Longitude must be a finite real number"):
            GroundReportValidator.validate_coordinates(30.0, float("inf"))

    def test_out_of_bounds_latitude_rejected(self):
        with pytest.raises(ValidationAppError, match="Latitude 90.1 out of valid range"):
            GroundReportValidator.validate_coordinates(90.1, 78.0)

        with pytest.raises(ValidationAppError, match="Latitude -95.0 out of valid range"):
            GroundReportValidator.validate_coordinates(-95.0, 78.0)

    def test_out_of_bounds_longitude_rejected(self):
        with pytest.raises(ValidationAppError, match="Longitude 180.5 out of valid range"):
            GroundReportValidator.validate_coordinates(30.0, 180.5)

    def test_observation_time_valid(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        obs = now - datetime.timedelta(hours=2)
        res = GroundReportValidator.validate_observation_time(obs)
        assert res.tzinfo is not None

    def test_observation_time_future_drift_tolerance(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        # 2 minutes into future -> accepted due to 5m clock drift tolerance
        res = GroundReportValidator.validate_observation_time(now + datetime.timedelta(minutes=2))
        assert res.tzinfo is not None

    def test_observation_time_future_excessive_rejected(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        with pytest.raises(ValidationAppError, match="cannot be in the future"):
            GroundReportValidator.validate_observation_time(now + datetime.timedelta(minutes=10))

    def test_observation_time_too_stale_rejected(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        with pytest.raises(ValidationAppError, match="too stale"):
            GroundReportValidator.validate_observation_time(now - datetime.timedelta(days=400))

    def test_description_whitespace_rejected(self):
        with pytest.raises(ValidationAppError, match="non-whitespace characters"):
            GroundReportValidator.validate_description("         \n   ")

    def test_description_too_short_rejected(self):
        with pytest.raises(ValidationAppError, match="at least 10 non-whitespace characters"):
            GroundReportValidator.validate_description("Crack")

    def test_description_too_long_rejected(self):
        with pytest.raises(ValidationAppError, match="exceeds maximum length"):
            GroundReportValidator.validate_description("a" * 2001)

    def test_description_sanitized(self):
        desc = "   Fresh slope failure observed on northern bypass.   "
        assert GroundReportValidator.validate_description(desc) == "Fresh slope failure observed on northern bypass."


class TestTimeDecayEvaluator:
    """Temporal freshness unit tests."""

    def test_zero_age_maximum_score(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        score = TimeDecayEvaluator.calculate_temporal_freshness(now, reference_time=now)
        assert score == 100.0

    def test_one_half_life_decay(self):
        ref = datetime.datetime.now(datetime.timezone.utc)
        obs = ref - datetime.timedelta(days=HALF_LIFE_DAYS)
        score = TimeDecayEvaluator.calculate_temporal_freshness(obs, reference_time=ref)
        # exp(-1) ~ 0.367879 -> 36.79
        assert pytest.approx(score, abs=0.1) == 36.79

    def test_30_days_decay(self):
        ref = datetime.datetime.now(datetime.timezone.utc)
        obs = ref - datetime.timedelta(days=30)
        score = TimeDecayEvaluator.calculate_temporal_freshness(obs, reference_time=ref)
        # exp(-30/7) = exp(-4.2857) ~ 0.0137 -> 1.38
        assert score < 2.0
        assert score >= 0.0

    def test_future_timestamp_clamped_to_100(self):
        ref = datetime.datetime.now(datetime.timezone.utc)
        obs = ref + datetime.timedelta(minutes=3)
        score = TimeDecayEvaluator.calculate_temporal_freshness(obs, reference_time=ref)
        assert score == 100.0

    def test_score_always_bounded(self):
        ref = datetime.datetime.now(datetime.timezone.utc)
        for days in [-5, 0, 1, 7, 14, 30, 90, 365, 1000]:
            obs = ref - datetime.timedelta(days=days)
            score = TimeDecayEvaluator.calculate_temporal_freshness(obs, reference_time=ref)
            assert 0.0 <= score <= 100.0


class TestUserReliabilityEvaluator:
    """User reliability unit tests."""

    def test_citizen_cold_start_prior(self):
        uid = uuid.uuid4()
        score = UserReliabilityEvaluator.calculate_reliability(uid, db=None, role="citizen")
        assert score == DEFAULT_USER_RELIABILITY_CITIZEN

    def test_official_cold_start_prior(self):
        uid = uuid.uuid4()
        score = UserReliabilityEvaluator.calculate_reliability(uid, db=None, role="official")
        assert score == DEFAULT_USER_RELIABILITY_OFFICIAL

    def test_admin_cold_start_prior(self):
        uid = uuid.uuid4()
        score = UserReliabilityEvaluator.calculate_reliability(uid, db=None, role="admin")
        assert score == DEFAULT_USER_RELIABILITY_OFFICIAL


class TestGeoPlausibilityEvaluator:
    """Geo-plausibility unit tests without DB."""

    def test_within_india_envelope(self):
        score = GeoPlausibilityEvaluator.calculate_geo_plausibility(
            latitude=30.3,
            longitude=78.0,
            report_type="LANDSLIDE",
            db=None,
        )
        assert score == 40.0

    def test_outside_india_envelope(self):
        score = GeoPlausibilityEvaluator.calculate_geo_plausibility(
            latitude=51.5,
            longitude=-0.1,
            report_type="LANDSLIDE",
            db=None,
        )
        assert score == 20.0


class TestReportDeduplicator:
    """Text similarity and deduplication unit tests."""

    def test_exact_text_similarity(self):
        t1 = "Major rockfall blocking both lanes of NH-58"
        t2 = "Major rockfall blocking both lanes of NH-58"
        assert ReportDeduplicator.calculate_text_similarity(t1, t2) == 1.0

    def test_case_insensitive_text_similarity(self):
        t1 = "Major rockfall blocking NH-58"
        t2 = "MAJOR ROCKFALL BLOCKING NH-58"
        assert ReportDeduplicator.calculate_text_similarity(t1, t2) == 1.0

    def test_partial_overlap_similarity(self):
        t1 = "Fresh cracks along road edge near milestone 42"
        t2 = "Large cracks along road shoulder near milestone 42"
        sim = ReportDeduplicator.calculate_text_similarity(t1, t2)
        assert 0.5 <= sim < 1.0

    def test_disjoint_text_similarity(self):
        t1 = "Heavy flooding observed in lower village"
        t2 = "Rockfall and boulders blocking mountain highway"
        assert ReportDeduplicator.calculate_text_similarity(t1, t2) == 0.0

    def test_empty_string_similarity(self):
        assert ReportDeduplicator.calculate_text_similarity("", "Some text") == 0.0


class TestTrustScoringEngine:
    """Trust composite scoring unit tests."""

    def test_all_zero_inputs(self):
        res = TrustScoringEngine.calculate_trust(0.0, 0.0, 0.0, 0.0)
        assert res.trust_score == 0.0
        assert res.geo_contribution == 0.0
        assert res.temporal_contribution == 0.0
        assert res.user_contribution == 0.0
        assert res.corroboration_contribution == 0.0

    def test_all_max_inputs(self):
        res = TrustScoringEngine.calculate_trust(100.0, 100.0, 100.0, 100.0)
        assert res.trust_score == 100.0
        assert res.geo_contribution == 25.0
        assert res.temporal_contribution == 20.0
        assert res.user_contribution == 25.0
        assert res.corroboration_contribution == 30.0

    def test_exact_weights_and_formula(self):
        # 25% of 80 + 20% of 50 + 25% of 60 + 30% of 70
        # = 20.0 + 10.0 + 15.0 + 21.0 = 66.0
        res = TrustScoringEngine.calculate_trust(
            geo_plausibility=80.0,
            temporal_freshness=50.0,
            user_reliability=60.0,
            corroboration=70.0,
        )
        assert res.geo_contribution == 20.0
        assert res.temporal_contribution == 10.0
        assert res.user_contribution == 15.0
        assert res.corroboration_contribution == 21.0
        assert res.trust_score == 66.0

    def test_clamping_negative_inputs(self):
        res = TrustScoringEngine.calculate_trust(-50.0, -20.0, -10.0, -5.0)
        assert res.trust_score == 0.0

    def test_clamping_excessive_inputs(self):
        res = TrustScoringEngine.calculate_trust(150.0, 200.0, 120.0, 180.0)
        assert res.trust_score == 100.0

    def test_determinism(self):
        res1 = TrustScoringEngine.calculate_trust(70.0, 85.0, 60.0, 90.0)
        res2 = TrustScoringEngine.calculate_trust(70.0, 85.0, 60.0, 90.0)
        assert res1.trust_score == res2.trust_score


class TestTrustClassifier:
    """Trust classification mapping unit tests."""

    def test_low_tier(self):
        assert TrustClassifier.classify(0.0) == TrustClass.LOW
        assert TrustClassifier.classify(24.0) == TrustClass.LOW

    def test_moderate_tier(self):
        assert TrustClassifier.classify(24.01) == TrustClass.MODERATE
        assert TrustClassifier.classify(49.0) == TrustClass.MODERATE

    def test_high_tier(self):
        assert TrustClassifier.classify(49.01) == TrustClass.HIGH
        assert TrustClassifier.classify(74.0) == TrustClass.HIGH

    def test_very_high_tier(self):
        assert TrustClassifier.classify(74.01) == TrustClass.VERY_HIGH
        assert TrustClassifier.classify(100.0) == TrustClass.VERY_HIGH


class TestRiskEligibilityEvaluator:
    """Automated risk influence eligibility policy unit tests."""

    def test_fully_eligible_report(self):
        obs = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=6)
        eligible, reasons = RiskEligibilityEvaluator.is_eligible(
            trust_score=75.0,
            is_duplicate=False,
            status="SUBMITTED",
            observed_at=obs,
            geo_plausibility_score=70.0,
        )
        assert eligible is True
        assert len(reasons) == 0

    def test_low_trust_ineligible(self):
        obs = datetime.datetime.now(datetime.timezone.utc)
        eligible, reasons = RiskEligibilityEvaluator.is_eligible(
            trust_score=55.0,  # below 60.0
            is_duplicate=False,
            status="SUBMITTED",
            observed_at=obs,
            geo_plausibility_score=70.0,
        )
        assert eligible is False
        assert any("below minimum threshold" in r for r in reasons)

    def test_duplicate_ineligible(self):
        obs = datetime.datetime.now(datetime.timezone.utc)
        eligible, reasons = RiskEligibilityEvaluator.is_eligible(
            trust_score=85.0,
            is_duplicate=True,
            status="DUPLICATE",
            observed_at=obs,
            geo_plausibility_score=80.0,
        )
        assert eligible is False
        assert any("duplicate" in r for r in reasons)

    def test_rejected_status_ineligible(self):
        obs = datetime.datetime.now(datetime.timezone.utc)
        eligible, reasons = RiskEligibilityEvaluator.is_eligible(
            trust_score=85.0,
            is_duplicate=False,
            status="REJECTED",
            observed_at=obs,
            geo_plausibility_score=80.0,
        )
        assert eligible is False
        assert any("REJECTED" in r for r in reasons)

    def test_stale_observation_ineligible(self):
        # 20 days old exceeds 14 day horizon
        obs = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=20)
        eligible, reasons = RiskEligibilityEvaluator.is_eligible(
            trust_score=80.0,
            is_duplicate=False,
            status="SUBMITTED",
            observed_at=obs,
            geo_plausibility_score=70.0,
        )
        assert eligible is False
        assert any("operational horizon" in r for r in reasons)

    def test_low_geo_plausibility_ineligible(self):
        obs = datetime.datetime.now(datetime.timezone.utc)
        eligible, reasons = RiskEligibilityEvaluator.is_eligible(
            trust_score=65.0,
            is_duplicate=False,
            status="SUBMITTED",
            observed_at=obs,
            geo_plausibility_score=35.0,  # below 40.0
        )
        assert eligible is False
        assert any("Geo-plausibility" in r for r in reasons)


class TestGroundIntelligenceExplanationGenerator:
    """Explanation synthesis unit tests."""

    def test_explanation_structure(self):
        trust_res = TrustScoreResult(
            trust_score=72.0,
            geo_plausibility=80.0,
            temporal_freshness=90.0,
            user_reliability=50.0,
            corroboration=70.0,
            geo_contribution=20.0,
            temporal_contribution=18.0,
            user_contribution=12.5,
            corroboration_contribution=21.0,
        )
        statements = GroundIntelligenceExplanationGenerator.generate_explanation(
            trust_result=trust_res,
            trust_class=TrustClass.HIGH,
            is_duplicate=False,
            duplicate_match_reason=None,
            corroborating_count=2,
            risk_influence_eligible=True,
            eligibility_reasons=[],
        )

        assert len(statements) == 5
        assert "72.0/100" in statements[0]
        assert "HIGH" in statements[0]
        assert "Geo-Plausibility" in statements[1]
        assert "2 independent nearby field report(s)" in statements[2]
        assert "distinct, unique observation" in statements[3]
        assert "ELIGIBLE" in statements[4]
