"""
RISKSETU AI — LIVE_RISK_V1 unit tests.

All external calls (weather, DB/risk engine) are mocked.
No live internet, no live DB required.

Test coverage:
  - Coordinate validation (bounds, missing params)
  - Historical risk integration (available, unavailable, error)
  - Weather integration (available, unavailable, timeout, provider_error, cached)
  - Weather trigger adjustment (tiers, cap, humidity)
  - ML status (unavailable — experimental artifact)
  - Terrain status (always unavailable)
  - Confidence calculation (all combos)
  - Final score composition (baseline + adjustment, clamping)
  - Risk level classification (LOW/MODERATE/HIGH/CRITICAL boundaries)
  - Contributing factors (only from actual data)
  - Recommended actions (per level)
  - Data freshness fields
  - No fabricated values (current/forecast null when weather unavailable)
  - Deterministic output (same inputs → same outputs)
  - Score bounds [0, 100]
  - Engine version tag
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.live_risk import LiveRiskData
from app.schemas.risk import RiskEvaluationData, RiskFactorDetail
from app.services.live_risk.constants import (
    CONF_DATA_LIMITED_MAX,
    ENGINE_VERSION,
    HUMIDITY_HIGH_THRESHOLD_PCT,
    PRECIP_EXTREME_MM_PER_H,
    PRECIP_HIGH_MM_PER_H,
    PRECIP_MODERATE_MM_PER_H,
    WEATHER_TRIGGER_CAP_POINTS,
)
from app.services.live_risk.engine import (
    LiveRiskEngine,
    _build_historical_layer,
    _build_weather_layer,
    _compute_confidence,
    _compute_weather_trigger_adjustment,
    _determine_risk_level,
)
from app.services.weather.schemas import (
    CurrentWeather,
    ForecastDay,
    ProviderStatus,
    WeatherResponse,
)

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 9, 4, 14, 0, 0, tzinfo=timezone.utc)


def _make_risk_data(score: float = 45.0, level: str = "MODERATE") -> RiskEvaluationData:
    factor = RiskFactorDetail(
        name="historical_landslide_evidence",
        display_name="Historical Landslide Spatial Density & Proximity",
        score=score,
        raw_weight=0.5,
        effective_weight=1.0,
        available=True,
        evidence={"count_within_5km": 3},
        explanation="3 slides within 5 km.",
    )
    return RiskEvaluationData(
        risk_score=score,
        risk_level=level,
        confidence_score=55.0,
        calculation_version="risk-v1",
        queried_location={"latitude": 30.5, "longitude": 79.0},
        factors=[factor],
        weight_redistributed=True,
        summary_explanation="Moderate historical evidence.",
        limitations=["No DEM available."],
    )


def _make_weather_response(
    precip_mm: float = 0.0,
    humidity: float = 60.0,
    status: ProviderStatus = ProviderStatus.OK,
) -> WeatherResponse:
    current = CurrentWeather(
        timestamp=_NOW,
        temperature_c=22.0,
        relative_humidity_pct=humidity,
        precipitation_mm=precip_mm,
        wind_speed_kmh=10.0,
        weather_code=63,
        weather_description="Moderate rain" if precip_mm > 2 else "Clear sky",
    )
    forecast = [
        ForecastDay(
            date=_NOW,
            precipitation_sum_mm=5.0,
            temperature_max_c=25.0,
            temperature_min_c=18.0,
            weather_code=63,
            weather_description="Moderate rain",
        )
    ]
    return WeatherResponse(
        latitude=30.5,
        longitude=79.0,
        provider="open-meteo",
        provider_status=status,
        fetched_at=_NOW,
        current=current if status in (ProviderStatus.OK, ProviderStatus.CACHED) else None,
        forecast=forecast if status in (ProviderStatus.OK, ProviderStatus.CACHED) else [],
        data_freshness_seconds=0,
    )


def _make_unavailable_weather(status: ProviderStatus = ProviderStatus.UNAVAILABLE) -> WeatherResponse:
    return WeatherResponse(
        latitude=30.5,
        longitude=79.0,
        provider="open-meteo",
        provider_status=status,
        fetched_at=_NOW,
        current=None,
        forecast=[],
        data_freshness_seconds=0,
        error_message="Provider unavailable.",
    )


@pytest.fixture
def mock_risk_engine() -> MagicMock:
    m = MagicMock()
    m.evaluate.return_value = _make_risk_data()
    return m


@pytest.fixture
def mock_weather_ok() -> AsyncMock:
    w = AsyncMock()
    w.get_weather.return_value = _make_weather_response(precip_mm=0.5)
    return w


@pytest.fixture
def mock_weather_unavailable() -> AsyncMock:
    w = AsyncMock()
    w.get_weather.return_value = _make_unavailable_weather(ProviderStatus.UNAVAILABLE)
    return w


@pytest.fixture
def mock_weather_heavy_rain() -> AsyncMock:
    w = AsyncMock()
    w.get_weather.return_value = _make_weather_response(
        precip_mm=PRECIP_HIGH_MM_PER_H + 1.0, humidity=85.0
    )
    return w


# ===========================================================================
# 1. Coordinate validation (via API endpoint)
# ===========================================================================


class TestCoordinateValidation:
    def _patch_engine(self) -> Any:
        """Patch LiveRiskEngine so tests don't hit DB or network."""
        mock_data = MagicMock()
        mock_data.model_dump.return_value = {}
        return patch(
            "app.api.v1.live_risk.LiveRiskEngine.assess",
            new_callable=AsyncMock,
            return_value=_build_minimal_live_risk_data(),
        )

    def test_valid_coordinates_accepted(self) -> None:
        with patch(
            "app.api.v1.live_risk.LiveRiskEngine.assess",
            new_callable=AsyncMock,
            return_value=_build_minimal_live_risk_data(),
        ):
            r = client.get("/api/v1/live-risk?lat=30.5&lon=79.0")
        assert r.status_code == 200

    def test_lat_too_low_rejected(self) -> None:
        r = client.get("/api/v1/live-risk?lat=-91.0&lon=79.0")
        assert r.status_code == 422

    def test_lat_too_high_rejected(self) -> None:
        r = client.get("/api/v1/live-risk?lat=91.0&lon=79.0")
        assert r.status_code == 422

    def test_lon_too_low_rejected(self) -> None:
        r = client.get("/api/v1/live-risk?lat=30.0&lon=-181.0")
        assert r.status_code == 422

    def test_lon_too_high_rejected(self) -> None:
        r = client.get("/api/v1/live-risk?lat=30.0&lon=181.0")
        assert r.status_code == 422

    def test_missing_lat_returns_422(self) -> None:
        r = client.get("/api/v1/live-risk?lon=79.0")
        assert r.status_code == 422

    def test_missing_lon_returns_422(self) -> None:
        r = client.get("/api/v1/live-risk?lat=30.0")
        assert r.status_code == 422

    def test_lat_boundary_minus90_accepted(self) -> None:
        with patch(
            "app.api.v1.live_risk.LiveRiskEngine.assess",
            new_callable=AsyncMock,
            return_value=_build_minimal_live_risk_data(),
        ):
            r = client.get("/api/v1/live-risk?lat=-90.0&lon=0.0")
        assert r.status_code == 200

    def test_lat_boundary_plus90_accepted(self) -> None:
        with patch(
            "app.api.v1.live_risk.LiveRiskEngine.assess",
            new_callable=AsyncMock,
            return_value=_build_minimal_live_risk_data(),
        ):
            r = client.get("/api/v1/live-risk?lat=90.0&lon=0.0")
        assert r.status_code == 200


