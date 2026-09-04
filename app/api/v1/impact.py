"""
Road network isolation and connectivity impact simulation API routes.
"""
from __future__ import annotations

from typing import Any
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
import structlog

from app.core.errors import NotFoundError, ValidationAppError
from app.db.session import get_db
from app.models.road import RoadNetworkEdge
from app.schemas.impact import (
    AlternativeComponent,
    BlockedEdgeInfo,
    ConnectivityImpact,
    GraphStats,
    RoadBlockageSimulationData,
    RoadBlockageSimulationRequest,
    RoadBlockageSimulationResponse,
)
from app.services.graph.builder import RoadGraphBuilder
from app.services.impact.isolation import RoadIsolationSimulator

logger = structlog.get_logger("risksetu.impact_api")

router = APIRouter(prefix="/impact", tags=["impact"])


@router.post(
    "/simulate-road-blockage",
    response_model=RoadBlockageSimulationResponse,
    summary="Simulate road blockage isolation impact",
)
async def simulate_road_blockage(
    request_body: RoadBlockageSimulationRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> RoadBlockageSimulationResponse:
    """Non-destructive what-if simulation of road blockage on the local road graph.

    Evaluates network partition, newly isolated components, topological bridges,
    and calculates an isolation severity score (0-100) using real OpenStreetMap road data.
    """
    builder = RoadGraphBuilder(db)

    # 1. Resolve edge to block (either specified by ID or find nearest)
    edge_info: dict[str, Any] | None = None

    if request_body.blocked_edge_id:
        edge = db.get(RoadNetworkEdge, request_body.blocked_edge_id)
        if not edge:
            raise NotFoundError(
                f"RoadNetworkEdge with ID '{request_body.blocked_edge_id}' was not found."
            )
        edge_info = {
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
    else:
        edge_info = builder.find_nearest_edge(
            latitude=request_body.latitude,
            longitude=request_body.longitude,
            search_radius_m=request_body.search_radius_m,
        )
        if not edge_info:
            raise NotFoundError(
                f"No road segment found within {request_body.search_radius_m:.0f}m of "
                f"({request_body.latitude}, {request_body.longitude}). "
                "Try expanding search_radius_m or verify roads have been ingested in this region."
            )

    # 2. Build local subgraph within radius_m
    # Ensure radius_m is at least search_radius_m so the edge is included
    effective_radius = max(request_body.radius_m, request_body.search_radius_m + 500.0)
    G = builder.build_local_subgraph(
        latitude=request_body.latitude,
        longitude=request_body.longitude,
        radius_m=effective_radius,
    )

    if G.number_of_nodes() == 0:
        raise ValidationAppError(
            f"No road network graph could be constructed within {effective_radius:.0f}m "
            f"of ({request_body.latitude}, {request_body.longitude})."
        )

    # Ensure the targeted edge is present in graph
    # Ensure the targeted edge is present in graph with its unique DB UUID key
    u = edge_info["from_node_id"]
    v = edge_info["to_node_id"]
    edge_key = edge_info.get("edge_db_id")

    if edge_key is not None and not G.has_edge(u, v, key=edge_key):
        G.add_edge(
            u,
            v,
            key=edge_key,
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
            u,
            v,
            edge_db_id=edge_key,
            osm_way_id=edge_info.get("osm_way_id"),
            highway_class=edge_info.get("highway_class"),
            length_m=edge_info.get("length_m", 0.0),
            name=edge_info.get("name"),
            bridge=edge_info.get("bridge", False),
            tunnel=edge_info.get("tunnel", False),
        )

    # 3. Simulate blockage
    blocked_spec = (u, v, edge_key) if edge_key else (u, v)
    sim_result = RoadIsolationSimulator.simulate_blockage(
        graph=G,
        blocked_edges=[blocked_spec],
        subgraph_radius_m=effective_radius,
    )

    # 4. Formulate summary explanation
    road_desc = edge_info.get("name") or edge_info.get("highway_class") or "road segment"
    bridge_note = "is a graph-theoretic bridge" if sim_result.is_bridge_edge else "is not a graph-theoretic bridge"
    component_diff = sim_result.components_after - sim_result.components_before

    if component_diff > 0:
        summary_explanation = (
            f"Simulated blockage of {road_desc} (OSM Way {edge_info.get('osm_way_id')}) severed connectivity. "
            f"Network partitions increased from {sim_result.components_before} to {sim_result.components_after} "
            f"(+{component_diff} isolated components). The segment {bridge_note}. "
            f"{sim_result.nodes_affected} nodes across {sim_result.edges_in_affected_components} internal road segments "
            f"are newly isolated. Isolation severity is rated at {sim_result.isolation_severity:.1f}/100."
        )
    else:
        summary_explanation = (
            f"Simulated blockage of {road_desc} (OSM Way {edge_info.get('osm_way_id')}) did not partition "
            f"the connected component. Redundant alternate paths remain open. "
            f"Isolation severity is rated at {sim_result.isolation_severity:.1f}/100."
        )


    # 5. Assemble response
    blocked_edge_payload = BlockedEdgeInfo(
        edge_db_id=edge_info.get("edge_db_id"),
        osm_way_id=edge_info.get("osm_way_id"),
        from_node_id=u,
        to_node_id=v,
        highway_class=edge_info.get("highway_class"),
        name=edge_info.get("name"),
        length_m=edge_info.get("length_m", 0.0),
        bridge=edge_info.get("bridge", False),
        tunnel=edge_info.get("tunnel", False),
        is_bridge_edge=sim_result.is_bridge_edge,
        distance_from_target_m=edge_info.get("distance_from_target_m"),
    )

    connectivity_impact_payload = ConnectivityImpact(
        components_before=sim_result.components_before,
        components_after=sim_result.components_after,
        component_increase=component_diff,
        nodes_affected=sim_result.nodes_affected,
        edges_in_affected_components=sim_result.edges_in_affected_components,
        is_bridge_edge=sim_result.is_bridge_edge,
        articulation_points_near_blockage=sim_result.articulation_points_near_blockage,
    )

    data_payload = RoadBlockageSimulationData(
        simulation_type="WHAT_IF_SCENARIO",
        target_location={
            "latitude": request_body.latitude,
            "longitude": request_body.longitude,
        },
        subgraph_radius_m=effective_radius,
        blocked_edge=blocked_edge_payload,
        connectivity_impact=connectivity_impact_payload,
        isolation_severity=sim_result.isolation_severity,
        isolated_components=[
            AlternativeComponent(
                component_index=c["component_index"],
                node_count=c["node_count"],
                edge_count=c["edge_count"],
            )
            for c in sim_result.alternative_components
        ],
        graph_stats_before=GraphStats(
            total_nodes=sim_result.graph_stats_before.get("total_nodes", 0),
            total_edges=sim_result.graph_stats_before.get("total_edges", 0),
            connected_components=sim_result.graph_stats_before.get("connected_components", 0),
            largest_component_nodes=sim_result.graph_stats_before.get("largest_component_nodes", 0),
        ),
        graph_stats_after=GraphStats(
            total_nodes=sim_result.graph_stats_after.get("total_nodes", 0),
            total_edges=sim_result.graph_stats_after.get("total_edges", 0),
            connected_components=sim_result.graph_stats_after.get("connected_components", 0),
            largest_component_nodes=sim_result.graph_stats_after.get("largest_component_nodes", 0),
        ),
        summary_explanation=summary_explanation,
        limitations=sim_result.limitations,
    )

    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return RoadBlockageSimulationResponse(
        data=data_payload,
        meta={"request_id": req_id},
    )
