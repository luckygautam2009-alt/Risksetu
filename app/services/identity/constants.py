"""
Constants and enumerations for the identity verification domain.
"""
from __future__ import annotations

from enum import Enum


class IdentityStatus(str, Enum):
    """Authoritative identity verification lifecycle status."""

    UNVERIFIED = "UNVERIFIED"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    VERIFIED = "VERIFIED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    VERIFICATION_EXPIRED = "VERIFICATION_EXPIRED"


class IdentityProviderType(str, Enum):
    """Supported identity verification provider adapters."""

    AADHAAR = "AADHAAR"
    DIGILOCKER = "DIGILOCKER"


class IdentityAuditEventType(str, Enum):
    """Immutable audit event types for identity lifecycle changes."""

    IDENTITY_VERIFICATION_STARTED = "IDENTITY_VERIFICATION_STARTED"
    IDENTITY_VERIFICATION_CALLBACK_RECEIVED = "IDENTITY_VERIFICATION_CALLBACK_RECEIVED"
    IDENTITY_VERIFIED = "IDENTITY_VERIFIED"
    IDENTITY_VERIFICATION_FAILED = "IDENTITY_VERIFICATION_FAILED"
    IDENTITY_VERIFICATION_EXPIRED = "IDENTITY_VERIFICATION_EXPIRED"


PROVIDER_UNAVAILABLE_CODE = "VERIFICATION_PROVIDER_UNAVAILABLE"
PROVIDER_UNAVAILABLE_MESSAGE = (
    "Identity verification provider is currently unconfigured or unavailable in this deployment."
)