def _build_minimal_live_risk_data() -> LiveRiskData:
    """Build the smallest valid LiveRiskData for API-level mock returns."""
    from app.schemas.live_risk import (
        DataFreshness,
        HistoricalRiskLayer,
        LiveRiskLocation,
        LiveRiskSummary,
        MLLayer,
        TerrainLayer,
        WeatherLayer,
    )
    return LiveRiskData(
        location=LiveRiskLocation(latitude=30.5, longitude=79.0),
        timestamp=_NOW,
        risk=LiveRiskSummary(score=45.0, level="MODERATE", confidence=55.0),
        historical=HistoricalRiskLayer(status="available", score=45.0, level="MODERATE", confidence=55.0),
        weather=WeatherLayer(status="available"),
        ml=MLLayer(status="unavailable"),
        terrain=TerrainLayer(status="unavailable"),
        data_freshness=DataFreshness(assessment_generated_at=_NOW),
    )


# ===========================================================================
# 2. Risk level determination (mirrors Phase 2A thresholds exactly)
# ===========================================================================


class TestRiskLevelDetermination:
    def test_score_0_is_low(self) -> None:
        assert _determine_risk_level(0.0) == "LOW"

    def test_score_24_is_low(self) -> None:
        assert _determine_risk_level(24.0) == "LOW"

    def test_score_24_1_is_moderate(self) -> None:
        assert _determine_risk_level(24.1) == "MODERATE"

    def test_score_49_is_moderate(self) -> None:
        assert _determine_risk_level(49.0) == "MODERATE"

    def test_score_49_1_is_high(self) -> None:
        assert _determine_risk_level(49.1) == "HIGH"

    def test_score_74_is_high(self) -> None:
        assert _determine_risk_level(74.0) == "HIGH"

    def test_score_74_1_is_critical(self) -> None:
        assert _determine_risk_level(74.1) == "CRITICAL"

    def test_score_100_is_critical(self) -> None:
        assert _determine_risk_level(100.0) == "CRITICAL"


