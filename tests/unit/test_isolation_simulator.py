"""
Unit tests for Road Network Graph Builder and Isolation Simulation Service.
"""
from __future__ import annotations

import networkx as nx

from app.services.impact.isolation import RoadIsolationSimulator


def test_empty_graph_simulation():
    """Verify empty graph handles blockage gracefully without error."""
    G = nx.Graph()
    result = RoadIsolationSimulator.simulate_blockage(G, [(1, 2)])

    assert result.isolation_severity == 0.0
    assert result.components_before == 0
    assert result.components_after == 0
    assert result.nodes_affected == 0
    assert result.is_bridge_edge is False
    assert len(result.limitations) > 0


def test_case_a_connected_graph_bridge_split():
    """Case A: Connected graph -> bridge removed -> graph splits into newly created partitions."""
    # Graph: 1 -- 2 -- 3 -- 4
    G = nx.Graph()
    G.add_edge(1, 2, osm_way_id=101, highway_class="primary", length_m=500.0)
    G.add_edge(2, 3, osm_way_id=102, highway_class="secondary", length_m=300.0)
    G.add_edge(3, 4, osm_way_id=103, highway_class="tertiary", length_m=400.0)

    # Edge (2, 3) is a graph-theoretic bridge
    result = RoadIsolationSimulator.simulate_blockage(G, [(2, 3)])

    assert result.components_before == 1
    assert result.components_after == 2
    assert result.component_increase == 1
    assert result.is_bridge_edge is True
    assert result.nodes_affected == 4  # All 4 nodes belong to the newly severed partitions
    assert result.edges_in_affected_components == 2  # Edges (1,2) and (3,4)
    assert 0.0 < result.isolation_severity <= 100.0
    assert len(result.alternative_components) == 2

    # Verify non-destructive behavior: original graph G still has the edge (2, 3)
    assert G.has_edge(2, 3)
    assert G.number_of_nodes() == 4
    assert G.number_of_edges() == 3


def test_case_b_preexisting_disconnected_components_unaffected():
    """Case B: Pre-existing disconnected components are NOT falsely attributed to the blockage."""
    # Graph has 3 pre-existing components:
    # Comp 1: 1 -- 2
    # Comp 2: 3 -- 4 -- 5 -- 6
    # Comp 3: 7 (isolated singleton)
    G = nx.Graph()
    G.add_edge(1, 2, osm_way_id=201)
    G.add_edge(3, 4, osm_way_id=202)
    G.add_edge(4, 5, osm_way_id=203)
    G.add_edge(5, 6, osm_way_id=204)
    G.add_node(7)

    assert nx.number_connected_components(G) == 3

    # Remove bridge (4, 5) inside Component 2
    result = RoadIsolationSimulator.simulate_blockage(G, [(4, 5)])

    assert result.components_before == 3
    assert result.components_after == 4
    assert result.component_increase == 1
    assert result.is_bridge_edge is True

    # Nodes affected must ONLY count the nodes in the newly split component 2: {3, 4} and {5, 6} = 4 nodes
    # Pre-existing {1, 2} and {7} must NOT be counted!
    assert result.nodes_affected == 4
    assert result.edges_in_affected_components == 2  # Edge (3,4) and Edge (5,6)
    assert len(result.alternative_components) == 2

    # Verify returned components are only the newly affected ones
    affected_node_counts = sorted([c["node_count"] for c in result.alternative_components])
    assert affected_node_counts == [2, 2]


def test_case_c_cycle_non_bridge_removal():
    """Case C: Cycle -> non-bridge edge removed -> no new component created."""
    # Triangle cycle: 1 -- 2 -- 3 -- 1
    G = nx.Graph()
    G.add_edge(1, 2, osm_way_id=301, highway_class="primary", length_m=200.0)
    G.add_edge(2, 3, osm_way_id=302, highway_class="primary", length_m=200.0)
    G.add_edge(3, 1, osm_way_id=303, highway_class="primary", length_m=200.0)

    # Edge (1, 2) is in a cycle, NOT a bridge
    result = RoadIsolationSimulator.simulate_blockage(G, [(1, 2)])

    assert result.components_before == 1
    assert result.components_after == 1
    assert result.component_increase == 0
    assert result.is_bridge_edge is False
    assert result.isolation_severity == 0.0
    assert result.nodes_affected == 0
    assert result.edges_in_affected_components == 0
    assert len(result.alternative_components) == 0

    # Original graph still has all 3 edges
    assert G.has_edge(1, 2)
    assert G.number_of_edges() == 3


