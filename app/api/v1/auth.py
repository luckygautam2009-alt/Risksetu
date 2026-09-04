"""
Authentication API endpoints for user registration and login.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
import structlog

from app.db.session import get_db
from app.schemas.ground_report import UserLoginRequest, UserRegisterRequest
from app.services.auth.service import AuthService

logger = structlog.get_logger("risksetu.auth_api")

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    request_body: UserRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Register a new user and return user info with initial access token."""
    user = AuthService.register_user(db, request_body)
    token_resp = AuthService.issue_token(user)
    rid = getattr(request.state, "request_id", "")

    logger.info("user_registered", user_id=str(user.id), email=user.email, role=user.role)
    return {
        "data": {
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
            "tokens": token_resp.model_dump(),
        },
        "meta": {"request_id": rid},
    }


@router.post(
    "/login",
    response_model=dict[str, Any],
    summary="Authenticate and obtain JWT access token",
)
async def login(
    request_body: UserLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Verify credentials and return access token."""
    user = AuthService.authenticate_user(db, request_body.email, request_body.password)
    token_resp = AuthService.issue_token(user)
    rid = getattr(request.state, "request_id", "")

    logger.info("user_logged_in", user_id=str(user.id), email=user.email)
    return {
        "data": {
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role,
            "tokens": token_resp.model_dump(),
        },
        "meta": {"request_id": rid},
    }
