"""
FastAPI authorization dependency requiring authoritative verified identity status.
"""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session
import structlog

from app.core.errors import IdentityVerificationRequiredError
from app.db.session import get_db
from app.models.user import User
from app.services.auth.dependencies import get_current_user
from app.services.identity.service import IdentityService

logger = structlog.get_logger("risksetu.identity.dependencies")

_identity_service = IdentityService()


async def require_verified_identity(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Authoritatively enforce that the requesting user has a verified identity.

    If unverified, verification is pending, failed, or expired, raises HTTP 403
    with stable machine error code IDENTITY_VERIFICATION_REQUIRED.
    """
    is_verified = _identity_service.is_user_verified(db=db, user_id=current_user.id)

    if not is_verified:
        logger.warning(
            "unverified_evidence_access_denied",
            user_id=str(current_user.id),
            user_role=current_user.role,
        )
        raise IdentityVerificationRequiredError(
            "Identity verification is required before submitting photographic emergency evidence."
        )

    return current_user
