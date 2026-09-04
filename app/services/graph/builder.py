"""
Road Network Graph Construction Service.

Builds NetworkX graphs from PostGIS road_network_edges/nodes for
connectivity analysis and what-if isolation simulation.
"""
from __future__ import annotations

from typing import Any

import networkx as nx
from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session
import structlog

from app.models.road import RoadNetworkEdge, RoadNetworkNode

logger = structlog.get_logger("risksetu.graph_builder")


class RoadGraphBuilder:
    """Constructs NetworkX graphs from PostGIS road network data."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def build_local_subgraph(
        self,
        latitude: float,
        longitude: float,
        radius_m: float = 5000.0,
    ) -> nx.Graph:
        """Build a NetworkX graph from road edges within a radius of target coordinates.

        Uses PostGIS ST_DWithin (geography cast) for accurate metre-based filtering.

        Args:
            latitude: WGS84 latitude of the center point.
            longitude: WGS84 longitude of the center point.
            radius_m: Search radius in meters (default 5km).

        Returns:
            NetworkX undirected Graph with osm_node_ids as nodes and edge attributes.
        """
        logger.info(
            "building_local_subgraph",
            lat=latitude,
            lon=longitude,
            radius_m=radius_m,
        )

        # Query edges within radius using ST_DWithin with geography cast
        target_point = func.ST_SetSRID(
            func.ST_MakePoint(longitude, latitude), 4326
        )

        stmt = (
            select(RoadNetworkEdge)
            .where(
                func.ST_DWithin(
                    cast(RoadNetworkEdge.geom, Geography),
                    cast(target_point, Geography),
                    radius_m,
                )
            )
        )
        edges = self.db.scalars(stmt).all()


        # Build multi-graph (MultiGraph preserves parallel road segments between identical node pairs)
        G = nx.MultiGraph()

        # Collect unique node IDs from edges
        node_ids_needed: set[int] = set()
        for edge in edges:
            node_ids_needed.add(edge.from_node_id)
            node_ids_needed.add(edge.to_node_id)

        # Fetch node coordinates
        if node_ids_needed:
            node_stmt = (
                select(
                    RoadNetworkNode.osm_node_id,
                    func.ST_X(RoadNetworkNode.geom).label("lon"),
                    func.ST_Y(RoadNetworkNode.geom).label("lat"),
                )

                .where(RoadNetworkNode.osm_node_id.in_(node_ids_needed))
            )
            node_rows = self.db.execute(node_stmt).all()
            for osm_id, lon, lat in node_rows:
                G.add_node(osm_id, pos=(lon, lat))

        # Add edges with attributes, using database UUID as the unique multigraph edge key
        for edge in edges:
            # Ensure both nodes exist in graph (may lack coordinates)
            if not G.has_node(edge.from_node_id):
                G.add_node(edge.from_node_id)
            if not G.has_node(edge.to_node_id):
                G.add_node(edge.to_node_id)

            edge_key = str(edge.id)
            G.add_edge(
                edge.from_node_id,
                edge.to_node_id,
                key=edge_key,
                edge_db_id=edge_key,
                osm_way_id=edge.osm_way_id,
                highway_class=edge.highway_class,
                length_m=edge.length_m,
                name=edge.name,
                bridge=edge.bridge,
                tunnel=edge.tunnel,
                oneway=edge.oneway,
            )

        logger.info(
            "local_subgraph_built",
            nodes=G.number_of_nodes(),
            edges=G.number_of_edges(),
            components=nx.number_connected_components(G),
        )

        return G


    def find_nearest_edge(
        self,
        latitude: float,
        longitude: float,
        search_radius_m: float = 500.0,
    ) -> dict[str, Any] | None:
        """Find the nearest road edge to given coordinates using PostGIS.

        Returns edge metadata dict or None if no edge found within radius.
        """
        target_point = func.ST_SetSRID(
            func.ST_MakePoint(longitude, latitude), 4326
        )

        dist_expr = func.ST_Distance(
            cast(RoadNetworkEdge.geom, Geography),
            cast(target_point, Geography),
        ).label("distance_m")

        stmt = (
            select(
                RoadNetworkEdge,
                dist_expr,
            )
            .where(
                func.ST_DWithin(
                    cast(RoadNetworkEdge.geom, Geography),
                    cast(target_point, Geography),
                    search_radius_m,
                )
            )
            .order_by(dist_expr)
            .limit(1)
        )

        row = self.db.execute(stmt).first()

        if not row:
            return None

        edge, distance_m = row
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
            "distance_from_target_m": round(distance_m, 2),
        }

    @staticmethod
    def get_graph_stats(G: nx.Graph) -> dict[str, Any]:
        """Return summary statistics for a NetworkX graph."""
        components = list(nx.connected_components(G))
        component_sizes = sorted([len(c) for c in components], reverse=True)
        return {
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "connected_components": len(components),
            "largest_component_nodes": component_sizes[0] if component_sizes else 0,
            "component_size_distribution": component_sizes[:10],
        }
