"""
Audience Subscriptions Service.

Manages user notification preferences and determines audience matching for emergency alerts.
"""
from __future__ import annotations

import datetime
from typing import Sequence
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.subscription import AlertSubscription

DEFAULT_NOTIFICATION_TYPES = [
    "EMERGENCY_ALERTS",
    "CRITICAL_RISK",
    "ROAD_DISRUPTION",
    "GROUND_INTELLIGENCE",
]


class SubscriptionService:
    """Service managing user notification categories and geographic audience filtering."""

    def get_user_subscriptions(
        self,
        db: Session,
        user_id: uuid.UUID,
    ) -> list[AlertSubscription]:
        """Fetch all category subscriptions for a user, initializing defaults if needed."""
        stmt = select(AlertSubscription).where(AlertSubscription.user_id == user_id)
        existing = list(db.execute(stmt).scalars().all())

        if not existing:
            # Seed default subscriptions
            now = datetime.datetime.now(datetime.timezone.utc)
            for n_type in DEFAULT_NOTIFICATION_TYPES:
                sub = AlertSubscription(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    notification_type=n_type,
                    enabled=True,
                    geofence_radius_km=None,
                    created_at=now,
                    updated_at=now,
                )
                db.add(sub)
            db.commit()
            existing = list(db.execute(stmt).scalars().all())

        return existing

    def upsert_user_subscription(
        self,
        db: Session,
        user_id: uuid.UUID,
        notification_type: str,
        enabled: bool,
        geofence_radius_km: float | None = None,
    ) -> AlertSubscription:
        """Update or create a user subscription for an alert notification category."""
        stmt = select(AlertSubscription).where(
            AlertSubscription.user_id == user_id,
            AlertSubscription.notification_type == notification_type,
        )
        sub = db.execute(stmt).scalar_one_or_none()

        now = datetime.datetime.now(datetime.timezone.utc)
        if sub:
            sub.enabled = enabled
            sub.geofence_radius_km = geofence_radius_km
            sub.updated_at = now
        else:
            sub = AlertSubscription(
                id=uuid.uuid4(),
                user_id=user_id,
                notification_type=notification_type,
                enabled=enabled,
                geofence_radius_km=geofence_radius_km,
                created_at=now,
                updated_at=now,
            )
            db.add(sub)

        db.commit()
        db.refresh(sub)
        return sub

    def get_subscribers_for_event(
        self,
        db: Session,
        notification_type: str,
    ) -> Sequence[AlertSubscription]:
        """Fetch all active subscribers for an alert notification category."""
        stmt = select(AlertSubscription).where(
            AlertSubscription.notification_type == notification_type,
            AlertSubscription.enabled == True,  # noqa: E712
        )
        return db.execute(stmt).scalars().all()
