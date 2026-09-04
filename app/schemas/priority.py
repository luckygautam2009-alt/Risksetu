"""
Pydantic schemas for the Impact-Aware Intervention Priority Engine.
"""
from __future__ import annotations

from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field


class PriorityBreakdownDetail(BaseModel):
    """Quantitative contribution breakdown of the composite priority score."""

    risk_contribution: float = Field(..., ge=0.0, le=45.0, description="Hazard risk weighted contribution (45% max).")
    impact_contribution: float = Field(..., ge=0.0, le=40.0, description="Isolation impact weighted contribution (40% max).")
    urgency_contribution: float = Field(..., ge=0.0, le=15.0, description="Urgency weighted contribution (15% max).")
    priority_score: float = Field(..., ge=0.0, le=100.0, description="Composite intervention priority score [0-100].")
    priority_level: str = Field(..., description="Standard categorical level: LOW, MODERATE, HIGH, CRITICAL.")


class PriorityCandidateInput(BaseModel):
    """Input representation of an intervention candidate scenario."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(
        default_factory=lambda: f"cand_{uuid.uuid4().hex[:8]}",
        description="Unique identifier for the priority candidate location.",
    )
    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS84 Latitude.")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 Longitude.")
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Phase 2A hazard risk score [0-100].")
    risk_level: str = Field(..., description="Categorical risk level: LOW, MODERATE, HIGH, CRITICAL.")
    risk_confidence: float = Field(default=50.0, ge=0.0, le=100.0, description="Phase 2A data confidence score [0-100].")
    isolation_severity: float = Field(..., ge=0.0, le=100.0, description="Phase 2B road isolation severity [0-100].")
    component_increase: int = Field(default=0, ge=0, description="Net component partition increase from road failure.")
    nodes_affected: int = Field(default=0, ge=0, description="Count of nodes located in newly disconnected subgraphs.")
    edges_in_affected_components: int = Field(default=0, ge=0, description="Remaining internal edges in newly disconnected subgraphs.")
    is_bridge_edge: bool = Field(default=False, description="Whether the primary access road is a graph cut-edge.")


class PriorityEvaluationRequest(BaseModel):
    """Input payload for single scenario priority evaluation."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str | None = Field(default=None, description="Optional custom candidate identifier.")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS84 Latitude.")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 Longitude.")
    risk_score: float | None = Field(default=None, ge=0.0, le=100.0, description="Pre-computed Phase 2A risk score if known.")
    risk_level: str | None = Field(default=None, description="Pre-computed Phase 2A risk level if known.")
    risk_confidence: float | None = Field(default=None, ge=0.0, le=100.0, description="Pre-computed Phase 2A confidence score.")
    isolation_severity: float | None = Field(default=None, ge=0.0, le=100.0, description="Pre-computed Phase 2B isolation severity.")
    component_increase: int = Field(default=0, ge=0, description="Net component partition increase.")
    nodes_affected: int = Field(default=0, ge=0, description="Count of newly disconnected nodes.")
    edges_in_affected_components: int = Field(default=0, ge=0, description="Remaining internal edges in disconnected components.")
    is_bridge_edge: bool = Field(default=False, description="Whether access route is a topological bridge.")
    radius_m: float = Field(default=3000.0, ge=500.0, le=50000.0, description="Local subgraph radius if orchestrating Phase 2B.")
    search_radius_m: float = Field(default=1000.0, ge=50.0, le=10000.0, description="Nearest road search radius if orchestrating Phase 2B.")


class PriorityEvaluationData(BaseModel):
    """Payload of priority evaluation response."""

    candidate_id: str
    latitude: float
    longitude: float
    priority_score: float = Field(..., ge=0.0, le=100.0)
    priority_level: str
    breakdown: PriorityBreakdownDetail
    risk_score: float
    risk_level: str
    risk_confidence: float
    isolation_severity: float
    component_increase: int
    nodes_affected: int
    edges_in_affected_components: int
    is_bridge_edge: bool
    urgency_score: float
    calculation_version: str
    explanation: str
    limitations: list[str]


class PriorityEvaluationResponse(BaseModel):
    """Standard success envelope for priority evaluation."""

    data: PriorityEvaluationData
    meta: dict[str, Any] = Field(default_factory=dict)


class PriorityRankingRequest(BaseModel):
    """Input payload for multi-candidate priority ranking."""

    model_config = ConfigDict(extra="forbid")

    candidates: list[PriorityCandidateInput] = Field(
        ...,
        min_length=1,
        description="List of evaluated intervention candidates to rank.",
    )


class RankedCandidatePayload(BaseModel):
    """Detailed ranked candidate output."""

    rank: int = Field(..., ge=1, description="Sequential rank (1 = highest intervention priority).")
    candidate_id: str
    latitude: float
    longitude: float
    priority_score: float = Field(..., ge=0.0, le=100.0)
    priority_level: str
    risk_score: float
    risk_level: str
    risk_confidence: float
    isolation_severity: float
    urgency_score: float
    is_bridge_edge: bool
    nodes_affected: int
    component_increase: int
    breakdown: PriorityBreakdownDetail
    explanation: str


class PriorityRankingData(BaseModel):
    """Payload of ranked intervention candidates."""

    total_candidates: int
    ranked_candidates: list[RankedCandidatePayload]
    calculation_version: str
    limitations: list[str]


class PriorityRankingResponse(BaseModel):
    """Standard success envelope for multi-candidate priority ranking."""

    data: PriorityRankingData
    meta: dict[str, Any] = Field(default_factory=dict)
