"""
Aadhaar Identity Verification Provider Adapter.

CRITICAL LEGAL & ARCHITECTURAL BOUNDARIES:
- Never invents direct unauthorized access to UIDAI production databases.
- Integrates via an authorized AUA/KUA / e-KYC gateway contract.
- If credentials or configuration are absent, returns VERIFICATION_PROVIDER_UNAVAILABLE.
- Never logs, captures, or persists raw 12-digit Aadhaar numbers, OTPs, or biometrics.
"""
from __future__ import annotations

import datetime
import hashlib
from typing import Any
import uuid

import structlog

from app.core.config import get_settings
from app.services.identity.constants import (
    PROVIDER_UNAVAILABLE_CODE,
    PROVIDER_UNAVAILABLE_MESSAGE,
    IdentityProviderType,
    IdentityStatus,
)
from app.services.identity.provider import (
    IdentityVerificationProvider,
    InitiationResult,
    VerificationResult,
)

logger = structlog.get_logger("risksetu.identity.aadhaar")


class AadhaarProvider(IdentityVerificationProvider):
    """Aadhaar provider adapter adhering to e-KYC/authentication boundaries."""

    @property
    def provider_type(self) -> IdentityProviderType:
        return IdentityProviderType.AADHAAR

    @property
    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(
            settings.aadhaar_provider_enabled
            and settings.aadhaar_client_id
            and settings.aadhaar_client_secret
            and settings.aadhaar_provider_url
        )

    async def initiate_verification(
        self,
        user_id: uuid.UUID,
        consent: bool,
        redirect_uri: str | None = None,
    ) -> InitiationResult:
        """Initiate an Aadhaar e-KYC / OTP verification session."""
        if not consent:
            return InitiationResult(
                success=False,
                provider=self.provider_type,
                error_code="CONSENT_REQUIRED",
                error_message="Explicit citizen consent is mandatory prior to Aadhaar verification.",
            )

        if not self.is_configured:
            logger.info("aadhaar_provider_unavailable_in_deployment")
            return InitiationResult(
                success=False,
                provider=self.provider_type,
                error_code=PROVIDER_UNAVAILABLE_CODE,
                error_message=PROVIDER_UNAVAILABLE_MESSAGE,
                is_provider_available=False,
            )

        settings = get_settings()
        # In a configured environment, generate transaction binding token
        tx_id = f"aadh_tx_{uuid.uuid4().hex}"
        state_nonce = f"state_{uuid.uuid4().hex[:16]}"

        redirect = f"{settings.aadhaar_provider_url}/auth?client_id={settings.aadhaar_client_id}&tx={tx_id}&state={state_nonce}"
        return InitiationResult(
            success=True,
            provider=self.provider_type,
            provider_transaction_id=tx_id,
            redirect_url=redirect,
            state_token=state_nonce,
            nonce=state_nonce,
            is_provider_available=True,
        )

    async def handle_callback(
        self,
        payload: dict[str, Any],
        state_token: str | None = None,
        expected_nonce: str | None = None,
    ) -> VerificationResult:
        """Handle callback/webhook from Aadhaar authorized provider gateway."""
        if not self.is_configured:
            return VerificationResult(
                success=False,
                provider=self.provider_type,
                status=IdentityStatus.VERIFICATION_FAILED,
                failure_code=PROVIDER_UNAVAILABLE_CODE,
                failure_message_safe=PROVIDER_UNAVAILABLE_MESSAGE,
                is_provider_available=False,
            )

        # Validate transaction binding & nonce
        tx_id = payload.get("provider_transaction_id") or payload.get("tx_id")
        provided_nonce = payload.get("nonce") or payload.get("state")

        if not tx_id:
            return VerificationResult(
                success=False,
                provider=self.provider_type,
                status=IdentityStatus.VERIFICATION_FAILED,
                failure_code="MISSING_TRANSACTION_ID",
                failure_message_safe="Callback missing required provider transaction reference.",
            )

        if expected_nonce and provided_nonce != expected_nonce:
            logger.warning("aadhaar_callback_nonce_mismatch", tx_id=tx_id)
            return VerificationResult(
                success=False,
                provider=self.provider_type,
                status=IdentityStatus.VERIFICATION_FAILED,
                failure_code="INVALID_NONCE_STATE",
                failure_message_safe="Verification state/nonce mismatch or expired replay attempt.",
            )

        # Validate provider response code
        gateway_status = payload.get("gateway_status", "").upper()
        if gateway_status == "SUCCESS":
            now = datetime.datetime.now(datetime.timezone.utc)
            # Safe reference hash: SHA256 of the provider reference code, NEVER raw Aadhaar
            provider_ref = str(payload.get("reference_id", tx_id))
            ref_hash = hashlib.sha256(provider_ref.encode()).hexdigest()

            # Name reference hash or minimal initials
            name_ref = payload.get("name_reference", "VERIFIED_INDIVIDUAL")
            name_hash = hashlib.sha256(name_ref.encode()).hexdigest()[:16]

            return VerificationResult(
                success=True,
                provider=self.provider_type,
                status=IdentityStatus.VERIFIED,
                provider_transaction_id=str(tx_id),
                provider_reference_hash=ref_hash,
                identity_name_hash_or_minimal_reference=f"REF-{name_hash}",
                verified_at=now,
                expires_at=now + datetime.timedelta(days=365),  # 1-year revalidation cycle
            )

        failure_code = payload.get("failure_code", "VERIFICATION_REJECTED")
        return VerificationResult(
            success=False,
            provider=self.provider_type,
            status=IdentityStatus.VERIFICATION_FAILED,
            provider_transaction_id=str(tx_id),
            failure_code=str(failure_code),
            failure_message_safe="Aadhaar authentication rejected or timed out at gateway.",
        )

    async def get_status(
        self,
        provider_transaction_id: str,
    ) -> VerificationResult:
        """Query verification status from gateway."""
        if not self.is_configured:
            return VerificationResult(
                success=False,
                provider=self.provider_type,
                status=IdentityStatus.UNVERIFIED,
                failure_code=PROVIDER_UNAVAILABLE_CODE,
                failure_message_safe=PROVIDER_UNAVAILABLE_MESSAGE,
                is_provider_available=False,
            )

        # If configured, inspect transaction
        return VerificationResult(
            success=False,
            provider=self.provider_type,
            status=IdentityStatus.VERIFICATION_PENDING,
            provider_transaction_id=provider_transaction_id,
        )
