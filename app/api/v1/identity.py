"""
Identity Verification API endpoints.

Handles initiation, status retrieval, callbacks, and user verification profiles.
All state is authoritative in PostgreSQL.
"""
from __future__ import annotations

from typing import Any
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
import structlog

from app.core.errors import ForbiddenError
from app.db.session import get_db
from app.models.user import User
from app.services.auth.dependencies import get_current_user
from app.services.identity.constants import (
    IdentityProviderType,
)
from app.services.identity.schemas import (
    IdentityStatusResponse,
    IdentityVerificationCallbackRequest,
    IdentityVerificationStartRequest,
    IdentityVerificationStartResponse,
)
from app.services.identity.service import IdentityService

logger = structlog.get_logger("risksetu.identity.api")
router = APIRouter(prefix="/identity", tags=["identity"])

_identity_service = IdentityService()


@router.post(
    "/verification/start",
    response_model=IdentityVerificationStartResponse,
    summary="Start an identity verification session",
)
async def start_identity_verification(
    request_body: IdentityVerificationStartRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IdentityVerificationStartResponse:
    """Initiate an identity verification session with Aadhaar or DigiLocker."""
    rid = getattr(request.state, "request_id", "")
    return await _identity_service.start_verification(
        db=db,
        user=current_user,
        provider_type=request_body.provider,
        consent=request_body.consent_obtained,
        redirect_uri=request_body.redirect_uri,
        request_id=rid,
    )


@router.post(
    "/verification/digilocker/start",
    response_model=IdentityVerificationStartResponse,
    summary="Initiate DigiLocker OAuth2 consent flow",
)
async def start_digilocker_verification(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IdentityVerificationStartResponse:
    """Convenience endpoint starting DigiLocker flow with default consent."""
    rid = getattr(request.state, "request_id", "")
    return await _identity_service.start_verification(
        db=db,
        user=current_user,
        provider_type=IdentityProviderType.DIGILOCKER,
        consent=True,
        request_id=rid,
    )


@router.get(
    "/verification/status",
    response_model=IdentityStatusResponse,
    summary="Query own identity verification status",
)
async def get_my_verification_status(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IdentityStatusResponse:
    """Retrieve current user's authoritative identity verification state."""
    rid = getattr(request.state, "request_id", "")
    return _identity_service.get_user_verification_status(
        db=db,
        user_id=current_user.id,
        request_id=rid,
    )


@router.get(
    "/verification/status/{target_user_id}",
    response_model=IdentityStatusResponse,
    summary="Inspect verification status (Official/Admin only or self)",
)
async def inspect_user_verification_status(
    target_user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IdentityStatusResponse:
    """Official and Admin operators may inspect citizen verification states for triage."""
    rid = getattr(request.state, "request_id", "")
    if current_user.id != target_user_id and current_user.role not in ("official", "admin"):
        raise ForbiddenError("Citizens may only inspect their own identity verification state.")

    return _identity_service.get_user_verification_status(
        db=db,
        user_id=target_user_id,
        request_id=rid,
    )


@router.post(
    "/verification/callback",
    response_model=IdentityStatusResponse,
    summary="Handle provider verification callback",
)
async def process_verification_callback(
    callback_payload: IdentityVerificationCallbackRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IdentityStatusResponse:
    """Process callback/redirect payload from identity provider."""
    rid = getattr(request.state, "request_id", "")
    return await _identity_service.process_callback(
        db=db,
        user_id=current_user.id,
        callback_data=callback_payload,
        request_id=rid,
    )


@router.get(
    "/me",
    response_model=dict[str, Any],
    summary="Retrieve current user profile with identity verification state",
)
async def get_identity_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve authenticated user details and authoritative verification badge."""
    rid = getattr(request.state, "request_id", "")
    status_resp = _identity_service.get_user_verification_status(db, current_user.id, request_id=rid)
    return {
        "data": {
            "user_id": str(current_user.id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "identity": status_resp.data.model_dump(),
        },
        "meta": {"request_id": rid},
    }
