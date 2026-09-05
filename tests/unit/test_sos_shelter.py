"""
RISKSETU AI — SOS + Shelter unit tests.

Uses FastAPI dependency_overrides to inject mock users without hitting DB or JWT.
All external calls (DB, live-risk, weather) are mocked. No live internet required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.services.auth.dependencies import get_current_user, require_role
from app.services.sos.constants import (
    SOSStatus,
    SUITABILITY_MAX_DISTANCE_M,
    SUITABILITY_W_DISTANCE,
)
from app.services.sos.shelter_service import (
    _distance_score,
    compute_suitability,
)
from app.services.sos.service import transition_sos_status

client = TestClient(app)
_NOW = datetime(2026, 9, 4, 15, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# User factories
# ---------------------------------------------------------------------------

def _user(role: str = "citizen") -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = f"{uuid.uuid4()}@test.com"
    u.hashed_password = "x"
    u.role = role
    u.is_active = True
    return u


_CITIZEN = _user("citizen")
_OFFICIAL = _user("official")
_ADMIN = _user("admin")
_OTHER_CITIZEN = _user("citizen")


# ---------------------------------------------------------------------------
# Dependency override helpers
# ---------------------------------------------------------------------------

def _override_user(user: User) -> None:
    """Override get_current_user and the require_role factory for the given user."""
    app.dependency_overrides[get_current_user] = lambda: user

    def _make_role_dep(roles: list[str]) -> Any:
        def _check() -> User:
            if user.role not in roles:
                from app.core.errors import ForbiddenError
                raise ForbiddenError(f"Requires role: {roles}")
            return user
        return _check

    app.dependency_overrides[require_role] = _make_role_dep


def _clear_overrides() -> None:
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# SOS mock factory
# ---------------------------------------------------------------------------

def _mock_sos(
    reported_by: uuid.UUID | None = None,
    status: str = "ACTIVE",
    risk_score: float | None = None,
    risk_level: str | None = None,
) -> MagicMock:
    sos = MagicMock()
    sos.id = uuid.uuid4()
    sos.latitude = 30.3
    sos.longitude = 79.6
    sos.severity = "HIGH"
    sos.status = status
    sos.description = "Landslide near village"
    sos.live_risk_score = risk_score
    sos.live_risk_level = risk_level
    sos.live_risk_confidence = 60.0 if risk_score else None
    sos.risk_context = {"weather_status": "available"} if risk_score else None
    sos.linked_alert_id = None
    sos.reported_by = reported_by
    sos.acknowledged_by = None
    sos.acknowledged_at = None
    sos.resolved_by = None
    sos.resolved_at = None
    sos.request_id = "req-123"
    sos.created_at = _NOW
    sos.updated_at = _NOW
    return sos


# ---------------------------------------------------------------------------
# Shared live-risk mock
# ---------------------------------------------------------------------------

def _mock_live_engine(risk_score: float = 40.0) -> MagicMock:
    engine = MagicMock()
    engine.assess = AsyncMock(return_value=MagicMock(
        risk=MagicMock(score=risk_score, level="MODERATE", confidence=55.0),
        historical=MagicMock(status="available"),
        weather=MagicMock(status="available"),
        timestamp=_NOW,
    ))
    return engine


# ===========================================================================
# 1. Coordinate validation
# ===========================================================================

class TestSOSCoordinateValidation:
    def setup_method(self) -> None:
        _override_user(_CITIZEN)

    def teardown_method(self) -> None:
        _clear_overrides()

    def test_valid_coordinates_accepted(self) -> None:
        sos_m = _mock_sos(reported_by=_CITIZEN.id)
        with patch("app.api.v1.sos.create_sos", return_value=sos_m), \
             patch("app.api.v1.sos.LiveRiskEngine", return_value=_mock_live_engine()), \
             patch("app.api.v1.sos.attach_risk_context", return_value=sos_m), \
             patch("app.api.v1.sos.maybe_generate_sos_alert", return_value=None):
            r = client.post("/api/v1/sos", json={"latitude": 30.3, "longitude": 79.6})
        assert r.status_code == 201

    def test_lat_out_of_range_rejected(self) -> None:
        r = client.post("/api/v1/sos", json={"latitude": 91.0, "longitude": 79.6})
        assert r.status_code == 422

    def test_lon_out_of_range_rejected(self) -> None:
        r = client.post("/api/v1/sos", json={"latitude": 30.0, "longitude": 181.0})
        assert r.status_code == 422

    def test_missing_latitude(self) -> None:
        r = client.post("/api/v1/sos", json={"longitude": 79.6})
        assert r.status_code == 422

    def test_missing_longitude(self) -> None:
        r = client.post("/api/v1/sos", json={"latitude": 30.0})
        assert r.status_code == 422

    def test_extra_fields_rejected(self) -> None:
        r = client.post("/api/v1/sos", json={
            "latitude": 30.0, "longitude": 79.0, "hack": "x"
        })
        assert r.status_code == 422


# ===========================================================================
# 2. Authentication
# ===========================================================================

class TestSOSAuth:
    def teardown_method(self) -> None:
        _clear_overrides()

    def test_unauthenticated_post_returns_401_or_403(self) -> None:
        r = client.post("/api/v1/sos", json={"latitude": 30.0, "longitude": 79.0})
        assert r.status_code in (401, 403)

    def test_unauthenticated_get_returns_401_or_403(self) -> None:
        r = client.get("/api/v1/sos")
        assert r.status_code in (401, 403)

    def test_unauthenticated_shelter_returns_401_or_403(self) -> None:
        r = client.get("/api/v1/shelters/nearby?lat=30.0&lon=79.0")
        assert r.status_code in (401, 403)

    def test_citizen_cannot_acknowledge(self) -> None:
        _override_user(_CITIZEN)
        sos_m = _mock_sos(reported_by=_CITIZEN.id)
        with patch("app.api.v1.sos.get_sos_by_id", return_value=sos_m):
            r = client.post(f"/api/v1/sos/{sos_m.id}/acknowledge", json={})
        assert r.status_code == 403

    def test_citizen_cannot_resolve(self) -> None:
        _override_user(_CITIZEN)
        sos_m = _mock_sos(reported_by=_CITIZEN.id)
        with patch("app.api.v1.sos.get_sos_by_id", return_value=sos_m):
            r = client.post(f"/api/v1/sos/{sos_m.id}/resolve", json={})
        assert r.status_code == 403

    def test_citizen_cannot_view_other_sos(self) -> None:
        _override_user(_CITIZEN)
        other_sos = _mock_sos(reported_by=_OTHER_CITIZEN.id)
        with patch("app.api.v1.sos.get_sos_by_id", return_value=other_sos):
            r = client.get(f"/api/v1/sos/{other_sos.id}")
        assert r.status_code == 403

    def test_citizen_cannot_view_other_recommendations(self) -> None:
        _override_user(_CITIZEN)
        other_sos = _mock_sos(reported_by=_OTHER_CITIZEN.id)
        with patch("app.api.v1.sos.get_sos_by_id", return_value=other_sos):
            r = client.get(f"/api/v1/sos/{other_sos.id}/recommendations")
        assert r.status_code == 403

    def test_official_can_view_any_sos(self) -> None:
        _override_user(_OFFICIAL)
        sos_m = _mock_sos(reported_by=_CITIZEN.id)
        with patch("app.api.v1.sos.get_sos_by_id", return_value=sos_m):
            r = client.get(f"/api/v1/sos/{sos_m.id}")
        assert r.status_code == 200

    def test_citizen_can_view_own_sos(self) -> None:
        _override_user(_CITIZEN)
        sos_m = _mock_sos(reported_by=_CITIZEN.id)
        with patch("app.api.v1.sos.get_sos_by_id", return_value=sos_m):
            r = client.get(f"/api/v1/sos/{sos_m.id}")
        assert r.status_code == 200


# ===========================================================================
# 3. SOS creation response shape
# ===========================================================================

class TestSOSCreationShape:
    def setup_method(self) -> None:
        _override_user(_CITIZEN)

    def teardown_method(self) -> None:
        _clear_overrides()

    def _post(self, risk_score: float = 40.0) -> Any:
        sos_m = _mock_sos(reported_by=_CITIZEN.id, risk_score=risk_score, risk_level="MODERATE")
        with patch("app.api.v1.sos.create_sos", return_value=sos_m), \
             patch("app.api.v1.sos.LiveRiskEngine", return_value=_mock_live_engine(risk_score)), \
             patch("app.api.v1.sos.attach_risk_context", return_value=sos_m), \
             patch("app.api.v1.sos.maybe_generate_sos_alert", return_value=None):
            return client.post(
                "/api/v1/sos",
                json={"latitude": 30.3, "longitude": 79.6, "severity": "HIGH"},
            )

    def test_status_201(self) -> None:
        assert self._post().status_code == 201

    def test_data_and_meta_present(self) -> None:
        r = self._post()
        assert "data" in r.json() and "meta" in r.json()

    def test_data_has_required_fields(self) -> None:
        data = self._post().json()["data"]
        for f in ["id", "latitude", "longitude", "severity", "status",
                  "risk_context", "created_at"]:
            assert f in data

    def test_status_is_active(self) -> None:
        assert self._post().json()["data"]["status"] == "ACTIVE"

    def test_meta_was_created(self) -> None:
        assert self._post().json()["meta"]["was_created"] is True

    def test_risk_context_present(self) -> None:
        ctx = self._post(risk_score=65.0).json()["data"]["risk_context"]
        assert "risk_score" in ctx and "live_risk_available" in ctx


# ===========================================================================
# 4. Lifecycle via service layer
# ===========================================================================

class TestSOSLifecycleService:
    def _db(self, sos: Any) -> MagicMock:
        db = MagicMock()
        db.get.return_value = sos
        return db

    def test_active_to_acknowledged(self) -> None:
        sos = _mock_sos(status="ACTIVE")
        with patch("app.services.sos.service._write_audit"):
            transition_sos_status(
                db=self._db(sos), sos_id=sos.id,
                target_status=SOSStatus.ACKNOWLEDGED,
                acting_user_id=_OFFICIAL.id,
            )
        assert sos.status == "ACKNOWLEDGED"

    def test_active_to_resolved(self) -> None:
        sos = _mock_sos(status="ACTIVE")
        with patch("app.services.sos.service._write_audit"):
            transition_sos_status(
                db=self._db(sos), sos_id=sos.id,
                target_status=SOSStatus.RESOLVED,
                acting_user_id=_OFFICIAL.id,
            )
        assert sos.status == "RESOLVED"

    def test_active_to_cancelled(self) -> None:
        sos = _mock_sos(status="ACTIVE")
        with patch("app.services.sos.service._write_audit"):
            transition_sos_status(
                db=self._db(sos), sos_id=sos.id,
                target_status=SOSStatus.CANCELLED,
                acting_user_id=_CITIZEN.id,
            )
        assert sos.status == "CANCELLED"

    def test_acknowledged_to_resolved(self) -> None:
        sos = _mock_sos(status="ACKNOWLEDGED")
        with patch("app.services.sos.service._write_audit"):
            transition_sos_status(
                db=self._db(sos), sos_id=sos.id,
                target_status=SOSStatus.RESOLVED,
                acting_user_id=_OFFICIAL.id,
            )
        assert sos.status == "RESOLVED"

    def test_resolved_to_acknowledged_raises_conflict(self) -> None:
        from app.core.errors import ConflictError
        with pytest.raises(ConflictError):
            transition_sos_status(
                db=self._db(_mock_sos(status="RESOLVED")),
                sos_id=uuid.uuid4(),
                target_status=SOSStatus.ACKNOWLEDGED,
                acting_user_id=_OFFICIAL.id,
            )

    def test_cancelled_to_resolved_raises_conflict(self) -> None:
        from app.core.errors import ConflictError
        with pytest.raises(ConflictError):
            transition_sos_status(
                db=self._db(_mock_sos(status="CANCELLED")),
                sos_id=uuid.uuid4(),
                target_status=SOSStatus.RESOLVED,
                acting_user_id=_OFFICIAL.id,
            )

    def test_not_found_raises_not_found(self) -> None:
        from app.core.errors import NotFoundError
        db = MagicMock()
        db.get.return_value = None
        with pytest.raises(NotFoundError):
            transition_sos_status(
                db=db, sos_id=uuid.uuid4(),
                target_status=SOSStatus.RESOLVED,
                acting_user_id=_OFFICIAL.id,
            )


# ===========================================================================
# 5. Lifecycle via API
# ===========================================================================

class TestSOSLifecycleAPI:
    def teardown_method(self) -> None:
        _clear_overrides()

    def test_official_can_acknowledge(self) -> None:
        _override_user(_OFFICIAL)
        sos_m = _mock_sos(status="ACTIVE")
        ack = _mock_sos(status="ACKNOWLEDGED")
        with patch("app.api.v1.sos.get_sos_by_id", return_value=sos_m), \
             patch("app.api.v1.sos.transition_sos_status", return_value=ack):
            r = client.post(f"/api/v1/sos/{sos_m.id}/acknowledge", json={})
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "ACKNOWLEDGED"

    def test_official_can_resolve(self) -> None:
        _override_user(_OFFICIAL)
        sos_m = _mock_sos(status="ACKNOWLEDGED")
        res = _mock_sos(status="RESOLVED")
        with patch("app.api.v1.sos.get_sos_by_id", return_value=sos_m), \
             patch("app.api.v1.sos.transition_sos_status", return_value=res):
            r = client.post(f"/api/v1/sos/{sos_m.id}/resolve", json={})
        assert r.status_code == 200

    def test_citizen_can_cancel_own(self) -> None:
        _override_user(_CITIZEN)
        sos_m = _mock_sos(reported_by=_CITIZEN.id, status="ACTIVE")
        cancelled = _mock_sos(reported_by=_CITIZEN.id, status="CANCELLED")
        with patch("app.api.v1.sos.get_sos_by_id", return_value=sos_m), \
             patch("app.api.v1.sos.transition_sos_status", return_value=cancelled):
            r = client.post(f"/api/v1/sos/{sos_m.id}/cancel", json={})
        assert r.status_code == 200

    def test_citizen_cannot_cancel_other(self) -> None:
        _override_user(_CITIZEN)
        other_sos = _mock_sos(reported_by=_OTHER_CITIZEN.id, status="ACTIVE")
        with patch("app.api.v1.sos.get_sos_by_id", return_value=other_sos):
            r = client.post(f"/api/v1/sos/{other_sos.id}/cancel", json={})
        assert r.status_code == 403

    def test_404_on_unknown_sos(self) -> None:
        _override_user(_OFFICIAL)
        with patch("app.api.v1.sos.get_sos_by_id", return_value=None):
            r = client.get(f"/api/v1/sos/{uuid.uuid4()}")
        assert r.status_code == 404


# ===========================================================================
# 6. Listing
# ===========================================================================

class TestSOSListing:
    def teardown_method(self) -> None:
        _clear_overrides()

    def test_citizen_list_returns_200(self) -> None:
        _override_user(_CITIZEN)
        with patch("app.api.v1.sos.list_sos", return_value=([], 0)):
            r = client.get("/api/v1/sos")
        assert r.status_code == 200

    def test_list_has_pagination_fields(self) -> None:
        _override_user(_CITIZEN)
        with patch("app.api.v1.sos.list_sos", return_value=([], 0)):
            r = client.get("/api/v1/sos?limit=10&offset=0")
        data = r.json()["data"]
        assert "total_count" in data and "items" in data

    def test_official_sees_all(self) -> None:
        _override_user(_OFFICIAL)
        mock_list = MagicMock(return_value=([], 0))
        with patch("app.api.v1.sos.list_sos", mock_list):
            client.get("/api/v1/sos")
        _, kwargs = mock_list.call_args
        assert kwargs.get("reported_by") is None

    def test_citizen_filtered_to_own(self) -> None:
        _override_user(_CITIZEN)
        mock_list = MagicMock(return_value=([], 0))
        with patch("app.api.v1.sos.list_sos", mock_list):
            client.get("/api/v1/sos")
        _, kwargs = mock_list.call_args
        assert kwargs.get("reported_by") == _CITIZEN.id


# ===========================================================================
# 7. Alert integration
# ===========================================================================

class TestSOSAlertIntegration:
    def test_alert_generated_when_risk_above_threshold(self) -> None:
        from app.services.sos.service import maybe_generate_sos_alert
        sos = _mock_sos(risk_score=75.0, risk_level="CRITICAL")
        db = MagicMock()
        mock_alert = MagicMock()
        mock_alert.id = uuid.uuid4()
        with patch("app.services.sos.service.generate_operational_alert",
                   return_value=(mock_alert, True)), \
             patch("app.services.sos.service._write_audit"):
            result = maybe_generate_sos_alert(db=db, sos=sos)
        assert result is not None

    def test_no_alert_below_threshold(self) -> None:
        from app.services.sos.service import maybe_generate_sos_alert
        sos = _mock_sos(risk_score=30.0, risk_level="LOW")
        result = maybe_generate_sos_alert(db=MagicMock(), sos=sos)
        assert result is None

    def test_no_alert_when_risk_none(self) -> None:
        from app.services.sos.service import maybe_generate_sos_alert
        result = maybe_generate_sos_alert(db=MagicMock(), sos=_mock_sos(risk_score=None))
        assert result is None


# ===========================================================================
# 8. Shelter nearby endpoint
# ===========================================================================

class TestShelterNearbyEndpoint:
    def setup_method(self) -> None:
        _override_user(_CITIZEN)

    def teardown_method(self) -> None:
        _clear_overrides()

    def test_returns_200_unavailable_when_no_dataset(self) -> None:
        with patch("app.api.v1.shelters.get_nearby_shelters",
                   return_value=("unavailable", "No dataset.", [])):
            r = client.get("/api/v1/shelters/nearby?lat=30.3&lon=79.6")
        assert r.status_code == 200
        assert r.json()["data"]["data_status"] == "unavailable"

    def test_no_fabricated_shelters(self) -> None:
        with patch("app.api.v1.shelters.get_nearby_shelters",
                   return_value=("unavailable", "No dataset.", [])):
            r = client.get("/api/v1/shelters/nearby?lat=30.3&lon=79.6")
        assert r.json()["data"]["shelters"] == []
        assert r.json()["data"]["total_found"] == 0

    def test_invalid_lat_rejected(self) -> None:
        r = client.get("/api/v1/shelters/nearby?lat=91&lon=79.6")
        assert r.status_code == 422

    def test_invalid_lon_rejected(self) -> None:
        r = client.get("/api/v1/shelters/nearby?lat=30.0&lon=181")
        assert r.status_code == 422

    def test_response_has_required_fields(self) -> None:
        with patch("app.api.v1.shelters.get_nearby_shelters",
                   return_value=("unavailable", "x", [])):
            r = client.get("/api/v1/shelters/nearby?lat=30.3&lon=79.6")
        data = r.json()["data"]
        for f in ["data_status", "data_source_note", "query_lat", "query_lon",
                  "radius_m", "total_found", "shelters", "limitations"]:
            assert f in data

    def test_limitations_list_present(self) -> None:
        with patch("app.api.v1.shelters.get_nearby_shelters",
                   return_value=("unavailable", "x", [])):
            r = client.get("/api/v1/shelters/nearby?lat=30.3&lon=79.6")
        lims = r.json()["data"]["limitations"]
        assert isinstance(lims, list) and len(lims) >= 1

    def test_meta_has_request_id(self) -> None:
        with patch("app.api.v1.shelters.get_nearby_shelters",
                   return_value=("unavailable", "x", [])):
            r = client.get("/api/v1/shelters/nearby?lat=30.3&lon=79.6")
        assert "request_id" in r.json()["meta"]


# ===========================================================================
# 9. Suitability formula
# ===========================================================================

class TestShelterSuitability:
    def test_distance_score_100_at_zero(self) -> None:
        assert _distance_score(0.0) == 100.0

    def test_distance_score_0_at_max(self) -> None:
        assert _distance_score(SUITABILITY_MAX_DISTANCE_M) == 0.0

    def test_distance_score_midpoint_near_50(self) -> None:
        s = _distance_score(SUITABILITY_MAX_DISTANCE_M / 2)
        assert 45.0 < s < 55.0

    def test_distance_score_beyond_max_is_zero(self) -> None:
        assert _distance_score(SUITABILITY_MAX_DISTANCE_M * 2) == 0.0

    def test_suitability_distance_only(self) -> None:
        score, factors = compute_suitability(1000.0, None, None)
        assert 0.0 <= score <= 100.0
        assert factors["capacity_available"] is False
        assert factors["accessibility_available"] is False

    def test_suitability_with_capacity(self) -> None:
        score, factors = compute_suitability(1000.0, 200, None)
        assert factors["capacity_available"] is True
        assert 0.0 <= score <= 100.0

    def test_suitability_all_weights_sum_to_1(self) -> None:
        _, factors = compute_suitability(1000.0, 100, True)
        total = sum(factors["weights_used"].values())
        assert abs(total - 1.0) < 1e-6

    def test_suitability_score_bounded(self) -> None:
        for dist in [0, 500, 5000, 25000, 60000]:
            score, _ = compute_suitability(dist, 50, True)
            assert 0.0 <= score <= 100.0

    def test_inaccessible_lower_than_accessible(self) -> None:
        score_ok, _ = compute_suitability(1000.0, 100, True)
        score_no, _ = compute_suitability(1000.0, 100, False)
        assert score_ok > score_no


# ===========================================================================
# 10. Recommendation endpoint
# ===========================================================================

class TestRecommendationEndpoint:
    def teardown_method(self) -> None:
        _clear_overrides()

    def test_404_on_unknown_sos(self) -> None:
        _override_user(_CITIZEN)
        with patch("app.api.v1.sos.get_sos_by_id", return_value=None):
            r = client.get(f"/api/v1/sos/{uuid.uuid4()}/recommendations")
        assert r.status_code == 404

    def test_returns_200_unavailable(self) -> None:
        from app.schemas.shelter import SOSRecommendationData
        _override_user(_CITIZEN)
        sos_m = _mock_sos(reported_by=_CITIZEN.id)
        rec = SOSRecommendationData(
            sos_id=str(sos_m.id), query_lat=30.3, query_lon=79.6,
            shelter_data_status="unavailable", shelter_data_note="No dataset.",
            limitations=["none"],
        )
        with patch("app.api.v1.sos.get_sos_by_id", return_value=sos_m), \
             patch("app.api.v1.sos.get_sos_recommendations", return_value=rec):
            r = client.get(f"/api/v1/sos/{sos_m.id}/recommendations")
        assert r.status_code == 200
        assert r.json()["data"]["shelter_data_status"] == "unavailable"
        assert r.json()["data"]["recommended_shelters"] == []

    def test_engine_version_sos_shelter_v1(self) -> None:
        from app.schemas.shelter import SOSRecommendationData
        _override_user(_CITIZEN)
        sos_m = _mock_sos(reported_by=_CITIZEN.id)
        rec = SOSRecommendationData(
            sos_id=str(sos_m.id), query_lat=30.3, query_lon=79.6,
            shelter_data_status="unavailable", shelter_data_note="x", limitations=[],
        )
        with patch("app.api.v1.sos.get_sos_by_id", return_value=sos_m), \
             patch("app.api.v1.sos.get_sos_recommendations", return_value=rec):
            r = client.get(f"/api/v1/sos/{sos_m.id}/recommendations")
        assert r.json()["data"]["engine_version"] == "SOS_SHELTER_V1"

    def test_citizen_cannot_view_other_rec(self) -> None:
        _override_user(_CITIZEN)
        other_sos = _mock_sos(reported_by=_OTHER_CITIZEN.id)
        with patch("app.api.v1.sos.get_sos_by_id", return_value=other_sos):
            r = client.get(f"/api/v1/sos/{other_sos.id}/recommendations")
        assert r.status_code == 403


# ===========================================================================
# 11. Constants
# ===========================================================================

class TestSOSConstants:
    def test_active_can_transition_to_acknowledged(self) -> None:
        from app.services.sos.constants import SOS_VALID_TRANSITIONS
        assert SOSStatus.ACKNOWLEDGED in SOS_VALID_TRANSITIONS[SOSStatus.ACTIVE]

    def test_resolved_has_no_transitions(self) -> None:
        from app.services.sos.constants import SOS_VALID_TRANSITIONS
        assert SOS_VALID_TRANSITIONS[SOSStatus.RESOLVED] == set()

    def test_cancelled_has_no_transitions(self) -> None:
        from app.services.sos.constants import SOS_VALID_TRANSITIONS
        assert SOS_VALID_TRANSITIONS[SOSStatus.CANCELLED] == set()

    def test_distance_weight_positive(self) -> None:
        assert SUITABILITY_W_DISTANCE > 0

    def test_alert_threshold_in_range(self) -> None:
        from app.services.sos.constants import SOS_ALERT_RISK_THRESHOLD
        assert 0 < SOS_ALERT_RISK_THRESHOLD <= 100
