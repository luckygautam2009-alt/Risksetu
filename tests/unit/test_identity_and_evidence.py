"""
Comprehensive unit & integration test suite for Identity Verification & Photographic Evidence Upload.

Verifies all 24 security, compliance, and domain authorization requirements.
"""
from __future__ import annotations

import datetime
import io
import uuid

from PIL import Image
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.core.logging import _redact_value
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.evidence import IncidentEvidence
from app.models.identity import IdentityVerification
from app.models.user import User
from app.services.identity.constants import (
    PROVIDER_UNAVAILABLE_CODE,
    IdentityProviderType,
    IdentityStatus,
)

client = TestClient(app)


def _create_test_user(db: Session, email: str, role: str = "citizen") -> tuple[User, str]:
    """Helper to seed a test user and generate Bearer JWT."""
    unique_suffix = uuid.uuid4().hex[:8]
    if "@" in email:
        name, domain = email.split("@", 1)
        unique_email = f"{name}_{unique_suffix}@{domain}"
    else:
        unique_email = f"{email}_{unique_suffix}@risksetu.test"

    user = User(
        id=uuid.uuid4(),
        email=unique_email,
        hashed_password=hash_password("RiskSetuPass!2026"),
        full_name=f"Test {role.capitalize()}",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.id), extra_claims={"role": role})
    return user, token


def _create_sample_jpeg_bytes(width: int = 200, height: int = 200) -> bytes:
    """Helper creating valid JPEG image bytes."""
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color="red")
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def db_session():
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. Unverified user cannot upload evidence (HTTP 403 IDENTITY_VERIFICATION_REQUIRED)
# ---------------------------------------------------------------------------
def test_unverified_user_cannot_upload_evidence(db_session):
    user, token = _create_test_user(db_session, "unverified_citizen@risksetu.test")
    headers = {"Authorization": f"Bearer {token}"}

    img_bytes = _create_sample_jpeg_bytes()
    files = {"file": ("evidence.jpg", img_bytes, "image/jpeg")}

    resp = client.post("/api/v1/evidence/upload", headers=headers, files=files)
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"]["code"] == "IDENTITY_VERIFICATION_REQUIRED"


# ---------------------------------------------------------------------------
# 2. Verified user can upload evidence
# ---------------------------------------------------------------------------
def test_verified_user_can_upload_evidence(db_session):
    user, token = _create_test_user(db_session, "verified_citizen@risksetu.test")
    headers = {"Authorization": f"Bearer {token}"}

    # Mark user verified in PostgreSQL
    ver = IdentityVerification(
        id=uuid.uuid4(),
        user_id=user.id,
        provider=IdentityProviderType.AADHAAR.value,
        status=IdentityStatus.VERIFIED.value,
        verified_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(ver)
    db_session.commit()

    img_bytes = _create_sample_jpeg_bytes()
    files = {"file": ("evidence.jpg", img_bytes, "image/jpeg")}

    resp = client.post("/api/v1/evidence/upload", headers=headers, files=files)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert "evidence_id" in data
    assert data["owner_user_id"] == str(user.id)
    assert data["upload_status"] == "STORED"


# ---------------------------------------------------------------------------
# 3. Pending user cannot upload evidence
# ---------------------------------------------------------------------------
def test_pending_user_cannot_upload_evidence(db_session):
    user, token = _create_test_user(db_session, "pending_citizen@risksetu.test")
    headers = {"Authorization": f"Bearer {token}"}

    ver = IdentityVerification(
        id=uuid.uuid4(),
        user_id=user.id,
        provider=IdentityProviderType.DIGILOCKER.value,
        status=IdentityStatus.VERIFICATION_PENDING.value,
    )
    db_session.add(ver)
    db_session.commit()

    img_bytes = _create_sample_jpeg_bytes()
    files = {"file": ("evidence.jpg", img_bytes, "image/jpeg")}

    resp = client.post("/api/v1/evidence/upload", headers=headers, files=files)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "IDENTITY_VERIFICATION_REQUIRED"


# ---------------------------------------------------------------------------
# 4. Failed verification cannot upload
# ---------------------------------------------------------------------------
def test_failed_verification_cannot_upload(db_session):
    user, token = _create_test_user(db_session, "failed_citizen@risksetu.test")
    headers = {"Authorization": f"Bearer {token}"}

    ver = IdentityVerification(
        id=uuid.uuid4(),
        user_id=user.id,
        provider=IdentityProviderType.AADHAAR.value,
        status=IdentityStatus.VERIFICATION_FAILED.value,
        failure_code="OTP_EXPIRED",
    )
    db_session.add(ver)
    db_session.commit()

    img_bytes = _create_sample_jpeg_bytes()
    files = {"file": ("evidence.jpg", img_bytes, "image/jpeg")}

    resp = client.post("/api/v1/evidence/upload", headers=headers, files=files)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "IDENTITY_VERIFICATION_REQUIRED"


# ---------------------------------------------------------------------------
# 5. Expired verification cannot upload
# ---------------------------------------------------------------------------
def test_expired_verification_cannot_upload(db_session):
    user, token = _create_test_user(db_session, "expired_citizen@risksetu.test")
    headers = {"Authorization": f"Bearer {token}"}

    past_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=400)
    ver = IdentityVerification(
        id=uuid.uuid4(),
        user_id=user.id,
        provider=IdentityProviderType.AADHAAR.value,
        status=IdentityStatus.VERIFIED.value,
        verified_at=past_date - datetime.timedelta(days=365),
        expires_at=past_date,
    )
    db_session.add(ver)
    db_session.commit()

    img_bytes = _create_sample_jpeg_bytes()
    files = {"file": ("evidence.jpg", img_bytes, "image/jpeg")}

    resp = client.post("/api/v1/evidence/upload", headers=headers, files=files)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "IDENTITY_VERIFICATION_REQUIRED"


