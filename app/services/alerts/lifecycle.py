"""
Alert lifecycle management and state transitions with mandatory audit trails.
"""
import datetime
import uuid

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.models.alert import Alert, AlertAudit
from app.services.alerts.constants import AlertAuditAction, AlertStatus


VALID_TRANSITIONS = {
    AlertStatus.ACTIVE: {AlertStatus.ACKNOWLEDGED, AlertStatus.RESOLVED, AlertStatus.DISMISSED},
    AlertStatus.ACKNOWLEDGED: {AlertStatus.RESOLVED, AlertStatus.DISMISSED},
    AlertStatus.RESOLVED: set(),
    AlertStatus.DISMISSED: set(),
}


def transition_alert_status(
    db: Session,
    alert_id: uuid.UUID,
    target_status: AlertStatus,
    user_id: uuid.UUID,
    reason: str | None = None,
) -> Alert:
    """
    Executes a validated state transition on an Alert entity, recording an immutable audit log.
    """
    alert = db.get(Alert, alert_id)
    if not alert:
        raise NotFoundError(f"Alert with id '{alert_id}' not found")

    current_status = AlertStatus(alert.status)

    if current_status == target_status:
        raise ConflictError(f"Alert is already in {target_status.value} status")

    if target_status not in VALID_TRANSITIONS.get(current_status, set()):
        if current_status in (AlertStatus.RESOLVED, AlertStatus.DISMISSED):
            raise ConflictError(f"Cannot transition alert from terminal status '{current_status.value}'")
        raise ValidationAppError(
            f"Invalid status transition from '{current_status.value}' to '{target_status.value}'"
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    old_state = {
        "status": alert.status,
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
    }

    if target_status == AlertStatus.ACKNOWLEDGED:
        alert.acknowledged_at = now
        alert.acknowledged_by = user_id
        action = AlertAuditAction.ACKNOWLEDGED
    elif target_status in (AlertStatus.RESOLVED, AlertStatus.DISMISSED):
        alert.resolved_at = now
        alert.resolved_by = user_id
        action = AlertAuditAction.RESOLVED if target_status == AlertStatus.RESOLVED else AlertAuditAction.DISMISSED
    else:
        action = AlertAuditAction.CREATED

    alert.status = target_status.value
    alert.updated_at = now

    new_state = {
        "status": alert.status,
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
    }

    audit = AlertAudit(
        alert_id=alert.id,
        user_id=user_id,
        action=action.value,
        previous_state=old_state,
        new_state=new_state,
        reason=reason,
        created_at=now,
    )
    db.add(audit)
    db.commit()
    db.refresh(alert)
    return alert
