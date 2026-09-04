# RISKSETU AI — PHASE 2B RUNTIME VERIFICATION & HARDENING REPORT

**Document ID:** `PHASE-2B-RUNTIME-VERIFICATION`  
**System:** RISKSETU AI — Cascading Road Isolation & Connectivity Impact Simulation Engine  
**Hackathon Target:** Smart India Hackathon (SIH) 2026 | PS ID: 26001  
**Verification Date:** 2026-09-04  
**Engine Version:** `impact-v1` (`v1.0.0-deterministic`)  
**Execution Environment:** macOS (Darwin arm64) | PostgreSQL 17.11 + PostGIS 3.6.4 | Python 3.11.16 | FastAPI 0.115.6 | NetworkX 3.3

---

## 1. Executive Status Summary

This document certifies the final hardening, correctness verification, and runtime certification of **Phase 2B: Cascading Road Isolation & Connectivity Impact Simulation Engine**.

### Hardening & Correctness Highlights
1. **NetworkX MultiGraph Architecture:**
   - Evaluated simple graph vs multigraph. Confirmed authentic OSM data contains parallel road segments between identical node pairs (e.g. Ways 22800005 & 22800006 between nodes 245134975 and 245135193).
   - Migrated to `nx.MultiGraph` keyed by database UUID `key=str(edge.id)`. Parallel bypass segments are preserved without data loss or false bridge determinations.
2. **Bridge Semantics Disambiguation:**
   - Physical civil engineering structures (OSM tag `bridge=yes`) and graph-theoretic bridges (cut edges whose removal strictly increases connected components $\kappa(G \setminus \{e\}) > \kappa(G)$) are strictly decoupled and separately exposed.
3. **Mathematically Pure Component Attribution:**
   - Pre-existing disconnected components ($C \in \mathcal{C}_{\text{after}} \cap \mathcal{C}_{\text{before}}$) are completely excluded from causal attribution.
   - `isolated_components` contains strictly newly created components ($C \in \mathcal{C}_{\text{after}} \setminus \mathcal{C}_{\text{before}}$).
   - Components are ordered deterministically by node count descending and minimum node ID.
4. **Exact Metric Definitions:**
   - `nodes_affected`: Number of nodes belonging to newly created disconnected components caused by the simulated blockage.
   - `edges_in_affected_components`: Exact internal edge count in newly created components (0 for singleton node partitions).
5. **Non-Destructive Database Immutability:**
   - Verified via automated integration tests that PostgreSQL tables (`road_network_edges`, `road_network_nodes`) remain 100% immutable across all simulation runs.
6. **Heuristic V1 Isolation Severity Formula:**
   - Deterministic and strictly bounded in $[0, 100]$:
     $$\text{Severity} = \text{round}\left((0.40 \cdot \text{frag\_ratio} + 0.60 \cdot \text{node\_ratio}) \times 100.0, 2\right)$$
     where $\text{frag\_ratio} = \min(1.0, \Delta \text{components} / \text{components}_{\text{before}})$ and $\text{node\_ratio} = \min(1.0, \text{nodes\_affected} / \text{total\_nodes})$.
7. **Comprehensive Test Suite & Zero Regressions:**
   - **72 of 72 automated tests passing** in `pytest` (100% pass rate).
   - Ruff linting: **0 errors**.
   - Mypy static typing: **0 errors** across 56 source files.
   - Bytecode compilation: `python -m compileall -q app` passed.

---

## 2. Real Transportation Network Data Status

### 2.1 Table Row Counts (Verified against PostgreSQL)
```sql
SELECT 'road_network_nodes' AS table_name, count(*) AS row_count FROM road_network_nodes
UNION ALL SELECT 'road_network_edges', count(*) FROM road_network_edges;
```

| Table Name | Record Count | Geometry Type | Data Origin |
|---|---|---|---|
| `road_network_nodes` | **122,883** | `POINT(lon, lat)` SRID 4326 | OpenStreetMap Northern Zone PBF (`DenseNodes`) |
| `road_network_edges` | **5,000** | `LINESTRING(...)` SRID 4326 | Routable highway ways (`trunk`, `primary`, `secondary`, etc.) |

### 2.2 Sample Ingested Road Segments
```text
Sample 1: Mahatma Gandhi Marg
  - Edge UUID: 83dd0498-e314-462d-983d-c54417b41864
  - OSM Way ID: 5873630
  - Highway Class: trunk
  - Length: 788.60 meters
  - Geometry: LINESTRING(77.2309078 28.6723292, 77.2306578 28.6733179, ...)

Sample 2: Ferozepur Road
  - Edge UUID: 72eceb55-fbec-48e2-a5a3-3b46f7e141f8
  - OSM Way ID: 5873808
  - Highway Class: trunk_link
  - Length: 233.04 meters
  - Geometry: LINESTRING(74.5911900 30.9430943, 74.5914679 30.9433030, ...)

Sample 3 (Parallel Pair):
  - Way ID 22800005 (9ebb16de-56de-4ff4-a902-cd4003c85b61): tertiary, 905.33m between nodes (245134975, 245135193)
  - Way ID 22800006 (ca0db24c-739c-4b95-b374-09f0e83fcca8): tertiary, 455.97m between nodes (245134975, 245135193)
```