# ===========================================================================
# 3. Weather trigger adjustment
# ===========================================================================


class TestWeatherTriggerAdjustment:
    def test_no_rain_no_adjustment(self) -> None:
        adj, factors = _compute_weather_trigger_adjustment(0.0, 50.0)
        assert adj == 0.0
        assert factors == []

    def test_light_rain_below_threshold_no_adjustment(self) -> None:
        adj, _ = _compute_weather_trigger_adjustment(PRECIP_MODERATE_MM_PER_H - 0.1, 50.0)
        assert adj == 0.0

    def test_moderate_rain_triggers_adjustment(self) -> None:
        adj, factors = _compute_weather_trigger_adjustment(PRECIP_MODERATE_MM_PER_H, 50.0)
        assert adj > 0.0
        assert any("moderate" in f.factor for f in factors)

    def test_heavy_rain_triggers_higher_adjustment(self) -> None:
        adj_mod, _ = _compute_weather_trigger_adjustment(PRECIP_MODERATE_MM_PER_H, 50.0)
        adj_heavy, _ = _compute_weather_trigger_adjustment(PRECIP_HIGH_MM_PER_H, 50.0)
        assert adj_heavy > adj_mod

    def test_extreme_rain_triggers_highest_adjustment(self) -> None:
        adj_heavy, _ = _compute_weather_trigger_adjustment(PRECIP_HIGH_MM_PER_H, 50.0)
        adj_extreme, _ = _compute_weather_trigger_adjustment(PRECIP_EXTREME_MM_PER_H, 50.0)
        assert adj_extreme >= adj_heavy

    def test_adjustment_capped_at_max(self) -> None:
        # Extreme rain + max humidity should not exceed cap
        adj, _ = _compute_weather_trigger_adjustment(200.0, 100.0)
        assert adj <= WEATHER_TRIGGER_CAP_POINTS

    def test_high_humidity_adds_adjustment(self) -> None:
        adj_low_hum, _ = _compute_weather_trigger_adjustment(0.0, HUMIDITY_HIGH_THRESHOLD_PCT - 1)
        adj_high_hum, factors = _compute_weather_trigger_adjustment(0.0, HUMIDITY_HIGH_THRESHOLD_PCT)
        assert adj_high_hum > adj_low_hum
        assert any("humidity" in f.factor for f in factors)

    def test_adjustment_non_negative(self) -> None:
        adj, _ = _compute_weather_trigger_adjustment(0.0, 0.0)
        assert adj >= 0.0

    def test_factors_source_is_weather(self) -> None:
        _, factors = _compute_weather_trigger_adjustment(PRECIP_HIGH_MM_PER_H, 85.0)
        for f in factors:
            assert f.source == "weather"


