"""
RISKSETU AI — Road Blockage Risk (ROAD_RISK_V1) Pydantic schemas.

Response envelope for POST /api/v1/road-risk/evaluate.
"""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class RoadRiskEvaluationRequest(BaseModel):
    """Input for road blockage risk evaluation.

    Follows the same segment-identification convention as Phase 2B:
      - preferred: supply latitude + longitude → nearest edge is auto-resolved.
      - alternative: supply blocked_edge_id to target a specific DB edge.
    """

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="WGS 84 latitude of the road segment or area of interest.",
        examples=[30.2936],
    )
    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="WGS 84 longitude of the road segment or area of interest.",
        examples=[79.5603],
    )
    radius_m: float = Field(
        default=5000.0,
        ge=500.0,
        le=50000.0,
        description="Radius in metres to extract the local road network subgraph.",
    )
    search_radius_m: float = Field(
        default=1000.0,
        ge=50.0,
        le=10000.0,
        description="Radius in metres to search for the nearest road segment when blocked_edge_id is omitted.",
    )
    blocked_edge_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Optional DB UUID of a specific RoadNetworkEdge to evaluate. "
            "If omitted, the nearest edge to (latitude, longitude) is used."
        ),
    )


# ---------------------------------------------------------------------------
# Road segment info
# ---------------------------------------------------------------------------


class RoadSegmentInfo(BaseModel):
    """Identifies the road segment under evaluation."""

    edge_db_id: str | None = Field(default=None)
    osm_way_id: int | None = Field(default=None)
    from_node_id: int = Field(...)
    to_node_id: int = Field(...)
    highway_class: str | None = Field(default=None)
    name: str | None = Field(default=None)
    length_m: float = Field(default=0.0)
    bridge: bool = Field(
        default=False,
        description="Physical civil engineering bridge (OSM bridge=yes tag).",
    )
    tunnel: bool = Field(default=False)
    distance_from_target_m: float | None = Field(default=None)


# ---------------------------------------------------------------------------
# Blockage risk assessment
# ---------------------------------------------------------------------------


class BlockageRiskAssessment(BaseModel):
    """Predicted blockage susceptibility for the selected road segment."""

    predicted_risk_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Composite predicted blockage risk [0-100].",
    )
    risk_level: str = Field(
        description="LOW / MODERATE / HIGH / CRITICAL (same thresholds as Phase 2A).",
    )
    confidence: float = Field(
        ge=0.0,
        le=100.0,
        description="Evidence coverage confidence [0-100].",
    )
    status: str = Field(
        default="PREDICTED",
        description="Always PREDICTED — this is a susceptibility estimate, not a confirmed event.",
    )
    closure_status: str = Field(
        default="UNKNOWN",
        description=(
            "Always UNKNOWN — no verified live road-closure feed is currently integrated. "
            "Never treat PREDICTED risk as a confirmed closure."
        ),
    )
    traffic_status: str = Field(
        default="unavailable",
        description="Always unavailable — no live traffic provider is integrated.",
    )


# ---------------------------------------------------------------------------
# Contributing factors
# ---------------------------------------------------------------------------


class RoadRiskFactor(BaseModel):
    """A single observable factor that contributed to the predicted blockage risk."""

    name: str
    description: str
    value: Any = Field(default=None)
    source: str = Field(
        description="Which layer this came from: live_risk | historical | weather | terrain | ml"
    )
    contribution_pts: float = Field(
        default=0.0,
        description="Approximate score contribution of this factor.",
    )


# ---------------------------------------------------------------------------
# Connectivity simulation (delegated to Phase 2B unchanged)
# ---------------------------------------------------------------------------


class RoadRiskConnectivity(BaseModel):
    """Phase 2B what-if simulation result, embedded verbatim."""

    simulation_type: str = Field(
        default="WHAT_IF",
        description="Always WHAT_IF — this is a non-destructive simulation, not a confirmed closure.",
    )
    components_before: int = Field(default=0)
    components_after: int = Field(default=0)
    component_increase: int = Field(default=0)
    nodes_affected: int = Field(default=0)
    edges_in_affected_components: int = Field(default=0)
    isolation_severity: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Phase 2B isolation severity score [0-100].",
    )
    is_bridge_edge: bool = Field(default=False)
    articulation_points_near_blockage: list[int] = Field(default_factory=list)
    isolated_components: list[dict[str, Any]] = Field(default_factory=list)
    graph_stats_before: dict[str, Any] = Field(default_factory=dict)
    graph_stats_after: dict[str, Any] = Field(default_factory=dict)
    subgraph_radius_m: float = Field(default=0.0)
    summary_explanation: str = Field(default="")
    limitations: list[str] = Field(default_factory=list)
    simulation_error: str | None = Field(
        default=None,
        description="Populated if Phase 2B simulation could not run (e.g. no road data in area).",
    )


# ---------------------------------------------------------------------------
# Recommended actions
# ---------------------------------------------------------------------------


class RoadRiskAction(BaseModel):
    action_id: str
    description: str
    priority: str = Field(description="immediate | high | moderate | low")


# ---------------------------------------------------------------------------
# Data freshness
# ---------------------------------------------------------------------------


class RoadRiskFreshness(BaseModel):
    assessment_generated_at: str = Field(description="ISO-8601 UTC timestamp.")
    live_risk_version: str | None = Field(default=None)
    weather_observation_time: str | None = Field(default=None)
    weather_fetched_at: str | None = Field(default=None)
    weather_freshness_seconds: int | None = Field(default=None)
    historical_data_version: str | None = Field(default=None)


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------


class RoadRiskData(BaseModel):
    """ROAD_RISK_V1 assessment payload."""

    road: RoadSegmentInfo
    blockage: BlockageRiskAssessment
    factors: list[RoadRiskFactor] = Field(default_factory=list)
    connectivity: RoadRiskConnectivity
    unavailable_inputs: list[str] = Field(default_factory=list)
    recommendations: list[RoadRiskAction] = Field(default_factory=list)
    data_freshness: RoadRiskFreshness
    engine_version: str = Field(default="ROAD_RISK_V1")


class RoadRiskResponse(BaseModel):
    """Standard RISKSETU envelope for road blockage risk."""

    data: RoadRiskData
    meta: dict[str, Any] = Field(default_factory=dict)
