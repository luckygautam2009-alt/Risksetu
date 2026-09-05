"""
Ground Intelligence & Trust-Weighted Reporting API endpoints.
"""
from __future__ import annotations

import datetime
from typing import Any
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, status
import redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session
import structlog

from app.core.errors import IdentityVerificationRequiredError, NotFoundError
from app.core.rate_limit import check_rate_limit
from app.core.redis import get_redis_client
from app.db.session import get_db
from app.models.evidence import IncidentEvidence
from app.models.ground_report import GroundReport, GroundReportAudit
from app.models.user import User
from app.services.identity.service import IdentityService

from app.schemas.ground_report import (
    GroundReportCreateRequest,
    GroundReportData,
    GroundReportListItem,
    GroundReportListData,
    GroundReportListResponse,
    GroundReportResponse,
    GroundReportStatusUpdateRequest,
    ReportStatus,
    ReportType,
    TrustBreakdown,
    TrustClass,
    TrustComponents,
    TrustRecalculateResponse,
)
from app.services.auth.dependencies import get_current_user, require_role
from app.services.ground_intelligence.constants import (
    CALCULATION_VERSION,
    DEFAULT_USER_RATE_LIMIT_PER_MINUTE,
    STANDARD_GROUND_INTELLIGENCE_LIMITATIONS,
    WEIGHT_CORROBORATION,
    WEIGHT_GEO,
    WEIGHT_TEMPORAL,
    WEIGHT_USER,
)
from app.services.ground_intelligence.eligibility import RiskEligibilityEvaluator
from app.services.ground_intelligence.engine import GroundIntelligenceEngine
from app.services.ground_intelligence.explanation import GroundIntelligenceExplanationGenerator
from app.services.ground_intelligence.trust import TrustScoreResult

logger = structlog.get_logger("risksetu.ground_reports_api")
_identity_service = IdentityService()

router = APIRouter(prefix="/ground-reports", tags=["ground-reports"])


