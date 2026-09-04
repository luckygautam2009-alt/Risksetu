"""
Unit tests for Phase 2C Impact-Aware Intervention Priority Engine.

Tests cover:
  - UrgencyEvaluator deterministic calculation
  - PriorityScoringEngine composite scoring and categorical levels
  - PriorityRankingEngine deterministic multi-tier tie-breaking
  - PriorityExplanationGenerator summary generation
  - PriorityEvaluationEngine orchestration with pre-supplied metrics
  - Boundary clamping, edge cases, and determinism guarantees
"""
from __future__ import annotations

import pytest

from app.services.priority.constants import (
    CALCULATION_VERSION,
    PRIORITY_LEVEL_HIGH_MAX,
    PRIORITY_LEVEL_LOW_MAX,
    PRIORITY_LEVEL_MODERATE_MAX,
    STANDARD_PRIORITY_LIMITATIONS,
    WEIGHT_IMPACT,
    WEIGHT_RISK,
    WEIGHT_URGENCY,
)
from app.services.priority.engine import PriorityEvaluationEngine
from app.services.priority.explanation import PriorityExplanationGenerator
from app.services.priority.ranking import PriorityRankingEngine
from app.services.priority.scoring import PriorityBreakdown, PriorityScoringEngine
from app.services.priority.urgency import UrgencyEvaluator


# ── Constants Integrity ──────────────────────────────────────────────────

class TestConstants:
    """Verify constants are internally consistent."""

    def test_weights_sum_to_one(self) -> None:
        assert abs(WEIGHT_RISK + WEIGHT_IMPACT + WEIGHT_URGENCY - 1.0) < 1e-9

    def test_priority_thresholds_monotonic(self) -> None:
        assert PRIORITY_LEVEL_LOW_MAX < PRIORITY_LEVEL_MODERATE_MAX < PRIORITY_LEVEL_HIGH_MAX

    def test_calculation_version_is_set(self) -> None:
        assert CALCULATION_VERSION == "priority-v1"

    def test_limitations_not_empty(self) -> None:
        assert len(STANDARD_PRIORITY_LIMITATIONS) >= 5


# ── Urgency Evaluator ───────────────────────────────────────────────────

class TestUrgencyEvaluator:
    """Verify urgency score calculation."""

    def test_critical_full_confidence(self) -> None:
        score = UrgencyEvaluator.calculate_urgency("CRITICAL", 100.0)
        assert score == 100.0

    def test_low_zero_confidence(self) -> None:
        score = UrgencyEvaluator.calculate_urgency("LOW", 0.0)
        assert score == 12.5  # 25.0 * (0.5 + 0.0)

    def test_moderate_half_confidence(self) -> None:
        score = UrgencyEvaluator.calculate_urgency("MODERATE", 50.0)
        assert score == 37.5  # 50.0 * (0.5 + 0.25)

    def test_high_full_confidence(self) -> None:
        score = UrgencyEvaluator.calculate_urgency("HIGH", 100.0)
        assert score == 75.0

    def test_unknown_level_defaults_to_low(self) -> None:
        score = UrgencyEvaluator.calculate_urgency("UNKNOWN", 100.0)
        assert score == 25.0  # defaults to 25.0 base

    def test_case_insensitive(self) -> None:
        score1 = UrgencyEvaluator.calculate_urgency("critical", 80.0)
        score2 = UrgencyEvaluator.calculate_urgency("CRITICAL", 80.0)
        assert score1 == score2

    def test_clamping_negative_confidence(self) -> None:
        score = UrgencyEvaluator.calculate_urgency("HIGH", -10.0)
        assert score >= 0.0

    def test_clamping_over_100_confidence(self) -> None:
        score = UrgencyEvaluator.calculate_urgency("HIGH", 200.0)
        assert score <= 100.0

    def test_result_always_bounded(self) -> None:
        for level in ["LOW", "MODERATE", "HIGH", "CRITICAL"]:
            for conf in [0.0, 25.0, 50.0, 75.0, 100.0]:
                s = UrgencyEvaluator.calculate_urgency(level, conf)
                assert 0.0 <= s <= 100.0


# ── Priority Scoring Engine ─────────────────────────────────────────────

