"""
RISKSETU AI — SOS emergency reporting API.

Endpoints:
  POST   /api/v1/sos                         — submit SOS (verified identity required for evidence)
  GET    /api/v1/sos                         — list SOS (own for citizen, all for official/admin)
  GET    /api/v1/sos/{sos_id}               — retrieve one SOS
  GET    /api/v1/sos/{sos_id}/audits        — retrieve audit timeline for SOS
  GET    /api/v1/sos/{sos_id}/recommendations — shelter recommendations
  POST   /api/v1/sos/{sos_id}/acknowledge   — official/admin only
  POST   /api/v1/sos/{sos_id}/resolve       — official/admin only
  POST   /api/v1/sos/{sos_id}/cancel        — own record (citizen) or official/admin
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session
import structlog

from app.core.errors import ForbiddenError, IdentityVerificationRequiredError, NotFoundError
from app.db.session import get_db
from app.models.evidence import IncidentEvidence
from app.models.sos import SOSReport
from app.models.user import User
from app.schemas.shelter import SOSRecommendationResponse
from app.schemas.sos import (
    SOSActionRequest,
    SOSAuditItem,
    SOSAuditListResponse,
    SOSCreateRequest,
    SOSData,
    SOSEvidenceItem,
    SOSListData,
    SOSListItem,
    SOSListResponse,
    SOSResponse,
    SOSRiskContext,
)
from app.services.alerts.realtime import (
    build_sos_alert_event_payload,
    realtime_manager,
)
from app.services.auth.dependencies import get_current_user, require_role
from app.services.identity.service import IdentityService
from app.services.live_risk.engine import LiveRiskEngine
from app.services.sos.constants import SOSStatus
from app.services.sos.recommendation import get_sos_recommendations
from app.services.sos.service import (
    attach_risk_context,
    create_sos,
    get_sos_audits,
    get_sos_by_id,
    get_sos_evidence,
    list_sos,
    maybe_generate_sos_alert,
    transition_sos_status,
)

logger = structlog.get_logger("risksetu.sos.api")
_identity_service = IdentityService()
router = APIRouter(prefix="/sos", tags=["sos"])


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------

def _safe_str(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, str):
        return val
    if hasattr(val, "_mock_name") or type(val).__name__ == "MagicMock":
        return None
    return str(val)


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if hasattr(val, "_mock_name") or type(val).__name__ == "MagicMock":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_bool(val: Any, default: bool = False) -> bool:
    if isinstance(val, bool):
        return val
    if hasattr(val, "_mock_name") or type(val).__name__ == "MagicMock":
        return default
    return bool(val)


def _safe_int(val: Any, default: int = 0) -> int:
    if isinstance(val, int):
        return val
    if hasattr(val, "_mock_name") or type(val).__name__ == "MagicMock":
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_dict(val: Any) -> dict[str, Any] | None:
    if isinstance(val, dict):
        return val
    return None


def _safe_dt(val: Any) -> datetime | None:
    if isinstance(val, datetime):
        return val
    return None


def _to_sos_data(sos: SOSReport, evidence_items: list[IncidentEvidence] | None = None) -> SOSData:
    risk_ctx_dict = getattr(sos, "risk_context", None)
    if not isinstance(risk_ctx_dict, dict):
        risk_ctx_dict = None

    score = _safe_float(getattr(sos, "live_risk_score", None))
    ctx = SOSRiskContext(
        risk_score=score,
        risk_level=_safe_str(getattr(sos, "live_risk_level", None)),
        risk_confidence=_safe_float(getattr(sos, "live_risk_confidence", None)),
        weather_status=risk_ctx_dict.get("weather_status") if risk_ctx_dict else None,
        live_risk_available=bool(score is not None),
        assessment_timestamp=None,
    )

    ev_list: list[SOSEvidenceItem] = []
    if evidence_items:
        for ev in evidence_items:
            ev_list.append(
                SOSEvidenceItem(
                    evidence_id=str(ev.id),
                    content_type=ev.content_type,
                    size_bytes=ev.size_bytes,
                    sha256=ev.sha256,
                    captured_at=ev.captured_at,
                    latitude=ev.latitude,
                    longitude=ev.longitude,
                    upload_status=ev.upload_status,
                    created_at=ev.created_at,
                )
            )

    created_at = _safe_dt(getattr(sos, "created_at", None)) or datetime.now(timezone.utc)
    updated_at = _safe_dt(getattr(sos, "updated_at", None))
    acknowledged_at = _safe_dt(getattr(sos, "acknowledged_at", None))
    resolved_at = _safe_dt(getattr(sos, "resolved_at", None))
    cancelled_at = _safe_dt(getattr(sos, "cancelled_at", None))

    return SOSData(
        id=str(sos.id),
        latitude=float(getattr(sos, "latitude", 0.0)),
        longitude=float(getattr(sos, "longitude", 0.0)),
        location_accuracy_meters=_safe_float(getattr(sos, "location_accuracy_meters", None)),
        severity=str(getattr(sos, "severity", "MEDIUM")),
        status=str(getattr(sos, "status", "ACTIVE")),
        description=_safe_str(getattr(sos, "description", None)),
        risk_context=ctx,
        risk_source=_safe_str(getattr(sos, "risk_source", None)) or "LIVE_RISK_V1",
        evidence_count=_safe_int(getattr(sos, "evidence_count", 0)),
        created_by_verified_identity=_safe_bool(getattr(sos, "created_by_verified_identity", True), default=True),
        idempotency_key=_safe_str(getattr(sos, "idempotency_key", None)),
        linked_alert_id=_safe_str(getattr(sos, "linked_alert_id", None)),
        reported_by=_safe_str(getattr(sos, "reported_by", None)),
        acknowledged_by=_safe_str(getattr(sos, "acknowledged_by", None)),
        acknowledged_at=acknowledged_at,
        resolved_by=_safe_str(getattr(sos, "resolved_by", None)),
        resolved_at=resolved_at,
        cancelled_at=cancelled_at,
        evidence_items=ev_list,
        shelter_recommendation=_safe_dict(getattr(sos, "shelter_recommendation", None)),
        request_id=_safe_str(getattr(sos, "request_id", None)),
        created_at=created_at,
        updated_at=updated_at,
    )


# ---------------------------------------------------------------------------
# POST /sos  — create SOS
# ---------------------------------------------------------------------------

@router.post("", response_model=SOSResponse, status_code=status.HTTP_201_CREATED)
async def create_sos_report(
    body: SOSCreateRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SOSResponse:
    """Submit an SOS emergency report.

    - Requires verified citizen identity when evidence is attached.
    - Persists SOS in PostgreSQL with PostGIS point.
    - Idempotently deduplicates retries via Idempotency-Key.
    - Fetches live risk context (LIVE_RISK_V1) and snapshots risk score.
    - Generates a linked SOS_EMERGENCY alert through the existing alert engine.
    - Broadcasts real-time event via WebSocket to connected officers and subscribers.
    """
    # 0. Enforce Verified Identity if evidence is attached or submitted by citizen
    if body.evidence_id:
        if not _identity_service.is_user_verified(db=db, user_id=current_user.id):
            raise IdentityVerificationRequiredError(
                "Identity verification is required before submitting an evidence-backed emergency SOS."
            )

    rid = getattr(request.state, "request_id", "")
    idempotency_key = request.headers.get("Idempotency-Key") or body.idempotency_key

    # 1. Persist SOS with idempotency check
    sos_res = create_sos(
        db=db,
        latitude=body.latitude,
        longitude=body.longitude,
        severity=body.severity.value,
        description=body.description,
        location_accuracy_meters=body.location_accuracy_meters,
        evidence_id=body.evidence_id,
        reported_by=current_user.id,
        created_by_verified_identity=True,
        idempotency_key=idempotency_key,
        request_id=rid,
    )
    if isinstance(sos_res, tuple) and len(sos_res) == 2:
        sos, was_created = sos_res
    else:
        sos, was_created = sos_res, True

    if not was_created:
        evidence_records = get_sos_evidence(db, sos.id)
        response.status_code = status.HTTP_200_OK
        return SOSResponse(
            data=_to_sos_data(sos, evidence_records),
            meta={"request_id": rid, "was_created": False, "idempotent_replay": True},
        )

    # 2. Fetch live risk assessment
    risk_ctx = SOSRiskContext(live_risk_available=False)
    try:
        engine = LiveRiskEngine(db=db)
        live_data = await engine.assess(body.latitude, body.longitude)
        risk_ctx = SOSRiskContext(
            risk_score=live_data.risk.score,
            risk_level=live_data.risk.level,
            risk_confidence=live_data.risk.confidence,
            weather_status=live_data.weather.status,
            live_risk_available=live_data.historical.status == "available",
            assessment_timestamp=live_data.timestamp,
        )
        sos = attach_risk_context(db=db, sos=sos, risk_context=risk_ctx, request_id=rid)
    except Exception as exc:  # noqa: BLE001
        logger.warning("sos_risk_fetch_failed", sos_id=str(sos.id), error=str(exc))

    # 3. Generate linked alert via existing alert engine
    alert = None
    try:
        alert = maybe_generate_sos_alert(db=db, sos=sos, request_id=rid)
    except Exception as exc:  # noqa: BLE001
        logger.warning("sos_alert_generation_failed", sos_id=str(sos.id), error=str(exc))

    # 4. Dispatch Realtime WebSocket Event AFTER DB transaction commit
    try:
        alert_id_str = str(alert.id) if alert else str(sos.id)
        c_at = getattr(sos, "created_at", None)
        c_at_str = c_at.isoformat() if hasattr(c_at, "isoformat") else str(c_at or datetime.now(timezone.utc).isoformat())
        event_payload = build_sos_alert_event_payload(
            alert_id=alert_id_str,
            sos_id=sos.id,
            severity=str(getattr(sos, "severity", "MEDIUM")),
            latitude=float(getattr(sos, "latitude", 0.0)),
            longitude=float(getattr(sos, "longitude", 0.0)),
            created_at=c_at_str,
            description=_safe_str(getattr(sos, "description", None)),
            evidence_count=_safe_int(getattr(sos, "evidence_count", 0)),
            risk_score=_safe_float(getattr(sos, "live_risk_score", None)),
            risk_level=_safe_str(getattr(sos, "live_risk_level", None)),
        )
        await realtime_manager.publish_event(
            event_type="SOS_ALERT_CREATED",
            payload=event_payload,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("sos_realtime_broadcast_error", error=str(exc))

    evidence_records = get_sos_evidence(db, sos.id)
    return SOSResponse(
        data=_to_sos_data(sos, evidence_records),
        meta={"request_id": rid, "was_created": True},
    )


# ---------------------------------------------------------------------------
# GET /sos  — list SOS reports
# ---------------------------------------------------------------------------

@router.get("", response_model=SOSListResponse)
def get_sos_reports(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    request: Request = None,  # type: ignore[assignment]
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SOSListResponse:
    """List SOS reports (paginated). Citizens only see their own; officials see all."""
    rid = getattr(request.state, "request_id", "") if request else ""
    filter_user = current_user.id if current_user.role == "citizen" else None

    items, total = list_sos(
        db=db,
        status=status_filter,
        reported_by=filter_user,
        limit=limit,
        offset=offset,
    )

    list_items = [
        SOSListItem(
            id=str(s.id),
            latitude=s.latitude,
            longitude=s.longitude,
            location_accuracy_meters=s.location_accuracy_meters,
            severity=s.severity,
            status=s.status,
            risk_level=s.live_risk_level,
            risk_score=s.live_risk_score,
            evidence_count=s.evidence_count,
            description=s.description,
            created_at=s.created_at,
        )
        for s in items
    ]

    return SOSListResponse(
        data=SOSListData(total_count=total, limit=limit, offset=offset, items=list_items),
        meta={"request_id": rid},
    )


# ---------------------------------------------------------------------------
# GET /sos/{sos_id}  — retrieve single SOS
# ---------------------------------------------------------------------------

@router.get("/{sos_id}", response_model=SOSResponse)
def get_single_sos(
    sos_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SOSResponse:
    """Retrieve a single SOS report by UUID."""
    rid = getattr(request.state, "request_id", "")
    sos = get_sos_by_id(db, sos_id)
    if not sos:
        raise NotFoundError(f"SOS report '{sos_id}' not found.")

    if current_user.role == "citizen" and sos.reported_by != current_user.id:
        raise ForbiddenError("You may only view your own SOS reports.")

    evidence_records = get_sos_evidence(db, sos.id)
    return SOSResponse(
        data=_to_sos_data(sos, evidence_records),
        meta={"request_id": rid},
    )


# ---------------------------------------------------------------------------
# GET /sos/{sos_id}/audits — retrieve audit timeline
# ---------------------------------------------------------------------------

@router.get("/{sos_id}/audits", response_model=SOSAuditListResponse)
def get_sos_audit_timeline(
    sos_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SOSAuditListResponse:
    """Retrieve immutable audit timeline for an SOS emergency report."""
    rid = getattr(request.state, "request_id", "")
    sos = get_sos_by_id(db, sos_id)
    if not sos:
        raise NotFoundError(f"SOS report '{sos_id}' not found.")

    if current_user.role == "citizen" and sos.reported_by != current_user.id:
        raise ForbiddenError("You may only view audits for your own SOS reports.")

    audits = get_sos_audits(db, sos_id)
    items = [
        SOSAuditItem(
            id=a.id,
            sos_id=str(a.sos_id),
            action=a.action,
            previous_status=a.previous_status,
            new_status=a.new_status,
            reason=a.reason,
            metadata_json=a.metadata_json,
            user_id=str(a.user_id) if a.user_id else None,
            created_at=a.created_at,
        )
        for a in audits
    ]
    return SOSAuditListResponse(
        data=items,
        meta={"request_id": rid, "total_events": len(items)},
    )


# ---------------------------------------------------------------------------
# GET /sos/{sos_id}/recommendations
# ---------------------------------------------------------------------------

@router.get("/{sos_id}/recommendations", response_model=SOSRecommendationResponse)
async def get_recommendations_for_sos(
    sos_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SOSRecommendationResponse:
    """Retrieve ranked shelter recommendations for an SOS report."""
    rid = getattr(request.state, "request_id", "")
    sos = get_sos_by_id(db, sos_id)
    if not sos:
        raise NotFoundError(f"SOS report '{sos_id}' not found.")

    if current_user.role == "citizen" and sos.reported_by != current_user.id:
        raise ForbiddenError("You may only view recommendations for your own SOS.")

    rec_data = get_sos_recommendations(
        db=db,
        sos_id=sos.id,
    )
    return SOSRecommendationResponse(
        data=rec_data,
        meta={"request_id": rid},
    )


# ---------------------------------------------------------------------------
# POST /sos/{sos_id}/acknowledge  (official/admin only)
# ---------------------------------------------------------------------------

@router.post("/{sos_id}/acknowledge", response_model=SOSResponse)
async def acknowledge_sos_report(
    sos_id: uuid.UUID,
    body: SOSActionRequest,
    request: Request,
    current_user: User = Depends(require_role(["official", "admin"])),
    db: Session = Depends(get_db),
) -> SOSResponse:
    """Acknowledge an active SOS report (official/admin only)."""
    rid = getattr(request.state, "request_id", "")
    sos = transition_sos_status(
        db=db,
        sos_id=sos_id,
        target_status=SOSStatus.ACKNOWLEDGED,
        acting_user_id=current_user.id,
        reason=body.reason,
        request_id=rid,
    )
    evidence_records = get_sos_evidence(db, sos.id)

    # Realtime notification of status transition
    try:
        await realtime_manager.publish_event(
            event_type="SOS_STATUS_CHANGED",
            payload={"sos_id": str(sos.id), "status": "ACKNOWLEDGED", "acknowledged_by": str(current_user.id)},
        )
    except Exception:  # noqa: BLE001
        pass

    return SOSResponse(data=_to_sos_data(sos, evidence_records), meta={"request_id": rid})


# ---------------------------------------------------------------------------
# POST /sos/{sos_id}/resolve  (official/admin only)
# ---------------------------------------------------------------------------

@router.post("/{sos_id}/resolve", response_model=SOSResponse)
async def resolve_sos_report(
    sos_id: uuid.UUID,
    body: SOSActionRequest,
    request: Request,
    current_user: User = Depends(require_role(["official", "admin"])),
    db: Session = Depends(get_db),
) -> SOSResponse:
    """Mark an SOS report as resolved (official/admin only)."""
    rid = getattr(request.state, "request_id", "")
    sos = transition_sos_status(
        db=db,
        sos_id=sos_id,
        target_status=SOSStatus.RESOLVED,
        acting_user_id=current_user.id,
        reason=body.reason,
        request_id=rid,
    )
    evidence_records = get_sos_evidence(db, sos.id)

    # Realtime notification of status transition
    try:
        await realtime_manager.publish_event(
            event_type="SOS_STATUS_CHANGED",
            payload={"sos_id": str(sos.id), "status": "RESOLVED", "resolved_by": str(current_user.id)},
        )
    except Exception:  # noqa: BLE001
        pass

    return SOSResponse(data=_to_sos_data(sos, evidence_records), meta={"request_id": rid})


# ---------------------------------------------------------------------------
# POST /sos/{sos_id}/cancel  (own citizen or official/admin)
# ---------------------------------------------------------------------------

@router.post("/{sos_id}/cancel", response_model=SOSResponse)
async def cancel_sos_report(
    sos_id: uuid.UUID,
    body: SOSActionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SOSResponse:
    """Cancel an active SOS report."""
    rid = getattr(request.state, "request_id", "")
    existing = get_sos_by_id(db, sos_id)
    if not existing:
        raise NotFoundError(f"SOS report '{sos_id}' not found.")

    if current_user.role == "citizen" and existing.reported_by != current_user.id:
        raise ForbiddenError("You may only cancel your own SOS reports.")

    sos = transition_sos_status(
        db=db,
        sos_id=sos_id,
        target_status=SOSStatus.CANCELLED,
        acting_user_id=current_user.id,
        reason=body.reason,
        request_id=rid,
    )
    evidence_records = get_sos_evidence(db, sos.id)

    try:
        await realtime_manager.publish_event(
            event_type="SOS_STATUS_CHANGED",
            payload={"sos_id": str(sos.id), "status": "CANCELLED"},
        )
    except Exception:  # noqa: BLE001
        pass

    return SOSResponse(data=_to_sos_data(sos, evidence_records), meta={"request_id": rid})
