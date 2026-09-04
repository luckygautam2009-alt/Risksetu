"""
Pydantic schemas for the Road Network Isolation & Connectivity Impact Simulation Engine.
"""
from __future__ import annotations

from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field


class RoadBlockageSimulationRequest(BaseModel):
    """Input parameters for simulating a road blockage on the local network graph."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="WGS 84 Latitude of the epicenter or target location.",
        examples=[30.3165],
    )
    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="WGS 84 Longitude of the epicenter or target location.",
        examples=[78.0322],
    )
    radius_m: float = Field(
        default=5000.0,
        ge=500.0,
        le=50000.0,
        description="Search radius in meters to construct the local road network subgraph.",
        examples=[5000.0],
    )
    blocked_edge_id: uuid.UUID | None = Field(
        default=None,
        description="Optional database UUID of the specific RoadNetworkEdge to block. If omitted, the nearest road edge to (latitude, longitude) is automatically identified and blocked.",
        examples=[None],
    )
    search_radius_m: float = Field(
        default=1000.0,
        ge=50.0,
        le=10000.0,
        description="Radius in meters to search for the nearest road edge if blocked_edge_id is omitted.",
        examples=[1000.0],
    )


class BlockedEdgeInfo(BaseModel):
    """Metadata describing the blocked road segment."""

    edge_db_id: str | None = Field(default=None, description="Database UUID of the edge record if known.")
    osm_way_id: int | None = Field(default=None, description="OpenStreetMap Way ID.")
    from_node_id: int = Field(..., description="Start node OSM ID.")
    to_node_id: int = Field(..., description="End node OSM ID.")
    highway_class: str | None = Field(default=None, description="OSM highway classification (e.g. primary, secondary).")
    name: str | None = Field(default=None, description="Road name if tagged.")
    length_m: float = Field(default=0.0, ge=0.0, description="Segment length in meters.")
    bridge: bool = Field(
        default=False,
        description="Physical civil engineering bridge structure tagged in OpenStreetMap (bridge=yes).",
    )
    tunnel: bool = Field(default=False, description="Whether the edge is a tunnel.")
    is_bridge_edge: bool = Field(
        default=False,
        description="Graph-theoretic bridge (cut edge): an edge whose removal strictly increases the number of connected components.",
    )
    distance_from_target_m: float | None = Field(
        default=None,
        description="Distance from the requested coordinates to this edge in meters.",
    )
    error: str | None = Field(default=None, description="Error note if edge could not be resolved.")


class ConnectivityImpact(BaseModel):
    """Topological impact metrics of the simulated road blockage."""

    components_before: int = Field(..., description="Number of connected components before blockage.")
    components_after: int = Field(..., description="Number of connected components after blockage.")
    component_increase: int = Field(..., description="Net increase in disconnected components directly caused by blockage.")
    nodes_affected: int = Field(
        ...,
        description="Total number of nodes belonging to newly created disconnected components caused by the simulated blockage.",
    )
    edges_in_affected_components: int = Field(
        ...,
        description="Total number of remaining internal edges within newly created disconnected components (0 for singleton nodes).",
    )
    is_bridge_edge: bool = Field(
        ...,
        description="True if the blocked segment is a graph-theoretic bridge in the extracted subgraph.",
    )
    articulation_points_near_blockage: list[int] = Field(
        default_factory=list,
        description="OSM node IDs of articulation points directly adjacent to the blocked edge.",
    )


class AlternativeComponent(BaseModel):
    """Details of a newly disconnected subgraph component resulting from the blockage."""

    component_index: int = Field(
        ...,
        description="Deterministic 1-based index (ordered by node count descending, then min node ID).",
    )
    node_count: int = Field(..., description="Number of nodes isolated in this component.")
    edge_count: int = Field(..., description="Number of internal edges in this component.")


class GraphStats(BaseModel):
    """Summary topology statistics of the road subgraph."""

    total_nodes: int = Field(..., description="Total nodes in subgraph.")
    total_edges: int = Field(..., description="Total edges in subgraph.")
    connected_components: int = Field(..., description="Total connected components.")
    largest_component_nodes: int = Field(default=0, description="Node count of largest connected component.")


class RoadBlockageSimulationData(BaseModel):
    """Payload for the road blockage simulation response."""

    simulation_type: str = Field(
        default="WHAT_IF_SCENARIO",
        description="Simulation paradigm indicator.",
    )
    target_location: dict[str, float] = Field(
        ...,
        description="Coordinates of the epicenter/query point.",
    )
    subgraph_radius_m: float = Field(..., description="Radius used to extract the local road network subgraph.")
    blocked_edge: BlockedEdgeInfo = Field(..., description="Road segment selected for the blockage simulation.")
    connectivity_impact: ConnectivityImpact = Field(..., description="Network connectivity impact metrics.")
    isolation_severity: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Heuristic V1 isolation severity score [0-100] reflecting component fragmentation and affected node proportion.",
    )
    isolated_components: list[AlternativeComponent] = Field(
        default_factory=list,
        description="List of newly created disconnected components resulting from the blockage.",
    )
    graph_stats_before: GraphStats = Field(..., description="Graph metrics before blockage.")
    graph_stats_after: GraphStats = Field(..., description="Graph metrics after blockage.")
    summary_explanation: str = Field(..., description="Plain-language explanation of the simulation findings.")
    limitations: list[str] = Field(..., description="Explicit caveats and assumptions of the simulation.")



class RoadBlockageSimulationResponse(BaseModel):
    """Standard API success envelope for road blockage simulation."""

    data: RoadBlockageSimulationData
    meta: dict[str, Any] = Field(default_factory=dict)