class TestPriorityScoringEngine:
    """Verify composite priority scoring."""

    def test_all_zero_inputs(self) -> None:
        bd = PriorityScoringEngine.calculate_priority(0.0, 0.0, 0.0)
        assert bd.priority_score == 0.0
        assert bd.priority_level == "LOW"

    def test_all_max_inputs(self) -> None:
        bd = PriorityScoringEngine.calculate_priority(100.0, 100.0, 100.0)
        assert bd.priority_score == 100.0
        assert bd.priority_level == "CRITICAL"

    def test_risk_only(self) -> None:
        bd = PriorityScoringEngine.calculate_priority(100.0, 0.0, 0.0)
        assert bd.priority_score == 45.0
        assert bd.risk_contribution == 45.0
        assert bd.impact_contribution == 0.0
        assert bd.urgency_contribution == 0.0

    def test_impact_only(self) -> None:
        bd = PriorityScoringEngine.calculate_priority(0.0, 100.0, 0.0)
        assert bd.priority_score == 40.0
        assert bd.impact_contribution == 40.0

    def test_urgency_only(self) -> None:
        bd = PriorityScoringEngine.calculate_priority(0.0, 0.0, 100.0)
        assert bd.priority_score == 15.0
        assert bd.urgency_contribution == 15.0

    def test_weighted_formula_correctness(self) -> None:
        bd = PriorityScoringEngine.calculate_priority(60.0, 80.0, 40.0)
        expected = round(0.45 * 60.0 + 0.40 * 80.0 + 0.15 * 40.0, 2)
        assert bd.priority_score == expected

    def test_contributions_sum_to_score(self) -> None:
        """Verify contribution breakdown sums approximate the total score."""
        bd = PriorityScoringEngine.calculate_priority(55.0, 72.0, 33.0)
        contrib_sum = bd.risk_contribution + bd.impact_contribution + bd.urgency_contribution
        assert abs(contrib_sum - bd.priority_score) < 0.05

    def test_level_low(self) -> None:
        assert PriorityScoringEngine.determine_priority_level(10.0) == "LOW"

    def test_level_moderate(self) -> None:
        assert PriorityScoringEngine.determine_priority_level(30.0) == "MODERATE"

    def test_level_high(self) -> None:
        assert PriorityScoringEngine.determine_priority_level(60.0) == "HIGH"

    def test_level_critical(self) -> None:
        assert PriorityScoringEngine.determine_priority_level(90.0) == "CRITICAL"

    def test_boundary_low_moderate(self) -> None:
        assert PriorityScoringEngine.determine_priority_level(PRIORITY_LEVEL_LOW_MAX) == "LOW"
        assert PriorityScoringEngine.determine_priority_level(PRIORITY_LEVEL_LOW_MAX + 0.01) == "MODERATE"

    def test_boundary_moderate_high(self) -> None:
        assert PriorityScoringEngine.determine_priority_level(PRIORITY_LEVEL_MODERATE_MAX) == "MODERATE"
        assert PriorityScoringEngine.determine_priority_level(PRIORITY_LEVEL_MODERATE_MAX + 0.01) == "HIGH"

    def test_boundary_high_critical(self) -> None:
        assert PriorityScoringEngine.determine_priority_level(PRIORITY_LEVEL_HIGH_MAX) == "HIGH"
        assert PriorityScoringEngine.determine_priority_level(PRIORITY_LEVEL_HIGH_MAX + 0.01) == "CRITICAL"

    def test_clamping_negative_inputs(self) -> None:
        bd = PriorityScoringEngine.calculate_priority(-50.0, -30.0, -10.0)
        assert bd.priority_score == 0.0

    def test_clamping_over_100_inputs(self) -> None:
        bd = PriorityScoringEngine.calculate_priority(200.0, 150.0, 300.0)
        assert bd.priority_score == 100.0

    def test_determinism(self) -> None:
        r1 = PriorityScoringEngine.calculate_priority(55.0, 72.0, 33.0)
        r2 = PriorityScoringEngine.calculate_priority(55.0, 72.0, 33.0)
        assert r1.priority_score == r2.priority_score
        assert r1.priority_level == r2.priority_level


# ── Priority Ranking Engine ──────────────────────────────────────────────

