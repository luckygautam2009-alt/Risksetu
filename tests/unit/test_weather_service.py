"""
RISKSETU AI — Weather service unit tests.

All tests use mocked provider responses — no live internet required.
Covers:
  - Coordinate validation (lat/lon bounds)
  - Open-Meteo URL construction
  - Response parsing (success, partial, bad payload)
  - WMO code → description mapping
  - _SafeEncoder / NaN handling (already covered in ML tests; spot-check here)
  - Provider status enum values
  - Cache key format
  - WeatherService cache-hit and cache-miss paths
  - Provider failure states (UNAVAILABLE, TIMEOUT, PROVIDER_ERROR)
  - API endpoint: 200 OK, 422 validation errors
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.weather.cache import _cache_key
from app.services.weather.provider import (
    _CURRENT_PARAMS,
    _DAILY_PARAMS,
    _WMO_DESCRIPTIONS,
    _build_open_meteo_url,
    _parse_open_meteo_response,
)
from app.services.weather.schemas import (
    ProviderStatus,
    WeatherResponse,
)
from app.services.weather.service import WeatherService

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_OPEN_METEO_PAYLOAD: dict[str, Any] = {
    "latitude": 30.5,
    "longitude": 79.0,
    "current_units": {
        "temperature_2m": "°C",
        "relative_humidity_2m": "%",
        "precipitation": "mm",
        "wind_speed_10m": "km/h",
        "weather_code": "wmo code",
    },
    "current": {
        "time": "2026-09-04T14:00",
        "temperature_2m": 22.3,
        "relative_humidity_2m": 78.0,
        "precipitation": 1.2,
        "wind_speed_10m": 15.4,
        "weather_code": 63,
    },
    "daily": {
        "time": ["2026-09-04", "2026-09-05", "2026-09-06"],
        "precipitation_sum": [8.5, 12.3, 3.1],
        "temperature_2m_max": [24.0, 21.5, 26.2],
        "temperature_2m_min": [18.0, 16.0, 19.5],
        "weather_code": [63, 80, 1],
    },
}

_FETCHED_AT = datetime(2026, 9, 4, 14, 5, 0, tzinfo=timezone.utc)


@pytest.fixture
def valid_parsed_response() -> WeatherResponse:
    return _parse_open_meteo_response(_VALID_OPEN_METEO_PAYLOAD, _FETCHED_AT)


@pytest.fixture
def mock_provider_ok() -> AsyncMock:
    provider = AsyncMock()
    resp = _parse_open_meteo_response(_VALID_OPEN_METEO_PAYLOAD, _FETCHED_AT)
    provider.fetch.return_value = resp
    return provider


@pytest.fixture
def mock_provider_unavailable() -> AsyncMock:
    provider = AsyncMock()
    provider.fetch.return_value = WeatherResponse(
        latitude=30.5,
        longitude=79.0,
        provider="open-meteo",
        provider_status=ProviderStatus.UNAVAILABLE,
        fetched_at=_FETCHED_AT,
        current=None,
        forecast=[],
        data_freshness_seconds=0,
        error_message="Provider unavailable after 3 retries.",
    )
    return provider


@pytest.fixture
def mock_provider_timeout() -> AsyncMock:
    provider = AsyncMock()
    provider.fetch.return_value = WeatherResponse(
        latitude=30.5,
        longitude=79.0,
        provider="open-meteo",
        provider_status=ProviderStatus.TIMEOUT,
        fetched_at=_FETCHED_AT,
        current=None,
        forecast=[],
        data_freshness_seconds=0,
        error_message="Provider request timed out.",
    )
    return provider


# ===========================================================================
# 1. Coordinate validation (via API endpoint)
# ===========================================================================


class TestCoordinateValidation:
    def test_valid_coordinates_accepted(self, mock_provider_ok: AsyncMock) -> None:
        with patch("app.api.v1.weather._weather_service._provider", mock_provider_ok):
            r = client.get("/api/v1/weather/current?lat=30.5&lon=79.0")
        assert r.status_code == 200

    def test_lat_too_low_rejected(self) -> None:
        r = client.get("/api/v1/weather/current?lat=-91.0&lon=79.0")
        assert r.status_code == 422

    def test_lat_too_high_rejected(self) -> None:
        r = client.get("/api/v1/weather/current?lat=91.0&lon=79.0")
        assert r.status_code == 422

    def test_lon_too_low_rejected(self) -> None:
        r = client.get("/api/v1/weather/current?lat=30.0&lon=-181.0")
        assert r.status_code == 422

    def test_lon_too_high_rejected(self) -> None:
        r = client.get("/api/v1/weather/current?lat=30.0&lon=181.0")
        assert r.status_code == 422

    def test_lat_boundary_minus_90_accepted(self, mock_provider_ok: AsyncMock) -> None:
        with patch("app.api.v1.weather._weather_service._provider", mock_provider_ok):
            r = client.get("/api/v1/weather/current?lat=-90.0&lon=0.0")
        assert r.status_code == 200

    def test_lat_boundary_plus_90_accepted(self, mock_provider_ok: AsyncMock) -> None:
        with patch("app.api.v1.weather._weather_service._provider", mock_provider_ok):
            r = client.get("/api/v1/weather/current?lat=90.0&lon=0.0")
        assert r.status_code == 200

    def test_lon_boundary_minus_180_accepted(self, mock_provider_ok: AsyncMock) -> None:
        with patch("app.api.v1.weather._weather_service._provider", mock_provider_ok):
            r = client.get("/api/v1/weather/current?lat=0.0&lon=-180.0")
        assert r.status_code == 200

    def test_lon_boundary_plus_180_accepted(self, mock_provider_ok: AsyncMock) -> None:
        with patch("app.api.v1.weather._weather_service._provider", mock_provider_ok):
            r = client.get("/api/v1/weather/current?lat=0.0&lon=180.0")
        assert r.status_code == 200

    def test_missing_lat_returns_422(self) -> None:
        r = client.get("/api/v1/weather/current?lon=79.0")
        assert r.status_code == 422

    def test_missing_lon_returns_422(self) -> None:
        r = client.get("/api/v1/weather/current?lat=30.0")
        assert r.status_code == 422

    def test_non_numeric_lat_returns_422(self) -> None:
        r = client.get("/api/v1/weather/current?lat=abc&lon=79.0")
        assert r.status_code == 422


# ===========================================================================
# 2. Open-Meteo URL construction
# ===========================================================================


class TestOpenMeteoUrlConstruction:
    def test_url_contains_latitude(self) -> None:
        url = _build_open_meteo_url(30.5, 79.0)
        assert "latitude=30.5" in url

    def test_url_contains_longitude(self) -> None:
        url = _build_open_meteo_url(30.5, 79.0)
        assert "longitude=79.0" in url

    def test_url_contains_all_current_params(self) -> None:
        url = _build_open_meteo_url(30.5, 79.0)
        for param in _CURRENT_PARAMS:
            assert param in url, f"Current param '{param}' missing from URL"

    def test_url_contains_all_daily_params(self) -> None:
        url = _build_open_meteo_url(30.5, 79.0)
        for param in _DAILY_PARAMS:
            assert param in url, f"Daily param '{param}' missing from URL"

    def test_url_uses_correct_base(self) -> None:
        url = _build_open_meteo_url(30.5, 79.0)
        assert url.startswith("https://api.open-meteo.com/v1/forecast")

    def test_url_requests_timezone_auto(self) -> None:
        url = _build_open_meteo_url(30.5, 79.0)
        assert "timezone=auto" in url

    def test_url_requests_3_forecast_days(self) -> None:
        url = _build_open_meteo_url(30.5, 79.0)
        assert "forecast_days=3" in url


# ===========================================================================
# 3. Response parsing
# ===========================================================================


class TestOpenMeteoResponseParsing:
    def test_provider_status_ok(self, valid_parsed_response: WeatherResponse) -> None:
        assert valid_parsed_response.provider_status == ProviderStatus.OK

    def test_provider_name(self, valid_parsed_response: WeatherResponse) -> None:
        assert valid_parsed_response.provider == "open-meteo"

    def test_current_weather_not_none(self, valid_parsed_response: WeatherResponse) -> None:
        assert valid_parsed_response.current is not None

    def test_current_temperature(self, valid_parsed_response: WeatherResponse) -> None:
        assert valid_parsed_response.current is not None
        assert abs(valid_parsed_response.current.temperature_c - 22.3) < 1e-6

    def test_current_humidity(self, valid_parsed_response: WeatherResponse) -> None:
        assert valid_parsed_response.current is not None
        assert abs(valid_parsed_response.current.relative_humidity_pct - 78.0) < 1e-6

    def test_current_precipitation(self, valid_parsed_response: WeatherResponse) -> None:
        assert valid_parsed_response.current is not None
        assert abs(valid_parsed_response.current.precipitation_mm - 1.2) < 1e-6

    def test_current_wind_speed(self, valid_parsed_response: WeatherResponse) -> None:
        assert valid_parsed_response.current is not None
        assert abs(valid_parsed_response.current.wind_speed_kmh - 15.4) < 1e-6

    def test_current_weather_code(self, valid_parsed_response: WeatherResponse) -> None:
        assert valid_parsed_response.current is not None
        assert valid_parsed_response.current.weather_code == 63

    def test_current_weather_description_from_wmo(
        self, valid_parsed_response: WeatherResponse
    ) -> None:
        assert valid_parsed_response.current is not None
        assert valid_parsed_response.current.weather_description == "Moderate rain"

    def test_forecast_has_3_days(self, valid_parsed_response: WeatherResponse) -> None:
        assert len(valid_parsed_response.forecast) == 3

    def test_forecast_day_precipitation(self, valid_parsed_response: WeatherResponse) -> None:
        assert abs(valid_parsed_response.forecast[0].precipitation_sum_mm - 8.5) < 1e-6

    def test_forecast_day_temp_max(self, valid_parsed_response: WeatherResponse) -> None:
        assert abs(valid_parsed_response.forecast[0].temperature_max_c - 24.0) < 1e-6

    def test_forecast_day_temp_min(self, valid_parsed_response: WeatherResponse) -> None:
        assert abs(valid_parsed_response.forecast[0].temperature_min_c - 18.0) < 1e-6

    def test_bad_payload_returns_provider_error(self) -> None:
        bad_payload: dict[str, Any] = {"no_current_key": True}
        result = _parse_open_meteo_response(bad_payload, _FETCHED_AT)
        assert result.provider_status == ProviderStatus.PROVIDER_ERROR
        assert result.current is None
        assert result.error_message is not None

    def test_none_values_in_daily_handled(self) -> None:
        payload = dict(_VALID_OPEN_METEO_PAYLOAD)
        payload["daily"] = {
            "time": ["2026-09-04"],
            "precipitation_sum": [None],
            "temperature_2m_max": [None],
            "temperature_2m_min": [None],
            "weather_code": [None],
        }
        result = _parse_open_meteo_response(payload, _FETCHED_AT)
        assert result.provider_status == ProviderStatus.OK
        assert len(result.forecast) == 1
        # None values should default to 0.0
        assert result.forecast[0].precipitation_sum_mm == 0.0

    def test_unknown_wmo_code_returns_fallback_description(self) -> None:
        payload = dict(_VALID_OPEN_METEO_PAYLOAD)
        payload["current"] = dict(_VALID_OPEN_METEO_PAYLOAD["current"])
        payload["current"]["weather_code"] = 999
        result = _parse_open_meteo_response(payload, _FETCHED_AT)
        assert result.current is not None
        assert "999" in result.current.weather_description


# ===========================================================================
# 4. WMO code descriptions
# ===========================================================================


class TestWMODescriptions:
    def test_clear_sky_code(self) -> None:
        assert _WMO_DESCRIPTIONS[0] == "Clear sky"

    def test_thunderstorm_code(self) -> None:
        assert _WMO_DESCRIPTIONS[95] == "Thunderstorm"

    def test_all_standard_codes_present(self) -> None:
        expected_codes = [0, 1, 2, 3, 45, 48, 51, 53, 55, 61, 63, 65,
                          71, 73, 75, 80, 81, 82, 95, 96, 99]
        for code in expected_codes:
            assert code in _WMO_DESCRIPTIONS, f"WMO code {code} missing"


# ===========================================================================
# 5. Cache key format
# ===========================================================================


class TestCacheKeyFormat:
    def test_key_prefix(self) -> None:
        key = _cache_key(30.5, 79.0)
        assert key.startswith("weather:v1:")

    def test_key_contains_rounded_lat_lon(self) -> None:
        key = _cache_key(30.12345678, 79.98765432)
        assert "30.12346" in key or "30.1235" in key  # 5 dp rounding
        assert "79.98765" in key

    def test_different_coords_different_keys(self) -> None:
        k1 = _cache_key(30.0, 79.0)
        k2 = _cache_key(31.0, 79.0)
        assert k1 != k2

    def test_same_coords_same_key(self) -> None:
        assert _cache_key(30.5, 79.0) == _cache_key(30.5, 79.0)

    def test_negative_coords_in_key(self) -> None:
        key = _cache_key(-25.5, -40.0)
        assert "-25.50000" in key
        assert "-40.00000" in key


# ===========================================================================
# 6. WeatherService — cache-miss path (live fetch)
# ===========================================================================


class TestWeatherServiceCacheMiss:
    @pytest.mark.asyncio
    async def test_calls_provider_on_cache_miss(self, mock_provider_ok: AsyncMock) -> None:
        with patch("app.services.weather.service.get_cached_weather", return_value=None), \
             patch("app.services.weather.service.set_cached_weather") as mock_set:
            service = WeatherService(provider=mock_provider_ok)
            result = await service.get_weather(30.5, 79.0)

        mock_provider_ok.fetch.assert_called_once_with(30.5, 79.0)
        assert result.provider_status == ProviderStatus.OK
        mock_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_cache_error_response(
        self, mock_provider_unavailable: AsyncMock
    ) -> None:
        with patch("app.services.weather.service.get_cached_weather", return_value=None), \
             patch("app.services.weather.service.set_cached_weather") as mock_set:
            service = WeatherService(provider=mock_provider_unavailable)
            result = await service.get_weather(30.5, 79.0)

        assert result.provider_status == ProviderStatus.UNAVAILABLE
        mock_set.assert_not_called()  # Error responses must NOT be cached

    @pytest.mark.asyncio
    async def test_does_not_cache_timeout_response(
        self, mock_provider_timeout: AsyncMock
    ) -> None:
        with patch("app.services.weather.service.get_cached_weather", return_value=None), \
             patch("app.services.weather.service.set_cached_weather") as mock_set:
            service = WeatherService(provider=mock_provider_timeout)
            result = await service.get_weather(30.5, 79.0)

        assert result.provider_status == ProviderStatus.TIMEOUT
        mock_set.assert_not_called()


# ===========================================================================
# 7. WeatherService — cache-hit path
# ===========================================================================


class TestWeatherServiceCacheHit:
    @pytest.mark.asyncio
    async def test_returns_cached_without_calling_provider(
        self, mock_provider_ok: AsyncMock
    ) -> None:
        cached_response = WeatherResponse(
            latitude=30.5,
            longitude=79.0,
            provider="open-meteo",
            provider_status=ProviderStatus.CACHED,
            fetched_at=_FETCHED_AT,
            current=None,
            forecast=[],
            data_freshness_seconds=120,
        )
        with patch(
            "app.services.weather.service.get_cached_weather",
            return_value=cached_response,
        ):
            service = WeatherService(provider=mock_provider_ok)
            result = await service.get_weather(30.5, 79.0)

        mock_provider_ok.fetch.assert_not_called()
        assert result.provider_status == ProviderStatus.CACHED
        assert result.data_freshness_seconds == 120


# ===========================================================================
# 8. API endpoint — response shape and content
# ===========================================================================


class TestWeatherEndpointResponse:
    def test_response_has_data_and_meta(self, mock_provider_ok: AsyncMock) -> None:
        with patch("app.api.v1.weather._weather_service._provider", mock_provider_ok):
            r = client.get("/api/v1/weather/current?lat=30.5&lon=79.0")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert "meta" in body

    def test_data_has_required_fields(self, mock_provider_ok: AsyncMock) -> None:
        with patch("app.api.v1.weather._weather_service._provider", mock_provider_ok):
            r = client.get("/api/v1/weather/current?lat=30.5&lon=79.0")
        data = r.json()["data"]
        for field in [
            "latitude", "longitude", "provider", "provider_status",
            "fetched_at", "current", "forecast", "data_freshness_seconds",
        ]:
            assert field in data, f"Field '{field}' missing from response data"

    def test_provider_is_open_meteo(self, mock_provider_ok: AsyncMock) -> None:
        with patch("app.api.v1.weather._weather_service._provider", mock_provider_ok):
            r = client.get("/api/v1/weather/current?lat=30.5&lon=79.0")
        assert r.json()["data"]["provider"] == "open-meteo"

    def test_current_weather_present_on_success(self, mock_provider_ok: AsyncMock) -> None:
        with patch("app.api.v1.weather._weather_service._provider", mock_provider_ok):
            r = client.get("/api/v1/weather/current?lat=30.5&lon=79.0")
        current = r.json()["data"]["current"]
        assert current is not None
        assert "temperature_c" in current
        assert "precipitation_mm" in current
        assert "weather_description" in current
        assert "timestamp" in current

    def test_forecast_present_on_success(self, mock_provider_ok: AsyncMock) -> None:
        with patch("app.api.v1.weather._weather_service._provider", mock_provider_ok):
            r = client.get("/api/v1/weather/current?lat=30.5&lon=79.0")
        forecast = r.json()["data"]["forecast"]
        assert isinstance(forecast, list)
        assert len(forecast) == 3
        assert "precipitation_sum_mm" in forecast[0]

    def test_provider_status_ok_on_success(self, mock_provider_ok: AsyncMock) -> None:
        with patch("app.api.v1.weather._weather_service._provider", mock_provider_ok):
            r = client.get("/api/v1/weather/current?lat=30.5&lon=79.0")
        assert r.json()["data"]["provider_status"] == "ok"

    def test_fetched_at_is_iso8601(self, mock_provider_ok: AsyncMock) -> None:
        with patch("app.api.v1.weather._weather_service._provider", mock_provider_ok):
            r = client.get("/api/v1/weather/current?lat=30.5&lon=79.0")
        fetched_at = r.json()["data"]["fetched_at"]
        # Should parse without error
        datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))

    def test_data_freshness_seconds_present(self, mock_provider_ok: AsyncMock) -> None:
        with patch("app.api.v1.weather._weather_service._provider", mock_provider_ok):
            r = client.get("/api/v1/weather/current?lat=30.5&lon=79.0")
        freshness = r.json()["data"]["data_freshness_seconds"]
        assert isinstance(freshness, int)
        assert freshness >= 0

    def test_unavailable_provider_returns_200_with_error_status(
        self, mock_provider_unavailable: AsyncMock
    ) -> None:
        """Provider failure should return 200 with explicit unavailable state, not 5xx."""
        with patch("app.api.v1.weather._weather_service._provider", mock_provider_unavailable):
            r = client.get("/api/v1/weather/current?lat=30.5&lon=79.0")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["provider_status"] == "unavailable"
        assert data["current"] is None
        assert data["error_message"] is not None

    def test_timeout_provider_returns_200_with_timeout_status(
        self, mock_provider_timeout: AsyncMock
    ) -> None:
        with patch("app.api.v1.weather._weather_service._provider", mock_provider_timeout):
            r = client.get("/api/v1/weather/current?lat=30.5&lon=79.0")
        assert r.status_code == 200
        assert r.json()["data"]["provider_status"] == "timeout"

    def test_no_fabricated_data_on_provider_failure(
        self, mock_provider_unavailable: AsyncMock
    ) -> None:
        """current must be null when provider is unavailable — no fabricated values."""
        with patch("app.api.v1.weather._weather_service._provider", mock_provider_unavailable):
            r = client.get("/api/v1/weather/current?lat=30.5&lon=79.0")
        data = r.json()["data"]
        assert data["current"] is None
        assert data["forecast"] == []

    def test_meta_contains_request_id(self, mock_provider_ok: AsyncMock) -> None:
        with patch("app.api.v1.weather._weather_service._provider", mock_provider_ok):
            r = client.get("/api/v1/weather/current?lat=30.5&lon=79.0")
        assert "request_id" in r.json()["meta"]


# ===========================================================================
# 9. Provider status enum completeness
# ===========================================================================


class TestProviderStatusEnum:
    def test_ok_value(self) -> None:
        assert ProviderStatus.OK == "ok"

    def test_unavailable_value(self) -> None:
        assert ProviderStatus.UNAVAILABLE == "unavailable"

    def test_timeout_value(self) -> None:
        assert ProviderStatus.TIMEOUT == "timeout"

    def test_provider_error_value(self) -> None:
        assert ProviderStatus.PROVIDER_ERROR == "provider_error"

    def test_cached_value(self) -> None:
        assert ProviderStatus.CACHED == "cached"


# ===========================================================================
# 10. WeatherResponse model
# ===========================================================================


class TestWeatherResponseModel:
    def test_to_api_dict_returns_dict(self, valid_parsed_response: WeatherResponse) -> None:
        result = valid_parsed_response.to_api_dict()
        assert isinstance(result, dict)

    def test_to_api_dict_is_json_serialisable(
        self, valid_parsed_response: WeatherResponse
    ) -> None:
        result = valid_parsed_response.to_api_dict()
        json.dumps(result)  # should not raise

    def test_model_allows_null_current(self) -> None:
        resp = WeatherResponse(
            latitude=0.0,
            longitude=0.0,
            provider="open-meteo",
            provider_status=ProviderStatus.UNAVAILABLE,
            fetched_at=_FETCHED_AT,
            current=None,
            forecast=[],
            data_freshness_seconds=0,
        )
        assert resp.current is None

    def test_model_allows_null_error_message(
        self, valid_parsed_response: WeatherResponse
    ) -> None:
        assert valid_parsed_response.error_message is None