# ===========================================================================
# 4. Confidence calculation
# ===========================================================================


class TestConfidenceCalculation:
    def test_no_inputs_returns_data_limited_max(self) -> None:
        conf = _compute_confidence(
            historical_available=False,
            historical_confidence=0.0,
            weather_available=False,
            weather_freshness_seconds=0,
            ml_available=False,
            terrain_available=False,
        )
        assert conf <= CONF_DATA_LIMITED_MAX

    def test_historical_only_gives_partial_confidence(self) -> None:
        conf = _compute_confidence(
            historical_available=True,
            historical_confidence=60.0,
            weather_available=False,
            weather_freshness_seconds=0,
            ml_available=False,
            terrain_available=False,
        )
        assert conf > 0.0
        assert conf < 100.0

    def test_historical_plus_weather_gives_higher_confidence(self) -> None:
        conf_hist_only = _compute_confidence(
            historical_available=True,
            historical_confidence=60.0,
            weather_available=False,
            weather_freshness_seconds=0,
            ml_available=False,
            terrain_available=False,
        )
        conf_both = _compute_confidence(
            historical_available=True,
            historical_confidence=60.0,
            weather_available=True,
            weather_freshness_seconds=0,
            ml_available=False,
            terrain_available=False,
        )
        assert conf_both > conf_hist_only

    def test_confidence_in_0_100_range(self) -> None:
        conf = _compute_confidence(
            historical_available=True,
            historical_confidence=100.0,
            weather_available=True,
            weather_freshness_seconds=0,
            ml_available=True,
            terrain_available=True,
        )
        assert 0.0 <= conf <= 100.0

    def test_stale_weather_reduces_confidence(self) -> None:
        conf_fresh = _compute_confidence(
            historical_available=True,
            historical_confidence=60.0,
            weather_available=True,
            weather_freshness_seconds=0,
            ml_available=False,
            terrain_available=False,
        )
        conf_stale = _compute_confidence(
            historical_available=True,
            historical_confidence=60.0,
            weather_available=True,
            weather_freshness_seconds=3600,  # 1 hour stale
            ml_available=False,
            terrain_available=False,
        )
        assert conf_stale <= conf_fresh


# ===========================================================================
# 5. _build_historical_layer
# ===========================================================================


class TestBuildHistoricalLayer:
    def test_available_when_data_provided(self) -> None:
        hist = _make_risk_data(45.0, "MODERATE")
        layer = _build_historical_layer(hist, None)
        assert layer.status == "available"
        assert layer.score == 45.0
        assert layer.level == "MODERATE"

    def test_unavailable_when_none(self) -> None:
        layer = _build_historical_layer(None, None)
        assert layer.status == "unavailable"
        assert layer.score is None

    def test_error_when_error_message_provided(self) -> None:
        layer = _build_historical_layer(None, "DB connection failed")
        assert layer.status == "error"
        assert "DB connection" in (layer.summary or "")


# ===========================================================================
# 6. _build_weather_layer
# ===========================================================================


