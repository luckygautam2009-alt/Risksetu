"""
RISKSETU AI — Public-Source AI Hazard Intelligence (OSINT) endpoints.

Endpoints:
  GET  /api/v1/osint        — Retrieve current corroborated public hazard leads.
  POST /api/v1/osint/scan   — Trigger situational scan (official/admin or demo).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.services.osint import scan_osint

router = APIRouter(prefix="/osint", tags=["osint"])


class OSINTLeadEvidence(BaseModel):
    source: str
    source_type: str
    title: str
    summary: str
    url: str | None = None
    published_at: str | None = None


class OSINTLead(BaseModel):
    area: str
    latitude: float
    longitude: float
    hazard: str
    severity: str
    confidence: str
    corroboration_score: float
    evidence_count: int
    independent_sources: int
    rainfall_24h_mm: float
    affected_areas: list[str] = Field(default_factory=list)
    impact_window: str
    recommended_action: str
    analysis_note: str
    evidence: list[OSINTLeadEvidence] = Field(default_factory=list)
    source: str
    data_mode: str
    updated_at: str


class OSINTResponse(BaseModel):
    data: list[OSINTLead]
    meta: dict[str, Any] = Field(default_factory=dict)


@router.get("", response_model=OSINTResponse, summary="Retrieve corroborated public hazard leads")
async def get_osint_leads(request: Request) -> OSINTResponse:
    """Retrieve public-source disaster intelligence leads.

    Leads are decision-support signals corroborated against live weather,
    never automated evacuation triggers.
    """
    rid = getattr(request.state, "request_id", "")
    leads = await scan_osint()
    return OSINTResponse(
        data=[OSINTLead(**lead) for lead in leads],
        meta={"request_id": rid, "total_leads": len(leads)},
    )


@router.post("/scan", response_model=OSINTResponse, summary="Run on-demand public lead scan")
async def trigger_osint_scan(request: Request) -> OSINTResponse:
    """Trigger an on-demand scan of public disaster feeds and news sources."""
    rid = getattr(request.state, "request_id", "")
    leads = await scan_osint()
    return OSINTResponse(
        data=[OSINTLead(**lead) for lead in leads],
        meta={"request_id": rid, "total_leads": len(leads), "scanned": True},
    )
