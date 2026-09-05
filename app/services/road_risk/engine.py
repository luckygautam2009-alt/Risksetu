"""
RISKSETU AI — ROAD_RISK_V1 orchestration engine.

Architecture:
  ┌──────────────────────────────────────────────────────────────────────┐
  │                      RoadRiskEngine.assess()                        │
  │                                                                      │
  │  Input: (lat, lon, radius_m, search_radius_m, blocked_edge_id, db)  │
  │                                                                      │
  │  1. Resolve road segment                                             │
  │       - Use blocked_edge_id if supplied, else find_nearest_edge()   │
  │       - Returns error state if no segment found                      │
  │                                                                      │
  │  2. Call LIVE_RISK_V1 (read-only)                                   │
  │       - Get live_risk_score + confidence for the coordinates         │
  │       - Contains Phase 2A historical + live weather trigger          │
  │                                                                      │
  │  3. Call Phase 2B simulation (read-only, what-if)                   │
  │       - build_local_subgraph → simulate_blockage                    │
  │       - Returns isolation_severity + connectivity metrics            │
  │                                                                      │
  │  4. Compute predicted_risk_score                                     │
  │       raw  = 0.65 × live_risk + 0.20 × isolation_severity           │
  │       mod  = 10 pts if bridge segment (capped at 10)                 │
  │       final = clamp(raw + mod, 0, 100)                               │
  │                                                                      │
  │  5. Compute confidence                                               │
  │       = 0.70 × live_confidence + 0.30 × (100 if sim OK else 0)      │
  │                                                                      │
  │  6. Build contributing factors (observed data only)                  │
  │  7. Build recommendations (deterministic, per risk level)            │
  │  8. Return RoadRiskData                                              │
  └──────────────────────────────────────────────────────────────────────┘

CERTIFIED COMPONENTS (unchanged):
  Phase 2A → accessed via LiveRiskEngine (no formula modification)
  Phase 2B → RoadGraphBuilder + RoadIsolationSimulator (no formula modification)

CLOSURE / TRAFFIC POLICY:
  closure_status = "UNKNOWN" — no verified live closure feed.
  traffic_status = "unavailable" — no live traffic provider.
  These fields are NEVER fabricated.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.models.road import RoadNetworkEdge
from app.schemas.road_risk import (
    BlockageRiskAssessment,
    RoadRiskAction,
    RoadRiskConnectivity,
    RoadRiskData,
    RoadRiskFactor,
    RoadRiskFreshness,
    RoadSegmentInfo,
)
from app.services.graph.builder import RoadGraphBuilder
from app.services.impact.isolation import IsolationResult, RoadIsolationSimulator
from app.services.live_risk.engine import LiveRiskEngine
from app.services.live_risk.ml_status import get_ml_status
from app.services.road_risk.constants import (
    BRIDGE_MODIFIER,
    BRIDGE_MODIFIER_CAP,
    CONF_DATA_LIMITED_MAX,
    ENGINE_VERSION,
    RISK_LEVEL_HIGH_MAX,
    RISK_LEVEL_LOW_MAX,
    RISK_LEVEL_MODERATE_MAX,
    W_CONF_ISOLATION,
    W_CONF_LIVE,
    W_ISOLATION,
    W_LIVE_RISK,
)
from app.services.weather.service import WeatherService

logger = structlog.get_logger("risksetu.road_risk.engine")

# ---------------------------------------------------------------------------
# Recommended actions table
# ---------------------------------------------------------------------------

_BASE_ACTIONS: dict[str, list[dict[str, str]]] = {
    "LOW": [
        {
            "action_id": "ROAD_MONITOR_ROUTINE",
            "description": "Continue routine road monitoring.",
            "priority": "low",
        },
    ],
    "MODERATE": [
        {
            "action_id": "ROAD_MONITOR_INCREASED",
            "description": "Increase monitoring frequency for this corridor.",
            "priority": "moderate",
        },
        {
            "action_id": "ROAD_INSPECT_CORRIDOR",
            "description": "Inspect the corridor for early signs of slope instability.",
            "priority": "moderate",
        },
    ],
    "HIGH": [
        {
            "action_id": "ROAD_FIELD_INSPECT",
            "description": "Prioritise field inspection of this road segment.",
            "priority": "high",
        },
        {
            "action_id": "ROAD_MONITOR_CONNECTIVITY",
            "description": "Monitor downstream road connectivity and alternate routes.",
            "priority": "high",
        },
        {
            "action_id": "ROAD_PREP_ALTERNATE",
            "description": "Identify and prepare alternate route options in advance.",
            "priority": "high",
        },
    ],
    "CRITICAL": [
        {
            "action_id": "ROAD_IMMEDIATE_VERIFY",
            "description": "Immediate field verification of road condition required.",
            "priority": "immediate",
        },
        {
            "action_id": "ROAD_PREP_ALTERNATE_CRITICAL",
            "description": "Prepare alternate route; notify downstream agencies.",
            "priority": "immediate",
        },
        {
            "action_id": "ROAD_MONITOR_CONNECTIVITY_CRITICAL",
            "description": "Monitor all affected downstream connectivity in real time.",
            "priority": "immediate",
        },
        {
            "action_id": "ROAD_COORD_RESPONSE",
            "description": "Coordinate response resources for potential blockage event.",
            "priority": "immediate",
        },
    ],
}

_BRIDGE_ACTIONS: dict[str, str] = {
    "action_id": "BRIDGE_STRUCTURAL_CHECK",
    "description": (
        "Segment is a bridge structure or graph-theoretic cut edge. "
        "Prioritise structural integrity assessment during/after rainfall events."
    ),
    "priority": "high",
}


def _determine_risk_level(score: float) -> str:
    """Mirror Phase 2A + LIVE_RISK_V1 thresholds exactly."""
    if score <= RISK_LEVEL_LOW_MAX:
        return "LOW"
    elif score <= RISK_LEVEL_MODERATE_MAX:
        return "MODERATE"
    elif score <= RISK_LEVEL_HIGH_MAX:
        return "HIGH"
    return "CRITICAL"


def _build_actions(
    risk_level: str,
    is_bridge: bool,
) -> list[RoadRiskAction]:
    seen: set[str] = set()
    actions: list[RoadRiskAction] = []
    for a in _BASE_ACTIONS.get(risk_level, []):
        if a["action_id"] not in seen:
            actions.append(RoadRiskAction(**a))  # type: ignore[arg-type]
            seen.add(a["action_id"])
    if is_bridge and _BRIDGE_ACTIONS["action_id"] not in seen:
        actions.append(RoadRiskAction(**_BRIDGE_ACTIONS))  # type: ignore[arg-type]
    return actions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_edge(
    db: Session,
    builder: RoadGraphBuilder,
    lat: float,
    lon: float,
    search_radius_m: float,
    blocked_edge_id: uuid.UUID | None,
) -> dict[str, Any] | None:
    """Resolve a road segment to its edge metadata dict, or return None."""
    if blocked_edge_id is not None:
        edge = db.get(RoadNetworkEdge, blocked_edge_id)
        if edge is None:
            return None
        return {
            "edge_db_id": str(edge.id),
            "osm_way_id": edge.osm_way_id,
            "from_node_id": edge.from_node_id,
            "to_node_id": edge.to_node_id,
            "highway_class": edge.highway_class,
            "name": edge.name,
            "length_m": edge.length_m,
            "bridge": edge.bridge,
            "tunnel": edge.tunnel,
            "distance_from_target_m": None,
        }
    return builder.find_nearest_edge(
        latitude=lat,
        longitude=lon,
        search_radius_m=search_radius_m,
    )


def _run_phase2b(
    builder: RoadGraphBuilder,
    edge_info: dict[str, Any],
    lat: float,
    lon: float,
    radius_m: float,
) -> IsolationResult | None:
    """Run Phase 2B simulation. Returns None on failure."""
    try:
        effective_radius = max(radius_m, edge_info.get("distance_from_target_m") or 0.0 + 500.0, 1500.0)
        G = builder.build_local_subgraph(lat, lon, radius_m=effective_radius)

        if G.number_of_nodes() == 0:
            return None

        u = edge_info["from_node_id"]
        v = edge_info["to_node_id"]
        edge_key = edge_info.get("edge_db_id")

        # Ensure the targeted edge is in the subgraph (mirrors impact.py logic)
        if edge_key is not None and not G.has_edge(u, v, key=edge_key):
            G.add_edge(
                u, v, key=edge_key,
                edge_db_id=edge_key,
                osm_way_id=edge_info.get("osm_way_id"),
                highway_class=edge_info.get("highway_class"),
                length_m=edge_info.get("length_m", 0.0),
                name=edge_info.get("name"),
                bridge=edge_info.get("bridge", False),
                tunnel=edge_info.get("tunnel", False),
            )
        elif edge_key is None and not G.has_edge(u, v):
            G.add_edge(
                u, v,
                osm_way_id=edge_info.get("osm_way_id"),
                highway_class=edge_info.get("highway_class"),
                length_m=edge_info.get("length_m", 0.0),
                name=edge_info.get("name"),
                bridge=edge_info.get("bridge", False),
                tunnel=edge_info.get("tunnel", False),
            )

        blocked_spec: tuple[int, int] | tuple[int, int, str] = (
            (u, v, edge_key) if edge_key else (u, v)
        )
        return RoadIsolationSimulator.simulate_blockage(
            graph=G,
            blocked_edges=[blocked_spec],
            subgraph_radius_m=effective_radius,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("road_risk_phase2b_error", error_type=type(exc).__name__, error=str(exc))
        return None


def _build_connectivity(
    sim: IsolationResult | None,
    sim_error: str | None,
    radius_m: float,
) -> RoadRiskConnectivity:
    if sim is None:
        return RoadRiskConnectivity(
            simulation_type="WHAT_IF",
            simulation_error=sim_error or "Phase 2B simulation could not be run.",
        )
    return RoadRiskConnectivity(
        simulation_type="WHAT_IF",
        components_before=sim.components_before,
        components_after=sim.components_after,
        component_increase=sim.component_increase,
        nodes_affected=sim.nodes_affected,
        edges_in_affected_components=sim.edges_in_affected_components,
        isolation_severity=sim.isolation_severity,
        is_bridge_edge=sim.is_bridge_edge,
        articulation_points_near_blockage=sim.articulation_points_near_blockage,
        isolated_components=sim.alternative_components,
        graph_stats_before=sim.graph_stats_before,
        graph_stats_after=sim.graph_stats_after,
        subgraph_radius_m=radius_m,
        summary_explanation="",
        limitations=sim.limitations,
        simulation_error=None,
    )


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class RoadRiskEngine:
    """ROAD_RISK_V1 orchestration engine.

    Reads from Phase 2A (via LiveRiskEngine) and Phase 2B (via
    RoadGraphBuilder + RoadIsolationSimulator) without modifying them.
    """

    def __init__(
        self,
        db: Session,
        weather_service: WeatherService | None = None,
    ) -> None:
        self._db = db
        self._live_risk_engine = LiveRiskEngine(db=db, weather_service=weather_service)
        self._builder = RoadGraphBuilder(db=db)

    async def assess(
        self,
        lat: float,
        lon: float,
        radius_m: float,
        search_radius_m: float,
        blocked_edge_id: uuid.UUID | None,
    ) -> RoadRiskData:
        """Produce a ROAD_RISK_V1 assessment for the given road segment."""
        now = datetime.now(timezone.utc)
        logger.info("road_risk_assessment_start", lat=lat, lon=lon)

        unavailable_inputs: list[str] = []

        # ── 1. Resolve road segment ────────────────────────────────────────
        edge_info = _resolve_edge(
            self._db, self._builder, lat, lon, search_radius_m, blocked_edge_id
        )

        if edge_info is None:
            # Return a data-limited state — no fabrication
            road_segment = RoadSegmentInfo(
                from_node_id=0, to_node_id=0,
                edge_db_id=None, osm_way_id=None,
            )
            unavailable_inputs.extend([
                "road_segment_not_found",
                "live_risk", "isolation_simulation",
                "ml_susceptibility", "terrain",
            ])
            return RoadRiskData(
                road=road_segment,
                blockage=BlockageRiskAssessment(
                    predicted_risk_score=0.0,
                    risk_level="LOW",
                    confidence=CONF_DATA_LIMITED_MAX,
                    status="PREDICTED",
                    closure_status="UNKNOWN",
                    traffic_status="unavailable",
                ),
                factors=[],
                connectivity=RoadRiskConnectivity(
                    simulation_type="WHAT_IF",
                    simulation_error="Road segment could not be resolved near the requested coordinates.",
                ),
                unavailable_inputs=unavailable_inputs,
                recommendations=_build_actions("LOW", False),
                data_freshness=RoadRiskFreshness(
                    assessment_generated_at=now.isoformat(),
                ),
                engine_version=ENGINE_VERSION,
            )

        road_segment = RoadSegmentInfo(
            edge_db_id=edge_info.get("edge_db_id"),
            osm_way_id=edge_info.get("osm_way_id"),
            from_node_id=edge_info["from_node_id"],
            to_node_id=edge_info["to_node_id"],
            highway_class=edge_info.get("highway_class"),
            name=edge_info.get("name"),
            length_m=float(edge_info.get("length_m") or 0.0),
            bridge=bool(edge_info.get("bridge", False)),
            tunnel=bool(edge_info.get("tunnel", False)),
            distance_from_target_m=edge_info.get("distance_from_target_m"),
        )

        # ── 2. Live Area Risk (LIVE_RISK_V1 — read-only) ─────────────────
        live_risk_score: float = 0.0
        live_risk_confidence: float = 0.0
        weather_obs_time: str | None = None
        weather_fetched_at: str | None = None
        weather_freshness_s: int | None = None
        live_risk_available = False
        factors: list[RoadRiskFactor] = []

        try:
            live_data = await self._live_risk_engine.assess(lat, lon)
            live_risk_score = live_data.risk.score
            live_risk_confidence = live_data.risk.confidence
            live_risk_available = live_data.historical.status == "available"

            # Weather freshness
            if live_data.data_freshness.weather_observation_time:
                weather_obs_time = live_data.data_freshness.weather_observation_time.isoformat()
            if live_data.data_freshness.weather_fetched_at:
                weather_fetched_at = live_data.data_freshness.weather_fetched_at.isoformat()
            weather_freshness_s = live_data.data_freshness.weather_freshness_seconds

            # Pass through contributing factors from live risk
            for cf in live_data.contributing_factors:
                factors.append(RoadRiskFactor(
                    name=cf.factor,
                    description=cf.description,
                    value=cf.value,
                    source=cf.source,
                    contribution_pts=0.0,  # exact attribution computed below
                ))

            if not live_risk_available:
                unavailable_inputs.append("live_risk_historical")

            if live_data.weather.status not in ("available", "cached"):
                unavailable_inputs.append("live_weather")

        except Exception as exc:  # noqa: BLE001
            logger.warning("road_risk_live_risk_error", error=str(exc))
            unavailable_inputs.append("live_risk")

        # ── 3. Phase 2B simulation (read-only, what-if) ───────────────────
        sim_result: IsolationResult | None = None
        sim_error: str | None = None
        try:
            sim_result = _run_phase2b(self._builder, edge_info, lat, lon, radius_m)
            if sim_result is None:
                sim_error = "No road network data available in this area."
                unavailable_inputs.append("isolation_simulation")
        except Exception as exc:  # noqa: BLE001
            sim_error = f"Simulation error: {type(exc).__name__}"
            unavailable_inputs.append("isolation_simulation")

        isolation_severity = sim_result.isolation_severity if sim_result else 0.0
        isolation_available = sim_result is not None

        # ── 4. ML / terrain status (always unavailable) ──────────────────
        ml_info = get_ml_status()
        if ml_info["status"] != "available":
            unavailable_inputs.append("ml_susceptibility")
        unavailable_inputs.append("terrain")

        # ── 5. Compute predicted blockage risk score ─────────────────────
        #
        #   raw_score = W_LIVE_RISK(0.65) × live_risk_score
        #             + W_ISOLATION(0.20)  × isolation_severity
        #   bridge_mod = BRIDGE_MODIFIER(10) if bridge segment, else 0
        #   final = clamp(raw + bridge_mod, 0, 100)
        #
        is_bridge = (
            road_segment.bridge
            or (sim_result is not None and sim_result.is_bridge_edge)
        )

        raw_score = (W_LIVE_RISK * live_risk_score) + (W_ISOLATION * isolation_severity)
        bridge_mod = min(BRIDGE_MODIFIER, BRIDGE_MODIFIER_CAP) if is_bridge else 0.0
        predicted_score = round(max(0.0, min(100.0, raw_score + bridge_mod)), 1)
        final_level = _determine_risk_level(predicted_score)

        # Annotate contribution_pts on live_risk factors (approximate)
        live_factor_pts = W_LIVE_RISK * live_risk_score
        for f in factors:
            f.contribution_pts = round(live_factor_pts / max(len(factors), 1), 2)

        # Add isolation severity as its own factor
        if isolation_available:
            factors.append(RoadRiskFactor(
                name="phase2b_isolation_severity",
                description=(
                    f"Phase 2B simulation: blocking this segment increases isolated components by "
                    f"{sim_result.component_increase if sim_result else 0}, "  # type: ignore[union-attr]
                    f"affecting {sim_result.nodes_affected if sim_result else 0} nodes."  # type: ignore[union-attr]
                ),
                value=round(isolation_severity, 2),
                source="phase2b_simulation",
                contribution_pts=round(W_ISOLATION * isolation_severity, 2),
            ))

        # Add bridge modifier factor if active
        if is_bridge and bridge_mod > 0:
            factors.append(RoadRiskFactor(
                name="bridge_segment_modifier",
                description=(
                    "This segment is a bridge structure (OSM bridge=yes) or graph-theoretic "
                    "cut edge. Bridges are disproportionately vulnerable in landslide zones."
                ),
                value={"osm_bridge": road_segment.bridge,
                       "is_graph_bridge": sim_result.is_bridge_edge if sim_result else False},
                source="phase2b_simulation",
                contribution_pts=bridge_mod,
            ))

        # ── 6. Confidence ─────────────────────────────────────────────────
        # confidence = W_CONF_LIVE(0.70) × live_confidence
        #            + W_CONF_ISOLATION(0.30) × (100 if isolation available else 0)
        if not live_risk_available and not isolation_available:
            confidence = CONF_DATA_LIMITED_MAX
        else:
            confidence = round(
                W_CONF_LIVE * live_risk_confidence
                + W_CONF_ISOLATION * (100.0 if isolation_available else 0.0),
                1,
            )
        confidence = max(0.0, min(100.0, confidence))

        # ── 7. Build connectivity layer ────────────────────────────────────
        connectivity = _build_connectivity(sim_result, sim_error, radius_m)

        # ── 8. Recommendations ────────────────────────────────────────────
        recommendations = _build_actions(final_level, is_bridge)

        # ── 9. Data freshness ─────────────────────────────────────────────
        freshness = RoadRiskFreshness(
            assessment_generated_at=now.isoformat(),
            live_risk_version=ENGINE_VERSION,
            weather_observation_time=weather_obs_time,
            weather_fetched_at=weather_fetched_at,
            weather_freshness_seconds=weather_freshness_s,
            historical_data_version="risk-v1",
        )

        logger.info(
            "road_risk_assessment_complete",
            lat=lat, lon=lon,
            predicted_score=predicted_score,
            final_level=final_level,
            is_bridge=is_bridge,
            isolation_severity=isolation_severity,
        )

        return RoadRiskData(
            road=road_segment,
            blockage=BlockageRiskAssessment(
                predicted_risk_score=predicted_score,
                risk_level=final_level,
                confidence=confidence,
                status="PREDICTED",
                closure_status="UNKNOWN",
                traffic_status="unavailable",
            ),
            factors=factors,
            connectivity=connectivity,
            unavailable_inputs=list(dict.fromkeys(unavailable_inputs)),  # deduplicate, preserve order
            recommendations=recommendations,
            data_freshness=freshness,
            engine_version=ENGINE_VERSION,
        )