class TestBuildWeatherLayer:
    def test_available_status_for_ok_response(self) -> None:
        weather = _make_weather_response(precip_mm=5.0)
        layer = _build_weather_layer(weather)
        assert layer.status == "available"
        assert layer.precipitation_mm == 5.0

    def test_unavailable_for_unavailable_response(self) -> None:
        layer = _build_weather_layer(_make_unavailable_weather())
        assert layer.status == "unavailable"
        assert layer.precipitation_mm is None

    def test_cached_status_preserved(self) -> None:
        weather = _make_weather_response(status=ProviderStatus.CACHED)
        layer = _build_weather_layer(weather)
        assert layer.status == "cached"

    def test_timeout_status_preserved(self) -> None:
        layer = _build_weather_layer(_make_unavailable_weather(ProviderStatus.TIMEOUT))
        assert layer.status == "timeout"

    def test_none_response_returns_unavailable(self) -> None:
        layer = _build_weather_layer(None)
        assert layer.status == "unavailable"

    def test_forecast_precip_extracted(self) -> None:
        weather = _make_weather_response(precip_mm=1.0)
        layer = _build_weather_layer(weather)
        assert isinstance(layer.forecast_3day_precip_mm, list)
        assert len(layer.forecast_3day_precip_mm) >= 1

    def test_observation_time_populated(self) -> None:
        weather = _make_weather_response()
        layer = _build_weather_layer(weather)
        assert layer.observation_time is not None
        assert layer.fetched_at is not None


# ===========================================================================
# 7. ML status — always unavailable with current experimental artifact
# ===========================================================================


class TestMLStatus:
    def test_ml_unavailable_with_experimental_artifact(self) -> None:
        from app.services.live_risk.ml_status import get_ml_status
        status = get_ml_status()
        assert status["status"] == "unavailable"

    def test_ml_unavailable_reason_explains_why(self) -> None:
        from app.services.live_risk.ml_status import get_ml_status
        status = get_ml_status()
        assert status["reason"] is not None
        assert len(status["reason"]) > 0

    def test_ml_model_version_present_even_when_unavailable(self) -> None:
        """model_version should be returned even when unavailable — for provenance."""
        from app.services.live_risk.ml_status import get_ml_status
        status = get_ml_status()
        # model_version may be None if metadata unreadable, but we don't require it
        # The important thing is the key exists
        assert "model_version" in status


# ===========================================================================
# 8. LiveRiskEngine integration (full async assessment, mocked components)
# ===========================================================================


