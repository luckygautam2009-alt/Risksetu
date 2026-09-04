"""
Census 2011 Primary Census Abstract (PCA) and Table A-1 streaming parser.

Uses streaming XML SAX parsing (xml.etree.ElementTree.iterparse) on OpenXML spreadsheet archives
to prevent memory exhaustion on 300+ MB Excel files (2.1 GB uncompressed XML).
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterator
import xml.etree.ElementTree as ET
import zipfile


@dataclass
class CensusVillageRecord:
    state_code: str
    district_code: str
    subdistrict_code: str
    village_code: str
    name: str
    level: str
    rural_urban: str
    total_population: int
    male_population: int
    female_population: int
    households: int
    child_population_0_6: int
    sc_population: int
    st_population: int
    literate_population: int
    illiterate_population: int
    working_population: int
    cultivators: int
    agricultural_labourers: int
    census_year: int
    source_record_hash: str


@dataclass
class CensusAreaRefRecord:
    state_code: str
    district_code: str
    subdistrict_code: str
    level: str
    name: str
    rural_urban: str
    inhabited_villages: int | None
    uninhabited_villages: int | None
    number_of_towns: int | None
    households: int | None
    population_persons: int | None
    area_sq_km: float | None
    population_density_per_sq_km: float | None
    source_record_hash: str


class CensusPCAParser:
    """Memory-safe streaming parser for 2011-IndiaStateDistSbDistVill-0000.xlsx."""

    def __init__(self, xlsx_path: str) -> None:
        self.xlsx_path = xlsx_path

    @staticmethod
    def compute_hash(st: str, dt: str, sdt: str, vil: str, pop: int, hh: int) -> str:
        """Compute deterministic SHA-256 hash for census record."""
        h = hashlib.sha256()
        h.update(f"{st}|{dt}|{sdt}|{vil}|{pop}|{hh}".encode("utf-8"))
        return h.hexdigest()

    def _load_shared_strings(self, z: zipfile.ZipFile) -> list[str]:
        """Load OpenXML sharedStrings.xml table efficiently."""
        sst: list[str] = []
        if "xl/sharedStrings.xml" not in z.namelist():
            return sst

        with z.open("xl/sharedStrings.xml") as sst_f:
            for _, elem in ET.iterparse(sst_f):
                if elem.tag.endswith("}t") or elem.tag == "t":
                    sst.append(elem.text or "")
                elem.clear()
        return sst

    def parse_villages(
        self,
        target_levels: set[str] | None = None,
        target_states: set[str] | None = None,
        limit: int | None = None,
    ) -> Iterator[CensusVillageRecord]:
        """Stream village demographic records from Census PCA Sheet 1."""
        if target_levels is None:
            target_levels = {"VILLAGE", "TOWN"}

        with zipfile.ZipFile(self.xlsx_path, "r") as z:
            sst = self._load_shared_strings(z)

            if "xl/worksheets/sheet1.xml" not in z.namelist():
                return

            yielded_count = 0
            with z.open("xl/worksheets/sheet1.xml") as s1_f:
                for _, elem in ET.iterparse(s1_f):
                    if not (elem.tag.endswith("}row") or elem.tag == "row"):
                        continue

                    r_num = elem.attrib.get("r", "0")
                    if r_num == "1":
                        # Header row
                        elem.clear()
                        continue

                    # Extract cell values in column order
                    cols: list[str] = []
                    for c in elem.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                        t = c.attrib.get("t")
                        v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                        v_text = v.text if v is not None else None
                        v_str = (v_text or "").strip()
                        if t == "s" and v_str.isdigit() and int(v_str) < len(sst):
                            cols.append(sst[int(v_str)].strip())
                        else:
                            cols.append(v_str)

                    elem.clear()

                    if len(cols) < 14:
                        continue

                    # Column mapping based on PCA schema:
                    # 0: State, 1: District, 2: Subdistt, 3: Town/Village, 4: Ward, 5: EB, 6: Level, 7: Name, 8: TRU,
                    # 9: No_HH, 10: TOT_P, 11: TOT_M, 12: TOT_F, 13: P_06, ...
                    st_code = cols[0].zfill(2)
                    dt_code = cols[1].zfill(3)
                    sdt_code = cols[2].zfill(5)
                    vil_code = cols[3].zfill(6)
                    level = cols[6].upper()
                    name = cols[7]
                    rural_urban = cols[8]

                    if target_levels and level not in target_levels:
                        continue

                    if target_states and st_code not in target_states:
                        continue

                    def to_int(idx: int) -> int:
                        if idx < len(cols):
                            try:
                                return max(0, int(float(cols[idx])))
                            except ValueError:
                                return 0
                        return 0

                    hh = to_int(9)
                    tot_p = to_int(10)
                    tot_m = to_int(11)
                    tot_f = to_int(12)
                    p_06 = to_int(13)

                    # Demographics (SC, ST, Literacy, Workers)
                    p_sc = to_int(16)
                    p_st = to_int(19)
                    p_lit = to_int(22)
                    p_ill = to_int(25)
                    tot_work = to_int(28)
                    cultivators = to_int(34)
                    agri_labourers = to_int(37)

                    rec_hash = self.compute_hash(st_code, dt_code, sdt_code, vil_code, tot_p, hh)

                    yield CensusVillageRecord(
                        state_code=st_code,
                        district_code=dt_code,
                        subdistrict_code=sdt_code,
                        village_code=vil_code,
                        name=name,
                        level=level,
                        rural_urban=rural_urban,
                        total_population=tot_p,
                        male_population=tot_m,
                        female_population=tot_f,
                        households=hh,
                        child_population_0_6=p_06,
                        sc_population=p_sc,
                        st_population=p_st,
                        literate_population=p_lit,
                        illiterate_population=p_ill,
                        working_population=tot_work,
                        cultivators=cultivators,
                        agricultural_labourers=agri_labourers,
                        census_year=2011,
                        source_record_hash=rec_hash,
                    )

                    yielded_count += 1
                    if limit and yielded_count >= limit:
                        break


class CensusA1Parser:
    """Parser for A-1_NO_OF_VILLAGES_TOWNS_HOUSEHOLDS_POPULATION_AND_AREA.xlsx."""

    def __init__(self, xlsx_path: str) -> None:
        self.xlsx_path = xlsx_path

    @staticmethod
    def compute_hash(st: str, dt: str, sdt: str, level: str, tru: str) -> str:
        h = hashlib.sha256()
        h.update(f"{st}|{dt}|{sdt}|{level}|{tru}".encode("utf-8"))
        return h.hexdigest()

    def parse_area_reference(self) -> Iterator[CensusAreaRefRecord]:
        """Stream area and village counts from Table A-1."""
        with zipfile.ZipFile(self.xlsx_path, "r") as z:
            # Load sharedStrings
            sst: list[str] = []
            if "xl/sharedStrings.xml" in z.namelist():
                with z.open("xl/sharedStrings.xml") as sst_f:
                    for _, elem in ET.iterparse(sst_f):
                        if elem.tag.endswith("}t") or elem.tag == "t":
                            sst.append(elem.text or "")
                        elem.clear()

            with z.open("xl/worksheets/sheet1.xml") as s1_f:
                for _, elem in ET.iterparse(s1_f):
                    if not (elem.tag.endswith("}row") or elem.tag == "row"):
                        continue

                    r_num = int(elem.attrib.get("r", "0"))
                    if r_num < 5:  # skip header rows (rows 1-4)
                        elem.clear()
                        continue

                    cols: list[str] = []
                    for c in elem.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                        t = c.attrib.get("t")
                        v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                        v_text = v.text if v is not None else None
                        v_str = (v_text or "").strip()
                        if t == "s" and v_str.isdigit() and int(v_str) < len(sst):
                            cols.append(sst[int(v_str)].strip())
                        else:
                            cols.append(v_str)

                    elem.clear()

                    if len(cols) < 6:
                        continue

                    st_code = cols[0].zfill(2)
                    dt_code = cols[1].zfill(3)
                    sdt_code = cols[2].zfill(5)
                    level = cols[3].upper()
                    name = cols[4]
                    tru = cols[5]

                    def to_int_opt(idx: int) -> int | None:
                        if idx < len(cols) and cols[idx]:
                            try:
                                return max(0, int(float(cols[idx])))
                            except ValueError:
                                return None
                        return None

                    def to_float_opt(idx: int) -> float | None:
                        if idx < len(cols) and cols[idx]:
                            try:
                                return max(0.0, float(cols[idx]))
                            except ValueError:
                                return None
                        return None

                    inhabited_vil = to_int_opt(6)
                    uninhabited_vil = to_int_opt(7)
                    num_towns = to_int_opt(8)
                    hh = to_int_opt(9)
                    pop = to_int_opt(10)
                    area = to_float_opt(13)
                    density = to_float_opt(14)

                    rec_hash = self.compute_hash(st_code, dt_code, sdt_code, level, tru)

                    yield CensusAreaRefRecord(
                        state_code=st_code,
                        district_code=dt_code,
                        subdistrict_code=sdt_code,
                        level=level,
                        name=name,
                        rural_urban=tru,
                        inhabited_villages=inhabited_vil,
                        uninhabited_villages=uninhabited_vil,
                        number_of_towns=num_towns,
                        households=hh,
                        population_persons=pop,
                        area_sq_km=area,
                        population_density_per_sq_km=density,
                        source_record_hash=rec_hash,
                    )
