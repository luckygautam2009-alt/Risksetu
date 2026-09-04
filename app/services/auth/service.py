"""
User authentication and credential verification service.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.ground_report import TokenResponse, UserRegisterRequest


class AuthService:
    """Handles user registration, authentication, and token management."""

    @staticmethod
    def register_user(db: Session, request: UserRegisterRequest) -> User:
        """Register a new user account."""
        existing = db.execute(select(User).where(User.email == request.email.lower())).scalar_one_or_none()
        if existing:
            raise ConflictError(f"User with email '{request.email}' already exists.")

        user = User(
            email=request.email.lower(),
            hashed_password=hash_password(request.password),
            full_name=request.full_name,
            role=request.role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def authenticate_user(db: Session, email: str, plain_password: str) -> User:
        """Authenticate user credentials and return the user entity."""
        user = db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()
        if not user or not user.is_active:
            raise UnauthorizedError("Invalid email or password.")

        if not verify_password(plain_password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password.")

        return user

    @staticmethod
    def issue_token(user: User) -> TokenResponse:
        """Generate JWT access token for an authenticated user."""
        token = create_access_token(
            subject=str(user.id),
            extra_claims={"email": user.email, "role": user.role},
        )
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user_id=str(user.id),
            role=user.role,
        )