class TestLiveRiskEngineIntegration:
    @pytest.mark.asyncio
    async def test_full_assessment_structure(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_ok: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_ok)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)

        assert result.engine_version == ENGINE_VERSION
        assert result.location.latitude == 30.5
        assert result.location.longitude == 79.0
        assert isinstance(result.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_historical_available_populates_layer(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_ok: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_ok)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        assert result.historical.status == "available"
        assert result.historical.score == 45.0

    @pytest.mark.asyncio
    async def test_weather_available_populates_layer(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_ok: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_ok)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        assert result.weather.status in ("available", "cached")
        assert result.weather.precipitation_mm is not None

    @pytest.mark.asyncio
    async def test_ml_always_unavailable(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_ok: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_ok)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        assert result.ml.status == "unavailable"
        assert result.ml.susceptibility_score is None

    @pytest.mark.asyncio
    async def test_terrain_always_unavailable(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_ok: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_ok)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        assert result.terrain.status == "unavailable"
        assert result.terrain.elevation_m is None
        assert result.terrain.slope_degrees is None

    @pytest.mark.asyncio
    async def test_weather_unavailable_fallback_to_historical(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_unavailable: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_unavailable)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)

        # Score should equal historical baseline exactly (no trigger adjustment)
        assert result.risk.score == 45.0
        assert "live_weather" in result.unavailable_inputs

    @pytest.mark.asyncio
    async def test_weather_trigger_increases_score(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_heavy_rain: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_heavy_rain)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        # Heavy rain should push score above historical baseline of 45
        assert result.risk.score > 45.0

    @pytest.mark.asyncio
    async def test_score_never_exceeds_100(
        self,
        mock_weather_heavy_rain: AsyncMock,
    ) -> None:
        db = MagicMock()
        mock_engine = MagicMock()
        mock_engine.evaluate.return_value = _make_risk_data(score=95.0, level="CRITICAL")
        live_engine = LiveRiskEngine(db=db, weather_service=mock_weather_heavy_rain)
        live_engine._risk_engine = mock_engine

        result = await live_engine.assess(30.5, 79.0)
        assert result.risk.score <= 100.0

    @pytest.mark.asyncio
    async def test_score_never_below_0(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_unavailable: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_unavailable)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        assert result.risk.score >= 0.0

    @pytest.mark.asyncio
    async def test_historical_unavailable_sets_data_limited(
        self,
        mock_weather_ok: AsyncMock,
    ) -> None:
        db = MagicMock()
        mock_engine = MagicMock()
        mock_engine.evaluate.side_effect = RuntimeError("DB offline")
        live_engine = LiveRiskEngine(db=db, weather_service=mock_weather_ok)
        live_engine._risk_engine = mock_engine

        result = await live_engine.assess(30.5, 79.0)
        assert "historical_risk" in result.unavailable_inputs
        assert "assessment_data_limited" in result.unavailable_inputs

    @pytest.mark.asyncio
    async def test_weather_exception_handled_gracefully(
        self,
        mock_risk_engine: MagicMock,
    ) -> None:
        db = MagicMock()
        weather_svc = AsyncMock()
        weather_svc.get_weather.side_effect = ConnectionError("Network down")
        engine = LiveRiskEngine(db=db, weather_service=weather_svc)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        assert "live_weather" in result.unavailable_inputs

    @pytest.mark.asyncio
    async def test_ml_and_terrain_in_unavailable_inputs(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_ok: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_ok)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        assert "ml_susceptibility" in result.unavailable_inputs
        assert "terrain" in result.unavailable_inputs

    @pytest.mark.asyncio
    async def test_deterministic_output_same_inputs(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_ok: AsyncMock,
    ) -> None:
        """Same inputs must produce the same risk score."""
        db = MagicMock()

        engine1 = LiveRiskEngine(db=db, weather_service=mock_weather_ok)
        engine1._risk_engine = mock_risk_engine
        result1 = await engine1.assess(30.5, 79.0)

        engine2 = LiveRiskEngine(db=db, weather_service=mock_weather_ok)
        engine2._risk_engine = mock_risk_engine
        result2 = await engine2.assess(30.5, 79.0)

        assert result1.risk.score == result2.risk.score
        assert result1.risk.level == result2.risk.level


# ===========================================================================
# 9. Contributing factors — only from actual observations
# ===========================================================================


class TestContributingFactors:
    @pytest.mark.asyncio
    async def test_no_rain_no_precipitation_factor(
        self,
        mock_risk_engine: MagicMock,
    ) -> None:
        db = MagicMock()
        weather_svc = AsyncMock()
        weather_svc.get_weather.return_value = _make_weather_response(precip_mm=0.0)
        engine = LiveRiskEngine(db=db, weather_service=weather_svc)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        precip_factors = [
            f for f in result.contributing_factors
            if "precipitation" in f.factor
        ]
        assert precip_factors == []

    @pytest.mark.asyncio
    async def test_heavy_rain_adds_precipitation_factor(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_heavy_rain: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_heavy_rain)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        precip_factors = [
            f for f in result.contributing_factors
            if "precipitation" in f.factor
        ]
        assert len(precip_factors) >= 1

    @pytest.mark.asyncio
    async def test_historical_factor_appears_when_available(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_ok: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_ok)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        hist_factors = [
            f for f in result.contributing_factors if f.source == "historical"
        ]
        assert len(hist_factors) >= 1

    @pytest.mark.asyncio
    async def test_no_fabricated_factors_when_weather_unavailable(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_unavailable: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_unavailable)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        weather_factors = [f for f in result.contributing_factors if f.source == "weather"]
        # No weather-source factors should appear when weather is unavailable
        assert weather_factors == []


# ===========================================================================
# 10. Recommended actions
# ===========================================================================