class TestPriorityRankingEngine:
    """Verify deterministic multi-tier ranking."""

    def _make_candidate(
        self,
        cid: str,
        risk: float = 50.0,
        iso: float = 50.0,
        conf: float = 50.0,
        level: str = "MODERATE",
    ) -> dict:
        return {
            "candidate_id": cid,
            "latitude": 30.0,
            "longitude": 78.0,
            "risk_score": risk,
            "risk_level": level,
            "risk_confidence": conf,
            "isolation_severity": iso,
            "component_increase": 0,
            "nodes_affected": 0,
            "edges_in_affected_components": 0,
            "is_bridge_edge": False,
        }

    def test_empty_input(self) -> None:
        assert PriorityRankingEngine.rank_candidates([]) == []

    def test_single_candidate(self) -> None:
        result = PriorityRankingEngine.rank_candidates([self._make_candidate("a")])
        assert len(result) == 1
        assert result[0].rank == 1
        assert result[0].candidate_id == "a"

    def test_descending_priority_order(self) -> None:
        candidates = [
            self._make_candidate("low", risk=10.0, iso=10.0, level="LOW"),
            self._make_candidate("high", risk=90.0, iso=90.0, level="CRITICAL"),
            self._make_candidate("mid", risk=50.0, iso=50.0, level="MODERATE"),
        ]
        result = PriorityRankingEngine.rank_candidates(candidates)
        assert result[0].candidate_id == "high"
        assert result[1].candidate_id == "mid"
        assert result[2].candidate_id == "low"
        assert result[0].rank == 1
        assert result[1].rank == 2
        assert result[2].rank == 3

    def test_tie_breaking_by_isolation(self) -> None:
        """When priority scores tie, higher isolation severity wins."""
        candidates = [
            self._make_candidate("a", risk=50.0, iso=60.0),
            self._make_candidate("b", risk=50.0, iso=70.0),
        ]
        result = PriorityRankingEngine.rank_candidates(candidates)
        assert result[0].candidate_id == "b"

    def test_tie_breaking_by_candidate_id(self) -> None:
        """When all scores tie, lexicographic candidate_id ASC is final tiebreaker."""
        candidates = [
            self._make_candidate("z_candidate"),
            self._make_candidate("a_candidate"),
        ]
        result = PriorityRankingEngine.rank_candidates(candidates)
        assert result[0].candidate_id == "a_candidate"
        assert result[1].candidate_id == "z_candidate"

    def test_ranking_determinism(self) -> None:
        candidates = [
            self._make_candidate("c", risk=50.0, iso=70.0),
            self._make_candidate("a", risk=80.0, iso=20.0),
            self._make_candidate("b", risk=30.0, iso=90.0),
        ]
        r1 = PriorityRankingEngine.rank_candidates(candidates)
        r2 = PriorityRankingEngine.rank_candidates(candidates)
        for a, b in zip(r1, r2):
            assert a.candidate_id == b.candidate_id
            assert a.rank == b.rank
            assert a.priority_score == b.priority_score

    def test_ranked_items_have_explanation(self) -> None:
        result = PriorityRankingEngine.rank_candidates([self._make_candidate("x")])
        assert len(result[0].explanation) > 0

    def test_ranked_items_have_breakdown(self) -> None:
        result = PriorityRankingEngine.rank_candidates([self._make_candidate("x")])
        bd = result[0].breakdown
        assert isinstance(bd, PriorityBreakdown)
        assert bd.priority_score >= 0.0


# ── Priority Explanation Generator ───────────────────────────────────────

class TestPriorityExplanationGenerator:
    """Verify explanation generation semantics."""

    def test_impact_driven_explanation(self) -> None:
        explanation = PriorityExplanationGenerator.generate_summary(
            priority_score=70.0, priority_level="HIGH",
            risk_score=30.0, isolation_severity=85.0,
            urgency_score=50.0, is_bridge_edge=True, nodes_affected=15,
        )
        assert "connectivity disruption" in explanation.lower() or "isolation" in explanation.lower()
        assert "bridge" in explanation.lower()

    def test_risk_driven_explanation(self) -> None:
        explanation = PriorityExplanationGenerator.generate_summary(
            priority_score=65.0, priority_level="HIGH",
            risk_score=85.0, isolation_severity=20.0,
            urgency_score=60.0, is_bridge_edge=False, nodes_affected=2,
        )
        assert "hazard risk" in explanation.lower()

    def test_balanced_explanation(self) -> None:
        explanation = PriorityExplanationGenerator.generate_summary(
            priority_score=50.0, priority_level="HIGH",
            risk_score=50.0, isolation_severity=50.0,
            urgency_score=50.0, is_bridge_edge=False, nodes_affected=5,
        )
        assert "balanced" in explanation.lower()

    def test_explanation_includes_level(self) -> None:
        explanation = PriorityExplanationGenerator.generate_summary(
            priority_score=50.0, priority_level="HIGH",
            risk_score=50.0, isolation_severity=50.0,
            urgency_score=50.0, is_bridge_edge=False, nodes_affected=5,
        )
        assert "HIGH" in explanation

    def test_limitations_not_empty(self) -> None:
        lims = PriorityExplanationGenerator.get_limitations()
        assert len(lims) >= 5


