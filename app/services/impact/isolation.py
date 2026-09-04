"""
Road Isolation Simulation Service.

Non-destructive what-if analysis: simulates road blockages on an in-memory
copy of the NetworkX graph (Graph or MultiGraph) to identify disconnected components,
affected nodes/edges, and isolation severity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx
import structlog

logger = structlog.get_logger("risksetu.isolation")


@dataclass
class IsolationResult:
    """Result of a road blockage simulation."""

    blocked_edges: list[dict[str, Any]]
    components_before: int
    components_after: int
    component_increase: int
    nodes_affected: int
    edges_in_affected_components: int
    isolation_severity: float  # 0-100 bounded heuristic V1 score
    is_bridge_edge: bool
    articulation_points_near_blockage: list[int]
    alternative_components: list[dict[str, Any]]
    graph_stats_before: dict[str, Any]
    graph_stats_after: dict[str, Any]
    limitations: list[str]


class RoadIsolationSimulator:
    """Non-destructive road blockage what-if simulation engine."""

    @staticmethod
    def simulate_blockage(
        graph: nx.Graph | nx.MultiGraph,
        blocked_edges: list[tuple[int, int] | tuple[int, int, str]],
        subgraph_radius_m: float | None = None,
    ) -> IsolationResult:
        """Simulate blocking one or more road edges and analyze connectivity impact.

        Operates strictly on an in-memory copy (G_after = graph.copy()), guaranteeing
        zero side effects on the database or the original graph instance.

        Args:
            graph: Original NetworkX Graph or MultiGraph (NOT modified).
            blocked_edges: List of (u, v) or (u, v, key) tuples to block.
            subgraph_radius_m: Optional radius in meters for context in reported limitations.

        Returns:
            IsolationResult with mathematically verified connectivity metrics.
        """
        if graph.number_of_nodes() == 0:
            return IsolationResult(
                blocked_edges=[],
                components_before=0,
                components_after=0,
                component_increase=0,
                nodes_affected=0,
                edges_in_affected_components=0,
                isolation_severity=0.0,
                is_bridge_edge=False,
                articulation_points_near_blockage=[],
                alternative_components=[],
                graph_stats_before={"total_nodes": 0, "total_edges": 0, "connected_components": 0},
                graph_stats_after={"total_nodes": 0, "total_edges": 0, "connected_components": 0},
                limitations=["Graph is empty — no road data in the specified area."],
            )

        is_multigraph = isinstance(graph, nx.MultiGraph)

        # 1. Analyze BEFORE state
        comps_before = [frozenset(c) for c in nx.connected_components(graph)]
        num_components_before = len(comps_before)
        comps_before_set = set(comps_before)

        # Articulation points in the graph
        try:
            all_articulation_points = set(nx.articulation_points(graph))
        except Exception:
            all_articulation_points = set()

        # 2. Collect blocked edge metadata and prepare removal list
        blocked_edge_info: list[dict[str, Any]] = []
        edges_to_remove: list[tuple[int, int, str | None]] = []
        nearby_articulation: list[int] = []

        for edge_spec in blocked_edges:
            u = edge_spec[0]
            v = edge_spec[1]
            key = edge_spec[2] if len(edge_spec) > 2 else None

            has_edge = False
            edge_data: dict[str, Any] = {}

            if is_multigraph:
                if key is not None and graph.has_edge(u, v, key=key):
                    has_edge = True
                    edge_data = graph[u][v][key]
                elif graph.has_edge(u, v):
                    has_edge = True
                    # If key not provided, pick first edge between u and v
                    key_found, edge_data = next(iter(graph[u][v].items()))
                    if key is None:
                        key = key_found
            else:
                if graph.has_edge(u, v):
                    has_edge = True
                    edge_data = graph.edges[u, v]

            if has_edge:
                blocked_edge_info.append({
                    "from_node_id": u,
                    "to_node_id": v,
                    "edge_key": key,
                    "osm_way_id": edge_data.get("osm_way_id"),
                    "highway_class": edge_data.get("highway_class"),
                    "name": edge_data.get("name"),
                    "length_m": edge_data.get("length_m", 0.0),
                    "bridge": bool(edge_data.get("bridge", False)),  # OSM physical civil structure tag
                    "tunnel": bool(edge_data.get("tunnel", False)),
                })
                edges_to_remove.append((u, v, key))

                # Identify adjacent articulation cut nodes
                for node in (u, v):
                    if node in all_articulation_points and node not in nearby_articulation:
                        nearby_articulation.append(node)
            else:
                blocked_edge_info.append({
                    "from_node_id": u,
                    "to_node_id": v,
                    "edge_key": key,
                    "error": "Edge not found in graph",
                })

        if not edges_to_remove:
            return IsolationResult(
                blocked_edges=blocked_edge_info,
                components_before=num_components_before,
                components_after=num_components_before,
                component_increase=0,
                nodes_affected=0,
                edges_in_affected_components=0,
                isolation_severity=0.0,
                is_bridge_edge=False,
                articulation_points_near_blockage=[],
                alternative_components=[],
                graph_stats_before=_graph_stats(graph),
                graph_stats_after=_graph_stats(graph),
                limitations=["No valid edges found to block in the graph."],
            )

        # 3. Create strictly NON-DESTRUCTIVE in-memory copy and remove blocked edges
        G_after = graph.copy()
        for u, v, key in edges_to_remove:
            if is_multigraph and key is not None:
                if G_after.has_edge(u, v, key=key):
                    G_after.remove_edge(u, v, key=key)
            else:
                if G_after.has_edge(u, v):
                    G_after.remove_edge(u, v)

        # 4. Analyze AFTER state
        comps_after = [frozenset(c) for c in nx.connected_components(G_after)]
        num_components_after = len(comps_after)
        component_increase = max(0, num_components_after - num_components_before)

        # Graph-theoretic bridge: strictly defined as an edge whose removal increases component count
        is_bridge = (num_components_after > num_components_before)

        # Update blocked edge metadata with graph-theoretic bridge determination
        for info in blocked_edge_info:
            if "error" not in info:
                info["is_bridge_edge"] = is_bridge

        # 5. Component Partitioning & Attribution
        # Pre-existing components: components in G_after that are identical to components in G_before
        # Newly affected components: components in G_after that did not exist before the simulation
        newly_affected_components = [c for c in comps_after if c not in comps_before_set]

        # Sort newly affected components deterministically:
        # 1. Largest component first (node count descending)
        # 2. Minimum node ID ascending for stable tie-breaking
        newly_affected_components.sort(key=lambda c: (-len(c), min(c)))

        affected_components_list: list[dict[str, Any]] = []
        nodes_affected = 0
        edges_in_affected = 0

        for idx, comp_nodes in enumerate(newly_affected_components, start=1):
            subgraph = G_after.subgraph(comp_nodes)
            n_count = len(comp_nodes)
            e_count = subgraph.number_of_edges()
            nodes_affected += n_count
            edges_in_affected += e_count
            affected_components_list.append({
                "component_index": idx,
                "node_count": n_count,
                "edge_count": e_count,
            })

        # 6. Isolation Severity Score (Heuristic V1, bounded [0, 100])
        # Deterministic combination of component fragmentation and affected node ratio
        total_nodes = graph.number_of_nodes()
        if total_nodes > 0 and component_increase > 0 and nodes_affected > 0:
            frag_ratio = min(1.0, component_increase / max(num_components_before, 1))
            node_ratio = min(1.0, nodes_affected / total_nodes)
            # 40% weight on network fragmentation, 60% weight on proportion of nodes severed
            raw_severity = (0.40 * frag_ratio + 0.60 * node_ratio) * 100.0
            isolation_severity = round(min(100.0, max(0.0, raw_severity)), 2)
        else:
            isolation_severity = 0.0

        # 7. Explicit Limitations & Scientific Disclosures
        radius_str = f" within {subgraph_radius_m:.0f}m" if subgraph_radius_m else ""
        limitations = [
            "This is a WHAT-IF simulation based on the currently ingested routable subset of the northern-zone OSM extract (5,000 edges).",
            f"Analysis is strictly confined to the extracted road network subgraph{radius_str} of the target location.",
            "Road network coverage is limited to the prototype ingested OSM dataset and does not represent the full national road network.",
            "No real-time traffic data or actual road closure information is used.",
            "Population impact cannot be estimated — Census village locations lack spatial boundary coordinates.",
            "Evacuation routing is not modeled in Phase 2B.",
            "The simulation assumes complete edge removal; partial lane blockage or speed reductions are not modeled.",
            "Isolation severity score is a deterministic Heuristic V1 metric, not a scientifically calibrated disaster hazard index.",
        ]

        logger.info(
            "blockage_simulation_complete",
            blocked_count=len(edges_to_remove),
            components_before=num_components_before,
            components_after=num_components_after,
            component_increase=component_increase,
            nodes_affected=nodes_affected,
            edges_in_affected=edges_in_affected,
            is_bridge_edge=is_bridge,
            isolation_severity=isolation_severity,
        )

        return IsolationResult(
            blocked_edges=blocked_edge_info,
            components_before=num_components_before,
            components_after=num_components_after,
            component_increase=component_increase,
            nodes_affected=nodes_affected,
            edges_in_affected_components=edges_in_affected,
            isolation_severity=isolation_severity,
            is_bridge_edge=is_bridge,
            articulation_points_near_blockage=nearby_articulation,
            alternative_components=affected_components_list,
            graph_stats_before=_graph_stats(graph),
            graph_stats_after=_graph_stats(G_after),
            limitations=limitations,
        )


def _graph_stats(G: nx.Graph | nx.MultiGraph) -> dict[str, Any]:
    """Compute summary statistics for a NetworkX graph."""
    components = list(nx.connected_components(G))
    sizes = sorted([len(c) for c in components], reverse=True)
    return {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "connected_components": len(components),
        "largest_component_nodes": sizes[0] if sizes else 0,
    }
