"""
Phase 2 Comprehensive Test Suite — Emergency Alert Network & SOS Evidence Pipeline.

Verifies:
1. Identity-gated SOS evidence submission (zero unverified evidence SOS).
2. Idempotent SOS deduplication and replay semantics.
3. SOS cancellation lifecycle and immutable audit trail.
4. Real-time WebSocket connection manager and payload sanitization.
5. User alert subscriptions (PostgreSQL authoritative state).
6. Emergency notification provider honest availability handling.
"""
from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock, PropertyMock, patch

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.evidence import IncidentEvidence
from app.models.identity import IdentityVerification
from app.models.user import User
from app.services.alerts.notification_provider import (
    NotificationChannel,
    NotificationDeliveryStatus,
    SMSNotificationProvider,
)
from app.services.alerts.realtime import (
    ConnectionManager,
    build_sos_alert_event_payload,
)
from app.services.identity.constants import IdentityProviderType, IdentityStatus
from app.services.sos.constants import SOSAuditAction, SOSStatus

client = TestClient(app)


def _create_user(db: Session, email_prefix: str, role: str = "citizen") -> tuple[User, str]:
    """Creates an active test user with JWT."""
    u_id = uuid.uuid4()
    user = User(
        id=u_id,
        email=f"{email_prefix}_{u_id.hex[:6]}@risksetu.test",
        hashed_password=hash_password("Pass123!Safe"),
        full_name=f"User {email_prefix}",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(subject=str(user.id), extra_claims={"role": role})
    return user, token


def _set_user_verified(db: Session, user: User) -> IdentityVerification:
    """Sets a user's identity status to VERIFIED in PostgreSQL."""
    rec = IdentityVerification(
        id=uuid.uuid4(),
        user_id=user.id,
        provider=IdentityProviderType.AADHAAR.value,
        status=IdentityStatus.VERIFIED.value,
        provider_reference_hash=f"hash_{uuid.uuid4().hex}",
        verified_at=datetime.datetime.now(datetime.timezone.utc),
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def _create_test_evidence(db: Session, user: User) -> IncidentEvidence:
    """Creates an approved evidence record in PostgreSQL."""
    ev = IncidentEvidence(
        id=uuid.uuid4(),
        owner_user_id=user.id,
        storage_key="evidence/emergency_scene.jpg",
        content_type="image/jpeg",
        size_bytes=10240,
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        upload_status="READY",
        latitude=30.3,
        longitude=79.6,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


# ---------------------------------------------------------------------------
# 1. Identity Gated Evidence SOS Tests
# ---------------------------------------------------------------------------

class TestIdentityGatedSOS:
    def test_unverified_citizen_cannot_submit_evidence_backed_sos(self) -> None:
        db = next(get_db())
        user, token = _create_user(db, "unverified_citizen")
        evidence = _create_test_evidence(db, user)

        res = client.post(
            "/api/v1/sos",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "latitude": 30.2936,
                "longitude": 79.5603,
                "severity": "HIGH",
                "description": "Flash flood approaching bridge",
                "evidence_id": str(evidence.id),
            },
        )
        assert res.status_code == 403
        data = res.json()
        assert "IDENTITY_VERIFICATION_REQUIRED" in str(data)

    def test_verified_citizen_can_submit_evidence_backed_sos(self) -> None:
        db = next(get_db())
        user, token = _create_user(db, "verified_citizen")
        _set_user_verified(db, user)
        evidence = _create_test_evidence(db, user)

        res = client.post(
            "/api/v1/sos",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "latitude": 30.2936,
                "longitude": 79.5603,
                "severity": "CRITICAL",
                "description": "Flash flood verified with photo",
                "evidence_id": str(evidence.id),
            },
        )
        assert res.status_code == 201
        body = res.json()
        assert body["data"]["status"] == "ACTIVE"
        assert body["data"]["evidence_count"] >= 1
        assert body["data"]["created_by_verified_identity"] is True
        assert len(body["data"]["evidence_items"]) >= 1
        assert body["data"]["evidence_items"][0]["evidence_id"] == str(evidence.id)


# ---------------------------------------------------------------------------
# 2. Idempotency Tests
# ---------------------------------------------------------------------------

class TestSOSIdempotency:
    def test_idempotent_replay_returns_existing_record(self) -> None:
        db = next(get_db())
        user, token = _create_user(db, "idempotent_citizen")
        _set_user_verified(db, user)
        idemp_key = f"idemp-test-{uuid.uuid4().hex}"

        payload = {
            "latitude": 30.3000,
            "longitude": 79.5500,
            "severity": "HIGH",
            "description": "Landslide blocking main route",
            "idempotency_key": idemp_key,
        }

        # 1st Submission
        res1 = client.post(
            "/api/v1/sos",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idemp_key},
            json=payload,
        )
        assert res1.status_code == 201
        data1 = res1.json()
        assert data1["meta"]["was_created"] is True

        # 2nd Replay Submission
        res2 = client.post(
            "/api/v1/sos",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idemp_key},
            json=payload,
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["meta"]["was_created"] is False
        assert data2["meta"]["idempotent_replay"] is True
        assert data2["data"]["id"] == data1["data"]["id"]


# ---------------------------------------------------------------------------
# 3. SOS Cancellation Lifecycle & Audits
# ---------------------------------------------------------------------------

