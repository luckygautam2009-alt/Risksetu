"""
Alert Subscription Management API endpoints.

Allows authenticated users to manage their notification preferences for
real-time alert delivery channels (emergency alerts, critical risk, etc.).

PostgreSQL is the single source of truth for subscription state.
"""
from __future__ import annotations

from typing import Any
import uuid

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
import structlog

from app.db.session import get_db
from app.models.subscription import AlertSubscription
from app.models.user import User
from app.services.auth.dependencies import get_current_user

logger = structlog.get_logger("risksetu.subscriptions_api")
router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

VALID_NOTIFICATION_TYPES = frozenset({
    "EMERGENCY_ALERTS",
    "CRITICAL_RISK",
    "ROAD_DISRUPTION",
    "GROUND_INTELLIGENCE",
})


class SubscriptionItem(BaseModel):
    notification_type: str
    enabled: bool = True
    geofence_radius_km: float | None = None

    @field_validator("notification_type")
    @classmethod
    def validate_notification_type(cls, v: str) -> str:
        if v not in VALID_NOTIFICATION_TYPES:
            raise ValueError(
                f"Invalid notification_type '{v}'. Must be one of: {sorted(VALID_NOTIFICATION_TYPES)}"
            )
        return v


class SubscriptionUpdateRequest(BaseModel):
    subscriptions: list[SubscriptionItem] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of subscription preferences to upsert.",
    )


class SubscriptionData(BaseModel):
    id: str
    notification_type: str
    enabled: bool
    geofence_radius_km: float | None
    created_at: str
    updated_at: str


class SubscriptionListResponse(BaseModel):
    data: list[SubscriptionData]
    meta: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def _to_subscription_data(sub: AlertSubscription) -> SubscriptionData:
    return SubscriptionData(
        id=str(sub.id),
        notification_type=sub.notification_type,
        enabled=sub.enabled,
        geofence_radius_km=sub.geofence_radius_km,
        created_at=sub.created_at.isoformat() if sub.created_at else "",
        updated_at=sub.updated_at.isoformat() if sub.updated_at else "",
    )


@router.get(
    "/me",
    response_model=SubscriptionListResponse,
    summary="Fetch current user's alert notification preferences",
)
async def get_my_subscriptions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionListResponse:
    """Returns the authenticated user's alert subscription preferences from PostgreSQL."""
    rid = getattr(request.state, "request_id", "")
    subs = (
        db.query(AlertSubscription)
        .filter(AlertSubscription.user_id == current_user.id)
        .order_by(AlertSubscription.notification_type)
        .all()
    )
    return SubscriptionListResponse(
        data=[_to_subscription_data(s) for s in subs],
        meta={"request_id": rid},
    )


@router.post(
    "",
    response_model=SubscriptionListResponse,
    status_code=status.HTTP_200_OK,
    summary="Upsert user notification subscriptions",
)
async def update_subscriptions(
    request_body: SubscriptionUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionListResponse:
    """Upserts notification subscription preferences.

    Creates new subscriptions or updates existing ones based on
    (user_id, notification_type) unique constraint.
    """
    rid = getattr(request.state, "request_id", "")
    results: list[AlertSubscription] = []

    for item in request_body.subscriptions:
        if item.notification_type not in VALID_NOTIFICATION_TYPES:
            logger.warning(
                "subscription_invalid_type",
                notification_type=item.notification_type,
                user_id=str(current_user.id),
            )
            continue

        existing = (
            db.query(AlertSubscription)
            .filter(
                AlertSubscription.user_id == current_user.id,
                AlertSubscription.notification_type == item.notification_type,
            )
            .first()
        )

        if existing:
            existing.enabled = item.enabled
            existing.geofence_radius_km = item.geofence_radius_km
            results.append(existing)
        else:
            new_sub = AlertSubscription(
                id=uuid.uuid4(),
                user_id=current_user.id,
                notification_type=item.notification_type,
                enabled=item.enabled,
                geofence_radius_km=item.geofence_radius_km,
            )
            db.add(new_sub)
            results.append(new_sub)

    db.commit()
    for r in results:
        db.refresh(r)

    logger.info(
        "subscriptions_updated",
        user_id=str(current_user.id),
        count=len(results),
    )

    return SubscriptionListResponse(
        data=[_to_subscription_data(s) for s in results],
        meta={"request_id": rid, "upserted": len(results)},
    )
