"""
Photographic Evidence API endpoints.

Protected by authoritative verified identity enforcement:
Unverified users cannot upload incident evidence.
"""
from __future__ import annotations

import datetime
from typing import Any
import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from sqlalchemy.orm import Session
import structlog

from app.core.errors import ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models.user import User
from app.services.auth.dependencies import get_current_user
from app.services.evidence.service import EvidenceService
from app.services.identity.dependencies import require_verified_identity

logger = structlog.get_logger("risksetu.evidence.api")
router = APIRouter(prefix="/evidence", tags=["evidence"])

_evidence_service = EvidenceService()


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload trusted photographic incident evidence (Verified identity required)",
)
async def upload_evidence(
    request: Request,
    file: UploadFile = File(...),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    captured_at: str | None = Form(None),
    current_user: User = Depends(require_verified_identity),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Upload photographic evidence.

    Authoritatively enforces that citizen identity is verified before
    accepting binary file payload.
    """
    rid = getattr(request.state, "request_id", "")
    content_bytes = await file.read()

    cap_dt: datetime.datetime | None = None
    if captured_at:
        try:
            cap_dt = datetime.datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        except ValueError:
            cap_dt = None

    evidence = _evidence_service.store_evidence(
        db=db,
        owner=current_user,
        file_bytes=content_bytes,
        original_filename=file.filename or "evidence.jpg",
        declared_content_type=file.content_type or "image/jpeg",
        latitude=latitude,
        longitude=longitude,
        captured_at=cap_dt,
    )

    return {
        "data": {
            "evidence_id": str(evidence.id),
            "owner_user_id": str(evidence.owner_user_id),
            "content_type": evidence.content_type,
            "size_bytes": evidence.size_bytes,
            "sha256": evidence.sha256,
            "captured_at": evidence.captured_at.isoformat() if evidence.captured_at else None,
            "latitude": evidence.latitude,
            "longitude": evidence.longitude,
            "upload_status": evidence.upload_status,
            "created_at": evidence.created_at.isoformat(),
        },
        "meta": {"request_id": rid, "verified_provenance": True},
    }


@router.get(
    "/{evidence_id}",
    summary="Retrieve evidence metadata",
)
async def get_evidence_metadata(
    evidence_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve metadata for an uploaded photographic evidence record."""
    rid = getattr(request.state, "request_id", "")
    evidence = _evidence_service.get_evidence(db, evidence_id)
    if not evidence:
        raise NotFoundError(f"Evidence '{evidence_id}' not found.")

    if current_user.role == "citizen" and evidence.owner_user_id != current_user.id:
        raise ForbiddenError("You may only view metadata for your own uploaded evidence.")

    return {
        "data": {
            "evidence_id": str(evidence.id),
            "owner_user_id": str(evidence.owner_user_id),
            "content_type": evidence.content_type,
            "size_bytes": evidence.size_bytes,
            "sha256": evidence.sha256,
            "captured_at": evidence.captured_at.isoformat() if evidence.captured_at else None,
            "latitude": evidence.latitude,
            "longitude": evidence.longitude,
            "upload_status": evidence.upload_status,
            "created_at": evidence.created_at.isoformat(),
        },
        "meta": {"request_id": rid},
    }