def _to_report_data(report: GroundReport) -> GroundReportData:
    """Helper to convert GroundReport ORM model into schema response."""
    audit_meta = report.audit_metadata or {}
    trust_res = TrustScoreResult(
        trust_score=report.trust_score,
        geo_plausibility=report.geo_plausibility_score,
        temporal_freshness=report.temporal_freshness_score,
        user_reliability=report.user_reliability_score,
        corroboration=report.corroboration_score,
        geo_contribution=round(WEIGHT_GEO * report.geo_plausibility_score, 2),
        temporal_contribution=round(WEIGHT_TEMPORAL * report.temporal_freshness_score, 2),
        user_contribution=round(WEIGHT_USER * report.user_reliability_score, 2),
        corroboration_contribution=round(WEIGHT_CORROBORATION * report.corroboration_score, 2),
    )
    trust_class = TrustClass(report.trust_class)
    corrob_count = len(audit_meta.get("corroborating_report_ids", []))
    disqualifications = audit_meta.get("disqualifications", [])

    explanation = GroundIntelligenceExplanationGenerator.generate_explanation(
        trust_result=trust_res,
        trust_class=trust_class,
        is_duplicate=report.is_duplicate,
        duplicate_match_reason=audit_meta.get("duplicate_match_reason"),
        corroborating_count=corrob_count,
        risk_influence_eligible=report.risk_influence_eligible,
        eligibility_reasons=disqualifications,
    )

    return GroundReportData(
        report_id=str(report.id),
        user_id=str(report.user_id),
        report_type=ReportType(report.report_type),
        description=report.description,
        latitude=report.latitude,
        longitude=report.longitude,
        observed_at=report.observed_at,
        status=ReportStatus(report.status),
        trust=TrustBreakdown(
            trust_score=report.trust_score,
            trust_class=trust_class,
            components=TrustComponents(
                geo_plausibility=report.geo_plausibility_score,
                temporal_freshness=report.temporal_freshness_score,
                user_reliability=report.user_reliability_score,
                corroboration=report.corroboration_score,
            ),
            weights={
                "geo": WEIGHT_GEO,
                "temporal": WEIGHT_TEMPORAL,
                "user": WEIGHT_USER,
                "corroboration": WEIGHT_CORROBORATION,
            },
            calculation_version=CALCULATION_VERSION,
        ),
        is_duplicate=report.is_duplicate,
        duplicate_of_id=str(report.duplicate_of_id) if report.duplicate_of_id else None,
        duplicate_group_id=report.duplicate_group_id,
        risk_influence_eligible=report.risk_influence_eligible,
        explanation=explanation,
        limitations=STANDARD_GROUND_INTELLIGENCE_LIMITATIONS,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.post(
    "",
    response_model=GroundReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a field observation ground report",
)
async def create_ground_report(
    request_body: GroundReportCreateRequest,
    request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroundReportResponse:
    """Submit a field observation with authenticated provenance and deterministic trust scoring."""
    rid = getattr(request.state, "request_id", "")

    # 1. Enforce Per-User Rate Limiting (Redis)
    check_rate_limit(
        user_id=str(current_user.id),
        key_prefix="ground_reports",
        limit=DEFAULT_USER_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
    )

    # 2. Check Idempotency Key — Redis first, DB fallback
    redis_client = get_redis_client()
    idempotency_redis_key = f"idempotency:report:{current_user.id}:{idempotency_key}" if idempotency_key else None

    if idempotency_key:
        # 2a. Try Redis cache (fast path)
        redis_hit = False
        try:
            cached_id = redis_client.get(idempotency_redis_key)  # type: ignore[arg-type]
            if cached_id:
                cached_id_str = cached_id.decode() if isinstance(cached_id, (bytes, bytearray)) else str(cached_id)
                report_uuid = uuid.UUID(cached_id_str)
                cached_report = db.execute(select(GroundReport).where(GroundReport.id == report_uuid)).scalar_one_or_none()
                if cached_report:
                    logger.info("idempotent_report_replay", report_id=str(report_uuid), key=idempotency_key, source="redis")
                    replay_meta = {"request_id": rid, "idempotency_key": idempotency_key, "idempotent_replay": True}
                    return GroundReportResponse(data=_to_report_data(cached_report), meta=replay_meta)
                redis_hit = True
        except (redis.RedisError, TimeoutError, OSError) as exc:
            logger.warning("idempotency_cache_read_failed", error=str(exc))

        # 2b. DB-level fallback when Redis is unavailable or no cache hit
        if not redis_hit:
            db_cached = db.execute(
                select(GroundReport).where(
                    GroundReport.user_id == current_user.id,
                    GroundReport.idempotency_key == idempotency_key,
                )
            ).scalar_one_or_none()
            if db_cached:
                logger.info("idempotent_report_replay", report_id=str(db_cached.id), key=idempotency_key, source="db")
                replay_meta = {"request_id": rid, "idempotency_key": idempotency_key, "idempotent_replay": True}
                return GroundReportResponse(data=_to_report_data(db_cached), meta=replay_meta)

    # 3. Enforce Verified Identity if photographic evidence is attached
    if request_body.evidence_id:
        if not _identity_service.is_user_verified(db=db, user_id=current_user.id):
            raise IdentityVerificationRequiredError(
                "Identity verification is required before submitting photographic emergency evidence."
            )

    # 4. Process report via Ground Intelligence Coordinator
    engine = GroundIntelligenceEngine(db=db)
    report_data = engine.submit_report(
        request=request_body,
        user_id=current_user.id,
        user_role=current_user.role,
        idempotency_key=idempotency_key,
    )

    # 5. Link evidence to report
    if request_body.evidence_id:
        evidence = db.get(IncidentEvidence, request_body.evidence_id)
        if evidence and evidence.owner_user_id == current_user.id:
            evidence.incident_id = uuid.UUID(report_data.report_id)
            db.commit()

    # 6. Cache idempotency key in Redis (24-hour TTL) — best-effort
    if idempotency_redis_key:
        try:
            redis_client.setex(idempotency_redis_key, 86400, report_data.report_id)  # type: ignore[arg-type]
        except (redis.RedisError, TimeoutError, OSError) as exc:
            logger.warning("idempotency_cache_write_failed", error=str(exc))

    meta: dict[str, Any] = {"request_id": rid}
    if idempotency_key:
        meta["idempotency_key"] = idempotency_key

    return GroundReportResponse(data=report_data, meta=meta)


@router.get(
    "/{report_id}",
    response_model=GroundReportResponse,
    summary="Get single ground report by ID",
)
async def get_ground_report(
    report_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroundReportResponse:
    """Retrieve ground report and its full trust evaluation breakdown."""
    rid = getattr(request.state, "request_id", "")
    report = db.execute(select(GroundReport).where(GroundReport.id == report_id)).scalar_one_or_none()
    if not report:
        raise NotFoundError(f"Ground report with ID '{report_id}' not found.")

    return GroundReportResponse(data=_to_report_data(report), meta={"request_id": rid})


@router.get(
    "",
    response_model=GroundReportListResponse,
    summary="Get paginated list of ground reports with filtering",
)
async def list_ground_reports(
    request: Request,
    report_type: ReportType | None = Query(None, description="Filter by observation category"),
    status_filter: ReportStatus | None = Query(None, alias="status", description="Filter by status"),
    trust_class: TrustClass | None = Query(None, description="Filter by trust category tier"),
    risk_influence_eligible: bool | None = Query(None, description="Filter by risk influence eligibility"),
    start_date: datetime.datetime | None = Query(None, description="Filter observations on or after this timestamp"),
    end_date: datetime.datetime | None = Query(None, description="Filter observations on or before this timestamp"),
    limit: int = Query(20, ge=1, le=100, description="Page limit (max 100)"),
    offset: int = Query(0, ge=0, description="Page offset"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroundReportListResponse:
    """List ground reports with safe parameterized filtering and bounded pagination."""
    rid = getattr(request.state, "request_id", "")

    query = select(GroundReport)

    if report_type is not None:
        query = query.where(GroundReport.report_type == report_type.value)
    if status_filter is not None:
        query = query.where(GroundReport.status == status_filter.value)
    if trust_class is not None:
        query = query.where(GroundReport.trust_class == trust_class.value)
    if risk_influence_eligible is not None:
        query = query.where(GroundReport.risk_influence_eligible.is_(risk_influence_eligible))
    if start_date is not None:
        query = query.where(GroundReport.observed_at >= start_date)
    if end_date is not None:
        query = query.where(GroundReport.observed_at <= end_date)

    # Count total matching records
    count_query = select(func.count()).select_from(query.subquery())
    total_count = db.execute(count_query).scalar() or 0

    # Paginate
    paged_query = query.order_by(GroundReport.observed_at.desc()).limit(limit).offset(offset)
    records = db.execute(paged_query).scalars().all()

    items = [
        GroundReportListItem(
            report_id=str(r.id),
            user_id=str(r.user_id),
            report_type=ReportType(r.report_type),
            latitude=r.latitude,
            longitude=r.longitude,
            observed_at=r.observed_at,
            status=ReportStatus(r.status),
            trust_score=r.trust_score,
            trust_class=TrustClass(r.trust_class),
            is_duplicate=r.is_duplicate,
            risk_influence_eligible=r.risk_influence_eligible,
            created_at=r.created_at,
        )
        for r in records
    ]

    return GroundReportListResponse(
        data=GroundReportListData(
            total_count=total_count,
            limit=limit,
            offset=offset,
            reports=items,
        ),
        meta={"request_id": rid},
    )


@router.post(
    "/{report_id}/recalculate-trust",
    response_model=TrustRecalculateResponse,
    summary="Recalculate trust score for an existing ground report",
)
async def recalculate_report_trust(
    report_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrustRecalculateResponse:
    """Idempotently re-evaluate trust score and multi-observer corroboration for an observation."""
    rid = getattr(request.state, "request_id", "")
    engine = GroundIntelligenceEngine(db=db)
    recalculated_data = engine.recalculate_trust(report_id)

    logger.info("report_trust_recalculated", report_id=str(report_id), user_id=str(current_user.id))
    return TrustRecalculateResponse(data=recalculated_data, meta={"request_id": rid})


@router.patch(
    "/{report_id}/status",
    response_model=GroundReportResponse,
    summary="Moderate ground report status (Officials/Admins only)",
)
async def update_report_status(
    report_id: uuid.UUID,
    update_req: GroundReportStatusUpdateRequest,
    request: Request,
    current_user: User = Depends(require_role(["official", "admin"])),
    db: Session = Depends(get_db),
) -> GroundReportResponse:
    """Update report lifecycle status (ACCEPTED, REJECTED, REVIEW_REQUIRED) with audit trail."""
    rid = getattr(request.state, "request_id", "")
    report = db.execute(select(GroundReport).where(GroundReport.id == report_id)).scalar_one_or_none()
    if not report:
        raise NotFoundError(f"Ground report with ID '{report_id}' not found.")

    prev_status = report.status
    report.status = update_req.status.value

    # Re-evaluate risk eligibility based on status transition
    eligible, disqualifications = RiskEligibilityEvaluator.is_eligible(
        trust_score=report.trust_score,
        is_duplicate=report.is_duplicate,
        status=report.status,
        observed_at=report.observed_at,
        geo_plausibility_score=report.geo_plausibility_score,
    )
    report.risk_influence_eligible = eligible

    # Audit record
    audit = GroundReportAudit(
        report_id=report.id,
        user_id=current_user.id,
        action="STATUS_UPDATED",
        previous_state={"status": prev_status, "risk_influence_eligible": not eligible},
        new_state={"status": report.status, "risk_influence_eligible": eligible},
        reason=update_req.reason or f"Status transitioned to {update_req.status.value} by {current_user.email}",
    )
    db.add(audit)
    db.commit()
    db.refresh(report)

    logger.info(
        "ground_report_status_moderated",
        report_id=str(report.id),
        prev_status=prev_status,
        new_status=report.status,
        moderator_id=str(current_user.id),
    )
    return GroundReportResponse(data=_to_report_data(report), meta={"request_id": rid})