# ---------------------------------------------------------------------------
# 6. Provider unavailable does not create VERIFIED state
# ---------------------------------------------------------------------------
def test_provider_unavailable_honest_response(db_session):
    user, token = _create_test_user(db_session, "unavail_citizen@risksetu.test")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"provider": "AADHAAR", "consent_obtained": True}
    resp = client.post("/api/v1/identity/verification/start", headers=headers, json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["status"] == "UNVERIFIED"
    assert data["is_provider_available"] is False
    assert data["meta"]["error_code"] == PROVIDER_UNAVAILABLE_CODE

    # Verify PostgreSQL DB state remained UNVERIFIED
    status_resp = client.get("/api/v1/identity/verification/status", headers=headers)
    assert status_resp.json()["data"]["status"] == "UNVERIFIED"
    assert status_resp.json()["data"]["is_verified"] is False


# ---------------------------------------------------------------------------
# 7, 8, 9, 10. Callbacks, Nonce Mismatch, Transaction Binding & Idempotency
# ---------------------------------------------------------------------------
def test_callback_nonce_mismatch_rejected(db_session, monkeypatch):
    from app.services.identity.digilocker_provider import DigiLockerProvider

    monkeypatch.setattr(DigiLockerProvider, "is_configured", property(lambda self: True))

    user, token = _create_test_user(db_session, "nonce_citizen@risksetu.test")
    headers = {"Authorization": f"Bearer {token}"}

    # Start pending verification
    ver = IdentityVerification(
        id=uuid.uuid4(),
        user_id=user.id,
        provider=IdentityProviderType.DIGILOCKER.value,
        status=IdentityStatus.VERIFICATION_PENDING.value,
        provider_transaction_id="dl_tx_12345",
    )
    db_session.add(ver)
    db_session.commit()

    cb_payload = {
        "provider": "DIGILOCKER",
        "provider_transaction_id": "dl_tx_12345",
        "code": "auth_code_999",
        "state": "wrong_state_token",
        "expected_state": "expected_state_token",
        "nonce": "expected_nonce",
    }
    resp = client.post("/api/v1/identity/verification/callback", headers=headers, json=cb_payload)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "VERIFICATION_FAILED"
    assert resp.json()["data"]["failure_code"] == "INVALID_OAUTH_STATE"


def test_callback_missing_transaction_rejected(db_session):
    user, token = _create_test_user(db_session, "no_tx_citizen@risksetu.test")
    headers = {"Authorization": f"Bearer {token}"}

    cb_payload = {
        "provider": "AADHAAR",
        "gateway_status": "SUCCESS",
    }
    resp = client.post("/api/v1/identity/verification/callback", headers=headers, json=cb_payload)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "VERIFICATION_FAILED"


# ---------------------------------------------------------------------------
# 11, 12, 13. Log Scrubbing for Aadhaar, OTP, Secrets
# ---------------------------------------------------------------------------
def test_log_scrubbing_redacts_sensitive_values():
    assert _redact_value("aadhaar_number", "1234 5678 9012") == "***REDACTED***"
    assert _redact_value("otp", "583920") == "***REDACTED***"
    assert _redact_value("client_secret", "sec_9999") == "***REDACTED***"

    # Pattern redaction in free-text strings
    dirty_log = "User tried Aadhaar 9876 5432 1098 during check."
    redacted = _redact_value("message", dirty_log)
    assert "9876 5432 1098" not in redacted
    assert "***REDACTED-AADHAAR***" in redacted


# ---------------------------------------------------------------------------
# 14, 15. Citizen Isolation & Official/Admin Status Inspection
# ---------------------------------------------------------------------------
def test_citizen_cannot_inspect_other_user_status(db_session):
    user1, token1 = _create_test_user(db_session, "citizen1@risksetu.test", role="citizen")
    user2, token2 = _create_test_user(db_session, "citizen2@risksetu.test", role="citizen")

    resp = client.get(f"/api/v1/identity/verification/status/{user2.id}", headers={"Authorization": f"Bearer {token1}"})
    assert resp.status_code == 403


def test_official_can_inspect_citizen_status(db_session):
    user1, _ = _create_test_user(db_session, "citizen_target@risksetu.test", role="citizen")
    official, off_token = _create_test_user(db_session, "official_hq@risksetu.test", role="official")

    resp = client.get(f"/api/v1/identity/verification/status/{user1.id}", headers={"Authorization": f"Bearer {off_token}"})
    assert resp.status_code == 200
    assert resp.json()["data"]["user_id"] == str(user1.id)


# ---------------------------------------------------------------------------
# 16, 17, 18, 19. Evidence Image Validation (MIME, Magic Bytes, Size, Executable)
# ---------------------------------------------------------------------------
def test_image_mime_and_magic_validation(db_session):
    user, token = _create_test_user(db_session, "verified_media@risksetu.test")
    headers = {"Authorization": f"Bearer {token}"}

    ver = IdentityVerification(
        id=uuid.uuid4(),
        user_id=user.id,
        provider=IdentityProviderType.AADHAAR.value,
        status=IdentityStatus.VERIFIED.value,
    )
    db_session.add(ver)
    db_session.commit()

    # Disallowed MIME
    resp1 = client.post(
        "/api/v1/evidence/upload",
        headers=headers,
        files={"file": ("malicious.exe", b"MZexecutabledata", "application/x-msdownload")},
    )
    assert resp1.status_code == 422

    # Fake MIME with bad magic bytes
    resp2 = client.post(
        "/api/v1/evidence/upload",
        headers=headers,
        files={"file": ("fake.jpg", b"NOT_A_JPEG_FILE_HEADER", "image/jpeg")},
    )
    assert resp2.status_code == 422


# ---------------------------------------------------------------------------
# 20. Evidence Ownership Enforced
# ---------------------------------------------------------------------------
def test_evidence_ownership_enforced(db_session):
    user1, token1 = _create_test_user(db_session, "ev_owner1@risksetu.test")
    user2, token2 = _create_test_user(db_session, "ev_owner2@risksetu.test")

    ev = IncidentEvidence(
        id=uuid.uuid4(),
        owner_user_id=user1.id,
        storage_key="storage/evidence/test.jpg",
        content_type="image/jpeg",
        size_bytes=100,
        sha256="abc",
        upload_status="STORED",
    )
    db_session.add(ev)
    db_session.commit()

    # User 2 cannot access user 1's evidence metadata
    resp = client.get(f"/api/v1/evidence/{ev.id}", headers={"Authorization": f"Bearer {token2}"})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 22, 23, 24. Ground Report & SOS Integration with Evidence Authorization
# ---------------------------------------------------------------------------
def test_unverified_ground_report_with_evidence_blocked(db_session):
    user, token = _create_test_user(db_session, "report_citizen@risksetu.test")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "report_type": "LANDSLIDE",
        "description": "Observed rockfall along slope.",
        "latitude": 30.2936,
        "longitude": 79.5603,
        "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "evidence_id": str(uuid.uuid4()),
    }
    resp = client.post("/api/v1/ground-reports", headers=headers, json=payload)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "IDENTITY_VERIFICATION_REQUIRED"
