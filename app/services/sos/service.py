"""
SOS service — CRUD, lifecycle, evidence linkage, and alert integration.

Responsibilities:
  - Create SOS report + audit + async risk assessment + evidence binding
  - Enforce idempotency key handling
  - Validate and execute lifecycle transitions (ACTIVE→ACKNOWLEDGED→RESOLVED/CANCELLED)
  - Link to alert system (generate SOS_EMERGENCY alert when risk ≥ threshold or high severity)
  - Never fabricate risk, shelter, weather, or closure data
"""
from __future__ import annotations

import datetime
from datetime import timezone
from typing import Any
import uuid

import structlog
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.alert import Alert
from app.models.evidence import IncidentEvidence
from app.models.sos import SOSAudit, SOSReport
from app.schemas.sos import SOSRiskContext
from app.services.alerts.engine import generate_operational_alert
from app.services.sos.constants import (
    SOS_ALERT_RISK_THRESHOLD,
    SOS_VALID_TRANSITIONS,
    SOSAuditAction,
    SOSSeverity,
    SOSStatus,
)

logger = structlog.get_logger("risksetu.sos.service")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _geom_expr(lat: float, lon: float) -> Any:
    from sqlalchemy import func as sql_func
    return sql_func.ST_SetSRID(sql_func.ST_MakePoint(lon, lat), 4326)


