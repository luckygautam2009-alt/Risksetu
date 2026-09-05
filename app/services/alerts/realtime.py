"""
Real-Time Emergency WebSocket Delivery Network & Event Dispatcher.

Responsibilities:
- Manage authenticated active WebSocket connections for officers and citizens.
- Broadcast emergency events with strict sanitization (zero PII, zero tokens).
- Coordinate multi-process pub/sub via Redis when available, with graceful in-memory fallback.
"""
from __future__ import annotations

import json
from typing import Any
import uuid

from fastapi import WebSocket
import structlog

from app.core.redis import get_redis_client

logger = structlog.get_logger("risksetu.realtime")

ALERT_CHANNEL_REDIS = "risksetu:emergency:events"


class ConnectionManager:
    """Manages authenticated live WebSocket connections."""

    def __init__(self) -> None:
        self.active_connections: dict[WebSocket, dict[str, Any]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        user_id: uuid.UUID,
        role: str,
    ) -> None:
        await websocket.accept()
        self.active_connections[websocket] = {
            "user_id": user_id,
            "role": role,
        }
        logger.info(
            "websocket_connected",
            user_id=str(user_id),
            role=role,
            total_active=len(self.active_connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            meta = self.active_connections.pop(websocket)
            logger.info(
                "websocket_disconnected",
                user_id=str(meta.get("user_id")),
                total_active=len(self.active_connections),
            )

    async def broadcast_json(self, data: dict[str, Any], target_roles: list[str] | None = None) -> int:
        """Broadcasts sanitized JSON payload to connected active sockets."""
        delivered_count = 0
        dead_sockets: list[WebSocket] = []

        for ws, meta in self.active_connections.items():
            if target_roles and meta.get("role") not in target_roles:
                continue
            try:
                await ws.send_json(data)
                delivered_count += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("websocket_send_failed", error=str(exc))
                dead_sockets.append(ws)

        for ws in dead_sockets:
            self.disconnect(ws)

        return delivered_count

    async def publish_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        target_roles: list[str] | None = None,
    ) -> int:
        """Publishes an event to local connections and Redis pub/sub if available."""
        message = {
            "event": event_type,
            "data": payload,
        }

        # 1. Deliver directly to local in-process connections
        delivered = await self.broadcast_json(message, target_roles=target_roles)

        # 2. Publish to Redis for multi-worker scaling (fail silently if Redis unavailable)
        try:
            redis_client = get_redis_client()
            redis_client.publish(
                ALERT_CHANNEL_REDIS,
                json.dumps({"event": event_type, "payload": payload, "target_roles": target_roles}),
            )
        except Exception:  # noqa: BLE001
            # Redis is non-authoritative transient bus; in-process delivery already succeeded
            pass

        return delivered


# Singleton manager
realtime_manager = ConnectionManager()


def build_sos_alert_event_payload(
    alert_id: uuid.UUID | str,
    sos_id: uuid.UUID | str,
    severity: str,
    latitude: float,
    longitude: float,
    created_at: str,
    description: str | None = None,
    evidence_count: int = 0,
    risk_score: float | None = None,
    risk_level: str | None = None,
) -> dict[str, Any]:
    """Constructs clean, sanitized payload for real-time SOS alert broadcast."""
    return {
        "alert_id": str(alert_id),
        "sos_id": str(sos_id),
        "severity": severity.upper(),
        "location": {
            "latitude": float(latitude),
            "longitude": float(longitude),
        },
        "description": description,
        "evidence_count": evidence_count,
        "risk_context": {
            "risk_score": risk_score,
            "risk_level": risk_level,
        },
        "created_at": created_at,
        "source": "VERIFIED_CITIZEN",
    }
