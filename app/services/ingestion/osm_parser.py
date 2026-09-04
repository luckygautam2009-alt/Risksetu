"""
OpenStreetMap Protocolbuffer Binary Format (OSM PBF) streaming parser.

Extracts routable road ways, highway classifications, topology nodes, and computes
metric segment lengths for graph modeling from database/northern-zone-260903.osm.pbf.

Two-pass architecture:
  Pass 1 — collect_node_coordinates(): streams DenseNodes to build osm_node_id → (lon, lat) map
  Pass 2 — parse_road_ways_with_coords(): resolves way node refs → real coordinates + haversine length
"""
from __future__ import annotations

import collections
from dataclasses import dataclass
import math
import struct
from typing import Any, Iterator
import zlib

import structlog

logger = structlog.get_logger("risksetu.osm_parser")


@dataclass
class OSMNodeRecord:
    osm_node_id: int
    latitude: float
    longitude: float


@dataclass
class OSMEdgeRecord:
    osm_way_id: int
    from_node_id: int
    to_node_id: int
    highway_class: str
    name: str | None
    oneway: bool
    maxspeed: int | None
    bridge: bool
    tunnel: bool
    layer: int
    surface: str | None
    access: str | None
    length_m: float
    coordinates: list[tuple[float, float]]  # [(lon, lat), ...]