class TestRecommendedActions:
    @pytest.mark.asyncio
    async def test_low_risk_has_routine_monitoring(
        self,
        mock_weather_ok: AsyncMock,
    ) -> None:
        db = MagicMock()
        mock_engine = MagicMock()
        mock_engine.evaluate.return_value = _make_risk_data(score=10.0, level="LOW")
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_ok)
        engine._risk_engine = mock_engine

        result = await engine.assess(30.5, 79.0)
        action_ids = [a.action_id for a in result.recommended_actions]
        assert "MONITOR_ROUTINE" in action_ids

    @pytest.mark.asyncio
    async def test_critical_risk_has_multiple_actions(
        self,
        mock_weather_ok: AsyncMock,
    ) -> None:
        db = MagicMock()
        mock_engine = MagicMock()
        mock_engine.evaluate.return_value = _make_risk_data(score=80.0, level="CRITICAL")
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_ok)
        engine._risk_engine = mock_engine

        result = await engine.assess(30.5, 79.0)
        assert len(result.recommended_actions) >= 4

    @pytest.mark.asyncio
    async def test_extreme_rain_adds_weather_action(
        self,
        mock_risk_engine: MagicMock,
    ) -> None:
        db = MagicMock()
        weather_svc = AsyncMock()
        weather_svc.get_weather.return_value = _make_weather_response(
            precip_mm=PRECIP_EXTREME_MM_PER_H + 5.0, humidity=90.0
        )
        engine = LiveRiskEngine(db=db, weather_service=weather_svc)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        action_ids = [a.action_id for a in result.recommended_actions]
        assert "ACTIVE_RAINFALL_EXTREME" in action_ids

    @pytest.mark.asyncio
    async def test_no_duplicate_action_ids(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_heavy_rain: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_heavy_rain)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        ids = [a.action_id for a in result.recommended_actions]
        assert len(ids) == len(set(ids)), "Duplicate action IDs found"


# ===========================================================================
# 11. Data freshness
# ===========================================================================


class TestDataFreshness:
    @pytest.mark.asyncio
    async def test_assessment_generated_at_is_populated(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_ok: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_ok)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        assert result.data_freshness.assessment_generated_at is not None

    @pytest.mark.asyncio
    async def test_weather_observation_time_populated_when_available(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_ok: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_ok)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        assert result.data_freshness.weather_observation_time is not None
        assert result.data_freshness.weather_fetched_at is not None

    @pytest.mark.asyncio
    async def test_weather_freshness_null_when_unavailable(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_unavailable: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_unavailable)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        assert result.data_freshness.weather_observation_time is None

    @pytest.mark.asyncio
    async def test_historical_data_version_populated(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_ok: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_ok)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        assert result.data_freshness.historical_data_version == "risk-v1"

    @pytest.mark.asyncio
    async def test_ml_artifact_version_null_when_unavailable(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_ok: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_ok)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        assert result.data_freshness.ml_artifact_version is None


# ===========================================================================
# 12. No fabricated values
# ===========================================================================


class TestNoFabricatedValues:
    @pytest.mark.asyncio
    async def test_weather_current_null_when_provider_fails(
        self,
        mock_risk_engine: MagicMock,
    ) -> None:
        db = MagicMock()
        weather_svc = AsyncMock()
        weather_svc.get_weather.return_value = _make_unavailable_weather()
        engine = LiveRiskEngine(db=db, weather_service=weather_svc)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        assert result.weather.precipitation_mm is None
        assert result.weather.temperature_c is None
        assert result.weather.humidity_pct is None

    @pytest.mark.asyncio
    async def test_ml_susceptibility_always_null(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_ok: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_ok)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        assert result.ml.susceptibility_score is None

    @pytest.mark.asyncio
    async def test_terrain_fields_always_null(
        self,
        mock_risk_engine: MagicMock,
        mock_weather_ok: AsyncMock,
    ) -> None:
        db = MagicMock()
        engine = LiveRiskEngine(db=db, weather_service=mock_weather_ok)
        engine._risk_engine = mock_risk_engine

        result = await engine.assess(30.5, 79.0)
        assert result.terrain.elevation_m is None
        assert result.terrain.slope_degrees is None
        assert result.terrain.aspect is None


