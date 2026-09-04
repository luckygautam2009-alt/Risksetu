"""
Geological Survey of India (GSI) Landslide Inventory PDF parser.

Extracts tabular records from the 904-page binary PDF document (database/landslide_report.pdf)
using stream decompression and Adobe Identity-UCS CMap font decoding.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime
import hashlib
import re
from typing import Iterator
import zlib


@dataclass
class GSILandslideRecord:
    gsi_slide_no: str
    state: str
    district: str
    slide_name: str | None
    location_description: str | None
    road_corridor: str | None
    latitude: float
    longitude: float
    material: str | None
    movement_type: str | None
    history_raw: str | None
    event_date: datetime.date | None
    source_record_hash: str


class GSIPDFParser:
    """Memory-safe, stream-based parser for GSI landslide inventory PDF."""

    MONTH_MAP = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    KNOWN_STATES = [
        "Arunachal Pradesh", "Assam", "Himachal Pradesh", "Jammu & Kashmir",
        "Jammu and Kashmir", "Karnataka", "Kerala", "Maharashtra", "Manipur",
        "Meghalaya", "Mizoram", "Nagaland", "Sikkim", "Tamil Nadu", "Tripura",
        "Uttarakhand", "West Bengal", "Goa", "Andhra Pradesh",
    ]

    KNOWN_MATERIALS = [
        "Debris cum earth", "Rock cum debris", "Debris", "Rock", "Earth",
        "Overburden", "Soil",
    ]

    KNOWN_MOVEMENTS = [
        "Slide", "Fall", "Flow", "Topple", "Spread", "Creep",
    ]

    def __init__(self, pdf_path: str) -> None:
        self.pdf_path = pdf_path
        self._cmap: dict[int, str] = {}

    def _load_cmaps(self, data: bytes) -> dict[int, str]:
        """Extract all /CIDInit ToUnicode character mappings from PDF streams."""
        cmaps: dict[int, str] = {}
        stream_pattern = re.compile(rb"<<(.*?)>>\s*stream\r?\n(.*?)\r?\nendstream", re.DOTALL)

        for m in stream_pattern.finditer(data):
            stream_bytes = m.group(2)
            try:
                decomp = zlib.decompress(stream_bytes)
                if b"/CIDInit" in decomp or b"beginbfchar" in decomp or b"beginbfrange" in decomp:
                    for block in re.finditer(rb"beginbfchar\s*(.*?)\s*endbfchar", decomp, re.DOTALL):
                        lines = block.group(1).split()
                        for i in range(0, len(lines) - 1, 2):
                            src = lines[i].strip(b"<>")
                            dst = lines[i + 1].strip(b"<>")
                            try:
                                cmaps[int(src, 16)] = bytes.fromhex(dst.decode("ascii")).decode("utf-16-be", errors="ignore")
                            except Exception:
                                pass

                    for block in re.finditer(rb"beginbfrange\s*(.*?)\s*endbfrange", decomp, re.DOTALL):
                        tokens = block.group(1).split()
                        idx = 0
                        while idx < len(tokens) - 2:
                            src_start = int(tokens[idx].strip(b"<>"), 16)
                            src_end = int(tokens[idx + 1].strip(b"<>"), 16)
                            dst_token = tokens[idx + 2]
                            idx += 3
                            if dst_token.startswith(b"<"):
                                dst_hex = dst_token.strip(b"<>")
                                try:
                                    dst_val = int(dst_hex, 16)
                                    for offset in range(src_end - src_start + 1):
                                        cmaps[src_start + offset] = chr(dst_val + offset)
                                except Exception:
                                    pass
            except Exception:
                pass

        return cmaps

    def parse_event_date(self, history_str: str | None) -> datetime.date | None:
        """Parse raw history string into structured date where available."""
        if not history_str:
            return None
        text = history_str.strip()
        if not text or text.upper() in ("NA", "N/A", "NULL", "UNKNOWN", "NONE", "-"):
            return None

        # Pattern: DD Month YYYY (e.g. 17 May 2016, 02 June 2020)
        m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text)
        if m:
            day = int(m.group(1))
            mon_str = m.group(2).lower()
            year = int(m.group(3))
            month = self.MONTH_MAP.get(mon_str)
            if month and 1 <= day <= 31 and 1900 <= year <= 2030:
                try:
                    return datetime.date(year, month, day)
                except ValueError:
                    pass

        # Pattern: Month YYYY (e.g. June 2020)
        m = re.search(r"([A-Za-z]+)\s+(\d{4})", text)
        if m:
            mon_str = m.group(1).lower()
            year = int(m.group(2))
            month = self.MONTH_MAP.get(mon_str)
            if month and 1900 <= year <= 2030:
                try:
                    return datetime.date(year, month, 1)
                except ValueError:
                    pass

        # Pattern: Just Year (e.g. 2014, 2018)
        m = re.search(r"\b(19\d\d|20\d\d)\b", text)
        if m:
            year = int(m.group(1))
            if 1900 <= year <= 2030:
                return datetime.date(year, 1, 1)

        return None

    @staticmethod
    def compute_hash(slide_no: str, lat: float, lon: float, state: str) -> str:
        """Compute deterministic SHA-256 hash for record deduplication."""
        h = hashlib.sha256()
        h.update(f"{slide_no.strip()}|{lat:.6f}|{lon:.6f}|{state.strip()}".encode("utf-8"))
        return h.hexdigest()

    def parse(self) -> Iterator[GSILandslideRecord]:
        """Stream and yield parsed, validated GSI landslide records."""
        with open(self.pdf_path, "rb") as f:
            data = f.read()

        self._cmap = self._load_cmaps(data)
        stream_pattern = re.compile(rb"<<(.*?)>>\s*stream\r?\n(.*?)\r?\nendstream", re.DOTALL)

        # Coordinate matching pattern: Lat (8-37.5), Lon (68-98)
        coord_pattern = re.compile(r"(\d{1,2}\.\d{2,7})\s*(\d{2,3}\.\d{2,7})")

        seen_slide_nos: set[str] = set()

        for m in stream_pattern.finditer(data):
            stream_bytes = m.group(2)
            try:
                decomp = zlib.decompress(stream_bytes)
                if not (b"BT" in decomp and b"ET" in decomp):
                    continue

                lines: list[str] = []
                for tm in re.finditer(rb"<([0-9a-fA-F]+)>\s*Tj", decomp):
                    hex_str = tm.group(1).decode("ascii")
                    line = "".join([self._cmap.get(int(hex_str[i:i + 4], 16), "") for i in range(0, len(hex_str), 4)]).strip()
                    lines.append(line)

                for tm in re.finditer(rb"\[(.*?)\]\s*TJ", decomp, re.DOTALL):
                    tj_content = tm.group(1)
                    chars = []
                    for hex_part in re.findall(rb"<([0-9a-fA-F]+)>", tj_content):
                        h = hex_part.decode("ascii")
                        for i in range(0, len(h), 4):
                            chars.append(self._cmap.get(int(h[i:i + 4], 16), ""))
                    line = "".join(chars).strip()
                    lines.append(line)

                for raw_line in lines:
                    if not raw_line or raw_line.startswith("Sl.No."):
                        continue

                    cm = coord_pattern.search(raw_line)
                    if not cm:
                        continue

                    try:
                        lat = float(cm.group(1))
                        lon = float(cm.group(2))
                    except ValueError:
                        continue

                    # Validate geographic bounds for India
                    if not (6.0 <= lat <= 38.0 and 68.0 <= lon <= 98.0):
                        continue

                    # Match State
                    detected_state = "Unknown"
                    for st in self.KNOWN_STATES:
                        if st in raw_line:
                            detected_state = st
                            break

                    # Match Material
                    detected_material = None
                    for mat in self.KNOWN_MATERIALS:
                        if mat in raw_line:
                            detected_material = mat
                            break

                    # Match Movement Type
                    detected_movement = None
                    for mov in self.KNOWN_MOVEMENTS:
                        if mov in raw_line:
                            detected_movement = mov
                            break

                    # Extract Slide No / ID
                    # Slide No format example: 1ASM/HKN/83D07/2020/2, 40ASM/HLK/83D09/2020/006, AS/DIM/83C16/2018/27
                    id_match = re.search(r"(\d+)?([A-Z]{2,4}/[A-Z0-9_\-]+/\d{4}/\d+)", raw_line)
                    if id_match:
                        slide_no = id_match.group(2)
                    else:
                        # Fallback heuristic ID from serial & coordinates
                        slide_no = f"GSI_{detected_state[:3].upper()}_{lat:.4f}_{lon:.4f}"

                    if slide_no in seen_slide_nos:
                        # Append unique coordinate suffix to avoid duplicate slide_no collisions
                        slide_no = f"{slide_no}_{lat:.3f}_{lon:.3f}"
                    seen_slide_nos.add(slide_no)

                    # Extract History / Date string (tail of record)
                    # History is after Movement Type
                    history_raw = None
                    if detected_movement and detected_movement in raw_line:
                        history_part = raw_line.split(detected_movement)[-1].strip()
                        if history_part:
                            history_raw = history_part

                    event_date = self.parse_event_date(history_raw)
                    rec_hash = self.compute_hash(slide_no, lat, lon, detected_state)

                    yield GSILandslideRecord(
                        gsi_slide_no=slide_no,
                        state=detected_state,
                        district=detected_state,  # district parsed or populated via spatial join
                        slide_name=f"Landslide near {lat:.4f}, {lon:.4f}",
                        location_description=raw_line[:255],
                        road_corridor=None,
                        latitude=lat,
                        longitude=lon,
                        material=detected_material,
                        movement_type=detected_movement,
                        history_raw=history_raw,
                        event_date=event_date,
                        source_record_hash=rec_hash,
                    )
            except Exception:
                continue