# ── Priority Evaluation Engine (Unit, No DB) ────────────────────────────

class TestPriorityEvaluationEngineUnit:
    """Verify engine with pre-supplied metrics (no DB dependency)."""

    def test_evaluate_with_all_metrics_supplied(self) -> None:
        engine = PriorityEvaluationEngine(db=None)
        result = engine.evaluate(
            candidate_id="test_01",
            latitude=30.0,
            longitude=78.0,
            risk_score=70.0,
            risk_level="HIGH",
            risk_confidence=80.0,
            isolation_severity=60.0,
            component_increase=2,
            nodes_affected=10,
            edges_in_affected_components=5,
            is_bridge_edge=True,
        )
        assert result.candidate_id == "test_01"
        assert result.latitude == 30.0
        assert result.longitude == 78.0
        assert 0.0 <= result.priority_score <= 100.0
        assert result.priority_level in ("LOW", "MODERATE", "HIGH", "CRITICAL")
        assert result.risk_score == 70.0
        assert result.isolation_severity == 60.0
        assert result.is_bridge_edge is True
        assert result.calculation_version == CALCULATION_VERSION
        assert len(result.limitations) >= 5
        assert len(result.explanation) > 0

    def test_evaluate_auto_generates_candidate_id(self) -> None:
        engine = PriorityEvaluationEngine(db=None)
        result = engine.evaluate(
            risk_score=50.0, risk_level="MODERATE",
            risk_confidence=50.0, isolation_severity=50.0,
        )
        assert result.candidate_id.startswith("cand_")

    def test_evaluate_defaults_when_no_db(self) -> None:
        """Without DB and without metrics, defaults to zero/LOW."""
        engine = PriorityEvaluationEngine(db=None)
        result = engine.evaluate()
        assert result.risk_score == 0.0
        assert result.risk_level == "LOW"
        assert result.isolation_severity == 0.0
        assert result.priority_score == pytest.approx(
            0.45 * 0.0 + 0.40 * 0.0 + 0.15 * UrgencyEvaluator.calculate_urgency("LOW", 50.0),
            abs=0.05,
        )

    def test_evaluate_determinism(self) -> None:
        engine = PriorityEvaluationEngine(db=None)
        kwargs = dict(
            candidate_id="det_test", latitude=30.0, longitude=78.0,
            risk_score=65.0, risk_level="HIGH", risk_confidence=70.0,
            isolation_severity=55.0, component_increase=1,
            nodes_affected=5, edges_in_affected_components=3,
            is_bridge_edge=False,
        )
        r1 = engine.evaluate(**kwargs)
        r2 = engine.evaluate(**kwargs)
        assert r1.priority_score == r2.priority_score
        assert r1.priority_level == r2.priority_level
        assert r1.urgency_score == r2.urgency_score
        assert r1.explanation == r2.explanation

    def test_evaluate_score_formula(self) -> None:
        engine = PriorityEvaluationEngine(db=None)
        result = engine.evaluate(
            risk_score=60.0, risk_level="HIGH",
            risk_confidence=80.0, isolation_severity=80.0,
        )
        expected_urgency = UrgencyEvaluator.calculate_urgency("HIGH", 80.0)
        expected_score = round(0.45 * 60.0 + 0.40 * 80.0 + 0.15 * expected_urgency, 2)
        assert result.priority_score == expected_score

    def test_evaluate_result_has_breakdown(self) -> None:
        engine = PriorityEvaluationEngine(db=None)
        result = engine.evaluate(risk_score=50.0, risk_level="MODERATE",
                                  risk_confidence=50.0, isolation_severity=50.0)
        assert isinstance(result.breakdown, PriorityBreakdown)
        assert result.breakdown.risk_contribution == round(0.45 * 50.0, 2)
        assert result.breakdown.impact_contribution == round(0.40 * 50.0, 2)