def _write_audit(
    db: Session,
    sos: SOSReport,
    action: SOSAuditAction,
    user_id: uuid.UUID | None,
    previous_status: str | None,
    new_status: str | None,
    reason: str | None = None,
    metadata_json: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> None:
    audit = SOSAudit(
        sos_id=sos.id,
        user_id=user_id,
        action=action.value,
        previous_status=previous_status,
        new_status=new_status,
        reason=reason,
        metadata_json=metadata_json,
        request_id=request_id,
    )
    db.add(audit)


# ---------------------------------------------------------------------------
# Create SOS
# ---------------------------------------------------------------------------

def create_sos(
    db: Session,
    latitude: float,
    longitude: float,
    severity: str = SOSSeverity.MEDIUM.value,
    description: str | None = None,
    location_accuracy_meters: float | None = None,
    evidence_id: uuid.UUID | str | None = None,
    reported_by: uuid.UUID | None = None,
    created_by_verified_identity: bool = True,
    idempotency_key: str | None = None,
    request_id: str | None = None,
) -> tuple[SOSReport, bool]:
    """Create a new SOS report or return existing idempotent record."""
    # 1. Idempotency Check
    if idempotency_key and reported_by:
        stmt = select(SOSReport).where(
            SOSReport.reported_by == reported_by,
            SOSReport.idempotency_key == idempotency_key,
        )
        existing = db.execute(stmt).scalar_one_or_none()
        if existing:
            logger.info("sos_idempotent_replay", sos_id=str(existing.id), key=idempotency_key)
            return existing, False

    # 2. Instantiate and persist SOS
    sos = SOSReport(
        id=uuid.uuid4(),
        latitude=latitude,
        longitude=longitude,
        geom=_geom_expr(latitude, longitude),
        location_accuracy_meters=location_accuracy_meters,
        severity=severity.upper(),
        description=description,
        status=SOSStatus.ACTIVE.value,
        risk_source="LIVE_RISK_V1",
        evidence_count=0,
        created_by_verified_identity=created_by_verified_identity,
        idempotency_key=idempotency_key,
        reported_by=reported_by,
        request_id=request_id,
    )
    db.add(sos)
    db.flush()

    _write_audit(
        db,
        sos,
        action=SOSAuditAction.CREATED,
        user_id=reported_by,
        previous_status=None,
        new_status=SOSStatus.ACTIVE.value,
        reason="SOS emergency report submitted.",
        metadata_json={
            "accuracy_m": location_accuracy_meters,
            "idempotency_key": idempotency_key,
            "has_evidence": bool(evidence_id),
        },
        request_id=request_id,
    )

    # 3. Evidence Attachment
    if evidence_id:
        try:
            ev_uuid = uuid.UUID(str(evidence_id))
            ev = db.get(IncidentEvidence, ev_uuid)
            if ev and (reported_by is None or ev.owner_user_id == reported_by):
                ev.sos_id = sos.id
                sos.evidence_count = 1
                _write_audit(
                    db,
                    sos,
                    action=SOSAuditAction.EVIDENCE_ATTACHED,
                    user_id=reported_by,
                    previous_status=sos.status,
                    new_status=sos.status,
                    metadata_json={
                        "evidence_id": str(ev.id),
                        "sha256": ev.sha256,
                        "size_bytes": ev.size_bytes,
                    },
                    request_id=request_id,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("sos_evidence_linking_error", error=str(exc))

    db.commit()
    db.refresh(sos)
    logger.info("sos_created", sos_id=str(sos.id), lat=latitude, lon=longitude, severity=severity)
    return sos, True


# ---------------------------------------------------------------------------
# Attach risk context (called after live-risk evaluation)
# ---------------------------------------------------------------------------

def attach_risk_context(
    db: Session,
    sos: SOSReport,
    risk_context: SOSRiskContext,
    request_id: str | None = None,
) -> SOSReport:
    """Store the live risk assessment snapshot on the SOS record."""
    sos.live_risk_score = risk_context.risk_score
    sos.live_risk_level = risk_context.risk_level
    sos.live_risk_confidence = risk_context.risk_confidence
    sos.risk_source = "LIVE_RISK_V1"
    sos.risk_context = {
        "risk_score": risk_context.risk_score,
        "risk_level": risk_context.risk_level,
        "risk_confidence": risk_context.risk_confidence,
        "weather_status": risk_context.weather_status,
        "live_risk_available": risk_context.live_risk_available,
        "assessment_timestamp": (
            risk_context.assessment_timestamp.isoformat()
            if risk_context.assessment_timestamp
            else None
        ),
    }
    _write_audit(
        db,
        sos,
        action=SOSAuditAction.RISK_ASSESSED,
        user_id=None,
        previous_status=sos.status,
        new_status=sos.status,
        metadata_json={
            "risk_score": risk_context.risk_score,
            "risk_level": risk_context.risk_level,
        },
        request_id=request_id,
    )
    db.commit()
    db.refresh(sos)
    return sos


# ---------------------------------------------------------------------------
# Generate linked alert when risk is high or severity is elevated
# ---------------------------------------------------------------------------

def maybe_generate_sos_alert(
    db: Session,
    sos: SOSReport,
    request_id: str | None = None,
) -> Alert | None:
    """Generate a linked SOS_EMERGENCY alert using the existing alert engine."""
    risk_score_norm: float | None = None
    if sos.live_risk_score is not None:
        risk_score_norm = sos.live_risk_score / 100.0 if sos.live_risk_score > 1.0 else sos.live_risk_score

    # Check trigger condition
    should_alert = (
        sos.live_risk_score is not None and sos.live_risk_score >= SOS_ALERT_RISK_THRESHOLD
    )

    if not should_alert:
        return None

    description_note = (sos.description or "")[:200]
    source_ref: dict[str, Any] = {
        "id": f"sos_{sos.id}",
        "sos_id": str(sos.id),
        "sos_severity": sos.severity,
        "evidence_count": sos.evidence_count,
        "description": description_note,
        "source": "VERIFIED_CITIZEN",
    }

    alert, _ = generate_operational_alert(
        db=db,
        latitude=sos.latitude,
        longitude=sos.longitude,
        risk_score=risk_score_norm,
        risk_level=sos.live_risk_level,
        risk_confidence=(
            sos.live_risk_confidence / 100.0
            if sos.live_risk_confidence is not None and sos.live_risk_confidence > 1.0
            else sos.live_risk_confidence
        ),
        isolation_severity=None,
        priority_score=None,
        priority_level=None,
        ground_intelligence_summary=None,
        source_reference=source_ref,
        data_freshness={"sos_created_at": sos.created_at.isoformat()},
        created_by_user_id=sos.reported_by,
    )

    if sos.linked_alert_id is None:
        sos.linked_alert_id = alert.id
        _write_audit(
            db,
            sos,
            action=SOSAuditAction.ALERT_LINKED,
            user_id=None,
            previous_status=sos.status,
            new_status=sos.status,
            metadata_json={"alert_id": str(alert.id)},
            request_id=request_id,
        )
        db.commit()
        db.refresh(sos)

    logger.info("sos_alert_linked", sos_id=str(sos.id), alert_id=str(alert.id))
    return alert


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------

def transition_sos_status(
    db: Session,
    sos_id: uuid.UUID,
    target_status: SOSStatus,
    acting_user_id: uuid.UUID,
    reason: str | None = None,
    request_id: str | None = None,
) -> SOSReport:
    """Validate and execute a lifecycle transition with audit trail."""
    sos = db.get(SOSReport, sos_id)
    if not sos:
        raise NotFoundError(f"SOS report '{sos_id}' not found.")

    current = SOSStatus(sos.status)
    allowed = SOS_VALID_TRANSITIONS.get(current, set())
    if target_status not in allowed:
        raise ConflictError(
            f"Cannot transition SOS from {current.value} to {target_status.value}. "
            f"Allowed: {[s.value for s in allowed] or 'none'}."
        )

    previous_status = sos.status
    sos.status = target_status.value

    now = datetime.datetime.now(timezone.utc)

    if target_status == SOSStatus.ACKNOWLEDGED:
        sos.acknowledged_by = acting_user_id
        sos.acknowledged_at = now
        action = SOSAuditAction.ACKNOWLEDGED
    elif target_status == SOSStatus.RESOLVED:
        sos.resolved_by = acting_user_id
        sos.resolved_at = now
        action = SOSAuditAction.RESOLVED
    else:
        sos.cancelled_at = now
        action = SOSAuditAction.CANCELLED

    _write_audit(
        db,
        sos,
        action=action,
        user_id=acting_user_id,
        previous_status=previous_status,
        new_status=target_status.value,
        reason=reason,
        request_id=request_id,
    )
    db.commit()
    db.refresh(sos)
    logger.info(
        "sos_transition",
        sos_id=str(sos_id),
        from_status=previous_status,
        to_status=target_status.value,
    )
    return sos


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def get_sos_by_id(db: Session, sos_id: uuid.UUID) -> SOSReport | None:
    return db.get(SOSReport, sos_id)


def get_sos_evidence(db: Session, sos_id: uuid.UUID) -> list[IncidentEvidence]:
    stmt = select(IncidentEvidence).where(IncidentEvidence.sos_id == sos_id)
    return list(db.execute(stmt).scalars().all())


def get_sos_audits(db: Session, sos_id: uuid.UUID) -> list[SOSAudit]:
    stmt = select(SOSAudit).where(SOSAudit.sos_id == sos_id).order_by(SOSAudit.created_at.asc())
    return list(db.execute(stmt).scalars().all())


def list_sos(
    db: Session,
    status: str | None = None,
    reported_by: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[SOSReport], int]:
    stmt = select(SOSReport)
    count_stmt = select(func.count(SOSReport.id))
    if status:
        stmt = stmt.where(SOSReport.status == status.upper())
        count_stmt = count_stmt.where(SOSReport.status == status.upper())
    if reported_by:
        stmt = stmt.where(SOSReport.reported_by == reported_by)
        count_stmt = count_stmt.where(SOSReport.reported_by == reported_by)

    total = db.execute(count_stmt).scalar() or 0
    stmt = stmt.order_by(desc(SOSReport.created_at)).limit(limit).offset(offset)
    items = list(db.execute(stmt).scalars().all())
    return items, total
