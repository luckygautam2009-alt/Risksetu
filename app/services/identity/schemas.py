"""
Pydantic v2 schemas for identity verification requests and responses.
"""
from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.services.identity.constants import (
    IdentityProviderType,
    IdentityStatus,
)


class IdentityVerificationStartRequest(BaseModel):
    """Payload to initiate an identity verification session."""

    model_config = ConfigDict(extra="forbid")

    provider: IdentityProviderType = Field(..., description="Identity provider (AADHAAR or DIGILOCKER)")
    consent_obtained: bool = Field(..., description="Explicit citizen consent acknowledgment")
    redirect_uri: str | None = Field(None, description="Optional OAuth redirect return URI")


class IdentityVerificationStartResponse(BaseModel):
    """Response returned upon initiation of verification."""

    success: bool
    provider: IdentityProviderType
    status: IdentityStatus
    provider_transaction_id: str | None = None
    redirect_url: str | None = None
    state_token: str | None = None
    message: str
    is_provider_available: bool = True
    meta: dict[str, Any] = Field(default_factory=dict)


class IdentityVerificationCallbackRequest(BaseModel):
    """Payload received from client or provider callback/webhook."""

    model_config = ConfigDict(extra="allow")

    provider: IdentityProviderType
    provider_transaction_id: str | None = None
    code: str | None = None
    state: str | None = None
    nonce: str | None = None
    gateway_status: str | None = None
    reference_id: str | None = None
    name_reference: str | None = None
    failure_code: str | None = None


class IdentityStatusData(BaseModel):
    """Current identity verification state of a user."""

    user_id: str
    status: IdentityStatus
    is_verified: bool
    provider: IdentityProviderType | None = None
    verified_at: datetime.datetime | None = None
    expires_at: datetime.datetime | None = None
    minimal_reference: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None


class IdentityStatusResponse(BaseModel):
    """Response envelope for identity verification status queries."""

    data: IdentityStatusData
    meta: dict[str, Any] = Field(default_factory=dict)
