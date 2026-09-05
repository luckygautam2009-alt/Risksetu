"""
Core Identity Service orchestrating PostgreSQL persistence, provider delegation,
and immutable verification audit trails.
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session
import structlog

from app.models.identity import (
    IdentityVerification,
    IdentityVerificationAudit,
)
from app.models.user import User
from app.services.identity.aadhaar_provider import AadhaarProvider
from app.services.identity.constants import (
    IdentityAuditEventType,
    IdentityProviderType,
    IdentityStatus,
    PROVIDER_UNAVAILABLE_MESSAGE,
)
from app.services.identity.digilocker_provider import DigiLockerProvider
from app.services.identity.provider import IdentityVerificationProvider
from app.services.identity.schemas import (
    IdentityStatusData,
    IdentityStatusResponse,
    IdentityVerificationCallbackRequest,
    IdentityVerificationStartResponse,
)

logger = structlog.get_logger("risksetu.identity.service")


class IdentityService:
    """Authoritative service for managing citizen identity verifications."""

    def __init__(self) -> None:
        self._providers: dict[IdentityProviderType, IdentityVerificationProvider] = {
            IdentityProviderType.AADHAAR: AadhaarProvider(),
            IdentityProviderType.DIGILOCKER: DigiLockerProvider(),
        }

    def get_provider(self, provider_type: IdentityProviderType) -> IdentityVerificationProvider:
        provider = self._providers.get(provider_type)
        if not provider:
            raise ValueError(f"Unsupported identity provider: {provider_type}")
        return provider

    def get_user_verification(
        self,
        db: Session,
        user_id: uuid.UUID,
    ) -> IdentityVerification | None:
        """Fetch the primary or most active verification record for a user."""
        stmt = (
            select(IdentityVerification)
            .where(IdentityVerification.user_id == user_id)
            .order_by(
                # Prioritize VERIFIED over PENDING over UNVERIFIED
                IdentityVerification.status == IdentityStatus.VERIFIED.value,
                IdentityVerification.updated_at.desc(),
            )
        )
        return db.execute(stmt).scalars().first()

    def is_user_verified(self, db: Session, user_id: uuid.UUID) -> bool:
        """Authoritatively query whether a user is currently verified and not expired."""
        ver = self.get_user_verification(db, user_id)
        if not ver:
            return False

        if ver.status != IdentityStatus.VERIFIED.value:
            return False

        now = datetime.datetime.now(datetime.timezone.utc)
        if ver.expires_at and ver.expires_at < now:
            logger.info("user_verification_expired", user_id=str(user_id))
            return False

        return True

    def get_user_verification_status(
        self,
        db: Session,
        user_id: uuid.UUID,
        request_id: str = "",
    ) -> IdentityStatusResponse:
        """Return the formatted identity verification status envelope."""
        ver = self.get_user_verification(db, user_id)
        now = datetime.datetime.now(datetime.timezone.utc)

        if not ver:
            data = IdentityStatusData(
                user_id=str(user_id),
                status=IdentityStatus.UNVERIFIED,
                is_verified=False,
            )
            return IdentityStatusResponse(data=data, meta={"request_id": request_id})

        # Check for expiry
        is_verified = (ver.status == IdentityStatus.VERIFIED.value)
        status_enum = IdentityStatus(ver.status)
        if is_verified and ver.expires_at and ver.expires_at < now:
            is_verified = False
            status_enum = IdentityStatus.VERIFICATION_EXPIRED

        data = IdentityStatusData(
            user_id=str(user_id),
            status=status_enum,
            is_verified=is_verified,
            provider=IdentityProviderType(ver.provider) if ver.provider else None,
            verified_at=ver.verified_at,
            expires_at=ver.expires_at,
            minimal_reference=ver.identity_name_hash_or_minimal_reference,
            failure_code=ver.failure_code,
            failure_message=ver.failure_message_safe,
        )
        return IdentityStatusResponse(data=data, meta={"request_id": request_id})

    async def start_verification(
        self,
        db: Session,
        user: User,
        provider_type: IdentityProviderType,
        consent: bool,
        redirect_uri: str | None = None,
        request_id: str = "",
    ) -> IdentityVerificationStartResponse:
        """Initiate verification with the selected provider and persist pending state."""
        provider = self.get_provider(provider_type)
        now = datetime.datetime.now(datetime.timezone.utc)

        # 1. Fetch or create verification record in PostgreSQL
        stmt = select(IdentityVerification).where(
            IdentityVerification.user_id == user.id,
            IdentityVerification.provider == provider_type.value,
        )
        ver = db.execute(stmt).scalar_one_or_none()
        if not ver:
            ver = IdentityVerification(
                id=uuid.uuid4(),
                user_id=user.id,
                provider=provider_type.value,
                status=IdentityStatus.UNVERIFIED.value,
                consent_obtained=consent,
                consent_timestamp=now if consent else None,
            )
            db.add(ver)

        # 2. Delegate to provider
        init_res = await provider.initiate_verification(
            user_id=user.id,
            consent=consent,
            redirect_uri=redirect_uri,
        )

        if not init_res.success:
            ver.failure_code = init_res.error_code or "INITIATION_FAILED"
            ver.failure_message_safe = init_res.error_message or "Failed to initiate provider verification."
            ver.status = IdentityStatus.UNVERIFIED.value
            db.commit()

            return IdentityVerificationStartResponse(
                success=False,
                provider=provider_type,
                status=IdentityStatus.UNVERIFIED,
                message=init_res.error_message or PROVIDER_UNAVAILABLE_MESSAGE,
                is_provider_available=init_res.is_provider_available,
                meta={"request_id": request_id, "error_code": init_res.error_code},
            )

        # 3. Mark verification as pending with transaction id
        ver.status = IdentityStatus.VERIFICATION_PENDING.value
        ver.provider_transaction_id = init_res.provider_transaction_id
        ver.failure_code = None
        ver.failure_message_safe = None
        ver.consent_obtained = True
        ver.consent_timestamp = now

        # 4. Record immutable audit
        audit = IdentityVerificationAudit(
            id=uuid.uuid4(),
            verification_id=ver.id,
            user_id=user.id,
            event_type=IdentityAuditEventType.IDENTITY_VERIFICATION_STARTED.value,
            provider=provider_type.value,
            actor_id=user.id,
            details_safe={
                "provider_transaction_id": init_res.provider_transaction_id,
                "request_id": request_id,
            },
        )
        db.add(audit)
        db.commit()

        logger.info(
            "identity_verification_started",
            user_id=str(user.id),
            provider=provider_type.value,
            tx_id=init_res.provider_transaction_id,
        )

        return IdentityVerificationStartResponse(
            success=True,
            provider=provider_type,
            status=IdentityStatus.VERIFICATION_PENDING,
            provider_transaction_id=init_res.provider_transaction_id,
            redirect_url=init_res.redirect_url,
            state_token=init_res.state_token,
            message="Verification session successfully initiated with provider.",
            is_provider_available=True,
            meta={"request_id": request_id},
        )

    async def process_callback(
        self,
        db: Session,
        user_id: uuid.UUID,
        callback_data: IdentityVerificationCallbackRequest,
        request_id: str = "",
    ) -> IdentityStatusResponse:
        """Process provider callback, validate tokens, and authoritatively update state."""
        provider_type = callback_data.provider
        provider = self.get_provider(provider_type)

        stmt = select(IdentityVerification).where(
            IdentityVerification.user_id == user_id,
            IdentityVerification.provider == provider_type.value,
        )
        ver = db.execute(stmt).scalar_one_or_none()
        if not ver:
            # Create placeholder if first touch
            ver = IdentityVerification(
                id=uuid.uuid4(),
                user_id=user_id,
                provider=provider_type.value,
                status=IdentityStatus.UNVERIFIED.value,
            )
            db.add(ver)

        # Idempotency check: if already verified with matching transaction, return existing state
        if (
            ver.status == IdentityStatus.VERIFIED.value
            and ver.provider_transaction_id
            and ver.provider_transaction_id == callback_data.provider_transaction_id
        ):
            logger.info("identity_callback_idempotent_replay", user_id=str(user_id))
            return self.get_user_verification_status(db, user_id, request_id=request_id)

        # Delegate validation to provider
        payload_dict = callback_data.model_dump(exclude_none=True)
        res = await provider.handle_callback(
            payload=payload_dict,
            state_token=callback_data.state,
            expected_nonce=callback_data.nonce,
        )

        audit_event = (
            IdentityAuditEventType.IDENTITY_VERIFIED.value
            if res.status == IdentityStatus.VERIFIED
            else IdentityAuditEventType.IDENTITY_VERIFICATION_FAILED.value
        )

        ver.status = res.status.value
        ver.provider_transaction_id = res.provider_transaction_id or ver.provider_transaction_id
        ver.provider_reference_hash = res.provider_reference_hash
        ver.identity_name_hash_or_minimal_reference = res.identity_name_hash_or_minimal_reference
        ver.verified_at = res.verified_at
        ver.expires_at = res.expires_at
        ver.failure_code = res.failure_code
        ver.failure_message_safe = res.failure_message_safe

        audit = IdentityVerificationAudit(
            id=uuid.uuid4(),
            verification_id=ver.id,
            user_id=user_id,
            event_type=audit_event,
            provider=provider_type.value,
            actor_id=user_id,
            details_safe={
                "status": res.status.value,
                "failure_code": res.failure_code,
                "request_id": request_id,
            },
        )
        db.add(audit)
        db.commit()

        logger.info(
            "identity_verification_completed",
            user_id=str(user_id),
            provider=provider_type.value,
            status=res.status.value,
            success=res.success,
        )

        return self.get_user_verification_status(db, user_id, request_id=request_id)
