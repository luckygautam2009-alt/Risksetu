"""
Abstract identity verification provider boundary.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import datetime
from typing import Any
import uuid

from app.services.identity.constants import (
    IdentityProviderType,
    IdentityStatus,
)


@dataclass
class InitiationResult:
    """Result of initiating an identity verification session with a provider."""

    success: bool
    provider: IdentityProviderType
    provider_transaction_id: str | None = None
    redirect_url: str | None = None
    state_token: str | None = None
    nonce: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    is_provider_available: bool = True


@dataclass
class VerificationResult:
    """Normalized result of a provider verification callback or query."""

    success: bool
    provider: IdentityProviderType
    status: IdentityStatus
    provider_transaction_id: str | None = None
    provider_reference_hash: str | None = None
    identity_name_hash_or_minimal_reference: str | None = None
    verified_at: datetime.datetime | None = None
    expires_at: datetime.datetime | None = None
    failure_code: str | None = None
    failure_message_safe: str | None = None
    is_provider_available: bool = True


class IdentityVerificationProvider(ABC):
    """Abstract interface defining the identity verification contract.

    RISKSETU AI business logic depends strictly on this abstraction, ensuring
    no coupling to specific UIDAI / DigiLocker protocols or SDKs.
    """

    @property
    @abstractmethod
    def provider_type(self) -> IdentityProviderType:
        """The identity provider classification."""

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """True if production or sandbox credentials and endpoints are validly configured."""

    @abstractmethod
    async def initiate_verification(
        self,
        user_id: uuid.UUID,
        consent: bool,
        redirect_uri: str | None = None,
    ) -> InitiationResult:
        """Start a verification flow with the external provider."""

    @abstractmethod
    async def handle_callback(
        self,
        payload: dict[str, Any],
        state_token: str | None = None,
        expected_nonce: str | None = None,
    ) -> VerificationResult:
        """Process and cryptographically validate provider callback / redirection data."""

    @abstractmethod
    async def get_status(
        self,
        provider_transaction_id: str,
    ) -> VerificationResult:
        """Poll or inspect the verification status for a provider transaction."""
