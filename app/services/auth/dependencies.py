"""
FastAPI dependencies for authentication and role-based access control (RBAC).
"""
from __future__ import annotations

from typing import Callable
import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session
import structlog

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User

logger = structlog.get_logger("risksetu.auth.dependencies")

bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Validate Bearer JWT access token and return the authenticated User."""
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except JWTError as exc:
        logger.warning("invalid_token_presented", error=str(exc))
        raise UnauthorizedError("Invalid or expired authentication token.") from exc

    subject = payload.get("sub")
    if not subject:
        raise UnauthorizedError("Token payload missing subject.")

    try:
        user_uuid = uuid.UUID(subject)
    except ValueError as exc:
        raise UnauthorizedError("Invalid subject identifier format in token.") from exc

    user = db.execute(select(User).where(User.id == user_uuid)).scalar_one_or_none()
    if not user:
        raise UnauthorizedError("User account associated with this token not found.")

    if not user.is_active:
        raise UnauthorizedError("User account has been disabled.")

    return user


def require_role(allowed_roles: list[str]) -> Callable[[User], User]:
    """Dependency factory checking if current user possesses one of the allowed roles."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            logger.warning(
                "insufficient_role_permissions",
                user_id=str(current_user.id),
                user_role=current_user.role,
                allowed=allowed_roles,
            )
            raise ForbiddenError(f"Action requires one of the following roles: {', '.join(allowed_roles)}.")
        return current_user

    return role_checker
