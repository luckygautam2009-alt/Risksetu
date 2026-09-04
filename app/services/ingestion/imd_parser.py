"""
India Meteorological Department (IMD) Rainfall dataset parser and normalizer.

Converts wide-format sub-divisional monthly rainfall (1901-2017) from database/Sub_Division_IMD_2017.csv
into normalized long-form observations and computes derived 117-year climatology baselines.
"""
from __future__ import annotations

import collections
import csv
from dataclasses import dataclass
import hashlib
import math
from typing import Iterator


@dataclass
class IMDSubdivisionRecord:
    subdivision_name: str
    normalized_name: str


@dataclass
class IMDObservationRecord:
    subdivision_name: str
    year: int
    month: int
    rainfall_mm: float | None
    source_record_hash: str


@dataclass
class IMDClimatologyRecord:
    subdivision_name: str
    month: int
    years_used: int
    mean_mm: float
    stddev_mm: float
    min_mm: float
    max_mm: float
    source_period_start: int
    source_period_end: int
    calculation_version: str


class IMDRainfallParser:
    """Parser and normalizer for IMD historical rainfall data."""

    MONTHS = [
        ("JAN", 1), ("FEB", 2), ("MAR", 3), ("APR", 4),
        ("MAY", 5), ("JUN", 6), ("JUL", 7), ("AUG", 8),
        ("SEP", 9), ("OCT", 10), ("NOV", 11), ("DEC", 12),
    ]

    def __init__(self, csv_path: str) -> None:
        self.csv_path = csv_path

    @staticmethod
    def normalize_subdivision_name(name: str) -> str:
        """Standardize subdivision name for controlled administrative joins."""
        n = name.strip()
        # Normalization rules
        n = n.replace("&", "and")
        n = " ".join(n.split())
        return n.upper()

    @staticmethod
    def compute_hash(subdivision: str, year: int, month: int, rainfall: float | None) -> str:
        """Compute deterministic SHA-256 hash for observation record."""
        rf_str = f"{rainfall:.2f}" if rainfall is not None else "NULL"
        h = hashlib.sha256()
        h.update(f"{subdivision.strip()}|{year}|{month}|{rf_str}".encode("utf-8"))
        return h.hexdigest()

    def get_subdivisions(self) -> list[IMDSubdivisionRecord]:
        """Extract unique meteorological subdivisions from CSV."""
        subdivs: dict[str, str] = {}
        with open(self.csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for r in reader:
                s_name = r.get("SUBDIVISION", "").strip()
                if s_name and s_name not in subdivs:
                    subdivs[s_name] = self.normalize_subdivision_name(s_name)

        return [
            IMDSubdivisionRecord(subdivision_name=k, normalized_name=v)
            for k, v in sorted(subdivs.items())
        ]

    def parse_observations(self) -> Iterator[IMDObservationRecord]:
        """Stream normalized long-form monthly observations."""
        with open(self.csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for r in reader:
                s_name = r.get("SUBDIVISION", "").strip()
                if not s_name:
                    continue

                try:
                    year = int(r.get("YEAR", "0").strip())
                except ValueError:
                    continue

                if year < 1800 or year > 2100:
                    continue

                for col_name, month_num in self.MONTHS:
                    raw_val = r.get(col_name, "").strip()
                    rainfall: float | None = None
                    if raw_val and raw_val.upper() not in ("NA", "NAN", "NULL", "N/A", ""):
                        try:
                            val = float(raw_val)
                            if val >= 0.0:
                                rainfall = val
                        except ValueError:
                            rainfall = None

                    rec_hash = self.compute_hash(s_name, year, month_num, rainfall)
                    yield IMDObservationRecord(
                        subdivision_name=s_name,
                        year=year,
                        month=month_num,
                        rainfall_mm=rainfall,
                        source_record_hash=rec_hash,
                    )

    def calculate_climatology(
        self,
        observations: list[IMDObservationRecord],
        version: str = "v1.0",
    ) -> list[IMDClimatologyRecord]:
        """Calculate 117-year climatology baseline from observation list."""
        # Group by (subdivision_name, month) -> list of valid rainfall values
        groups: dict[tuple[str, int], list[float]] = collections.defaultdict(list)
        years_range: dict[str, tuple[int, int]] = {}

        for obs in observations:
            if obs.rainfall_mm is not None:
                groups[(obs.subdivision_name, obs.month)].append(obs.rainfall_mm)
                if obs.subdivision_name not in years_range:
                    years_range[obs.subdivision_name] = (obs.year, obs.year)
                else:
                    curr_min, curr_max = years_range[obs.subdivision_name]
                    years_range[obs.subdivision_name] = (min(curr_min, obs.year), max(curr_max, obs.year))

        climatology_records: list[IMDClimatologyRecord] = []
        for (s_name, month), vals in sorted(groups.items()):
            if not vals:
                continue

            n = len(vals)
            mean_val = sum(vals) / n
            variance = sum((x - mean_val) ** 2 for x in vals) / n if n > 1 else 0.0
            stddev_val = math.sqrt(variance)
            min_val = min(vals)
            max_val = max(vals)
            start_yr, end_yr = years_range.get(s_name, (1901, 2017))

            climatology_records.append(
                IMDClimatologyRecord(
                    subdivision_name=s_name,
                    month=month,
                    years_used=n,
                    mean_mm=round(mean_val, 2),
                    stddev_mm=round(stddev_val, 2),
                    min_mm=round(min_val, 2),
                    max_mm=round(max_val, 2),
                    source_period_start=start_yr,
                    source_period_end=end_yr,
                    calculation_version=version,
                )
            )

        return climatology_records