class TestSOSCancellationAndAudits:
    def test_citizen_can_cancel_own_sos_and_view_audits(self) -> None:
        db = next(get_db())
        user, token = _create_user(db, "canceller_citizen")
        _set_user_verified(db, user)

        # Create SOS
        res = client.post(
            "/api/v1/sos",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "latitude": 30.2936,
                "longitude": 79.5603,
                "severity": "MEDIUM",
                "description": "Temporary tree blockage cleared",
            },
        )
        assert res.status_code == 201
        sos_id = res.json()["data"]["id"]

        # Cancel SOS
        cancel_res = client.post(
            f"/api/v1/sos/{sos_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "Situation is resolved safely by locals."},
        )
        assert cancel_res.status_code == 200
        cancel_data = cancel_res.json()["data"]
        assert cancel_data["status"] == SOSStatus.CANCELLED.value
        assert cancel_data["cancelled_at"] is not None

        # Inspect Audits
        audit_res = client.get(
            f"/api/v1/sos/{sos_id}/audits",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert audit_res.status_code == 200
        audits = audit_res.json()["data"]
        actions = [a["action"] for a in audits]
        assert SOSAuditAction.CREATED.value in actions
        assert SOSAuditAction.CANCELLED.value in actions


# ---------------------------------------------------------------------------
# 4. Real-Time Connection Manager & Sanitization
# ---------------------------------------------------------------------------

class TestRealtimeDelivery:
    @pytest.mark.asyncio
    async def test_connection_manager_broadcast_and_role_filtering(self) -> None:
        mgr = ConnectionManager()

        mock_ws_officer = AsyncMock()
        mock_ws_citizen = AsyncMock()

        user_officer_id = uuid.uuid4()
        user_citizen_id = uuid.uuid4()

        await mgr.connect(mock_ws_officer, user_officer_id, role="official")
        await mgr.connect(mock_ws_citizen, user_citizen_id, role="citizen")

        assert len(mgr.active_connections) == 2

        # Broadcast to all
        delivered = await mgr.publish_event("TEST_EVENT", {"msg": "hello"})
        assert delivered == 2

        # Role targeted broadcast (officer only)
        delivered_officers = await mgr.publish_event(
            "OFFICER_ALERT",
            {"urgent": True},
            target_roles=["official", "admin"],
        )
        assert delivered_officers == 1
        mock_ws_officer.send_json.assert_called()

        # Disconnect
        mgr.disconnect(mock_ws_officer)
        assert len(mgr.active_connections) == 1

    def test_build_sos_alert_event_payload_sanitized(self) -> None:
        payload = build_sos_alert_event_payload(
            alert_id=uuid.uuid4(),
            sos_id=uuid.uuid4(),
            severity="CRITICAL",
            latitude=30.2936,
            longitude=79.5603,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            description="Road cave-in",
            evidence_count=2,
            risk_score=78.5,
            risk_level="CRITICAL",
        )
        # Verify no PII fields
        assert "token" not in payload
        assert "password" not in payload
        assert "user_id" not in payload
        assert "aadhaar" not in payload
        assert payload["severity"] == "CRITICAL"
        assert payload["source"] == "VERIFIED_CITIZEN"
        assert payload["evidence_count"] == 2
        assert payload["risk_context"]["risk_score"] == 78.5


# ---------------------------------------------------------------------------
# 5. Alert Subscriptions API
# ---------------------------------------------------------------------------

class TestAlertSubscriptions:
    def test_get_and_update_subscriptions(self) -> None:
        db = next(get_db())
        user, token = _create_user(db, "subscriber_user")

        # GET /subscriptions/me (initial empty/default)
        r_get = client.get(
            "/api/v1/subscriptions/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r_get.status_code == 200
        assert isinstance(r_get.json()["data"], list)

        # POST /subscriptions
        r_post = client.post(
            "/api/v1/subscriptions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "subscriptions": [
                    {"notification_type": "EMERGENCY_ALERTS", "enabled": True, "geofence_radius_km": 25.0},
                    {"notification_type": "ROAD_DISRUPTION", "enabled": False},
                ]
            },
        )
        assert r_post.status_code == 200
        data = r_post.json()["data"]
        assert len(data) == 2
        types = {d["notification_type"]: d for d in data}
        assert types["EMERGENCY_ALERTS"]["enabled"] is True
        assert types["EMERGENCY_ALERTS"]["geofence_radius_km"] == 25.0
        assert types["ROAD_DISRUPTION"]["enabled"] is False

    def test_invalid_notification_type_rejected(self) -> None:
        db = next(get_db())
        user, token = _create_user(db, "invalid_sub_user")

        r_post = client.post(
            "/api/v1/subscriptions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "subscriptions": [
                    {"notification_type": "UNKNOWN_SUPER_ALERT", "enabled": True},
                ]
            },
        )
        assert r_post.status_code == 422


# ---------------------------------------------------------------------------
# 6. Notification Provider Honest State Handling
# ---------------------------------------------------------------------------

class TestEmergencyNotificationProvider:
    @pytest.mark.asyncio
    async def test_sms_provider_reports_not_configured_honestly(self) -> None:
        provider = SMSNotificationProvider()
        # When unconfigured, it must report NOT_CONFIGURED without throwing or claiming success
        with patch.object(SMSNotificationProvider, "is_configured", new_callable=PropertyMock, return_value=False):
            result = await provider.dispatch(
                alert_id=uuid.uuid4(),
                recipients=["+919876543210"],
                title="EMERGENCY ALERT",
                message="Flash flood warning in Joshimath area.",
                severity="CRITICAL",
            )
            assert result.channel == NotificationChannel.SMS
            assert result.status == NotificationDeliveryStatus.NOT_CONFIGURED
            assert result.recipient_count == 0
            assert "NOT_CONFIGURED" in result.message