class OSMPBFParser:
    """Streaming parser for OSM PBF files."""

    HIGHWAY_CLASSES = {
        "motorway", "trunk", "primary", "secondary", "tertiary",
        "unclassified", "residential", "service", "track", "living_street",
        "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link",
    }

    def __init__(self, pbf_path: str) -> None:
        self.pbf_path = pbf_path

    @staticmethod
    def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
        res = 0
        shift = 0
        while True:
            b = data[pos]
            pos += 1
            res |= (b & 0x7F) << shift
            shift += 7
            if not (b & 0x80):
                break
        return res, pos

    @staticmethod
    def _decode_sint64(raw: int) -> int:
        """Decode a ZigZag-encoded sint64 value."""
        return (raw >> 1) ^ (-(raw & 1))

    @classmethod
    def _parse_protobuf_fields(cls, data: bytes) -> dict[int, list[Any]]:
        pos = 0
        fields: dict[int, list[Any]] = collections.defaultdict(list)
        while pos < len(data):
            tag, pos = cls._read_varint(data, pos)
            wire_type = tag & 0x07
            field_num = tag >> 3
            if wire_type == 0:  # varint
                v_int, pos = cls._read_varint(data, pos)
                fields[field_num].append(v_int)
            elif wire_type == 1:  # 64-bit
                v_float = struct.unpack("<d", data[pos:pos + 8])[0]
                pos += 8
                fields[field_num].append(v_float)
            elif wire_type == 2:  # length-delimited
                length, pos = cls._read_varint(data, pos)
                v_bytes = data[pos:pos + length]
                pos += length
                fields[field_num].append(v_bytes)
            elif wire_type == 5:  # 32-bit
                v_uint = struct.unpack("<I", data[pos:pos + 4])[0]
                pos += 4
                fields[field_num].append(v_uint)
            else:
                break
        return fields

    @staticmethod
    def _unpack_packed_varints(data: bytes) -> list[int]:
        """Unpack a packed repeated varint field."""
        values: list[int] = []
        pos = 0
        while pos < len(data):
            res = 0
            shift = 0
            while True:
                b = data[pos]
                pos += 1
                res |= (b & 0x7F) << shift
                shift += 7
                if not (b & 0x80):
                    break
            values.append(res)
        return values

    @staticmethod
    def _unpack_packed_sint64s(data: bytes) -> list[int]:
        """Unpack a packed repeated sint64 (zigzag) field."""
        values: list[int] = []
        pos = 0
        while pos < len(data):
            res = 0
            shift = 0
            while True:
                b = data[pos]
                pos += 1
                res |= (b & 0x7F) << shift
                shift += 7
                if not (b & 0x80):
                    break
            values.append((res >> 1) ^ (-(res & 1)))
        return values

    @staticmethod
    def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """Calculate great-circle distance between two points in meters."""
        r = 6371000.0  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return r * c

    def _iter_osm_blocks(self) -> Iterator[tuple[str, bytes]]:
        """Iterate over raw decompressed OSMData blocks from the PBF file."""
        with open(self.pbf_path, "rb") as f:
            while True:
                header_len_bytes = f.read(4)
                if not header_len_bytes or len(header_len_bytes) < 4:
                    break
                header_len = struct.unpack(">I", header_len_bytes)[0]
                blob_header_data = f.read(header_len)
                blob_header = self._parse_protobuf_fields(blob_header_data)

                block_type = blob_header.get(1, [b""])[0].decode("utf-8", errors="ignore")
                blob_size = blob_header.get(3, [0])[0]

                blob_data = f.read(blob_size)
                blob = self._parse_protobuf_fields(blob_data)

                raw_data = None
                if 1 in blob:
                    raw_data = blob[1][0]
                elif 3 in blob:
                    raw_data = zlib.decompress(blob[3][0])

                if raw_data and block_type == "OSMData":
                    yield block_type, raw_data

    # -------------------------------------------------------------------------
    # Pass 1: Collect Node Coordinates
    # -------------------------------------------------------------------------
    def collect_node_coordinates(
        self,
        required_node_ids: set[int] | None = None,
    ) -> dict[int, tuple[float, float]]:
        """Extract node coordinates from DenseNodes in all OSMData blocks.

        Returns dict mapping osm_node_id → (longitude, latitude).
        If required_node_ids is provided, only those nodes are kept (memory optimization).
        """
        node_coords: dict[int, tuple[float, float]] = {}
        blocks_processed = 0

        for _, raw_data in self._iter_osm_blocks():
            pblock = self._parse_protobuf_fields(raw_data)

            # PrimitiveBlock header: granularity (field 17), lat_offset (19), lon_offset (20)
            granularity = pblock.get(17, [100])[0]
            lat_offset = pblock.get(19, [0])[0]
            lon_offset = pblock.get(20, [0])[0]

            for pg_bytes in pblock.get(2, []):
                pg = self._parse_protobuf_fields(pg_bytes)

                # DenseNodes = field 2 in PrimitiveGroup
                for dense_bytes in pg.get(2, []):
                    dense = self._parse_protobuf_fields(dense_bytes)

                    # Field 1: packed delta-encoded IDs (sint64)
                    ids_data = dense.get(1, [b""])[0]
                    if not ids_data or not isinstance(ids_data, bytes):
                        continue

                    # Field 8: packed delta-encoded latitudes (sint64)
                    lat_data = dense.get(8, [b""])[0]
                    # Field 9: packed delta-encoded longitudes (sint64)
                    lon_data = dense.get(9, [b""])[0]

                    if not lat_data or not lon_data:
                        continue

                    ids = self._unpack_packed_sint64s(ids_data)
                    lats = self._unpack_packed_sint64s(lat_data)
                    lons = self._unpack_packed_sint64s(lon_data)

                    # Decode delta-encoded values
                    curr_id = 0
                    curr_lat = 0
                    curr_lon = 0

                    for i in range(min(len(ids), len(lats), len(lons))):
                        curr_id += ids[i]
                        curr_lat += lats[i]
                        curr_lon += lons[i]

                        # Convert to degrees: (offset + granularity * value) * 1e-9
                        lat_deg = (lat_offset + granularity * curr_lat) * 1e-9
                        lon_deg = (lon_offset + granularity * curr_lon) * 1e-9

                        if required_node_ids is None or curr_id in required_node_ids:
                            node_coords[curr_id] = (lon_deg, lat_deg)

            blocks_processed += 1

        logger.info(
            "node_coordinates_collected",
            blocks_processed=blocks_processed,
            nodes_found=len(node_coords),
        )
        return node_coords

    # -------------------------------------------------------------------------
    # Pass 1.5: Collect Required Node IDs from Road Ways
    # -------------------------------------------------------------------------
    def collect_road_node_ids(
        self,
        allowed_highways: set[str] | None = None,
        limit: int | None = None,
    ) -> set[int]:
        """Quick pass to collect all node IDs referenced by road ways."""
        if allowed_highways is None:
            allowed_highways = self.HIGHWAY_CLASSES

        node_ids: set[int] = set()
        way_count = 0

        for way_dict, node_refs in self.parse_road_ways(
            allowed_highways=allowed_highways,
            limit=limit,
        ):
            node_ids.update(node_refs)
            way_count += 1

        logger.info(
            "road_node_ids_collected",
            ways_scanned=way_count,
            unique_nodes=len(node_ids),
        )
        return node_ids

    # -------------------------------------------------------------------------
    # Pass 2: Parse Road Ways with Real Coordinates
    # -------------------------------------------------------------------------
    def parse_road_ways_with_coords(
        self,
        node_coords: dict[int, tuple[float, float]],
        allowed_highways: set[str] | None = None,
        limit: int | None = None,
    ) -> Iterator[OSMEdgeRecord]:
        """Stream road ways with resolved real coordinates and computed length.

        Args:
            node_coords: Pre-built map from collect_node_coordinates()
            allowed_highways: Set of highway types to include
            limit: Maximum number of ways to yield
        """
        resolved = 0
        skipped_no_coords = 0

        for way_dict, node_refs in self.parse_road_ways(
            allowed_highways=allowed_highways,
            limit=None,  # We manage our own limit after filtering
        ):
            # Resolve node refs to coordinates
            coords: list[tuple[float, float]] = []
            for nid in node_refs:
                if nid in node_coords:
                    coords.append(node_coords[nid])

            # Need at least 2 resolved coordinates for a valid linestring
            if len(coords) < 2:
                skipped_no_coords += 1
                continue

            # Compute total haversine length
            total_length = 0.0
            for i in range(len(coords) - 1):
                lon1, lat1 = coords[i]
                lon2, lat2 = coords[i + 1]
                total_length += self.haversine_distance(lon1, lat1, lon2, lat2)

            yield OSMEdgeRecord(
                osm_way_id=way_dict["way_id"],
                from_node_id=node_refs[0],
                to_node_id=node_refs[-1],
                highway_class=way_dict["highway_class"],
                name=way_dict["name"],
                oneway=way_dict["oneway"],
                maxspeed=way_dict["maxspeed"],
                bridge=way_dict["bridge"],
                tunnel=way_dict["tunnel"],
                layer=way_dict["layer"],
                surface=way_dict["surface"],
                access=way_dict["access"],
                length_m=round(total_length, 2),
                coordinates=coords,
            )
            resolved += 1
            if limit and resolved >= limit:
                break

        logger.info(
            "road_ways_resolved",
            resolved=resolved,
            skipped_no_coords=skipped_no_coords,
        )

    # -------------------------------------------------------------------------
    # Original Pass (backward-compatible): Road Ways without Coordinates
    # -------------------------------------------------------------------------
    def parse_road_ways(
        self,
        allowed_highways: set[str] | None = None,
        limit: int | None = None,
    ) -> Iterator[tuple[dict[str, Any], list[int]]]:
        """Stream road ways with tags and referenced node IDs."""
        if allowed_highways is None:
            allowed_highways = self.HIGHWAY_CLASSES

        with open(self.pbf_path, "rb") as f:
            yielded = 0
            while True:
                header_len_bytes = f.read(4)
                if not header_len_bytes or len(header_len_bytes) < 4:
                    break
                header_len = struct.unpack(">I", header_len_bytes)[0]
                blob_header_data = f.read(header_len)
                blob_header = self._parse_protobuf_fields(blob_header_data)

                block_type = blob_header.get(1, [b""])[0].decode("utf-8", errors="ignore")
                blob_size = blob_header.get(3, [0])[0]

                blob_data = f.read(blob_size)
                blob = self._parse_protobuf_fields(blob_data)

                raw_data = None
                if 1 in blob:
                    raw_data = blob[1][0]
                elif 3 in blob:
                    raw_data = zlib.decompress(blob[3][0])

                if not raw_data or block_type != "OSMData":
                    continue

                pblock = self._parse_protobuf_fields(raw_data)
                string_table: list[str] = []
                if 1 in pblock:
                    st_fields = self._parse_protobuf_fields(pblock[1][0])
                    string_table = [s.decode("utf-8", errors="replace") for s in st_fields.get(1, [])]

                for pg_bytes in pblock.get(2, []):
                    pg = self._parse_protobuf_fields(pg_bytes)
                    for way_bytes in pg.get(3, []):
                        w = self._parse_protobuf_fields(way_bytes)
                        way_id = w.get(1, [0])[0]
                        keys_data = w.get(2, [b""])[0]
                        vals_data = w.get(3, [b""])[0]

                        tags: dict[str, str] = {}
                        if keys_data and vals_data:
                            kp = 0
                            vp = 0
                            while kp < len(keys_data) and vp < len(vals_data):
                                k_idx, kp = self._read_varint(keys_data, kp)
                                v_idx, vp = self._read_varint(vals_data, vp)
                                k_str = string_table[k_idx] if k_idx < len(string_table) else ""
                                v_str = string_table[v_idx] if v_idx < len(string_table) else ""
                                tags[k_str] = v_str

                        hw = tags.get("highway")
                        if not hw or (allowed_highways and hw not in allowed_highways):
                            continue

                        # Decode delta-encoded refs (field 8)
                        refs_data = w.get(8, [b""])[0]
                        node_refs: list[int] = []
                        if refs_data:
                            rp = 0
                            curr_node = 0
                            while rp < len(refs_data):
                                raw_delta, rp = self._read_varint(refs_data, rp)
                                # sint64 unzigzag: (n >> 1) ^ (-(n & 1))
                                delta = (raw_delta >> 1) ^ (-(raw_delta & 1))
                                curr_node += delta
                                node_refs.append(curr_node)

                        if len(node_refs) >= 2:
                            way_dict = {
                                "way_id": way_id,
                                "highway_class": hw,
                                "name": tags.get("name"),
                                "oneway": tags.get("oneway") in ("yes", "1", "true"),
                                "maxspeed": int(tags["maxspeed"]) if tags.get("maxspeed", "").isdigit() else None,
                                "bridge": tags.get("bridge") in ("yes", "1", "true"),
                                "tunnel": tags.get("tunnel") in ("yes", "1", "true"),
                                "layer": int(tags["layer"]) if tags.get("layer", "").lstrip("-").isdigit() else 0,
                                "surface": tags.get("surface"),
                                "access": tags.get("access"),
                            }
                            yield way_dict, node_refs
                            yielded += 1
                            if limit and yielded >= limit:
                                return