# ===========================================================================
# 13. API endpoint response shape
# ===========================================================================


class TestAPIResponseShape:
    def test_response_has_data_and_meta(self) -> None:
        with patch(
            "app.api.v1.live_risk.LiveRiskEngine.assess",
            new_callable=AsyncMock,
            return_value=_build_minimal_live_risk_data(),
        ):
            r = client.get("/api/v1/live-risk?lat=30.5&lon=79.0")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert "meta" in body

    def test_data_has_required_top_level_fields(self) -> None:
        with patch(
            "app.api.v1.live_risk.LiveRiskEngine.assess",
            new_callable=AsyncMock,
            return_value=_build_minimal_live_risk_data(),
        ):
            r = client.get("/api/v1/live-risk?lat=30.5&lon=79.0")
        data = r.json()["data"]
        for field in [
            "location", "timestamp", "risk", "historical", "weather",
            "ml", "terrain", "contributing_factors", "unavailable_inputs",
            "recommended_actions", "data_freshness", "engine_version",
        ]:
            assert field in data, f"Field '{field}' missing from response"

    def test_engine_version_is_live_risk_v1(self) -> None:
        with patch(
            "app.api.v1.live_risk.LiveRiskEngine.assess",
            new_callable=AsyncMock,
            return_value=_build_minimal_live_risk_data(),
        ):
            r = client.get("/api/v1/live-risk?lat=30.5&lon=79.0")
        assert r.json()["data"]["engine_version"] == "LIVE_RISK_V1"

    def test_meta_contains_request_id(self) -> None:
        with patch(
            "app.api.v1.live_risk.LiveRiskEngine.assess",
            new_callable=AsyncMock,
            return_value=_build_minimal_live_risk_data(),
        ):
            r = client.get("/api/v1/live-risk?lat=30.5&lon=79.0")
        assert "request_id" in r.json()["meta"]

    def test_risk_has_score_level_confidence(self) -> None:
        with patch(
            "app.api.v1.live_risk.LiveRiskEngine.assess",
            new_callable=AsyncMock,
            return_value=_build_minimal_live_risk_data(),
        ):
            r = client.get("/api/v1/live-risk?lat=30.5&lon=79.0")
        risk = r.json()["data"]["risk"]
        assert "score" in risk
        assert "level" in risk
        assert "confidence" in risk

    def test_risk_score_within_bounds(self) -> None:
        with patch(
            "app.api.v1.live_risk.LiveRiskEngine.assess",
            new_callable=AsyncMock,
            return_value=_build_minimal_live_risk_data(),
        ):
            r = client.get("/api/v1/live-risk?lat=30.5&lon=79.0")
        score = r.json()["data"]["risk"]["score"]
        assert 0.0 <= score <= 100.0

    def test_ml_status_unavailable_in_response(self) -> None:
        with patch(
            "app.api.v1.live_risk.LiveRiskEngine.assess",
            new_callable=AsyncMock,
            return_value=_build_minimal_live_risk_data(),
        ):
            r = client.get("/api/v1/live-risk?lat=30.5&lon=79.0")
        ml = r.json()["data"]["ml"]
        assert ml["status"] == "unavailable"
        assert ml["susceptibility_score"] is None

    def test_terrain_status_unavailable_in_response(self) -> None:
        with patch(
            "app.api.v1.live_risk.LiveRiskEngine.assess",
            new_callable=AsyncMock,
            return_value=_build_minimal_live_risk_data(),
        ):
            r = client.get("/api/v1/live-risk?lat=30.5&lon=79.0")
        terrain = r.json()["data"]["terrain"]
        assert terrain["status"] == "unavailable"
        assert terrain["elevation_m"] is None