def test_case_d_singleton_components_preexisting_vs_new():
    """Case D: Distinguish pre-existing singleton nodes from singletons created by edge removal."""
    # Graph: (1 -- 2) and pre-existing isolated node (3)
    G = nx.Graph()
    G.add_edge(1, 2, osm_way_id=401)
    G.add_node(3)

    assert nx.number_connected_components(G) == 2

    # Remove edge (1, 2), turning {1} and {2} into newly created singletons
    result = RoadIsolationSimulator.simulate_blockage(G, [(1, 2)])

    assert result.components_before == 2
    assert result.components_after == 3
    assert result.component_increase == 1
    assert result.is_bridge_edge is True

    # Only nodes 1 and 2 are affected, NOT node 3
    assert result.nodes_affected == 2
    # For singletons, remaining internal edges is 0 (documented behavior)
    assert result.edges_in_affected_components == 0
    assert len(result.alternative_components) == 2
    assert result.alternative_components[0]["node_count"] == 1
    assert result.alternative_components[0]["edge_count"] == 0
    assert result.alternative_components[1]["node_count"] == 1
    assert result.alternative_components[1]["edge_count"] == 0


def test_parallel_edge_multigraph_support():
    """Verify MultiGraph preserves parallel edges and prevents false bridge detection."""
    MG = nx.MultiGraph()
    # Two distinct parallel roads between 1 and 2
    MG.add_edge(1, 2, key="road_a", osm_way_id=501, name="Bypass A")
    MG.add_edge(1, 2, key="road_b", osm_way_id=502, name="Bypass B")
    # Road from 2 to 3
    MG.add_edge(2, 3, key="road_c", osm_way_id=503, name="Main Road")

    assert MG.number_of_edges() == 3
    assert nx.number_connected_components(MG) == 1

    # Block Road A only
    result_a = RoadIsolationSimulator.simulate_blockage(MG, [(1, 2, "road_a")])

    # Since Road B still connects 1 and 2, the network is NOT partitioned!
    assert result_a.components_before == 1
    assert result_a.components_after == 1
    assert result_a.component_increase == 0
    assert result_a.is_bridge_edge is False
    assert result_a.isolation_severity == 0.0
    assert result_a.nodes_affected == 0

    # If BOTH Road A and Road B are blocked, the network partitions
    result_both = RoadIsolationSimulator.simulate_blockage(MG, [(1, 2, "road_a"), (1, 2, "road_b")])
    assert result_both.components_after == 2
    assert result_both.is_bridge_edge is True
    assert result_both.nodes_affected == 3


def test_deterministic_component_ordering():
    """Verify alternative_components ordering is 100% deterministic across repeated runs."""
    G = nx.Graph()
    # Star with branches of different sizes:
    # Center: 0
    # Branch 1: 0 -- 1 -- 2 (size 2)
    # Branch 2: 0 -- 3 -- 4 -- 5 (size 3)
    G.add_edge(0, 1)
    G.add_edge(1, 2)
    G.add_edge(0, 3)
    G.add_edge(3, 4)
    G.add_edge(4, 5)

    # Cut edge (0, 3): splits into {0, 1, 2} (size 3) and {3, 4, 5} (size 3)
    res1 = RoadIsolationSimulator.simulate_blockage(G, [(0, 3)])
    res2 = RoadIsolationSimulator.simulate_blockage(G, [(0, 3)])

    assert res1.alternative_components == res2.alternative_components
    # Component indices must be 1, 2 (1-based deterministic index)
    assert res1.alternative_components[0]["component_index"] == 1
    assert res1.alternative_components[1]["component_index"] == 2
    # Sorted by (-node_count, min_node_id):
    # Both have node_count 3. min node of {0,1,2} is 0; min node of {3,4,5} is 3.
    # Therefore {0,1,2} must come first!
    assert res1.alternative_components[0]["node_count"] == 3