---

## 3. Graph Model & Topology Semantics

### 3.1 NetworkX Graph Representation
- **Class:** `nx.MultiGraph` (undirected multi-graph).
- **Node Identifier:** OpenStreetMap node ID (`osm_node_id: int`).
- **Edge Key:** Database UUID (`str(edge.id)`).
- **Rationale:** Authentic road data features dual carriageways, slip ramps, and alternate loops sharing the same intersection node pair. A standard `nx.Graph` would collapse these segments into a single edge, causing false bridge detections. `nx.MultiGraph` models each physical road segment independently.

### 3.2 Bridge Semantics Distinction
- **OSM Tag `bridge: bool`:** Physical civil infrastructure bridge structure recorded in OpenStreetMap (`bridge=yes`).
- **Graph Cut Edge `is_bridge_edge: bool`:** Graph-theoretic bridge: removal of this segment strictly increases connected components ($\kappa(G_{\text{after}}) > \kappa(G_{\text{before}})$).
- Both concepts are distinct in schemas, code, and response payloads.

### 3.3 Component Attribution & Definitions
- **Pre-existing components:** $\mathcal{C}_{\text{pre}} = \{ C \in \mathcal{C}_{\text{after}} : C \in \mathcal{C}_{\text{before}} \}$. Untouched by the simulation; excluded from all impact counts.
- **Newly affected components:** $\mathcal{C}_{\text{new}} = \{ C \in \mathcal{C}_{\text{after}} : C \notin \mathcal{C}_{\text{before}} \}$.
- **`nodes_affected`:** $\sum_{C \in \mathcal{C}_{\text{new}}} |C|$. Total count of nodes in newly partitioned subgraphs.
- **`edges_in_affected_components`:** $\sum_{C \in \mathcal{C}_{\text{new}}} |E(G_{\text{after}}[C])|$. Internal edges remaining inside newly created subgraphs (0 for isolated singleton nodes).
- **`isolated_components` ordering:** Deterministically sorted by `(-len(c), min(c))` with stable 1-based indices.

---

## 4. End-to-End API Runtime Verification

### 4.1 Real Road Coordinate Test (Nearest-Edge Resolution)
**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/impact/simulate-road-blockage \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 28.6723,
    "longitude": 77.2309,
    "radius_m": 3000.0,
    "search_radius_m": 1000.0
  }'
