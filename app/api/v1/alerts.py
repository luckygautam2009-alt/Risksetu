"""
Operational Alert Generation & Explainable Decision Support API endpoints.
"""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
import structlog

from app.core.errors import NotFoundError
from app.core.rate_limit import check_rate_limit
from app.core.security import decode_token
from app.db.session import get_db
from app.models.alert import Alert
from app.models.user import User
from app.schemas.alert import (
    AlertActionRequest,
    AlertData,
    AlertGenerateRequest,
    AlertListItem,
    AlertListData,
    AlertListResponse,
    AlertResponse,
)
from app.services.alerts.constants import AlertSeverity, AlertStatus, AlertType
from app.services.alerts.engine import (
    generate_operational_alert,
    get_alert_by_id,
    list_alerts,
)
from app.services.alerts.lifecycle import transition_alert_status
from app.services.alerts.realtime import realtime_manager
from app.services.auth.dependencies import get_current_user, require_role

logger = structlog.get_logger("risksetu.alerts_api")

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _to_alert_data(alert: Alert) -> AlertData:
    """Helper to convert Alert ORM model to AlertData Pydantic schema."""
    return AlertData(
        id=str(alert.id),
        alert_type=AlertType(alert.alert_type),
        severity=AlertSeverity(alert.severity),
        status=AlertStatus(alert.status),
        title=alert.title,
        message=alert.message,
        latitude=alert.latitude,
        longitude=alert.longitude,
        risk_score=alert.risk_score,
        risk_level=alert.risk_level,
        risk_confidence=alert.risk_confidence,
        isolation_severity=alert.isolation_severity,
        priority_score=alert.priority_score,
        priority_level=alert.priority_level,
        ground_intelligence_summary=alert.ground_intelligence_summary,
        fingerprint=alert.fingerprint,
        source_reference=alert.source_reference,
        recommended_actions=alert.recommended_actions or [],
        explanation=alert.explanation or {},
        data_freshness=alert.data_freshness or {},
        acknowledged_at=alert.acknowledged_at,
        acknowledged_by=str(alert.acknowledged_by) if alert.acknowledged_by else None,
        resolved_at=alert.resolved_at,
        resolved_by=str(alert.resolved_by) if alert.resolved_by else None,
        calculation_version=alert.calculation_version,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    )


def _to_alert_list_item(alert: Alert) -> AlertListItem:
    """Helper to convert Alert ORM model to AlertListItem schema."""
    return AlertListItem(
        id=str(alert.id),
        alert_type=AlertType(alert.alert_type),
        severity=AlertSeverity(alert.severity),
        status=AlertStatus(alert.status),
        title=alert.title,
        latitude=alert.latitude,
        longitude=alert.longitude,
        risk_score=alert.risk_score,
        priority_score=alert.priority_score,
        isolation_severity=alert.isolation_severity,
        created_at=alert.created_at,
    )