def test_severity_score_boundaries():
    """Verify isolation severity score is strictly bounded [0, 100] and monotonically behaves."""
    G = nx.Graph()
    G.add_edge(1, 2)

    # Empty graph
    empty_res = RoadIsolationSimulator.simulate_blockage(nx.Graph(), [(1, 2)])
    assert empty_res.isolation_severity == 0.0

    # Non-bridge (cycle)
    cycle_G = nx.cycle_graph(4)
    cycle_res = RoadIsolationSimulator.simulate_blockage(cycle_G, [(0, 1)])
    assert cycle_res.isolation_severity == 0.0

    # Bridge in 2-node graph:
    # components_before = 1, components_after = 2 (+1), nodes_affected = 2 / 2 (100%)
    # frag_ratio = 1.0, node_ratio = 1.0 -> (0.40 * 1.0 + 0.60 * 1.0) * 100 = 100.0
    res_max = RoadIsolationSimulator.simulate_blockage(G, [(1, 2)])
    assert res_max.isolation_severity == 100.0

    # Intermediate score in larger network with multiple components
    # 2 components of 10 nodes each (total 20 nodes).
    # Cutting an edge in Component 1 affects 10 nodes out of 20.
    G_multi = nx.Graph()
    for i in range(9):
        G_multi.add_edge(i, i + 1)
    for i in range(10, 19):
        G_multi.add_edge(i, i + 1)

    assert G_multi.number_of_nodes() == 20
    assert nx.number_connected_components(G_multi) == 2

    res_inter = RoadIsolationSimulator.simulate_blockage(G_multi, [(0, 1)])
    assert 0.0 < res_inter.isolation_severity < 100.0
    assert res_inter.isolation_severity == 50.0
    assert res_inter.nodes_affected == 10



def test_physical_bridge_vs_graph_bridge_distinction():
    """Verify physical OSM bridge tag is kept completely distinct from graph cut edge."""
    G = nx.Graph()
    # Physical bridge that is in a cycle (NOT a graph bridge)
    G.add_edge(1, 2, osm_way_id=601, bridge=True)
    G.add_edge(2, 3, osm_way_id=602, bridge=False)
    G.add_edge(3, 1, osm_way_id=603, bridge=False)

    res = RoadIsolationSimulator.simulate_blockage(G, [(1, 2)])
    # Blocked edge was physically a bridge
    assert res.blocked_edges[0]["bridge"] is True
    # But topologically it was NOT a bridge (graph did not partition)
    assert res.is_bridge_edge is False
    assert res.blocked_edges[0]["is_bridge_edge"] is False

    # Conversely: non-physical bridge that IS a graph bridge
    G2 = nx.path_graph(3)  # 0 -- 1 -- 2
    G2.edges[0, 1]["bridge"] = False
    res2 = RoadIsolationSimulator.simulate_blockage(G2, [(0, 1)])
    assert res2.blocked_edges[0]["bridge"] is False
    assert res2.is_bridge_edge is True
    assert res2.blocked_edges[0]["is_bridge_edge"] is True


def test_nonexistent_edge_blockage():
    """Verify attempting to block an edge not present in the graph returns safe result."""
    G = nx.Graph()
    G.add_edge(1, 2, osm_way_id=701, highway_class="residential", length_m=100.0)

    result = RoadIsolationSimulator.simulate_blockage(G, [(5, 6)])

    assert result.components_before == 1
    assert result.components_after == 1
    assert result.component_increase == 0
    assert result.isolation_severity == 0.0
    assert result.is_bridge_edge is False
    assert len(result.limitations) > 0