```

**Actual Response Payload (Status 200 OK):**
```json
{
  "data": {
    "simulation_type": "WHAT_IF_SCENARIO",
    "target_location": {
      "latitude": 28.6723,
      "longitude": 77.2309
    },
    "subgraph_radius_m": 3000.0,
    "blocked_edge": {
      "edge_db_id": "83dd0498-e314-462d-983d-c54417b41864",
      "osm_way_id": 5873630,
      "from_node_id": 12211581303,
      "to_node_id": 2001957701,
      "highway_class": "trunk",
      "name": "Mahatma Gandhi Marg",
      "length_m": 788.6,
      "bridge": false,
      "tunnel": false,
      "is_bridge_edge": true,
      "distance_from_target_m": 3.32,
      "error": null
    },
    "connectivity_impact": {
      "components_before": 18,
      "components_after": 19,
      "component_increase": 1,
      "nodes_affected": 2,
      "edges_in_affected_components": 0,
      "is_bridge_edge": true,
      "articulation_points_near_blockage": []
    },
    "isolation_severity": 5.22,
    "isolated_components": [
      {
        "component_index": 1,
        "node_count": 1,
        "edge_count": 0
      },
      {
        "component_index": 2,
        "node_count": 1,
        "edge_count": 0
      }
    ],
    "graph_stats_before": {
      "total_nodes": 40,
      "total_edges": 22,
      "connected_components": 18,
      "largest_component_nodes": 4
    },
    "graph_stats_after": {
      "total_nodes": 40,
      "total_edges": 21,
      "connected_components": 19,
      "largest_component_nodes": 4
    },
    "summary_explanation": "Simulated blockage of Mahatma Gandhi Marg (OSM Way 5873630) severed connectivity. Network partitions increased from 18 to 19 (+1 isolated components). The segment is a graph-theoretic bridge. 2 nodes across 0 internal road segments are newly isolated. Isolation severity is rated at 5.2/100.",
    "limitations": [
      "This is a WHAT-IF simulation based on the currently ingested routable subset of the northern-zone OSM extract (5,000 edges).",
      "Analysis is strictly confined to the extracted road network subgraph within 3000m of the target location.",
      "Road network coverage is limited to the prototype ingested OSM dataset and does not represent the full national road network.",
      "No real-time traffic data or actual road closure information is used.",
      "Population impact cannot be estimated — Census village locations lack spatial boundary coordinates.",
      "Evacuation routing is not modeled in Phase 2B.",
      "The simulation assumes complete edge removal; partial lane blockage or speed reductions are not modeled.",
      "Isolation severity score is a deterministic Heuristic V1 metric, not a scientifically calibrated disaster hazard index."
    ]
  },
  "meta": {
    "request_id": "ba549236-99a9-4eb3-954e-611c81eae747"
  }
}
```

### 4.2 Explicit Edge UUID Test
- **UUID:** `83dd0498-e314-462d-983d-c54417b41864`
- **Result:** Status 200 OK. Matches targeted edge directly, eliminates nearest-edge search.

### 4.3 Database Immutability Test
- Pre-simulation: `road_network_edges: 5,000`, `road_network_nodes: 122,883`.
- Post-simulation: `road_network_edges: 5,000`, `road_network_nodes: 122,883`.
- Target edge record verified identical field-by-field (`osm_way_id`, `length_m`, `geom`, `name`). Zero database writes.

### 4.4 Repeatability & Determinism Test
- Two identical requests executed sequentially. Output structural metrics, node counts, component lists, and isolation severity match 100%.

---

## 5. Performance Verification (25-Iteration Benchmark)

Measured against the live PostgreSQL + PostGIS database:

| Component / Step | Median Latency | p95 Latency | Min Latency | Max Latency |
|---|---|---|---|---|
| **1. Nearest-edge PostGIS query** (`ST_Distance` on Geography) | **60.75 ms** | 127.60 ms | 60.14 ms | 137.93 ms |
| **2. Subgraph edges PostGIS query** (`ST_DWithin` 3km radius) | **59.14 ms** | 59.62 ms | 58.88 ms | 66.30 ms |
| **3. Node loading query** (Batch `osm_node_id IN (...)`) | **0.92 ms** | 0.99 ms | 0.84 ms | 0.99 ms |
| **4. NetworkX MultiGraph construction** | **0.09 ms** | 0.10 ms | 0.08 ms | 0.10 ms |
| **5/6. Simulation (Bridges, cuts, components)** | **0.39 ms** | 0.43 ms | 0.38 ms | 0.51 ms |
| **7. Complete API request (HTTP End-to-End)** | **124.08 ms** | **126.29 ms** | 123.38 ms | 126.64 ms |

*Note: Graph operations (MultiGraph construction and simulation) complete in <0.5ms. The dominant latency contributor (~120ms total) is the two PostGIS spatial queries, which are well within real-time SLA thresholds.*

---

## 6. Automated Test Suite Results

```text
============================= test session starts ==============================
platform darwin -- Python 3.11.16, pytest-8.4.2, pluggy-1.6.0
rootdir: /Users/yashgautam/Desktop/risksetu
configfile: pyproject.toml
testpaths: tests
plugins: asyncio-0.24.0, cov-5.0.0, Faker-28.4.1, anyio-4.15.0

tests/integration/test_impact_api.py .......                             [  9%]
tests/unit/test_census_streaming.py ..                                   [ 12%]
tests/unit/test_cli_commands.py .                                        [ 13%]
tests/unit/test_config.py .......                                        [ 23%]
tests/unit/test_db_models.py ....                                        [ 29%]
tests/unit/test_errors.py .....                                          [ 36%]
tests/unit/test_gsi_ingestion.py ..                                      [ 38%]
tests/unit/test_health.py .....                                          [ 45%]
tests/unit/test_isolation_simulator.py ..........                        [ 59%]
tests/unit/test_logging.py ...                                           [ 63%]
tests/unit/test_osm_ingestion.py ..                                      [ 66%]
tests/unit/test_rainfall_ingestion.py ..                                 [ 69%]
tests/unit/test_redis.py ...                                             [ 73%]
tests/unit/test_request_id.py .....                                      [ 80%]
tests/unit/test_risk_engine.py ............                              [ 97%]
tests/unit/test_security.py ..                                           [100%]

======================== 72 passed, 3 warnings in 1.43s ========================
```

- **Ruff:** `poetry run ruff check app tests` -> `All checks passed!`
- **Mypy:** `poetry run mypy app/` -> `Success: no issues found in 56 source files`
- **Compileall:** `python -m compileall -q app` -> `0 errors`

---

## 7. Limitations & Honest Disclosures

1. **WHAT-IF Simulation Only:** All blockage simulations are counterfactual what-if scenarios modeled on an in-memory graph.
2. **5,000-Edge Routable Subset:** Road network coverage is limited to the prototype ingested subset of the northern-zone OSM extract (5,000 edges, 122,883 nodes), not the entire national road network.
3. **Local Subgraph Scope:** Simulation is strictly confined to the extracted road network subgraph within the requested radius (`subgraph_radius_m`).
4. **No Real-Time Traffic or Closure Feeds:** The model does not integrate live Google Maps, Waze, or sensor traffic feeds.
5. **No Direct Population Linkage:** Census 2011 village demographics lack spatial boundary polygons in source data; population isolation counts are omitted to avoid speculation.
6. **Heuristic V1 Severity Index:** The 0–100 isolation severity score is a deterministic topological heuristic, not a scientifically calibrated disaster hazard index.