@router.post(
    "/generate",
    response_model=AlertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate operational alert from multi-phase intelligence",
)
async def generate_alert(
    request_body: AlertGenerateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertResponse:
    """
    Evaluates trigger criteria against pre-computed outputs from Phases 2A/2B/2C/3
    and generates an idempotent, deduplicated alert with recommended actions.
    """
    rid = getattr(request.state, "request_id", "")

    # Rate limit check (60 per minute per user)
    check_rate_limit(
        user_id=str(current_user.id),
        key_prefix="alerts_generate",
        limit=60,
        window_seconds=60,
    )

    alert, was_created = generate_operational_alert(
        db=db,
        latitude=request_body.latitude,
        longitude=request_body.longitude,
        risk_score=request_body.risk_score,
        risk_level=request_body.risk_level,
        risk_confidence=request_body.risk_confidence,
        isolation_severity=request_body.isolation_severity,
        priority_score=request_body.priority_score,
        priority_level=request_body.priority_level,
        ground_intelligence_summary=request_body.ground_intelligence_summary,
        source_reference=request_body.source_reference,
        data_freshness=request_body.data_freshness,
        created_by_user_id=current_user.id,
    )

    return AlertResponse(
        data=_to_alert_data(alert),
        meta={"request_id": rid, "was_created": was_created, "fingerprint": alert.fingerprint},
    )


@router.get(
    "",
    response_model=AlertListResponse,
    summary="Query paginated operational alerts with filters",
)
async def get_alerts(
    status_filter: str | None = Query(None, alias="status", description="Filter by status (ACTIVE, ACKNOWLEDGED, RESOLVED, DISMISSED)"),
    severity_filter: str | None = Query(None, alias="severity", description="Filter by severity (CRITICAL, HIGH, WARNING, INFO)"),
    alert_type: str | None = Query(None, description="Filter by alert type"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    request: Request = None,  # type: ignore[assignment]
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertListResponse:
    """Lists operational alerts with flexible filtering and pagination."""
    rid = getattr(request.state, "request_id", "") if request else ""
    alerts, total_count = list_alerts(
        db=db,
        status=status_filter,
        severity=severity_filter,
        alert_type=alert_type,
        limit=limit,
        offset=offset,
    )

    return AlertListResponse(
        data=AlertListData(
            total_count=total_count,
            limit=limit,
            offset=offset,
            alerts=[_to_alert_list_item(a) for a in alerts],
        ),
        meta={"request_id": rid},
    )


@router.get(
    "/{alert_id}",
    response_model=AlertResponse,
    summary="Retrieve single alert with full explainability & actions",
)
async def get_alert(
    alert_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertResponse:
    """Retrieves full details, explainability breakdown, and recommended actions for a specific alert."""
    rid = getattr(request.state, "request_id", "")
    alert = get_alert_by_id(db, alert_id)
    if not alert:
        raise NotFoundError(f"Alert with id '{alert_id}' not found")

    return AlertResponse(
        data=_to_alert_data(alert),
        meta={"request_id": rid},
    )


@router.post(
    "/{alert_id}/acknowledge",
    response_model=AlertResponse,
    summary="Acknowledge an active alert (Official/Admin only)",
)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    request_body: AlertActionRequest,
    request: Request,
    current_user: User = Depends(require_role(["official", "admin"])),
    db: Session = Depends(get_db),
) -> AlertResponse:
    """Acknowledges an active alert, establishing operational ownership and audit trail."""
    rid = getattr(request.state, "request_id", "")
    alert = transition_alert_status(
        db=db,
        alert_id=alert_id,
        target_status=AlertStatus.ACKNOWLEDGED,
        user_id=current_user.id,
        reason=request_body.reason,
    )
    return AlertResponse(
        data=_to_alert_data(alert),
        meta={"request_id": rid, "action": "ACKNOWLEDGED"},
    )


@router.post(
    "/{alert_id}/resolve",
    response_model=AlertResponse,
    summary="Resolve an alert (Official/Admin only)",
)
async def resolve_alert(
    alert_id: uuid.UUID,
    request_body: AlertActionRequest,
    request: Request,
    current_user: User = Depends(require_role(["official", "admin"])),
    db: Session = Depends(get_db),
) -> AlertResponse:
    """Marks an alert as resolved after operational intervention has been verified."""
    rid = getattr(request.state, "request_id", "")
    alert = transition_alert_status(
        db=db,
        alert_id=alert_id,
        target_status=AlertStatus.RESOLVED,
        user_id=current_user.id,
        reason=request_body.reason,
    )
    return AlertResponse(
        data=_to_alert_data(alert),
        meta={"request_id": rid, "action": "RESOLVED"},
    )


@router.post(
    "/{alert_id}/dismiss",
    response_model=AlertResponse,
    summary="Dismiss an alert (Official/Admin only)",
)
async def dismiss_alert(
    alert_id: uuid.UUID,
    request_body: AlertActionRequest,
    request: Request,
    current_user: User = Depends(require_role(["official", "admin"])),
    db: Session = Depends(get_db),
) -> AlertResponse:
    """Dismisses an alert with mandatory operational justification recorded in audit log."""
    rid = getattr(request.state, "request_id", "")
    alert = transition_alert_status(
        db=db,
        alert_id=alert_id,
        target_status=AlertStatus.DISMISSED,
        user_id=current_user.id,
        reason=request_body.reason,
    )
    return AlertResponse(
        data=_to_alert_data(alert),
        meta={"request_id": rid, "action": "DISMISSED"},
    )


# ---------------------------------------------------------------------------
# WebSocket /alerts/ws — Real-time Emergency Broadcast Stream
# ---------------------------------------------------------------------------

@router.websocket("/ws")
async def alerts_websocket_endpoint(
    websocket: WebSocket,
    token: str | None = Query(None),
) -> None:
    """Authenticated real-time WebSocket stream for emergency alerts and SOS events.

    Clients must pass JWT token via query parameter (?token=...).
    Maintains heartbeat and delivers events upon authoritative backend DB commit.
    """
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_token(token)
        user_id_str = payload.get("sub")
        role = payload.get("role", "citizen")
        if not user_id_str:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        user_uuid = uuid.UUID(user_id_str)
    except Exception as exc:  # noqa: BLE001
        logger.warning("websocket_auth_failed", error=str(exc))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await realtime_manager.connect(websocket, user_id=user_uuid, role=role)

    try:
        while True:
            raw_msg = await websocket.receive_text()
            # Handle heartbeat ping/pong
            try:
                msg_data = json.loads(raw_msg)
                if isinstance(msg_data, dict) and msg_data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except Exception:  # noqa: BLE001
                pass
    except WebSocketDisconnect:
        realtime_manager.disconnect(websocket)
    except Exception as exc:  # noqa: BLE001
        logger.info("websocket_connection_closed", error=str(exc))
        realtime_manager.disconnect(websocket)
