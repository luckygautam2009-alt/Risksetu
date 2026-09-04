"""
Alert generation orchestration engine coordinating triggers, severity, deduplication, and persistence.
"""
from typing import Any
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertAudit
from app.services.alerts.constants import (
    AlertAuditAction,
    AlertStatus,
    CALCULATION_VERSION,
)
from app.services.alerts.decision_support import (
    generate_explanation_payload,
    generate_recommended_actions,
)
from app.services.alerts.deduplication import compute_alert_fingerprint, find_active_duplicate
from app.services.alerts.severity import determine_alert_severity
from app.services.alerts.triggers import evaluate_alert_triggers


def generate_operational_alert(
    db: Session,
    latitude: float,
    longitude: float,
    risk_score: float | None = None,
    risk_level: str | None = None,
    risk_confidence: float | None = None,
    isolation_severity: str | None = None,
    priority_score: float | None = None,
    priority_level: str | None = None,
    ground_intelligence_summary: dict[str, Any] | None = None,
    source_reference: dict[str, Any] | None = None,
    data_freshness: dict[str, Any] | None = None,
    created_by_user_id: uuid.UUID | None = None,
) -> tuple[Alert, bool]:
    """
    Coordinates end-to-end alert evaluation, deduplication, and persistence.
    Returns: (alert, is_newly_created)
    """
    # 1. Determine severity
    severity = determine_alert_severity(
        risk_score=risk_score,
        risk_level=risk_level,
        priority_score=priority_score,
        priority_level=priority_level,
        isolation_severity=isolation_severity,
        ground_intelligence_summary=ground_intelligence_summary,
    )

    # 2. Evaluate trigger
    alert_type, title, message, reasons = evaluate_alert_triggers(
        risk_score=risk_score,
        risk_level=risk_level,
        priority_score=priority_score,
        priority_level=priority_level,
        isolation_severity=isolation_severity,
        ground_intelligence_summary=ground_intelligence_summary,
    )

    # 3. Compute deterministic fingerprint
    source_id = str(source_reference.get("id") or "") if source_reference else ""
    fingerprint = compute_alert_fingerprint(
        alert_type=alert_type.value,
        severity=severity.value,
        latitude=latitude,
        longitude=longitude,
        source_id=source_id,
        calculation_version=CALCULATION_VERSION,
    )

    # 4. Check for existing active duplicate
    existing = find_active_duplicate(db, fingerprint)
    if existing:
        return existing, False

    # 5. Generate decision support recommendations & explainability
    recommended_actions = generate_recommended_actions(
        alert_type=alert_type,
        severity=severity,
        risk_score=risk_score,
        priority_score=priority_score,
        isolation_severity=isolation_severity,
        ground_intelligence_summary=ground_intelligence_summary,
    )

    explanation = generate_explanation_payload(
        alert_type=alert_type,
        severity=severity,
        reasons=reasons,
        risk_score=risk_score,
        risk_level=risk_level,
        priority_score=priority_score,
        priority_level=priority_level,
        isolation_severity=isolation_severity,
        ground_intelligence_summary=ground_intelligence_summary,
        data_freshness=data_freshness,
    )

    # 6. Instantiate and persist new Alert
    alert = Alert(
        id=uuid.uuid4(),
        alert_type=alert_type.value,
        severity=severity.value,
        status=AlertStatus.ACTIVE.value,
        title=title,
        message=message,
        latitude=latitude,
        longitude=longitude,
        risk_score=risk_score,
        risk_level=risk_level,
        risk_confidence=risk_confidence,
        isolation_severity=isolation_severity,
        priority_score=priority_score,
        priority_level=priority_level,
        ground_intelligence_summary=ground_intelligence_summary,
        fingerprint=fingerprint,
        source_reference=source_reference,
        recommended_actions=recommended_actions,
        explanation=explanation,
        data_freshness=data_freshness,
        calculation_version=CALCULATION_VERSION,
        audit_metadata={"created_by": str(created_by_user_id) if created_by_user_id else "SYSTEM"},
    )
    db.add(alert)
    db.flush()

    # 7. Add creation audit entry
    audit = AlertAudit(
        alert_id=alert.id,
        user_id=created_by_user_id,
        action=AlertAuditAction.CREATED.value,
        previous_state=None,
        new_state={"status": alert.status, "severity": alert.severity, "alert_type": alert.alert_type},
        reason="Initial automated alert generation",
    )
    db.add(audit)
    db.commit()
    db.refresh(alert)

    return alert, True


def list_alerts(
    db: Session,
    status: str | None = None,
    severity: str | None = None,
    alert_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Alert], int]:
    """
    Retrieves a paginated list of alerts with optional status/severity/type filters.
    """
    stmt = select(Alert)
    count_stmt = select(func.count(Alert.id))

    if status:
        stmt = stmt.where(Alert.status == status.upper())
        count_stmt = count_stmt.where(Alert.status == status.upper())
    if severity:
        stmt = stmt.where(Alert.severity == severity.upper())
        count_stmt = count_stmt.where(Alert.severity == severity.upper())
    if alert_type:
        stmt = stmt.where(Alert.alert_type == alert_type.upper())
        count_stmt = count_stmt.where(Alert.alert_type == alert_type.upper())

    total_count = db.execute(count_stmt).scalar() or 0
    stmt = stmt.order_by(desc(Alert.created_at)).limit(limit).offset(offset)
    alerts = list(db.execute(stmt).scalars().all())

    return alerts, total_count


def get_alert_by_id(db: Session, alert_id: uuid.UUID) -> Alert | None:
    """
    Retrieves a single alert entity by UUID.
    """
    return db.get(Alert, alert_id)
